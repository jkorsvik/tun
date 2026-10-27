#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a standalone small-multiples page: one panel per group, all on ONE shared scale.

A small multiple answers a question a single chart cannot: which of these groups behaves
differently from the others? That question has exactly one requirement, and it is the one that
gets broken. Every panel must be drawn on the same scale. Give each panel its own axis and a
group that moves between 4 and 8 looks precisely like a group that moves between 400 and 800:
the eye compares shapes, and per-panel scaling makes every shape identical. The mistake is
invisible, because the picture is beautiful and every number in it is true.

    python3 tools/build_smallmultiples.py \\
      --data examples/45-smallmultiples/ko.csv \\
      --group Enhet --period Uke --measure Saker \\
      --title "Saker i ko, per enhet og uke" \\
      --source "Syntetisk eksempeldata (ko.csv)" \\
      --requested-by "Driftsavdelingen" \\
      --out examples/45-smallmultiples/smaaflater.html

What is built in, rather than left to whoever assembles the file:

  * **one scale, derived from every value, and printed.** The low and the top are on the page,
    once per row of panels, so the shared scale is a claim the reader can check rather than
    trust. Nothing is scaled per panel.
  * **the axis starts at zero unless you say otherwise.** `--truncate` is allowed, because a
    level that barely moves is invisible under a zero floor, and then the page says on its face
    that the axis does not start at zero. What is never allowed is a truncated axis that
    nobody mentions.
  * **every period appears in every panel, or the line breaks.** A missing row is a gap, not a
    zero: drawn as a break, counted on the page. Bridging it draws a trend through a hole.
  * **the period order is declared, never inferred.** `--periods A,B,C` sets it; without it the
    labels are sorted as text and the page says so. Panels are ordered by `--order`
    (name, latest, change) and the page names the order it used.
  * **each panel prints its latest value.** The shape says "different", the number says how
    different, and a reader who only reads numbers still gets the answer.
  * **there is no script.** A filter would re-lay the grid, and the grid is the claim.

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

TEMPLATE = ROOT / "templates" / "smallmultiples.html"
STRINGS = "smallmultiples"
MAX_BYTES = 40 * 1024 * 1024

# Named here, literally, so the i18n gate can see that every key is used: a key built by an
# f-string, or indexed as `order_%s`, is invisible to a scanner that reads the source.
ORDER_KEYS = {"name": "order_name", "latest": "order_latest", "change": "order_change"}
ORDER_CHOICES = tuple(ORDER_KEYS)

MAX_PANELS = 16            # more than this and no two panels are compared, only looked at
MIN_PERIODS = 3            # two points are a difference, not a shape

# The canvas. Units, not pixels: the SVG scales, so a theme's font size cannot move a panel.
PANEL_W = 250
PANEL_H = 132
PAD_L = 12                 # inside a panel
PAD_R = 12
PAD_T = 30                 # room for the name and the latest value above the plot
PAD_B = 14                 # the baseline rule, and nothing below it
AXIS_W = 44                # the gutter left of the first column, for the shared scale's numbers
COL_GAP = 20
ROW_GAP = 26

# How many panels fit across, by count: two panels across an otherwise empty row look like a
# mistake, and four is the most that keeps a panel wide enough to show a shape.
def columns_for(n: int) -> int:
    if n <= 1:
        return 1
    if n <= 4:
        return 2
    if n <= 9:
        return 3
    return 4


# ------------------------------------------------------------------------------ numbers
def num_text(value: float, lang: str) -> str:
    """A measure as the reader's locale writes it. Whole numbers carry no decimals."""
    if float(value).is_integer():
        return i18n.group_int(int(value), lang)
    text = f"{value:.1f}"
    return text.replace(".", ",") if lang == "nb" else text


# --------------------------------------------------------------------------------- load
def load(path: pathlib.Path, group_col: str, period_col: str,
         measure_col: str) -> tuple[dict[str, dict[str, float]], int]:
    """Every value per group and period, plus how many rows had no usable measure.

    A row with an empty measure is not a zero: it says nothing was measured, which is the
    distinction a small multiple is supposed to keep visible.
    """
    rows = tun_core.read_rows(path)
    cols = tun_core.columns(rows)
    for name, given in (("--group", group_col), ("--period", period_col),
                        ("--measure", measure_col)):
        if given not in cols:
            die(f"{name} {given!r} is not a column in {path.name}. It has: {', '.join(cols)}")

    values: dict[str, dict[str, float]] = {}
    skipped = 0
    for i, row in enumerate(rows, start=2):
        group = (row.get(group_col) or "").strip()
        period = (row.get(period_col) or "").strip()
        if not group or not period:
            skipped += 1
            continue
        raw = (row.get(measure_col) or "").strip()
        if not raw:
            skipped += 1
            continue
        value = tun_core.to_number(raw)
        if value is None:
            die(f"row {i} of {path.name} holds {raw!r} in {measure_col!r}, which is not a "
                f"number. A text value drawn on a numeric axis is a scale that means nothing.")
        values.setdefault(group, {})[period] = value
    if not values:
        die(f"no row in {path.name} has a {group_col!r}, a {period_col!r} and a number in "
            f"{measure_col!r}. Nothing to draw.")
    return values, skipped


def periods_of(values: dict[str, dict[str, float]], declared: list[str]) -> tuple[list[str], list[str]]:
    """The period axis, in the order the page will use, and the labels the data holds.

    The order is declared or it is text order. Never the order of the rows in the file: that
    would make the same extract tell a different story depending on how it was sorted.
    """
    found = sorted({p for per_group in values.values() for p in per_group})
    if declared:
        unknown = [p for p in found if p not in declared]
        if unknown:
            die(f"--periods names {len(declared)} periods and the data holds "
                f"{len(unknown)} it does not name: {', '.join(unknown[:4])}"
                + (", ..." if len(unknown) > 4 else "")
                + ". Every period in the data needs a place on the axis.")
        return list(declared), found
    return found, found


def order_panels(values: dict[str, dict[str, float]], periods: list[str],
                 order: str) -> list[str]:
    """The panel order, from the declared rule, computed from the same numbers that are drawn."""
    names = list(values)
    if order == "name":
        return sorted(names)
    if order == "latest":
        return sorted(names, key=lambda g: (-last_value(values[g], periods), g))
    return sorted(names, key=lambda g: (-(last_value(values[g], periods)
                                         - first_value(values[g], periods)), g))


def first_value(cells: dict[str, float], periods: list[str]) -> float:
    for period in periods:
        if period in cells:
            return cells[period]
    return 0.0


def last_value(cells: dict[str, float], periods: list[str]) -> float:
    for period in reversed(periods):
        if period in cells:
            return cells[period]
    return 0.0


# -------------------------------------------------------------------------------- scale
def scale_of(values: dict[str, dict[str, float]], truncate: bool) -> tuple[float, float]:
    """The one scale every panel is drawn on: (low, high), and it includes zero by default.

    A level measured against a truncated axis turns a two per cent wobble into a mountain. That
    is a legitimate choice and an illegitimate surprise, so it needs a flag and a sentence.
    """
    every = [v for cells in values.values() for v in cells.values()]
    low, high = min(every), max(every)
    if truncate:
        if low == high:
            pad = abs(low) * 0.1 or 1.0
            return low - pad, high + pad
        pad = (high - low) * 0.05
        return low - pad, high + pad
    low = min(0.0, low)
    high = max(0.0, high)
    if low == high:
        high = low + 1.0
    return low, high


# --------------------------------------------------------------------------------- draw
def draw(values: dict[str, dict[str, float]], names: list[str], periods: list[str],
         scale: tuple[float, float], lang: str, t: dict) -> str:
    """The grid. Every panel maps a value through the same two numbers."""
    low, high = scale
    span = (high - low) or 1.0
    ncols = columns_for(len(names))
    nrows = (len(names) + ncols - 1) // ncols
    width = AXIS_W + ncols * PANEL_W + (ncols - 1) * COL_GAP
    height = nrows * PANEL_H + (nrows - 1) * ROW_GAP + 26   # 26 units for the period axis

    def y_of(value: float, top: float) -> float:
        plot_h = PANEL_H - PAD_T - PAD_B
        return top + PAD_T + plot_h - (value - low) / span * plot_h

    def x_of(index: int, left: float) -> float:
        plot_w = PANEL_W - PAD_L - PAD_R
        if len(periods) == 1:
            return left + PAD_L + plot_w / 2
        return left + PAD_L + index * plot_w / (len(periods) - 1)

    parts: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-labelledby="sm-t sm-d" '
        f'preserveAspectRatio="xMinYMin meet">',
        f'<title id="sm-t">{html.escape(t["svg_title"])}</title>',
        f'<desc id="sm-d">{html.escape(i18n.fill(t["svg_desc"], panels=len(names),
                                                 periods=len(periods),
                                                 low=num_text(low, lang),
                                                 high=num_text(high, lang)))}</desc>',
    ]
    for index, name in enumerate(names):
        col, row = index % ncols, index // ncols
        left = AXIS_W + col * (PANEL_W + COL_GAP)
        top = row * (PANEL_H + ROW_GAP)
        cells = values[name]
        latest = last_value(cells, periods)
        parts.append(f'<g class="sm-panel" data-group="{html.escape(name)}">')
        parts.append(f'<rect class="sm-box" x="{left:.1f}" y="{top:.1f}" '
                     f'width="{PANEL_W}" height="{PANEL_H}" rx="6"/>')
        parts.append(f'<text class="sm-name" x="{left + PAD_L:.1f}" y="{top + 20:.1f}">'
                     f'{html.escape(name)}</text>')
        parts.append(f'<text class="sm-latest" x="{left + PANEL_W - PAD_R:.1f}" '
                     f'y="{top + 20:.1f}" text-anchor="end">'
                     f'{html.escape(num_text(latest, lang))}</text>')
        # The two rules that make the shared scale visible in every single panel: the top of
        # the scale and its floor. A reader who covers the other panels still sees the range.
        for cls, value in (("sm-rule-top", high), ("sm-rule", low)):
            y = y_of(value, top)
            parts.append(f'<line class="{cls}" x1="{left + PAD_L:.1f}" y1="{y:.1f}" '
                         f'x2="{left + PANEL_W - PAD_R:.1f}" y2="{y:.1f}"/>')
        # One polyline per unbroken run, so a missing period is a break rather than a bridge.
        run: list[str] = []
        for index_p, period in enumerate(periods):
            if period not in cells:
                if len(run) > 1:
                    parts.append(f'<polyline class="sm-line" points="{" ".join(run)}"/>')
                run = []
                continue
            run.append(f'{x_of(index_p, left):.1f},{y_of(cells[period], top):.1f}')
        if len(run) > 1:
            parts.append(f'<polyline class="sm-line" points="{" ".join(run)}"/>')
        for index_p, period in enumerate(periods):
            if period not in cells:
                continue
            parts.append(f'<circle class="sm-dot" data-p="{html.escape(period)}" '
                         f'data-v="{html.escape(str(cells[period]))}" '
                         f'cx="{x_of(index_p, left):.1f}" '
                         f'cy="{y_of(cells[period], top):.1f}" r="2.5"/>')
        parts.append("</g>")
        # The scale is printed once per row of panels, in a gutter left of the first column:
        # inside a panel it collides with the group's own name, and the two numbers a reader
        # needs to compare every panel against must not be pushed out of the way.
        if col == 0:
            for value in (high, low):
                parts.append(f'<text class="sm-axis" x="{AXIS_W - 8:.1f}" '
                             f'y="{y_of(value, top) + 5:.1f}" text-anchor="end">'
                             f'{html.escape(num_text(value, lang))}</text>')
    axis_y = height - 8
    parts.append(f'<text class="sm-axis" x="0" y="{axis_y}">{html.escape(periods[0])}</text>')
    parts.append(f'<text class="sm-axis" x="{width}" y="{axis_y}" text-anchor="end">'
                 f'{html.escape(periods[-1])}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


# ------------------------------------------------------------------------------ summary
def summary(values: dict[str, dict[str, float]], names: list[str], periods: list[str],
            lang: str, t: dict) -> str:
    """The picture said in words: the highest latest, the lowest, and the widest swing.

    Computed from the drawn numbers, so the sentence cannot disagree with the grid. A page
    whose panels are all alike says that instead of inventing a finding.
    """
    latest = {g: last_value(values[g], periods) for g in names}
    highest = max(names, key=lambda g: latest[g])
    lowest = min(names, key=lambda g: latest[g])
    swings = {}
    for group in names:
        seen = [v for v in values[group].values()]
        swings[group] = max(seen) - min(seen) if seen else 0.0
    widest = max(names, key=lambda g: swings[g])
    if latest[highest] == latest[lowest]:
        return i18n.fill(t["summary_flat"], panels=len(names),
                         value=num_text(latest[highest], lang))
    # Slot names carry no underscore: i18n.fill's slot is lower-case letters and digits, so
    # `{high_group}` would survive filling and land on the page as text.
    return i18n.fill(t["summary_line"], panels=len(names),
                     top=highest, topv=num_text(latest[highest], lang),
                     bottom=lowest, bottomv=num_text(latest[lowest], lang),
                     mover=widest, swing=num_text(swings[widest], lang))


def gap_line(values: dict[str, dict[str, float]], names: list[str], periods: list[str],
             lang: str, t: dict) -> str:
    """How many panel-periods have no row at all. Silence drawn as a bridge is a claim."""
    missing = sum(1 for g in names for p in periods if p not in values[g])
    if not missing:
        return t["gaps_none"]
    panels = sum(1 for g in names if any(p not in values[g] for p in periods))
    return i18n.fill(t["gaps_line"], n=missing, panels=panels)


# -------------------------------------------------------------------------------- table
def table_rows(values: dict[str, dict[str, float]], names: list[str], periods: list[str],
               lang: str, t: dict) -> str:
    out = []
    for group in names:
        cells = values[group]
        first = first_value(cells, periods)
        last = last_value(cells, periods)
        delta = last - first
        seen = list(cells.values())
        out.append(f'      <tr><th scope="row">{html.escape(group)}</th>'
                   f'<td class="num">{num_text(first, lang)}</td>'
                   f'<td class="num">{num_text(last, lang)}</td>'
                   f'<td class="num">{html.escape(signed(delta, lang, t))}</td>'
                   f'<td class="num">{num_text(min(seen), lang)}</td>'
                   f'<td class="num">{num_text(max(seen), lang)}</td>'
                   f'<td class="num">{len(cells)}/{len(periods)}</td></tr>')
    return "\n".join(out)


def signed(value: float, lang: str, t: dict) -> str:
    if value > 0:
        return i18n.fill(t["plus"], value=num_text(value, lang))
    if value < 0:
        return i18n.fill(t["minus"], value=num_text(abs(value), lang))
    return t["unchanged"]


# --------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True,
                    help="CSV with one row per group per period")
    ap.add_argument("--group", required=True, help="the column that names one panel")
    ap.add_argument("--period", required=True, help="the column that names the step on the axis")
    ap.add_argument("--measure", required=True, help="the numeric column that is drawn")
    ap.add_argument("--periods", default="", metavar="A,B,C",
                    help="the periods in order, comma separated. Never inferred from the "
                         "row order; without this the labels are sorted as text")
    ap.add_argument("--order", choices=ORDER_CHOICES, default="name",
                    help="panel order: name (default), latest value, or change first to last")
    ap.add_argument("--truncate", action="store_true",
                    help="start the axis at the data instead of at zero, and say so on the page")
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

    declared = [p.strip() for p in args.periods.split(",") if p.strip()]
    values, skipped = load(args.data, args.group, args.period, args.measure)
    periods, found = periods_of(values, declared)

    if len(values) > MAX_PANELS:
        die(f"{len(values)} groups is more than the {MAX_PANELS} panels this page draws: past "
            f"that the reader looks at panels instead of comparing them. Split the group "
            f"column, pick a subset of rows, or build one page per part.")
    if len(periods) < MIN_PERIODS:
        die(f"the axis holds {len(periods)} period(s). A series needs at least "
            f"{MIN_PERIODS} points to show a shape; with one or two, a number in a table says "
            f"more than a picture.")
    if len(found) != len(periods) and len(found) < MIN_PERIODS:
        die(f"'{args.period}' holds only {len(found)} distinct values. "
            f"A small multiple needs a step on the axis.")

    scale = scale_of(values, args.truncate)
    names = order_panels(values, periods, args.order)
    svg = draw(values, names, periods, scale, lang, t)

    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)
    source = i18n.fill(t["source_line"], name=args.source or args.data.name,
                       rows=sum(len(c) for c in values.values()))
    if skipped:
        source += " \u00b7 " + i18n.fill(t["skipped"], n=skipped)
    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=built,
                                           source=source, lang=lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    truncate_note = ""
    if args.truncate:
        truncate_note = (f'  <div class="warn">\n'
                         f'    <h2 id="trunc-h">{html.escape(t["truncate_head"])}</h2>\n'
                         f'    <p>{html.escape(i18n.fill(t["truncate_line"],
                                                      low=num_text(scale[0], lang)))}</p>\n'
                         f'  </div>')

    # The colours come from tools/tokens/: one seam with every other artefact. auto_dark: a
    # reader whose system is dark gets dark panels with no script.
    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css)))
    for token, value in {
        "{{TITLE}}": html.escape(args.title),
        "{{SUBTITLE}}": html.escape(i18n.fill(
            t["sub_line"], panels=len(names), periods=len(periods),
            first=periods[0], last=periods[-1])),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(source),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{ROWS_INLINED}}": str(sum(len(c) for c in values.values())),
        "{{SVG}}": svg,
        "{{CAPTION}}": html.escape(i18n.fill(t["caption"],
                                             low=num_text(scale[0], lang),
                                             high=num_text(scale[1], lang))),
        "{{SUMMARY}}": html.escape(summary(values, names, periods, lang, t)),
        "{{GAPS}}": html.escape(gap_line(values, names, periods, lang, t)),
        "{{ORDER_LINE}}": html.escape(i18n.fill(t[ORDER_KEYS[args.order]], panels=len(names))),
        "{{TRUNCATE_NOTE}}": truncate_note,
        "{{TABLE_ROWS}}": table_rows(values, names, periods, lang, t),
        "{{COL_PERIODS}}": str(len(periods)),
        "{{SCALE_LOW}}": num_text(scale[0], lang),
        "{{SCALE_HIGH}}": num_text(scale[1], lang),
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

    print(f"panels        : {len(names)} groups, {len(periods)} periods "
          f"({periods[0]} to {periods[-1]})")
    print(f"scale         : {num_text(scale[0], lang)} to {num_text(scale[1], lang)}"
          f"{'  (truncated: does not start at zero)' if args.truncate else '  (from zero)'}")
    print(f"order         : {args.order}")
    for group in names:
        cells = values[group]
        print(f"  {group:<16} {num_text(last_value(cells, periods), lang):>8} latest"
              f"   {len(cells)}/{len(periods)} periods")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
