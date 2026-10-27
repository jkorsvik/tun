#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a standalone survey board: one self-contained HTML file, no server.

Reads answers in long format, one row per answer given:

    Enhet,Rolle,Sporsmal,Svar
    Okonomi,Ledelse,Hvordan var oppfolgingen,5 Svart enig
    ...

and writes a file that opens from disk, filters by the segment columns, and prints
one stacked card per question with the count and the share of each option.

Two rules are built in, not left to whoever assembles the file:

  * **nothing that identifies a respondent is read.** The builder takes the
    question column, the answer column and the segment columns; every other column
    is dropped before anything is written. Only answers are counted, never people.
  * **a cell with fewer than ``--min-cell`` answers is hidden** (k-anonymity),
    both per question and per option. A count of three in a small unit points at
    three people, so the number is withheld and the page says why.
  * **a cross-tab gets its own rule, not the one above.** Two questions multiplied is
    how a small group becomes one person, and a per-cell floor is not enough there: the
    question totals are on the page, so one withheld cell is recovered by subtracting
    the visible ones from the total. So a pair is printed only when every combination
    reaches the floor, and dropped with its reason otherwise. See ``cross_tables``.

A cross-tab needs ``--wide`` input, one row per respondent: it is the row boundary
that says which answers belong to the same person. The long format carries no such
boundary, so the builder refuses to guess one.

Free text is not supported, at all: no threshold can anonymise a sentence, so a
builder that accepted one would ship the exception that breaks the rule.

Stdlib only, like the rest of tools/. Python 3.8+.

    python3 tools/build_survey_dashboard.py \\
      --data examples/27-survey-board/survey.csv \\
      --title "Arbeidsmiljo 2026" \\
      --segments Enhet,Rolle \\
      --source "Syntetisk eksempeldata (survey.csv)" \\
      --requested-by "HR" \\
      --out examples/27-survey-board/survey.html
"""
from __future__ import annotations

import argparse
import collections
import datetime
import html
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import build_stamp  # noqa: E402
import build_size  # noqa: E402
import feedback_link  # noqa: E402
import i18n  # noqa: E402
import tun_core  # noqa: E402
import tun_tokens  # noqa: E402
from tun_tokens import strip_css_comments  # noqa: E402
from tun_core import NOT_STATED, die  # noqa: E402

TEMPLATE = ROOT / "templates" / "survey-dashboard.html"
STRINGS = "survey-dashboard"
MIN_CELL_DEFAULT = 5
MAX_ANSWERS = 400_000        # above this the file stops being attachable; see build_size

# die and NOT_STATED are tun_core's, so a refusal reads the same from every builder.


def load_answers(path: pathlib.Path, q_col: str, a_col: str, segments: list[str]) -> list[dict]:
    # tun_core reads the table, so a semicolon export from a Norwegian Excel gets the same
    # columns as a comma one instead of arriving as a single column called "Q;A;Enhet".
    table = tun_core.read_rows(path)
    have = tun_core.columns(table)
    if not have:
        die(f"{path.name} has no rows and no header")
    for col in [q_col, a_col] + segments:
        if col not in have:
            die(f"column {col!r} is not in {path.name}. Available: {', '.join(have)}")
    rows = []
    for row in table:
        q = (row.get(q_col) or "").strip()
        a = (row.get(a_col) or "").strip()
        if not q or not a:
            continue
        rows.append({"q": q, "a": a, "seg": [(row.get(c) or "").strip() for c in segments],
                     "r": None})
    return rows


def load_wide(path: pathlib.Path, questions: list[str], segments: list[str]) -> list[dict]:
    """One row per respondent; one answer row per question, carrying its respondent.

    ``r`` is the row number in the file. It exists only so two answers can be known to
    come from the same person, and it is never written into the page.
    """
    table = tun_core.read_rows(path)
    have = tun_core.columns(table)
    if not have:
        die(f"{path.name} has no rows and no header")
    for col in questions + segments:
        if col not in have:
            die(f"column {col!r} is not in {path.name}. Available: {', '.join(have)}")
    rows = []
    for r, row in enumerate(table):
        seg = [(row.get(c) or "").strip() for c in segments]
        for q in questions:
            a = (row.get(q) or "").strip()
            if a:
                rows.append({"q": q, "a": a, "seg": seg, "r": r})
    return rows


def aggregate(rows: list[dict], min_cell: int) -> dict:
    """Questions, options and the counts, with the suppression rule applied once.

    Returns the JSON the page carries plus the cards for the no-JS view, so the
    file a reader gets is complete before any script runs.
    """
    questions: list[str] = []
    options: list[list[str]] = []
    q_index: dict[str, int] = {}
    o_index: list[dict[str, int]] = []
    seg_values: list[list[str]] = [[] for _ in rows[0]["seg"]] if rows else []
    seg_seen: list[set] = [set() for _ in seg_values]

    for row in rows:
        if row["q"] not in q_index:
            q_index[row["q"]] = len(questions)
            questions.append(row["q"])
            options.append([])
            o_index.append({})
        qi = q_index[row["q"]]
        if row["a"] not in o_index[qi]:
            o_index[qi][row["a"]] = len(options[qi])
            options[qi].append(row["a"])
        for s, value in enumerate(row["seg"]):
            if value not in seg_seen[s]:
                seg_seen[s].add(value)
                seg_values[s].append(value)

    packed = []
    for row in rows:
        qi = q_index[row["q"]]
        packed.append([qi, o_index[qi][row["a"]]] + [seg_values[s].index(v)
                                                     for s, v in enumerate(row["seg"])])
    return {"questions": questions, "options": options,
            "segments": [], "segmentValues": seg_values, "rows": packed,
            "minCell": min_cell}


def parse_pairs(raw: list[str]) -> list[tuple[str, str]]:
    pairs = []
    for item in raw:
        for chunk in item.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            bits = [b.strip() for b in chunk.split("|")]
            if len(bits) != 2 or not all(bits):
                die(f'--cross wants "Question A|Question B", got {chunk!r}')
            pairs.append((bits[0], bits[1]))
    return pairs


def cross_tables(rows: list[dict], pairs: list[tuple[str, str]], min_cell: int) -> list[dict]:
    """One table per question pair, with the rule a cross-tab needs.

    The rule is all or nothing, and the reason is on the page: the question totals are
    already printed above every table, so a single withheld cell is recovered by
    subtracting the visible ones from the total. Partial suppression in a cross-tab
    therefore buys nothing, and hiding a second cell to stop the subtraction starts a
    cascade that ends with the whole table hidden. So a pair is printed only when every
    combination it contains reaches the floor; otherwise the table is dropped and the
    page says why. A zero cell is not identifying and does not block a table.

    Two limits worth knowing, both stated on the page:
      * the rule protects a count, not a pattern: the same group described across
        several tables is still a group;
      * it is deliberately blunt. On a 5 by 5 matrix a single small cell removes the
        table, and the reader gets a reason instead of a number.
    """
    if any(row["r"] is None for row in rows):
        die("--cross needs --wide input (one row per respondent): the long format does not "
            "say which answers belong to the same person, and guessing would invent a table")

    q_opts: dict[str, list[str]] = {}
    o_index: dict[str, dict[str, int]] = {}
    for row in rows:
        idx = o_index.setdefault(row["q"], {})
        if row["a"] not in idx:
            idx[row["a"]] = len(idx)
            q_opts.setdefault(row["q"], []).append(row["a"])

    answered: dict[int, dict[str, int]] = collections.defaultdict(dict)
    for row in rows:
        answered[row["r"]][row["q"]] = o_index[row["q"]][row["a"]]

    tables = []
    for qa, qb in pairs:
        for q in (qa, qb):
            if q not in q_opts:
                die(f"--cross names a question that is not in the data: {q!r}. "
                    f"Questions: {'; '.join(sorted(q_opts))}")
        cells = [[0] * len(q_opts[qb]) for _ in q_opts[qa]]
        n = 0
        for resp in answered.values():
            if qa in resp and qb in resp:
                cells[resp[qa]][resp[qb]] += 1
                n += 1
        if not n:
            continue
        thin = [(i, j) for i, row in enumerate(cells) for j, v in enumerate(row)
                if 0 < v < min_cell]
        tables.append({"a": qa, "b": qb, "optionsA": q_opts[qa], "optionsB": q_opts[qb],
                       "cells": cells, "n": n,
                       "dropped": bool(thin), "thin": len(thin)})
    return tables


def cell_cards(data: dict, t: dict, num) -> tuple[str, str]:
    """The unfiltered view, painted by the builder: the page's no-JS content."""
    questions, options, rows = data["questions"], data["options"], data["rows"]
    counts = [collections.Counter() for _ in questions]
    totals = collections.Counter()
    for qi, oi, *_ in rows:
        counts[qi][oi] += 1
        totals[qi] += 1

    hidden = 0
    cards = []
    for qi, question in enumerate(questions):
        n = totals[qi]
        if not n:
            continue
        if n < data["minCell"]:
            hidden += 1
            cards.append(
                f'<section class="q"><h2>{html.escape(question)}</h2>'
                f'<div class="supp"><strong>{t["suppressed_head"]}</strong>'
                f'{t["suppressed_body"]}</div></section>')
            continue
        stack = "".join(
            f'<span style="width:{counts[qi][oi] / n * 100:.2f}%;background:var(--cat-{(oi % 5) + 1})"></span>'
            for oi, option in enumerate(options[qi]) if counts[qi][oi])
        lines = []
        for oi, option in enumerate(options[qi]):
            c = counts[qi][oi]
            shown = c >= data["minCell"]
            if c and not shown:
                hidden += 1
            value = (f'{num(c)}' if shown
                     else f'<i class="hidden">{t["suppressed_head"]}</i>')
            # c / n is a fraction; the cell says "per cent", and the script's own pct()
            # multiplies by 100. This one did not, so the static view -- the one a
            # reader gets before any filter is touched, and the only one where
            # scripting is blocked -- printed 0,2 % for 14 answers of 60.
            share = f'{num(c / n * 100, 1)} %' if shown else ""
            lines.append(
                f'<li><span class="k"><i class="sw" style="background:var(--cat-{(oi % 5) + 1})"></i>'
                f'{html.escape(option)}</span>'
                f'<span class="v">{value}</span><span class="p">{share}</span></li>')
        cards.append(
            f'<section class="q"><h2>{html.escape(question)}</h2>'
            f'<p class="n">{num(n)} {t["answered"]}</p>'
            f'<div class="stack" aria-hidden="true">{stack}</div>'
            f'<ul class="rows">{"".join(lines)}</ul></section>')

    kpis = (f'<li><span class="label">{t["kpi_answers"]}</span>'
            f'<span class="num">{num(len(rows))}</span></li>'
            f'<li><span class="label">{t["kpi_questions"]}</span>'
            f'<span class="num">{num(len(questions))}</span></li>'
            f'<li><span class="label">{t["kpi_suppressed"]}</span>'
            f'<span class="num">{num(hidden)}</span></li>')
    return "\n  ".join(cards), kpis


def cross_sections(tables: list[dict], t: dict, num) -> str:
    """The cross-tab blocks, painted by the builder and never recomputed in the page.

    One implementation of the rule is the point: a second one in JavaScript would drift
    from this one, and the drift would be invisible until it leaked.
    """
    out = []
    for tab in tables:
        opts_a, opts_b = tab["optionsA"], tab["optionsB"]
        if tab["dropped"]:
            out.append(f'<section class="x"><h2>{html.escape(t["cross_head"])}: '
                       f'{html.escape(tab["a"])} &times; {html.escape(tab["b"])}</h2>'
                       f'<div class="supp"><strong>{t["suppressed_head"]}</strong>'
                       f'{t["cross_dropped"]}</div></section>')
            continue
        head = "".join(f'<th scope="col">{html.escape(o)}</th>' for o in opts_b)
        body = []
        for i, oa in enumerate(opts_a):
            cells = [f'<td>{num(tab["cells"][i][j])}</td>' for j in range(len(opts_b))]
            body.append(f'<tr><th scope="row">{html.escape(oa)}</th>{"".join(cells)}'
                        f'<td class="t">{num(sum(tab["cells"][i]))}</td></tr>')
        foot = "".join(f'<td class="t">{num(sum(row[j] for row in tab["cells"]))}</td>'
                       for j in range(len(opts_b)))
        out.append(
            f'<section class="x"><h2>{html.escape(t["cross_head"])}: '
            f'{html.escape(tab["a"])} &times; {html.escape(tab["b"])}</h2>'
            f'<p class="n">{num(tab["n"])} {t["cross_answered"]}</p>'
            f'<div class="scroll"><table><thead><tr><th scope="col">'
            f'{html.escape(tab["a"])} \\ {html.escape(tab["b"])}</th>{head}'
            f'<th scope="col">{t["cross_total"]}</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody>'
            f'<tfoot><tr><th scope="row">{t["cross_total"]}</th>{foot}'
            f'<td class="t">{num(tab["n"])}</td></tr></tfoot></table></div>'
            f'<p class="note">{t["cross_note"]}</p></section>')
    return "\n  ".join(out)


def filter_fields(names: list[str], values: list[list[str]], t: dict) -> str:
    out = []
    for i, name in enumerate(names):
        opts = "".join(f'<option value="{j}">{html.escape(v)}</option>'
                       for j, v in enumerate(values[i]))
        out.append(f'<div class="field"><label for="s{i}">{html.escape(name)}</label>'
                   f'<select id="s{i}" name="s{i}"><option value="">{t["all"]}</option>'
                   f'{opts}</select></div>')
    return "\n    ".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True, help="CSV of answers, long format")
    ap.add_argument("--title", required=True)
    ap.add_argument("--segments", default="",
                    help="comma-separated columns to filter by, e.g. Enhet,Rolle")
    ap.add_argument("--question-col", default="Sporsmal", help="column holding the question")
    ap.add_argument("--wide", action="store_true",
                    help="one row per respondent, one column per question (needed for --cross)")
    ap.add_argument("--questions", default="",
                    help="with --wide: comma-separated question columns, in page order")
    ap.add_argument("--cross", action="append", default=[], metavar='"A|B"',
                    help='cross-tabulate two questions: "Question A|Question B", repeatable')
    ap.add_argument("--answer-col", default="Svar", help="column holding the chosen option")
    ap.add_argument("--min-cell", type=int, default=MIN_CELL_DEFAULT,
                    help=f"hide a cell with fewer answers than this (default {MIN_CELL_DEFAULT})")
    ap.add_argument("--source", default="", help="where the answers came from")
    ap.add_argument("--requested-by", default="", help="a role, not a person's name")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--feedback-to", default="", metavar="ADDRESS_OR_ISSUE_URL",
                    help=feedback_link.FLAG_HELP)
    i18n.add_lang_argument(ap)
    args = ap.parse_args(argv)
    t = i18n.load(STRINGS, args.lang)

    if not args.data.is_file():
        die(f"{args.data} not found")
    if not TEMPLATE.is_file():
        die(f"template missing: {TEMPLATE}")
    segments = [s.strip() for s in args.segments.split(",") if s.strip()]

    pairs = parse_pairs(args.cross)
    if pairs and not args.wide:
        die("--cross needs --wide input: one row per respondent is what says which answers "
            "belong to the same person, and the long format does not carry it")
    if args.wide:
        wide_questions = [q.strip() for q in args.questions.split(",") if q.strip()]
        if not wide_questions:
            die("--wide needs --questions: the columns to count, in page order")
        rows = load_wide(args.data, wide_questions, segments)
        if not rows:
            die(f"{args.data.name} has no answers in {', '.join(wide_questions)}")
    else:
        rows = load_answers(args.data, args.question_col, args.answer_col, segments)
        if not rows:
            die(f"{args.data.name} has no answers in {args.question_col!r} / {args.answer_col!r}")
    if len(rows) > MAX_ANSWERS:
        die(f"{len(rows):,} answers is beyond the {MAX_ANSWERS:,} this builder will inline. "
            f"Pre-aggregate to counts per question and option first.")

    data = aggregate(rows, args.min_cell)
    data["segments"] = segments

    def num(value, digits: int = 0) -> str:
        text = f"{value:,.{digits}f}"
        if t["dec"] == ",":
            text = text.replace(",", "\u00a0").replace(".", ",")
        return text

    cards, kpis = cell_cards(data, t, num)
    tables = cross_tables(rows, pairs, args.min_cell) if pairs else []
    cross = cross_sections(tables, t, num)
    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)
    source = i18n.fill(t["source_line"], name=args.source or args.data.name,
                       answers=f"{len(rows):,}", questions=len(data["questions"]))
    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=built,
                                           source=source, lang=args.lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # The tokens are inlined here rather than written into the template, so this page shares
    # one seam with every other artefact. auto_dark: a reader whose system is dark gets a dark
    # survey with no script.
    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css))
            .replace("{{TITLE}}", html.escape(args.title))
            .replace("{{SOURCE_DESCRIPTION}}", html.escape(source))
            .replace("{{EXTRACT_TIMESTAMP}}", extracted)
            .replace("{{BUILD_TIMESTAMP}}", built)
            .replace("{{REQUESTED_BY}}", args.requested_by or NOT_STATED)
            .replace("{{ANSWERS_INLINED}}", f"{len(rows):,}")
            .replace("{{MIN_CELL}}", str(args.min_cell))
            .replace("{{FILTER_FIELDS}}", filter_fields(segments, data["segmentValues"], t))
            .replace("{{KPI_CARDS}}", kpis)
            .replace("{{QUESTION_CARDS}}", cards)
            .replace("{{CROSS_SECTIONS}}", cross)
            .replace("{{SURVEY_DATA}}", payload)
            .replace("{{FEEDBACK_BLOCK}}", feedback))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")

    print(f"answers       : {len(rows):,}")
    print(f"questions     : {len(data['questions'])}")
    print(f"segments      : {', '.join(segments) or '(none)'}")
    print(f"hidden cells  : see the page (fewer than {args.min_cell} answers)")
    if pairs:
        kept = sum(1 for x in tables if not x["dropped"])
        print(f"cross-tabs    : {kept} of {len(tables)} shown, "
              f"{len(tables) - kept} dropped (a combination under {args.min_cell} answers)")
    print(f"wrote         : {args.out} ({args.out.stat().st_size / 1024:.1f} KB)")
    build_size.enforce(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
