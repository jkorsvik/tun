#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The calendar heatmap: when in the week, and when in the year.

The claim of a calendar is its ALIGNMENT, so the checks are about position as much as about
numbers: which row a day sits on, which column, and whether a day with no data can be told from
a day that recorded zero.

  1. one cell per day in the range, and missing days are hatched rather than shaded
  2. every cell sits on the row of its own weekday (measured in a browser)
  3. the columns are weeks that start on Monday, and the first column holds the first day
  4. every cell's band is the band this suite computes from the printed legend edges
  5. a day that recorded zero is the lowest band, and is not a missing day
  6. refusals: a duplicated date, a dd.mm date, a range past the ceiling, a column of words
  7. the committed example is the builder's own output, byte for byte
  8. no script, and the English build carries no Norwegian
  9. the legend shows a shade per band, and the shade for "no data" is not one of them
 10. three mutations, each breaking exactly one of the checks above

    python3 tests/test_calendar.py
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_calendar.py"
EXAMPLE = ROOT / "examples" / "50-calendar"
DATA = EXAMPLE / "hendelser.csv"
PAGE = EXAMPLE / "kalender.html"
CLAMP = "40"
PIN = "1792836000"

FAILURES: list[str] = []
CHECKS = 0

CELL = re.compile(r'<rect class="cl-cell (cal-b(\d+)|cl-none)" data-day="([\d-]+)" '
                  r'x="([-\d.]+)" y="([-\d.]+)"')
LEGEND = re.compile(r'<span class="sw (cal-b\d+|sw-none)" aria-hidden="true"></span>'
                    r'<span class="rg">([^<]*)</span>')


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


def run(data: pathlib.Path, out: pathlib.Path, *extra: str, lang: str = "nb",
        tools: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    builder = (tools / "build_calendar.py") if tools else BUILDER
    args = [sys.executable, str(builder), "--data", str(data), "--date", "Dato",
            "--value", "Antall", "--title", "Hendelser per dag, 2026",
            "--source", "Syntetisk eksempeldata (hendelser.csv)",
            "--requested-by", "Driftsavdelingen", "--lang", lang, "--out", str(out), *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env)


def scratch(root: pathlib.Path, *pairs: tuple[str, str]) -> pathlib.Path:
    tools = root / "tools"
    tools.mkdir(parents=True)
    shutil.copy2(BUILDER, tools / "build_calendar.py")
    for name in ("build_size.py", "build_stamp.py", "feedback_link.py", "i18n.py",
                 "tun_core.py", "tun_tokens.py"):
        shutil.copy2(ROOT / "tools" / name, tools / name)
    shutil.copytree(ROOT / "tools" / "tokens", tools / "tokens")
    shutil.copytree(ROOT / "templates", root / "templates")
    target = tools / "build_calendar.py"
    text = target.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            raise SystemExit(f"the mutation does not apply: {old[:70]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")
    return tools


def own_values(path: pathlib.Path = DATA) -> dict[dt.date, float]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return {dt.date.fromisoformat(row["Dato"]): float(row["Antall"])
                for row in csv.DictReader(fh, delimiter=";")}


def legend_edges(page: str) -> list[tuple[int, float | None, float | None]]:
    """The printed scale, read back: (band, low, high) with high None for the top band."""
    out = []
    for cls, text in LEGEND.findall(page):
        if cls == "sw-none":
            continue
        band = int(cls.split("-b")[1])
        clean = text.replace("\u00a0", "").replace("\u2009", "").replace(",", ".").strip()
        if clean.startswith("\u2265"):
            out.append((band, float(clean[1:]), None))
        else:
            low, high = clean.split("\u2013")
            out.append((band, float(low), float(high)))
    return out


def own_band(value: float, edges: list[tuple[int, float | None, float | None]]) -> int:
    for band, low, high in edges:
        if high is None:
            return band
        if value < high:
            return band
    return edges[-1][0]


def main() -> int:
    if not DATA.is_file():
        raise SystemExit(f"{DATA} is missing; run examples/50-calendar/generate_data.py")
    values = own_values()
    first, last = min(values), max(values)
    days = (last - first).days + 1
    missing = {first + dt.timedelta(days=i) for i in range(days)} - set(values)

    with tempfile.TemporaryDirectory() as raw:
        work = pathlib.Path(raw)
        out = work / "cal.html"
        done = run(DATA, out, "--clamp", CLAMP)
        print("1. one cell per day, and missing days are hatched")
        chk(done.returncode == 0, "the builder exits 0", (done.stderr or "")[-400:])
        page = out.read_text(encoding="utf-8")
        cells = {day: (cls, int(band) if band else None, float(x), float(y))
                 for cls, band, day, x, y in
                 ((c, b, d, x, y) for c, b, d, x, y in CELL.findall(page))}
        chk(len(cells) == days, f"one cell for each of the {days} days", str(len(cells)))
        hatched = {dt.date.fromisoformat(d) for d, (cls, _b, _x, _y) in cells.items()
                   if cls == "cl-none"}
        chk(hatched == missing, "the hatched cells are exactly the days with no row",
            f"{sorted(hatched)[:3]} vs {sorted(missing)[:3]}")
        chk(len(hatched) == 12, "and there are twelve of them, so the check is not vacuous",
            str(len(hatched)))

        print("\n2. every cell sits on the row of its own weekday")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            chk(False, "playwright is installed (this suite measures position)")
            report()
            return 1
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx = browser.new_context(viewport={"width": 1200, "height": 900})
            view = ctx.new_page()
            view.goto(PAGE.resolve().as_uri())
            view.wait_for_selector(".cl-cell")
            measured = view.evaluate(
                """() => ({
                     labels: [...document.querySelectorAll('.cl-wd')].map(e => {
                       const r = e.getBoundingClientRect();
                       return {t: e.textContent, y: r.y + r.height / 2,
                               size: parseFloat(getComputedStyle(e).fontSize)}; }),
                     cells: [...document.querySelectorAll('.cl-cell')].map(e => {
                       const r = e.getBoundingClientRect();
                       return {d: e.dataset.day, x: r.x, y: r.y + r.height / 2}; }) })""")
            rows = {label["y"]: index for index, label in enumerate(measured["labels"])}
            misplaced = []
            for cell in measured["cells"]:
                weekday = dt.date.fromisoformat(cell["d"]).weekday()
                want = measured["labels"][weekday]["y"]
                if abs(cell["y"] - want) > 3:
                    misplaced.append(f"{cell['d']} at {cell['y']:.1f}, weekday {want:.1f}")
            chk(not misplaced,
                "measured in a browser: each cell is on its weekday row", str(misplaced[:3]))
            chk(len(measured["labels"]) == 7, "seven weekday rows", str(len(measured["labels"])))
            small = [label["t"] for label in measured["labels"] if label["size"] < 14]
            chk(not small, "and every weekday label is at least 14 px", str(small))

            print("\n3. the columns are weeks that start on Monday")
            # Columns: distinct x values, ordered. A Monday must open every column.
            column_x = sorted({cell["x"] for cell in measured["cells"]})
            chk(len(column_x) > 50, "the year uses more than fifty columns",
                str(len(column_x)))
            by_column: dict[float, list[str]] = {}
            for cell in measured["cells"]:
                by_column.setdefault(cell["x"], []).append(cell["d"])
            bad_columns = []
            for x, members in by_column.items():
                dates = sorted(dt.date.fromisoformat(d) for d in members)
                monday = min(d for d in dates if d.weekday() == 0) if any(
                    d.weekday() == 0 for d in dates) else None
                if monday is None:
                    continue                       # a short column at the ends
                if any(d.weekday() < monday.weekday() and d < monday for d in dates):
                    bad_columns.append(x)
            chk(not bad_columns, "no column holds a day from the previous week",
                str(bad_columns[:3]))
            first_column = by_column[min(by_column)]
            chk(str(first) in first_column or str(first) in measured_cells_days(measured),
                "the first day is on the page", str(first))
            chk(dt.date.fromisoformat(str(first)).weekday() == 3,
                "2026-01-01 is a Thursday, so the first row used is Thursday", "")
            ctx.close()
            browser.close()

        print("\n4. every cell's band is the band the printed legend gives")
        edges = legend_edges(page)
        chk(len(edges) >= 3, f"the legend prints {len(edges)} bands", str(edges))
        wrong = []
        for day, (cls, band, _x, _y) in cells.items():
            if cls == "cl-none":
                continue
            want = own_band(values[dt.date.fromisoformat(day)], edges)
            if band != want:
                wrong.append(f"{day}: band {band}, wanted {want}")
        chk(not wrong, "and every shaded day is in the band its value belongs to",
            str(wrong[:3]))
        top = edges[-1]
        chk(top[2] is None, "the top band prints a minimum rather than a range", str(top))
        chk(any(values[d] >= top[1] for d in values), "and at least one day sits in it",
            str(top))

        print("\n5. zero is a value, and is not a missing day")
        zero_days = {day for day, value in values.items() if value == 0}
        chk(zero_days, "the example holds days that recorded 0", str(len(zero_days)))
        lowest = edges[0][0]
        zero_bands = {cells[d.isoformat()][1] for d in zero_days}
        chk(zero_bands == {lowest}, "each of them takes the lowest band", str(zero_bands))
        chk(not (zero_days & missing), "and none of them is hatched")

        print("\n6. refusals name what to fix")
        twice = work / "twice.csv"
        twice.write_text("Dato;Antall\n2026-03-01;5\n2026-03-01;7\n", encoding="utf-8")
        done = run(twice, work / "t.html")
        chk(done.returncode != 0 and "appears 2 times" in (done.stderr or ""),
            "a duplicated date is refused by name", (done.stderr or "")[-200:])

        dotted = work / "dotted.csv"
        dotted.write_text("Dato;Antall\n03.04.2026;5\n", encoding="utf-8")
        done = run(dotted, work / "d.html")
        chk(done.returncode != 0 and "not a date" in (done.stderr or ""),
            "a dd.mm date is refused rather than guessed", (done.stderr or "")[-200:])

        words = work / "words.csv"
        words.write_text("Dato;Antall\n2026-03-01;noe\n", encoding="utf-8")
        done = run(words, work / "w.html")
        chk(done.returncode != 0 and "not numeric" in (done.stderr or ""),
            "a column of words is refused", (done.stderr or "")[-200:])

        long_span = work / "long.csv"
        long_span.write_text("Dato;Antall\n2024-01-01;1\n2026-12-31;2\n", encoding="utf-8")
        done = run(long_span, work / "l.html")
        chk(done.returncode != 0 and "past the" in (done.stderr or ""),
            "a range past the day ceiling is refused", (done.stderr or "")[-200:])

        print("\n7. the committed example is the builder's own output")
        pinned = work / "pinned.html"
        done = run(DATA, pinned, "--clamp", CLAMP)
        chk(done.returncode == 0 and pinned.read_bytes() == PAGE.read_bytes(),
            "a pinned rebuild equals the committed file byte for byte")

        print("\n8. no script, and the English build is English")
        chk("<script" not in page, "the page carries no script")
        out_en = work / "en.html"
        done = run(DATA, out_en, "--clamp", CLAMP, lang="en")
        page_en = out_en.read_text(encoding="utf-8")
        chk(done.returncode == 0 and '<html lang="en">' in page_en, "the English build runs")
        norwegian = [w for w in ("Ukedag", "ingen data", "Skalaen", "Kilde:", "Bygget",
                                 "Gjennomsnitt", "Høyeste") if w in page_en]
        chk(not norwegian, "the English page keeps no Norwegian chrome", str(norwegian))

        print("\n9. the legend shows one shade per band, and a hatch for no data")
        swatches = [cls for cls, _text in LEGEND.findall(page)]
        chk(swatches[-1] == "sw-none", "the hatch is listed last and named", str(swatches[-1]))
        chk(len(set(swatches[:-1])) == len(swatches) - 1,
            "every band has its own swatch class", str(swatches))
        fills = re.findall(r"\.cal-b(\d+)\{fill:(#[0-9a-f]{6})\}", page)
        light = {int(band): fill for band, fill in fills}
        chk(len(set(light.values())) == len(light),
            "and every band has its own colour in the light theme", str(light))

        print("\n10. the mutations")
        with tempfile.TemporaryDirectory() as mraw:
            mraw = pathlib.Path(mraw)

            # a. a missing day drawn as the lowest band instead of a hatch.
            tools = scratch(mraw / "missing",
                            ('            out.append(f\'<rect class="cl-cell cl-none" '
                             'data-day="{day.isoformat()}" \'',
                             '            out.append(f\'<rect class="cl-cell cal-b0" '
                             'data-day="{day.isoformat()}" \''))
            out_m = mraw / "missing.html"
            done = run(DATA, out_m, "--clamp", CLAMP, tools=tools)
            chk(done.returncode == 0, "the hatched-to-shaded mutation still builds",
                (done.stderr or "")[-200:])
            mpage = out_m.read_text(encoding="utf-8")
            mhatched = [d for c, _b, d, _x, _y in CELL.findall(mpage) if c == "cl-none"]
            chk(not mhatched,
                "and no day is hatched any more, so check 1 sees it", str(len(mhatched)))

            # b. the week starting on Sunday: every cell moves one row up.
            tools = scratch(mraw / "sunday",
                            ("        row = day.weekday()", "        row = (day.weekday() + 6) % 7"))
            out_m = mraw / "sunday.html"
            done = run(DATA, out_m, "--clamp", CLAMP, tools=tools)
            chk(done.returncode == 0, "the Sunday-week mutation still builds",
                (done.stderr or "")[-200:])
            mpage = out_m.read_text(encoding="utf-8")
            mcells = {d: float(y) for _c, _b, d, _x, y in CELL.findall(mpage)}
            shifted = sum(1 for d, y in mcells.items()
                          if abs(y - cells[d][3]) > 1)
            chk(shifted > 0,
                "and the cells no longer sit on the rows they did, so check 2 sees it",
                str(shifted))

            # c. one shade for everything: the bands collapsed.
            tools = scratch(mraw / "oneband",
                            ("            band = bands[band_of(value, edges)]",
                             "            band = bands[0]"))
            out_m = mraw / "oneband.html"
            done = run(DATA, out_m, "--clamp", CLAMP, tools=tools)
            chk(done.returncode == 0, "the single-shade mutation still builds",
                (done.stderr or "")[-200:])
            mpage = out_m.read_text(encoding="utf-8")
            mbands = {b for _c, b, _d, _x, _y in CELL.findall(mpage) if b}
            chk(mbands == {"0"},
                "and every shaded day is in band 0, so check 4 sees it", str(mbands))

    report()
    return 1 if FAILURES else 0


def measured_cells_days(measured: dict) -> set[str]:
    return {cell["d"] for cell in measured["cells"]}


def report() -> None:
    print()
    if FAILURES:
        print(f"{CHECKS - len(FAILURES)} passed, {len(FAILURES)} failed")
        for name in FAILURES:
            print(f"  - {name}")
    else:
        print(f"{CHECKS} checks passed")


if __name__ == "__main__":
    raise SystemExit(main())
