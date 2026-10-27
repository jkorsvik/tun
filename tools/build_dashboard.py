#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
build_dashboard.py — fill the single-file dashboard template with real data.

Used by the skill `tun-new`. Stdlib only: no pip install, no
node_modules, nothing for a non-developer to set up.

    python3 tools/build_dashboard.py \
        --data sales.csv \
        --title "Salg per region" \
        --dimension Region --measure Belop --time Maaned \
        --filters Region,Produkt \
        --out dashboards/salg.html

Input formats: .csv, .tsv, .json (array of objects). For .xlsx, convert first
(`tun-data` handles that) — we deliberately avoid an Excel dependency here
so the Tier 1 path stays prerequisite-free.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_size  # noqa: E402
import build_stamp  # noqa: E402
import feedback_link  # noqa: E402
import i18n  # noqa: E402
import review_layer  # noqa: E402
import tun_core  # noqa: E402
import tun_tokens  # noqa: E402
from tun_tokens import strip_css_comments  # noqa: E402
from tun_core import NOT_STATED, die  # noqa: E402

TEMPLATE = pathlib.Path(__file__).resolve().parents[1] / "templates" / "single-file-dashboard.html"
# The strings table is named, not derived from TEMPLATE: a test points TEMPLATE at a copy.
STRINGS = "single-file-dashboard"

# Anything above this is a Tier 1 violation — see docs/02-architecture.md

# NOT_STATED, the provenance block's wording for "no requester named", is tun_core's.

# The KPI cards a caller can pick with --kpis: the label in the strings table, and the
# JavaScript for the value. It runs inside renderKpis(), where total, dims and avg exist.
KPI_CARDS = {
    "total": ("kpi_label_total", "fmt(total)"),
    "distinct": ("kpi_label_distinct", "fmt(dims)"),
    # The total over the number of time values that have a value: "per quarter".
    "per_period": ("kpi_label_per_period", "fmt((p => p ? total / p : 0)"
                   "(uniq(valued(rows, META.measure), META.timeColumn).length))"),
    "mean": ("kpi_label_mean", "fmt(avg)"),
    "rows": ("kpi_label_rows", "fmt(rows.length)"),
}
# The cards each --measure-kind shows. per_period is dropped when there is no --time.
# A rate (kroner per person) has no mean per row: that number means nothing.
MEASURE_KINDS = {
    "amount": ("total", "per_period", "distinct", "mean"),
    "rate": ("total", "per_period", "distinct"),
}


def kpi_cards(args, t: dict[str, str]) -> str:
    """The body of the `cards` array in renderKpis(), one card per line.

    With neither --kpis nor --measure-kind it is the four cards the template always had,
    with their old labels, so a build without the new flags is byte for byte what it was.
    Exits with a message when a card is unknown, needs --time, or misleads for a rate."""
    if not args.kpis and not args.measure_kind:
        return ("    { label: `" + t["kpi_total"] + " ${META.measure}`, value: fmt(total) },\n"
                '    { label: "' + t["kpi_rows"] + '", value: fmt(rows.length) },\n'
                "    { label: `" + t["kpi_unique"] + " ${META.dimension}`, value: fmt(dims) },\n"
                '    { label: "' + t["kpi_avg"] + '", value: fmt(avg) }')
    if args.kpis:
        kinds = [k.strip() for k in args.kpis.split(",") if k.strip()]
        if not kinds:
            die(f"--kpis names no card. Choose from: {', '.join(KPI_CARDS)}")
        for k in kinds:
            if k not in KPI_CARDS:
                die(f"--kpis: unknown card {k!r}. Choose from: {', '.join(KPI_CARDS)}")
        if "per_period" in kinds and not args.time:
            die("--kpis per_period needs --time.")
        if "mean" in kinds and args.measure_kind == "rate":
            die("--kpis mean is the mean per row, which misleads for "
                "--measure-kind rate. Drop it, or use per_period.")
    else:
        kinds = [k for k in MEASURE_KINDS[args.measure_kind] if k != "per_period" or args.time]
    lines = []
    for k in kinds:
        key, value = KPI_CARDS[k]
        label = i18n.fill(t[key], measure=args.measure, dimension=args.dimension, time=args.time)
        # The label lands in innerHTML, inside a script: escape it for both.
        label = json.dumps(html.escape(label, quote=False), ensure_ascii=False).replace("</", "<\\/")
        lines.append(f"    {{ label: {label}, value: {value} }}")
    return ",\n".join(lines)


# Reading the table, reading the numbers out of it, and stopping on a bad one all live in
# tools/tun_core.py, so this builder cannot drift from the other four. See the module
# docstring for why the numeric parse is the part that mattered.
load_rows = tun_core.read_rows
coerce_numbers = tun_core.coerce_numbers
is_numeric_column = tun_core.is_numeric_column


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, type=pathlib.Path)
    ap.add_argument("--title", required=True)
    ap.add_argument("--dimension", required=True, help="categorical column for the bar chart")
    ap.add_argument("--measure", required=True, help="numeric column to sum")
    ap.add_argument("--time", default="", help="ordered column for the line chart")
    ap.add_argument("--filters", default="", help="comma-separated filter columns")
    ap.add_argument("--kpis", default="", metavar="CARDS",
                    help="comma-separated KPI cards, in order: " + ", ".join(KPI_CARDS) + ". "
                         "per_period is the total over the number of --time values.")
    ap.add_argument("--measure-kind", choices=tuple(MEASURE_KINDS), default="",
                    help="amount = a sum or a count; rate = a value per person or per unit "
                         "that still adds up across rows (the charts sum it). A rate drops the "
                         "mean per row, which means nothing for it. Without this flag or "
                         "--kpis, the four cards are the ones this builder always made.")
    ap.add_argument("--source", default="", help="human description of where data came from")
    ap.add_argument("--requested-by", default="",
                    help="a role, e.g. \"Salgsavdelingen\". Not a person's name.")
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--mode", choices=("bundled", "paired"), default="bundled",
                    help="bundled = one self-contained file (max portability, email it). "
                         "paired = dashboard + sibling data.js that OneDrive syncs, so the "
                         "data updates for everyone without rebuilding the dashboard.")
    ap.add_argument("--feedback-to", default="", metavar="ADDRESS_OR_ISSUE_URL",
                    help=feedback_link.FLAG_HELP)
    ap.add_argument("--annotate", action="store_true", help=review_layer.FLAG_HELP)
    i18n.add_lang_argument(ap)
    args = ap.parse_args()
    t = i18n.load(STRINGS, args.lang)

    rows = coerce_numbers(load_rows(args.data))
    if not rows:
        die("input contained zero rows")

    cols = list(rows[0].keys())
    for name, col in (("--dimension", args.dimension), ("--measure", args.measure)):
        if col not in cols:
            die(f"{name} {col!r} not found. Available: {', '.join(cols)}")
    if args.time and args.time not in cols:
        die(f"--time {args.time!r} not found. Available: {', '.join(cols)}")

    # Decided on the non-empty values: a query result often has NULL in the first row.
    if not is_numeric_column(rows, args.measure):
        die(f"--measure {args.measure!r} is not numeric — charts would be empty. "
            "Check the column, or pick a numeric one from: "
            f"{', '.join(c for c in cols if is_numeric_column(rows, c)) or '(none found)'}")
    no_value = sum(1 for r in rows if r.get(args.measure) in (None, ""))

    filters = [c.strip() for c in args.filters.split(",") if c.strip()]
    missing = [c for c in filters if c not in cols]
    if missing:
        die(f"filter column(s) not found: {', '.join(missing)}")

    cards_js = kpi_cards(args, t)

    # Both stamps honour SOURCE_DATE_EPOCH, so a pinned rebuild is byte-identical.
    now = build_stamp.local()
    extracted = build_stamp.from_mtime(args.data)

    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    meta_js = json.dumps({
        "generated": extracted,
        "source": args.source or args.data.name,
        "rows": len(rows),
    }, ensure_ascii=False)

    if args.mode == "paired":
        data_path = args.out.parent / "data.js"
        data_block = '<script src="./data.js"></script>'
    else:
        data_path = None
        data_block = ("<script>\n"
                      f"window.DASHBOARD_DATA={payload};\n"
                      f"window.DASHBOARD_META={meta_js};\n"
                      "</script>")

    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=now,
                                           source=args.source or args.data.name,
                                           lang=args.lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    # Nothing the caller types goes into the page raw (ROADMAP A0b, 2026-10-24): a title of
    # `<b>x` became bold text, a column named `Navn "sitert"` ended the JavaScript string it
    # was pasted into, and a `"` anywhere in a column name stopped the page. Two contexts, so
    # two treatments: HTML gets html.escape, a JavaScript string gets json.dumps, which is the
    # JSON escape and therefore also a valid JavaScript one.
    # The static view (docs/11 section 3c). A viewer that blocks scripting — Quick Look on
    # iOS and macOS does — shows what the build already knew: the totals, and the first rows
    # of the file. The same rows feed the script, so the two can only disagree if the file is
    # regenerated, and then both change together.
    def static_num(v) -> str:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return html.escape("" if v is None else str(v))
        if float(v).is_integer():
            return i18n.group_int(int(v), args.lang)
        whole, frac = divmod(round(abs(v), 1), 1)
        sign = "-" if v < 0 else ""
        sep = "," if args.lang == "nb" else "."
        return f"{sign}{i18n.group_int(int(whole), args.lang)}{sep}{int(round(frac * 10))}"

    measure_values = [r.get(args.measure) for r in rows]
    measure_total = sum(v for v in measure_values
                        if isinstance(v, (int, float)) and not isinstance(v, bool))
    dims = {r.get(args.dimension) for r in rows}
    nojs_facts = "".join(
        f"<div><dt>{html.escape(label)}</dt><dd>{value}</dd></div>"
        for label, value in (
            (i18n.fill(t["kpi_total"], measure=args.measure), static_num(measure_total)),
            (t["kpi_rows"], i18n.group_int(len(rows), args.lang)),
            (i18n.fill(t["kpi_unique"], dimension=args.dimension),
             i18n.group_int(len(dims), args.lang)),
        ))
    cols = [c for c in (args.dimension, args.time, args.measure) if c]
    nojs_head = "".join(
        f'<th class="{"num" if c == args.measure else ""}">{html.escape(c)}</th>' for c in cols)
    nojs_rows = "".join(
        "<tr>" + "".join(
            f'<td class="{"num" if c == args.measure else ""}">'
            f'{static_num(r.get(c)) if c == args.measure else html.escape(str(r.get(c, "")))}</td>'
            for c in cols) + "</tr>"
        for r in rows[:8])

    source_name = args.source or args.data.name
    subs = {
        "DATA_BLOCK": data_block,
        "DATA_MODE": args.mode,
        "DASHBOARD_TITLE": html.escape(args.title),
        "NOJS_FACTS": nojs_facts,
        "NOJS_HEAD": nojs_head,
        "NOJS_ROWS": nojs_rows,
        "SOURCE_DESCRIPTION": html.escape(source_name),
        "EXTRACT_TIMESTAMP": extracted,
        "BUILD_TIMESTAMP": now,
        "REQUESTED_BY": html.escape(args.requested_by or NOT_STATED),
        "ROW_COUNT": i18n.group_int(len(rows), args.lang),
        "FILTER_COLS_JSON": json.dumps(filters or [args.dimension], ensure_ascii=False),
        "CHART1_TITLE": html.escape(i18n.fill(t["chart1_title"], measure=args.measure,
                                             dimension=args.dimension)),
        "CHART2_TITLE": html.escape(i18n.fill(t["chart2_title"], measure=args.measure, time=args.time)
                                    if args.time else t["chart2_default"]),
        # Holds column names, so it goes in late, like the feedback block below.
        "KPI_CARDS": cards_js,
        # Last on purpose: the block holds reader-facing text (the title), and no
        # later replacement should get a chance to rewrite a token inside it.
        "FEEDBACK_BLOCK": feedback,
    }

    # The colours come from tools/tokens/: one seam with every other artefact. auto_dark:
    # a reader whose system is dark gets a dark dashboard with no script.
    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css)))
    # The three column names and the source fallback sit inside a JavaScript string, so they
    # are substituted on their quoted form, before the HTML pass below can escape them.
    for token, value in (("DIMENSION_COL", args.dimension), ("TIME_COL", args.time),
                         ("MEASURE_COL", args.measure)):
        page = page.replace('"{{' + token + '}}"', json.dumps(value, ensure_ascii=False))
    page = page.replace('DATA_META.source || "{{SOURCE_DESCRIPTION}}"',
                        "DATA_META.source || " + json.dumps(source_name, ensure_ascii=False))
    for key, value in subs.items():
        page = page.replace("{{" + key + "}}", str(value))

    leftover = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", page)))
    if leftover:
        die(f"template placeholders not substituted: {leftover}")

    if args.annotate:
        # The review round trip (docs/31): the reader comments on a row and copies a text
        # block back. The layer is appended here, never baked into the template, so an
        # artefact built without --annotate is byte for byte what it was.
        # A row is named by its categorical cells, not by every cell: a number that moves
        # between builds must not make the row the reader pointed at unfindable. The
        # measure is the value under discussion, so it is never part of the name. In the
        # example data these four columns are unique per row; where the source file holds
        # genuine duplicates the report says how many rows share the name.
        all_cols = list(rows[0]) if rows else [args.dimension]
        keys = [c for c in all_cols
                if c != args.measure and not is_numeric_column(rows, c)] or [args.dimension]

        def annotate_num(v) -> str:
            """A cell as the table shows it: whole numbers grouped, nothing else."""
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return "" if v is None else str(v)
            return i18n.group_int(int(round(v)), args.lang)

        try:
            head_html, body_html = review_layer.layer(
                title=args.title, file=args.out.name, built=now, rows=len(rows),
                source=source_name, keys=keys, measure=args.measure,
                examples=[([str(r.get(k, "")) for k in keys], annotate_num(r.get(args.measure)))
                          for r in rows[:review_layer.MAX_EXAMPLES]],
                lang=args.lang)
            page = review_layer.insert(page, head_html, body_html)
        except (ValueError, KeyError) as exc:
            die(f"--annotate: {exc}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")

    if data_path is not None:
        data_path.write_text(
            "// Data for " + args.out.name + " — replace this file to update the dashboard.\n"
            "// Generated " + now + " from " + (args.source or args.data.name) + "\n"
            f"window.DASHBOARD_DATA={payload};\n"
            f"window.DASHBOARD_META={meta_js};\n",
            encoding="utf-8")

    size_mb = args.out.stat().st_size / 1_048_576
    print(f"built {args.out}  ({size_mb:.2f} MB, {len(rows):,} rows)".replace(",", " "))
    if no_value:
        counts = f"{no_value:,} of {len(rows):,}".replace(",", " ")
        print(f"  note: {counts} rows have no {args.measure!r} value. They show empty in the "
              f"table and are left out of the charts and the average.")
    if data_path is not None:
        d_mb = data_path.stat().st_size / 1_048_576
        print(f"  + {data_path.name}  ({d_mb:.2f} MB)  <- keep these two together")
        print("  paired mode: replace data.js to update the numbers everywhere, "
              "no rebuild needed")
        size_mb += d_mb
    # The budget is shared with every other builder, so a ceiling that changes
    # changes once (tools/build_size.py, docs/02-architecture.md).
    build_size.enforce(args.out, extra_mb=0.0 if data_path is None else build_size.megabytes(data_path))
    print("  next: python3 " + _shell_arg(_verifier_path()) + " " + _shell_arg(args.out.as_posix()))


def _verifier_path() -> str:
    """The verifier next to this file, as the caller can type it from where they stand.

    Relative to the working directory when it is below it (`tools/verify_dashboard.py` in
    the repo), absolute otherwise. A fixed `tools/...` was wrong in the installed plugin,
    where the engine lives in skills/tun-new/engine/tools/.
    """
    verifier = pathlib.Path(__file__).resolve().parent / "verify_dashboard.py"
    try:
        return verifier.relative_to(pathlib.Path.cwd().resolve()).as_posix()
    except ValueError:
        return verifier.as_posix()


def _shell_arg(arg: str) -> str:
    """Double-quote an argument with a space: a OneDrive path on Windows has one, and
    double quotes work in cmd, PowerShell, bash and zsh alike."""
    return f'"{arg}"' if " " in arg else arg


if __name__ == "__main__":
    main()
