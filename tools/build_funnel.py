#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a standalone funnel: how many reach each stage, and where the cohort leaks.

Most operational reporting is a funnel: how many cases start, how many get assessed, how many
are decided, how many are paid out. It is drawn badly almost everywhere, in two ways. The
stages are inferred from the data rather than declared, so the order is a guess presented as a
fact. And the drop between two stages is left as a gap in a picture, when the number a reader
wants is the difference.

    python3 tools/build_funnel.py \\
      --data examples/42-funnel/soknader.csv \\
      --id Soknadsnr --stage Status \\
      --stages "Mottatt,Vurdert,Innstilt,Utbetalt" \\
      --title "Soknader gjennom behandlingen" \\
      --source "Syntetisk eksempeldata (soknader.csv)" \\
      --requested-by "Saksbehandlingen" \\
      --out examples/42-funnel/tratt.html

What is built in, rather than left to whoever assembles the file:

  * **the stages are declared.** `--stages` gives the order; nothing is inferred from the
    data, because an inferred order is a guess with a picture drawn on top of it.
  * **the nesting is checked, because that is what makes it a funnel.** Reaching stage n+1
    means the same record passed stage n. A record that appears at a later stage without an
    earlier one is a defect in the extract, not a step in a funnel: the builder refuses and
    names how many records skip which stage. `--allow-skips` proceeds, and then the page says
    on its face that the stages are not nested.
  * **the width carries the count, and nothing else does.** Scaling both bar dimensions turns
    a 50 per cent drop into a 75 per cent loss of area. One dimension, stated on the page.
  * **both percentages are printed.** Of the first stage (overall conversion) and of the
    previous stage (step conversion). They answer different questions, and a page that shows
    one invites the reader to answer the other with it.
  * **the drop is a number.** "Minus 1 240 between these two stages" is what the reader asks
    for, and a gap in a picture does not say it.
  * **the worst step is named in words**, computed from the counts and never from a judgement
    about them: which pair of stages loses the largest share of the records that reached it.
  * **there is no script.** A filter would re-lay the drawing; every figure is on the page.

Stdlib only, like the rest of tools/. Python 3.8+.
"""
from __future__ import annotations

import argparse
import html
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import build_size  # noqa: E402
import build_stamp  # noqa: E402
import feedback_link  # noqa: E402
import i18n  # noqa: E402
import tun_core  # noqa: E402
import tun_tokens  # noqa: E402
from tun_tokens import strip_css_comments  # noqa: E402
from tun_core import NOT_STATED, die  # noqa: E402

TEMPLATE = ROOT / "templates" / "funnel.html"
STRINGS = "funnel"
MAX_STAGES = 9             # above this the labels have no room and the shape stops reading
MAX_BYTES = 40 * 1024 * 1024

# The canvas. Units, not pixels: the SVG scales, so a theme's font size cannot move a bar.
W = 1000
LEFT = 16
RIGHT = 16
ROW_H = 62                 # one stage: the bar, its name and its three figures
BAR_H = 34
NAME_H = 15                # the stage name under the bar
GAP = 10
HEAD_H = 24                # the column headers above the first row
COUNT_X = 560              # the count, right-anchored here
FIRST_X = 700              # the share of the first stage
REST_X = W - RIGHT         # the share of the previous stage and the number lost
LONGEST = COUNT_X - LEFT - 48   # the width of a bar holding every record


# ------------------------------------------------------------------------------ numbers
def fmt(value: int | float, lang: str) -> str:
    """A count as the reader's locale writes it."""
    text = f"{value:,.0f}"
    return text.replace(",", "\u00a0") if lang == "nb" else text.replace(",", "\u2009")


def pct_text(share: float, lang: str) -> str:
    """A conversion rate with one decimal, and a comma where the locale wants one."""
    text = f"{share * 100:.1f}"
    return (text.replace(".", ",") if lang == "nb" else text) + "\u00a0%"


# --------------------------------------------------------------------------------- load
def load(path: pathlib.Path, id_col: str, stage_col: str,
         stages: list[str]) -> tuple[list[dict], int, int]:
    """Count the distinct records that reached each stage, and check the stages are nested.

    Returns one entry per stage in the declared order, the number of collapsed duplicate
    (record, stage) rows, and how many records the file holds at all.
    """
    if not path.is_file():
        die(f"{path} does not exist")
    rows = tun_core.read_rows(path)
    if not rows:
        die(f"{path.name} has no rows")
    header = tun_core.columns(rows)
    for flag, name in (("--id", id_col), ("--stage", stage_col)):
        if name not in header:
            die(f"{flag} {name!r} is not a column in {path.name}. "
                f"Available: {', '.join(header)}")
    if len(set(stages)) != len(stages):
        die("--stages names the same stage twice, so the funnel would count it twice")
    if len(stages) < 2:
        die("--stages needs at least two stages: a funnel of one stage is a count")

    reached: dict[str, set[str]] = {stage: set() for stage in stages}
    seen: set[tuple[str, str]] = set()
    duplicates = 0
    unknown: dict[str, int] = {}
    missing_id = 0
    for row in rows:
        record = str(row.get(id_col) or "").strip()
        stage = str(row.get(stage_col) or "").strip()
        if not record:
            missing_id += 1
            continue
        if stage not in reached:
            unknown[stage] = unknown.get(stage, 0) + 1
            continue
        if (record, stage) in seen:
            duplicates += 1
            continue
        seen.add((record, stage))
        reached[stage].add(record)
    if missing_id:
        die(f"{missing_id} row(s) have no value in {id_col!r}, so they cannot be counted at "
            f"any stage. Fix the extract, or filter those rows out before building.")
    if unknown:
        named = ", ".join(f"{name!r} ({n} row(s))" for name, n in sorted(unknown.items())[:3])
        die(f"the file holds stages --stages does not name: {named}. A stage that is not in "
            f"the declared order cannot be placed in the funnel. Add it to --stages, or "
            f"filter the extract.")
    empty = [s for s in stages if not reached[s]]
    if empty:
        die(f"no record reaches {empty[0]!r}, one of the declared stages. A funnel that stops "
            f"before its last stage is a finding, not a drawing: report it, or drop the stage "
            f"from --stages.")
    counts = [{"stage": stage, "ids": reached[stage], "n": len(reached[stage])}
              for stage in stages]
    return counts, duplicates, len({r for s in reached.values() for r in s})


def skips_of(counts: list[dict]) -> list[dict]:
    """Records that reach a stage without reaching the one before it: not a funnel.

    Reported per pair rather than in total, because "12 records skip assessment" is a sentence
    somebody can act on and "43 records skip something" is not.
    """
    out = []
    for before, after in zip(counts, counts[1:]):
        skipped = after["ids"] - before["ids"]
        if skipped:
            out.append({"from": before["stage"], "to": after["stage"], "n": len(skipped)})
    return out


def steps_of(counts: list[dict]) -> list[dict]:
    """Each stage with its two conversion rates and the number it lost since the last one."""
    first = counts[0]["n"] or 1
    out = []
    for i, stage in enumerate(counts):
        previous = counts[i - 1]["n"] if i else stage["n"]
        out.append({
            "stage": stage["stage"],
            "n": stage["n"],
            "of_first": stage["n"] / first,
            "of_previous": (stage["n"] / previous) if previous else 0.0,
            "lost": (previous - stage["n"]) if i else 0,
            "is_first": i == 0,
        })
    return out


# --------------------------------------------------------------------------------- draw
def draw(steps: list[dict], lang: str, t: dict) -> tuple[str, int]:
    """The SVG: one bar per stage, width proportional to the count, figures beside it."""
    height = HEAD_H + len(steps) * ROW_H + GAP
    longest = LONGEST
    top = steps[0]["n"] or 1
    parts: list[str] = [
        f'<svg viewBox="0 0 {W} {height}" role="img" aria-labelledby="fn-t fn-d" '
        f'preserveAspectRatio="xMinYMin meet">',
        f'<title id="fn-t">{html.escape(t["svg_title"])}</title>',
        f'<desc id="fn-d">{html.escape(i18n.fill(t["svg_desc"], n=len(steps),
                                                  first=steps[0]["stage"],
                                                  last=steps[-1]["stage"],
                                                  start=fmt(steps[0]["n"], lang),
                                                  end=fmt(steps[-1]["n"], lang)))}</desc>',
    ]
    # The figures have fixed columns, and each one is named above them: three numbers in a
    # row mean nothing without the words that say which is which.
    for x, key in ((COUNT_X, "col_count"), (FIRST_X, "col_of_first"), (REST_X, "col_head_rest")):
        parts.append(f'<text class="fn-head" x="{x}" y="{HEAD_H - 8}" text-anchor="end">'
                     f'{html.escape(t[key])}</text>')
    for i, step in enumerate(steps):
        y = HEAD_H + GAP + i * ROW_H
        width = max(step["n"] / top * longest, 3.0)
        parts.append(f'<rect class="fn-bar" x="{LEFT}" y="{y}" width="{width:.1f}" '
                     f'height="{BAR_H}"><title>{html.escape(i18n.fill(t["bar_title"], stage=step["stage"], n=fmt(step["n"], lang), share=pct_text(step["of_first"], lang)))}</title></rect>')
        parts.append(f'<text class="fn-count" x="{COUNT_X}" '
                     f'y="{y + BAR_H / 2 + 6:.1f}" text-anchor="end">'
                     f'{html.escape(fmt(step["n"], lang))}</text>')
        parts.append(f'<text class="fn-fig" x="{FIRST_X}" y="{y + BAR_H / 2 + 6:.1f}" '
                     f'text-anchor="end">{html.escape(pct_text(step["of_first"], lang))}</text>')
        if not step["is_first"]:
            parts.append(f'<text class="fn-fig" x="{REST_X}" y="{y + BAR_H / 2 + 6:.1f}" '
                         f'text-anchor="end">'
                         f'{html.escape(i18n.fill(t["of_previous"], share=pct_text(step["of_previous"], lang), lost=fmt(step["lost"], lang)))}</text>')
        parts.append(f'<text class="fn-name" x="{LEFT}" '
                     f'y="{y + BAR_H + NAME_H:.1f}">{html.escape(step["stage"])}</text>')
    parts.append("</svg>")
    return "\n".join(parts), height


def worst_step(steps: list[dict], t: dict, lang: str) -> str:
    """The pair of stages that loses the largest share of what reached the earlier one.

    Named from the counts, so the sentence cannot disagree with the drawing. A funnel that
    loses nothing gets a sentence saying that, rather than an empty line.
    """
    worst = None
    for previous, step in zip(steps, steps[1:]):
        if not previous["n"]:
            continue
        loss = (previous["n"] - step["n"]) / previous["n"]
        if worst is None or loss > worst[0]:
            worst = (loss, previous, step)
    if worst is None or worst[0] <= 0:
        return t["worst_none"]
    loss, previous, step = worst
    return i18n.fill(t["worst_line"], share=pct_text(loss, lang),
                     lost=fmt(previous["n"] - step["n"], lang),
                     before=previous["stage"], after=step["stage"])


# -------------------------------------------------------------------------------- table
def table_rows(steps: list[dict], lang: str, t: dict) -> str:
    out = []
    for step in steps:
        of_previous = (html.escape(t["dash"]) if step["is_first"]
                       else pct_text(step["of_previous"], lang))
        lost = html.escape(t["dash"]) if step["is_first"] else fmt(step["lost"], lang)
        out.append(f'      <tr><th scope="row">{html.escape(step["stage"])}</th>'
                   f'<td class="num">{fmt(step["n"], lang)}</td>'
                   f'<td class="num">{pct_text(step["of_first"], lang)}</td>'
                   f'<td class="num">{of_previous}</td>'
                   f'<td class="num">{lost}</td></tr>')
    return "\n".join(out)


# --------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True,
                    help="CSV with one row per record per stage it reached")
    ap.add_argument("--id", required=True, help="the column that identifies one record")
    ap.add_argument("--stage", required=True, help="the column that names the stage")
    ap.add_argument("--stages", required=True, metavar="A,B,C",
                    help="the stages in order, comma separated. Never inferred from the data")
    ap.add_argument("--allow-skips", action="store_true",
                    help="draw a funnel whose stages are not nested, and say so on the page")
    ap.add_argument("--title", required=True)
    ap.add_argument("--source", default="", help="where the rows came from")
    ap.add_argument("--requested-by", default="", help="a role, not a person's name")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--feedback-to", default="", metavar="ADDRESS_OR_ISSUE_URL",
                    help=feedback_link.FLAG_HELP)
    i18n.add_lang_argument(ap)
    args = ap.parse_args(argv)
    t = i18n.load(STRINGS, args.lang)
    lang = args.lang

    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    if not stages:
        die("--stages is empty. Give the stages in order, comma separated")
    if len(stages) > MAX_STAGES:
        die(f"--stages names {len(stages)} stages; this page draws at most {MAX_STAGES} "
            f"without the names running together. Group the middle ones, or build two pages.")

    counts, duplicates, records = load(args.data, args.id, args.stage, stages)
    skips = skips_of(counts)
    if skips and not args.allow_skips:
        worst = max(skips, key=lambda s: s["n"])
        die(f"the stages are not nested: {worst['n']} record(s) reach {worst['to']!r} "
            f"without reaching {worst['from']!r}"
            + (f", and {len(skips) - 1} other stage pair(s) are out of order" if len(skips) > 1
               else "")
            + ". A funnel counts the same cohort passing each stage, so this extract is not "
              "one: either a record's earlier stages are missing from it, or `--stage` names "
              "a status rather than a stage. Fix the extract, or pass --allow-skips and the "
              "page will say on its face that the stages are not nested.")
    steps = steps_of(counts)
    svg, _height = draw(steps, lang, t)

    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)
    source = i18n.fill(t["source_line"], name=args.source or args.data.name, records=records)
    if duplicates:
        source += " \u00b7 " + i18n.fill(t["duplicates"], n=duplicates)
    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=built,
                                           source=source, lang=lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    skip_note = ""
    if skips:
        lines = "".join(f'    <li>{html.escape(i18n.fill(t["skip_line"], n=s["n"], to=s["to"], frm=s["from"]))}</li>\n'
                        for s in skips)
        skip_note = (f'  <div class="warn">\n'
                     f'    <h2 id="skip-h">{html.escape(t["skip_head"])}</h2>\n'
                     f'    <p>{html.escape(t["skip_intro"])}</p>\n'
                     f'    <ul>{lines}</ul>\n'
                     f'  </div>')

    # The colours come from tools/tokens/: one seam with every other artefact. auto_dark: a
    # reader whose system is dark gets a dark funnel with no script.
    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css)))
    for token, value in {
        "{{TITLE}}": html.escape(args.title),
        "{{SUBTITLE}}": html.escape(i18n.fill(
            t["sub_line"], first=stages[0], last=stages[-1], stages=len(stages),
            records=fmt(records, lang))),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(source),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{ROWS_INLINED}}": str(records),
        "{{SVG}}": svg,
        "{{CAPTION}}": html.escape(i18n.fill(t["caption"], first=stages[0])),
        "{{WORST}}": html.escape(worst_step(steps, t, lang)),
        "{{SKIP_NOTE}}": skip_note,
        "{{TABLE_ROWS}}": table_rows(steps, lang, t),
        "{{TOTAL_START}}": fmt(steps[0]["n"], lang),
        "{{TOTAL_END}}": fmt(steps[-1]["n"], lang),
        "{{TOTAL_SHARE}}": pct_text(steps[-1]["n"] / (steps[0]["n"] or 1), lang),
        "{{FEEDBACK_BLOCK}}": feedback,
    }.items():
        page = page.replace(token, value)

    if "{{" in page:
        left = sorted({piece.split("}}")[0] + "}}" for piece in page.split("{{")[1:]})
        die(f"the template still holds {', '.join(left)} after filling")

    data = page.encode("utf-8")
    if len(data) > MAX_BYTES:
        die(f"the file is {len(data) / 1048576:.1f} MB, over the 40 MB ceiling")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)

    print(f"records       : {records} distinct {args.id}(s)")
    for i, step in enumerate(steps):
        tail = ("" if step["is_first"]
                else f"  {pct_text(step['of_previous'], lang)} of {steps[i - 1]['stage']}")
        print(f"  {step['stage']:<14} {fmt(step['n'], lang):>8}  "
              f"{pct_text(step['of_first'], lang):>7} of {stages[0]}{tail}")
    if skips:
        print(f"not nested    : {sum(s['n'] for s in skips)} record(s) skip a stage")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
