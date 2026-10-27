#!/usr/bin/env python3
"""The Gantt: the plan against what happened, and the slip as a number.

The shape is a comparison, so the checks are about the comparison: that both bars use the same
day scale, that the difference printed is the difference the dates give, that an unfinished task
is a word rather than a bar, and that the axis refuses to guess a date format.

  1. every task gets a plan bar, and every task that started gets an actual bar
  2. both bars share one day scale, and each bar starts on its own date
  3. the printed difference is (actual finish - planned finish) in days, with its sign
  4. a task that has not started is a word, and a task with no finish is "running"
  5. the table repeats every date, the difference and the state
  6. refusals: an end before its start, a non-ISO date, half an actual pair, too many tasks
  7. the committed example is the builder's own output, byte for byte
  8. no script, and the English build carries no Norwegian
  9. the task names and the today marker do not collide, measured in a browser
 10. three mutations, each breaking exactly one of the checks above

    python3 tests/test_gantt.py
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
BUILDER = ROOT / "tools" / "build_gantt.py"
EXAMPLE = ROOT / "examples" / "49-gantt"
DATA = EXAMPLE / "fremdrift.csv"
PAGE = EXAMPLE / "fremdrift.html"
TODAY = "2026-10-26"
PIN = "1792836000"

FAILURES: list[str] = []
CHECKS = 0

PLAN = re.compile(r'<rect class="gt-plan" data-task="([^"]*)" x="([-\d.]+)" y="[-\d.]+" '
                  r'width="([-\d.]+)" height="[-\d.]+"')
ACTUAL = re.compile(r'<rect class="(gt-actual[^"]*)" data-task="([^"]*)" x="([-\d.]+)" '
                    r'y="[-\d.]+" width="([-\d.]+)" height="[-\d.]+"')
NAME = re.compile(r'<text class="gt-name" x="[-\d.]+" y="[-\d.]+" text-anchor="end">([^<]*)</text>')
GUTTER = 210.0


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


def run(data: pathlib.Path, out: pathlib.Path, *extra: str, lang: str = "nb",
        tools: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    builder = (tools / "build_gantt.py") if tools else BUILDER
    args = [sys.executable, str(builder), "--data", str(data), "--task", "Tiltak",
            "--start", "Planstart", "--end", "Planferdig",
            "--actual-start", "Faktisk-start", "--actual-end", "Faktisk-ferdig",
            "--today", TODAY, "--title", "Fremdrift per tiltak",
            "--source", "Syntetisk eksempeldata (fremdrift.csv)",
            "--requested-by", "Prosjektkontoret", "--lang", lang, "--out", str(out), *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env)


def scratch(root: pathlib.Path, *pairs: tuple[str, str]) -> pathlib.Path:
    tools = root / "tools"
    tools.mkdir(parents=True)
    shutil.copy2(BUILDER, tools / "build_gantt.py")
    for name in ("build_size.py", "build_stamp.py", "feedback_link.py", "i18n.py",
                 "tun_core.py", "tun_tokens.py"):
        shutil.copy2(ROOT / "tools" / name, tools / name)
    shutil.copytree(ROOT / "tools" / "tokens", tools / "tokens")
    shutil.copytree(ROOT / "templates", root / "templates")
    target = tools / "build_gantt.py"
    text = target.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            raise SystemExit(f"the mutation does not apply: {old[:70]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")
    return tools


def own_rows(path: pathlib.Path = DATA) -> list[dict]:
    def day(text: str) -> dt.date | None:
        return dt.date.fromisoformat(text) if text.strip() else None

    with path.open(newline="", encoding="utf-8-sig") as fh:
        out = []
        for row in csv.DictReader(fh, delimiter=";"):
            out.append({"task": row["Tiltak"],
                        "plan_start": day(row["Planstart"]), "plan_end": day(row["Planferdig"]),
                        "act_start": day(row["Faktisk-start"]),
                        "act_end": day(row["Faktisk-ferdig"])})
    out.sort(key=lambda r: (r["plan_start"], r["plan_end"]))
    return out


def own_state(row: dict) -> str:
    """Written out again from the definition, so the builder is not marking its own work."""
    if not row["act_start"]:
        return "notstarted"
    if not row["act_end"]:
        return "running"
    slip = (row["act_end"] - row["plan_end"]).days
    return "late" if slip > 0 else ("early" if slip < 0 else "ontime")


def table_rows(page: str) -> list[list[str]]:
    body = re.search(r"<tbody>(.*?)</tbody>", page, re.S).group(1)
    return [[re.sub(r"<[^>]+>", "", cell).strip()
             for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            for row in re.findall(r"<tr>(.*?)</tr>", body, re.S)]


def main() -> int:
    if not DATA.is_file():
        raise SystemExit(f"{DATA} is missing; run examples/49-gantt/generate_data.py")
    rows = own_rows()
    today = dt.date.fromisoformat(TODAY)
    first = min(min(r["plan_start"] for r in rows),
                min(r["act_start"] for r in rows if r["act_start"]))
    last = max(max(r["plan_end"] for r in rows),
               max((r["act_end"] for r in rows if r["act_end"]), default=first), today)
    span = (last - first).days

    with tempfile.TemporaryDirectory() as raw:
        work = pathlib.Path(raw)
        out = work / "gt.html"
        done = run(DATA, out)
        print("1. every task gets a plan bar, and every started task an actual bar")
        chk(done.returncode == 0, "the builder exits 0", (done.stderr or "")[-400:])
        page = out.read_text(encoding="utf-8")
        plan = {name: (float(x), float(w)) for name, x, w in PLAN.findall(page)}
        actual = {name: (cls, float(x), float(w)) for cls, name, x, w
                  in ACTUAL.findall(page)}
        chk(list(plan) == [r["task"] for r in rows],
            "one plan bar per task, in the page's row order",
            f"{list(plan)[:3]} vs {[r['task'] for r in rows][:3]}")
        started = [r["task"] for r in rows if r["act_start"]]
        chk(sorted(actual) == sorted(started),
            "one actual bar for every task that started, and none for the rest",
            f"{sorted(actual)} vs {sorted(started)}")
        not_started = [r["task"] for r in rows if not r["act_start"]]
        chk(all(t in page for t in not_started),
            "and a task that never started is named on the drawing", str(not_started))
        chk(all(actual[t][0] == "gt-actual gt-running"
                for t in started if not next(r for r in rows if r["task"] == t)["act_end"]),
            "a task with no finish is drawn as running rather than finished")

        print("\n2. both bars use one day scale, and each starts on its own date")
        # The plan bars are the reference: derive pixels-per-day from them, then hold the
        # actual bars to the same number. A second scale is exactly what would slip through a
        # check that measured each bar against itself.
        ratios = [plan[r["task"]][1] / max(1, (r["plan_end"] - r["plan_start"]).days)
                  for r in rows]
        k = sum(ratios) / len(ratios)
        chk(max(ratios) - min(ratios) < 0.01,
            "every plan bar is the same number of pixels per day",
            f"{min(ratios):.3f} .. {max(ratios):.3f}")
        wrong_start = [r["task"] for r in rows
                       if abs(plan[r["task"]][0] - (GUTTER + (r["plan_start"] - first).days * k)) > 0.6]
        chk(not wrong_start, "and starts at its own planned date", str(wrong_start[:3]))
        wrong_actual = []
        for row in rows:
            if not row["act_start"]:
                continue
            end = row["act_end"] or today
            want_x = GUTTER + (row["act_start"] - first).days * k
            want_w = max(2.0, (end - row["act_start"]).days * k)
            got = actual[row["task"]]
            if abs(got[1] - want_x) > 0.6 or abs(got[2] - want_w) > 0.6:
                wrong_actual.append(f"{row['task']}: x {got[1]:.1f}/{want_x:.1f} "
                                    f"w {got[2]:.1f}/{want_w:.1f}")
        chk(not wrong_actual,
            "and the actual bar lands on the same scale, so a slip cannot be drawn to lie",
            str(wrong_actual[:2]))

        print("\n3. the printed difference is the difference the dates give")
        shown = NAME.findall(page)
        slips = {name: float(v.replace("\u2212", "-").replace(",", "."))
                 for name, v in zip(shown, re.findall(
                     r'<text class="gt-slip" x="[-\d.]+" y="[-\d.]+" text-anchor="end">([^<]*)</text>',
                     page)) if v not in ("", "\u2013") and v != "pågår"}
        want_slips = {r["task"]: (r["act_end"] - r["plan_end"]).days
                      for r in rows if r["act_end"] and r["act_start"]}
        chk(slips == {k2: float(v) for k2, v in want_slips.items()},
            "every finished task carries its own difference in days", f"{slips} vs {want_slips}")
        signs = re.findall(r'<text class="gt-slip"[^>]*>([+\u2212]?[\d]+)</text>', page)
        positive = {k2 for k2, v in want_slips.items() if v > 0}
        chk(any(s.startswith("+") for s in signs),
            "a late task prints a plus, so the direction is not left to the reader")
        negative = {k2 for k2, v in want_slips.items() if v < 0}
        chk(negative and any(s.startswith("\u2212") for s in signs),
            "and an early one prints a real minus", str(negative))
        chk(positive and not any(
            re.search(rf'data-task="{re.escape(t)}"', page) and False for t in positive),
            "the late set is non-empty, so the sign checks above are not vacuous",
            str(positive))

        print("\n4. an unfinished task is a word, and the five states are five words")
        body = page
        chk("pågår" in body and "ikke startet" in body,
            "the two unfinished states carry different words")
        chk("ferdig i tide" in body and "ferdig før planen" in body
            and "ferdig etter planen" in body,
            "and the three finished states do too")

        print("\n5. the table repeats every date, the difference and the state")
        table = table_rows(page)
        chk(len(table) == len(rows), "one row per task", str(len(table)))
        bad = []
        for cells, row in zip(table, rows):
            slip = ((row["act_end"] - row["plan_end"]).days
                    if row["act_end"] and row["act_start"] else None)
            want = [row["task"], row["plan_start"].strftime("%d.%m.%Y"),
                    row["plan_end"].strftime("%d.%m.%Y"),
                    row["act_start"].strftime("%d.%m.%Y") if row["act_start"] else "\u2013",
                    row["act_end"].strftime("%d.%m.%Y") if row["act_end"] else "\u2013",
                    ("\u2212" if slip < 0 else "+" if slip > 0 else "") + str(abs(slip))
                    if slip is not None else "\u2013"]
            for got, want_value in zip(cells[:6], want):
                if got != want_value:
                    bad.append(f"{row['task']}: {got!r} vs {want_value!r}")
            if cells[6] != {
                "notstarted": "ikke startet", "running": "pågår", "late": "ferdig etter planen",
                "early": "ferdig før planen", "ontime": "ferdig i tide",
            }[own_state(row)]:
                bad.append(f"{row['task']}: state {cells[6]!r}")
        chk(not bad, "and every cell is this suite's own number or word", str(bad[:3]))
        chk(any(c[5] == "0" for c in table),
            "a task that finished exactly on its planned date prints 0, not 00",
            str([c[5] for c in table]))

        print("\n6. refusals name what to fix")
        backwards = work / "backwards.csv"
        backwards.write_text("Tiltak;Planstart;Planferdig;Faktisk-start;Faktisk-ferdig\n"
                             "Alfa;2026-06-10;2026-06-01;;\n",
                             encoding="utf-8")
        done = run(backwards, work / "b.html")
        chk(done.returncode != 0 and "before the planned start" in (done.stderr or ""),
            "an end before its start is refused", (done.stderr or "")[-200:])

        dotted = work / "dotted.csv"
        dotted.write_text("Tiltak;Planstart;Planferdig;Faktisk-start;Faktisk-ferdig\n"
                           "Alfa;03.04.2026;10.04.2026;;\n",
                          encoding="utf-8")
        done = run(dotted, work / "d2.html")
        chk(done.returncode != 0 and "not a date" in (done.stderr or ""),
            "a dd.mm date is refused rather than guessed", (done.stderr or "")[-200:])

        half = work / "half.csv"
        half.write_text("Tiltak;Planstart;Planferdig;Faktisk-start;Faktisk-ferdig\n"
                        "Alfa;2026-06-01;2026-06-05;2026-06-02;\n", encoding="utf-8")
        args = [sys.executable, str(BUILDER), "--data", str(half), "--task", "Tiltak",
                "--start", "Planstart", "--end", "Planferdig", "--actual-start",
                "Faktisk-start", "--title", "t", "--out", str(work / "h.html")]
        done = subprocess.run(args, capture_output=True, text=True, cwd=ROOT)
        chk(done.returncode != 0 and "go together" in (done.stderr or ""),
            "half an actual pair is refused", (done.stderr or "")[-200:])

        many = work / "many.csv"
        lines = ["Tiltak;Planstart;Planferdig"]
        base = dt.date(2026, 6, 1)
        for i in range(30):
            start = base + dt.timedelta(days=i)
            lines.append(f"T{i};{start};{start + dt.timedelta(days=3)}")
        many.write_text("\n".join(lines) + "\n", encoding="utf-8")
        done = run(many, work / "m.html", "--actual-start", "", "--actual-end", "")
        chk(done.returncode != 0 and "ceiling" in (done.stderr or ""),
            "past the task ceiling it names the timeline instead", (done.stderr or "")[-200:])

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
        norwegian = [w for w in ("Tiltak", "pågår", "ikke startet", "Kilde:", "Bygget",
                                 "i dag", "Avvik") if w in page_en]
        chk(not norwegian, "the English page keeps no Norwegian chrome", str(norwegian))

        print("\n9. nothing collides, measured in a browser")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            chk(False, "playwright is installed (this suite measures text)")
            report()
            return 1
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for width in (1100, 1500):
                ctx = browser.new_context(viewport={"width": width, "height": 1000})
                view = ctx.new_page()
                view.goto(PAGE.resolve().as_uri())
                view.wait_for_selector(".gt-plan")
                boxes = view.evaluate(
                    """() => {
                         const grab = (sel) => [...document.querySelectorAll(sel)].map(e => {
                           const r = e.getBoundingClientRect();
                           return {t: e.textContent, x: r.x, y: r.y, w: r.width, h: r.height,
                                   size: parseFloat(getComputedStyle(e).fontSize)}; });
                         return {names: grab('.gt-name'), marks: grab('.gt-tick, .gt-today-label')};
                       }""")
                def overlaps(items):
                    out = []
                    for i, a in enumerate(items):
                        for b in items[i + 1:]:
                            if (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                                    and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]):
                                out.append(f"{a['t']}/{b['t']}")
                    return out
                chk(not overlaps(boxes["names"]),
                    f"no two task names overlap at {width} px", str(overlaps(boxes["names"])[:3]))
                chk(not overlaps(boxes["marks"]),
                    f"the today marker does not print through a month label at {width} px",
                    str(overlaps(boxes["marks"])[:3]))
                small = [b["t"] for b in boxes["names"] + boxes["marks"] if b["size"] < 14]
                chk(not small, f"and every label is at least 14 px at {width} px", str(small[:3]))
                ctx.close()
            browser.close()

        print("\n10. the mutations")
        with tempfile.TemporaryDirectory() as mraw:
            mraw = pathlib.Path(mraw)

            # a. the difference printed without its sign.
            tools = scratch(mraw / "sign",
                            ('            sign = "\\u2212" if slip < 0 else ("+" if slip > 0 else "")',
                             '            sign = ""'))
            out_m = mraw / "sign.html"
            done = run(DATA, out_m, tools=tools)
            chk(done.returncode == 0, "the unsigned-slip mutation still builds",
                (done.stderr or "")[-200:])
            mpage = out_m.read_text(encoding="utf-8")
            msigns = re.findall(r'<text class="gt-slip"[^>]*>([+\u2212]?[\d]+)</text>', mpage)
            chk(not any(s.startswith(("+", "\u2212")) for s in msigns),
                "and no difference carries a sign any more, so check 3 sees it")

            # b. an unstarted task drawn as a zero-length bar.
            tools = scratch(mraw / "zero",
                            ('        if state == "notstarted":', '        if False:'),
                            ('            ax1, ax2 = px(row["act_start"]), px(act_end)',
                             '            ax1, ax2 = px(row["act_start"] or row["plan_start"]), px(act_end)'))
            out_m = mraw / "zero.html"
            done = run(DATA, out_m, tools=tools)
            chk(done.returncode == 0, "the zero-bar mutation still builds",
                (done.stderr or "")[-200:])
            mpage = out_m.read_text(encoding="utf-8")
            mactual = [n for _c, n, _x, _w in ACTUAL.findall(mpage)]
            chk(len(mactual) == len(rows),
                "and every task now has a bar, including the ones that never started, so "
                "check 1 sees it", f"{len(mactual)} vs {len(started)}")

            # c. the actual bar on its own scale, a quarter wider.
            tools = scratch(mraw / "scale")
            # The wider bar is made by scaling the width after it is computed: a second scale
            # is the defect, and it has to be introduced where the scale is used.
            target = tools / "build_gantt.py"
            text = target.read_text(encoding="utf-8")
            old = 'width="{max(2.0, ax2 - ax1):.2f}"'
            assert text.count(old) == 1
            target.write_text(text.replace(old, 'width="{max(2.0, ax2 - ax1) * 1.25:.2f}"', 1),
                              encoding="utf-8")
            out_m = mraw / "scale.html"
            done = run(DATA, out_m, tools=tools)
            chk(done.returncode == 0, "the second-scale mutation still builds",
                (done.stderr or "")[-200:])
            mpage = out_m.read_text(encoding="utf-8")
            mactual = {n: (float(x), float(w)) for _c, n, x, w in ACTUAL.findall(mpage)}
            mwrong = []
            for row in rows:
                if not row["act_start"]:
                    continue
                end = row["act_end"] or today
                want_w = max(2.0, (end - row["act_start"]).days * k)
                if abs(mactual[row["task"]][1] - want_w) > 0.6:
                    mwrong.append(row["task"])
            chk(bool(mwrong),
                "and the actual bars no longer sit on the plan scale, so check 2 sees it",
                str(mwrong[:3]))

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
