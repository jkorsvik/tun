#!/usr/bin/env python3
"""Build a standalone rank-change page: who moved up, who moved down, and how far.

"Who is top now" is a sorted list. "Who moved" is a different question, and a table answers it
badly: the reader compares two long columns by eye and gives up somewhere in the middle. A
two-column chart answers it, and carries four traps that all produce a page that looks right:

  * **rank is not value.** A key can climb four places on a rounding difference, and another
    can fall one place while growing. The number is printed at both ends or the picture lies.
  * **a newcomer is not a mover.** Drawing a line from the middle of an empty column to a row
    invents an ascent that nobody made. An entity that appears in one period only gets a stub
    and a word, never a diagonal.
  * **a tie is a shared rank.** Two equal values are ranks 1 and 1, and the next one is 3. Drawn
    as 1 and 2, the page invents a difference that the data does not hold.
  * **rank is derived from the values, never from the row order.** A file sorted the other way
    must produce the same page.

    python3 tools/build_rank_change.py \\
      --data examples/46-rank-change/produkter.csv \\
      --entity Produkt --period Kvartal --measure Omsetning \\
      --from 2026-K1 --to 2026-K2 \\
      --title "Hvem klatret, hvem falt" \\
      --source "Syntetisk eksempeldata (produkter.csv)" \\
      --requested-by "Salg" \\
      --out examples/46-rank-change/rang.html

What is built in, rather than left to whoever assembles the file:

  * **both ranks are derived, and printed.** Left column ordered by the `--from` value, right
    column by the `--to` value, and the rank number stands beside every name on both sides.
  * **the value is printed at both ends**, because rank alone cannot tell a move on a rounding
    difference from a collapse.
  * **only an entity present in both periods is connected.** A newcomer and a leaver are drawn
    as a stub with the word for it, counted in the notes, and left out of the movement sentence.
  * **ties share a rank and the page says so** when it happens: 1, 1, 3 rather than 1, 2, 3.
  * **the movement sentence is computed**, naming the largest climb and the largest fall by rank,
    and saying how many held their place. If nothing moved, it says that.
  * **there is no script.** A filter would re-lay the columns, and the columns are the claim.

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

TEMPLATE = ROOT / "templates" / "rank-change.html"
STRINGS = "rank-change"
MAX_BYTES = 40 * 1024 * 1024
MAX_ROWS = 18              # above this the columns are a list again, and the eye stops comparing

# The canvas. Units, not pixels: the SVG scales, so a theme's font size cannot move a row.
W = 980
LEFT_RANK_X = 8            # the rank number of the left column, left-aligned
LEFT_NAME_X = 40           # the left names
LEFT_VALUE_X = 300         # the first period's value, right-aligned here
LINE_X = 310               # where the connector starts
RIGHT_NAME_X = 660         # the second period's names
RIGHT_VALUE_X = 880        # the second period's value, right-aligned here
RIGHT_RANK_X = W - 8       # the second period's rank, right-aligned
ROW_H = 30
HEAD_H = 34


# ------------------------------------------------------------------------------ numbers
def num_text(value: float, lang: str) -> str:
    if float(value).is_integer():
        return i18n.group_int(int(value), lang)
    text = f"{value:.1f}"
    return text.replace(".", ",") if lang == "nb" else text


def delta_text(value: float, lang: str, t: dict) -> str:
    if value > 0:
        return i18n.fill(t["plus"], value=num_text(value, lang))
    if value < 0:
        return i18n.fill(t["minus"], value=num_text(abs(value), lang))
    return t["unchanged"]


# --------------------------------------------------------------------------------- load
def load(path: pathlib.Path, entity_col: str, period_col: str, measure_col: str,
         period_from: str, period_to: str) -> dict[str, dict[str, float]]:
    rows = tun_core.read_rows(path)
    cols = tun_core.columns(rows)
    for name, given in (("--entity", entity_col), ("--period", period_col),
                        ("--measure", measure_col)):
        if given not in cols:
            die(f"{name} {given!r} is not a column in {path.name}. It has: {', '.join(cols)}")

    values: dict[str, dict[str, float]] = {}
    seen_periods: set[str] = set()
    for i, row in enumerate(rows, start=2):
        entity = (row.get(entity_col) or "").strip()
        period = (row.get(period_col) or "").strip()
        if not entity or not period:
            continue
        seen_periods.add(period)
        if period not in (period_from, period_to):
            continue
        raw = (row.get(measure_col) or "").strip()
        if not raw:
            die(f"row {i} of {path.name} has a {entity_col!r} and a {period_col!r} but no "
                f"{measure_col!r}. An entity with no number has no rank, and drawing it at "
                f"zero would put it last as a finding.")
        value = tun_core.to_number(raw)
        if value is None:
            die(f"row {i} of {path.name} holds {raw!r} in {measure_col!r}, which is not a "
                f"number. A text value ranked against numbers is a rank that means nothing.")
        cells = values.setdefault(entity, {})
        if period in cells:
            die(f"{entity!r} appears twice in {period!r}. Two rows for one entity in one "
                f"period is two numbers for one rank: sum them in the extract, or name the "
                f"rows apart by adding a column to --entity.")
        cells[period] = value

    for period in (period_from, period_to):
        if period not in seen_periods:
            die(f"--from/--to names {period!r} and the data holds no such period in "
                f"{period_col!r}. It holds: {', '.join(sorted(seen_periods)[:6])}"
                + (", ..." if len(seen_periods) > 6 else "")
                + ". A rank change between a period that does not exist is a page about nothing.")
    if period_from == period_to:
        die("--from and --to are the same period, so nothing can move.")
    return values


def ranked(values: dict[str, dict[str, float]], period: str) -> list[dict]:
    """[(entity, value, rank)], best first, with competition ranking: 1, 1, 3 on a tie.

    The order inside a tie is by name, so the same extract in a different row order gives the
    same page. The rank number is derived from the values, never from position in the file.
    """
    present = [(entity, cells[period]) for entity, cells in values.items() if period in cells]
    present.sort(key=lambda pair: (-pair[1], pair[0]))
    out = []
    for index, (entity, value) in enumerate(present):
        rank = index + 1
        if index and value == present[index - 1][1]:
            rank = out[-1]["rank"]          # a tie shares the rank of the one above it
        out.append({"entity": entity, "value": value, "rank": rank})
    return out


# --------------------------------------------------------------------------------- draw
def draw(values: dict[str, dict[str, float]], before: list[dict], after: list[dict],
         period_from: str, period_to: str, lang: str, t: dict) -> str:
    height = HEAD_H + max(len(before), len(after)) * ROW_H + 18
    left_of = {row["entity"]: i for i, row in enumerate(before)}
    right_of = {row["entity"]: i for i, row in enumerate(after)}
    before_of = {row["entity"]: row for row in before}
    after_of = {row["entity"]: row for row in after}

    parts: list[str] = [
        f'<svg viewBox="0 0 {W} {height}" role="img" aria-labelledby="rc-t rc-d" '
        f'preserveAspectRatio="xMinYMin meet">',
        f'<title id="rc-t">{html.escape(t["svg_title"])}</title>',
        f'<desc id="rc-d">{html.escape(i18n.fill(t["svg_desc"], n=len(before) + len(after),
                                                 before=len(before), after=len(after),
                                                 first=period_from, last=period_to))}</desc>',
        f'<text class="rc-head" x="{LEFT_RANK_X}" y="20">{html.escape(period_from)}</text>',
        f'<text class="rc-head" x="{RIGHT_VALUE_X}" y="20" text-anchor="end">'
        f'{html.escape(period_to)}</text>',
    ]

    def y_of(index: int) -> float:
        return HEAD_H + index * ROW_H + ROW_H / 2

    # The connectors first, so the labels sit on top of them.
    for entity, cells in values.items():
        if len(cells) < 2:
            continue                        # a newcomer or a leaver gets no line at all
        y1, y2 = y_of(left_of[entity]), y_of(right_of[entity])
        # Positive means CLIMBED: the old rank minus the new one. Taken the other way round it
        # draws every climber as a fall, which is a page that is wrong everywhere at once and
        # looks entirely normal, because a line between two columns has no inherent direction.
        moved = before_of[entity]["rank"] - after_of[entity]["rank"]
        cls = "rc-up" if moved > 0 else "rc-down" if moved < 0 else "rc-flat"
        parts.append(f'<path class="{cls}" data-entity="{html.escape(entity)}" '
                     f'data-move="{moved}" d="M{LINE_X} {y1:.1f} '
                     f'C{LINE_X + 120} {y1:.1f} {RIGHT_NAME_X - 120} {y2:.1f} '
                     f'{RIGHT_NAME_X - 10} {y2:.1f}"/>')

    for side, rows, period, rank_x, rank_anchor, name_x, value_x in (
            ("left", before, period_from, LEFT_RANK_X, "start", LEFT_NAME_X, LEFT_VALUE_X),
            ("right", after, period_to, RIGHT_RANK_X, "end", RIGHT_NAME_X, RIGHT_VALUE_X)):
        for index, row in enumerate(rows):
            y = y_of(index) + 5
            entity = row["entity"]
            parts.append(f'<text class="rc-rank" x="{rank_x}" y="{y:.1f}" '
                         f'text-anchor="{rank_anchor}">{row["rank"]}</text>')
            parts.append(f'<text class="rc-name" x="{name_x}" y="{y:.1f}">'
                         f'{html.escape(entity)}</text>')
            parts.append(f'<text class="rc-value" x="{value_x}" y="{y:.1f}" '
                         f'text-anchor="end" data-side="{side}" data-rank="{row["rank"]}" '
                         f'data-value="{html.escape(str(row["value"]))}">'
                         f'{html.escape(num_text(row["value"], lang))}</text>')
            if len(values[entity]) < 2:
                # One period only: a word instead of a line, because there is no move to draw.
                word = t["left"] if period == period_from else t["entered"]
                parts.append(f'<text class="rc-mark" x="{name_x}" y="{y + 13:.1f}">'
                             f'{html.escape(word)}</text>')

    parts.append("</svg>")

    return "\n".join(parts)


# ------------------------------------------------------------------------------ summary
def movement(values: dict[str, dict[str, float]], before: list[dict], after: list[dict],
             period_from: str, period_to: str, lang: str, t: dict) -> str:
    """The picture in words, computed from the drawn ranks and never from a judgement."""
    was = {row["entity"]: row["rank"] for row in before}
    now = {row["entity"]: row["rank"] for row in after}
    shared = [e for e in was if e in now]
    entered = [row["entity"] for row in before if len(values[row["entity"]]) < 2]
    left = [row["entity"] for row in after if len(values[row["entity"]]) < 2]
    if not shared:
        return i18n.fill(t["summary_none"], first=period_from, last=period_to)

    moves = {entity: was[entity] - now[entity] for entity in shared}
    climbs = [e for e in shared if moves[e] > 0]
    falls = [e for e in shared if moves[e] < 0]
    flat = [e for e in shared if moves[e] == 0]
    if not climbs and not falls:
        return i18n.fill(t["summary_still"], shared=len(shared), first=period_from,
                         last=period_to)

    top_climb = max(shared, key=lambda e: (moves[e], e))
    top_fall = min(shared, key=lambda e: (moves[e], e))
    parts = [i18n.fill(t["summary_head"], shared=len(shared), climbs=len(climbs),
                       falls=len(falls), flat=len(flat), first=period_from, last=period_to)]
    if moves[top_climb] > 0:
        parts.append(i18n.fill(t["summary_climb"], entity=top_climb,
                               places=moves[top_climb], rank=now[top_climb]))
    if moves[top_fall] < 0:
        parts.append(i18n.fill(t["summary_fall"], entity=top_fall,
                               places=abs(moves[top_fall]), rank=now[top_fall]))
    if entered or left:
        parts.append(i18n.fill(t["summary_edges"], entered=len(entered), left=len(left)))
    return " ".join(parts)


def tie_line(before: list[dict], after: list[dict], period_from: str, period_to: str,
             t: dict) -> str:
    """A shared rank is stated, because 1, 1, 3 looks like a mistake until it is explained."""
    def ties(rows: list[dict]) -> int:
        return sum(1 for i, row in enumerate(rows)
                   if (i and row["rank"] == rows[i - 1]["rank"])
                   or (i + 1 < len(rows) and row["rank"] == rows[i + 1]["rank"]))

    count = ties(before) + ties(after)
    if not count:
        return t["ties_none"]
    return i18n.fill(t["ties_line"], n=count, first=period_from, last=period_to)


# -------------------------------------------------------------------------------- table
def table_rows(before: list[dict], after: list[dict], values: dict[str, dict[str, float]],
               period_from: str, period_to: str, lang: str, t: dict) -> str:
    was = {row["entity"]: row for row in before}
    now = {row["entity"]: row for row in after}
    order = [row["entity"] for row in after] + [row["entity"] for row in before
                                                if row["entity"] not in now]
    out = []
    for entity in order:
        left = was.get(entity)
        right = now.get(entity)
        dash = html.escape(t["dash"])
        out.append(f'      <tr><th scope="row">{html.escape(entity)}</th>'
                   f'<td class="num">{num_text(left["value"], lang) if left else dash}</td>'
                   f'<td class="num">{left["rank"] if left else dash}</td>'
                   f'<td class="num">{num_text(right["value"], lang) if right else dash}</td>'
                   f'<td class="num">{right["rank"] if right else dash}</td>'
                   f'<td class="num">{delta_text(right["value"] - left["value"], lang, t) if left and right else dash}</td>'
                   f'<td class="num">{str(right["rank"] - left["rank"]) if left and right else dash}</td></tr>')
    return "\n".join(out)


# --------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True,
                    help="CSV with one row per entity per period")
    ap.add_argument("--entity", required=True, help="the column that names what is ranked")
    ap.add_argument("--period", required=True, help="the column that names the two periods")
    ap.add_argument("--measure", required=True, help="the numeric column that is ranked")
    ap.add_argument("--from", dest="period_from", required=True,
                    help="the earlier period, exactly as the data writes it")
    ap.add_argument("--to", dest="period_to", required=True,
                    help="the later period, exactly as the data writes it")
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

    values = load(args.data, args.entity, args.period, args.measure,
                  args.period_from, args.period_to)
    before = ranked(values, args.period_from)
    after = ranked(values, args.period_to)

    for label, rows in (("--from", before), ("--to", after)):
        if not rows:
            die(f"no entity has a value in {label} "
                f"({'%s' % (args.period_from if label == '--from' else args.period_to)!r}).")
    if len(before) > MAX_ROWS or len(after) > MAX_ROWS:
        die(f"{max(len(before), len(after))} entities is more than the {MAX_ROWS} rows this "
            f"page draws: past that nobody compares the two columns, they read a list. Filter "
            f"the extract to the part being asked about.")

    shared = [e for e in values if len(values[e]) > 1]
    if not shared:
        die(f"no entity appears in both {args.period_from!r} and {args.period_to!r}, so "
            f"nothing can have moved. That is a page about two different populations, not a "
            f"rank change.")

    svg = draw(values, before, after, args.period_from, args.period_to, lang, t)

    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)
    source = i18n.fill(t["source_line"], name=args.source or args.data.name,
                       entities=len(values))
    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=built,
                                           source=source, lang=lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    # The colours come from tools/tokens/: one seam with every other artefact. auto_dark: a
    # reader whose system is dark gets a dark chart with no script.
    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css)))
    for token, value in {
        "{{TITLE}}": html.escape(args.title),
        "{{SUBTITLE}}": html.escape(i18n.fill(
            t["sub_line"], before=len(before), after=len(after),
            first=args.period_from, last=args.period_to)),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(source),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{ROWS_INLINED}}": str(sum(len(c) for c in values.values())),
        "{{SVG}}": svg,
        "{{CAPTION}}": html.escape(t["caption"]),
        "{{MOVEMENT}}": html.escape(movement(values, before, after, args.period_from,
                                             args.period_to, lang, t)),
        "{{TIES}}": html.escape(tie_line(before, after, args.period_from, args.period_to, t)),
        "{{TABLE_ROWS}}": table_rows(before, after, values, args.period_from, args.period_to,
                                     lang, t),
        "{{PERIOD_FROM}}": html.escape(args.period_from),
        "{{PERIOD_TO}}": html.escape(args.period_to),
        "{{N_SHARED}}": str(len(shared)),
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

    was = {row["entity"]: row["rank"] for row in before}
    now = {row["entity"]: row["rank"] for row in after}
    print(f"periods       : {args.period_from} -> {args.period_to}")
    print(f"entities      : {len(before)} in the first period, {len(after)} in the second, "
          f"{len(shared)} in both")
    for row in after:
        entity = row["entity"]
        if entity in was:
            moved = was[entity] - row["rank"]
            tail = (f"  {i18n.fill(t['plus'], value=moved) if moved > 0 else ('-' + str(-moved)) if moved < 0 else '0'}"
                    f" places from {was[entity]}")
        elif len(values[entity]) < 2:
            # One period only: say which, so the console does not call a newcomer "gone".
            tail = "  " + (t["left"] if args.period_from in values[entity] else t["entered"])
        else:
            tail = ""
        print(f"  {row['rank']:>3} {entity:<18} {num_text(row['value'], lang):>10}{tail}")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
