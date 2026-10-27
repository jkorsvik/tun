#!/usr/bin/env python3
"""Build a standalone heatmap: one number per row-and-column cell, drawn as a shade.

A heatmap answers "where is the mass, and where is there none". It is drawn badly almost
everywhere, in five ways, and this builder refuses all five:

  * **the scale is not stated.** A shade nobody can convert back into a number is decoration.
    Every cell here prints its own value, and the legend prints the numeric range of every
    shade, so the colour is a second reading of a number that is already on the page.
  * **the ends of the scale are the data's own extremes**, so one outlier flattens the rest.
    The scale is stated on the page, and `--clamp` fixes the top of it: past that point the
    shade means "at least", which the legend says and the page counts.
  * **an empty cell is drawn as zero.** They are different findings: no cases, versus no
    cases *recorded*. A missing cell gets its own hatch, its own legend entry and the dash.
  * **the ramp is not ordered.** A hue ramp (blue to red through green) has no direction, and
    two shades of different lightness can read as the same value. This ramp is one hue and
    strictly decreasing lightness, which the suite checks.
  * **colour alone carries the number.** Every cell prints it, and the ink is chosen per cell
    by measured contrast against that cell's own fill, so a dark cell cannot swallow its text.

    python3 tools/build_heatmap.py \\
      --data examples/43-heatmap/henvendelser.csv \\
      --row Enhet --col Uke --measure Antall \\
      --title "Henvendelser per enhet og uke" \\
      --source "Syntetisk eksempeldata (henvendelser.csv)" \\
      --requested-by "Kundeservice" \\
      --out examples/43-heatmap/varmekart.html

There is no script in the page: every figure is worked out here, and a filter would have to
re-lay the drawing, which is the claim being made.

Stdlib only, like the rest of tools/. Python 3.8+.
"""
from __future__ import annotations

import argparse
import html
import pathlib
import sys
from decimal import Decimal, ROUND_HALF_UP

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

TEMPLATE = ROOT / "templates" / "heatmap.html"
STRINGS = "heatmap"

# The canvas is units, not pixels: the SVG scales, and the page never lets it scale below
# 1 unit = 1 px, so 14 units of text is 14 px of text.
W = 1000
LEFT = 16
RIGHT = 16
TOP = 30                  # the column headers above the first row
ROW_H = 34
CHAR_W = 7.4              # units one character of 14 px system sans needs, with margin
MIN_CELL = 46             # narrower than this, a five-digit number does not fit
MIN_LABEL = 60
MAX_LABEL = 240           # above this the drawing is all row names and no cells
MAX_COLS = 12             # above this the column headers run together
MAX_ROWS = 60             # above this a page is a table, not a picture
MAX_BYTES = 40 * 1024 * 1024

# Named here, literally, so the i18n gate can see that every key is used: `t[f"agg_{x}"]`
# is invisible to a scanner that reads the source.
AGG_KEYS = {"sum": "agg_sum", "mean": "agg_mean", "count": "agg_count"}
TOTAL_KEYS = {"sum": "col_total_sum", "mean": "col_total_mean", "count": "col_total_count"}

BINS = 5
# One hue (the design system blue #2F5D9E) mixed into white, at fractions chosen so that EVERY
# stop has an ink with a contrast of at least 4.5:1. The fractions skip the narrow band
# around 0.86, where neither dark nor white ink reaches 4.5 against the fill.
RAMP_T = (0.12, 0.32, 0.55, 0.78, 1.00)
BRAND = (47, 93, 158)
INK = (10, 10, 10)
WHITE = (255, 255, 255)
MISSING_FILL = "#f2f2f2"


# ------------------------------------------------------------------------------ colour
def _channel(value: float) -> float:
    value /= 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def hexa(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def mix(fraction: float, base: tuple[int, int, int] = WHITE,
        brand: tuple[int, int, int] = BRAND) -> tuple[int, int, int]:
    """The brand colour drawn that far out of a base: 0 is the base, 1 is the brand."""
    return tuple(round(base[i] * (1 - fraction) + brand[i] * fraction) for i in range(3))  # type: ignore[return-value]


# The dark page needs its own ramp, and not by re-pointing this one: blue on #0E1C2E is
# 1.31:1 against the panel, so a coloured cell would read as an empty one. The dark ramp is
# mixed from the panel toward a light teal, which puts the strongest value at the LIGHT end.
# Both ramps are checked at build time: every stop must have an ink at 4.5:1, or the page is
# refused rather than shipped with a number nobody can read.
DARK_BASE = (14, 28, 46)          # --panel in theme-dark for the neutral palette
DARK_BRAND = (127, 212, 200)      # a light teal, the dark theme's own first series colour
RAMP = [mix(t) for t in RAMP_T]
RAMP_DARK = [mix(t, DARK_BASE, DARK_BRAND) for t in RAMP_T]

for _stop in RAMP + RAMP_DARK:
    if contrast(_stop, (10, 10, 10)) < 4.5 and contrast(_stop, WHITE) < 4.5:
        raise SystemExit(f"heatmap ramp: no ink reaches 4.5:1 against {hexa(_stop)}")


def ink_for(fill: tuple[int, int, int]) -> str:
    """The ink with more contrast against this fill, measured rather than assumed."""
    return hexa(INK) if contrast(fill, INK) >= contrast(fill, WHITE) else "#ffffff"


# ------------------------------------------------------------------------------ numbers
def fmt(value: float, lang: str, decimals: int = 0) -> str:
    """A number as the reader's locale writes it, to the decimals it was asked for."""
    quantum = Decimal(1).scaleb(-decimals)
    rounded = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    text = f"{rounded:,.{decimals}f}"
    if lang != "nb":
        return text.replace(",", "\u2009")
    # Norwegian writes 1 234,5: the point becomes the decimal comma, and the thousands
    # separator a space. Done through a marker, so the point of one cannot touch the other.
    return text.replace(",", "\u0000").replace(".", ",").replace("\u0000", "\u00a0")


def parse_number(value, col: str, row_no: int):
    """The measure's value, or the first unreadable cell named as the thing to fix."""
    number = tun_core.to_number(value)
    if number is None:
        die(f"{col!r} must hold numbers, and row {row_no} holds {value!r}. A heatmap shades "
            f"a quantity, so a cell that is not a number cannot be placed on the scale. Fix "
            f"the extract, or pass --agg count to draw how many rows fall in each cell.")
    return float(number)


# --------------------------------------------------------------------------------- load
def load(path: pathlib.Path, row_col: str, col_col: str, measure: str | None,
         agg: str) -> tuple[dict, int, int]:
    """Sum (or average, or count) the measure into one value per (row, col) cell.

    Returns the cells, how many duplicate (row, col) rows were combined, and how many rows
    were skipped because the row or the column was empty.
    """
    if not path.is_file():
        die(f"{path} does not exist")
    rows = tun_core.read_rows(path)
    if not rows:
        die(f"{path.name} has no rows")
    header = tun_core.columns(rows)
    for flag, name in (("--row", row_col), ("--col", col_col), ("--measure", measure)):
        if name and name not in header:
            die(f"{flag} {name!r} is not a column in {path.name}. "
                f"Available: {', '.join(header)}")

    total: dict[tuple[str, str], float] = {}
    counted: dict[tuple[str, str], int] = {}
    combined = 0
    skipped = 0
    for index, row in enumerate(rows, start=2):        # row 1 is the header
        key_row = str(row.get(row_col) or "").strip()
        key_col = str(row.get(col_col) or "").strip()
        if not key_row or not key_col:
            skipped += 1
            continue
        key = (key_row, key_col)
        if key in total:
            combined += 1
        total[key] = total.get(key, 0.0) + (0.0 if measure is None
                                           else parse_number(row.get(measure), measure, index))
        counted[key] = counted.get(key, 0) + 1

    if not total:
        die(f"no row in {path.name} has both {row_col!r} and {col_col!r} filled in, so there "
            f"are no cells to draw")
    cells = {}
    for key, summed in total.items():
        if agg == "count":
            cells[key] = float(counted[key])
        elif agg == "mean":
            cells[key] = summed / counted[key]
        else:
            cells[key] = summed
    return cells, combined, skipped


def negative_name(cells: dict) -> str | None:
    for (key_row, key_col), value in cells.items():
        if value < 0:
            return f"{key_row} / {key_col}"
    return None


def _round(value: float, decimals: int) -> float:
    quantum = Decimal(1).scaleb(-decimals)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def scale_of(cells: dict, clamp: float | None, decimals: int) -> list[dict]:
    """The bands: equal width, from the lowest value to the top of the scale.

    The edges are rounded to the precision the page prints, and the SAME rounded edges decide
    which band a cell gets. Otherwise the legend says "13-28" and "28-44" while a cell holding
    28 sits in the first band: the printed range and the drawn shade would disagree, which is
    the one thing a legend may never do.
    """
    values = sorted(cells.values())
    low = _round(values[0], decimals)
    high = _round(max(values[-1], 0.0), decimals)
    top = _round(clamp, decimals) if clamp is not None else high
    if clamp is not None and top <= low:
        die(f"--clamp {fmt(clamp, 'nb', decimals)} is not above the lowest value "
            f"({fmt(low, 'nb', decimals)}), so every cell would sit in the top band. Give a "
            f"higher clamp, or drop the flag.")
    if top <= low:                                   # every cell holds the same number
        return [{"low": low, "high": low, "band": BINS - 1, "fill": RAMP[-1],
                 "dark": RAMP_DARK[-1], "ink": ink_for(RAMP[-1]),
                 "dark_ink": ink_for(RAMP_DARK[-1])}]
    width = (top - low) / BINS
    edges = [_round(low + i * width, decimals) for i in range(BINS + 1)]
    edges[-1] = top
    if len(set(edges)) < BINS + 1:
        die(f"the values run from {fmt(low, 'nb', decimals)} to {fmt(top, 'nb', decimals)}, "
            f"which is too narrow for {BINS} bands at {decimals} decimal(s): two edges would "
            f"round to the same number and the legend would print a range that is empty. Pass "
            f"more decimals, or fewer bands' worth of precision.")
    return [{"low": edges[i], "high": edges[i + 1], "edge": edges[i], "band": i,
             "fill": RAMP[i], "dark": RAMP_DARK[i], "ink": ink_for(RAMP[i]),
             "dark_ink": ink_for(RAMP_DARK[i])} for i in range(BINS)]


def bin_index(value: float, bins: list[dict]) -> int:
    """Which shade a value gets, from the same edges the legend prints."""
    for i, band in enumerate(bins[:-1]):
        if value < band["high"]:
            return i
    return len(bins) - 1


def layout_of(row_names: list[str], col_names: list[str], values: list[str]) -> dict:
    """The gutter, the cell size, and whether the names fit the canvas at all.

    Measured from the longest name and the longest figure rather than guessed, and refused
    with the numbers when they do not fit: a page whose names are cut off or whose figures
    overrun their cells is worse than a page that says the drawing needs two pages.
    """
    label = max((len(name) for name in row_names), default=1) * CHAR_W + 10
    label = max(min(label, MAX_LABEL), MIN_LABEL)
    body = W - LEFT - RIGHT - label
    cell = body / len(col_names)
    wanted = max((len(text) for text in values), default=1) * CHAR_W + 8
    if cell < max(MIN_CELL, wanted):
        die(f"{len(col_names)} columns need {max(MIN_CELL, wanted):.0f} units each for their "
            f"figures, and the canvas has {cell:.0f} left after the row names. Draw at most "
            f"{min(MAX_COLS, int(body // max(MIN_CELL, wanted)))} columns on one page: group "
            f"the rest, or build a second page for the other half.")
    header = max((len(name) for name in col_names), default=1) * CHAR_W + 8
    if header > cell:
        widest = max(col_names, key=len)
        die(f"the column name {widest!r} needs {header:.0f} units and a cell has "
            f"{cell:.0f}. Shorten the column names, or draw fewer columns on one page.")
    return {"label": label, "cell": cell, "header": header}


# --------------------------------------------------------------------------------- draw
def draw(rows: list[dict], col_names: list[str], bins: list[dict], box: dict,
         lang: str, decimals: int, t: dict) -> tuple[str, float]:
    """The SVG: one rectangle per declared cell, its own value printed inside it."""
    height = TOP + len(rows) * ROW_H + 4
    desc = i18n.fill(t["svg_desc"], rows=len(rows), cols=len(col_names))
    parts: list[str] = [
        f'<svg viewBox="0 0 {W} {height:.0f}" role="img" aria-labelledby="hm-t hm-d" '
        f'preserveAspectRatio="xMinYMin meet">',
        f'<title id="hm-t">{html.escape(t["svg_title"])}</title>',
        f'<desc id="hm-d">{html.escape(desc)}</desc>',
        # The hatch takes its two colours from CSS, so the same pattern answers the media
        # query. A presentation attribute cannot hold var(), so the shapes carry classes.
        '<defs><pattern id="hm-none" width="8" height="8" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)"><rect class="hatch-bg" width="8" height="8"/>'
        '<line class="hatch-line" x1="0" y1="0" x2="0" y2="8" stroke-width="3"/></pattern>'
        '</defs>',
    ]
    for j, name in enumerate(col_names):
        x = LEFT + box["label"] + j * box["cell"] + box["cell"] / 2
        parts.append(f'<text class="hm-chead" x="{x:.1f}" y="{TOP - 12}" '
                     f'text-anchor="middle">{html.escape(name)}</text>')
    for i, row in enumerate(rows):
        y = TOP + i * ROW_H
        parts.append(f'<text class="hm-rname" x="{LEFT}" y="{y + ROW_H / 2 + 5:.1f}">'
                     f'{html.escape(row["name"])}</text>')
        for j, name in enumerate(col_names):
            x = LEFT + box["label"] + j * box["cell"]
            value = row["values"].get(name)
            if value is None:
                css, fill, text, label = " hm-none", ' fill="url(#hm-none)"', t["dash"], \
                    i18n.fill(t["cell_missing"], row=row["name"], col=name)
            else:
                band = bins[bin_index(value, bins)]
                css, fill = f" hm-b{band['band']}", ""
                text = fmt(value, lang, decimals)
                label = i18n.fill(t["cell_title"], row=row["name"], col=name, value=text)
            parts.append(f'<g class="hm-cell{css}"><title>{html.escape(label)}</title>'
                         f'<rect class="hm-box" x="{x:.1f}" y="{y + 1}" '
                         f'width="{box["cell"] - 2:.1f}" height="{ROW_H - 2}"{fill}/>'
                         f'<text class="hm-val" x="{x + box["cell"] / 2:.1f}" '
                         f'y="{y + ROW_H / 2 + 5:.1f}" text-anchor="middle">'
                         f'{html.escape(text)}</text></g>')
    parts.append("</svg>")
    return "\n".join(parts), height


def ramp_css(bins: list[dict]) -> str:
    """The ramp as classes, so one build serves both themes.

    A band's fill and its ink are decided together: the ink is whichever of black and white
    measures better against that fill, and in the dark ramp that is the opposite choice at the
    same band. Writing the pair into CSS is what lets the same page answer the media query.
    """
    def rule(band: dict, fill: str, ink: str, indent: str) -> str:
        n = band["band"]
        return (f"{indent}.hm-b{n}{{fill:{fill}}}\n"
                f"{indent}.hm-b{n} .hm-val{{fill:{ink}}}\n"
                f"{indent}.sw.hm-b{n}{{background:{fill}}}")

    light = "\n".join(rule(b, hexa(b["fill"]), b["ink"], "  ") for b in bins)
    dark = "\n".join(rule(b, hexa(b["dark"]), b["dark_ink"], "    ") for b in bins)
    return f"{light}\n  @media (prefers-color-scheme: dark){{\n{dark}\n  }}\n"


def legend_html(bins: list[dict], lang: str, decimals: int, t: dict,
                clamped: int) -> str:
    """Every shade with the numbers it stands for, and the top band's "at least"."""
    items = []
    for i, band in enumerate(bins):
        if len(bins) == 1:
            text = fmt(band["low"], lang, decimals)
        elif i == len(bins) - 1:
            text = "\u2265\u00a0" + fmt(band["low"], lang, decimals)
        else:
            text = (fmt(band["low"], lang, decimals) + "\u2013"
                    + fmt(band["high"], lang, decimals))
        items.append(f'<li><span class="sw hm-b{band["band"]}" aria-hidden="true"></span>'
                     f'<span class="rg">{html.escape(text)}</span></li>')
    items.append(f'<li><span class="sw sw-none" aria-hidden="true"></span>'
                 f'<span class="rg">{html.escape(t["legend_missing"])}</span></li>')
    note = ""
    if clamped:
        note = (f'<p class="legend-note">{html.escape(i18n.fill(t["legend_clamped"], n=clamped))}'
                f'</p>')
    return (f'<h2 id="lg-h">{html.escape(t["legend_head"])}</h2>\n'
            f'<ul class="legend" aria-labelledby="lg-h">\n  ' + "\n  ".join(items) + "\n</ul>\n"
            + note)


def extreme_of(cells: dict, lang: str, decimals: int, t: dict) -> str:
    """The highest cell named in words, from the values and never from a judgement."""
    highest = max(cells.values())
    winners = [(r, c) for (r, c), v in cells.items() if v == highest]
    total = sum(cells.values())
    share = (highest / total) if total else 0.0
    if len(winners) > 1:
        names = ", ".join(f"{r} / {c}" for r, c in winners[:3])
        return i18n.fill(t["extreme_tie"], n=len(winners), value=fmt(highest, lang, decimals),
                         names=names)
    name_row, name_col = winners[0]
    return i18n.fill(t["extreme_line"], row=name_row, col=name_col,
                     value=fmt(highest, lang, decimals),
                     share=fmt(share * 100, lang, 1) + "\u00a0%")


# -------------------------------------------------------------------------------- table
def table_html(rows: list[dict], col_names: list[str], lang: str, decimals: int,
               t: dict, grand: float, agg: str) -> tuple[str, str]:
    """The same figures as a table, with the row and column totals a reader can check.

    The total column carries the aggregation's own name. A column of cell averages labelled
    "Sum" is the kind of quiet arithmetic error a reader cannot see, so the heading and the
    number move together or not at all.
    """
    label = t[TOTAL_KEYS[agg]]
    body = []
    for row in rows:
        cells = []
        for name in col_names:
            value = row["values"].get(name)
            cells.append(f'<td class="num">'
                         f'{html.escape(t["dash"] if value is None else fmt(value, lang, decimals))}'
                         f'</td>')
        body.append(f'      <tr><th scope="row">{html.escape(row["name"])}</th>'
                    + "".join(cells)
                    + f'<td class="num tot">{html.escape(fmt(row["total"], lang, decimals))}'
                      f'</td></tr>')
    col_totals = []
    for name in col_names:
        total = sum(row["values"].get(name) or 0.0 for row in rows)
        col_totals.append(f'<td class="num">{html.escape(fmt(total, lang, decimals))}</td>')
    foot = ("      <tr><th scope=\"row\">" + html.escape(label) + "</th>"
            + "".join(col_totals)
            + f'<td class="num">{html.escape(fmt(grand, lang, decimals))}</td></tr>')
    return "\n".join(body), foot


# --------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True)
    ap.add_argument("--row", required=True, help="the column that names a row")
    ap.add_argument("--col", required=True, help="the column that names a column")
    ap.add_argument("--measure", default=None, help="the numeric column to shade by")
    ap.add_argument("--agg", choices=("sum", "mean", "count"), default="sum",
                    help="how several rows in one cell combine (default sum)")
    ap.add_argument("--row-order", default="", metavar="A,B,C",
                    help="the rows in order. Default: by row total, largest first")
    ap.add_argument("--col-order", default="", metavar="X,Y,Z",
                    help="the columns in order. Default: as the file sorts them")
    ap.add_argument("--clamp", type=float, default=None, metavar="TOP",
                    help="the top of the scale. Above it the shade means 'at least'")
    ap.add_argument("--decimals", type=int, default=0, choices=range(0, 4),
                    help="decimals on every figure (default 0)")
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

    if args.agg != "count" and not args.measure:
        die("--measure is required: a heatmap shades a quantity. Pass the numeric column, or "
            "--agg count to shade how many rows fall in each cell.")
    cells, combined, skipped = load(args.data, args.row, args.col, args.measure, args.agg)
    bad = negative_name(cells)
    if bad:
        die(f"the cell {bad} holds a negative value. A shade has one direction, so a value "
            f"below zero has no place on this scale, and drawing it as a pale cell would say "
            f"the opposite of what it is. This page draws gains; split losses into their own "
            f"page (a diverging scale is a different drawing), or drop the rows.")

    row_names = sorted({r for r, _ in cells})
    col_names = sorted({c for _, c in cells})
    if args.row_order:
        wanted = [name.strip() for name in args.row_order.split(",") if name.strip()]
        order = order_of(wanted, row_names, "--row-order", args.row)
        row_names = order
    if args.col_order:
        wanted = [name.strip() for name in args.col_order.split(",") if name.strip()]
        col_names = order_of(wanted, col_names, "--col-order", args.col)
    if len(col_names) > MAX_COLS:
        die(f"the data has {len(col_names)} distinct {args.col!r} values, and this page draws "
            f"at most {MAX_COLS} columns before the headers run together. Group them, filter "
            f"the extract, or build one page per group.")
    if len(row_names) > MAX_ROWS:
        die(f"the data has {len(row_names)} distinct {args.row!r} values, and this page draws "
            f"at most {MAX_ROWS} rows. A heatmap that long is a table: filter the extract, or "
            f"group the small rows into one.")

    rows = []
    for name in row_names:
        values = {c: cells[(name, c)] for c in col_names if (name, c) in cells}
        rows.append({"name": name, "values": values, "total": sum(values.values())})
    if not args.row_order:
        rows.sort(key=lambda r: (-r["total"], r["name"]))
    grand = sum(r["total"] for r in rows)
    missing = len(rows) * len(col_names) - sum(len(r["values"]) for r in rows)

    bins = scale_of(cells, args.clamp, args.decimals)
    clamped = 0 if args.clamp is None else sum(1 for v in cells.values() if v > args.clamp)
    figures = [fmt(v, lang, args.decimals) for v in cells.values()]
    box = layout_of([r["name"] for r in rows], col_names, figures)
    svg, _height = draw(rows, col_names, bins, box, lang, args.decimals, t)
    body, foot = table_html(rows, col_names, lang, args.decimals, t, grand,
                            args.agg)

    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)
    source = i18n.fill(t["source_line"], name=args.source or args.data.name, cells=len(cells))
    if combined:
        source += " \u00b7 " + i18n.fill(t["duplicates"], n=combined)
    if skipped:
        source += " \u00b7 " + i18n.fill(t["skipped"], n=skipped)
    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=built,
                                           source=source, lang=lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    # One finding is a callout. Everything else is how the page was made, and a stack of five
    # identical boxes is a stack nobody reads past the second: the shape has to differ.
    lead = extreme_of(cells, lang, args.decimals, t)
    notes = []
    if args.agg == "mean":
        notes.append(t["note_mean"])
    notes.append(t["note_order_rows"] if args.row_order else t["note_sorted_rows"])
    if not args.col_order:
        notes.append(t["note_sorted_cols"])
    if missing:
        notes.append(i18n.fill(t["note_missing"], missing=missing, all=len(rows) * len(col_names)))
    if len(bins) == 1:
        notes.append(t["note_flat"])
    if args.clamp is None:
        notes.append(i18n.fill(t["note_scale"], low=fmt(bins[0]["low"], lang, args.decimals),
                               high=fmt(bins[-1]["high"], lang, args.decimals)))
    else:
        notes.append(i18n.fill(t["note_scale_clamped"],
                               low=fmt(bins[0]["low"], lang, args.decimals),
                               high=fmt(args.clamp, lang, args.decimals)))
    note_block = "\n".join(f'    <li>{html.escape(note)}</li>' for note in notes)

    # The colours come from tools/tokens/: one seam with every other artefact. auto_dark: a
    # reader whose system is dark gets a dark heatmap with no script. The ramp travels with
    # the page, because its bands are a design decision the seam does not carry.
    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css))
            .replace("{{RAMP_CSS}}", ramp_css(bins)))
    for token, value in {
        "{{TITLE}}": html.escape(args.title),
        "{{SUBTITLE}}": html.escape(i18n.fill(
            t["sub_line"], rows=len(rows), cols=len(col_names),
            measure=args.measure or args.row, agg=t[AGG_KEYS[args.agg]])),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(source),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{ROWS_INLINED}}": str(len(cells)),
        "{{SVG}}": svg,
        "{{LEGEND}}": legend_html(bins, lang, args.decimals, t, clamped),
        "{{CAPTION}}": html.escape(i18n.fill(t["caption"], measure=args.measure or args.row)),
        "{{NOTE_LEAD}}": html.escape(lead),
        "{{NOTE_LIST}}": note_block,
        "{{TABLE_HEAD_COLS}}": "\n".join(
            f'      <th scope="col" class="num">{html.escape(name)}</th>' for name in col_names),
        "{{COL_TOTAL_LABEL}}": html.escape(t[TOTAL_KEYS[args.agg]]),
        "{{TABLE_ROWS}}": body,
        "{{TABLE_FOOT}}": foot,
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

    print(f"cells         : {len(cells)} of {len(rows) * len(col_names)} "
          f"({missing} with no data)")
    print(f"rows x cols   : {len(rows)} x {len(col_names)}")
    print(f"scale         : {fmt(bins[0]['low'], lang, args.decimals)} to "
          f"{fmt(bins[-1]['high'], lang, args.decimals)}"
          + (f" (clamped, {clamped} cell(s) above)" if clamped else ""))
    print(f"highest       : {extreme_of(cells, lang, args.decimals, t)}")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


def order_of(wanted: list[str], present: list[str], flag: str, column: str) -> list[str]:
    """Apply a declared order, refusing when it drops or invents a value.

    An order that silently ignores a value removes its row from the page, which is the kind
    of absence a reader cannot see.
    """
    unknown = [name for name in wanted if name not in present]
    if unknown:
        die(f"{flag} names {unknown[0]!r}, which is not a value in {column!r}. Available: "
            f"{', '.join(present[:12])}")
    absent = [name for name in present if name not in wanted]
    if absent:
        die(f"{flag} does not name {len(absent)} value(s) the data holds, starting with "
            f"{absent[0]!r}. An order that leaves a value out removes its row from the page: "
            f"name every value, or drop the flag and let the page sort them.")
    return wanted


if __name__ == "__main__":
    sys.exit(main())
