#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a standalone bullet chart: one row per unit, its value, its target, and the gap.

A scorecard (39) judges a handful of measures over time. This judges a LIST: forty units, each
with a number and a target, and the question is which of them is behind. It is the shape for
"which of these is off plan", where a table of two columns makes the reader do the subtraction
and a bar chart with no target line hides the only thing that matters.

    python3 tools/build_bullet.py \\
      --data examples/51-bullet/dekning.csv \\
      --label Enhet --value Dekning --target Maal --direction up \\
      --title "Dekning mot mål per enhet" \\
      --source "Syntetisk eksempeldata (dekning.csv)" \\
      --requested-by "Fagavdelingen" \\
      --out examples/51-bullet/dekning.html

What is built in, rather than left to whoever assembles the file:

  * **no direction, no verdict.** Whether being above the target is good or bad is a property
    of the measure, not of the picture, so `--direction up|down` is required. A page that
    cannot say which way is better cannot say who is behind.
  * **the target is drawn as a mark, and printed as a number.** A target is a policy, not a
    measurement: the mark says where the line was drawn, and the table says who drew it and
    when, so a reader can argue with the target instead of with the chart.
  * **the gap is a signed number in the unit of the measure**, with the sign meaning "how far
    past the target", on the good side. Never a colour alone: the colour is a summary, and the
    number is the answer.
  * **the axis starts at zero** when every value is positive, because a bar read from a
    non-zero baseline overstates a difference. When the data has negatives, zero is inside the
    axis and the picture says so.
  * **units that agree are one row each, and the count is printed.** Thirty behind out of
    forty is the sentence; the rows are the evidence.
  * **there is no script.** A target page is a snapshot of a period.

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

TEMPLATE = ROOT / "templates" / "bullet.html"
STRINGS = "bullet"
MAX_ROWS = 30
MAX_LABEL = 34
MAX_BYTES = 40 * 1024 * 1024

W = 780
GUTTER = 168
NUMW = 150                     # the three figures, right-aligned in their own column
PAD_R = 14
PAD_T = 40
ROW_H = 38
BAR_H = 14
PLOT_W = W - GUTTER - NUMW - PAD_R


def decimals_of(values: list[float]) -> int:
    if all(float(v).is_integer() for v in values):
        return 0
    return 2 if any(round(v, 1) != round(v, 2) for v in values) else 1


def fmt(value: float, lang: str, dec: int) -> str:
    text = f"{value:,.{dec}f}"
    if lang == "nb":
        return text.replace(",", "\u00a0").replace(".", ",")
    return text.replace(",", "\u2009")


def signed(value: float, lang: str, dec: int) -> str:
    """A gap with its sign, so the direction is in the characters and not only in the colour."""
    if abs(value) < 10 ** (-dec - 1):
        return fmt(0.0, lang, dec)
    sign = "\u2212" if value < 0 else "+"
    return sign + fmt(abs(value), lang, dec)


# ----------------------------------------------------------------------------------- load
def load(path: pathlib.Path, label_col: str, value_col: str, target_col: str) -> list[dict]:
    if not path.is_file():
        die(f"{path} does not exist")
    rows = tun_core.coerce_numbers(tun_core.read_rows(path))
    if not rows:
        die(f"{path.name} has no rows")
    header = tun_core.columns(rows)
    for name, flag in ((label_col, "--label"), (value_col, "--value"),
                       (target_col, "--target")):
        if name not in header:
            die(f"{flag} names {name!r}, which is not a column in {path.name}. "
                f"Columns: {', '.join(header)}")
    for column, flag in ((value_col, "--value"), (target_col, "--target")):
        if not tun_core.is_numeric_column(rows, column):
            die(f"{flag} names {column!r}, and that column is not numeric in every row. A bullet "
                f"chart compares two numbers; a category in either column is a count, so count "
                f"it first.")

    out = []
    for i, row in enumerate(rows, 2):
        label = str(row.get(label_col) or "").strip()
        if not label:
            continue
        if len(label) > MAX_LABEL:
            die(f"{path.name}:{i}: the label is {len(label)} characters, past the {MAX_LABEL} "
                f"this row holds. Shorten it in the extract; a truncated name is not a name.")
        value = tun_core.to_number(row.get(value_col))
        target = tun_core.to_number(row.get(target_col))
        if value is None or target is None:
            die(f"{path.name}:{i}: {label} has no value or no target. A bullet chart without a "
                f"target is a bar chart (build_dashboard.py); drop the row or fill the target.")
        out.append({"label": label, "value": float(value), "target": float(target)})
    if not out:
        die(f"no row in {path.name} has a label, a value and a target.")
    if len(out) > MAX_ROWS:
        die(f"{len(out)} rows is past the {MAX_ROWS}-row ceiling: the labels collide and the "
            f"bars are hairlines. Show the ones that are off target, or split the list.")
    return out


# ----------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True)
    ap.add_argument("--label", required=True, help="the column naming each unit")
    ap.add_argument("--value", required=True, help="the column holding the current number")
    ap.add_argument("--target", required=True, help="the column holding the target")
    ap.add_argument("--direction", choices=("up", "down"), required=True,
                    help="which way is better: up for more-is-better, down for less-is-better")
    ap.add_argument("--order", choices=("gap", "name"), default="gap",
                    help="rows sorted by how far past the target they are (default), or by name")
    ap.add_argument("--target-note", default="",
                    help="where the target comes from: a decision, a date, a document")
    ap.add_argument("--title", required=True)
    ap.add_argument("--source", default="")
    ap.add_argument("--requested-by", default="")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--feedback-to", default="", metavar="ADDRESS_OR_ISSUE_URL",
                    help=feedback_link.FLAG_HELP)
    i18n.add_lang_argument(ap)
    args = ap.parse_args(argv)
    t = i18n.load(STRINGS, args.lang)
    lang = args.lang
    sign = 1.0 if args.direction == "up" else -1.0

    rows = load(args.data, args.label, args.value, args.target)
    every = [r["value"] for r in rows] + [r["target"] for r in rows]
    dec = decimals_of(every)

    def past(row: dict) -> float:
        """How far past the target this row is, positive on the good side."""
        return (row["value"] - row["target"]) * sign

    behind = [r for r in rows if past(r) < 0]
    if args.order == "gap":
        rows.sort(key=lambda r: (past(r), r["label"]))
    else:
        rows.sort(key=lambda r: r["label"])

    low = min(0.0, min(every))
    high = max(every)
    if high == low:
        high = low + 1
    span = high - low
    # Padding on the low side is what made the first build print a tick at -2,9 while the page
    # said the axis starts at zero. When every value is positive the axis starts AT zero, and
    # only the high side is padded.
    low_pad = 0.0 if min(every) >= 0 else span * 0.03
    high_pad = span * 0.06
    axis_low, axis_high = low - low_pad, high + high_pad

    def px(value: float) -> float:
        return GUTTER + (value - axis_low) / (axis_high - axis_low) * PLOT_W

    height = PAD_T + ROW_H * len(rows) + 40
    out = [f'<svg viewBox="0 0 {W} {height}" role="img" aria-labelledby="bl-t bl-d">',
           f'<title id="bl-t">{html.escape(t["svg_title"])}</title>',
           f'<desc id="bl-d">{html.escape(i18n.fill(t["svg_desc"], n=len(rows), value=args.value, target=args.target))}</desc>']
    for i in range(5):
        value = axis_low + (axis_high - axis_low) * i / 4
        x = px(value)
        out.append(f'<line class="bl-grid" x1="{x:.2f}" y1="{PAD_T - 8}" x2="{x:.2f}" '
                   f'y2="{PAD_T + ROW_H * len(rows)}"/>')
        out.append(f'<text class="bl-tick" x="{x:.2f}" y="{PAD_T + ROW_H * len(rows) + 18}" '
                   f'text-anchor="middle">{html.escape(fmt(value, lang, dec))}</text>')
    out.append(f'<text class="bl-head" x="{W - PAD_R}" y="{PAD_T - 18}" text-anchor="end">'
               f'{html.escape(t["col_value"])}  ·  {html.escape(t["col_target"])}'
               f'  ·  {html.escape(t["col_gap"])}</text>')

    for index, row in enumerate(rows):
        cy = PAD_T + ROW_H * index + ROW_H / 2
        top = cy - BAR_H / 2
        good = past(row) >= 0
        out.append(f'<text class="bl-name" x="{GUTTER - 10}" y="{cy + 5:.2f}" '
                   f'text-anchor="end">{html.escape(row["label"])}</text>')
        # the track: the whole axis, faint, so a short bar reads as "short of the axis" and not
        # as "short of the target"
        out.append(f'<rect class="bl-track" x="{px(low):.2f}" y="{top:.2f}" '
                   f'width="{max(1.0, px(high) - px(low)):.2f}" height="{BAR_H}" rx="2"/>')
        out.append(f'<rect class="bl-bar{" bl-good" if good else " bl-behind"}" '
                   f'data-label="{html.escape(row["label"])}" x="{px(min(row["value"], 0.0)):.2f}" '
                   f'y="{top:.2f}" width="{max(1.5, abs(px(row["value"]) - px(min(row["value"], 0.0)))):.2f}" '
                   f'height="{BAR_H}" rx="2"/>')
        # the target: a mark across the bar, and the one repeated reading on the page
        out.append(f'<line class="bl-target" data-label="{html.escape(row["label"])}" '
                   f'x1="{px(row["target"]):.2f}" y1="{top - 4:.2f}" '
                   f'x2="{px(row["target"]):.2f}" y2="{top + BAR_H + 4:.2f}"/>')
        figures = (f'{fmt(row["value"], lang, dec)}  ·  {fmt(row["target"], lang, dec)}'
                   f'  ·  {signed(past(row), lang, dec)}')
        out.append(f'<text class="bl-num" x="{W - PAD_R}" y="{cy + 5:.2f}" '
                   f'text-anchor="end">{html.escape(figures)}</text>')
    out.append("</svg>")
    drawing = "\n".join(out)

    worst = min(rows, key=past)
    beat = [r for r in rows if past(r) > 0]
    summary = i18n.fill(t["summary_line"], n=len(rows), behind=len(behind),
                        at=len(rows) - len(behind) - len(beat), ahead=len(beat))
    if behind:
        summary += " " + i18n.fill(t["summary_worst"], label=worst["label"],
                                   gap=fmt(abs(past(worst)), lang, dec))
    else:
        summary += " " + t["summary_none"]
    if args.target_note:
        summary += " " + i18n.fill(t["summary_target_note"], note=args.target_note)
    else:
        summary += " " + t["summary_no_target_note"]

    notes = [t["note_direction"], t["note_target"], t["note_gap"], t["note_zero"],
             i18n.fill(t["note_order"], rule=t["order_gap"] if args.order == "gap"
                       else t["order_name"])]

    table = []
    for row in rows:
        table.append(
            "<tr>"
            f"<td>{html.escape(row['label'])}</td>"
            f'<td class="num">{html.escape(fmt(row["value"], lang, dec))}</td>'
            f'<td class="num">{html.escape(fmt(row["target"], lang, dec))}</td>'
            f'<td class="num">{html.escape(signed(past(row), lang, dec))}</td>'
            f'<td>{html.escape(t["state_ahead"] if past(row) > 0 else
                               (t["state_behind"] if past(row) < 0 else t["state_at"]))}</td>'
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
        "{{SUBTITLE}}": html.escape(i18n.fill(t["sub_line"], n=len(rows),
                                              direction=t["dir_up"] if args.direction == "up"
                                              else t["dir_down"])),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(i18n.fill(t["source_line"], name=source, rows=len(rows))),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{ROWS_INLINED}}": str(len(rows)),
        "{{CAPTION}}": html.escape(t["caption"]),
        "{{SUMMARY}}": html.escape(summary),
        "{{DRAWING}}": drawing,
        "{{NOTES}}": "".join(f"<li>{html.escape(n)}</li>" for n in notes),
        "{{TABLE_ROWS}}": "\n".join(table),
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

    print(f"rows          : {len(rows)} ({len(behind)} behind, {len(beat)} past the target)")
    print(f"direction     : {args.direction} is better")
    print(f"worst         : {worst['label']} by {abs(past(worst)):.{dec}f}")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
