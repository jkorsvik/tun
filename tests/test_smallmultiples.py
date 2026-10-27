#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The small multiples: one panel per group, every panel on ONE scale.

This artefact exists to answer one question, "which group behaves differently", and it has
exactly one requirement: all panels share a vertical scale. Give each panel its own axis and a
group moving between 4 and 8 looks precisely like one moving between 400 and 800. Every number
in the picture is still true, so the mistake is invisible to a reader and to `verify_a11y`.

So the suite re-derives the drawing from the extract, with no help from the builder:

  * one linear map from value to y, fitted over EVERY dot in EVERY panel. A per-panel scale
    puts the dots on different lines and the residual explodes. A mutation does exactly that
  * the two rules drawn in each panel (the top of the scale and its floor) must land on the y
    that map gives for the two numbers printed on the axis, in every panel of every row
  * one x map too: the same period sits at the same x in every panel, so a reader can carry a
    week down the column with the eye
  * the scale starts at zero unless `--truncate` says otherwise, and then the page says so in
    a warning that names the floor
  * a missing period is a break in the line, never a bridge and never a zero: the number of
    unbroken runs is re-derived from the extract for every panel
  * each panel prints its own latest value; the table re-states first, latest, change, lowest,
    highest and how many periods the group actually has
  * the panel order is the order that was asked for, computed from the drawn numbers

Five mutations, each of which must break one named check and no other.

    python3 tests/test_smallmultiples.py
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_smallmultiples.py"
EXAMPLE = ROOT / "examples" / "45-smallmultiples"
DATA = EXAMPLE / "ko.csv"
PAGE = EXAMPLE / "smaaflater.html"
PIN = "1792836000"          # a fixed clock: one input, one file, on any day

sys.path.insert(0, str(ROOT / "tools"))
import build_smallmultiples as B  # noqa: E402  the scale and the grid, checked here

FAILURES: list[str] = []
CHECKS = 0

PANEL = re.compile(r'<g class="sm-panel" data-group="(.*?)">(.*?)</g>', re.S)
NAME = re.compile(r'<text class="sm-name"[^>]*>(.*?)</text>')
LATEST = re.compile(r'<text class="sm-latest"[^>]*>(.*?)</text>')
RULE_TOP = re.compile(r'<line class="sm-rule-top"[^>]*y1="([-\d.]+)"')
RULE_LOW = re.compile(r'<line class="sm-rule"[^>]*y1="([-\d.]+)"')
DOT = re.compile(r'<circle class="sm-dot" data-p="(.*?)" data-v="(.*?)" cx="([-\d.]+)" '
                 r'cy="([-\d.]+)"')
POLY = re.compile(r'<polyline class="sm-line" points="([^"]*)"')
AXIS = re.compile(r'<text class="sm-axis" x="([-\d.]+)" y="([-\d.]+)"'
                  r'(?: text-anchor="end")?>(.*?)</text>')


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


# ------------------------------------------------------------------------------- fixtures
def read_data(path: pathlib.Path = DATA) -> tuple[dict[str, dict[str, float]], list[str]]:
    """The extract, parsed here rather than by the builder: group -> period -> value."""
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    head = lines[0].split(";")
    gi, pi, mi = head.index("Enhet"), head.index("Uke"), head.index("Saker")
    values: dict[str, dict[str, float]] = {}
    for line in lines[1:]:
        cells = line.split(";")
        values.setdefault(cells[gi], {})[cells[pi]] = float(cells[mi])
    return values, sorted({p for per in values.values() for p in per})


def run(data: pathlib.Path, out: pathlib.Path, *extra: str, lang: str = "nb",
        tools: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    builder = (tools / "build_smallmultiples.py") if tools else BUILDER
    args = [sys.executable, str(builder), "--data", str(data),
            "--group", "Enhet", "--period", "Uke", "--measure", "Saker",
            "--title", "Saker i ko, per enhet og uke",
            "--source", "Syntetisk eksempeldata (ko.csv)",
            "--requested-by", "Driftsavdelingen", "--lang", lang, "--out", str(out), *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env)


def scratch(root: pathlib.Path, old: str, new: str) -> pathlib.Path:
    """A copy of tools/ and templates/ a mutation can break without touching the repo."""
    tools = root / "tools"
    tools.mkdir(parents=True)
    for name in ("build_smallmultiples.py", "build_size.py", "build_stamp.py",
                 "feedback_link.py", "i18n.py", "tun_core.py", "tun_tokens.py"):
        shutil.copy2(ROOT / "tools" / name, tools / name)
    # tun_tokens resolves the token files from its own location, so the scratch tree needs them:
    # the template carries {{TOKEN_CSS}} and the builder cannot produce a page without the seam.
    shutil.copytree(ROOT / "tools" / "tokens", tools / "tokens")
    shutil.copytree(ROOT / "templates", root / "templates")
    target = tools / "build_smallmultiples.py"
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"the mutation does not apply once: {text.count(old)} x {old[:70]!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")
    return tools


def num(text: str) -> float:
    """A number as the page prints it: no-break thousands, and a comma decimal in nb."""
    cleaned = (text.replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
               .replace(",", ".").replace("\u2212", "-"))
    return float(cleaned)


# --------------------------------------------------------------------------------- parse
def panels_of(html: str) -> list[dict]:
    """Every panel with its name, latest label, rules, dots and lines, in page order."""
    out = []
    for group, body in PANEL.findall(html):
        dots = [{"period": p, "value": float(v), "x": float(x), "y": float(y)}
                for p, v, x, y in DOT.findall(body)]
        out.append({
            "group": group,
            "name": (NAME.search(body) or [None, ""])[1],
            "latest": num((LATEST.search(body) or [None, "0"])[1]),
            "rule_top": float(RULE_TOP.search(body).group(1)),
            "rule_low": float(RULE_LOW.search(body).group(1)),
            "dots": dots,
            "runs": [[tuple(float(n) for n in pair.split(","))
                      for pair in run.split()] for run in POLY.findall(body)],
        })
    if not out:
        raise SystemExit("no panel parsed: the markup this suite knows is not on the page")
    return out


def axis_of(html: str) -> tuple[float, float, list[tuple[float, float, str]]]:
    """(high, low) as printed on the axis, plus every axis label with its position."""
    labels = [(float(x), float(y), text) for x, y, text in AXIS.findall(html)]
    numbers = [(y, num(text)) for x, y, text in labels if text.replace("\u00a0", "").isdigit()
               or re.fullmatch(r"[\d\u00a0\u202f ,]+", text)]
    if not numbers:
        return 0.0, 0.0, labels
    values = [v for _, v in numbers]
    return max(values), min(values), labels


# ---------------------------------------------------------------------------------- main
def main() -> int:
    values, periods = read_data()
    names = sorted(values)
    total_panels = len(names)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        out = tmp / "page.html"
        result = run(DATA, out)
        if result.returncode != 0:
            print(result.stderr[-2000:])
            raise SystemExit("the builder refused the example, so nothing below could run")
        page = out.read_text(encoding="utf-8")

        panels = panels_of(page)
        high, low, labels = axis_of(page)

        # ---------------------------------------------------------------- 1. one scale
        print("\n1. every panel is drawn on one scale, and the page prints that scale")
        expected_high = max(v for c in values.values() for v in c.values())
        expected_low = 0.0
        chk(high == expected_high, "the top of the printed scale is the largest value drawn",
            f"printed {high}, data {expected_high}")
        chk(low == expected_low, "the floor of the printed scale is zero, without --truncate",
            f"printed {low}")

        # Each panel draws the top of the scale and its floor as two rules. Those two lines
        # plus the printed numbers are the whole scale, so every dot can be checked against
        # the scale the page itself prints. A panel that scaled itself would put its own
        # numbers on the axis and its dots would land elsewhere.
        def expected_y(panel: dict, value: float) -> float:
            span = panel["rule_low"] - panel["rule_top"]
            return panel["rule_low"] - (value - low) / ((high - low) or 1.0) * span

        off = []
        for panel in panels:
            for dot in panel["dots"]:
                delta = expected_y(panel, dot["value"]) - dot["y"]
                if abs(delta) > 0.3:
                    off.append((panel["group"], dot["period"], dot["value"], round(delta, 2)))
        chk(not off, "every dot lands where the printed scale puts it, in every panel",
            str(off[:4]))
        chk(all(p["rule_top"] < p["rule_low"] for p in panels),
            "a larger value is drawn higher: the top rule is above the floor rule")
        spans = {round(p["rule_low"] - p["rule_top"], 1) for p in panels}
        chk(len(spans) == 1, "the scale covers the same height in every panel", str(spans))
        units = {round((high - low) / (p["rule_low"] - p["rule_top"]), 4) for p in panels}
        chk(len(units) == 1, "so one value is worth the same number of units everywhere",
            str(units))

        # ------------------------------------------------------------- 2. the grid
        print("\n2. one panel per group, in the order that was asked for")
        chk([p["group"] for p in panels] == names,
            "one panel per group, in name order by default",
            str([p["group"] for p in panels]))
        chk(all(p["name"] == p["group"] for p in panels), "each panel is labelled with its own name")
        chk(all(abs(expected_y(p, p["latest"]) - p["dots"][-1]["y"]) < 0.3 for p in panels),
            "the latest value printed in each panel is the last dot in it")
        for p in panels:
            want = values[p["group"]]
            last = max(want, key=lambda k: periods.index(k))
            if abs(p["latest"] - want[last]) > 1e-9:
                chk(False, "each panel prints the group's own last value",
                    f"{p['group']}: printed {p['latest']}, data {want[last]}")
                break
        else:
            chk(True, "each panel prints the group's own last value")

        # ------------------------------------------------------------ 3. one x axis
        print("\n3. one x axis: a period sits at the same place in every panel")
        # A panel's x positions are local to its column, so the shared axis is a shared
        # SPACING: one period is worth the same width everywhere, which is what lets the eye
        # carry a week straight down a column.
        steps = {}
        for p in panels:
            first, last = p["dots"][0], p["dots"][-1]
            i0, i1 = periods.index(first["period"]), periods.index(last["period"])
            steps[p["group"]] = round((last["x"] - first["x"]) / (i1 - i0), 3)
        spread = max(steps.values()) - min(steps.values())
        chk(spread < 0.2, "one period is worth the same width in every panel",
            f"spread {spread:.2f} units: {sorted(set(steps.values()))}")
        chk(all(p["dots"] == sorted(p["dots"], key=lambda d: periods.index(d["period"]))
                for p in panels), "each panel's dots run left to right in period order")
        chk({d["period"] for p in panels for d in p["dots"]} == set(periods),
            "the axis spans every period the data holds")

        # ---------------------------------------------------------- 4. missing = break
        print("\n4. a period with no row is a break in the line, never a bridge or a zero")
        for p in panels:
            cells = values[p["group"]]
            runs, current = 0, 0
            for period in periods:
                if period in cells:
                    current += 1
                else:
                    if current > 1:
                        runs += 1
                    current = 0
            if current > 1:
                runs += 1
            if len(p["runs"]) != runs:
                chk(False, "the number of unbroken runs matches the extract, panel by panel",
                    f"{p['group']}: drawn {len(p['runs'])}, extract says {runs}")
                break
        else:
            chk(True, "the number of unbroken runs matches the extract, panel by panel")
        chk(any(len(p["runs"]) > 1 for p in panels),
            "at least one panel really does hold a break, so the check above can fail")
        chk(all(len(run) == len({x for x, _ in run}) for p in panels for run in p["runs"]),
            "no point is drawn twice inside one run")
        gaps = sum(1 for g in names for period in periods if period not in values[g])
        chk(f"{gaps} periode" in page, "the page counts the missing panel-periods",
            f"{gaps} missing")

        # ------------------------------------------------------------- 5. the table
        print("\n5. the table restates every panel, and adds what a picture cannot")
        body = page.split("<tbody>")[1].split("</tbody>")[0]
        rows = re.findall(r'<tr><th scope="row">(.*?)</th>(.*?)</tr>', body, re.S)
        chk(len(rows) == total_panels, "one row per group", f"{len(rows)}")
        for group, rest in rows:
            cells = [num(c) for c in re.findall(r'<td class="num">(.*?)</td>', rest)[:5]]
            want = values[group]
            first = want[periods[[i for i, p in enumerate(periods) if p in want][0]]]
            last = want[periods[max(i for i, p in enumerate(periods) if p in want)]]
            if (cells[0] != first or cells[1] != last or cells[3] != min(want.values())
                    or cells[4] != max(want.values())):
                chk(False, "first, latest, lowest and highest are the extract's own numbers",
                    f"{group}: {cells} vs {first}, {last}, {min(want.values())}, "
                    f"{max(want.values())}")
                break
        else:
            chk(True, "first, latest, lowest and highest are the extract's own numbers")
        chk(all(f"{len(values[g])}/{len(periods)}" in rest for g, rest in rows),
            "each row says how many periods that group actually has",
            str([f"{len(values[g])}/{len(periods)}" for g, _ in rows]))
        chk(page.count("{{") == 0, "no template token survived filling")

        # ----------------------------------------------------------- 6. refusals
        print("\n6. refusals name what to fix")
        bad = tmp / "bad.csv"
        bad.write_text("Enhet;Uke;Annet\nA;2026-W01;1\n", encoding="utf-8")
        r = run(bad, tmp / "x.html")
        chk(r.returncode != 0 and "is not a column" in r.stderr and "Enhet" in r.stderr,
            "a --measure that is not a column names the columns it has")

        text = tmp / "text.csv"
        lines = DATA.read_text(encoding="utf-8").splitlines()
        cells = lines[1].split(";")
        cells[2] = "mange"
        lines[1] = ";".join(cells)
        text.write_text("\n".join(lines) + "\n", encoding="utf-8")
        r = run(text, tmp / "x.html")
        chk(r.returncode != 0 and "not a number" in r.stderr,
            "a value that is not a number stops the build instead of drawing a guess")

        many = tmp / "many.csv"
        lines = ["Enhet;Uke;Saker"]
        for i in range(B.MAX_PANELS + 1):
            for period in periods:
                lines.append(f"G{i:02d};{period};{10 + i}")
        many.write_text("\n".join(lines) + "\n", encoding="utf-8")
        r = run(many, tmp / "x.html")
        chk(r.returncode != 0 and str(B.MAX_PANELS) in r.stderr,
            "more groups than the page can carry is refused, with the ceiling named")

        short = tmp / "short.csv"
        short.write_text("Enhet;Uke;Saker\nA;2026-W01;1\nA;2026-W02;2\n", encoding="utf-8")
        r = run(short, tmp / "x.html")
        chk(r.returncode != 0 and str(B.MIN_PERIODS) in r.stderr,
            "one or two periods is refused: that is a difference, not a shape")

        r = run(DATA, tmp / "x.html", "--periods", "2026-W24,2026-W25,2026-W26")
        chk(r.returncode != 0 and "does not name" in r.stderr,
            "--periods that leaves a period in the data without a place is refused")

        # ------------------------------------------------------ 7. the other order
        print("\n7. the panel order is the order that was asked for, and it is printed")
        for order, key in (("latest", lambda g: -last_of(values[g], periods)),
                           ("change", lambda g: -(last_of(values[g], periods)
                                                  - first_of(values[g], periods)))):
            out2 = tmp / f"{order}.html"
            r = run(DATA, out2, "--order", order)
            if r.returncode != 0:
                chk(False, f"--order {order} builds", r.stderr[-300:])
                continue
            shown = [p["group"] for p in panels_of(out2.read_text(encoding="utf-8"))]
            chk(shown == sorted(names, key=key), f"--order {order} puts the right panel first",
                str(shown[:3]))
            chk("sortert" in out2.read_text(encoding="utf-8"),
                f"the page says which order it used for {order}")

        # --------------------------------------------------------- 8. the floor
        print("\n8. a truncated axis is allowed only when the page says so")
        out3 = tmp / "trunc.html"
        r = run(DATA, out3, "--truncate")
        page3 = out3.read_text(encoding="utf-8")
        high3, low3, _ = axis_of(page3)
        every = [v for c in values.values() for v in c.values()]
        chk(r.returncode == 0 and low3 > 0 and low3 < min(every),
            "with --truncate the floor is the data, not zero", f"printed {low3}")
        chk("Aksen starter ikke" in page3, "and the page warns about it in its own words")
        chk(B.num_text(low3, "nb") in page3,
            "the warning names the floor it used", B.num_text(low3, "nb"))

        # ---------------------------------------------------------- 9. languages
        print("\n9. no script, and the English page is English")
        chk("<script" not in page, "the page carries no script")
        out4 = tmp / "en.html"
        r = run(DATA, out4, lang="en")
        page_en = out4.read_text(encoding="utf-8")
        chk(r.returncode == 0 and '<html lang="en">' in page_en, "the English build runs")
        for word in ("Småflater", "Gruppe", "Høyest", "Perioder", "Bygget", "Aksen"):
            if word in page_en:
                chk(False, "the English page keeps no Norwegian chrome", word)
                break
        else:
            chk(True, "the English page keeps no Norwegian chrome")
        panels_en = panels_of(page_en)
        chk([p["group"] for p in panels_en] == names, "the data is not translated")

        # ------------------------------------------------- 10. committed example
        print("\n10. the committed example is the builder's own output")
        pinned = tmp / "pinned.html"
        r = run(DATA, pinned)
        chk(r.returncode == 0 and pinned.read_bytes() == PAGE.read_bytes(),
            "a pinned rebuild equals the committed file byte for byte")

        # --------------------------------------------------------- 11. mutations
        print("\n11. the mutations")
        with tempfile.TemporaryDirectory() as mtmp:
            mtmp = pathlib.Path(mtmp)

            # a. every panel gets its own scale: the lie this artefact exists to prevent
            tools = scratch(mtmp / "perpanel", 'return top + PAD_T + plot_h - (value - low) / span * plot_h',
                            'pl = min([v for v in cells.values()] + [0.0]); ph = max(cells.values()) or 1.0\n'
                            '        return top + PAD_T + plot_h - (value - pl) / ((ph - pl) or 1.0) * plot_h')
            out_m = mtmp / "perpanel.html"
            r = run(DATA, out_m, tools=tools)
            chk(r.returncode == 0, "the per-panel-scale mutation still builds")
            mp = panels_of(out_m.read_text(encoding="utf-8"))
            mspans = {round(p["rule_low"] - p["rule_top"], 1) for p in mp}
            chk(len(mspans) > 1, "and the panels no longer share one height, so check 1 sees it",
                str(sorted(mspans)))

            # f. only the dots are scaled per panel, the rules stay on the shared scale: the
            # complementary lie, and the one the height check above cannot see.
            tools = scratch(mtmp / "dotsonly",
                            'cy="{y_of(cells[period], top):.1f}"',
                            'cy="{top + PAD_T + (PANEL_H - PAD_T - PAD_B)'
                            ' - (cells[period] - min(cells.values()))'
                            ' / ((max(cells.values()) - min(cells.values())) or 1)'
                            ' * (PANEL_H - PAD_T - PAD_B):.1f}"')
            out_m = mtmp / "dotsonly.html"
            r = run(DATA, out_m, tools=tools)
            chk(r.returncode == 0, "the scaled-dots mutation still builds")
            mp = panels_of(out_m.read_text(encoding="utf-8"))
            mhigh, mlow, _ = axis_of(out_m.read_text(encoding="utf-8"))
            bad = [(p["group"], d["value"])
                   for p in mp for d in p["dots"]
                   if abs((p["rule_low"] - (d["value"] - mlow) / ((mhigh - mlow) or 1.0)
                           * (p["rule_low"] - p["rule_top"])) - d["y"]) > 0.3]
            chk(len(bad) > 10, "and its dots leave the printed scale, so the dot check sees it",
                f"{len(bad)} dots adrift")
            mspans = {round(p["rule_low"] - p["rule_top"], 1) for p in mp}
            chk(len(mspans) == 1,
                "and the heights are all equal, so only the dot check can catch this one",
                str(sorted(mspans)))

            # b. the gap is bridged: a trend drawn straight through a hole
            tools = scratch(mtmp / "bridge", '                if len(run) > 1:\n'
                                             '                    parts.append(f\'<polyline class="sm-line" points="{" ".join(run)}"/>\')\n'
                                             '                run = []\n'
                                             '                continue',
                            '                if run:\n'
                            '                    run.append(f\'{x_of(index_p, left):.1f},{y_of(low, top):.1f}\')\n'
                            '                continue')
            out_m = mtmp / "bridge.html"
            r = run(DATA, out_m, tools=tools)
            chk(r.returncode == 0, "the bridged-gap mutation still builds")
            mp = panels_of(out_m.read_text(encoding="utf-8"))
            chk(sum(len(p["runs"]) for p in mp) == total_panels,
                "and every panel is one unbroken run, so check 4 sees it",
                str([len(p["runs"]) for p in mp]))

            # c. the order flag is silently ignored: the panel order becomes an accident
            tools = scratch(mtmp / "order",
                            '    names = list(values)\n    if order == "name":',
                            '    names = list(values)\n    order = "name"\n    if order == "name":')
            out_m = mtmp / "order.html"
            r = run(DATA, out_m, "--order", "latest", tools=tools)
            chk(r.returncode == 0, "the ignored-order mutation still builds")
            mp = panels_of(out_m.read_text(encoding="utf-8"))
            chk([p["group"] for p in mp] == names,
                "and every order looks like name order, so check 7 sees it")

            # d. the latest label prints the first value: a number that contradicts its panel
            tools = scratch(mtmp / "latest", "        latest = last_value(cells, periods)",
                            "        latest = first_value(cells, periods)")
            out_m = mtmp / "latest.html"
            r = run(DATA, out_m, tools=tools)
            chk(r.returncode == 0, "the wrong-latest mutation still builds")
            mp = panels_of(out_m.read_text(encoding="utf-8"))
            chk(any(abs(p["latest"] - last_of(values[p["group"]], periods)) > 1e-9
                    for p in mp),
                "and a panel prints a number its own dots contradict, so check 2 sees it")

            # e. the floor is the data even without --truncate: an unannounced truncation
            tools = scratch(mtmp / "floor", "    low = min(0.0, low)", "    low = low")
            out_m = mtmp / "floor.html"
            r = run(DATA, out_m, tools=tools)
            chk(r.returncode == 0, "the silent-truncation mutation still builds")
            _h, mlow, _l = axis_of(out_m.read_text(encoding="utf-8"))
            chk(mlow > 0, "and the axis no longer starts at zero, so check 8 sees it",
                f"floor {mlow}")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failed of {CHECKS} checks:")
        for item in FAILURES:
            print(f"  - {item}")
        return 1
    print(f"{CHECKS} checks passed")
    return 0


def last_of(cells: dict[str, float], periods: list[str]) -> float:
    for period in reversed(periods):
        if period in cells:
            return cells[period]
    return 0.0


def first_of(cells: dict[str, float], periods: list[str]) -> float:
    for period in periods:
        if period in cells:
            return cells[period]
    return 0.0


if __name__ == "__main__":
    sys.exit(main())
