#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a standalone waterfall: the steps that add up to the change.

Most reporting stops at "the number went from 12,4 to 14,5 million". The next question is
always the same: which of the moving parts account for it, and do they add up? That answer
lives in a spreadsheet nobody keeps, where the arithmetic is invisible and the total is
whatever the last person typed. This makes it an artefact: one self-contained file where
every step is drawn, every step is written out with its own figures, and the column adds up
on the page.

    python3 tools/build_waterfall.py \\
      --data examples/40-waterfall/saker.csv \\
      --measure Timer --dim Enhet --period-col Maned \\
      --from September --to Oktober \\
      --title "Bruk av saksbehandlingstid: september til oktober" \\
      --source "Syntetisk eksempeldata (saker.csv)" \\
      --requested-by "Fagavdelingen" \\
      --out examples/40-waterfall/bro.html

What is built in, rather than left to whoever assembles the file:

  * **the bridge closes.** Opening plus every step equals closing, and the page prints the
    three figures so a reader can check the claim by adding one column. The builder also
    checks it before writing: a bridge that does not close is a bug in the builder, and it
    dies rather than shipping a picture whose total is wrong.
  * **nothing is dropped.** The drawing carries the largest steps by size, and the rest are
    one bar whose height is their exact net, named with how many steps it holds. Every
    contributor is still listed in the table underneath, so the picture is a summary and the
    table is the whole account.
  * **the axis is stated, not implied.** A bridge that starts at zero cannot show steps that
    are small against the level, and one that does not start at zero exaggerates them. This
    page starts at the lowest level so the steps are visible, and says on the page where the
    axis starts, what the highest and lowest levels are, and how big each step is against the
    opening figure.
  * **direction is geometry and a sign, not a colour.** An increase goes up, a decrease goes
    down, and every step carries its own signed number. Colour stays neutral unless the
    caller states which direction is good news (`--meaning up|down`), because more revenue
    and more overtime are the same arithmetic and only one of them is good.
  * **a contributor present in one period only is a step, not an absence.** It is named new
    or gone and contributes its whole value, since that is what happened to the total.
  * **a step is summed per contributor, not read off the first row.** The input is a
    transaction extract, and one row per contributor would answer a different question.
  * **there is no script.** A filter would re-lay the drawing, and the drawing is the claim.

Deliberately absent: the mode where the rows are already deltas (a hand-kept bridge table
with a row per step and its own sign). Two input shapes would be two ways to get the
arithmetic wrong; the derived route is the one whose total can be checked against the rows.

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

TEMPLATE = ROOT / "templates" / "waterfall.html"
STRINGS = "waterfall"
FLAT_EPSILON = 0.005      # below half a hundredth, "unchanged" is the honest word
MAX_DRAWN = 6             # steps in the drawing, before the rest become one bar
MAX_COLUMNS = 9           # drawn steps plus the two totals: above this a name has no room
MAX_TABLE = 200           # contributors listed one by one; above this the rest are one row
MAX_BYTES = 40 * 1024 * 1024
HEADROOM = 0.06           # of the level span, so the tallest number has room above it

# The canvas. Units, not pixels: the SVG scales, so a theme's font size cannot move a bar.
W = 1000
LEFT = 118                # a gridline label is right-anchored here and must not be clipped
RIGHT = 12
TOP = 34                  # the number above the tallest column
PLOT_H = 320
NAME_TOP = 18             # the rule under the plot, then the names
NAME_LINE = 15
NAME_LINES = 2
NAME_MIN = 8              # the narrowest a name line may be before the column is too thin
AXIS_H = 22               # the note under the names
BAR_SHARE = 0.58


# ------------------------------------------------------------------------------ numbers
def decimals_of(values: list[float]) -> int:
    """How many decimals the page prints: none for whole numbers, two otherwise."""
    return 0 if all(float(v).is_integer() for v in values) else 2


def fmt(value: float, lang: str, dec: int) -> str:
    """A number as the reader's locale writes it. The separator is decided at build time."""
    text = f"{abs(value):,.{dec}f}"
    if lang == "nb":
        text = text.replace(",", "\u00a0").replace(".", ",")
    else:
        text = text.replace(",", "\u2009")
    return ("\u2212" if value < 0 else "") + text


def signed(value: float, lang: str, dec: int) -> str:
    """A change, with the plus the page needs: a bare figure does not say which way it went."""
    if abs(value) < FLAT_EPSILON:
        return fmt(0.0, lang, dec)
    return ("+" if value > 0 else "\u2212") + fmt(abs(value), lang, dec)


def pct(value: float, base: float) -> str | None:
    """A step as a share of the opening figure, or None when there is nothing to divide by."""
    if not base:
        return None
    return f"{value / base * 100:+.1f} %".replace(".", ",")


# --------------------------------------------------------------------------------- load
def load(path: pathlib.Path, measure: str, dim: str, period_col: str,
         want_from: str, want_to: str) -> tuple[list[dict], str, str, int]:
    """The rows in the two periods chosen, plus which two they are and how many were left.

    A row with no contributor name is refused: it has a figure and no place in a bridge, and
    squeezing it in under a made-up name would put a name on the page nobody can trace.
    """
    if not path.is_file():
        die(f"{path} does not exist")
    rows = tun_core.read_rows(path)
    if not rows:
        die(f"{path.name} has no rows")
    header = tun_core.columns(rows)
    for flag, name in (("--measure", measure), ("--dim", dim), ("--period-col", period_col)):
        if name not in header:
            die(f"{flag} {name!r} is not a column in {path.name}. "
                f"Available: {', '.join(header)}")

    seen: list[str] = []
    parsed: list[dict] = []
    bad: list[str] = []
    for i, row in enumerate(rows, 2):
        period = str(row.get(period_col) or "").strip()
        if period and period not in seen:
            seen.append(period)
        raw = row.get(measure)
        number = tun_core.to_number(raw)
        if number is None:
            if raw is None or str(raw).strip() == "":
                continue                   # an empty cell is not a step of zero
            bad.append(f"{path.name}:{i}: {measure} is {str(raw).strip()!r}, "
                       f"which is not a number")
            continue
        name = str(row.get(dim) or "").strip()
        if not name:
            bad.append(f"{path.name}:{i}: {dim} is empty, so the row has a figure and no "
                       f"contributor to put it under")
            continue
        parsed.append({"period": period, "name": name, "value": float(number)})
    if bad:
        die(bad[0] + (f" (and {len(bad) - 1} more)" if len(bad) > 1 else ""))

    if want_from or want_to:
        for label, wanted in (("--from", want_from), ("--to", want_to)):
            if wanted and wanted not in seen:
                die(f"{label} {wanted!r} is not a value in {period_col!r}. "
                    f"The file holds: {', '.join(seen) or '(nothing)'}")
        if not (want_from and want_to):
            die("pass both --from and --to, or neither and let the file decide "
                "(which needs exactly two periods in it)")
        if want_from == want_to:
            die("--from and --to are the same period, so the bridge would be all zeroes")
        before, after = want_from, want_to
    else:
        if len(seen) != 2:
            die(f"{period_col!r} holds {len(seen)} periods ({', '.join(seen)}). A bridge is "
                f"between two of them: pass --from and --to to say which.")
        before, after = seen[0], seen[1]

    kept = [r for r in parsed if r["period"] in (before, after)]
    dropped = len(parsed) - len(kept)
    if not kept:
        die(f"no row in {path.name} has a figure in {before!r} or {after!r}")
    return kept, before, after, dropped


def bridge(kept: list[dict], before: str, after: str) -> tuple[list[dict], float, float]:
    """One step per contributor, in the file's own figures, plus the opening and closing.

    Summed per contributor because the input is an extract: a contributor that appears eleven
    times in a period has one figure for that period, and that figure is the sum. A
    contributor in one period only gets zero on the other side, which is what makes a new or
    departed contributor a real step in the bridge instead of a hole in the totals.
    """
    sums: dict[tuple[str, str], float] = {}
    for row in kept:
        key = (row["name"], row["period"])
        sums[key] = sums.get(key, 0.0) + row["value"]
    names = sorted({row["name"] for row in kept})
    opening = sum(v for (name, p), v in sums.items() if p == before)
    closing = sum(v for (name, p), v in sums.items() if p == after)

    steps = []
    for name in names:
        frm = sums.get((name, before))
        to = sums.get((name, after))
        if frm is None:
            state, delta = "new", to
        elif to is None:
            state, delta = "gone", -frm
        else:
            delta = to - frm
            state = "flat" if abs(delta) < FLAT_EPSILON else ("up" if delta > 0 else "down")
        steps.append({"name": name, "frm": frm, "to": to, "delta": delta, "state": state})
    steps.sort(key=lambda s: (-abs(s["delta"]), s["name"]))
    return steps, opening, closing


def split(steps: list[dict], drawn: int) -> tuple[list[dict], list[dict]]:
    """The steps the drawing carries, and the rest, which become one bar.

    The rest are summed rather than cut, because a bridge whose bars do not add up to the
    change is the one thing this artefact exists to prevent. A flat step is never drawn on
    its own: it has no height, and a hairline with a name under it reads as a defect.
    """
    moved = [s for s in steps if abs(s["delta"]) >= FLAT_EPSILON]
    top, rest = moved[:drawn], moved[drawn:]
    if len(moved) <= drawn:
        return top, []
    return top, rest


def levels_of(columns: list[dict], opening: float) -> list[dict]:
    """Give every column its own before and after level, and check the chain closes.

    A step's height means nothing on its own: what a reader follows is the level it starts
    from and the level it leaves behind. So the level is computed here, once, and both the
    drawing and the table read it from the same place.
    """
    running = opening
    for column in columns:
        if column["kind"] == "total":
            column["before"] = column["value"]
            column["after"] = column["value"]
            running = column["value"]
        else:
            column["before"] = running
            column["after"] = running + column["delta"]
            running = column["after"]
    return columns


def axis_for(columns: list[dict]) -> tuple[float, float]:
    """The levels the drawing must show, with headroom for the number above each bar."""
    levels = [c["before"] for c in columns] + [c["after"] for c in columns]
    low, high = min(levels), max(levels)
    if high == low:                        # every step is nothing: one level, one band
        pad = abs(high) * 0.1 or 1.0
        return low - pad, high + pad
    pad = (high - low) * HEADROOM
    return low - pad, high + pad


def nice_ticks(low: float, high: float, count: int = 4) -> list[float]:
    """Gridlines at numbers a person would choose: 1, 2 or 5 times a power of ten.

    Chosen from the span, not divided into it: an axis labelled 11,732,000 helps nobody, and
    the reader who cannot read the axis cannot check the picture.
    """
    span = high - low
    if span <= 0:
        return []
    raw = span / max(1, count)
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next((m * magnitude for m in (1, 2, 5, 10) if m * magnitude >= raw), raw)
    start = math.ceil(low / step) * step
    ticks, value = [], start
    while value <= high and len(ticks) < count + 2:
        ticks.append(round(value, 10))
        value += step
    return ticks


# --------------------------------------------------------------------------------- draw
def wrap(name: str, chars: int, lines: int = NAME_LINES) -> list[str]:
    """A name broken at a space so it fits under its column, marked when it cannot.

    The budget comes from the column's own width, and a word that is wider than the whole
    budget is cut with an ellipsis rather than allowed to run into its neighbour: the table
    below carries every name in full, so nothing is lost by shortening it under the drawing.
    """
    budget = max(NAME_MIN, chars)
    if len(name) <= budget:
        return [name]
    words, out, current = name.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= budget or not current:
            current = candidate
        else:
            out.append(current)
            current = word
    out.append(current)
    if len(out) > lines:
        out = out[:lines]
    return [line if len(line) <= budget else line[:budget - 1].rstrip(" -") + "\u2026"
            for line in out]


def draw(columns: list[dict], low: float, high: float, caption: dict, lang: str, dec: int,
         t: dict) -> tuple[str, int]:
    """The SVG: one column per step, floating between the levels it moves the total across."""
    plot = W - LEFT - RIGHT
    total_h = NAME_TOP + NAME_LINE * NAME_LINES + AXIS_H
    height = TOP + PLOT_H + total_h
    col = plot / len(columns)
    bar = col * BAR_SHARE

    def y_of(level: float) -> float:
        return TOP + PLOT_H - (level - low) / (high - low) * PLOT_H

    parts: list[str] = [
        f'<svg viewBox="0 0 {W} {height}" role="img" aria-labelledby="wf-t wf-d" '
        f'preserveAspectRatio="xMinYMin meet">',
        f'<title id="wf-t">{html.escape(caption["title"])}</title>',
        f'<desc id="wf-d">{html.escape(caption["desc"])}</desc>',
    ]
    for tick in nice_ticks(low, high):
        y = y_of(tick)
        parts.append(f'<line class="wf-grid" x1="{LEFT}" y1="{y:.1f}" x2="{W - RIGHT}" '
                     f'y2="{y:.1f}"/>')
        parts.append(f'<text class="wf-tick" x="{LEFT - 8}" y="{y + 5:.1f}" '
                     f'text-anchor="end">{html.escape(fmt(tick, lang, dec))}</text>')

    # The connectors first, so a bar is drawn over its own line and never under it.
    for i in range(len(columns) - 1):
        if columns[i]["kind"] == "step":
            y = y_of(columns[i]["after"])
            x1 = LEFT + i * col + (col - bar) / 2 + bar
            x2 = LEFT + (i + 1) * col + (col - bar) / 2
            parts.append(f'<line class="wf-link" x1="{x1:.1f}" y1="{y:.1f}" '
                         f'x2="{x2:.1f}" y2="{y:.1f}"/>')

    chars = int(col / 7.4)                 # 14 px glyphs average about 7.4 units wide
    for i, c in enumerate(columns):
        x = LEFT + i * col + (col - bar) / 2
        top = y_of(max(c["before"], c["after"]))
        bottom = y_of(min(c["before"], c["after"]))
        if c["kind"] == "total":
            # A total is a level, not a bar: on a truncated axis a bar from the axis bottom
            # would be a two-pixel sliver labelled with a large number, which reads as a
            # defect. A rule at the level, with the figure above it, says what it is.
            y = y_of(c["value"])
            parts.append(f'<line class="wf-level" x1="{x - bar / 2:.1f}" y1="{y:.1f}" '
                         f'x2="{x + bar * 1.5:.1f}" y2="{y:.1f}">'
                         f'<title>{html.escape(c["label"])}</title></line>')
            label_y = y - 10
        else:
            h = max(bottom - top, 2.0)     # a step of nothing still gets a visible mark
            tone = "" if c["tone"] == "step" else f' wf-{c["tone"]}'
            parts.append(f'<rect class="wf-step{tone}" x="{x:.1f}" y="{top:.1f}" '
                         f'width="{bar:.1f}" height="{h:.1f}">'
                         f'<title>{html.escape(c["label"])}</title></rect>')
            label_y = top - 10
        # Every column carries its own number, because height against a truncated axis is a
        # cue and the figure is the fact.
        parts.append(f'<text class="wf-num" x="{x + bar / 2:.1f}" y="{label_y:.1f}" '
                     f'text-anchor="middle">{html.escape(c["printed"])}</text>')
        lines = wrap(c["name"], chars)
        for n, line in enumerate(lines):
            parts.append(f'<text class="wf-name" x="{x + bar / 2:.1f}" '
                         f'y="{TOP + PLOT_H + NAME_TOP + NAME_LINE * (n + 1):.1f}" '
                         f'text-anchor="middle">{html.escape(line)}</text>')

    base = TOP + PLOT_H
    parts.append(f'<line class="wf-base" x1="{LEFT}" y1="{base}" x2="{W - RIGHT}" '
                 f'y2="{base}"/>')
    parts.append(f'<text class="wf-axis" x="{LEFT}" y="{base + NAME_TOP + NAME_LINE * NAME_LINES + 14:.1f}">'
                 f'{html.escape(caption["axis"])}</text>')
    parts.append("</svg>")
    return "\n".join(parts), height


# -------------------------------------------------------------------------------- table
def table_rows(steps: list[dict], drawn_names: set[str], aggregated: list[dict], lang: str,
               dec: int, t: dict) -> str:
    """Every contributor, in the order of the drawing's size, with the figures to add up."""
    out = []
    for s in steps:
        tags = []
        if s["state"] in ("new", "gone"):
            tags.append(f'<span class="tag">{html.escape(t[s["state"]])}</span>')
        if s["name"] not in drawn_names and not aggregated:
            tags.append(f'<span class="tag tag-quiet">{html.escape(t["in_other"])}</span>')
        share = pct(s["delta"], s["base"]) if s.get("base") else None
        out.append(
            f'      <tr data-step="{html.escape(s["name"])}">'
            f'<th scope="row">{html.escape(s["name"])}{"".join(" " + g for g in tags)}</th>'
            f'<td class="num">{fmt(s["frm"], lang, dec) if s["frm"] is not None else html.escape(t["dash"])}</td>'
            f'<td class="num delta">{signed(s["delta"], lang, dec)}</td>'
            f'<td class="num">{share or html.escape(t["dash"])}</td>'
            f'<td class="num">{fmt(s["to"], lang, dec) if s["to"] is not None else html.escape(t["dash"])}</td>'
            f'</tr>')
    if aggregated:
        net = sum(s["delta"] for s in aggregated)
        out.append(
            f'      <tr data-step="{html.escape(t["other_name"])}">'
            f'<th scope="row">{html.escape(i18n.fill(t["other_name"], n=len(aggregated)))}</th>'
            f'<td class="num">{html.escape(t["dash"])}</td>'
            f'<td class="num delta">{signed(net, lang, dec)}</td>'
            f'<td class="num">{html.escape(t["dash"])}</td>'
            f'<td class="num">{html.escape(t["dash"])}</td>'
            f'</tr>')
    return "\n".join(out)


def chain_rows(columns: list[dict], lang: str, dec: int, t: dict) -> str:
    """The drawing's own levels, in order, so the picture can be read as arithmetic."""
    out = []
    for c in columns:
        change = html.escape(t["dash"]) if c["kind"] == "total" else signed(c["delta"], lang, dec)
        out.append(f'      <tr><th scope="row">{html.escape(c["name"])}</th>'
                   f'<td class="num">{fmt(c["before"], lang, dec)}</td>'
                   f'<td class="num delta">{change}</td>'
                   f'<td class="num">{fmt(c["after"], lang, dec)}</td></tr>')
    return "\n".join(out)


# --------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True,
                    help="CSV with one row per transaction, both periods in it")
    ap.add_argument("--measure", required=True, help="the numeric column that moves")
    ap.add_argument("--dim", required=True,
                    help="the column whose members are the steps of the bridge")
    ap.add_argument("--period-col", required=True,
                    help="the column that says which period a row belongs to")
    ap.add_argument("--from", dest="from_", default="",
                    help="the earlier period's value in that column (default: the first of two)")
    ap.add_argument("--to", dest="to_", default="",
                    help="the later period's value in that column (default: the second of two)")
    ap.add_argument("--top", type=int, default=MAX_DRAWN, metavar="N",
                    help=f"how many steps the drawing carries; the rest become one bar, and "
                         f"the table still lists them (default {MAX_DRAWN}, at most "
                         f"{MAX_COLUMNS - 2})")
    ap.add_argument("--title", required=True)
    ap.add_argument("--source", default="", help="where the rows came from")
    ap.add_argument("--requested-by", default="", help="a role, not a person's name")
    ap.add_argument("--meaning", choices=("none", "up", "down"), default="none",
                    help="which direction is good news, so colour may encode a verdict: "
                         "'up' or 'down'. Default none, where the geometry and the sign carry "
                         "direction and colour stays neutral")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--feedback-to", default="", metavar="ADDRESS_OR_ISSUE_URL",
                    help=feedback_link.FLAG_HELP)
    i18n.add_lang_argument(ap)
    args = ap.parse_args(argv)
    t = i18n.load(STRINGS, args.lang)
    lang = args.lang

    if args.top < 1:
        die("--top must be at least 1")
    drawn = min(args.top, MAX_COLUMNS - 2)

    kept, before, after, dropped = load(args.data, args.measure, args.dim, args.period_col,
                                        args.from_, args.to_)
    steps, opening, closing = bridge(kept, before, after)
    for s in steps:                        # each step as a share of the opening figure
        s["base"] = opening
    top, rest = split(steps, drawn)
    change = closing - opening

    # The chain, built once and read by both the drawing and the tables below it.
    columns = [{"kind": "total", "value": opening, "name": t["open_name"],
                "printed": fmt(opening, lang, 0), "label": i18n.fill(
                    t["open_title"], value=fmt(opening, lang, 0))}]
    for s in top:
        columns.append({"kind": "step", "delta": s["delta"], "name": s["name"],
                        "printed": signed(s["delta"], lang, 0),
                        "tone": tone_of(s, args.meaning),
                        "label": i18n.fill(t["step_title"], name=s["name"],
                                           delta=signed(s["delta"], lang, 0))})
    if rest:
        net = sum(s["delta"] for s in rest)
        columns.append({"kind": "step", "delta": net, "name": i18n.fill(
            t["other_name"], n=len(rest)), "printed": signed(net, lang, 0),
            "tone": tone_of({"delta": net}, args.meaning),
            "label": i18n.fill(t["other_title"], n=len(rest), delta=signed(net, lang, 0))})
    # The claim of the page, checked before the closing column is added: the steps the
    # drawing carries must arrive at the closing figure. Taken from `closing` instead, the
    # closing column would always agree with itself and a step left out of the drawing would
    # pass unseen, which is the one bug this artefact exists to make impossible.
    reached = opening + sum(c["delta"] for c in columns[1:])
    if abs(reached - closing) > 1e-6:
        die(f"internal: the drawn steps add up to {reached} but the closing figure is "
            f"{closing}. This is a bug in the builder, not in the data.")
    columns.append({"kind": "total", "value": closing, "name": t["close_name"],
                    "printed": fmt(closing, lang, 0), "label": i18n.fill(
                        t["close_title"], value=fmt(closing, lang, 0))})
    columns = levels_of(columns, opening)

    for column in columns[1:-1]:
        if abs((column["before"] + column["delta"]) - column["after"]) > 1e-6:
            die("internal: a step's own figures do not chain. Builder bug, not data.")

    dec = decimals_of([c["before"] for c in columns] + [c["after"] for c in columns])
    low, high = axis_for(columns)
    caption = {
        "title": args.title,
        "desc": i18n.fill(t["svg_desc"], measure=args.measure, before=before, after=after,
                          opening=fmt(opening, lang, dec), closing=fmt(closing, lang, dec),
                          n=len(steps)),
        "axis": i18n.fill(t["axis_note"], low=fmt(low, lang, dec), high=fmt(high, lang, dec),
                          opening=fmt(opening, lang, dec)),
    }
    svg, _height = draw(columns, low, high, caption, lang, dec, t)

    drawn_names = {c["name"] for c in columns if c["kind"] == "step"}
    aggregated = rest if len(steps) > MAX_TABLE else []

    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)
    source = i18n.fill(t["source_line"], name=args.source or args.data.name, rows=len(kept))
    if dropped:
        source += " \u00b7 " + i18n.fill(t["dropped"], n=dropped)
    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=built,
                                           source=source, lang=lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    meaning_note = t["colour_neutral"] if args.meaning == "none" else i18n.fill(
        t["colour_meaning"], good=after if args.meaning == "up" else before)
    legend = (f'<li><span class="sw sw-total"></span>{html.escape(t["legend_total"])}</li>'
              f'<li><span class="sw sw-step"></span>{html.escape(t["legend_step"])}</li>'
              f'<li><span class="ln"></span>{html.escape(t["legend_link"])}</li>')

    # The colours come from tools/tokens/: one seam with every other artefact. auto_dark: a
    # reader whose system is dark gets a dark waterfall with no script.
    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css)))
    for token, value in {
        "{{TITLE}}": html.escape(args.title),
        "{{SUBTITLE}}": html.escape(i18n.fill(
            t["sub_line"], measure=args.measure, dim=args.dim, before=before, after=after,
            n=len(steps))),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(source),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{ROWS_INLINED}}": str(len(kept)),
        "{{SVG}}": svg,
        "{{LEGEND}}": legend,
        "{{CAPTION}}": html.escape(i18n.fill(t["caption"], measure=args.measure,
                                             dim=args.dim)),
        "{{IDENTITY}}": html.escape(i18n.fill(
            t["identity"], opening=fmt(opening, lang, dec),
            op="\u2212" if change < 0 else "+", amount=fmt(abs(change), lang, dec),
            closing=fmt(closing, lang, dec))),
        "{{MEANING_NOTE}}": html.escape(meaning_note),
        "{{OTHER_NOTE}}": html.escape(i18n.fill(t["other_note"], n=len(rest),
                                                drawn=len(top))) if rest else "",
        "{{CHAIN_ROWS}}": chain_rows(columns, lang, dec, t),
        "{{TABLE_ROWS}}": table_rows(steps, drawn_names, aggregated, lang, dec, t),
        "{{TABLE_NOTE}}": html.escape(t["table_note"] if not aggregated else
                                      i18n.fill(t["table_note_aggregated"],
                                                n=len(aggregated), cap=MAX_TABLE)),
        "{{TOTAL_FROM}}": fmt(opening, lang, dec),
        "{{TOTAL_CHANGE}}": signed(change, lang, dec),
        "{{TOTAL_TO}}": fmt(closing, lang, dec),
        "{{TOTAL_PCT}}": pct(change, opening) or html.escape(t["dash"]),
        "{{STEPS_COUNT}}": str(len(steps)),
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

    print(f"bridge        : {before} \u2192 {after}")
    print(f"opening       : {fmt(opening, lang, dec)}")
    print(f"steps         : {len(steps)} ({len(top)} drawn"
          + (f", {len(rest)} in one bar" if rest else "") + ")")
    print(f"closing       : {fmt(closing, lang, dec)}  (change {signed(change, lang, dec)})")
    if dropped:
        print(f"not in bridge : {dropped} row(s) in other periods")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


def tone_of(step: dict, meaning: str) -> str:
    """Which approved colour a step gets: a verdict only when the caller declared one."""
    if meaning == "none":
        return "step"
    good = (step["delta"] > 0) if meaning == "up" else (step["delta"] < 0)
    return "good" if good else "bad"


if __name__ == "__main__":
    sys.exit(main())
