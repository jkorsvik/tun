#!/usr/bin/env python3
"""The box plot: five numbers per group, and the tail the box cannot hide.

A box plot is the one shape here whose arithmetic is a *convention*: quartiles, whiskers and
outliers are all defined by a rule, and two tools that pick different rules draw different
pictures from the same rows. So this suite recomputes every number its own way and compares,
rather than reading the builder's own results back.

  1. every group is drawn once, and its box spans this suite's own quartiles
  2. the median line is at the median, and it is a line rather than a shade
  3. the whisker is Tukey's: the furthest observation within 1.5 IQR, and every observation
     beyond it is drawn as a dot, so min-and-max whiskers cannot pass
  4. the row order is the rule the page says it is, and the two rules differ on this example
  5. the table repeats all five numbers and the outlier count for every group
  6. refusals name what to fix: a group with two observations, more groups than the ceiling,
     a column that is not a number
  7. the committed example is the builder's own output, byte for byte
  8. there is no script, and the English build carries no Norwegian
  9. the row names do not overlap, and every one is at least 14 px, measured in a browser
 10. three mutations each trip exactly the check they should

Stdlib for the arithmetic; chromium for the text measurement.

    python3 tests/test_boxplot.py
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
BUILDER = ROOT / "tools" / "build_boxplot.py"
EXAMPLE = ROOT / "examples" / "48-boxplot"
DATA = EXAMPLE / "saksbehandlingstid.csv"
PAGE = EXAMPLE / "boksplott.html"
PIN = "1792836000"

FAILURES: list[str] = []
CHECKS = 0

BOX = re.compile(r'<rect class="bx-box" data-group="([^"]*)" x="([-\d.]+)" y="([-\d.]+)" '
                 r'width="([-\d.]+)" height="([-\d.]+)"')
MEDIAN = re.compile(r'<line class="bx-median" x1="([-\d.]+)"')
CAP = re.compile(r'<line class="bx-cap" x1="([-\d.]+)"')
OUTLIER = re.compile(r'<circle class="bx-outlier" data-group="([^"]*)" cx="([-\d.]+)"')
NAME = re.compile(r'<text class="bx-name" x="[-\d.]+" y="[-\d.]+" text-anchor="end">([^<]*)</text>')


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


# ------------------------------------------------------------------------------- helpers
def run(data: pathlib.Path, out: pathlib.Path, *extra: str, lang: str = "nb",
        tools: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    builder = (tools / "build_boxplot.py") if tools else BUILDER
    args = [sys.executable, str(builder), "--data", str(data), "--value", "Dager",
            "--group", "Enhet", "--title", "Saksbehandlingstid per enhet",
            "--source", "Syntetisk eksempeldata (saksbehandlingstid.csv)",
            "--requested-by", "Fagavdelingen", "--lang", lang, "--out", str(out), *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env)


def scratch(root: pathlib.Path, *pairs: tuple[str, str]) -> pathlib.Path:
    tools = root / "tools"
    tools.mkdir(parents=True)
    shutil.copy2(BUILDER, tools / "build_boxplot.py")
    for name in ("build_size.py", "build_stamp.py", "feedback_link.py", "i18n.py",
                 "tun_core.py", "tun_tokens.py"):
        shutil.copy2(ROOT / "tools" / name, tools / name)
    shutil.copytree(ROOT / "tools" / "tokens", tools / "tokens")
    shutil.copytree(ROOT / "templates", root / "templates")
    target = tools / "build_boxplot.py"
    text = target.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            raise SystemExit(f"the mutation does not apply: {old[:70]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")
    return tools


def own_values(path: pathlib.Path = DATA) -> dict[str, list[float]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        groups: dict[str, list[float]] = {}
        for row in csv.DictReader(fh, delimiter=";"):
            groups.setdefault(row["Enhet"], []).append(float(row["Dager"]))
    return groups


def own_quantile(ordered: list[float], p: float) -> float:
    """Written out again, from the definition, so the builder is not marking its own work."""
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * p
    lo, hi = int(pos // 1), int(-(-pos // 1))
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (pos - lo) * (ordered[hi] - ordered[lo])


def own_box(values: list[float]) -> dict:
    ordered = sorted(values)
    q1, mid, q3 = (own_quantile(ordered, p) for p in (0.25, 0.5, 0.75))
    iqr = q3 - q1
    inside = [v for v in ordered if q1 - 1.5 * iqr <= v <= q3 + 1.5 * iqr]
    return {"n": len(ordered), "q1": q1, "median": mid, "q3": q3,
            "low": inside[0], "high": inside[-1],
            "outliers": [v for v in ordered if v < q1 - 1.5 * iqr or v > q3 + 1.5 * iqr]}


def num(text: str) -> float:
    return float(text.replace("\u00a0", "").replace("\u2009", "")
                 .replace("\u2212", "-").replace(",", ".").strip())


def write_csv(path: pathlib.Path, rows: list[tuple[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["Enhet", "Dager"])
        writer.writerows(rows)


def table_rows(page: str) -> list[list[str]]:
    body = re.search(r"<tbody>(.*?)</tbody>", page, re.S).group(1)
    return [[re.sub(r"<[^>]+>", "", cell) for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            for row in re.findall(r"<tr>(.*?)</tr>", body, re.S)]


# ---------------------------------------------------------------------------------- main
def main() -> int:
    if not DATA.is_file():
        raise SystemExit(f"{DATA} is missing; run examples/48-boxplot/generate_data.py")
    groups = own_values(DATA)
    boxes = {name: own_box(values) for name, values in groups.items()}

    with tempfile.TemporaryDirectory() as raw:
        work = pathlib.Path(raw)
        out = work / "bx.html"
        done = run(DATA, out)
        print("1. the example builds, and every box spans this suite's own quartiles")
        chk(done.returncode == 0, "the builder exits 0", (done.stderr or "")[-400:])
        page = out.read_text(encoding="utf-8")
        drawn = {name: (float(x), float(w)) for name, x, _y, w, _h in BOX.findall(page)}
        chk(sorted(drawn) == sorted(groups), "one box per group",
            f"{sorted(drawn)} vs {sorted(groups)}")

        # The projection is linear, so the box width predicts the quartile distance exactly.
        widths = {name: drawn[name][1] for name in drawn}
        wide = {name: boxes[name]["q3"] - boxes[name]["q1"] for name in boxes}
        scale = [widths[n] / wide[n] for n in widths if wide[n] > 0]
        chk(scale and max(scale) - min(scale) < 0.01,
            "every box's width is the same multiple of its own quartile distance",
            f"{min(scale):.3f} .. {max(scale):.3f}")
        k = sum(scale) / len(scale)
        wrong = [name for name in drawn
                 if abs(widths[name] - wide[name] * k) > 0.6]
        chk(not wrong, "so each box is as wide as its own quartiles", str(wrong[:3]))
        starts = [drawn[name][0] - boxes[name]["q1"] * k for name in drawn]
        chk(max(starts) - min(starts) < 0.6,
            "and its left edge is the first quartile on the same axis",
            f"{min(starts):.1f} .. {max(starts):.1f}")

        print("\n2. the median is a line, at the median")
        medians = [float(v) for v in MEDIAN.findall(page)]
        chk(len(medians) == len(groups), "one median mark per group", str(len(medians)))
        # x(value) = px(q1) + (value - q1) * k: the left edge of a box is its q1, so a
        # position is measured from that edge and not from zero.
        want = sorted(drawn[name][0] + (boxes[name]["median"] - boxes[name]["q1"]) * k
                      for name in drawn)
        chk(max(abs(a - b) for a, b in zip(sorted(medians), want)) < 0.6,
            "and each mark sits at that group's median", str(medians[:3]))

        print("\n3. the whiskers are Tukey's, and the tail is drawn")
        caps = [float(v) for v in CAP.findall(page)]
        chk(len(caps) == 2 * len(groups), "two caps per group", str(len(caps)))
        want_caps = sorted([drawn[n][0] + (boxes[n]["low"] - boxes[n]["q1"]) * k for n in drawn]
                           + [drawn[n][0] + (boxes[n]["high"] - boxes[n]["q1"]) * k
                              for n in drawn])
        chk(max(abs(a - b) for a, b in zip(sorted(caps), want_caps)) < 0.6,
            "and they sit at the furthest observation inside 1.5 IQR",
            f"{caps[:2]} vs {want_caps[:2]}")
        dotted = [float(x) for _g, x in OUTLIER.findall(page)]
        total_outliers = sum(len(boxes[n]["outliers"]) for n in boxes)
        chk(len(dotted) == total_outliers,
            "every observation beyond the fences is drawn as a dot",
            f"{len(dotted)} vs {total_outliers}")
        per_group = {}
        for name, _x in OUTLIER.findall(page):
            per_group[name] = per_group.get(name, 0) + 1
        chk(all(per_group.get(n, 0) == len(boxes[n]["outliers"]) for n in boxes),
            "and the dots belong to the right group",
            str({n: per_group.get(n, 0) for n in boxes if per_group.get(n, 0) != len(boxes[n]["outliers"])}))
        chk("minste og største verdi" in page,
            "the page names the alternative it did not use, so the rule is not a secret")

        print("\n4. the row order is the rule the page states")
        shown = NAME.findall(page)
        chk(shown == sorted(groups, key=lambda n: (boxes[n]["median"], n)),
            "by median by default", str(shown[:3]))
        chk("sortert etter median" in page, "and the page says so")
        by_name = work / "name.html"
        done = run(DATA, by_name, "--order", "name")
        chk(done.returncode == 0, "--order name builds", (done.stderr or "")[-200:])
        named = NAME.findall(by_name.read_text(encoding="utf-8"))
        chk(named == sorted(groups), "and sorts by the group's own name", str(named[:3]))
        chk(named != shown, "the two rules give different orders on this example, which is why "
                            "the page has to state which one it used")

        print("\n5. the table repeats all five numbers and the tail count")
        rows = table_rows(page)
        chk(len(rows) == len(groups), "one row per group", str(len(rows)))
        bad = []
        for row, name in zip(rows, shown):
            box = boxes[name]
            want_row = [name, str(box["n"]), box["low"], box["q1"], box["median"], box["q3"],
                        box["high"], len(box["outliers"])]
            got_num = [row[0], row[1]] + [num(c) for c in row[2:7]] + [row[7]]
            for got, want_value in zip(got_num, want_row):
                if isinstance(want_value, float):
                    if abs(float(got) - want_value) > 0.005:
                        bad.append(f"{name}: {got} vs {want_value}")
                elif str(got) != str(want_value):
                    bad.append(f"{name}: {got} vs {want_value}")
        chk(not bad, "and every cell is this suite's own number", str(bad[:3]))

        print("\n6. refusals name what to fix")
        thin = work / "thin.csv"
        write_csv(thin, [("Alfa", 5), ("Alfa", 6), ("Beta", 7), ("Beta", 8), ("Beta", 9),
                         ("Gamma", 4), ("Gamma", 5), ("Gamma", 6)])
        done = run(thin, work / "thin.html")
        chk(done.returncode != 0 and "fewer than 3" in (done.stderr or ""),
            "a group with two observations is refused by name", (done.stderr or "")[-200:])

        many = work / "many.csv"
        write_csv(many, [(f"G{i // 4}", i % 9 + 1) for i in range(4 * 30)])
        done = run(many, work / "many.html")
        chk(done.returncode != 0 and "ceiling" in (done.stderr or ""),
            "past the row ceiling it names the distribution page instead",
            (done.stderr or "")[-200:])

        words = work / "words.csv"
        write_csv(words, [(f"G{i}", "x") for i in range(9)])
        done = run(words, work / "words.html")
        chk(done.returncode != 0 and "not numeric" in (done.stderr or ""),
            "a value column of words is refused", (done.stderr or "")[-200:])

        print("\n7. the committed example is the builder's own output")
        pinned = work / "pinned.html"
        done = run(DATA, pinned)
        chk(done.returncode == 0 and pinned.read_bytes() == PAGE.read_bytes(),
            "a pinned rebuild equals the committed file byte for byte")

        print("\n8. no script, and the English build is English")
        chk("<script" not in page, "the page carries no script")
        out_en = work / "en.html"
        done = run(DATA, out_en, lang="en")
        page_en = out_en.read_text(encoding="utf-8")
        chk(done.returncode == 0 and '<html lang="en">' in page_en, "the English build runs")
        norwegian = [w for w in ("En boks", "Kvartilene", "Kilde:", "Bygget", "Tallene bak")
                     if w in page_en]
        chk(not norwegian, "the English page keeps no Norwegian chrome", str(norwegian))

        print("\n9. the row names do not collide, measured in a browser")
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
                view.wait_for_selector(".bx-box")
                boxes_on_page = view.evaluate(
                    """() => [...document.querySelectorAll('.bx-name')].map(e => {
                         const r = e.getBoundingClientRect();
                         return {t: e.textContent, x: r.x, y: r.y, w: r.width, h: r.height,
                                 size: parseFloat(getComputedStyle(e).fontSize)}; })""")
                overlap = []
                for i, a in enumerate(boxes_on_page):
                    for b in boxes_on_page[i + 1:]:
                        if (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                                and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]):
                            overlap.append(f"{a['t']}/{b['t']}")
                chk(not overlap, f"no two row names overlap at {width} px", str(overlap[:3]))
                small = [b["t"] for b in boxes_on_page if b["size"] < 14]
                chk(not small, f"and every name is at least 14 px at {width} px", str(small[:3]))
                ctx.close()
            browser.close()

        print("\n10. the mutations")
        with tempfile.TemporaryDirectory() as mraw:
            mraw = pathlib.Path(mraw)

            # a. whiskers as min and max: the range instead of the tail.
            tools = scratch(mraw / "range",
                            ('    inside = [v for v in ordered if low_fence <= v <= high_fence]',
                             '    inside = ordered'),
                            ('    outliers = [v for v in ordered if v < low_fence or v > high_fence]',
                             '    outliers = []'))
            out_m = mraw / "range.html"
            done = run(DATA, out_m, tools=tools)
            chk(done.returncode == 0, "the min-and-max mutation still builds",
                (done.stderr or "")[-200:])
            mpage = out_m.read_text(encoding="utf-8")
            chk(not OUTLIER.findall(mpage),
                "and no observation is drawn as an outlier any more, so check 3 sees it")

            # b. the quartile snapped to the nearest observation instead of interpolating.
            tools = scratch(mraw / "snap",
                            ('    return ordered[low] + (position - low) * (ordered[high] - ordered[low])',
                             '    return ordered[low]'))
            out_m = mraw / "snap.html"
            done = run(DATA, out_m, tools=tools)
            chk(done.returncode == 0, "the snapped-quantile mutation still builds",
                (done.stderr or "")[-200:])
            mpage = out_m.read_text(encoding="utf-8")
            mrows = table_rows(mpage)
            mismatched = [row[0] for row, name in zip(mrows, NAME.findall(mpage))
                          if abs(num(row[4]) - boxes[name]["median"]) > 0.005]
            chk(bool(mismatched),
                "and the table's median stops matching this suite's, so check 5 sees it",
                str(mismatched[:3]))

            # c. the row order ignored: always by name, whatever the page claims.
            tools = scratch(mraw / "order",
                            ('    order = (sorted(boxes, key=lambda name: (boxes[name]["median"], name))',
                             '    order = (sorted(boxes, key=lambda name: (name, name))'))
            out_m = mraw / "order.html"
            done = run(DATA, out_m, tools=tools)
            chk(done.returncode == 0, "the ignored-order mutation still builds",
                (done.stderr or "")[-200:])
            mpage = out_m.read_text(encoding="utf-8")
            chk(NAME.findall(mpage) == sorted(groups) and sorted(groups) != shown,
                "and the rows come out by name while the page still claims median order, so "
                "check 4 sees it")

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
