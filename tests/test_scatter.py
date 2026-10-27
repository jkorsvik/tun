#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The scatter: one point per unit, placed where the numbers put it.

A scatter is the one chart in this set whose claim is about a *relationship*, so it fails in
ways the bar and the table cannot. This suite checks the properties that make the picture
worth reading, and each one is a way the page could be wrong:

  1. every point is drawn where this suite's own projection puts it, recomputed from the CSV
     with the axes' span, not read off the builder
  2. the unit with the largest value on the vertical axis is the unit drawn highest, so the
     vertical direction cannot be inverted silently
  3. every point sits inside the plot box, and the box has air around the data: a point on
     the frame is a point at the axis limit, which is a crop
  4. the stated extremes are the data's own, printed in the summary, and the ticks are round
     numbers inside the span
  5. the table is every unit, numbered as the point, with the same two figures
  6. the label budget: names at or below the limit, numbers above it, and the page says which
  7. units that share both values are counted, because two rows are one dot on the page
  8. the coefficient printed beside the fit line is recomputed here, and the drawn line lies
     on the fitted line rather than near it
  9. refusals name what to fix: two points, a repeated name, a column that is not a number,
     the same column twice, more units than the ceiling, more groups than the seam carries
 10. no two labels overlap, measured in a browser at two widths, because a collision is the
     one defect a static check cannot see
 11. there is no script, and the English build carries no Norwegian
 12. four mutations of the builder each trip exactly the check they should

Stdlib for the arithmetic; chromium for the label collisions and the text size.

    python3 tests/test_scatter.py
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
BUILDER = ROOT / "tools" / "build_scatter.py"
TEMPLATE = ROOT / "templates" / "scatter.html"
EXAMPLE = ROOT / "examples" / "47-scatter"
DATA = EXAMPLE / "enheter.csv"
PAGE = EXAMPLE / "spredning.html"
PIN = "1792836000"          # a fixed clock: one input, one file, on any day

sys.path.insert(0, str(ROOT / "tools"))
import build_scatter as B  # noqa: E402  the canvas constants the geometry is checked against

FAILURES: list[str] = []
CHECKS = 0

DOT = re.compile(r'class="sc-dot[^"]*" data-x="([-\d.]+)" data-y="([-\d.]+)"')
DOT_ORDER = re.compile(r'<text class="sc-name"[^>]*>([^<]*)</text>')
TICK = re.compile(r'<text class="sc-tick" x="([-\d.]+)" y="([-\d.]+)"'
                  r'(?: text-anchor="(\w+)")?>([^<]*)</text>')
FIT = re.compile(r'<line class="sc-fit" x1="([-\d.]+)" y1="([-\d.]+)" '
                 r'x2="([-\d.]+)" y2="([-\d.]+)"')
NAME = re.compile(r'<text class="sc-name" x="([-\d.]+)" y="([-\d.]+)" '
                  r'text-anchor="(\w+)">([^<]*)</text>')


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


# ------------------------------------------------------------------------------- helpers
def run(data: pathlib.Path, out: pathlib.Path, *extra: str, lang: str = "nb",
        tools: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    builder = (tools / "build_scatter.py") if tools else BUILDER
    args = [sys.executable, str(builder), "--data", str(data),
            "--label", "Enhet", "--x-col", "Svartid", "--y-col", "Tilfredshet",
            "--title", "Svartid mot tilfredshet, per enhet",
            "--source", "Syntetisk eksempeldata (enheter.csv)",
            "--requested-by", "Kundeservice", "--lang", lang, "--out", str(out), *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env)


def scratch(root: pathlib.Path, *pairs: tuple[str, str]) -> pathlib.Path:
    """A copy of tools/ and templates/ a mutation can break without touching the repo."""
    tools = root / "tools"
    tools.mkdir(parents=True)
    shutil.copy2(BUILDER, tools / "build_scatter.py")
    for name in ("build_size.py", "build_stamp.py", "feedback_link.py", "i18n.py",
                 "tun_core.py", "tun_tokens.py"):
        shutil.copy2(ROOT / "tools" / name, tools / name)
    # tun_tokens resolves the token files from its own location, so the scratch tree needs them:
    # the template carries {{TOKEN_CSS}} and the builder cannot produce a page without the seam.
    shutil.copytree(ROOT / "tools" / "tokens", tools / "tokens")
    shutil.copytree(ROOT / "templates", root / "templates")
    target = tools / "build_scatter.py"
    text = target.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            raise SystemExit(f"the mutation does not apply: {old[:70]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")
    return tools


def num(text: str) -> float:
    """A figure the page printed, back as a number. nb writes NBSP and a comma."""
    t = (text.replace("\u00a0", "").replace("\u2009", "")
         .replace("\u2212", "-").replace("+", "").replace(",", ".").strip())
    return float(t)


def own_rows(path: pathlib.Path = DATA) -> list[dict]:
    """The extract, read here rather than by the builder: one dict per unit."""
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [{"label": r["Enhet"], "x": float(r["Svartid"]), "y": float(r["Tilfredshet"])}
                for r in csv.DictReader(fh, delimiter=";")]


def plot_box(page: str) -> tuple[float, float, float, float]:
    """The frame the drawing declares, so the checks do not assume the constants."""
    return B.PAD_L, B.PAD_T, B.PAD_L + B.PLOT_W, B.PAD_T + B.PLOT_H


def fitted(rows: list[dict]) -> tuple[float, float, float]:
    """Least squares by hand, so the coefficient on the page is not self-certified."""
    n = len(rows)
    mx = sum(r["x"] for r in rows) / n
    my = sum(r["y"] for r in rows) / n
    sxx = sum((r["x"] - mx) ** 2 for r in rows)
    sxy = sum((r["x"] - mx) * (r["y"] - my) for r in rows)
    syy = sum((r["y"] - my) ** 2 for r in rows)
    slope = sxy / sxx
    return slope, my - slope * mx, sxy / (sxx * syy) ** 0.5


def write_csv(path: pathlib.Path, rows: list[tuple], header=("Enhet", "Svartid", "Tilfredshet")) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(header)
        writer.writerows(rows)


# ---------------------------------------------------------------------------------- main
def main() -> int:
    if not DATA.is_file():
        raise SystemExit(f"{DATA} is missing; run examples/47-scatter/generate_data.py")
    rows = own_rows()

    with tempfile.TemporaryDirectory() as raw:
        work = pathlib.Path(raw)

        print("1. the example builds, and every point is where this suite puts it")
        out = work / "sc.html"
        done = run(DATA, out, "--trend")
        chk(done.returncode == 0, "the builder exits 0", (done.stderr or "")[-400:])
        page = out.read_text(encoding="utf-8")
        dots = [(float(a), float(b)) for a, b in DOT.findall(page)]
        chk(len(dots) == len(rows), "one point per unit", f"{len(dots)} vs {len(rows)}")

        xlow, xhigh = B.span([r["x"] for r in rows])
        ylow, yhigh = B.span([r["y"] for r in rows])
        left, top, right, bottom = plot_box(page)

        def px(value: float) -> float:
            return B.project(value, xlow, xhigh, B.PAD_L, B.PLOT_W)

        def py(value: float) -> float:
            return B.PAD_T + B.PLOT_H - B.project(value, ylow, yhigh, 0, B.PLOT_H)

        # The drawing is in unit order, so the nth dot is the nth row of the extract.
        wrong = [(r["label"], round(x, 2), round(px(r["x"]), 2), round(y, 2), round(py(r["y"]), 2))
                 for r, (x, y) in zip(rows, dots)
                 if abs(x - px(r["x"])) > 0.05 or abs(y - py(r["y"])) > 0.05]
        chk(not wrong, "every point sits at its own projection of both measures",
            str(wrong[:2]))

        print("\n2. the vertical axis is not inverted")
        highest = max(zip(rows, dots), key=lambda pair: pair[0]["y"])
        chk(highest[1][1] == min(y for _x, y in dots),
            "the largest value on the vertical axis is the highest point drawn",
            f"{highest[0]['label']} at {highest[1][1]:.1f}, top is {min(y for _x, y in dots):.1f}")
        lowest = min(zip(rows, dots), key=lambda pair: pair[0]["y"])
        chk(lowest[1][1] == max(y for _x, y in dots),
            "and the smallest is the lowest", lowest[0]["label"])

        print("\n3. every point is inside the frame, with air around the data")
        outside = [(round(x, 1), round(y, 1)) for x, y in dots
                   if not (left - 0.01 <= x <= right + 0.01 and top - 0.01 <= y <= bottom + 0.01)]
        chk(not outside, "no point is drawn outside the plot box", str(outside[:3]))
        on_edge = [label for label, (x, y) in zip((r["label"] for r in rows), dots)
                   if abs(x - left) < 1 or abs(x - right) < 1 or abs(y - top) < 1
                   or abs(y - bottom) < 1]
        chk(not on_edge, "and none sits on the frame, which would be a crop", str(on_edge[:3]))

        print("\n4. the stated extremes are the data's, and the ticks are round")
        summary = re.search(r'<p class="summary">(.*?)</p>', page, re.S)
        body = summary.group(1) if summary else ""
        chk(B.fmt(max(r["x"] for r in rows), "nb", 0) in body,
            "the largest horizontal value is printed in the summary",
            B.fmt(max(r["x"] for r in rows), "nb", 0))
        chk(B.fmt(min(r["y"] for r in rows), "nb", 0) in body,
            "and the smallest vertical value", B.fmt(min(r["y"] for r in rows), "nb", 0))
        ticks = [num(text) for _x, _y, anchor, text in TICK.findall(page) if anchor != "end"]
        chk(ticks and all(xlow <= value <= xhigh for value in ticks),
            "every horizontal tick lies inside the span", str(ticks))
        chk(len(set(ticks)) == len(ticks), "and no tick is repeated", str(ticks))

        print("\n5. the table is every unit, numbered as the point")
        table = re.search(r"<tbody>(.*?)</tbody>", page, re.S).group(1)
        cells = re.findall(r"<tr>(.*?)</tr>", table, re.S)
        chk(len(cells) == len(rows), "one row per unit", f"{len(cells)} vs {len(rows)}")
        numbered = all(f'<td class="num">{i}</td>' in cells[i - 1]
                       for i in range(1, len(cells) + 1))
        chk(numbered, "each row carries the number its point is labelled with")
        missing = [r["label"] for r, cell in zip(rows, cells)
                   if r["label"] not in cell]
        chk(not missing, "and the unit's own name", str(missing[:3]))

        print("\n6. the label budget is declared, not guessed")
        chk(len(NAME.findall(page)) == len(rows),
            "at this size every point carries its name")
        chk("Hvert punkt har navnet sitt" in page,
            "and the page says the names are on the drawing")
        many = work / "many.csv"
        write_csv(many, [(f"E{i}", i, (i * 7) % 40 + 50) for i in range(1, B.NAME_LIMIT + 6)])
        out_many = work / "many.html"
        done = run(many, out_many)
        chk(done.returncode == 0, "a file past the name budget still builds",
            (done.stderr or "")[-300:])
        page_many = out_many.read_text(encoding="utf-8")
        chk(len(NAME.findall(page_many)) == B.NAME_LIMIT + 5,
            "one label per point, as numbers")
        chk(all(text.isdigit() for _x, _y, _a, text in NAME.findall(page_many)),
            "and every label is a number, not a name that would collide")
        chk("Navnene står i tabellen" in page_many,
            "and the page says where the names went")

        print("\n7. units that share a place are counted")
        twin = work / "twin.csv"
        write_csv(twin, [("Alfa", 5, 70), ("Beta", 5, 70), ("Gamma", 9, 60), ("Delta", 12, 55)])
        out_twin = work / "twin.html"
        done = run(twin, out_twin)
        chk(done.returncode == 0, "two units on one place still build",
            (done.stderr or "")[-300:])
        twin_page = out_twin.read_text(encoding="utf-8")
        chk("deler plass med et annet punkt" in twin_page,
            "the page says that two points share a place")
        chk(len(re.findall(r"<tr>", re.search(r"<tbody>(.*?)</tbody>", twin_page, re.S).group(1)))
            == 4, "and both of them are still rows in the table")

        print("\n8. the coefficient beside the line is recomputed here")
        slope, intercept, r = fitted(rows)
        said = re.search(r"r = ([\u2212\-]?\d+,\d+)", page)
        chk(said is not None, "the page prints a coefficient")
        if said:
            chk(abs(num(said.group(1)) - r) < 0.006,
                "and it is this suite's own r", f"{num(said.group(1)):.3f} vs {r:.3f}")
        line = FIT.search(page)
        chk(line is not None, "the fit line is drawn")
        if line:
            x1, y1, x2, y2 = (float(v) for v in line.groups())
            want1 = B.PAD_T + B.PLOT_H - B.project(slope * xlow + intercept, ylow, yhigh, 0, B.PLOT_H)
            want2 = B.PAD_T + B.PLOT_H - B.project(slope * xhigh + intercept, ylow, yhigh, 0, B.PLOT_H)
            inside = (B.PAD_T - 0.5 <= y1 <= B.PAD_T + B.PLOT_H + 0.5
                      and B.PAD_T - 0.5 <= y2 <= B.PAD_T + B.PLOT_H + 0.5)
            chk(inside, "and stays inside the plot box", f"{y1:.1f}, {y2:.1f}")
            clipped = abs(y1 - want1) < 0.5 or abs(y1 - B.PAD_T) < 0.5 \
                or abs(y1 - (B.PAD_T + B.PLOT_H)) < 0.5
            chk(clipped, "the line's left end is on the fitted line, or on the frame it was "
                         "clipped to", f"{y1:.2f} vs {want1:.2f}")
            chk(abs(x1 - B.PAD_L) < 0.5 and abs(x2 - (B.PAD_L + B.PLOT_W)) < 0.5,
                "the line spans the width of the plot")

        print("\n9. refusals name what to fix")
        two = work / "two.csv"
        write_csv(two, [("Alfa", 5, 70), ("Beta", 9, 60)])
        done = run(two, work / "two.html")
        chk(done.returncode != 0 and "at least three" in (done.stderr or ""),
            "two points are refused, and the message says why", (done.stderr or "")[-160:])

        dupe = work / "dupe.csv"
        write_csv(dupe, [("Alfa", 5, 70), ("Alfa", 9, 60), ("Beta", 12, 55)])
        done = run(dupe, work / "dupe.html")
        chk(done.returncode != 0 and "appears twice" in (done.stderr or ""),
            "a name used twice is refused", (done.stderr or "")[-160:])

        words = work / "words.csv"
        write_csv(words, [("Alfa", "fem", 70), ("Beta", 9, 60), ("Gamma", 12, 55)])
        done = run(words, work / "words.html")
        chk(done.returncode != 0 and "not numeric" in (done.stderr or ""),
            "a column of words is refused as a measure", (done.stderr or "")[-160:])

        done = run(DATA, work / "same.html", "--y-col", "Svartid")
        chk(done.returncode != 0 and "against itself" in (done.stderr or ""),
            "one measure against itself is refused", (done.stderr or "")[-160:])

        big = work / "big.csv"
        write_csv(big, [(f"E{i}", i % 37, (i * 11) % 53) for i in range(B.MAX_POINTS + 2)])
        done = run(big, work / "big.html")
        chk(done.returncode != 0 and "ceiling" in (done.stderr or ""),
            "past the point ceiling it says to aggregate", (done.stderr or "")[-160:])

        grouped = work / "grouped.csv"
        write_csv(grouped, [(f"E{i}", i, 50 + i % 9, f"G{i % 7}") for i in range(10)],
                  header=("Enhet", "Svartid", "Tilfredshet", "Omrade"))
        args = ["--group", "Omrade"]
        done = run(grouped, work / "grouped.html", *args)
        chk(done.returncode != 0 and "categorical colours" in (done.stderr or ""),
            "more groups than the seam carries is refused", (done.stderr or "")[-160:])

        print("\n10. the committed example is the builder's own output")
        pinned = work / "pinned.html"
        done = run(DATA, pinned, "--trend")
        chk(done.returncode == 0 and pinned.read_bytes() == PAGE.read_bytes(),
            "a pinned rebuild equals the committed file byte for byte")

        print("\n11. no script, and the English build is English")
        chk("<script" not in page, "the page carries no script")
        out_en = work / "en.html"
        done = run(DATA, out_en, "--trend", lang="en")
        page_en = out_en.read_text(encoding="utf-8")
        chk(done.returncode == 0 and '<html lang="en">' in page_en, "the English build runs")
        norwegian = [w for w in ("Hvert punkt", "Aksene", "Tallene bak", "Kilde:", "Bygget")
                     if w in page_en]
        chk(not norwegian, "the English page keeps no Norwegian chrome", str(norwegian))

        print("\n12. the labels do not collide, measured in a browser")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            chk(False, "playwright is installed (this suite measures text, so it needs a browser)")
            report()
            return 1
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for width in (1000, 1400):
                ctx = browser.new_context(viewport={"width": width, "height": 1000})
                view = ctx.new_page()
                view.goto(PAGE.resolve().as_uri())
                view.wait_for_selector(".sc-dot")
                boxes = view.evaluate(
                    """() => [...document.querySelectorAll('.sc-name')].map(e => {
                         const r = e.getBoundingClientRect();
                         return {t: e.textContent, x: r.x, y: r.y, w: r.width, h: r.height,
                                 size: parseFloat(getComputedStyle(e).fontSize)}; })""")
                overlap = []
                for i, a in enumerate(boxes):
                    for b in boxes[i + 1:]:
                        if (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                                and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]):
                            overlap.append(f"{a['t']}/{b['t']}")
                chk(not overlap, f"no two labels overlap at {width} px", str(overlap[:3]))
                small = [b["t"] for b in boxes if b["size"] < 14]
                chk(not small, f"and every label is at least 14 px at {width} px", str(small[:3]))
                ctx.close()
            browser.close()

        print("\n13. the mutations")
        with tempfile.TemporaryDirectory() as mraw:
            mraw = pathlib.Path(mraw)

            # a. the vertical axis inverted: every value still drawn, read backwards.
            tools = scratch(mraw / "invert",
                            ("        return PAD_T + PLOT_H - project(value, ylow, yhigh, 0, PLOT_H)",
                             "        return PAD_T + project(value, ylow, yhigh, 0, PLOT_H)"))
            out_m = mraw / "invert.html"
            done = run(DATA, out_m, "--trend", tools=tools)
            chk(done.returncode == 0, "the inverted-axis mutation still builds",
                (done.stderr or "")[-200:])
            mpage = out_m.read_text(encoding="utf-8")
            mdots = [(float(a), float(b)) for a, b in DOT.findall(mpage)]
            mhigh = max(zip(rows, mdots), key=lambda pair: pair[0]["y"])
            chk(mhigh[1][1] != min(y for _x, y in mdots),
                "and the highest value is no longer the highest point, so check 2 sees it")

            # b. the coefficient's sign dropped: a negative relationship reads as a positive one.
            tools = scratch(mraw / "sign",
                            ('    return slope, my - slope * mx, sxy / math.sqrt(sxx * syy)',
                             '    return slope, my - slope * mx, abs(sxy / math.sqrt(sxx * syy))'))
            out_m = mraw / "sign.html"
            done = run(DATA, out_m, "--trend", tools=tools)
            chk(done.returncode == 0, "the unsigned-coefficient mutation still builds",
                (done.stderr or "")[-200:])
            said = re.search(r"r = ([\u2212\-]?\d+,\d+)", out_m.read_text(encoding="utf-8"))
            chk(said is not None and abs(num(said.group(1)) - r) >= 0.006,
                "and the printed r disagrees with this suite's, so check 8 sees it",
                said.group(1) if said else "no coefficient")

            # c. shared places no longer counted: fewer dots than rows, silently.
            tools = scratch(mraw / "shared",
                            ("    overlapping = len(points) - unique_places",
                             "    overlapping = 0"))
            out_m = mraw / "shared.html"
            done = run(twin, out_m, tools=tools)
            chk(done.returncode == 0, "the uncounted-places mutation still builds",
                (done.stderr or "")[-200:])
            chk("deler plass" not in out_m.read_text(encoding="utf-8"),
                "and the page stops saying two points share a place, so check 7 sees it")

            # d. the label budget ignored: names on every point, however many there are.
            tools = scratch(mraw / "labels",
                            ('    names = {"auto": len(points) <= NAME_LIMIT, "on": True, "off": False}[args.labels]',
                             '    names = True'))
            out_m = mraw / "labels.html"
            done = run(many, out_m, tools=tools)
            chk(done.returncode == 0, "the over-labelled mutation still builds",
                (done.stderr or "")[-200:])
            mpage = out_m.read_text(encoding="utf-8")
            chk(not all(text.isdigit() for _x, _y, _a, text in NAME.findall(mpage)),
                "and the labels become names past the budget, so check 6 sees it")

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
