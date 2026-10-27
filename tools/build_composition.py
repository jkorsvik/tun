#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a standalone composition page: what the total is made of, and how the mix moves.

Every other artefact here answers a question about a level, a change in it, or the shape of
one measure. None answers the one a management report actually asks most often: what is this
total made of, and how did the mix change? That question has a trap built into it, and it is
the reason this page exists: a category can take a bigger share of the total while its own
figure falls, if the total fell faster. A picture of shares alone cannot show that, so this
page prints the level, the share and the carry every category makes towards both.

    python3 tools/build_composition.py \\
      --data examples/41-composition/bemanning.csv \\
      --measure Timer --cat Oppgave --period-col Kvartal \\
      --title "Hva timene gikk til: 2026" \\
      --source "Syntetisk eksempeldata (bemanning.csv)" \\
      --requested-by "Bemanningskontoret" \\
      --out examples/41-composition/sammensetning.html

What is built in, rather than left to whoever assembles the file:

  * **the shares are rounded so they add up.** Printed shares use the largest-remainder
    rule, so a column adds to exactly 100,0. A table of shares that sums to 99,9 teaches the
    reader to distrust every other number on the page.
  * **the level is never hidden by the share.** Every period's total is printed above its
    column, and the table carries each category's absolute figure beside its share.
  * **a divergence between share and level is named in words.** One sentence per category
    that gained share while losing volume, or the reverse, generated from the numbers and
    never from a judgement about them.
  * **a category with a negative figure is refused.** A share of a total that holds negatives
    cannot be stacked, and a page that stacks it anyway produces bands that overflow their
    own column.
  * **the largest categories are drawn, and the rest are one band.** Its height is the exact
    sum of what it replaces, named with how many categories it holds, and every category is
    still in the table underneath: the picture is a summary, the table is the account.
  * **the bands are one ramp, not a verdict.** Four slots from dark blue to a tint of Sea
    Green, so the stack reads as an order rather than as good news and bad news. Fire Red is
    left out on purpose: red on an ordinary category is a judgement the page has no basis for.
  * **there is no script.** A filter would re-lay the drawing and then the picture would be
    a second thing to get wrong. What a filter would give the reader is below it: every
    period, every category, both figures.

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

TEMPLATE = ROOT / "templates" / "composition.html"
STRINGS = "composition"
MAX_BANDS = 4              # drawn categories: four approved slots, then the rest band
MAX_PERIODS = 12           # above this a column is thinner than its own label
MAX_BYTES = 40 * 1024 * 1024
SHARE_DP = 1               # one decimal: the resolution a reader can act on

# The canvas. Units, not pixels: the SVG scales, so a theme's font size cannot move a band.
W = 1000
LEFT = 64
RIGHT = 16
TOP = 30                   # the total above the tallest column
PLOT_H = 340
NAME_TOP = 16              # the rule under the plot, then the period labels
NAME_LINE = 18
AXIS_H = 22                # the note under the period labels
BAR_SHARE = 0.62


# ------------------------------------------------------------------------------ numbers
def decimals_of(values: list[float]) -> int:
    """How many decimals a level prints: none for whole numbers, two otherwise."""
    return 0 if all(float(v).is_integer() for v in values) else 2


def fmt(value: float, lang: str, dec: int) -> str:
    """A number as the reader's locale writes it. The separator is decided at build time."""
    text = f"{abs(value):,.{dec}f}"
    if lang == "nb":
        text = text.replace(",", "\u00a0").replace(".", ",")
    else:
        text = text.replace(",", "\u2009")
    return ("\u2212" if value < 0 else "") + text


def share_text(share: float, lang: str) -> str:
    """A share in per cent, with one decimal, and a comma where the locale wants one."""
    text = f"{share:.{SHARE_DP}f}"
    return (text.replace(".", ",") if lang == "nb" else text) + "\u00a0%"


def largest_remainder(values: list[float], total: float, places: int = SHARE_DP) -> list[int]:
    """Shares in units of 10^-places that add up to exactly the total, by largest remainder.

    Rounding each share on its own is what produces a column that adds to 99,9. Hamilton's
    method hands out the last units to the largest remainders instead, so the printed column
    always adds up, and no share is ever more than one unit away from its own exact value.
    """
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


# --------------------------------------------------------------------------------- load
def load(path: pathlib.Path, measure: str, cat: str, period: str,
         only: list[str]) -> tuple[dict[str, dict[str, float]], list[str], int]:
    """Sum the measure per (category, period). Returns the grid, the periods, rows dropped.

    Summed rather than read off one row, because the input is an extract. A negative figure
    is refused: the page's whole construction is a share of a positive whole, and a share of
    a total that holds a negative has no meaning a reader can act on.
    """
    if not path.is_file():
        die(f"{path} does not exist")
    rows = tun_core.read_rows(path)
    if not rows:
        die(f"{path.name} has no rows")
    header = tun_core.columns(rows)
    for flag, name in (("--measure", measure), ("--cat", cat), ("--period-col", period)):
        if name not in header:
            die(f"{flag} {name!r} is not a column in {path.name}. "
                f"Available: {', '.join(header)}")
    grid: dict[str, dict[str, float]] = {}
    periods: list[str] = []
    bad: list[str] = []
    for i, row in enumerate(rows, 2):
        when = str(row.get(period) or "").strip()
        name = str(row.get(cat) or "").strip()
        raw = row.get(measure)
        number = tun_core.to_number(raw)
        if number is None:
            if raw is None or str(raw).strip() == "":
                continue                     # an empty cell is not a zero
            bad.append(f"{path.name}:{i}: {measure} is {str(raw).strip()!r}, "
                       f"which is not a number")
            continue
        if not name:
            bad.append(f"{path.name}:{i}: {cat} is empty, so the figure belongs to nothing")
            continue
        if not when:
            bad.append(f"{path.name}:{i}: {period} is empty, so the figure has no period")
            continue
        if number < 0:
            bad.append(f"{path.name}:{i}: {measure} is {number}, and a negative share of a "
                       f"total cannot be stacked. Drop the row, or build a waterfall instead")
            continue
        if when not in periods:
            periods.append(when)
        grid.setdefault(name, {}).setdefault(when, 0.0)
        grid[name][when] += float(number)
    if bad:
        die(bad[0] + (f" (and {len(bad) - 1} more)" if len(bad) > 1 else ""))
    if only:
        missing = [p for p in only if p not in periods]
        if missing:
            die(f"--period {missing[0]!r} is not a value in {period!r}. "
                f"The file holds: {', '.join(periods)}")
        periods = [p for p in periods if p in only]
    if not periods:
        die(f"no row in {path.name} has a figure")
    if len(periods) > MAX_PERIODS:
        die(f"{len(periods)} periods is more than the {MAX_PERIODS} columns this page can "
            f"draw without a label having room. Pass --period to choose, or aggregate the "
            f"periods before building.")
    for name, per in grid.items():
        for when in periods:
            per.setdefault(when, 0.0)
    return grid, periods, len(rows)


def totals_of(grid: dict[str, dict[str, float]], periods: list[str]) -> dict[str, float]:
    return {when: sum(per[when] for per in grid.values()) for when in periods}


def share_grid(grid: dict[str, dict[str, float]], periods: list[str],
               totals: dict[str, float]) -> dict[str, dict[str, int]]:
    """Each period's shares as whole tenths of a per cent, adding up to 1000."""
    out: dict[str, dict[str, int]] = {}
    for when in periods:
        names = list(grid)
        units = largest_remainder([grid[n][when] for n in names], totals[when])
        out[when] = {n: u for n, u in zip(names, units)}
    return out


def order_of(grid: dict[str, dict[str, float]], periods: list[str]) -> list[str]:
    """Categories by their size across the whole page, largest first, ties by name.

    Ordered by the total each category carries over every period, not by one period: a
    category that appears late must not be pushed to the bottom of the drawing, and a stable
    order across columns is what makes two periods comparable at a glance.
    """
    sums = {name: sum(per[when] for when in periods) for name, per in grid.items()}
    return sorted(sums, key=lambda n: (-sums[n], n))


# --------------------------------------------------------------------------------- draw
def draw(bands: list[dict], periods: list[str], totals: dict[str, float], lang: str,
         dec: int, t: dict) -> tuple[str, int]:
    """The SVG: one column per period, bands stacked in a fixed order, shares on the axis."""
    plot = W - LEFT - RIGHT
    height = TOP + PLOT_H + NAME_TOP + NAME_LINE + AXIS_H
    col = plot / len(periods)
    bar = col * BAR_SHARE
    parts: list[str] = [
        f'<svg viewBox="0 0 {W} {height}" role="img" aria-labelledby="cs-t cs-d" '
        f'preserveAspectRatio="xMinYMin meet">',
        f'<title id="cs-t">{html.escape(t["svg_title"])}</title>',
        f'<desc id="cs-d">{html.escape(i18n.fill(t["svg_desc"], periods=len(periods),
                                                  bands=len(bands)))}</desc>',
    ]
    for pct in (0, 25, 50, 75, 100):
        y = TOP + PLOT_H - pct / 100 * PLOT_H
        parts.append(f'<line class="cs-grid" x1="{LEFT}" y1="{y:.1f}" x2="{W - RIGHT}" '
                     f'y2="{y:.1f}"/>')
        parts.append(f'<text class="cs-tick" x="{LEFT - 8}" y="{y + 5:.1f}" '
                     f'text-anchor="end">{pct}\u00a0%</text>')

    for i, when in enumerate(periods):
        x = LEFT + i * col + (col - bar) / 2
        y = TOP + PLOT_H
        for band in bands:
            units = band["shares"][when]
            if not units:
                continue
            h = units / 1000 * PLOT_H
            y -= h
            parts.append(f'<rect class="cs-band cs-{band["slot"]}" x="{x:.1f}" y="{y:.1f}" '
                         f'width="{bar:.1f}" height="{h:.1f}">'
                         f'<title>{html.escape(i18n.fill(t["band_title"], name=band["name"], period=when, share=share_text(units / 10, lang), value=fmt(band["value"][when], lang, dec)))}</title></rect>')
            # A band's own share is printed inside it when there is room for the text: a
            # number in a legend tells a reader nothing about which band it belongs to.
            if h >= 26:
                parts.append(f'<text class="cs-share cs-ink-{band["slot"]}" '
                             f'x="{x + bar / 2:.1f}" y="{y + h / 2 + 5:.1f}" '
                             f'text-anchor="middle">'
                             f'{html.escape(share_text(units / 10, lang))}</text>')
        parts.append(f'<text class="cs-total" x="{x + bar / 2:.1f}" y="{TOP - 10:.1f}" '
                     f'text-anchor="middle">{html.escape(fmt(totals[when], lang, dec))}</text>')
        parts.append(f'<text class="cs-period" x="{x + bar / 2:.1f}" '
                     f'y="{TOP + PLOT_H + NAME_TOP + NAME_LINE - 4:.1f}" '
                     f'text-anchor="middle">{html.escape(when)}</text>')
    base = TOP + PLOT_H
    parts.append(f'<line class="cs-base" x1="{LEFT}" y1="{base}" x2="{W - RIGHT}" '
                 f'y2="{base}"/>')
    parts.append(f'<text class="cs-axis" x="{LEFT}" '
                 f'y="{base + NAME_TOP + NAME_LINE + 14}">{html.escape(t["axis_note"])}'
                 f'</text>')
    parts.append("</svg>")
    return "\n".join(parts), height


def move_lines(bands: list[dict], periods: list[str], lang: str, t: dict) -> str:
    """One sentence per category whose share and level move in opposite directions.

    This is the sentence the artefact exists for: a share is a ratio, and a ratio can rise
    while the figure falls. Generated from the two ends of the page only, and only when both
    ends exist, so a single-period page says nothing rather than something wrong.
    """
    if len(periods) < 2:
        return f'    <li>{html.escape(t["move_single"])}</li>'
    first, last = periods[0], periods[-1]
    out = []
    for band in bands:
        before = band["shares"][first] / 10
        after = band["shares"][last] / 10
        value_before, value_after = band["value"][first], band["value"][last]
        if abs(after - before) < 0.5:
            continue
        share_up = after > before
        value_up = value_after > value_before
        if share_up == value_up:
            continue
        key = "move_share_up" if share_up else "move_share_down"
        out.append("    <li>" + html.escape(i18n.fill(
            t[key], name=band["name"],
            sharebefore=share_text(before, lang), shareafter=share_text(after, lang),
            valuebefore=fmt(value_before, lang, 0), valueafter=fmt(value_after, lang, 0)))
            + "</li>")
    if not out:
        out.append(f'    <li>{html.escape(t["move_none"])}</li>')
    return "\n".join(out)


# -------------------------------------------------------------------------------- table
def table_rows(bands: list[dict], periods: list[str], lang: str, dec: int,
               drawn: int, t: dict) -> str:
    """Every category, both figures per period: the share first, the level beside it.

    A category the drawing could not carry gets a neutral swatch and says which band it sits
    in. Giving it a band colour would promise a band that is not there, and two categories
    with the same colour in one table is a defect a reader cannot resolve.
    """
    out = []
    for i, band in enumerate(bands):
        swatch = f'cs-{band["slot"]}' if i < drawn else "cs-rest"
        tag = ("" if i < drawn or not drawn
               else f' <span class="tag">{html.escape(t["in_rest"])}</span>')
        cells = []
        for when in periods:
            cells.append(f'<td class="num">{share_text(band["shares"][when] / 10, lang)}'
                         f'<span class="lvl">{fmt(band["value"][when], lang, dec)}</span></td>')
        out.append(f'      <tr><th scope="row">'
                   f'<span class="dot {swatch}" aria-hidden="true"></span>'
                   f'{html.escape(band["name"])}{tag}</th>' + "".join(cells) + "</tr>")
    return "\n".join(out)


def total_row(periods: list[str], totals: dict[str, float], lang: str, dec: int,
              t: dict) -> str:
    cells = "".join(f'<td class="num">{html.escape(share_text(100.0, lang))}'
                    f'<span class="lvl">{fmt(totals[when], lang, dec)}</span></td>'
                    for when in periods)
    return f'      <tr><th scope="row">{html.escape(t["row_total"])}</th>{cells}</tr>'


# --------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True,
                    help="CSV with one row per record, the period and the category in it")
    ap.add_argument("--measure", required=True, help="the numeric column that is shared out")
    ap.add_argument("--cat", required=True, help="the column whose members are the bands")
    ap.add_argument("--period-col", required=True,
                    help="the column that says which period a row belongs to")
    ap.add_argument("--period", action="append", default=[], metavar="VALUE",
                    help="keep only this period's value; repeat for more, in the order given")
    ap.add_argument("--top", type=int, default=MAX_BANDS, metavar="N",
                    help=f"how many categories the drawing carries, largest first; the rest "
                         f"are one band and the table lists them (default {MAX_BANDS}, at most "
                         f"{MAX_BANDS}: the approved palette has that many slots, and a column "
                         f"with more bands than that cannot be read)")
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

    if args.top < 1:
        die("--top must be at least 1")
    if args.top > MAX_BANDS:
        die(f"--top {args.top} is more than the {MAX_BANDS} slots the approved palette has. "
            f"A stacked column with more bands than that cannot be read: the reader cannot "
            f"tell two similar greens apart, and the table carries every category anyway.")

    grid, periods, rows_read = load(args.data, args.measure, args.cat, args.period_col,
                                    args.period)
    totals = totals_of(grid, periods)
    zeroed = [when for when in periods if totals[when] <= 0]
    if zeroed:
        die(f"{zeroed[0]!r} has no figure at all, so every share in it would be a division "
            f"by zero. Drop that period, or say why the column is empty.")
    shares = share_grid(grid, periods, totals)

    # The invariant, checked before anything is drawn: a column of shares adds to exactly
    # 100,0. The rounding rule exists for this, and it is checked rather than trusted.
    for when in periods:
        if sum(shares[when].values()) != 1000:
            die(f"internal: the shares of {when} add to {sum(shares[when].values()) / 10}, "
                f"not 100,0. This is a bug in the builder, not in the data.")

    order = order_of(grid, periods)
    drawn, rest = order[:args.top], order[args.top:]
    bands = [{"name": n, "value": grid[n], "shares": {w: shares[w][n] for w in periods},
              "slot": 0} for n in drawn]
    if rest:
        # The rest are one band whose height is their exact sum, so the column still adds to
        # 100 per cent. Named with how many categories it holds, never "other" alone.
        per = {w: sum(grid[n][w] for n in rest) for w in periods}
        bands.append({"name": i18n.fill(t["rest_name"], n=len(rest)), "value": per,
                      "shares": {}, "slot": 0})
        for when in periods:
            bands[-1]["shares"][when] = 1000 - sum(b["shares"][when] for b in bands[:-1])
    for i, band in enumerate(bands):
        band["slot"] = i + 1 if i < len(drawn) else "rest"
    for when in periods:
        if sum(b["shares"][when] for b in bands) != 1000:
            die(f"internal: the drawn bands of {when} do not add to 100,0. Builder bug.")

    dec = decimals_of([v for per in grid.values() for v in per.values()])
    svg, _height = draw(bands, periods, totals, lang, dec, t)

    # The table carries every category, drawn or not, with its own two figures per period.
    table_bands = [b for b in bands if not (rest and b is bands[-1])]
    table_bands += [{"name": n, "value": grid[n],
                     "shares": {w: shares[w][n] for w in periods}, "slot": "rest"}
                    for n in rest]
    for i, band in enumerate(table_bands):
        band["slot"] = i + 1 if i < len(drawn) else "rest"

    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)
    source = i18n.fill(t["source_line"], name=args.source or args.data.name, rows=rows_read)
    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=built,
                                           source=source, lang=lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    legend = "".join(
        f'<li><span class="sw cs-{band["slot"]}"></span>{html.escape(band["name"])} '
        f'<span class="lg-share">{html.escape(share_text(band["shares"][periods[-1]] / 10, lang))}</span></li>'
        for band in bands)

    # The colours come from tools/tokens/: one seam with every other artefact. auto_dark: a
    # reader whose system is dark gets a dark composition with no script.
    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css)))
    for token, value in {
        "{{TITLE}}": html.escape(args.title),
        "{{SUBTITLE}}": html.escape(i18n.fill(
            t["sub_line"], measure=args.measure, cat=args.cat, periods=len(periods),
            bands=len(bands), first=periods[0], last=periods[-1])),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(source),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{ROWS_INLINED}}": str(rows_read),
        "{{SVG}}": svg,
        "{{LEGEND}}": legend,
        "{{CAPTION}}": html.escape(i18n.fill(t["caption"], measure=args.measure,
                                             cat=args.cat)),
        "{{MOVES}}": move_lines(bands, periods, lang, t),
        "{{REST_NOTE}}": html.escape(i18n.fill(t["rest_note"], n=len(rest),
                                               drawn=len(drawn))) if rest else "",
        "{{TABLE_HEAD}}": "".join(
            f'<th scope="col" class="num">{html.escape(w)}</th>' for w in periods),
        "{{TABLE_ROWS}}": table_rows(table_bands, periods, lang, dec, len(drawn), t),
        "{{TOTAL_ROW}}": total_row(periods, totals, lang, dec, t),
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

    print(f"periods       : {len(periods)} ({periods[0]} \u2192 {periods[-1]})")
    print(f"categories    : {len(order)} ({len(drawn)} drawn"
          + (f", {len(rest)} in one band" if rest else "") + ")")
    for when in periods:
        print(f"  {when:<12}: {fmt(totals[when], lang, dec):>14}  "
              f"({len([n for n in order if grid[n][when]])} categories with a figure)")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
