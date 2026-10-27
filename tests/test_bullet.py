#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The bullet chart: a value, its target, and the gap that is the answer.

The shape is a comparison with a threshold, so the checks are about the threshold: that the
target mark is where the target is, that the gap is the difference in the right direction, that
flipping `--direction` flips who is behind, and that the axis does not quietly start below zero
while the page says it starts at zero.

  1. one row per unit, with a bar, a target mark and a name
  2. every bar and every target mark sits on one shared axis, at its own value
  3. the printed gap is the difference, signed, in the unit of the measure
  4. the state word agrees with the gap, and the rows are in the stated order
  5. `--direction down` flips the verdict on the same numbers
  6. the axis starts at zero when every value is positive, and says so
  7. refusals: no target, a column of words, too many rows, a label past the ceiling
  8. the committed example is the builder's own output, byte for byte
  9. no script, and the English build carries no Norwegian
 10. four mutations, each breaking exactly one of the checks above

    python3 tests/test_bullet.py
"""
from __future__ import annotations

import csv
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_bullet.py"
EXAMPLE = ROOT / "examples" / "51-bullet"
DATA = EXAMPLE / "dekning.csv"
PAGE = EXAMPLE / "dekning.html"
NOTE = "styremøtet 12.05.2026"
PIN = "1792836000"

FAILURES: list[str] = []
CHECKS = 0

TRACK = re.compile(r'<rect class="bl-track" x="([-\d.]+)" y="[-\d.]+" width="([-\d.]+)"')
BAR = re.compile(r'<rect class="(bl-bar[^"]*)" data-label="([^"]*)" x="([-\d.]+)" '
                 r'y="[-\d.]+" width="([-\d.]+)"')
TARGET = re.compile(r'<line class="bl-target" data-label="([^"]*)" x1="([-\d.]+)"')
NUM = re.compile(r'<text class="bl-num" x="[-\d.]+" y="[-\d.]+" text-anchor="end">([^<]*)</text>')
NAME = re.compile(r'<text class="bl-name" x="[-\d.]+" y="[-\d.]+" text-anchor="end">([^<]*)</text>')
TICK = re.compile(r'<text class="bl-tick" x="[-\d.]+" y="[-\d.]+" text-anchor="middle">([^<]*)</text>')


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


def run(data: pathlib.Path, out: pathlib.Path, *extra: str, lang: str = "nb",
        direction: str = "up", tools: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    builder = (tools / "build_bullet.py") if tools else BUILDER
    args = [sys.executable, str(builder), "--data", str(data), "--label", "Enhet",
            "--value", "Dekning", "--target", "Maal", "--direction", direction,
            "--target-note", NOTE, "--title", "Dekning mot mål per enhet",
            "--source", "Syntetisk eksempeldata (dekning.csv)",
            "--requested-by", "Fagavdelingen", "--lang", lang, "--out", str(out), *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env)


def scratch(root: pathlib.Path, *pairs: tuple[str, str]) -> pathlib.Path:
    tools = root / "tools"
    tools.mkdir(parents=True)
    shutil.copy2(BUILDER, tools / "build_bullet.py")
    for name in ("build_size.py", "build_stamp.py", "feedback_link.py", "i18n.py",
                 "tun_core.py", "tun_tokens.py"):
        shutil.copy2(ROOT / "tools" / name, tools / name)
    shutil.copytree(ROOT / "tools" / "tokens", tools / "tokens")
    shutil.copytree(ROOT / "templates", root / "templates")
    target = tools / "build_bullet.py"
    text = target.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            raise SystemExit(f"the mutation does not apply: {old[:70]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")
    return tools


def own_rows(path: pathlib.Path = DATA) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [{"label": row["Enhet"], "value": float(row["Dekning"]),
                 "target": float(row["Maal"])} for row in csv.DictReader(fh, delimiter=";")]


def num(text: str) -> float:
    return float(text.replace("\u00a0", "").replace("\u2009", "")
                 .replace("\u2212", "-").replace(",", ".").strip())


def table_rows(page: str) -> list[list[str]]:
    body = re.search(r"<tbody>(.*?)</tbody>", page, re.S).group(1)
    return [[re.sub(r"<[^>]+>", "", cell).strip()
             for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            for row in re.findall(r"<tr>(.*?)</tr>", body, re.S)]


def main() -> int:
    if not DATA.is_file():
        raise SystemExit(f"{DATA} is missing; run examples/51-bullet/generate_data.py")
    rows = own_rows()

    with tempfile.TemporaryDirectory() as raw:
        work = pathlib.Path(raw)
        out = work / "b.html"
        done = run(DATA, out)
        print("1. one row per unit, with a bar, a target mark and a name")
        chk(done.returncode == 0, "the builder exits 0", (done.stderr or "")[-400:])
        page = out.read_text(encoding="utf-8")
        bars = {name: (float(x), float(w)) for _cls, name, x, w in BAR.findall(page)}
        marks = {name: float(x) for name, x in TARGET.findall(page)}
        names = NAME.findall(page)
        chk(sorted(bars) == sorted(r["label"] for r in rows), "a bar per unit",
            f"{sorted(bars)[:3]}")
        chk(sorted(marks) == sorted(bars), "a target mark per unit", f"{sorted(marks)[:3]}")
        chk(len(names) == len(rows), "and a name per row", str(len(names)))

        print("\n2. every bar and mark sits on one shared axis, at its own value")
        tracks = [(float(x), float(w)) for x, w in TRACK.findall(page)]
        chk(len(tracks) == len(rows), "a track per row", str(len(tracks)))
        tick_values = [num(v) for v in TICK.findall(page)]
        tick_x = [float(x) for x in re.findall(r'<text class="bl-tick" x="([-\d.]+)"', page)]
        # The axis read off the ticks on the page itself: value = a + b*x, where a is the
        # INTERCEPT and not the first tick. Getting that wrong made the first run of this suite
        # report a 39-unit error on a correct drawing.
        b = (tick_values[-1] - tick_values[0]) / (tick_x[-1] - tick_x[0])
        a = tick_values[0] - b * tick_x[0]
        chk(all(abs(a + b * x - v) < 0.2 for x, v in zip(tick_x, tick_values)),
            "the printed ticks are evenly spaced on one axis",
            str([round(a + b * x - v, 2) for x, v in zip(tick_x, tick_values)]))
        wrong_mark = []
        for row in rows:
            want = (row["target"] - a) / b
            if abs(marks[row["label"]] - want) > 0.7:
                wrong_mark.append(f"{row['label']}: {marks[row['label']]:.1f} vs {want:.1f}")
        chk(not wrong_mark, "every target mark is at its own target", str(wrong_mark[:3]))
        wrong_bar = []
        for row in rows:
            end = a + b * (bars[row["label"]][0] + bars[row["label"]][1])
            if abs(end - row["value"]) > 0.5:
                wrong_bar.append(f"{row['label']}: bar ends at {end:.1f}, value {row['value']}")
        chk(not wrong_bar, "and every bar ends at its own value", str(wrong_bar[:3]))

        print("\n3. the printed gap is the difference, signed")
        gaps = {name: figures for name, figures in zip(names, NUM.findall(page))}
        bad = []
        for row in rows:
            want = row["value"] - row["target"]
            figures = gaps[row["label"]]
            printed = num(figures.split("\u00b7")[-1])
            if abs(printed - want) > 0.051:
                bad.append(f"{row['label']}: {printed} vs {want}")
        chk(not bad, "every gap is value minus target", str(bad[:3]))
        negatives = [n for n, f in gaps.items() if "\u2212" in f.split("\u00b7")[-1]]
        positives = [n for n, f in gaps.items() if f.split("\u00b7")[-1].strip().startswith("+")]
        chk(negatives and positives, "and both signs appear, so the check is not vacuous",
            f"{len(negatives)}/{len(positives)}")

        print("\n4. the state word agrees with the gap, and the rows are in the stated order")
        table = table_rows(page)
        states = {cells[0]: cells[4] for cells in table}
        behind = {r["label"] for r in rows if r["value"] < r["target"]}
        ahead = {r["label"] for r in rows if r["value"] > r["target"]}
        chk(all(states[n] == "bak målet" for n in behind), "a unit below its target says so",
            str({n: states[n] for n in list(behind)[:3]}))
        chk(all(states[n] == "foran målet" for n in ahead), "and one above says so")
        chk(all(states[n] == "på målet" for n in set(states) - behind - ahead),
            "and one exactly on it says that instead")
        shown = [cells[0] for cells in table]
        want_order = sorted(rows, key=lambda r: (r["value"] - r["target"], r["label"]))
        chk(shown == [r["label"] for r in want_order], "rows run furthest behind first",
            str(shown[:3]))
        by_name = work / "name.html"
        done = run(DATA, by_name, "--order", "name")
        chk(done.returncode == 0
            and [c[0] for c in table_rows(by_name.read_text(encoding="utf-8"))]
            == sorted(r["label"] for r in rows), "--order name sorts by name")

        print("\n5. --direction down flips the verdict on the same numbers")
        down = work / "down.html"
        done = run(DATA, down, direction="down")
        chk(done.returncode == 0, "the same data builds with --direction down",
            (done.stderr or "")[-200:])
        down_states = {c[0]: c[4] for c in table_rows(down.read_text(encoding="utf-8"))}
        flipped = {n for n, state in down_states.items() if state == "bak målet"}
        chk(flipped == ahead,
            "and the units now behind the target are the ones that were ahead", str(flipped))
        chk(flipped != behind, "which is a different set, so the flag is doing work")

        print("\n6. the axis starts at zero when every value is positive")
        chk(min(tick_values) == 0,
            "the lowest tick is zero", str(tick_values))
        chk(all(v >= 0 for v in tick_values), "and no tick is negative", str(tick_values))
        chk("starter på null" in page or "startar på null" in page,
            "the page states the rule it followed")

        print("\n7. refusals name what to fix")
        no_target = work / "notarget.csv"
        # A blank target in a column that is otherwise numeric: the column passes the numeric
        # probe and the ROW is what gets refused, which is the message under test.
        no_target.write_text("Enhet;Dekning;Maal\nAlfa;90;90\nBeta;80;\n", encoding="utf-8")
        done = run(no_target, work / "n.html")
        chk(done.returncode != 0 and "no target" in (done.stderr or ""),
            "a row with no target is refused", (done.stderr or "")[-200:])

        words = work / "words.csv"
        words.write_text("Enhet;Dekning;Maal\nAlfa;høy;90\n", encoding="utf-8")
        done = run(words, work / "w.html")
        chk(done.returncode != 0 and "not numeric" in (done.stderr or ""),
            "a column of words is refused", (done.stderr or "")[-200:])

        many = work / "many.csv"
        lines = ["Enhet;Dekning;Maal"] + [f"E{i};{80 + i % 10};90" for i in range(31)]
        many.write_text("\n".join(lines) + "\n", encoding="utf-8")
        done = run(many, work / "m.html")
        chk(done.returncode != 0 and "ceiling" in (done.stderr or ""),
            "past the row ceiling it says so", (done.stderr or "")[-200:])

        long_label = work / "long.csv"
        long_label.write_text("Enhet;Dekning;Maal\n" + "x" * 40 + ";80;90\n", encoding="utf-8")
        done = run(long_label, work / "l.html")
        chk(done.returncode != 0 and "characters" in (done.stderr or ""),
            "a label past the ceiling is refused rather than truncated",
            (done.stderr or "")[-200:])

        print("\n8. the committed example is the builder's own output")
        pinned = work / "pinned.html"
        done = run(DATA, pinned)
        chk(done.returncode == 0 and pinned.read_bytes() == PAGE.read_bytes(),
            "a pinned rebuild equals the committed file byte for byte")

        print("\n9. no script, and the English build is English")
        chk("<script" not in page, "the page carries no script")
        out_en = work / "en.html"
        done = run(DATA, out_en, lang="en")
        page_en = out_en.read_text(encoding="utf-8")
        chk(done.returncode == 0 and '<html lang="en">' in page_en, "the English build runs")
        norwegian = [w for w in ("bak målet", "foran målet", "på målet", "Kilde:", "Bygget",
                                 "Avvik", "Enhet") if w in page_en]
        chk(not norwegian, "the English page keeps no Norwegian chrome", str(norwegian))

        print("\n10. the names do not collide, measured in a browser")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            chk(False, "playwright is installed (this suite measures text)")
            report()
            return 1
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for width in (1000, 1400):
                ctx = browser.new_context(viewport={"width": width, "height": 1000})
                view = ctx.new_page()
                view.goto(PAGE.resolve().as_uri())
                view.wait_for_selector(".bl-bar")
                measured = view.evaluate(
                    """() => [...document.querySelectorAll('.bl-name, .bl-num')].map(e => {
                         const r = e.getBoundingClientRect();
                         return {t: e.textContent.trim(), x: r.x, y: r.y, w: r.width,
                                 h: r.height, size: parseFloat(getComputedStyle(e).fontSize)}; })""")
                overlap = []
                for i, one in enumerate(measured):
                    for other in measured[i + 1:]:
                        if (one["x"] < other["x"] + other["w"] and other["x"] < one["x"] + one["w"]
                                and one["y"] < other["y"] + other["h"]
                                and other["y"] < one["y"] + one["h"]):
                            overlap.append(f"{one['t']}/{other['t']}")
                chk(not overlap, f"no two labels overlap at {width} px", str(overlap[:3]))
                small = [m["t"] for m in measured if m["size"] < 14]
                chk(not small, f"and every label is at least 14 px at {width} px", str(small[:3]))
                ctx.close()
            browser.close()

        print("\n11. the mutations")
        with tempfile.TemporaryDirectory() as mraw:
            mraw = pathlib.Path(mraw)

            # a. the direction ignored: always "up is better".
            tools = scratch(mraw / "direction",
                            ('    sign = 1.0 if args.direction == "up" else -1.0',
                             '    sign = 1.0'))
            out_m = mraw / "direction.html"
            done = run(DATA, out_m, direction="down", tools=tools)
            chk(done.returncode == 0, "the ignored-direction mutation still builds",
                (done.stderr or "")[-200:])
            mstates = {c[0]: c[4] for c in table_rows(out_m.read_text(encoding="utf-8"))}
            mflip = {n for n, state in mstates.items() if state == "bak målet"}
            chk(mflip == behind and mflip != ahead,
                "and the verdict under --direction down becomes the one from up, so check 5 "
                "sees it", str(mflip))

            # b. the gap printed without its sign.
            tools = scratch(mraw / "sign",
                            ('    sign = "\\u2212" if value < 0 else "+"', '    sign = ""'))
            out_m = mraw / "sign.html"
            done = run(DATA, out_m, tools=tools)
            chk(done.returncode == 0, "the unsigned-gap mutation still builds",
                (done.stderr or "")[-200:])
            mnums = NUM.findall(out_m.read_text(encoding="utf-8"))
            chk(not any("\u2212" in f.split("\u00b7")[-1] for f in mnums),
                "and no gap carries a minus any more, so check 3 sees it")

            # c. the axis padded on both sides, which is the defect this page had.
            tools = scratch(mraw / "pad",
                            ("    low_pad = 0.0 if min(every) >= 0 else span * 0.03",
                             "    low_pad = span * 0.03"))
            out_m = mraw / "pad.html"
            done = run(DATA, out_m, tools=tools)
            chk(done.returncode == 0, "the padded-axis mutation still builds",
                (done.stderr or "")[-200:])
            mtick = [num(v) for v in TICK.findall(out_m.read_text(encoding="utf-8"))]
            chk(min(mtick) < 0,
                "and the lowest tick goes below zero while the page still says it starts at "
                "zero, so check 6 sees it", str(mtick))

            # d. the bar drawn from zero to the value but with the mark at the wrong place.
            tools = scratch(mraw / "mark",
                            ('                   f\'x1="{px(row["target"]):.2f}"',
                             '                   f\'x1="{px(row["value"]):.2f}"'))
            out_m = mraw / "mark.html"
            done = run(DATA, out_m, tools=tools)
            chk(done.returncode == 0, "the misplaced-mark mutation still builds",
                (done.stderr or "")[-200:])
            mmarks = {n: float(x) for n, x in
                      TARGET.findall(out_m.read_text(encoding="utf-8"))}
            moff = [r["label"] for r in rows
                    if r["value"] != r["target"]
                    and abs(mmarks[r["label"]] - marks[r["label"]]) > 0.7]
            chk(bool(moff),
                "and the marks are no longer at the targets, so check 2 sees it", str(moff[:3]))

    report()
    return 1 if FAILURES else 0


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
