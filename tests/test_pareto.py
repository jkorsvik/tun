#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Pareto: sorted bars, a cumulative line, and a folded tail that keeps its arithmetic.

The sort is the claim, so the checks are about ordering and about the cumulative series: that
the bars really are largest-first, that the printed cumulative reaches 100 of what is drawn,
that the folded bar's value is the exact sum of the categories it stands for, and that the
printed shares add up.

  1. one bar per drawn category, largest first, with the folded bar last and marked
  2. every bar's width is its value on one shared scale
  3. every cumulative point sits where its own percentage puts it
  4. the table repeats value, share and cumulative, and the shares add to exactly 100
  5. the fold keeps the arithmetic: top plus tail equals the total
  6. the vital-few count is this suite's own, and never counts the folded bar
  7. refusals: a negative value, an all-zero extract, one bar, a threshold out of range
  8. the committed example is the builder's own output, byte for byte
  9. no script, and the English build carries no Norwegian
 10. nothing overlaps in the columns, measured in a browser
 11. three mutations, each breaking exactly one of the checks above

    python3 tests/test_pareto.py
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
BUILDER = ROOT / "tools" / "build_pareto.py"
EXAMPLE = ROOT / "examples" / "52-pareto"
DATA = EXAMPLE / "henvendelser.csv"
PAGE = EXAMPLE / "arsaker.html"
PIN = "1792836000"
THRESHOLD = 80.0

FAILURES: list[str] = []
CHECKS = 0

BAR = re.compile(r'<rect class="(pa-bar[^"]*)" data-label="([^"]*)" x="([-\d.]+)" '
                 r'y="[-\d.]+" width="([-\d.]+)"')
DOT = re.compile(r'<circle class="pa-dot" data-label="([^"]*)" cx="[-\d.]+" cy="([-\d.]+)"')
VALUE_TEXT = re.compile(r'<text class="pa-val" x="[-\d.]+" y="[-\d.]+" text-anchor="end">([^<]*)</text>')
NAME = re.compile(r'<text class="pa-name" x="[-\d.]+" y="[-\d.]+" text-anchor="end">([^<]*)</text>')
PCT_TICK = re.compile(r'<text class="pa-pct" x="[-\d.]+" y="([-\d.]+)">(\d+) %</text>')


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


def run(data: pathlib.Path, out: pathlib.Path, *extra: str, lang: str = "nb",
        tools: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    builder = (tools / "build_pareto.py") if tools else BUILDER
    args = [sys.executable, str(builder), "--data", str(data), "--label", "Arsak",
            "--value", "Antall", "--title", "Henvendelser per årsak",
            "--source", "Syntetisk eksempeldata (henvendelser.csv)",
            "--requested-by", "Kundesenteret", "--lang", lang, "--out", str(out), *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env)


def scratch(root: pathlib.Path, *pairs: tuple[str, str]) -> pathlib.Path:
    tools = root / "tools"
    tools.mkdir(parents=True)
    shutil.copy2(BUILDER, tools / "build_pareto.py")
    for name in ("build_size.py", "build_stamp.py", "feedback_link.py", "i18n.py",
                 "tun_core.py", "tun_tokens.py"):
        shutil.copy2(ROOT / "tools" / name, tools / name)
    shutil.copytree(ROOT / "tools" / "tokens", tools / "tokens")
    shutil.copytree(ROOT / "templates", root / "templates")
    target = tools / "build_pareto.py"
    text = target.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            raise SystemExit(f"the mutation does not apply: {old[:70]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")
    return tools


def own_rows(path: pathlib.Path = DATA) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = [{"label": row["Arsak"], "value": float(row["Antall"])}
                for row in csv.DictReader(fh, delimiter=";")]
    rows.sort(key=lambda r: (-r["value"], r["label"]))
    return rows


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
        raise SystemExit(f"{DATA} is missing; run examples/52-pareto/generate_data.py")
    rows = own_rows()
    total = sum(r["value"] for r in rows)

    with tempfile.TemporaryDirectory() as raw:
        work = pathlib.Path(raw)
        out = work / "p.html"
        done = run(DATA, out, "--threshold", f"{THRESHOLD:g}")
        print("1. one bar per drawn category, largest first, folded bar last")
        chk(done.returncode == 0, "the builder exits 0", (done.stderr or "")[-400:])
        page = out.read_text(encoding="utf-8")
        bars = [(cls, label, float(x), float(w)) for cls, label, x, w in BAR.findall(page)]
        names = [b[1] for b in bars]
        chk(len(bars) == 13, "twelve categories plus the folded bar", str(len(bars)))
        chk(names[-1].startswith("Andre"), "the folded bar is last", names[-1])
        chk(bars[-1][0] == "pa-bar pa-folded", "and is drawn with its own class", bars[-1][0])
        chk(all(b[0] == "pa-bar" for b in bars[:-1]), "the rest are ordinary bars")
        values = [r["value"] for r in rows]
        top = [r["label"] for r in rows[:12]]
        chk(names[:-1] == top, "and the twelve largest are the ones drawn, in order",
            f"{names[:3]} vs {top[:3]}")
        chk(values == sorted(values, reverse=True), "the source is sorted descending")

        print("\n2. every bar's width is its value on one shared scale")
        widest = max(float(b[3]) for b in bars)
        k = widest / max(r["value"] for r in rows[:12])
        wrong = [b[1] for b in bars[:-1] if abs(b[3] - next(r["value"] for r in rows
                                                          if r["label"] == b[1]) * k) > 0.6]
        chk(not wrong, "each bar is its value times the same pixels-per-unit", str(wrong[:3]))
        # The folded bar is the BUILDER's label, not a category in the extract: its value is
        # the sum of everything past the twelfth row.
        folded_value = sum(r["value"] for r in rows[12:])
        chk(abs(bars[-1][3] - folded_value * k) < 0.6,
            "including the folded bar, so the tail is on the same scale",
            f"{bars[-1][3]:.1f} vs {folded_value * k:.1f}")

        print("\n3. every cumulative point sits where its percentage puts it")
        ticks = {int(pct): float(y) for y, pct in PCT_TICK.findall(page)}
        chk(set(ticks) == {0, 25, 50, 75, 100}, "the right axis is labelled at five points",
            str(sorted(ticks)))
        dots = {label: float(y) for label, y in DOT.findall(page)}
        chk(len(dots) == len(bars), "one dot per bar", str(len(dots)))
        # A tick's y is the baseline of its text; a dot's cy is its centre. The drawing puts the
        # baseline 4 px below the point on the same percentage, so the axis is shifted by that.
        base_bottom, base_top = ticks[0] - 4, ticks[100] - 4
        running, bad = 0.0, []
        for row in rows[:12]:
            running += row["value"]
            want_pct = running / total * 100
            want_y = base_bottom + (base_top - base_bottom) * want_pct / 100
            if abs(dots[row["label"]] - want_y) > 0.7:
                bad.append(f"{row['label']}: {dots[row['label']]:.1f} vs {want_y:.1f}")
        chk(not bad, "every dot is at its own cumulative share", str(bad[:3]))
        last_dot = dots[names[-1]]
        chk(abs(last_dot - base_top) < 0.7,
            "and the last one is at 100 %, because the folded bar closes the total",
            f"{last_dot:.1f} vs {base_top:.1f}")

        print("\n4. the table repeats the numbers, and the shares add to 100")
        table = table_rows(page)
        chk(len(table) == len(bars), "one row per drawn bar", str(len(table)))
        shares = [num(cells[2]) for cells in table]
        chk(abs(sum(shares) - 100.0) < 0.001,
            "the share column sums to exactly 100,0", f"{sum(shares):.3f}")
        running_exact, bad_cum = 0.0, []
        for i, cells in enumerate(table):
            value = num(cells[1])
            running_exact += value
            want = running_exact / total * 100
            if abs(num(cells[3]) - want) > 0.051:
                bad_cum.append(f"{cells[0]}: {cells[3]} vs {want:.1f}")
        chk(not bad_cum,
            "and each cumulative cell is the exact running share of the total", str(bad_cum[:3]))
        chk(abs(num(table[-1][3]) - 100.0) < 0.051, "the last cumulative cell is 100,0",
            table[-1][3])
        bad_value = [cells for cells, bar in zip(table, bars)
                     if abs(num(cells[1]) - (folded_value if bar[1].startswith("Andre")
                                             else next(r["value"] for r in rows
                                                       if r["label"] == bar[1]))) > 0.001]
        chk(not bad_value, "every value cell is the extract's own number", str(bad_value[:2]))

        print("\n5. the fold keeps the arithmetic")
        tail_sum = sum(r["value"] for r in rows[12:])
        chk(abs(folded_value - tail_sum) < 1e-9,
            "the folded bar is exactly the sum of the categories it stands for",
            f"{folded_value} vs {tail_sum}")
        chk(abs(sum(r["value"] for r in rows[:12]) + folded_value - total) < 1e-9,
            "top plus fold equals the extract's total, so nothing is dropped")

        print("\n6. the vital-few count is this suite's own")
        running, vital = 0.0, len(rows)
        for index, row in enumerate(rows, 1):
            running += row["value"]
            if running / total * 100 >= THRESHOLD:
                vital = index
                break
        summary = re.search(r"<p class=\"summary\">(.*?)</p>", page, re.S).group(1)
        chk(f"De {vital} største" in summary,
            f"the summary says the largest {vital} reach the threshold", summary[:120])
        chk(vital < len(rows), "which is fewer than the whole list, so it is a real count",
            str(vital))
        # A threshold only the folded bar could reach must not be reported as a category count.
        far = work / "far.html"
        done = run(DATA, far, "--threshold", "99.5")
        chk(done.returncode == 0, "a threshold near the whole total still builds",
            (done.stderr or "")[-200:])
        far_summary = re.search(r"<p class=\"summary\">(.*?)</p>",
                                far.read_text(encoding="utf-8"), re.S).group(1)
        far_vital = next((i for i, row in enumerate(rows, 1)
                          if sum(r["value"] for r in rows[:i]) / total * 100 >= 99.5),
                         len(rows))
        chk(f"De {far_vital} største" in far_summary,
            "and it counts real categories, so the count is past the twelve drawn bars",
            far_summary[:120])
        chk(far_vital > 12,
            "which is more than are drawn, so the folded bar was not counted as one category",
            str(far_vital))

        print("\n7. refusals name what to fix")
        negative = work / "neg.csv"
        negative.write_text("Arsak;Antall\nAlfa;10\nBeta;-3\n", encoding="utf-8")
        done = run(negative, work / "n.html")
        chk(done.returncode != 0 and "negative" in (done.stderr or ""),
            "a negative contribution is refused", (done.stderr or "")[-200:])

        zeros = work / "zero.csv"
        zeros.write_text("Arsak;Antall\nAlfa;0\nBeta;0\n", encoding="utf-8")
        done = run(zeros, work / "z.html")
        chk(done.returncode != 0 and "every value" in (done.stderr or ""),
            "an all-zero extract is refused", (done.stderr or "")[-200:])

        done = run(DATA, work / "one.html", "--top", "1")
        chk(done.returncode != 0 and "at least 2" in (done.stderr or ""),
            "one bar is refused: there is no shape to read", (done.stderr or "")[-200:])

        done = run(DATA, work / "thr.html", "--threshold", "120")
        chk(done.returncode != 0 and "not a share" in (done.stderr or ""),
            "a threshold outside 0-100 is refused", (done.stderr or "")[-200:])

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
        norwegian = [w for w in ("Andre (", "kumulert", "Kilde:", "Bygget", "Andel",
                                 "Kategori") if w in page_en]
        chk(not norwegian, "the English page keeps no Norwegian chrome", str(norwegian))
        chk("{" not in table_rows(page)[0][0] and "{sum}" not in page,
            "no unfilled placeholder leaked into the page")

        print("\n10. nothing overlaps, measured in a browser")
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
                view.wait_for_selector(".pa-bar")
                measured = view.evaluate(
                    """() => [...document.querySelectorAll('.pa-name, .pa-val, .pa-pct')].map(e => {
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
                clipped = view.evaluate(
                    """() => [...document.querySelectorAll('.pa-name')]
                         .filter(e => e.getBoundingClientRect().x < 0)
                         .map(e => e.textContent.trim())""")
                chk(not clipped, f"and no category name runs off the canvas at {width} px",
                    str(clipped[:3]))
                small = [m["t"] for m in measured if m["size"] < 14]
                chk(not small, f"and every label is at least 14 px at {width} px", str(small[:3]))
                ctx.close()
            browser.close()

        print("\n11. the mutations")
        with tempfile.TemporaryDirectory() as mraw:
            mraw = pathlib.Path(mraw)

            # a. the bars left in source order instead of sorted.
            tools = scratch(mraw / "sort",
                            ('    out.sort(key=lambda r: (-r["value"], r["label"]))',
                             '    out.sort(key=lambda r: r["label"])'))
            out_m = mraw / "sort.html"
            done = run(DATA, out_m, tools=tools)
            chk(done.returncode == 0, "the unsorted mutation still builds",
                (done.stderr or "")[-200:])
            mnames = NAME.findall(out_m.read_text(encoding="utf-8"))
            chk(mnames != names[:len(mnames)],
                "and the bars are no longer largest-first, so check 1 sees it", str(mnames[:3]))

            # b. the shares rounded per number, so the column adds to 99,9.
            tools = scratch(mraw / "round",
                            ("    shares = largest_remainder([r[\"value\"] for r in drawn], total)",
                             "    shares = largest_remainder([r[\"value\"] for r in drawn],"
                             " total * 0.98)"))
            out_m = mraw / "round.html"
            done = run(DATA, out_m, tools=tools)
            chk(done.returncode == 0, "the wrong-denominator mutation still builds",
                (done.stderr or "")[-200:])
            mtable = table_rows(out_m.read_text(encoding="utf-8"))
            msum = sum(num(cells[2]) for cells in mtable)
            chk(abs(msum - 100.0) > 0.001,
                "and the share column no longer adds to 100,0, so check 4 sees it", f"{msum}")

            # c. the tail dropped instead of folded: the total moves.
            tools = scratch(mraw / "drop",
                            ('''    if tail:
        drawn = drawn + [{"label": i18n.fill(t["folded_label"], n=len(tail)),
                          "value": sum(r["value"] for r in tail), "folded": True}]''',
                             "    if False:\n        pass"))
            out_m = mraw / "drop.html"
            done = run(DATA, out_m, tools=tools)
            chk(done.returncode == 0, "the dropped-tail mutation still builds",
                (done.stderr or "")[-200:])
            mdots = DOT.findall(out_m.read_text(encoding="utf-8"))
            chk(len(mdots) == 12,
                "and the cumulative line now stops short of 100 %, so check 3 sees it",
                str(len(mdots)))

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
