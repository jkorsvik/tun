#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a standalone cohort grid: one row per cohort, one column per period since it started.

A cohort grid answers "of the people who started in March, how many were still here in
April, in May, and so on". It is the one shape that has to *derive* its own axis: the
columns are not a column in the file, they are periods counted from each cohort's own
start, and that derivation is where the shape is usually drawn wrongly:

  * **the denominator is the whole file.** Then every cell is small and the picture says
    nothing. Here every share is divided by that row's own cohort size, printed beside it.
  * **a cell that cannot exist yet is drawn as zero.** "Nobody came back" and "the period
    has not happened" are opposite findings. A cell that is not yet observable is hatched,
    is never a number, and has its own legend entry.
  * **the cohort is the first row the file happens to hold.** A cohort must be the period
    of each entity's earliest date, so an extract sorted the other way gives the same
    picture. That is asserted in the tests, not assumed.
  * **one entity counts twice in one cell** because someone had three rows that month.
    Cells count distinct entities.
  * **a cohort too small to speak about is drawn anyway.** A square with two people in it
    is noise wearing the same colour as a finding. Cohorts under `--min-cohort` are named
    with their sizes instead of drawn.

    python3 tools/build_cohort.py \\
      --data examples/44-cohort/kunder.csv \\
      --id Kunde --date Dato \\
      --title "Hvor mange blir med videre" \\
      --source "Syntetisk eksempeldata (kunder.csv)" \\
      --requested-by "Kundeservice" \\
      --out examples/44-cohort/kohort.html

There is no script in the page: a filter would re-derive the cohorts, and the derivation is
the claim being made.

Stdlib only, like the rest of tools/. Python 3.8+.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import pathlib
import re
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

TEMPLATE = ROOT / "templates" / "cohort.html"
STRINGS = "cohort"

MAX_BYTES = 40 * 1024 * 1024
MAX_COHORTS = 40          # longer than this, the page is a table of rows nobody compares
MAX_PERIODS = 24

# One hue (the design system blue) mixed out of white, the same stops as the heatmap, chosen so
# every stop has an ink at 4.5:1 or better. The band edges are percentages of the cohort,
# not of the file, and they are fixed rather than fitted to this extract so that two pages
# can be read against each other.
RAMP_T = (0.12, 0.32, 0.55, 0.78, 1.00)
EDGES = (10, 25, 50, 75)
BRAND = (47, 93, 158)
INK = (10, 10, 10)
WHITE = (255, 255, 255)

# Named here, literally, so the i18n gate can see that every key is used: a key built by
# an f-string, or indexed as `band_%d`, is invisible to a scanner that reads the source.
PERIODS = {"month": "month", "week": "week"}
PERIOD_KEYS = {"month": "period_month", "week": "period_week"}
BAND_KEYS = ("band_0", "band_1", "band_2", "band_3", "band_4")
_ISO = re.compile(r"^(\d{4})-(\d{2})(?:-(\d{2}))?$")


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


def mix(fraction: float) -> tuple[int, int, int]:
    return tuple(round(WHITE[i] * (1 - fraction) + BRAND[i] * fraction)  # type: ignore[return-value]
                 for i in range(3))


RAMP = [mix(t) for t in RAMP_T]


def ink_for(fill: tuple[int, int, int]) -> str:
    """The ink with more contrast against this fill, measured rather than assumed."""
    return hexa(INK) if contrast(fill, INK) >= contrast(fill, WHITE) else "#ffffff"


def band_of(share: float) -> int:
    """Which of the five bands a share falls in. Edges are upper-exclusive."""
    for index, edge in enumerate(EDGES):
        if share < edge:
            return index
    return len(EDGES)


# ------------------------------------------------------------------------------- dates
def period_of(value, row_no: int, column: str, unit: str) -> tuple[int, str]:
    """(a sortable index, the label) for one date cell.

    Month accepts `YYYY-MM` and `YYYY-MM-DD`. Week accepts a full date only: an ISO week
    cannot be named without the day, and guessing one would move rows between cohorts.
    """
    text = str(value or "").strip()
    match = _ISO.match(text)
    if not match:
        die(f"{column!r} must hold dates as YYYY-MM-DD (or YYYY-MM for months), and row "
            f"{row_no} holds {text!r}. A cohort needs a date per row; a value that cannot be "
            f"read would silently join the wrong cohort.")
    year, month, day = int(match.group(1)), int(match.group(2)), match.group(3)
    if not 1 <= month <= 12:
        die(f"{column!r} row {row_no} holds month {month} in {text!r}, which is not a month")
    if unit == "month":
        return year * 12 + (month - 1), f"{year:04d}-{month:02d}"
    if day is None:
        die(f"--period week needs a full date, and row {row_no} holds {text!r}. An ISO week "
            f"cannot be named from a month alone.")
    try:
        date = dt.date(year, month, int(day))
    except ValueError:
        die(f"{column!r} row {row_no} holds {text!r}, which is not a real date")
    iso = date.isocalendar()
    return iso.year * 100 + iso.week, f"{iso.year:04d}-W{iso.week:02d}"


def label_of(index: int, unit: str) -> str:
    if unit == "month":
        return f"{index // 12:04d}-{index % 12 + 1:02d}"
    return f"{index // 100:04d}-W{index % 100:02d}"


# -------------------------------------------------------------------------------- load
def load(path: pathlib.Path, id_col: str, date_col: str, unit: str):
    """{entity: {period index: rows}} and how many rows had an empty id."""
    if not path.is_file():
        die(f"{path} does not exist")
    rows = tun_core.read_rows(path)
    if not rows:
        die(f"{path.name} has no rows")
    header = tun_core.columns(rows)
    for flag, name in (("--id", id_col), ("--date", date_col)):
        if name not in header:
            die(f"{flag} {name!r} is not a column in {path.name}. "
                f"Available: {', '.join(header)}")
    seen: dict[str, dict[int, int]] = {}
    blank = 0
    for index, row in enumerate(rows, start=2):
        entity = str(row.get(id_col) or "").strip()
        if not entity:
            blank += 1
            continue
        period, _label = period_of(row.get(date_col), index, date_col, unit)
        bucket = seen.setdefault(entity, {})
        bucket[period] = bucket.get(period, 0) + 1
    if not seen:
        die(f"no row in {path.name} has both {id_col!r} and {date_col!r} filled in, so there "
            f"are no cohorts to draw")
    return seen, blank


def build_matrix(seen: dict[str, dict[int, int]], max_periods: int, unit: str):
    """Rows sorted by cohort, each with its size and its per-offset counts."""
    groups: dict[int, dict[int, int]] = {}
    for periods in seen.values():
        first = min(periods)
        counts = groups.setdefault(first, {})
        for period in periods:
            offset = period - first
            if 0 <= offset < max_periods:
                counts[offset] = counts.get(offset, 0) + 1
    last = max(max(periods) for periods in seen.values())
    rows = []
    for first in sorted(groups):
        counts = groups[first]
        rows.append({"index": first, "label": label_of(first, unit),
                     "size": counts.get(0, 0), "cells": counts})
    return rows, last


# ------------------------------------------------------------------------------ render
def share_pct(count: int, size: int) -> int:
    """The share as a whole percent, rounded half up. The count is always beside it."""
    return (count * 200 + size) // (2 * size)


def percent_text(value: int, lang: str) -> str:
    return f"{value}\u00a0%" if lang == "nb" else f"{value}%"


def head_cols(periods: int) -> str:
    return "\n".join(
        f'      <th scope="col">{html.escape("+" + str(k))}</th>' for k in range(periods))


def table_rows(rows, periods: int, lang: str, size_text) -> str:
    out = []
    for row in rows:
        cells = []
        for k in range(periods):
            count = row["cells"].get(k)
            if count is None:
                cells.append('<td class="future"></td>')
                continue
            fill = RAMP[band_of(share_pct(count, row["size"]))]
            ink = ink_for(fill)
            cells.append(
                f'<td style="background:{hexa(fill)};color:{ink}">'
                f'{i18n.group_int(count, lang)}'
                f'<span class="pc">{html.escape(percent_text(share_pct(count, row["size"]), lang))}</span>'
                f'</td>')
        out.append(
            f'      <tr><th scope="row">{html.escape(row["label"])}'
            f'<span class="sz">{html.escape(size_text(row["size"]))}</span></th>'
            + "".join(cells) + "</tr>")
    return "\n".join(out)


def legend_html(lang: str, t: dict[str, str]) -> str:
    items = []
    for index, fill in enumerate(RAMP):
        items.append(f'    <li><span class="sw" style="background:{hexa(fill)}"></span>'
                     f'{html.escape(t[BAND_KEYS[index]])}</li>')
    items.append(f'    <li><span class="sw sw-future"></span>'
                 f'{html.escape(t["band_future"])}</li>')
    return ('  <ul class="legend" aria-label="' + html.escape(t["legend_head"]) + '">\n'
            + "\n".join(items) + "\n  </ul>")


def word_of(t: dict[str, str], n: int) -> str:
    """The noun alone: "person" or "personer". A sentence supplies its own number."""
    return t["word_one" if n == 1 else "word_other"]


def size_label(t: dict[str, str], n: int, lang: str) -> str:
    """The noun with its number, for the line under a cohort name."""
    return i18n.fill(t["col_size"], n=i18n.group_int(n, lang), word=word_of(t, n))


# -------------------------------------------------------------------------------- main
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a cohort grid: one row per cohort, one column per period since it started.")
    parser.add_argument("--data", required=True, type=pathlib.Path)
    parser.add_argument("--id", required=True, help="the column that names one person or account")
    parser.add_argument("--date", required=True, help="the column holding the activity date")
    parser.add_argument("--period", choices=sorted(PERIODS), default="month")
    parser.add_argument("--min-cohort", type=int, default=5,
                        help="cohorts smaller than this are named, not drawn (default 5)")
    parser.add_argument("--max-periods", type=int, default=12,
                        help=f"how many columns to draw at most (default 12, max {MAX_PERIODS})")
    parser.add_argument("--title", required=True)
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--source", default="")
    parser.add_argument("--requested-by", default="")
    parser.add_argument("--out", required=True, type=pathlib.Path)
    parser.add_argument("--feedback-to", default="")
    i18n.add_lang_argument(parser)
    args = parser.parse_args()

    lang = getattr(args, "lang", i18n.DEFAULT_LANG)
    if not 1 <= args.max_periods <= MAX_PERIODS:
        die(f"--max-periods must be between 1 and {MAX_PERIODS}")
    if args.min_cohort < 1:
        die("--min-cohort must be at least 1")

    t = i18n.load(STRINGS, lang)

    seen, blank = load(args.data, args.id, args.date, args.period)
    rows, last = build_matrix(seen, args.max_periods, args.period)
    if len(rows) > MAX_COHORTS:
        die(f"the data holds {len(rows)} cohorts and this page draws at most {MAX_COHORTS}. "
            f"A grid longer than that is a table: widen the period with --period week, or "
            f"filter the extract.")

    drawn = [r for r in rows if r["size"] >= args.min_cohort]
    small = [r for r in rows if r["size"] < args.min_cohort]
    if not drawn:
        biggest = max(r["size"] for r in rows)
        die(f"every cohort is smaller than --min-cohort {args.min_cohort} (the largest holds "
            f"{biggest}). Lower the threshold, or widen the period with --period week.")

    periods = min(args.max_periods, last - min(r["index"] for r in drawn) + 1)

    def size_word(n: int) -> str:
        return word_of(t, n)

    body = table_rows(drawn, periods, lang, lambda n: size_label(t, n, lang))
    cols = head_cols(periods)

    biggest = max(drawn, key=lambda r: (r["size"], -r["index"]))
    k1 = biggest["cells"].get(1)
    if periods < 2 or k1 is None:
        lead = t["note_none"]
    else:
        lead = i18n.fill(t["note_lead"], cohort=biggest["label"],
                         size=i18n.group_int(biggest["size"], lang),
                         word=size_word(biggest["size"]),
                         k1=i18n.group_int(k1, lang),
                         k1p=i18n.group_int(share_pct(k1, biggest["size"]), lang))

    if small:
        small_list = ", ".join(f"{r['label']} ({i18n.group_int(r['size'], lang)})" for r in small)
    else:
        small_list = t["none"]
    notes = [
        i18n.fill(t["meta_1"], entity=args.id),
        t["meta_2"],
        t["meta_3"],
        t["meta_4"],
        i18n.fill(t["meta_5"], mincohort=i18n.group_int(args.min_cohort, lang),
                  word=size_word(args.min_cohort), smalllist=small_list),
        i18n.fill(t["meta_6"], period=t[PERIOD_KEYS[args.period]]),
    ]
    note_block = "\n".join(f"    <li>{html.escape(note)}</li>" for note in notes)

    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)
    source = args.source or args.data.name
    if blank:
        source += " \u00b7 " + i18n.fill(t["blank_rows"], n=i18n.group_int(blank, lang))
    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=built,
                                           source=source, lang=lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    subtitle = args.subtitle or i18n.fill(
        t["sub_line"], cohorts=len(drawn), entities=i18n.group_int(len(seen), lang),
        word=size_word(len(seen)))

    # The colours come from tools/tokens/: one seam with every other artefact. auto_dark: a
    # reader whose system is dark gets a dark cohort grid with no script.
    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css)))
    for token, value in {
        "{{TITLE}}": html.escape(args.title),
        "{{SUBTITLE}}": html.escape(subtitle),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(source),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{COHORT_COUNT}}": str(len(drawn)),
        "{{ENTITY_COUNT}}": i18n.group_int(len(seen), lang),
        "{{ENTITY_WORD}}": size_word(len(seen)),
        "{{CAPTION}}": html.escape(f'{t["caption_intro"]} {t["caption_future"]}'),
        "{{TABLE_HEAD_COLS}}": cols,
        "{{TABLE_ROWS}}": body,
        "{{LEGEND}}": legend_html(lang, t),
        "{{NOTE_LEAD}}": html.escape(lead),
        "{{NOTE_LIST}}": note_block,
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

    print(f"cohorts       : {len(drawn)} drawn, {len(small)} too small (under "
          f"{args.min_cohort})")
    print(f"people        : {len(seen)} distinct")
    print(f"grid          : {len(drawn)} x {periods} ({args.period})")
    print(f"lead          : {lead}")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
