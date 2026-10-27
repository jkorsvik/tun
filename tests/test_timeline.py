#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The timeline: one bar per row, positioned by its own start and end on one axis.

A date column pair answers "when" only for someone willing to compare two columns by eye.
The picture answers it by looking, which is exactly why it has to be checked rather than
trusted: a bar in the wrong place is a plausible picture of a wrong plan.

  1. every bar's x and width is the proportion its own dates ask for, measured against the
     domain the page printed, not against numbers the builder kept to itself
  2. the picture and the table hold the same rows in the same order, so neither can lose one
  3. the ruler is chosen from the span and named on the page
  4. a row that cannot be drawn is refused by name: an end before its start, a date that is
     not ISO, a label that would run over the bars, more rows than can be read
  5. "today" is drawn only inside the window, and only when asked
  6. there is no script, and the drawing is announced as a picture with a name and a
     description, because a screen reader cannot read bars

Run: python3 tests/test_timeline.py
"""
from __future__ import annotations

import datetime as dt
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_timeline.py"
TEMPLATE = ROOT / "templates" / "timeline.html"

FAILURES: list[str] = []
CHECKS = 0
W, LABEL_W, PAD_R = 1000, 300, 16


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


def build(out: pathlib.Path, data: pathlib.Path, *extra: str,
          no_today: bool = True) -> subprocess.CompletedProcess:
    """Build. `no_today` is on by default so a test does not depend on the day it runs."""
    flag = ["--no-today"] if no_today else []
    return subprocess.run(
        [sys.executable, str(BUILDER), "--data", str(data), "--title", "Tidslinje",
         *flag, "--out", str(out), *extra],
        capture_output=True, text=True)


def write(path: pathlib.Path, rows: list[str]) -> pathlib.Path:
    path.write_text("Task,Start,End,Group,Owner,Status\n" + "\n".join(rows) + "\n",
                    encoding="utf-8")
    return path


def bars(blob: str) -> list[tuple[float, float]]:
    """(x, width) for every bar, in document order."""
    return [(float(x), float(w)) for x, w in
            re.findall(r'<rect class="tl-bar" x="([-\d.]+)" y="[-\d.]+" width="([-\d.]+)"', blob)]


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td)
        data = write(work / "plan.csv", [
            "Alfa,2026-01-05,2026-01-16,Forst,Team A,Pagaende",
            "Beta,2026-01-12,2026-02-06,Forst,Team B,Pagaende",
            "Gamma,2026-02-02,2026-02-06,Andre,Team A,Planlagt",
            "Delta,2026-02-09,2026-02-09,Andre,Team B,Planlagt",
        ])
        page = work / "tl.html"
        res = build(page, data, "--today", "2026-01-20")
        chk(res.returncode == 0, "the builder runs", (res.stderr or "")[-300:])
        blob = page.read_text(encoding="utf-8")

        print("\nthe picture is the dates, to scale")
        parsed = [("Alfa", "2026-01-05", "2026-01-16"), ("Beta", "2026-01-12", "2026-02-06"),
                  ("Gamma", "2026-02-02", "2026-02-06"), ("Delta", "2026-02-09", "2026-02-09")]
        # The domain is the window the page printed in its own subtitle, not a number the
        # builder kept to itself: that is what makes this a check on the drawing.
        sub = re.search(r'class="sub">[^<]*?(\d{2})\.(\d{2})\.(\d{4}) til (\d{2})\.(\d{2})\.(\d{4})',
                        blob)
        chk(sub is not None, "the page states the window it drew")
        if sub:
            dom_start = dt.date(int(sub.group(3)), int(sub.group(2)), int(sub.group(1)))
            dom_end = dt.date(int(sub.group(6)), int(sub.group(5)), int(sub.group(4)))
            span = max(1, (dom_end - dom_start).days)
            plot = W - LABEL_W - PAD_R
            got = bars(blob)
            chk(len(got) == len(parsed), "one bar per row", f"{len(got)} bars, {len(parsed)} rows")
            wrong = []
            for (name, s, e), (bx, bw) in zip(parsed, got):
                start, end = dt.date.fromisoformat(s), dt.date.fromisoformat(e)
                want_x = LABEL_W + (start - dom_start).days / span * plot
                # The bar covers its end day, so its right edge is the end plus one unit of
                # the axis; the tolerance is one unit of the 1000-unit canvas.
                want_w = max(3.0, (end - start).days / span * plot + plot / span)
                if abs(bx - want_x) > 1.0 or abs(bw - want_w) > 1.5:
                    wrong.append(f"{name}: x {bx:.1f}/{want_x:.1f} w {bw:.1f}/{want_w:.1f}")
            chk(not wrong, "every bar starts and ends where its own dates put it",
                "; ".join(wrong[:2]))
            chk(got[0][0] < got[1][0] < got[3][0],
                "a later start is further right, so the axis runs one way")
            chk(got[3][1] <= got[2][1] and got[3][1] >= 3.0,
                "a one-day row is still a visible bar, not a hairline", f"{got[3][1]}")

        print("\nthe picture and the table cannot disagree")
        body = re.search(r"<tbody>(.*?)</tbody>", blob, re.S)
        chk(body is not None, "the table has a body")
        if body:
            rows = re.findall(r"<tr>(.*?)</tr>", body.group(1), re.S)
            chk(len(rows) == len(parsed), "the table has the same number of rows as the picture",
                f"{len(rows)} vs {len(parsed)}")
            names = [re.search(r"<td>([^<]*)</td>", r).group(1) for r in rows]
            chk(names == [p[0] for p in parsed], "in the file's own order, not a sort",
                ", ".join(names))
            dates = re.findall(r"<td>(\d{2}\.\d{2}\.\d{4})</td>", body.group(1))
            chk(dates[:2] == ["05.01.2026", "16.01.2026"],
                "with the dates written out, so a reader can check the bar", str(dates[:2]))

        print("\nthe ruler is chosen from the span and named")
        for days, unit, label in ((10, "days", "dagsmerker"), (200, "weeks", "ukemerker"),
                                  (800, "months", "månedsmerker"), (3000, "quarters", "kvartalsmerker")):
            span_data = write(work / f"span{days}.csv",
                              [f"Lang,2026-01-05,{(dt.date(2026, 1, 5) + dt.timedelta(days=days)).isoformat()},"
                               f"En,Team,Pagaende"])
            out = work / f"span{days}.html"
            res = build(out, span_data)
            text = out.read_text(encoding="utf-8") if out.exists() else ""
            chk(res.returncode == 0 and label in text,
                f"{days} days is drawn with {unit} ticks", (res.stderr or "")[-120:])

        print("\na row that cannot be drawn is refused by name")
        refusals = [
            ("end before start", "Snu,2026-03-10,2026-03-01,En,Team,Pagaende",
             ["ends", "before it starts"]),
            ("a date that is not ISO", "Dato,10.03.2026,2026-03-20,En,Team,Pagaende",
             ["not a date", "YYYY-MM-DD"]),
            ("a label that would run over the bars",
             "Denne raden har et navn som er alt for langt,2026-03-01,2026-03-02,En,Team,Pagaende",
             ["overlaps the bars"]),
        ]
        for what, row, words in refusals:
            bad = write(work / "bad.csv", [row])
            res = build(work / "bad.html", bad)
            chk(res.returncode == 2 and all(w in res.stderr for w in words),
                f"{what} is refused, with the reason", (res.stderr or "")[-160:])

        crowd = write(work / "crowd.csv",
                      [f"Rad {i},2026-01-05,2026-01-06,En,Team,Pagaende" for i in range(80)])
        res = build(work / "crowd.html", crowd)
        chk(res.returncode == 2 and "unreadable" in res.stderr,
            "more rows than the drawing can hold is refused, not squeezed",
            (res.stderr or "")[-140:])

        empty = work / "empty.csv"
        empty.write_text("Task,Start,End,Group,Owner,Status\n", encoding="utf-8")
        res = build(work / "empty.html", empty)
        chk(res.returncode == 2, "an empty file is refused rather than drawn empty")

        print("\n'today' is drawn only inside the window, and only when asked")
        inside = work / "inside.html"
        build(inside, data, "--today", "2026-01-20", no_today=False)
        chk('class="tl-today"' in inside.read_text(encoding="utf-8"),
            "a today inside the window is drawn")
        outside = work / "outside.html"
        build(outside, data, "--today", "2027-06-01", no_today=False)
        chk('class="tl-today"' not in outside.read_text(encoding="utf-8"),
            "a today after the window is not drawn at all, rather than pinned to the edge")
        chk('class="tl-today"' not in blob, "--no-today draws none")

        print("\nthe drawing is a picture, and says so")
        chk('role="img"' in blob, "the SVG announces itself as a picture")
        chk('aria-labelledby="tl-t" aria-labelledby="tl-d"' not in blob and
            'aria-labelledby="tl-t tl-d"' in blob, "named and described by its own ids")
        chk('<title id="tl-t">' in blob and '<desc id="tl-d">' in blob,
            "and both the title and the description are there")
        chk("{" not in re.search(r'<desc id="tl-d">([^<]*)</desc>', blob).group(1),
            "the description carries no unfilled slot", "a slot survived")

        print("\nthere is no script, and the same input gives the same bytes")
        chk("<script" not in blob.lower(), "no script element, in any case")
        again = work / "again.html"
        build(again, data, "--today", "2026-01-20")
        chk(again.read_bytes() == page.read_bytes(),
            "two builds with the same inputs and a given --today are identical")

        print("\nthe English build is English")
        en = work / "en.html"
        res = build(en, data, "--today", "2026-01-20", "--lang", "en")
        eblob = en.read_text(encoding="utf-8")
        chk(res.returncode == 0, "the English build runs", (res.stderr or "")[-160:])
        for word in ("The rows behind the picture", "Start", "End", "Days", "Group"):
            chk(word in eblob, f"the English page says {word!r}")
        for word in ("Radene bak bildet", "Dager", "ukemerker", " ikke "):
            chk(word not in eblob, f"and not {word!r}")

    print()
    if FAILURES:
        print(f"{CHECKS - len(FAILURES)} passed, {len(FAILURES)} failed")
        for f in FAILURES:
            print(f"  \u2717 {f}")
        return 1
    print(f"{CHECKS} passed, 0 failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
