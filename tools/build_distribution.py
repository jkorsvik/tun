#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a standalone distribution page: the shape of one measure, not its total.

Every other artefact in this repository answers a question about a total. A total says
nothing about whether a typical case is typical: three cases at 1, 1 and 40 have the same
sum as eleven cases at 4, and a mean of 14 describes neither. This page draws the bucket
counts of one measure across the cases that hold it, and prints the median, the 90th
percentile and the largest value beside the picture.

    python3 tools/build_distribution.py \\
      --data examples/38-distribution/saksbehandlingstid.csv \\
      --measure-col Dager \\
      --group-col Enhet \\
      --title "Saksbehandlingstid per enhet" \\
      --source "Syntetisk eksempeldata (saksbehandlingstid.csv)" \\
      --requested-by "Fagavdelingen" \\
      --out examples/38-distribution/behandlingstid.html

What is built in, rather than left to whoever assembles the file:

  * **the bucket counts must add up.** Every row lands in exactly one bucket: the lower edge
    is inclusive and the upper edge is exclusive, except the last bucket, which is closed at
    the top so the largest value is never the one that falls off. The table carries the same
    counts as the drawing and a total, so the arithmetic is checkable on the page.
  * **the edges are printed.** They come from a 1-2-5 ladder and they are stated in the
    caption and in every table row, because a different width draws a different picture of
    the same rows. A picture whose axis is unstated cannot be checked by anyone.
  * **the mean never appears alone.** The stat line carries the median, the mean, p90 and the
    largest value together, and when the mean runs well above the median the page says so in
    words, since that gap is the whole reason this artefact exists.
  * **a value that is not a number is refused by name and row number.** Skipping it would
    change the count that the total row is checked against, silently.
  * **a group below the floor is named, not hidden.** `--min-group 5` stops a group of three
    cases from being drawn as if it were a shape, and the page lists what it left out and
    why. It does not pretend the rows are not in the source.
  * **there is no script.** A filter would re-lay the drawing, and what a script would have
    given the reader is already there: every count, in a table, per bucket and per group.

Stdlib only, like the rest of tools/. Python 3.8+.
"""
from __future__ import annotations

import argparse
import html
import math
import pathlib
import statistics
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

TEMPLATE = ROOT / "templates" / "distribution.html"
STRINGS = "distribution"
MAX_GROUPS = 8                # above this the page is a wall of small pictures
MAX_BUCKETS = 16              # above this a bar is thinner than its own count label
TARGET_BUCKETS = 10           # the width ladder aims here, then rounds to a nice number
SKEW_RATIO = 1.5              # mean over median by more than this is worth a sentence
CONCENTRATED = 40             # per cent in one bucket above which the page names that bucket
MAX_BYTES = 40 * 1024 * 1024

# The canvas. Units, not pixels: the SVG scales, and a theme's font size cannot move a bar.
W = 1000
LEFT = 12                     # padding, not a count axis: every bar carries its number
RIGHT = 16
TITLE_H = 22                  # the group's name
STAT_H = 18                   # n, median, mean, p90, largest
HEAD = TITLE_H + STAT_H + 8   # everything above the plot
PLOT_H = 110
COUNT_ROOM = 18               # room above the tallest bar for its own count
EDGE_H = 22                   # the interval edges under the plot
PANEL_GAP = 24
NICE = (1, 2, 5, 10)


# ------------------------------------------------------------------------------ numbers
def decimals_of(values: list[float]) -> int:
    """How many decimals the page prints: none for whole numbers, two otherwise.

    A page that prints 4 next to 4,25 in the same column invites the reader to think the
    first is exact and the second is not. One decision for the whole page.
    """
    return 0 if all(float(v).is_integer() for v in values) else 2


def fmt(value: float, lang: str, dec: int) -> str:
    """A number as the reader's locale writes it. The separator is decided at build time."""
    text = f"{value:,.{dec}f}"
    if lang == "nb":
        return text.replace(",", "\u00a0").replace(".", ",")
    return text.replace(",", "\u2009")


def stat(value: float, lang: str, dec: int) -> str:
    """A computed figure printed with the decimals it has, not the column's.

    The column decides the edges and the counts. A median of 6,5 printed as 6 in a table of
    whole days would be the kind of quiet rounding this whole artefact is an argument against,
    so a figure that is not whole keeps one decimal.
    """
    if dec:
        return fmt(value, lang, dec)
    return fmt(value, lang, 0 if float(value).is_integer() else 1)


def nice_width(span: float, target: int) -> float:
    """A bucket width a person would choose: 1, 2 or 5 times a power of ten.

    Not span / target: that produces edges at 3.47 and 6.94, and an axis nobody can hold in
    their head is an axis nobody checks. The ladder step is the one whose bucket count lands
    nearest the target rather than the first one that is wide enough: rounding up from 5.9 to
    10 would halve the number of buckets and hide the shape the page exists to show.
    """
    if span <= 0:
        return 1.0
    raw = span / max(1, target)
    magnitude = 10 ** math.floor(math.log10(raw))
    best: tuple[int, float] | None = None
    for step in NICE:
        width = step * magnitude
        count = max(1, math.ceil(span / width))
        score = (abs(count - target), width)
        if best is None or score < best:
            best = score
    return best[1] if best else 1.0


def edges_for(values: list[float], target: int) -> list[float]:
    """Bucket edges covering every value, from a nice width, widest at MAX_BUCKETS.

    The first edge is at or below the smallest value and the last is at or above the largest,
    so the closed-bucket rule below can put every row somewhere without a special case.
    """
    low, high = min(values), max(values)
    if low == high:
        # One value, so one bucket. A width of 1 is a presentational choice and the caption
        # says so; the alternative is a zero-width axis with a division by zero inside it.
        return [low, low + 1]
    width = nice_width(high - low, target)
    start = math.floor(low / width) * width
    count = math.ceil((high - start) / width) or 1
    while count > MAX_BUCKETS:              # a ladder step, not a fraction
        width *= 2
        start = math.floor(low / width) * width
        count = math.ceil((high - start) / width) or 1
    step = round(width, 10)
    return [round(start + i * step, 10) for i in range(count + 1)]


def bucket_of(value: float, edges: list[float]) -> int:
    """Which bucket a value belongs to. Lower edge inclusive, upper edge exclusive.

    The last bucket is closed at the top. A reader who sees the axis stop at 40 and a case of
    exactly 40 knows which bar it is in, and the alternative is a bar that does not exist for
    one value.
    """
    width = edges[1] - edges[0]
    index = int(math.floor((value - edges[0]) / width))
    return min(max(index, 0), len(edges) - 2)


def p90(values: list[float]) -> float:
    """The nearest observed value at or above the 90th percentile.

    Nearest observed, not interpolated: the caption claims "the value 90 per cent of the cases
    sit at or below", and an interpolated figure can sit between two cases and make that claim
    false. The median is allowed to be an average, because that is what a median is.
    """
    ordered = sorted(values)
    index = max(0, math.ceil(0.9 * len(ordered)) - 1)
    return ordered[min(index, len(ordered) - 1)]


def summarise(values: list[float]) -> dict:
    counts: dict[int, int] = {}
    return {
        "n": len(values),
        "min": min(values),
        "max": max(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "p90": p90(values),
    }


def buckets_of(values: list[float], edges: list[float]) -> list[int]:
    counts = [0] * (len(edges) - 1)
    for value in values:
        counts[bucket_of(value, edges)] += 1
    return counts


# --------------------------------------------------------------------------------- load
def load(path: pathlib.Path, measure: str, group: str, drop_missing: bool
         ) -> tuple[list[dict], int, list[str]]:
    """The rows that carry a number, with the count of the ones that do not.

    A row whose measure is empty is not a case with a value of zero, so it is refused unless
    the caller says otherwise, and when it is dropped the page says how many.
    """
    rows = tun_core.read_rows(path)
    if not rows:
        die(f"{path.name} has no rows")
    header = tun_core.columns(rows)
    for flag, name in (("--measure-col", measure), ("--group-col", group)):
        if name and name not in header:
            die(f"{flag} {name!r} is not a column in {path.name}. "
                f"Available: {', '.join(header)}")
    empty: list[int] = []
    bad: list[str] = []
    parsed: list[dict] = []
    for i, row in enumerate(rows, 2):
        raw = row.get(measure)
        number = tun_core.to_number(raw)
        if number is None:
            if raw is None or str(raw).strip() == "":
                empty.append(i)
            else:
                bad.append(f"{path.name}:{i}: {measure} is {str(raw).strip()!r}, "
                           f"which is not a number")
            continue
        parsed.append({"value": float(number),
                       "group": str(row.get(group) or "").strip() if group else ""})
    if bad:
        die(bad[0] + (f" (and {len(bad) - 1} more)" if len(bad) > 1 else "")
            + ". A row that cannot be read is refused, not skipped: skipping it would move "
              "the total the table is checked against.")
    if empty and not drop_missing:
        die(f"{len(empty)} of {len(rows)} rows have no value in {measure!r} "
            f"(first at line {empty[0]}). Those rows are not zeros. Filter them out of the "
            f"extract, or pass --drop-missing to leave them out and say how many on the page.")
    if not parsed:
        die(f"no row in {path.name} has a number in {measure!r}")
    return parsed, len(empty), header


def panels_of(parsed: list[dict], group: str, edges: list[float], min_group: int
              ) -> tuple[list[dict], list[dict]]:
    """One panel per group, in the order the file gives them, and the ones left out."""
    order: list[str] = []
    per: dict[str, list[float]] = {}
    for row in parsed:
        name = row["group"] if group else ""
        if name not in per:
            per[name] = []
            order.append(name)
        per[name].append(row["value"])
    if len(order) > MAX_GROUPS:
        die(f"{len(order)} groups is more than the {MAX_GROUPS} this page can draw without "
            f"becoming a wall of small pictures. Pick the groups that answer the question, "
            f"or build one file per group.")
    drawn, withheld = [], []
    for name in order:
        values = per[name]
        if group and min_group and len(values) < min_group:
            withheld.append({"group": name, "n": len(values)})
            continue
        drawn.append({"group": name, "values": values, "counts": buckets_of(values, edges),
                      **summarise(values)})
    if not drawn:
        die(f"every group has fewer than {min_group} rows, so nothing would be drawn. "
            f"Lower --min-group or drop it.")
    return drawn, withheld


# --------------------------------------------------------------------------------- draw
def draw(panels: list[dict], edges: list[float], measure: str, lang: str, dec: int,
         t: dict) -> tuple[str, int]:
    """The SVG: one panel per group, the same bucket edges in every panel.

    Shared edges make two panels comparable across, which is the reason to put them on one
    page. The count axis is per panel, because one large group would otherwise flatten a
    small one into a line, so every bar carries its own count instead of relying on height.
    """
    nb = lang == "nb"
    plot = W - LEFT - RIGHT
    buckets = len(edges) - 1
    bar = plot / buckets
    gap = 2.0 if bar > 12 else 0.5
    height = len(panels) * (HEAD + PLOT_H + EDGE_H + PANEL_GAP) - PANEL_GAP
    parts: list[str] = [
        f'<svg viewBox="0 0 {W} {height}" role="img" aria-labelledby="ds-t ds-d" '
        f'preserveAspectRatio="xMinYMin meet">',
        f'<title id="ds-t">{html.escape(t["svg_title"])}: {html.escape(measure)}</title>',
        f'<desc id="ds-d">{html.escape(i18n.fill(t["svg_desc"], measure=measure, n=sum(p["n"] for p in panels), buckets=buckets, median=fmt(panels[0]["median"], lang, dec)))}</desc>',
    ]

    def x_of(value: float) -> float:
        index = bucket_of(value, edges)
        width = edges[index + 1] - edges[index]
        inside = 0.0 if width == 0 else (value - edges[index]) / width
        return LEFT + (index + min(max(inside, 0.0), 1.0)) * bar

    y0 = 0
    for panel in panels:
        top = y0 + HEAD
        base = top + PLOT_H
        peak = max(panel["counts"]) or 1
        parts.append(f'<text class="ds-panel" x="0" y="{y0 + TITLE_H - 4}">'
                     f'{html.escape(panel["group"] or measure)}</text>')
        parts.append(f'<text class="ds-stat" x="0" y="{y0 + HEAD - 8}">'
                     f'{html.escape(i18n.fill(t["shape_line"], n=panel["n"],
                                              median=stat(panel["median"], lang, dec),
                                              mean=stat(panel["mean"], lang, dec),
                                              p90=stat(panel["p90"], lang, dec),
                                              max=stat(panel["max"], lang, dec)))}'
                     f'</text>')
        # No printed count axis: every bar carries its own number, so the height is a cue and
        # the text is the figure. A maximum label in the gutter was the same number twice.
        heights = []
        for index, count in enumerate(panel["counts"]):
            bar_h = (PLOT_H - COUNT_ROOM) * count / peak if count else 0.0
            heights.append(bar_h)
            if count:
                bx = LEFT + index * bar
                parts.append(f'<rect class="ds-bar" x="{bx + gap / 2:.1f}" '
                             f'y="{base - bar_h:.1f}" width="{bar - gap:.1f}" '
                             f'height="{bar_h:.1f}"><title>{html.escape(bucket_label(edges, index, lang, dec))}: {i18n.group_int(count, lang)}</title></rect>')
        parts.append(f'<line class="ds-base" x1="{LEFT}" y1="{base:.1f}" x2="{W - RIGHT}" '
                     f'y2="{base:.1f}"/>')
        # Three edges named, not all of them: the table below carries every boundary, and a
        # row of numbers under a bar chart is a row nobody reads.
        for index, anchor in ((0, "start"), (buckets // 2, "middle"), (buckets, "end")):
            parts.append(f'<text class="ds-edge" x="{LEFT + index * bar:.1f}" '
                         f'y="{base + EDGE_H - 4:.1f}" text-anchor="{anchor}">'
                         f'{html.escape(fmt(edges[index], lang, dec))}</text>')
        # The median, drawn where it actually sits, which is the figure the mean hides. Drawn
        # before the count labels so a dashed line never runs through a number.
        mx = x_of(panel["median"])
        parts.append(f'<line class="ds-median" x1="{mx:.1f}" y1="{top:.1f}" '
                     f'x2="{mx:.1f}" y2="{base:.1f}"><title>{html.escape(t["median_label"])}'
                     f': {html.escape(stat(panel["median"], lang, dec))}</title></line>')
        for index, count in enumerate(panel["counts"]):
            if count:
                parts.append(f'<text class="ds-count" x="{LEFT + index * bar + bar / 2:.1f}" '
                             f'y="{base - heights[index] - 5:.1f}" text-anchor="middle">'
                             f'{i18n.group_int(count, lang)}</text>')
        y0 += HEAD + PLOT_H + EDGE_H + PANEL_GAP

    parts.append("</svg>")
    return "\n".join(parts), height


def bucket_label(edges: list[float], index: int, lang: str, dec: int) -> str:
    lo, hi = edges[index], edges[index + 1]
    return f"{fmt(lo, lang, dec)} \u2013 {fmt(hi, lang, dec)}"


def shape_lines(panels: list[dict], edges: list[float], lang: str, dec: int,
                t: dict) -> str:
    """One sentence per group, generated from that group's own numbers.

    A picture shows the shape; a sentence says what the shape is. Neither is allowed to be
    the only thing on the page, and the sentence is written from the counts rather than from
    a judgement about them: which bucket is fullest is arithmetic, "the process is slow" is an
    opinion and does not belong in a generated file.
    """
    out = []
    for panel in panels:
        counts = panel["counts"]
        where = max(range(len(counts)), key=lambda i: counts[i])
        share = 100 * counts[where] / panel["n"]
        name = html.escape(panel["group"]) if panel["group"] else ""
        if panel["n"] == 1 or panel["min"] == panel["max"]:
            sentence = i18n.fill(t["shape_single"], n=panel["n"],
                                 value=stat(panel["min"], lang, dec))
        elif share >= CONCENTRATED:
            sentence = i18n.fill(t["shape_one"], share=f"{share:.0f}",
                                 lo=fmt(edges[where], lang, dec),
                                 hi=fmt(edges[where + 1], lang, dec),
                                 max=stat(panel["max"], lang, dec))
        else:
            sentence = i18n.fill(t["shape_spread"], share=f"{share:.0f}",
                                 max=stat(panel["max"], lang, dec))
        if panel["median"] and panel["mean"] / panel["median"] >= SKEW_RATIO:
            sentence += " " + i18n.fill(t["shape_skew"], mean=stat(panel["mean"], lang, dec),
                                        factor=fmt(panel["mean"] / panel["median"], lang, 1))
        if name:
            out.append(f"    <li><strong>{name}</strong> \u2014 {html.escape(sentence)}</li>")
        else:
            out.append(f"    <li>{html.escape(sentence)}</li>")
    return "\n".join(out)


# -------------------------------------------------------------------------------- table
def table_head(panels: list[dict], lang: str, dec: int, t: dict) -> str:
    cells = []
    for panel in panels:
        label = panel["group"] or t["col_total"]
        cells.append(f'      <th scope="col" class="num">'
                     f'{html.escape(label)} ({i18n.group_int(panel["n"], lang)})</th>')
    if len(panels) > 1:
        cells.append(f'      <th scope="col" class="num">{html.escape(t["col_total"])} '
                     f'({i18n.group_int(sum(p["n"] for p in panels), lang)})</th>')
    return "\n".join(cells)


def table_rows(panels: list[dict], edges: list[float], lang: str, dec: int) -> str:
    out = []
    for index in range(len(edges) - 1):
        cells = [f'<th scope="row">{html.escape(bucket_label(edges, index, lang, dec))}</th>']
        cells += [f'<td class="num">{i18n.group_int(p["counts"][index], lang)}</td>'
                  for p in panels]
        if len(panels) > 1:
            cells.append(f'<td class="num">'
                         f'{i18n.group_int(sum(p["counts"][index] for p in panels), lang)}</td>')
        out.append("      <tr>" + "".join(cells) + "</tr>")
    return "\n".join(out)


def total_row(panels: list[dict], lang: str, t: dict) -> str:
    cells = [f'<th scope="row">{html.escape(t["row_total"])}</th>']
    cells += [f'<td class="num">{i18n.group_int(p["n"], lang)}</td>' for p in panels]
    if len(panels) > 1:
        cells.append(f'<td class="num">'
                     f'{i18n.group_int(sum(p["n"] for p in panels), lang)}</td>')
    return "      <tr>" + "".join(cells) + "</tr>"


# --------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True, help="CSV with a row per case")
    ap.add_argument("--measure-col", required=True,
                    help="the numeric column whose shape is drawn")
    ap.add_argument("--group-col", default="",
                    help="the column to split into panels (empty for one panel)")
    ap.add_argument("--buckets", type=int, default=TARGET_BUCKETS,
                    help=f"how many buckets to aim for, rounded to a nice width "
                         f"(default {TARGET_BUCKETS}, at most {MAX_BUCKETS})")
    ap.add_argument("--min-group", type=int, default=0, metavar="N",
                    help="do not draw a group with fewer than N cases, and name it instead "
                         "(default 0: draw every group)")
    ap.add_argument("--drop-missing", action="store_true",
                    help="leave rows with an empty measure out, and print how many")
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

    if args.buckets < 1:
        die("--buckets must be at least 1")
    parsed, dropped, _header = load(args.data, args.measure_col, args.group_col,
                                   args.drop_missing)
    values = [row["value"] for row in parsed]
    dec = decimals_of(values)
    edges = edges_for(values, min(args.buckets, MAX_BUCKETS))
    panels, withheld = panels_of(parsed, args.group_col, edges, args.min_group)
    # The sum invariant, checked at build time as well as in the suite: a bar chart whose
    # counts do not add up to the row count is the one defect a reader cannot see.
    for panel in panels:
        if sum(panel["counts"]) != panel["n"]:
            die(f"internal: the buckets of {panel['group'] or 'the page'} hold "
                f"{sum(panel['counts'])} cases but {panel['n']} were read. This is a bug in "
                f"the builder, not in the data.")

    svg, _height = draw(panels, edges, args.measure_col, lang, dec, t)

    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)
    source = i18n.fill(t["source_line"], name=args.source or args.data.name, rows=len(parsed))
    if dropped:
        source += " · " + i18n.fill(t["dropped"], n=dropped)
    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=built,
                                           source=source, lang=lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    withheld_html = ""
    if withheld:
        lines = "".join(
            f'    <p>{html.escape(i18n.fill(t["withheld_line"], group=w["group"], n=w["n"], min=args.min_group))}</p>\n'
            for w in withheld)
        withheld_html = (f'  <div class="withheld">\n'
                         f'    <h2 id="wh-h">{html.escape(t["withheld_head"])}</h2>\n'
                         f'{lines}  </div>')

    legend = (f'<li><span class="sw" style="background:var(--bar)"></span>'
              f'{html.escape(t["legend_bar"])}</li>'
              f'<li><span class="ln"></span>{html.escape(t["legend_median"])}</li>')

    # The colours come from tools/tokens/: one seam with every other artefact. auto_dark: a
    # reader whose system is dark gets a dark distribution with no script.
    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css)))
    for token, value in {
        "{{TITLE}}": html.escape(args.title),
        "{{SUBTITLE}}": html.escape(i18n.fill(
            t["sub_line"], rows=len(parsed), buckets=len(edges) - 1,
            lo=fmt(edges[0], lang, dec), hi=fmt(edges[-1], lang, dec))),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(source),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{ROWS_INLINED}}": str(len(parsed)),
        "{{BUCKET_NOTE}}": html.escape(i18n.fill(
            t["buckets_note"], buckets=len(edges) - 1,
            width=fmt(edges[1] - edges[0], lang, dec))),
        "{{SVG}}": svg,
        "{{LEGEND}}": legend,
        "{{SHAPE_LINES}}": shape_lines(panels, edges, lang, dec, t),
        "{{CAPTION}}": html.escape(i18n.fill(t["caption"], measure=args.measure_col)),
        "{{WITHHELD}}": withheld_html,
        "{{TABLE_HEAD}}": table_head(panels, lang, dec, t),
        "{{TABLE_ROWS}}": table_rows(panels, edges, lang, dec),
        "{{TOTAL_ROW}}": total_row(panels, lang, t),
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

    print(f"cases         : {len(parsed)} in {len(panels)} group(s)")
    print(f"buckets       : {len(edges) - 1} of width {fmt(edges[1] - edges[0], lang, dec)}, "
          f"from {fmt(edges[0], lang, dec)} to {fmt(edges[-1], lang, dec)}")
    if dropped:
        print(f"dropped       : {dropped} row(s) with an empty measure")
    if withheld:
        print(f"not drawn     : {', '.join(w['group'] for w in withheld)} "
              f"(under {args.min_group} cases)")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
