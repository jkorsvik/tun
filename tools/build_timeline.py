#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a standalone timeline: one bar per row, positioned by its own start and end.

The question "when does this happen, and what overlaps" is answered in a spreadsheet by
comparing two date columns by eye. This draws it: one time axis, one bar per row, the numbers
still written out in a table underneath so a reader can check the picture instead of trusting
it.

    python3 tools/build_timeline.py \\
      --data examples/35-timeline/milepaeler.csv \\
      --title "Utredningen: når skjer det" \\
      --source "Syntetisk eksempeldata (milepaeler.csv)" \\
      --requested-by "Programmet" \\
      --out examples/35-timeline/tidslinje.html

What is built in, rather than left to whoever assembles the file:

  * **there is no script.** A timeline is a picture, and the numbers behind it are in the
    table below the picture, which is also what a screen reader and a printer read. A filter
    would have to re-lay the drawing, and a re-laid drawing is a second thing to get wrong.
  * **the picture and the table are generated from one list of parsed rows**, so they cannot
    disagree. The suite counts both and compares the dates.
  * **a row whose end comes before its start is refused by name.** It cannot be drawn
    honestly, and a negative bar on a time axis is the kind of thing a reader believes.
  * **the tick unit is chosen from the span and printed**, so a two-week plan and a
    four-year plan are not drawn with the same ruler.
  * **"today" is drawn only when it falls inside the window.** A vertical line outside the
    axis is a distraction that implies the drawing is about now when it is about then.

What it deliberately does not do: dependencies, a critical path, percent complete, or colour
by status. Those are claims about the future, and this file only knows the dates it was
given. Status stays a column in the table, where it is a value rather than a colour a
reader has to decode.

Stdlib only, like the rest of tools/. Python 3.8+.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
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

TEMPLATE = ROOT / "templates" / "timeline.html"
STRINGS = "timeline"
MAX_ROWS = 60                 # above this the drawing stops being readable at any size
MAX_SPAN_DAYS = 365 * 40      # a 40-year window on one axis answers no question
MAX_BYTES = 40 * 1024 * 1024

# The canvas. Units, not pixels: the SVG scales, and a theme's font size cannot move a bar.
W = 1000
LABEL_W = 300                 # the name column, left of the axis
MAX_LABEL = 34                # a guard, not a fit: past this the name overlaps the bars
PAD_R = 16
AXIS_H = 30                   # room above the first row for the tick labels
GROUP_H = 26
ROW_H = 30
BAR_H = 16

TICKS = ("days", "weeks", "months", "quarters")
# The word for each ruler, named literally: the i18n gate looks for the key in the
# code, and a key built by string concatenation is a key nobody can find.
TICK_WORDS = {"days": "ticks_days", "weeks": "ticks_weeks",
              "months": "ticks_months", "quarters": "ticks_quarters"}


def parse_date(value: str, where: str) -> dt.date:
    """ISO dates only, refused by name otherwise.

    Accepting a second spelling would mean guessing which of 03.04 and 04.03 the source
    meant, and a timeline drawn one month off is worse than one that does not build.
    """
    try:
        return dt.date.fromisoformat(value.strip())
    except ValueError:
        die(f"{where}: {value!r} is not a date. Write it as YYYY-MM-DD (2026-10-24); "
            f"this builder will not guess a dd.mm from an mm.dd.")


def load(path: pathlib.Path, cols: dict) -> tuple[list[dict], list[str]]:
    """Read the rows, refuse the ones that cannot be drawn, keep the source order."""
    if not path.is_file():
        die(f"{path} does not exist")
    rows = tun_core.read_rows(path)
    if not rows:
        die(f"{path.name} has no rows")
    header = tun_core.columns(rows)
    for role, name in cols.items():
        if name and name not in header:
            die(f"--{role}-col {name!r} is not a column in {path.name}. "
                f"Available: {', '.join(header)}")

    parsed = []
    for i, row in enumerate(rows, 2):
        task = str(row.get(cols["task"]) or "").strip()
        if not task:
            continue                       # a row with no name cannot be labelled
        start = parse_date(str(row.get(cols["start"]) or ""), f"{path.name}:{i} start")
        end = parse_date(str(row.get(cols["end"]) or ""), f"{path.name}:{i} end")
        if len(task) > MAX_LABEL:
            die(f"{path.name}:{i}: {task!r} is {len(task)} characters. A label that runs "
                f"past {MAX_LABEL} overlaps the bars, and a label nobody can read is not a "
                f"label: shorten it, or move the detail into the table.")
        if end < start:
            die(f"{path.name}:{i} ({task}): ends {end} before it starts {start}. "
                f"A bar that runs backwards cannot be drawn honestly.")
        parsed.append({
            "task": task,
            "start": start,
            "end": end,
            "group": str(row.get(cols["group"]) or "").strip() if cols["group"] else "",
            "owner": str(row.get(cols["owner"]) or "").strip() if cols["owner"] else "",
            "status": str(row.get(cols["status"]) or "").strip() if cols["status"] else "",
        })
    if not parsed:
        die(f"{path.name} has no row with a name in {cols['task']!r}")
    if len(parsed) > MAX_ROWS:
        die(f"{len(parsed)} rows is more than the {MAX_ROWS} this drawing can hold without "
            f"becoming unreadable. Group them, split the file, or cut the window.")
    return parsed, header


def tick_unit(span_days: int) -> str:
    """How fine the ruler is, chosen from the span rather than from a preference."""
    if span_days <= 45:
        return "days"
    if span_days <= 400:
        return "weeks"
    if span_days <= 1500:
        return "months"
    return "quarters"


def tick_dates(start: dt.date, end: dt.date, unit: str) -> list[dt.date]:
    """Every tick inside [start, end], aligned to the unit's own boundary.

    Aligned, not evenly spaced: a month tick belongs on the first of the month, or the grid
    lines sit at arbitrary dates and the reader cannot count months off the picture.
    """
    out: list[dt.date] = []
    if unit == "days":
        day = start
        while day <= end:
            out.append(day)
            day += dt.timedelta(days=1)
        return out
    if unit == "weeks":
        day = start - dt.timedelta(days=start.weekday())      # Monday of that week
        if day < start:
            out.append(day)
        while day <= end:
            if day >= start - dt.timedelta(days=7):
                out.append(day)
            day += dt.timedelta(days=7)
        return out
    if unit == "months":
        year, month = start.year, start.month
        while True:
            day = dt.date(year, month, 1)
            if day > end:
                break
            out.append(day)
            month += 1
            if month == 13:
                year, month = year + 1, 1
        return out
    year, month = start.year, ((start.month - 1) // 3) * 3 + 1
    while True:
        day = dt.date(year, month, 1)
        if day > end:
            break
        out.append(day)
        month += 3
        if month > 12:
            year, month = year + 1, month - 12
    return out


def tick_label(day: dt.date, unit: str, t: dict) -> str:
    """A tick in the reader's own words. The first tick of a year carries the year."""
    nb = t["html_lang"] == "nb"
    if unit == "days":
        return f"{day.day}. {MONTH_NB[day.month - 1]}" if nb else f"{day.day} {MONTH_EN[day.month - 1]}"
    if unit == "weeks":
        week = day.isocalendar()[1]
        text = f"uke {week}" if nb else f"w{week}"
        # A year boundary inside the window is the one place a bare week number misleads.
        return f"{text} {day.isocalendar()[0]}" if week == 1 else text
    if unit == "months":
        name = MONTH_NB[day.month - 1] if nb else MONTH_EN[day.month - 1]
        return f"{name} {day.year}" if day.month == 1 else name
    quarter = (day.month - 1) // 3 + 1
    return f"Q{quarter} {day.year}"


MONTH_NB = ("jan", "feb", "mar", "apr", "mai", "jun", "jul", "aug", "sep", "okt", "nov", "des")
MONTH_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def iso_date(day: dt.date, nb: bool) -> str:
    """The date as a reader writes it: 24.10.2026 in Norwegian, 24 Oct 2026 in English."""
    if nb:
        return f"{day.day:02d}.{day.month:02d}.{day.year}"
    return f"{day.day} {MONTH_EN[day.month - 1]} {day.year}"


def draw(rows: list[dict], ticks: list[dt.date], unit: str, today: dt.date | None,
         t: dict) -> tuple[str, int]:
    """The SVG, and the height it needs.

    Geometry only: every x is a date on one axis, so two bars that overlap in time overlap
    on the page. That is the whole claim the picture makes.
    """
    nb = t["html_lang"] == "nb"
    dom_start = min(min(r["start"] for r in rows), ticks[0] if ticks else rows[0]["start"])
    dom_end = max(max(r["end"] for r in rows), ticks[-1] if ticks else rows[0]["end"])
    span = max(1, (dom_end - dom_start).days)
    plot = W - LABEL_W - PAD_R

    def x(day: dt.date) -> float:
        return LABEL_W + (day - dom_start).days / span * plot

    # Rows, in the order the file gave them: a timeline sorted behind the reader's back is a
    # second opinion about the data. Groups keep their first appearance for the same reason.
    order: list[str] = []
    per_group: dict[str, list[dict]] = {}
    for row in rows:
        key = row["group"]
        if key not in per_group:
            per_group[key] = []
            order.append(key)
        per_group[key].append(row)

    TODAY_ROOM = 18          # the "today" label sits under the last row, not on it
    height = AXIS_H + sum(GROUP_H + ROW_H * len(per_group[g]) for g in order) \
        + TODAY_ROOM
    parts: list[str] = [
        f'<svg viewBox="0 0 {W} {height}" role="img" aria-labelledby="tl-t tl-d" '
        f'preserveAspectRatio="xMinYMin meet">',
        f'<title id="tl-t">{html.escape(t["svg_title"])}</title>',
        f'<desc id="tl-d">{html.escape(i18n.fill(t["svg_desc"], n=len(rows),
                                                  **{"from": iso_date(dom_start, nb),
                                                     "to": iso_date(dom_end, nb)}))}</desc>',
    ]

    # Every tick gets its grid line; a label is printed only where there is room for it.
    # 64 units is about one 14-unit label and its padding, measured off the drawing rather
    # than guessed per label: labels that collide are five words on top of each other.
    spacing = plot / max(1, len(ticks) - 1) if len(ticks) > 1 else plot
    step = max(1, int(64 / spacing + 0.999)) if spacing else 1
    labelled = set(range(0, len(ticks), step))
    if len(ticks) > 1:
        last = len(ticks) - 1
        # The window's end is always worth a label, and the one it would land on top of is
        # dropped instead: with a stepped label plus a forced last one, the pair can end up
        # one tick apart, which is two labels in one place.
        before = max((i for i in labelled if i < last), default=None)
        if before is not None and (last - before) < step:
            labelled.discard(before)
        labelled.add(last)
    for i, day in enumerate(ticks):
        tx = x(day)
        parts.append(f'<line class="tl-grid" x1="{tx:.1f}" y1="{AXIS_H - 6}" '
                     f'x2="{tx:.1f}" y2="{height - 8}"/>')
        if i not in labelled:
            continue
        anchor = "start" if i == 0 else ("end" if i == len(ticks) - 1 else "middle")
        parts.append(f'<text class="tl-tick" x="{tx:.1f}" y="{AXIS_H - 12}" '
                     f'text-anchor="{anchor}">{html.escape(tick_label(day, unit, t))}</text>')

    y = AXIS_H
    for group in order:
        if group:
            parts.append(f'<rect class="tl-band" x="0" y="{y}" width="{W}" height="{GROUP_H}"/>')
            parts.append(f'<text class="tl-group" x="8" y="{y + 18}">'
                         f'{html.escape(group)}</text>')
        y += GROUP_H
        for row in per_group[group]:
            bar_y = y + (ROW_H - BAR_H) / 2
            x1 = x(row["start"])
            x2 = x(row["end"]) + (plot / span)     # a one-day bar is still a bar
            width = max(3.0, x2 - x1)
            parts.append(f'<text class="tl-task" x="8" y="{y + 20}">'
                         f'{html.escape(row["task"])}</text>')
            parts.append(f'<rect class="tl-bar" x="{x1:.1f}" y="{bar_y:.1f}" '
                         f'width="{width:.1f}" height="{BAR_H}"><title>{html.escape(row["task"])}'
                         f': {iso_date(row["start"], nb)} – {iso_date(row["end"], nb)}</title>'
                         f'</rect>')
            # The duration sits beside the bar only when there is room for it: a number
            # printed over the axis is a number nobody reads.
            if x2 + 70 < W - PAD_R:
                days = (row["end"] - row["start"]).days + 1
                parts.append(f'<text class="tl-days" x="{x2 + 6:.1f}" '
                             f'y="{y + 20}">{days}</text>')
            y += ROW_H

    if today is not None and dom_start <= today <= dom_end:
        tx = x(today)
        parts.append(f'<line class="tl-today" x1="{tx:.1f}" y1="{AXIS_H - 6}" '
                     f'x2="{tx:.1f}" y2="{height - 8}"/>')
        parts.append(f'<text class="tl-today-label" x="{tx:.1f}" y="{height - 5}" '
                     f'text-anchor="middle">{html.escape(t["legend_today"])}</text>')

    parts.append("</svg>")
    return "\n".join(parts), height


def table_rows(rows: list[dict], t: dict) -> str:
    """The same rows as the picture, with the dates written out.

    Same list, same order, no filtering: a table that dropped a row the picture drew would
    make the two disagree about how many rows there are.
    """
    nb = t["html_lang"] == "nb"
    out = []
    for row in rows:
        days = (row["end"] - row["start"]).days + 1
        cells = [
            f"<td>{html.escape(row['task'])}</td>",
            f"<td>{iso_date(row['start'], nb)}</td>",
            f"<td>{iso_date(row['end'], nb)}</td>",
            f'<td class="num">{days}</td>',
            f"<td>{html.escape(row['group'] or t['unknown'])}</td>",
            f"<td>{html.escape(row['owner'] or t['unknown'])}</td>",
            f"<td>{html.escape(row['status'] or t['unknown'])}</td>",
        ]
        out.append("      <tr>" + "".join(cells) + "</tr>")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True, help="CSV with a row per bar")
    ap.add_argument("--title", required=True)
    ap.add_argument("--task-col", default="Task", help="the column with the row's name")
    ap.add_argument("--start-col", default="Start", help="the column with the start date")
    ap.add_argument("--end-col", default="End", help="the column with the end date")
    ap.add_argument("--group-col", default="Group",
                    help="the column that groups rows under a band (empty for none)")
    ap.add_argument("--owner-col", default="Owner", help="who is responsible (optional)")
    ap.add_argument("--status-col", default="Status", help="the status value (optional)")
    ap.add_argument("--today", default="",
                    help="YYYY-MM-DD to draw as today, if it falls inside the window. "
                         "Default: the build date, drawn only when it is inside")
    ap.add_argument("--no-today", action="store_true", help="draw no today line at all")
    ap.add_argument("--source", default="", help="where the rows came from")
    ap.add_argument("--requested-by", default="", help="a role, not a person's name")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--feedback-to", default="", metavar="ADDRESS_OR_ISSUE_URL",
                    help=feedback_link.FLAG_HELP)
    i18n.add_lang_argument(ap)
    args = ap.parse_args(argv)
    t = i18n.load(STRINGS, args.lang)

    cols = {"task": args.task_col, "start": args.start_col, "end": args.end_col,
            "group": args.group_col, "owner": args.owner_col, "status": args.status_col}
    rows, header = load(args.data, cols)

    dom_start = min(r["start"] for r in rows)
    dom_end = max(r["end"] for r in rows)
    span_days = max(1, (dom_end - dom_start).days)
    if span_days > MAX_SPAN_DAYS:
        die(f"the rows span {span_days} days. One axis over {MAX_SPAN_DAYS // 365} years "
            f"answers no question; split the window and build two files.")

    unit = tick_unit(span_days)
    ticks = tick_dates(dom_start, dom_end, unit)

    today: dt.date | None = None
    if not args.no_today:
        today = parse_date(args.today, "--today") if args.today else dt.date.today()

    svg, height = draw(rows, ticks, unit, today, t)

    nb = args.lang == "nb"
    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)
    source = i18n.fill(t["source_line"], name=args.source or args.data.name,
                       rows=len(rows), **{"from": iso_date(dom_start, nb), "to": iso_date(dom_end, nb)})
    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=built,
                                           source=source, lang=args.lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    legend = []
    if today is not None and dom_start <= today <= dom_end:
        legend.append(f'<li><span class="sw" style="background:var(--today)"></span>'
                      f'{html.escape(t["legend_today"])}</li>')
    legend.append(f'<li><span class="sw" style="background:var(--bar)"></span>'
                  f'{html.escape(t["legend_row"])}</li>')

    # The tokens are inlined here rather than written into the template, so this page shares
    # one seam with every other artefact. auto_dark: a reader whose system is dark gets a
    # dark drawing with no script, and the bars are re-pointed in the template because a
    # bar fill cannot inherit a page colour.
    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
    for token, value in {
        "{{TOKEN_CSS}}": strip_css_comments(token_css),
        "{{TITLE}}": html.escape(args.title),
        "{{SUBTITLE}}": html.escape(i18n.fill(t["sub_line"], rows=len(rows),
                                              **{"from": iso_date(dom_start, nb),
                                                 "to": iso_date(dom_end, nb)})),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(source),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{ROWS_INLINED}}": str(len(rows)),
        "{{TICKS_NOTE}}": html.escape(t[TICK_WORDS[unit]]),
        "{{SVG}}": svg,
        "{{LEGEND}}": "".join(legend),
        "{{TABLE_ROWS}}": table_rows(rows, t),
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
    print(f"rows          : {len(rows)}")
    print(f"window        : {iso_date(dom_start, nb)} to {iso_date(dom_end, nb)} "
          f"({span_days} days, {t[f'ticks_{unit}']})")
    print(f"today line    : {'drawn' if today is not None and dom_start <= today <= dom_end else 'not drawn'}")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
