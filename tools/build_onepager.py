#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
build_onepager.py — one A4 sheet, for paper or PDF.

The other builders make something you explore. This one makes something you hand over: four
numbers, the chart behind them, and the sentences that say what moved. No filter, no hover,
no scroll, because the reader is holding it.

    python3 tools/build_onepager.py \
      --data examples/37-printable-onepager/salgsdata.csv \
      --title "Salg per produkt, september 2026" \
      --dimension Produkt --measure Belop --period Maaned \
      --source "Syntetisk eksempeldata (salgsdata.csv)" \
      --requested-by "Salgsavdelingen" \
      --out examples/37-printable-onepager/ett-ark.html

The page is measured, not assumed: tools/verify_print.py opens it, switches to print media,
and fails if the content is taller than one A4 printable area, if anything runs past the
right edge, or if any text is smaller than 9 pt. A one-pager that quietly becomes two pages
is the failure mode this file exists to prevent.

Nothing here uses SVG for text. A viewBox scales its labels with the drawing, so a chart that
looks right a glance can print its category names at 6 pt; these bars are HTML, so the type
size in the stylesheet is the type size on the paper.
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
import i18n  # noqa: E402
import tun_core  # noqa: E402
from tun_core import NOT_STATED, die  # noqa: E402

TEMPLATE = ROOT / "templates" / "onepager.html"
STRINGS = "onepager"
MAX_BYTES = 2 * 1024 * 1024     # a one-pager that is not small is not a one-pager
TOP_BARS = 6
MOVED_ROWS = 4
MOVED_FLOOR = 1.0               # per cent: below this, "moved" is noise on a printed page


def fmt(value: float, lang: str) -> str:
    """A number as the reader's locale writes it, with no decimals at this scale.

    The one thing a printed page cannot do is re-format itself for the reader, so the group
    separator is decided at build time and is the same everywhere on the sheet.
    """
    return f"{round(value):,}".replace(",", "\u00a0" if lang == "nb" else ",")


def pct(value: float) -> str:
    sign = "+" if value >= 0 else "\u2212"
    return f"{sign}{abs(value):.1f}\u00a0%"


def group(rows: list[dict], dim: str, measure: str, period: str) -> dict[str, dict[str, float]]:
    """{period: {category: total}}, with a missing period simply absent."""
    out: dict[str, dict[str, float]] = {}
    for row in rows:
        key = str(row.get(period, "") or "")
        name = str(row.get(dim, "") or "")
        out.setdefault(key, {})
        out[key][name] = out[key].get(name, 0.0) + tun_core.number_or_zero(row.get(measure))
    return out


def bars_html(latest: dict[str, float], lang: str) -> str:
    if not latest:
        return ""
    total = sum(latest.values()) or 1.0
    biggest = max(latest.values()) or 1.0
    ranked = sorted(latest.items(), key=lambda kv: kv[1], reverse=True)[:TOP_BARS]
    rows = []
    for name, value in ranked:
        share = 100.0 * value / biggest
        rows.append(
            '<div class="bar-row">'
            f'<span class="bar-name">{html.escape(name)}</span>'
            '<span class="bar-track">'
            f'<span class="bar-fill" style="width:{share:.1f}%"></span>'
            "</span>"
            f'<span class="bar-value">{fmt(value, lang)}</span>'
            "</div>")
    return "\n".join(rows)


def moved_html(now: dict[str, float], before: dict[str, float] | None, t: dict,
               lang: str) -> str:
    if not before:
        return f'      <li>{html.escape(t["moved_missing"])}</li>'
    moves = []
    for name, after in now.items():
        was = before.get(name)
        if not was:
            continue
        change = 100.0 * (after - was) / was
        if abs(change) < MOVED_FLOOR:
            continue
        moves.append((abs(change), name, was, after, change))
    if not moves:
        return f'      <li>{html.escape(t["moved_none"])}</li>'
    moves.sort(reverse=True)
    out = []
    for _, name, was, after, change in moves[:MOVED_ROWS]:
        line = i18n.fill(t["moved_line"], name=html.escape(name), before=fmt(was, lang),
                         after=fmt(after, lang), pct=pct(change))
        # The arrow is the sentence's own emphasis, not a colour: printed in greyscale the
        # bullet still reads, and the sign is in the text.
        cls = "up" if change > 0 else "down"
        out.append(f'      <li class="{cls}">{line}</li>')
    return "\n".join(out)


def kpi_html(label: str, value: str, note: str = "", kind: str = "") -> str:
    cls = f" {kind}" if kind else ""
    tail = f'<p class="delta{cls}">{note}</p>' if note else ""
    return ('    <div class="kpi">'
            f'<p class="label">{html.escape(label)}</p>'
            f'<p class="value">{value}</p>{tail}</div>')


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True, help="CSV, one row per figure")
    ap.add_argument("--title", required=True)
    ap.add_argument("--dimension", required=True, help="the column the bars are drawn from")
    ap.add_argument("--measure", required=True, help="the column summed, e.g. Belop")
    ap.add_argument("--period", required=True,
                    help="the column that orders time. The latest value becomes the sheet's "
                         "period, and the one before it is what change is measured against")
    ap.add_argument("--top", type=int, default=TOP_BARS,
                    help=f"bars to draw (default {TOP_BARS}); a one-pager has room for few")
    ap.add_argument("--source", default="", help="where the figures came from")
    ap.add_argument("--requested-by", default="", help="a role, not a person's name")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    i18n.add_lang_argument(ap)
    args = ap.parse_args(argv)
    t = i18n.load(STRINGS, args.lang)

    if not args.data.is_file():
        die(f"{args.data} not found")
    if not TEMPLATE.is_file():
        die(f"template missing: {TEMPLATE}")
    if not 1 <= args.top <= 12:
        die("--top must be between 1 and 12: this sheet holds one chart, not a report")

    rows = tun_core.coerce_numbers(tun_core.read_rows(args.data))
    if not rows:
        die("input contained zero rows")
    cols = tun_core.columns(rows)
    for flag, name in (("--dimension", args.dimension), ("--measure", args.measure),
                       ("--period", args.period)):
        if name not in cols:
            die(f"{flag} {name!r} is not one of the columns in {args.data.name} "
                f"({', '.join(cols)})")

    per_period = group(rows, args.dimension, args.measure, args.period)
    if not per_period:
        die(f"{args.period} is empty in every row: there is no period to print")
    periods = sorted(per_period)
    latest_key = periods[-1]
    before_key = periods[-2] if len(periods) > 1 else None
    latest = per_period[latest_key]
    before = per_period.get(before_key, {}) if before_key else None
    if not latest:
        die(i18n.fill(t["period_missing"], measure=args.measure))

    total = sum(latest.values())
    count = len(latest)
    biggest_name, biggest_value = max(latest.items(), key=lambda kv: kv[1])
    share = 100.0 * biggest_value / total if total else 0.0

    prev_total = sum(before.values()) if before else None
    if prev_total:
        change = 100.0 * (total - prev_total) / prev_total
        change_note = i18n.fill(t["vs_previous"], period=before_key)
        change_kind = "up" if change > 0 else "down"
    else:
        change_note = t["change_none"]
        change_kind = ""

    kpis = "\n".join([
        kpi_html(i18n.fill(t["kpi_total"], measure=args.measure), fmt(total, args.lang)),
        kpi_html(t["kpi_change"], pct(change) if prev_total else "\u2014", change_note,
                 change_kind),
        kpi_html(t["kpi_categories"], str(count),
                 i18n.fill(t["across_periods"], n=len(periods))),
        kpi_html(t["kpi_largest"], html.escape(biggest_name),
                 i18n.fill(t["largest_share"], share=f"{share:.0f}\u00a0%")),
    ])

    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)
    source = args.source or args.data.name
    standfirst = i18n.fill(t["standfirst"], period=latest_key,
                           shown=min(args.top, count), total=count)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{LANG}}", args.lang)
            .replace("{{TITLE}}", html.escape(args.title))
            .replace("{{SOURCE_DESCRIPTION}}", html.escape(source))
            .replace("{{EXTRACT_TIMESTAMP}}", extracted)
            .replace("{{BUILD_TIMESTAMP}}", built)
            .replace("{{REQUESTED_BY}}", html.escape(args.requested_by or NOT_STATED))
            .replace("{{ROWS_INLINED}}", str(len(rows)))
            .replace("{{PERIOD_LABEL}}", latest_key)
            .replace("{{CATEGORY_COUNT}}", str(count))
            .replace("{{STANDFIRST}}", html.escape(standfirst))
            .replace("{{KPIS}}", kpis)
            .replace("{{CHART_TITLE}}",
                     html.escape(i18n.fill(t["chart_title"], dimension=args.dimension,
                                           period=latest_key)))
            .replace("{{CHART}}", bars_html(dict(sorted(latest.items(),
                                                        key=lambda kv: kv[1],
                                                        reverse=True)[:args.top]), args.lang))
            .replace("{{MOVED_TITLE}}", html.escape(t["moved_title"]))
            .replace("{{MOVED}}", moved_html(latest, before, t, args.lang))
            .replace("{{SOURCE_LINE}}",
                     html.escape(i18n.fill(t["source_line"], source=source,
                                           rows=f"{len(rows):,}".replace(",", "\u00a0"),
                                           cols=len(cols))))
            .replace("{{PROVENANCE_LINE}}",
                     html.escape(i18n.fill(t["provenance_line"], extracted=extracted,
                                           built=built,
                                           who=args.requested_by or NOT_STATED))))
    if "{{" in page.split("<script>")[0]:
        die("a template placeholder was left unfilled; the file would ship a visible {{...}}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    size = args.out.stat().st_size
    if size > MAX_BYTES:
        die(f"{args.out} is {size / 1024:.0f} KB, above the {MAX_BYTES // 1024} KB this builder "
            f"will write. A one-pager that carries this much data is a dashboard; use "
            f"build_dashboard.py.")
    build_size.enforce(args.out)

    print(f"period        : {latest_key}"
          + (f" (change measured against {before_key})" if before_key else " (no earlier period)"))
    print(f"categories    : {count} in the sheet, {args.top} bar(s) drawn")
    print(f"total         : {fmt(total, args.lang)} {args.measure}")
    print(f"wrote         : {args.out} ({size / 1024:.0f} KB)")
    print("next          : python3 tools/verify_print.py " + str(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
