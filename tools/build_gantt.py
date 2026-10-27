#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a standalone Gantt: the plan, what actually happened, and the slip as a number.

A timeline (35) shows when things happen. This shows whether the plan was kept: for every
task, one bar for what was planned and one for what happened, on the same axis, with the
difference printed as a signed number of days.

    python3 tools/build_gantt.py \\
      --data examples/49-gantt/fremdrift.csv \\
      --task Tiltak --start Planstart --end Planferdig \\
      --actual-start Faktisk-start --actual-end Faktisk-ferdig \\
      --today 2026-10-26 \\
      --title "Fremdrift per tiltak" \\
      --source "Syntetisk eksempeldata (fremdrift.csv)" \\
      --requested-by "Prosjektkontoret" \\
      --out examples/49-gantt/fremdrift.html

What is built in, rather than left to whoever assembles the file:

  * **the slip is a signed number, never a colour.** "Four days late" is the answer; a red bar
    is a mood. Every finished task carries its difference in days in the table and beside the
    bar, and the sign is printed with a real minus.
  * **an unfinished task is a word, not a bar.** A task with no actual end is either not
    started or still running, and drawing a zero-length bar for it would read as "finished on
    time". The state is written out, and the two states are not the same word.
  * **the axis is dates, and only ISO dates are accepted.** Accepting 03.04 and 04.03 means
    guessing which month the source meant, and a plan drawn one month off is worse than one
    that refuses to build.
  * **an end before its start is refused by name**, both for the plan and for the actual bar.
  * **one scale for both bars.** The whole point is comparing them; a second axis would make a
    slip of three days look like a slip of three weeks.
  * **the row order is stated.** Sorted by planned start, ties in source order.
  * **every date and every difference is in the table**, so the picture can be checked.
  * **there is no script.** A plan is a snapshot of the plan as it stood.

Stdlib only, like the rest of tools/. Python 3.8+.
"""
from __future__ import annotations

import argparse
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

TEMPLATE = ROOT / "templates" / "gantt.html"
STRINGS = "gantt"
MAX_TASKS = 28                # above this the task names are a wall and the bars are hairlines
MAX_LABEL = 46
MAX_BYTES = 40 * 1024 * 1024

W = 820
GUTTER = 210                  # the task names live here, right-aligned
SLIPW = 74                    # the signed difference, in its own column
PAD_R = 16
PAD_T = 60                    # room for the tick labels AND the today marker above them
ROW_H = 46
BAR_H = 9
PLOT_W = W - GUTTER - SLIPW - PAD_R

MONTH_NB = ("jan", "feb", "mar", "apr", "mai", "jun", "jul", "aug", "sep", "okt", "nov", "des")
MONTH_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


# ---------------------------------------------------------------------------------- dates
def parse_date(value: str, where: str) -> dt.date:
    """ISO dates only, refused by name otherwise.

    Accepting a second spelling means guessing whether 03.04 is April or March, and a plan
    drawn one month off is worse than one that does not build.
    """
    try:
        return dt.date.fromisoformat(value.strip())
    except ValueError:
        die(f"{where}: {value!r} is not a date. Write it as YYYY-MM-DD (2026-10-24); this "
            f"builder will not guess a dd.mm from an mm.dd.")


def iso_date(day: dt.date, nb: bool) -> str:
    if nb:
        return f"{day.day:02d}.{day.month:02d}.{day.year}"
    return f"{day.day} {MONTH_EN[day.month - 1]} {day.year}"


def month_label(day: dt.date, nb: bool) -> str:
    """Short month and a two-digit year: "okt 26", because the axis is dense."""
    return f"{(MONTH_NB if nb else MONTH_EN)[day.month - 1]} {str(day.year)[2:]}"


# ----------------------------------------------------------------------------------- load
def load(path: pathlib.Path, cols: dict[str, str], lang: str) -> tuple[list[dict], int]:
    if not path.is_file():
        die(f"{path} does not exist")
    rows = tun_core.read_rows(path)
    if not rows:
        die(f"{path.name} has no rows")
    header = tun_core.columns(rows)
    for role, name in cols.items():
        if name and name not in header:
            die(f"--{role} names {name!r}, which is not a column in {path.name}. "
                f"Available: {', '.join(header)}")
    if bool(cols.get("actual-start")) != bool(cols.get("actual-end")):
        die("--actual-start and --actual-end go together: with only one of them there is no "
            "actual bar to draw, and a plan compared against nothing is a timeline (35).")

    parsed: list[dict] = []
    skipped = 0
    for i, row in enumerate(rows, 2):
        task = str(row.get(cols["task"]) or "").strip()
        if not task:
            skipped += 1
            continue                       # a row with no name cannot be labelled
        if len(task) > MAX_LABEL:
            die(f"{path.name}:{i}: the task name is {len(task)} characters, past the "
                f"{MAX_LABEL} this row can hold. Shorten it in the extract; the builder will "
                f"not truncate a name a reader needs to recognise.")
        plan_start = parse_date(str(row.get(cols["start"]) or ""), f"{path.name}:{i} start")
        plan_end = parse_date(str(row.get(cols["end"]) or ""), f"{path.name}:{i} end")
        if plan_end < plan_start:
            die(f"{path.name}:{i}: the planned end {plan_end} is before the planned start "
                f"{plan_start}. A bar cannot run backwards.")
        entry = {"task": task, "plan_start": plan_start, "plan_end": plan_end,
                 "act_start": None, "act_end": None}
        if cols.get("actual-start"):
            raw_start = str(row.get(cols["actual-start"]) or "").strip()
            raw_end = str(row.get(cols["actual-end"]) or "").strip()
            if raw_start:
                entry["act_start"] = parse_date(raw_start,
                                                f"{path.name}:{i} actual start")
            if raw_end:
                entry["act_end"] = parse_date(raw_end, f"{path.name}:{i} actual end")
            if entry["act_end"] and not entry["act_start"]:
                die(f"{path.name}:{i}: the actual end is given but not the actual start. A bar "
                    f"needs both ends; without the start there is nothing to draw.")
            if entry["act_start"] and entry["act_end"] and entry["act_end"] < entry["act_start"]:
                die(f"{path.name}:{i}: the actual end {entry['act_end']} is before the actual "
                    f"start {entry['act_start']}. A bar cannot run backwards.")
        parsed.append(entry)

    if not parsed:
        die(f"no row in {path.name} has a task name and both planned dates.")
    if len(parsed) > MAX_TASKS:
        die(f"{len(parsed)} tasks is past the {MAX_TASKS}-row ceiling: the names collide and "
            f"the bars become hairlines. Split the plan, or keep the milestones and use the "
            f"timeline (build_timeline.py) for the rest.")
    return parsed, skipped


# One declared mapping from a state to its string key. Built by concatenation it would be
# invisible to the i18n gate, which reads usage from source, and a key nobody can see is a key
# nobody notices going stale.
STATE_KEY = {"late": "state_late", "early": "state_early", "ontime": "state_ontime",
             "running": "state_running", "notstarted": "state_notstarted"}


def state_of(row: dict, today: dt.date | None) -> str:
    """Which of the five states this task is in, as a key the page has a word for.

    The order matters: a task that never started is not "on time", and a task with no end but a
    start is running rather than finished.
    """
    if not row["act_start"]:
        return "notstarted"
    if not row["act_end"]:
        return "running"
    slip = (row["act_end"] - row["plan_end"]).days
    return "late" if slip > 0 else ("early" if slip < 0 else "ontime")


def slip_of(row: dict) -> int | None:
    if not (row["act_start"] and row["act_end"]):
        return None
    return (row["act_end"] - row["plan_end"]).days


# ----------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True)
    ap.add_argument("--task", required=True, help="the column naming each task")
    ap.add_argument("--start", required=True, help="planned start, YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="planned finish, YYYY-MM-DD")
    ap.add_argument("--actual-start", default="", metavar="COLUMN",
                    help="actual start, when the extract has one")
    ap.add_argument("--actual-end", default="", metavar="COLUMN",
                    help="actual finish, when the extract has one; empty once a task is done")
    ap.add_argument("--today", default="", metavar="YYYY-MM-DD",
                    help="draw the date as a rule across the plan")
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
    nb = lang == "nb"

    today = parse_date(args.today, "--today") if args.today else None
    cols = {"task": args.task, "start": args.start, "end": args.end,
            "actual-start": args.actual_start, "actual-end": args.actual_end}
    rows, skipped = load(args.data, cols, lang)
    rows.sort(key=lambda r: (r["plan_start"], r["plan_end"]))

    first = min([r["plan_start"] for r in rows] + [r["act_start"] for r in rows if r["act_start"]])
    last = max([r["plan_end"] for r in rows] + [r["act_end"] for r in rows if r["act_end"]]
               + ([today] if today else []))
    if last < first:
        die("every date in this extract is the same day, so there is no axis to draw.")
    span = (last - first).days or 1

    def px(day: dt.date) -> float:
        return GUTTER + (day - first).days / span * PLOT_W

    height = PAD_T + ROW_H * len(rows) + 44
    out = [f'<svg viewBox="0 0 {W} {height}" role="img" aria-labelledby="gt-t gt-d">',
           f'<title id="gt-t">{html.escape(t["svg_title"])}</title>',
           f'<desc id="gt-d">{html.escape(i18n.fill(t["svg_desc"], n=len(rows),
                                                    first=iso_date(first, nb),
                                                    last=iso_date(last, nb),
                                                    plan=args.start))}</desc>']

    # Ticks: weekly while the span is short enough to read, monthly beyond that, and never
    # more than twelve of them whatever the span.
    ticks: list[tuple[dt.date, str]] = []
    if span <= 84:
        day = first
        while day <= last:
            if day.weekday() == 0:                      # Mondays
                ticks.append((day, f"{day.day}. {MONTH_NB[day.month - 1]}" if nb
                              else f"{day.day} {MONTH_EN[day.month - 1]}"))
            day += dt.timedelta(days=1)
    if not ticks or len(ticks) > 14:
        ticks = []
        month = first.replace(day=1)
        while month <= last:
            if month >= first.replace(day=1):
                ticks.append((month, month_label(month, nb)))
            month = (month.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    for day, label in ticks:
        x = px(day)
        out.append(f'<line class="gt-grid" x1="{x:.2f}" y1="{PAD_T - 12}" x2="{x:.2f}" '
                   f'y2="{PAD_T + ROW_H * len(rows)}"/>')
        out.append(f'<text class="gt-tick" x="{x:.2f}" y="{PAD_T - 18}" '
                   f'text-anchor="middle">{html.escape(label)}</text>')

    if today:
        x = px(today)
        out.append(f'<line class="gt-today" x1="{x:.2f}" y1="{PAD_T - 12}" x2="{x:.2f}" '
                   f'y2="{PAD_T + ROW_H * len(rows)}"/>')
        # Its own line, above the tick labels: the marker is often within a few pixels of a
        # month boundary, and two labels at the same y print through each other.
        anchor_x = min(x + 5, W - PAD_R - 44)
        out.append(f'<text class="gt-today-label" x="{anchor_x:.2f}" y="{PAD_T - 46}">'
                   f'{html.escape(t["legend_today"])}</text>')

    late = 0
    worst: tuple[int, str] | None = None
    running = notstarted = 0
    for index, row in enumerate(rows):
        cy = PAD_T + ROW_H * index + ROW_H / 2
        plan_top = cy - BAR_H - 3
        act_top = cy + 3
        out.append(f'<text class="gt-name" x="{GUTTER - 12}" y="{cy + 4:.2f}" '
                   f'text-anchor="end">{html.escape(row["task"])}</text>')
        # the planned bar: an outline, so the actual bar can sit under it and both stay legible
        x1, x2 = px(row["plan_start"]), px(row["plan_end"])
        out.append(f'<rect class="gt-plan" data-task="{html.escape(row["task"])}" '
                   f'x="{x1:.2f}" y="{plan_top:.2f}" width="{max(2.0, x2 - x1):.2f}" '
                   f'height="{BAR_H}"/>')
        # the actual bar: filled, with a distinct shape when the task is still running
        state = state_of(row, today)
        if state == "notstarted":
            out.append(f'<text class="gt-state" x="{px(row["plan_start"]) + 4:.2f}" '
                       f'y="{act_top + BAR_H - 1:.2f}">{html.escape(t["state_notstarted"])}</text>')
            notstarted += 1
        else:
            act_end = row["act_end"] or (today or last)
            ax1, ax2 = px(row["act_start"]), px(act_end)
            cls = "gt-actual gt-running" if state == "running" else "gt-actual"
            out.append(f'<rect class="{cls}" data-task="{html.escape(row["task"])}" '
                       f'x="{ax1:.2f}" y="{act_top:.2f}" width="{max(2.0, ax2 - ax1):.2f}" '
                       f'height="{BAR_H}"/>')
            if state == "running":
                running += 1
        slip = slip_of(row)
        mark = ""
        if slip is not None:
            sign = "\u2212" if slip < 0 else ("+" if slip > 0 else "")
            mark = f'{sign}{abs(slip)}'
            if slip > 0:
                late += 1
                if worst is None or slip > worst[0]:
                    worst = (slip, row["task"])
        elif state == "running":
            mark = t["running_mark"]
        out.append(f'<text class="gt-slip" x="{W - PAD_R}" y="{cy + 4:.2f}" '
                   f'text-anchor="end">{html.escape(mark)}</text>')

    out.append(f'<text class="gt-slip-head" x="{W - PAD_R}" y="{PAD_T - 18}" '
               f'text-anchor="end">{html.escape(t["col_slip"])}</text>')
    out.append("</svg>")
    drawing = "\n".join(out)

    summary = i18n.fill(t["summary_line"], n=len(rows), late=late)
    if worst:
        summary += " " + i18n.fill(t["summary_worst"], task=worst[1], days=worst[0])
    else:
        summary += " " + t["summary_none_late"]
    if running or notstarted:
        summary += " " + i18n.fill(t["summary_open"], running=running, notstarted=notstarted)

    notes = [t["note_bars"], t["note_slip"], t["note_unfinished"], t["note_order"],
             t["note_dates"]]
    if skipped:
        notes.append(i18n.fill(t["skipped"], n=skipped))

    table = []
    for row in rows:
        slip = slip_of(row)
        state = state_of(row, today)
        sign = "" if not slip else ("\u2212" if slip < 0 else "+")
        table.append(
            "<tr>"
            f"<td>{html.escape(row['task'])}</td>"
            f'<td class="num">{html.escape(iso_date(row["plan_start"], nb))}</td>'
            f'<td class="num">{html.escape(iso_date(row["plan_end"], nb))}</td>'
            f'<td class="num">{html.escape(iso_date(row["act_start"], nb)) if row["act_start"] else "–"}</td>'
            f'<td class="num">{html.escape(iso_date(row["act_end"], nb)) if row["act_end"] else "–"}</td>'
            f'<td class="num">{html.escape(sign + str(abs(slip))) if slip is not None else "–"}</td>'
            f'<td>{html.escape(t[STATE_KEY[state]])}</td>'
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
                                              first=iso_date(first, nb),
                                              last=iso_date(last, nb))),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(i18n.fill(t["source_line"], name=source,
                                                 rows=len(rows) + skipped)),
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

    print(f"tasks         : {len(rows)}")
    print(f"span          : {first} .. {last} ({(last - first).days} days)")
    print(f"late          : {late}" + (f", worst +{worst[0]} ({worst[1]})" if worst else ""))
    print(f"open          : {running} running, {notstarted} not started")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
