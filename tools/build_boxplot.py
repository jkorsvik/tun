#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a standalone box plot: the spread of many groups on one scale.

A distribution per group is the honest answer to "how long does this take", and it stops
working at about six groups: six histograms is a wall. A box plot puts twenty groups on one
axis, which is the only shape here that answers "which of these is wide, which is late, and
which has a tail" for a whole list at once.

    python3 tools/build_boxplot.py \\
      --data examples/48-boxplot/saksbehandlingstid.csv \\
      --value Dager --group Enhet \\
      --title "Saksbehandlingstid per enhet" \\
      --source "Syntetisk eksempeldata (saksbehandlingstid.csv)" \\
      --requested-by "Fagavdelingen" \\
      --out examples/48-boxplot/boksplott.html

What is built in, rather than left to whoever assembles the file:

  * **n is printed at every box.** A box drawn over four observations has a median that is
    an accident and quartiles that are interpolation, and it looks exactly like a box drawn
    over four hundred. A group with fewer than three values is refused by name.
  * **the quartiles are computed one declared way**, interpolating between order statistics,
    and the rule is on the page. Two tools disagree about quartiles because they use
    different conventions; a figure nobody can reproduce is not a figure.
  * **the whiskers are Tukey's**: the furthest observation within 1.5 IQR of the box, and
    everything beyond it drawn as a dot and counted. The alternative, min and max, makes the
    whisker a range and hides exactly the tail this chart exists to show.
  * **a box hides the shape, and the page says so.** Two groups with identical quartiles can
    be one peak or two. This is the one defect no box plot can fix, so it is stated instead
    of drawn over, and the distribution (38) is named as the page to use when the shape is
    the question.
  * **the row order is a claim.** Sorted by median, or by name, and the page says which. An
    unsorted list of boxes is a pile.
  * **every five numbers are in a table**: n, first quartile, median, third quartile, and
    both whisker ends, per group. The drawing can be checked instead of trusted.
  * **there is no script.** A box plot is a snapshot; a filter would re-lay the rows.

Stdlib only, like the rest of tools/. Python 3.8+.
"""
from __future__ import annotations

import argparse
import html
import math
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

TEMPLATE = ROOT / "templates" / "boxplot.html"
STRINGS = "boxplot"
MIN_PER_GROUP = 3             # below this a box is a line with a box drawn round it
MAX_GROUPS = 24               # above this the row labels collide and the page is a wall
MAX_BYTES = 40 * 1024 * 1024
FENCE = 1.5                   # Tukey's rule, declared on the page

# The canvas. One unit is one pixel and the template refuses to scale below that, so the
# 14-unit text is 14 px.
W = 760
GUTTER = 168                  # the group names live here, right-aligned
PAD_R = 34
PAD_T = 34
ROW_H = 40
BOX_H = 20
DOT_R = 3
PLOT_W = W - GUTTER - PAD_R


# -------------------------------------------------------------------------------- numbers
def decimals_of(values: list[float]) -> int:
    if all(float(v).is_integer() for v in values):
        return 0
    return 2 if any(round(v, 1) != round(v, 2) for v in values) else 1


def smart(value: float, lang: str) -> str:
    """One figure, printed with the precision IT needs: 8 stays 8, 8,75 stays 8,75.

    A table where every cell carries two decimals reads as if the second one meant something,
    and a table that rounds 8,75 to 9 hides the interpolation. This keeps both: a whole number
    prints whole, an interpolated one prints as far as it needs.
    """
    return fmt(value, lang, decimals_of([value]))


def fmt(value: float, lang: str, dec: int) -> str:
    text = f"{value:,.{dec}f}"
    if lang == "nb":
        return text.replace(",", "\u00a0").replace(".", ",")
    return text.replace(",", "\u2009")


def quantile(ordered: list[float], p: float) -> float:
    """The p-quantile, interpolating between order statistics.

    One declared convention, because tools disagree and a figure nobody can reproduce is not a
    figure. This is the "linear" rule: position (n-1)p, interpolated between its neighbours.
    """
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * p
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (position - low) * (ordered[high] - ordered[low])


def box_of(values: list[float]) -> dict:
    """The five numbers, the Tukey whiskers and the outliers, from one group's values."""
    ordered = sorted(values)
    q1, mid, q3 = quantile(ordered, 0.25), quantile(ordered, 0.5), quantile(ordered, 0.75)
    iqr = q3 - q1
    low_fence, high_fence = q1 - FENCE * iqr, q3 + FENCE * iqr
    inside = [v for v in ordered if low_fence <= v <= high_fence]
    outliers = [v for v in ordered if v < low_fence or v > high_fence]
    return {"n": len(ordered), "q1": q1, "median": mid, "q3": q3,
            "low": inside[0] if inside else ordered[0],
            "high": inside[-1] if inside else ordered[-1],
            "outliers": outliers, "iqr": iqr}


# ----------------------------------------------------------------------------------- load
def load(path: pathlib.Path, value_col: str, group_col: str) -> dict[str, list[float]]:
    rows = tun_core.coerce_numbers(tun_core.read_rows(path))
    if not rows:
        die(f"{path} holds no rows")
    cols = tun_core.columns(rows)
    for name, flag in ((value_col, "--value"), (group_col, "--group")):
        if name not in cols:
            die(f"{flag} names {name!r}, which is not a column in {path.name}. "
                f"Columns: {', '.join(cols)}")
    if not tun_core.is_numeric_column(rows, value_col):
        die(f"--value names {value_col!r}, and that column is not numeric in every row. A box "
            f"plot is drawn on a number axis; a category on that axis is a bar chart.")

    groups: dict[str, list[float]] = {}
    skipped = 0
    for row in rows:
        value = tun_core.to_number(row.get(value_col))
        name = str(row.get(group_col, "")).strip()
        if value is None or not name:
            skipped += 1
            continue
        groups.setdefault(name, []).append(float(value))
    if not groups:
        die(f"no row in {path.name} has both a group and a number, so there is nothing to draw.")
    return groups, skipped


# ----------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True,
                    help="CSV with one row per observation")
    ap.add_argument("--value", required=True, help="the numeric column to draw")
    ap.add_argument("--group", required=True, help="the column that puts observations in groups")
    ap.add_argument("--order", choices=("median", "name"), default="median",
                    help="row order: by median (default) or by the group's own name")
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

    groups, skipped = load(args.data, args.value, args.group)
    if len(groups) > MAX_GROUPS:
        die(f"{len(groups)} groups is past the {MAX_GROUPS}-row ceiling. Above that the row "
            f"labels collide and the page stops being readable; group the smallest together, "
            f"or use the distribution (build_distribution.py) for the groups that matter.")
    thin = sorted((name, len(values)) for name, values in groups.items()
                  if len(values) < MIN_PER_GROUP)
    if thin:
        listed = ", ".join(f"{name} ({n})" for name, n in thin[:4])
        die(f"{len(thin)} group(s) hold fewer than {MIN_PER_GROUP} values: {listed}. A box "
            f"drawn over two observations is a line, and its quartiles are interpolation "
            f"rather than measurement. Merge them, or drop them from the extract.")

    boxes = {name: box_of(values) for name, values in groups.items()}
    order = (sorted(boxes, key=lambda name: (boxes[name]["median"], name))
             if args.order == "median" else sorted(boxes))

    every = [v for values in groups.values() for v in values]
    # Precision comes from the STATISTICS, not from the observations. Whole observations can
    # interpolate to a fractional quartile, and printing that to the observations' precision
    # rounds 8,75 to 9: the figure on the page then cannot be reproduced from the rows, which
    # is the one thing every number here has to survive.
    stats = [box[key] for box in boxes.values()
             for key in ("q1", "median", "q3", "low", "high")]
    dec = decimals_of(stats)
    low, high = min(every), max(every)
    if low == high:
        low, high = low - 1, high + 1
    air = (high - low) * 0.04

    def px(value: float) -> float:
        return GUTTER + (value - low + air) / (high - low + 2 * air) * PLOT_W

    height = PAD_T + ROW_H * len(order) + 46
    out = [f'<svg viewBox="0 0 {W} {height}" role="img" aria-labelledby="bx-t bx-d">',
           f'<title id="bx-t">{html.escape(t["svg_title"])}</title>',
           f'<desc id="bx-d">{html.escape(i18n.fill(t["svg_desc"], n=len(order), value=args.value))}</desc>']

    # A few round ticks along the axis, and the same numbers in the caption.
    step_ticks = 4
    for i in range(step_ticks + 1):
        value = low - air + (high - low + 2 * air) * i / step_ticks
        x = px(value)
        out.append(f'<line class="bx-grid" x1="{x:.2f}" y1="{PAD_T - 8}" x2="{x:.2f}" '
                   f'y2="{PAD_T + ROW_H * len(order)}"/>')
        out.append(f'<text class="bx-tick" x="{x:.2f}" y="{PAD_T + ROW_H * len(order) + 20}" '
                   f'text-anchor="middle">{html.escape(fmt(value, lang, dec))}</text>')

    for index, name in enumerate(order):
        box = boxes[name]
        cy = PAD_T + ROW_H * index + ROW_H / 2
        top = cy - BOX_H / 2
        out.append(f'<text class="bx-name" x="{GUTTER - 12}" y="{cy + 5:.2f}" '
                   f'text-anchor="end">{html.escape(name)}</text>')
        # whisker: one line from tip to tip, with caps, drawn under the box
        out.append(f'<line class="bx-whisker" x1="{px(box["low"]):.2f}" y1="{cy:.2f}" '
                   f'x2="{px(box["high"]):.2f}" y2="{cy:.2f}"/>')
        for tip in (box["low"], box["high"]):
            out.append(f'<line class="bx-cap" x1="{px(tip):.2f}" y1="{top + 4:.2f}" '
                       f'x2="{px(tip):.2f}" y2="{top + BOX_H - 4:.2f}"/>')
        out.append(f'<rect class="bx-box" data-group="{html.escape(name)}" '
                   f'x="{px(box["q1"]):.2f}" y="{top:.2f}" '
                   f'width="{max(1.0, px(box["q3"]) - px(box["q1"])):.2f}" height="{BOX_H}"/>')
        out.append(f'<line class="bx-median" x1="{px(box["median"]):.2f}" y1="{top:.2f}" '
                   f'x2="{px(box["median"]):.2f}" y2="{top + BOX_H:.2f}"/>')
        for value in box["outliers"]:
            out.append(f'<circle class="bx-outlier" data-group="{html.escape(name)}" '
                       f'cx="{px(value):.2f}" cy="{cy:.2f}" r="{DOT_R}"/>')

    out.append(f'<text class="bx-axis-title" x="{GUTTER + PLOT_W / 2:.2f}" '
               f'y="{height - 8}" text-anchor="middle">{html.escape(args.value)}</text>')
    out.append("</svg>")
    drawing = "\n".join(out)

    widest = max(boxes, key=lambda name: boxes[name]["iqr"])
    latest = max(boxes, key=lambda name: boxes[name]["median"])
    earliest = min(boxes, key=lambda name: boxes[name]["median"])
    tails = sum(len(box["outliers"]) for box in boxes.values())
    summary = i18n.fill(
        t["summary_line"], groups=len(order), value=args.value,
        late=latest, latev=smart(boxes[latest]["median"], lang),
        early=earliest, earlyv=smart(boxes[earliest]["median"], lang),
        wide=widest, widev=smart(boxes[widest]["iqr"], lang))
    if tails:
        summary += " " + i18n.fill(t["summary_tails"], n=tails, groups=len(order))
    else:
        summary += " " + t["summary_no_tails"]

    notes = [t["note_box"], t["note_quantiles"], t["note_fence"],
             i18n.fill(t["note_order"], rule=t["order_median"] if args.order == "median"
                       else t["order_name"]), t["note_n"]]
    if skipped:
        notes.append(i18n.fill(t["skipped"], n=skipped))

    rows_html = []
    for name in order:
        box = boxes[name]
        rows_html.append(
            "<tr>"
            f"<td>{html.escape(name)}</td>"
            f'<td class="num">{box["n"]}</td>'
            f'<td class="num">{html.escape(smart(box["low"], lang))}</td>'
            f'<td class="num">{html.escape(smart(box["q1"], lang))}</td>'
            f'<td class="num">{html.escape(smart(box["median"], lang))}</td>'
            f'<td class="num">{html.escape(smart(box["q3"], lang))}</td>'
            f'<td class="num">{html.escape(smart(box["high"], lang))}</td>'
            f'<td class="num">{len(box["outliers"])}</td>'
            "</tr>")

    source = args.source or NOT_STATED
    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)

    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=built,
                                           source=source, lang=lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css)))
    for token, value in {
        "{{TITLE}}": html.escape(args.title),
        "{{SUBTITLE}}": html.escape(i18n.fill(t["sub_line"], groups=len(order),
                                              rows=len(every), value=args.value)),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(i18n.fill(t["source_line"], name=source,
                                                 rows=len(every) + skipped)),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{ROWS_INLINED}}": str(len(every)),
        "{{CAPTION}}": html.escape(i18n.fill(t["caption"], groups=len(order))),
        "{{SUMMARY}}": html.escape(summary),
        "{{DRAWING}}": drawing,
        "{{NOTES}}": "".join(f"<li>{html.escape(n)}</li>" for n in notes),
        "{{TABLE_ROWS}}": "\n".join(rows_html),
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

    print(f"groups        : {len(order)} ({len(every)} observations)")
    print(f"order         : {args.order}")
    print(f"outliers      : {tails} beyond {FENCE} x IQR")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
