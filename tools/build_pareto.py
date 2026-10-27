#!/usr/bin/env python3
"""Build a standalone Pareto: the few categories that make up most of the total.

A composition (41) splits a total into parts. This answers the next question: of these forty
categories, which handful accounts for eighty percent. Sorted bars plus a cumulative line, with
the count of categories that reach the threshold printed as a sentence.

    python3 tools/build_pareto.py \\
      --data examples/52-pareto/henvendelser.csv \\
      --label Arsak --value Antall \\
      --title "Henvendelser per årsak" \\
      --source "Syntetisk eksempeldata (henvendelser.csv)" \\
      --requested-by "Kundesenteret" \\
      --out examples/52-pareto/arsaker.html

What is built in, rather than left to whoever assembles the file:

  * **the sort is the claim, and it is stated.** "Sorted by size, largest first" is on the page,
    because a Pareto whose bars are in source order is a bar chart with a line drawn over it.
  * **the cumulative line ends at the total it was computed from.** Every point is printed in
    the table, and the last one is 100 percent of the categories drawn.
  * **the folded tail keeps its arithmetic.** Past `--top` categories the rest become one bar
    labelled with its count, so nothing is dropped and the total does not move.
  * **negative values are refused by name.** A Pareto adds quantities; a negative contribution
    makes the cumulative line run backwards, which is not a picture of anything.
  * **the shares add up.** Printed shares use the largest remainder, so a column of them is
    exactly 100,0 and the reader can add them without finding 99,9.
  * **the two axes are labelled and explained.** A cumulative percentage needs a second scale;
    the page says so, so nobody reads the line against the left axis.
  * **there is no script.** A snapshot of one period.

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

TEMPLATE = ROOT / "templates" / "pareto.html"
STRINGS = "pareto"
MAX_BARS = 16                 # drawn bars, the folded tail counts as one
MAX_BYTES = 40 * 1024 * 1024
SHARE_DP = 1

W = 820
MIN_GUTTER = [96]             # the left axis; the real width is measured from the labels
RIGHT = 66                    # the cumulative axis, wide enough for "100 %"
LABEL_W = 148                 # the value-and-share column, between the bars and the axis
PAD_T = 40
ROW_H = 34
BAR_H = 22
# The plot width is computed per build, from the measured gutter and the fixed right axis.


def decimals_of(values: list[float]) -> int:
    if all(float(v).is_integer() for v in values):
        return 0
    return 2 if any(round(v, 1) != round(v, 2) for v in values) else 1


def fmt(value: float, lang: str, dec: int) -> str:
    text = f"{value:,.{dec}f}"
    if lang == "nb":
        return text.replace(",", "\u00a0").replace(".", ",")
    return text.replace(",", "\u2009")


def largest_remainder(values: list[float], total: float, places: int = SHARE_DP) -> list[int]:
    """Shares in units of 10^-places that add up to exactly 100, by largest remainder."""
    if total <= 0:
        return [0] * len(values)
    scale = 10 ** places
    exact = [v / total * 100 * scale for v in values]
    floors = [math.floor(x) for x in exact]
    short = round(100 * scale) - sum(floors)
    order = sorted(range(len(values)), key=lambda i: (-(exact[i] - floors[i]), i))
    for i in order[:max(0, short)]:
        floors[i] += 1
    return floors


# ----------------------------------------------------------------------------------- load
def load(path: pathlib.Path, label_col: str, value_col: str) -> tuple[list[dict], int]:
    if not path.is_file():
        die(f"{path} does not exist")
    rows = tun_core.coerce_numbers(tun_core.read_rows(path))
    if not rows:
        die(f"{path.name} has no rows")
    header = tun_core.columns(rows)
    for name, flag in ((label_col, "--label"), (value_col, "--value")):
        if name not in header:
            die(f"{flag} names {name!r}, which is not a column in {path.name}. "
                f"Columns: {', '.join(header)}")
    if not tun_core.is_numeric_column(rows, value_col):
        die(f"--value names {value_col!r}, and that column is not numeric in every row. A Pareto "
            f"adds quantities; a category in that column is a count, so count it first.")

    summed: dict[str, float] = {}
    merged = 0
    for i, row in enumerate(rows, 2):
        label = str(row.get(label_col) or "").strip()
        if not label:
            continue
        value = tun_core.to_number(row.get(value_col))
        if value is None:
            die(f"{path.name}:{i}: {label!r} has no number in {value_col}. Sum or fix it in the "
                f"extract; a Pareto cannot draw an empty bar.")
        if float(value) < 0:
            die(f"{path.name}:{i}: {label!r} is {value}, and a Pareto cannot hold a negative "
                f"contribution: the cumulative line would run backwards. Filter the credits out, "
                f"or use the waterfall (build_waterfall.py) if the question is what moved a total.")
        if label in summed:
            merged += 1
        summed[label] = summed.get(label, 0.0) + float(value)
    if not summed:
        die(f"no row in {path.name} has a label and a number.")
    total = sum(summed.values())
    if total <= 0:
        die(f"every value in {path.name} is zero, so there is no total to split.")
    out = [{"label": label, "value": value} for label, value in summed.items()]
    out.sort(key=lambda r: (-r["value"], r["label"]))
    return out, merged


# ----------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True)
    ap.add_argument("--label", required=True, help="the column naming each category")
    ap.add_argument("--value", required=True, help="the additive quantity")
    ap.add_argument("--top", type=int, default=12, metavar="N",
                    help=f"how many categories to draw (default 12, at most {MAX_BARS}); the rest "
                         f"become one folded bar that keeps its count")
    ap.add_argument("--threshold", type=float, default=80.0, metavar="PCT",
                    help="the share that defines the vital few (default 80)")
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

    if args.top < 2:
        die("--top needs at least 2 categories: with one bar there is no shape to read.")
    if args.top > MAX_BARS:
        die(f"--top {args.top} is past the {MAX_BARS}-bar ceiling; the axis labels stop fitting. "
            f"Fold harder, or split the extract by period.")
    if not 0 < args.threshold < 100:
        die(f"--threshold {args.threshold} is not a share between 0 and 100.")

    rows, merged = load(args.data, args.label, args.value)
    total = sum(r["value"] for r in rows)
    drawn = rows[:args.top]
    tail = rows[args.top:]
    if tail:
        drawn = drawn + [{"label": i18n.fill(t["folded_label"], n=len(tail)),
                          "value": sum(r["value"] for r in tail), "folded": True}]
    shares = largest_remainder([r["value"] for r in drawn], total)
    # The cumulative column is computed from the EXACT values and printed once per bar; the last
    # one is 100,0 by construction, and the suite checks that it is.
    cumulative: list[float] = []
    running = 0.0
    for row in drawn:
        running += row["value"]
        cumulative.append(running / total * 100)

    # The vital few are counted over the REAL categories, never over the folded bar: "the
    # largest thirteen" would then include a bar that stands for ten categories.
    running_all = 0.0
    vital = len(rows)
    for index, row in enumerate(rows, 1):
        running_all += row["value"]
        if running_all / total * 100 >= args.threshold:
            vital = index
            break
    dec = decimals_of([r["value"] for r in rows])
    biggest = rows[0]

    height = PAD_T + ROW_H * len(drawn) + 46
    plot_h = ROW_H * len(drawn)
    max_value = max(r["value"] for r in drawn)
    # The names are drawn right-aligned in the gutter, so the gutter has to be wide enough for
    # the longest one: a fixed 62 px clipped "Fakturafeil" to "kturafeil" on the first build.
    GUTTER = min(260, max(MIN_GUTTER[0], int(max(len(r["label"]) for r in drawn) * 7.6) + 22))
    # Four columns: names, bars, the value labels, and the percentage axis. The labels get
    # their own column because both alternatives collide: outside the bar the cumulative line
    # prints through them, and inside it a short bar is narrower than its own number.
    plot_w = max(120, W - GUTTER - LABEL_W - RIGHT)
    bar_max = max(1.0, plot_w - 4)

    def bar_w(value: float) -> float:
        return max(1.0, value / max_value * bar_max)

    def cum_y(pct: float) -> float:
        return PAD_T + plot_h - pct / 100 * (plot_h - 8)

    out = [f'<svg viewBox="0 0 {W} {height}" role="img" aria-labelledby="pa-t pa-d">',
           f'<title id="pa-t">{html.escape(t["svg_title"])}</title>',
           f'<desc id="pa-d">{html.escape(i18n.fill(t["svg_desc"], n=len(rows), value=args.value, threshold=f"{args.threshold:g}"))}</desc>']
    # left axis ticks: the bar scale, in the measure's own unit
    for i in range(5):
        value = max_value * i / 4
        x = GUTTER + bar_w(value)
        out.append(f'<line class="pa-grid" x1="{x:.2f}" y1="{PAD_T - 8}" x2="{x:.2f}" '
                   f'y2="{PAD_T + plot_h}"/>')
        out.append(f'<text class="pa-tick" x="{x:.2f}" y="{PAD_T + plot_h + 18}" '
                   f'text-anchor="middle">{html.escape(fmt(value, lang, dec))}</text>')
    # right axis: the cumulative percentage, labelled as its own scale
    for pct in (0, 25, 50, 75, 100):
        y = cum_y(pct)
        out.append(f'<text class="pa-pct" x="{W - RIGHT + 12}" y="{y + 4:.2f}">'
                   f'{pct} %</text>')
    out.append(f'<text class="pa-axis-title" x="{W - 14}" y="{PAD_T - 14}" '
               f'text-anchor="end">{html.escape(t["cumulative_axis"])}</text>')

    for index, row in enumerate(drawn):
        cy = PAD_T + index * ROW_H + ROW_H / 2
        top = cy - BAR_H / 2
        out.append(f'<text class="pa-name" x="{GUTTER - 10}" y="{cy + 5:.2f}" '
                   f'text-anchor="end">{html.escape(row["label"])}</text>')
        cls = "pa-bar pa-folded" if row.get("folded") else "pa-bar"
        out.append(f'<rect class="{cls}" data-label="{html.escape(row["label"])}" '
                   f'x="{GUTTER}" y="{top:.2f}" width="{bar_w(row["value"]):.2f}" '
                   f'height="{BAR_H}" rx="2"/>')
        # In its own column, right-aligned against the percentage axis, so neither the line
        # nor the bar can cross it.
        out.append(f'<text class="pa-val" x="{W - RIGHT - 12}" '
                   f'y="{cy + 5:.2f}" text-anchor="end">{html.escape(fmt(row["value"], lang, dec))}'
                   f' ({html.escape(fmt(shares[index] / 10 ** SHARE_DP, lang, SHARE_DP))} %)</text>')

    points = " ".join(f"{GUTTER + bar_w(r['value']):.2f},{cum_y(c):.2f}"
                      for r, c in zip(drawn, cumulative))
    out.append(f'<polyline class="pa-cum" points="{points}"/>')
    for index, (row, pct) in enumerate(zip(drawn, cumulative)):
        cx = GUTTER + bar_w(row["value"])
        out.append(f'<circle class="pa-dot" data-label="{html.escape(row["label"])}" '
                   f'cx="{cx:.2f}" cy="{cum_y(pct):.2f}" r="3.5"/>')
    out.append("</svg>")
    drawing = "\n".join(out)

    summary = i18n.fill(t["summary_line"], n=len(rows), total=fmt(total, lang, dec),
                        threshold=f"{args.threshold:g}", vital=vital)
    summary += " " + i18n.fill(t["summary_biggest"], label=biggest["label"],
                               value=fmt(biggest["value"], lang, dec),
                               share=fmt(shares[0] / 10 ** SHARE_DP, lang, SHARE_DP))
    if tail:
        summary += " " + i18n.fill(t["summary_folded"], n=len(tail), drawn=args.top)
    if merged:
        summary += " " + i18n.fill(t["summary_merged"], n=merged)

    notes = [t["note_sort"], t["note_cumulative"], t["note_axes"], t["note_fold"],
             t["note_shares"]]

    table = []
    for index, (row, share) in enumerate(zip(drawn, shares)):
        table.append(
            "<tr>"
            f"<td>{html.escape(row['label'])}</td>"
            f'<td class="num">{html.escape(fmt(row["value"], lang, dec))}</td>'
            f'<td class="num">{html.escape(fmt(share / 10 ** SHARE_DP, lang, SHARE_DP))}</td>'
            f'<td class="num">{html.escape(fmt(cumulative[index], lang, SHARE_DP))}</td>'
            "</tr>")
    share_sum = sum(shares) / 10 ** SHARE_DP

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
                                              total=fmt(total, lang, dec))),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(i18n.fill(t["source_line"], name=source, rows=len(rows))),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{ROWS_INLINED}}": str(len(rows)),
        "{{CAPTION}}": html.escape(i18n.fill(t["caption"], threshold=f"{args.threshold:g}")),
        "{{SUMMARY}}": html.escape(summary),
        "{{DRAWING}}": drawing,
        "{{NOTES}}": "".join(f"<li>{html.escape(n)}</li>" for n in notes),
        "{{TABLE_ROWS}}": "\n".join(table),
        "{{TABLE_CAPTION}}": html.escape(i18n.fill(t["table_caption"],
                                                   sum=fmt(share_sum, lang, SHARE_DP))),
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

    print(f"categories    : {len(rows)} ({len(drawn)} drawn, {len(tail)} folded)")
    print(f"total         : {fmt(total, 'nb', dec)}")
    print(f"vital few     : {vital} categories reach {args.threshold:g} %")
    print(f"shares add to : {share_sum:.1f}")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
