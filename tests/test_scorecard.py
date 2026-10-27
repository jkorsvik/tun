#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The scorecard: many measures, one period, with their targets and their history.

A scorecard is the one report where a number is supposed to carry a verdict, so this suite
spends its checks on the things that decide whether the verdict is earned:

  1. every measure in the file has a card and a row, and the table holds the source figures
     period by period. The card is a view of the table, never a second computation
  2. the change against the previous period, the change against the same month a year
     earlier, and the gap to the target are this suite's own subtractions. A plausible figure
     that is off by one period is the failure mode a screenshot cannot show
  3. the gap is always latest minus target, whichever direction is good, so the number a
     reader checks by hand is the number on the page
  4. a status exists only when both a direction and both bands were given, and it is
     recomputed here from the ratio to the target. Without a direction the page must print no
     verdict at all: an increase is good for revenue and bad for complaints
  5. a period missing from a series is a break in the drawing, never a line through it
  6. the drawing's points are the series: each dot's position is the value's, on the
     measure's own scale
  7. refusals, each naming what to fix: a direction word that is neither opp/ned nor up/down,
     two figures for one measure and period, a measure with no unit, a period that is not
     YYYY-MM, a band pair that is out of order
  8. the page holds no script, and the English build carries no Norwegian
  9. four mutations of the builder each trip exactly the check they should. Without them the
     checks above could be satisfied by a page that never had the property

Stdlib for the arithmetic. No browser: nothing here is measured on screen.

    python3 tests/test_scorecard.py
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
BUILDER = ROOT / "tools" / "build_scorecard.py"
EXAMPLE = ROOT / "examples" / "39-scorecard"
DATA = EXAMPLE / "manedstall.csv"
EN_FIXTURE = ROOT / "tests" / "fixtures" / "i18n-scorecard-en.csv"
PIN = "1792836000"

sys.path.insert(0, str(ROOT / "tools"))
import i18n  # noqa: E402   the card labels, so the suite reads the page by its own keys

T = i18n.load("scorecard", "nb")
T_EN = i18n.load("scorecard", "en")

FAILURES: list[str] = []
CHECKS = 0


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


# ---------------------------------------------------------------------------------- build
def run(data: pathlib.Path, out: pathlib.Path, *extra: str, tools: pathlib.Path | None = None,
        cols: dict | None = None, title: str = "Månedsrapport oktober 2026",
        source: str = "Syntetisk eksempeldata (manedstall.csv)",
        requested_by: str = "Kvalitetsavdelingen") -> subprocess.CompletedProcess:
    builder = (tools / "build_scorecard.py") if tools else BUILDER
    names = cols or {"kpi": "KPI", "period": "Periode", "value": "Verdi", "target": "Mal",
                     "direction": "Retning", "unit": "Enhet"}
    args = [sys.executable, str(builder), "--data", str(data),
            "--kpi-col", names["kpi"], "--period-col", names["period"],
            "--value-col", names["value"], "--target-col", names["target"],
            "--direction-col", names["direction"], "--unit-col", names["unit"],
            "--title", title, "--source", source, "--requested-by", requested_by,
            "--out", str(out), *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env)


def scratch(root: pathlib.Path, mutate: tuple[str, str]) -> pathlib.Path:
    tools = root / "tools"
    shutil.copytree(ROOT / "tools", tools,
                    ignore=shutil.ignore_patterns("__pycache__", "hooks"))
    shutil.copytree(ROOT / "templates", root / "templates")
    p = tools / "build_scorecard.py"
    text = p.read_text(encoding="utf-8")
    if mutate[0] not in text:
        raise SystemExit(f"mutation target not found: {mutate[0][:60]!r}")
    p.write_text(text.replace(mutate[0], mutate[1], 1), encoding="utf-8")
    return tools


# ---------------------------------------------------------------------------------- parse
def number(text: str) -> float:
    """A figure as the page prints it: nbsp grouping, comma decimal, a real minus sign."""
    clean = text.replace("\u00a0", "").replace("\u2009", "").replace("\u2212", "-")
    clean = re.sub(r"[^0-9,.\-]", "", clean).replace(",", ".")
    return float(clean) if clean not in ("", "-", ".") else 0.0


DOT = re.compile(r'<circle class="spark-dot" cx="([^"]*)" cy="([^"]*)"[^>]*>'
                 r"<title>([^<]+)</title>")


def cards(page: str) -> list[dict]:
    """Every card: its name, its unit, its figures, its status, and its drawing."""
    out = []
    for block in re.findall(r'<article class="card">(.*?)</article>', page, re.S):
        pairs = {}
        for m in re.finditer(r"<dt>([^<]+)</dt><dd(?: class=\"[^\"]*\")?>([^<]*)</dd>", block):
            pairs[m.group(1)] = m.group(2)
        out.append({
            "name": re.search(r"<h2>([^<]+)<span", block).group(1),
            "unit": re.search(r'<span class="unit">,\s*([^<]*)</span>', block).group(1),
            "big": number(re.search(r'<p class="big">([^<]+)</p>', block).group(1)),
            "pairs": pairs,
            "segments": len(re.findall(r'<polyline class="spark-line"', block)),
            "dots": [(float(m.group(1)), float(m.group(2)), m.group(3))
                     for m in DOT.finditer(block)],
            "target_line": bool(re.search(r'<line class="spark-target"', block)),
            "status_class": (re.search(r'<dd class="s-(green|amber|red)">', block) or
                             [None, ""])[1] if re.search(
                r'<dd class="s-(green|amber|red)">', block) else "",
        })
    return out


def table(page: str) -> dict:
    head = re.search(r"<thead>.*?</thead>", page, re.S).group(0)
    periods = re.findall(r'<th scope="col" class="num">([^<]+)</th>', head)[1:]
    rows = {}
    for m in re.finditer(r'<tr><th scope="row">([^<]+)<span[^>]*>[^<]*</span></th>'
                         r'<td class="num target">([^<]+)</td>(.*?)</tr>', page, re.S):
        cells = re.findall(r'<td class="num[^"]*">([^<]+)</td>', m.group(3))
        rows[m.group(1)] = {"target": m.group(2), "cells": cells}
    return {"periods": periods, "rows": rows}


def source(data: pathlib.Path = DATA, cols: dict | None = None) -> dict[str, dict[str, dict]]:
    names = cols or {"kpi": "KPI", "period": "Periode", "value": "Verdi", "target": "Mal"}
    series: dict[str, dict[str, dict]] = {}
    with data.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            series.setdefault(row[names["kpi"]], {})[row[names["period"]]] = {
                "value": number(row[names["value"]]),
                "target": number(row[names["target"]]),
            }
    return series


NB_MONTHS = ("jan", "feb", "mar", "apr", "mai", "jun",
             "jul", "aug", "sep", "okt", "nov", "des")


def period_of(label: str) -> str:
    """The column header read back as a period: "okt 2025" is 2025-10.

    The table prints month names, so the suite reads them back rather than assuming the order
    the table happens to have: a column in the wrong place then fails instead of passing.
    """
    name, _, year = label.partition(" ")
    return f"{year}-{NB_MONTHS.index(name.lower()) + 1:02d}"


def shift_year(period: str) -> str:
    year, month = period.split("-")
    return f"{int(year) - 1:04d}-{month}"


def expected_status(latest: float, target: float, direction: str,
                    green: float | None, amber: float | None) -> str:
    if not direction or green is None or amber is None:
        return ""
    if direction == "up":
        ratio = None if target == 0 else latest / target
    else:
        ratio = None if latest == 0 else target / latest
    if ratio is None:
        return ""
    return "green" if ratio >= green else ("amber" if ratio >= amber else "red")


# ----------------------------------------------------------------------------- properties
def table_is_the_source(page: str, series: dict) -> bool:
    tab = table(page)
    if set(tab["rows"]) != set(series):
        return False
    for name, periods in series.items():
        cells = tab["rows"][name]["cells"]
        if len(cells) != len(tab["periods"]):
            return False
        wanted = [periods.get(period_of(label)) for label in tab["periods"]]
        for cell, want in zip(cells, wanted):
            if want is None:
                if T["period_missing"] not in cell:
                    return False
            elif abs(number(cell) - want["value"]) > 0.005:
                return False
        target = next((p["target"] for p in reversed(list(periods.values()))), None)
        if abs(number(tab["rows"][name]["target"]) - target) > 0.005:
            return False
    return True


def changes_are_ours(page: str, series: dict) -> bool:
    for card in cards(page):
        periods = series[card["name"]]
        order = sorted(periods)
        latest = periods[order[-1]]["value"]
        if abs(card["big"] - latest) > 0.005:
            return False
        if len(order) > 1 and order[-2] == _month_before(order[-1]):
            if abs(number(card["pairs"][T["card_change"]]) - (latest - periods[order[-2]]["value"])) > 0.005:
                return False
        yoy = periods.get(shift_year(order[-1]))
        if yoy is not None:
            if abs(number(card["pairs"][T["card_yoy"]]) - (latest - yoy["value"])) > 0.005:
                return False
    return True


def gaps_are_latest_minus_target(page: str, series: dict) -> bool:
    for card in cards(page):
        periods = series[card["name"]]
        latest = periods[sorted(periods)[-1]]
        if abs(number(card["pairs"][T["card_gap"]]) - (latest["value"] - latest["target"])) > 0.005:
            return False
    return True


def statuses_are_recomputed(page: str, series: dict, direction: dict[str, str],
                            green: float | None, amber: float | None) -> bool:
    for card in cards(page):
        periods = series[card["name"]]
        latest = periods[sorted(periods)[-1]]
        want = expected_status(latest["value"], latest["target"], direction[card["name"]],
                               green, amber)
        word = card["pairs"][T["card_status"]]
        if want:
            if word != T[f"status_{want}"]:
                return False
        elif word in (T["status_green"], T["status_amber"], T["status_red"]):
            return False
    return True


def points_are_the_series(page: str, series: dict) -> bool:
    """Each dot's height is its value on that measure's own scale, and x is even.

    The window a card draws is the page's own last twelve periods, read off the table rather
    than assumed, so a card that drew a different window from the page fails here.
    """
    window = [period_of(label) for label in table(page)["periods"]][-12:]
    for card in cards(page):
        periods = series[card["name"]]
        drawn = [period_of(title.split(":")[0]) for _, _, title in card["dots"]]
        if drawn != [p for p in window if p in periods]:
            return False
        values = [periods[p]["value"] for p in drawn]
        xs = [x for x, _, _ in card["dots"]]
        if len(xs) > 2:
            # The coordinates are printed to one decimal, so equal spacing can differ by a
            # rounding step. A step that is not a whole multiple of the smallest one is a
            # point in the wrong column, and a multiple of two is a missing period.
            steps = [b - a for a, b in zip(xs, xs[1:])]
            base = min(steps)
            if any(abs(step - round(step / base) * base) > 0.25 for step in steps):
                return False
        # cy falls when the value rises, on one scale: comparing any pair is enough.
        for (ax, ay, _), (bx, by, _), av, bv in zip(card["dots"], card["dots"][1:],
                                                    values, values[1:]):
            if av == bv:
                if abs(ay - by) > 0.05:
                    return False
            elif (av < bv) != (ay > by):
                return False
    return True


def holes_break_the_line(page: str, series: dict) -> bool:
    """One polyline per run of two or more adjacent periods, so a missing month is a gap."""
    for card in cards(page):
        order = sorted(series[card["name"]])[-12:]
        runs, length = 0, 1
        for previous, current in zip(order, order[1:]):
            if _month_before(current) == previous:
                length += 1
            else:
                runs += 1 if length > 1 else 0
                length = 1
        runs += 1 if length > 1 else 0
        if card["segments"] != runs:
            return False
    return True


def _month_before(period: str) -> str:
    year, month = period.split("-")
    year, month = int(year), int(month) - 1
    if month == 0:
        year, month = year - 1, 12
    return f"{year:04d}-{month:02d}"


def no_verdict_without_direction(page: str) -> bool:
    for card in cards(page):
        if card["pairs"][T["card_status"]] != T["no_direction"]:
            return False
    return not re.search(r'<dd class="s-(green|amber|red)"', page)


def no_status_without_bands(page: str, series: dict) -> bool:
    for card in cards(page):
        if card["pairs"][T["card_status"]] != T["no_status"]:
            return False
        target = card["pairs"][T["card_target"]]
        if target == T["no_target"]:
            return False
    return not re.search(r'<dd class="s-(green|amber|red)"', page)


# ----------------------------------------------------------------------------------- main
def main() -> int:
    if not DATA.is_file():
        print(f"error: {DATA} is missing. Run {EXAMPLE / 'generate_data.py'} first.")
        return 2
    series = source()
    direction = {}
    with DATA.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            direction[row["KPI"]] = {"opp": "up", "ned": "down"}[row["Retning"]]

    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td)
        out = work / "nb.html"
        green, amber = 1.00, 0.95
        done = run(DATA, out, "--green-at", str(green), "--amber-at", str(amber))
        chk(done.returncode == 0, "the example builds", (done.stderr or "")[-400:])
        page = out.read_text(encoding="utf-8")

        print("\n1. the page and the source")
        chk(len(cards(page)) == len(series), "one card per measure",
            f"{len(cards(page))} cards, {len(series)} measures")
        chk(table_is_the_source(page, series),
            "the table holds the source figures, period by period, and the target")
        chk("<script" not in page, "the page holds no script at all")

        print("\n2. the figures on the cards")
        chk(changes_are_ours(page, series),
            "the change against the previous period and against last year are our subtractions")
        chk(gaps_are_latest_minus_target(page, series),
            "the gap is latest minus target, whichever direction is good")
        chk(sum(1 for c in cards(page) if c["big"] > 0) == len(series),
            "every card carries its latest figure")

        print("\n3. the verdict")
        chk(statuses_are_recomputed(page, series, direction, green, amber),
            "every status is the ratio to the target, measured against the bands")
        words = {c["pairs"][T["card_status"]] for c in cards(page)}
        chk(T["status_green"] in words and T["status_red"] in words,
            "the example holds both a green line and a red one", str(sorted(words)))
        chk(all((c["status_class"] == "") == (c["pairs"][T["card_status"]] not in words)
                for c in cards(page)),
            "a status colour is present exactly when a status word is")

        print("\n4. the drawing")
        chk(points_are_the_series(page, series),
            "every dot is its value on that measure's own scale, and x is evenly spaced")
        chk(holes_break_the_line(page, series),
            "a missing period is a break, not a line through it")
        klager = [c for c in cards(page) if c["segments"] > 1]
        chk(bool(klager), "the example's own hole really is drawn as two segments",
            f"{len(klager)} card(s)")
        chk(all(c["target_line"] for c in cards(page)
                if c["pairs"][T["card_target"]] != T["no_target"]),
            "every measure with a target draws it")

        print("\n5. no direction, no verdict")
        nodir = work / "nodir.csv"
        with DATA.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        with nodir.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["KPI", "Periode", "Verdi", "Mal", "Enhet"])
            writer.writeheader()
            for row in rows:
                writer.writerow({"KPI": row["KPI"], "Periode": row["Periode"],
                                 "Verdi": row["Verdi"], "Mal": row["Mal"], "Enhet": row["Enhet"]})
        out2 = work / "nodir.html"
        done = run(nodir, out2, "--green-at", "1.0", "--amber-at", "0.95",
                   "--direction-col", "Retning")
        chk(done.returncode == 0, "a file with no direction column still builds",
            (done.stderr or "")[-300:])
        chk(no_verdict_without_direction(out2.read_text(encoding="utf-8")),
            "and the page prints no status and no status colour at all")

        print("\n6. no bands, no status word")
        out3 = work / "nobands.html"
        done = run(DATA, out3)
        chk(done.returncode == 0, "a build without bands runs", (done.stderr or "")[-300:])
        chk(no_status_without_bands(out3.read_text(encoding="utf-8"), series),
            "and every measure says so instead of guessing a band")

        print("\n7. refusals")
        cases = []
        bad_dir = work / "baddir.csv"
        bad_dir.write_text(DATA.read_text(encoding="utf-8").replace(",opp,", ",oppover,", 1),
                           encoding="utf-8")
        cases.append((bad_dir, (), "bad direction word", "oppover"))
        dup = work / "dup.csv"
        lines = DATA.read_text(encoding="utf-8").splitlines()
        dup.write_text("\n".join(lines + [lines[1]]) + "\n", encoding="utf-8")
        cases.append((dup, (), "two figures for one measure and period", "two figures"))
        nounit = work / "nounit.csv"
        with nounit.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["KPI", "Periode", "Verdi", "Mal", "Retning"])
            writer.writerow(["Kundetilfredshet", "2026-01", "77", "78", "opp"])
        cases.append((nounit, (), "a measure with no unit", "--unit"))
        badperiod = work / "badperiod.csv"
        badperiod.write_text(DATA.read_text(encoding="utf-8").replace(",2026-01,", ",2026-13,", 1),
                             encoding="utf-8")
        cases.append((badperiod, (), "a period that is not YYYY-MM", "2026-13"))
        cases.append((DATA, ("--green-at", "0.9", "--amber-at", "1.0"), "bands out of order",
                      "amber"))
        for data, extra, what, needle in cases:
            done = run(data, work / "refused.html", *extra)
            chk(done.returncode == 2, f"refuses {what}", str(done.returncode))
            chk(needle in done.stderr, f"and says why: {what}", (done.stderr or "").strip()[:200])

        print("\n8. a measure with no unit is rescued by --unit")
        out4 = work / "unit.html"
        done = run(nounit, out4, "--unit", "Kundetilfredshet=poeng")
        chk(done.returncode == 0, "--unit fills the gap", (done.stderr or "")[-200:])
        chk("poeng" in out4.read_text(encoding="utf-8"), "and the unit is on the page")

        print("\n9. a target of zero has no ratio, and the page says so")
        zero = work / "zero.csv"
        with zero.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["KPI", "Periode", "Verdi", "Mal", "Retning", "Enhet"])
            writer.writerow(["Avvik", "2026-01", "4", "0", "opp", "antall"])
        out5 = work / "zero.html"
        done = run(zero, out5, "--green-at", "1.0", "--amber-at", "0.9")
        chk(done.returncode == 0, "it builds", (done.stderr or "")[-300:])
        page5 = out5.read_text(encoding="utf-8")
        chk(T["no_ratio"] in page5, "the status says the target is zero")
        chk(not re.search(r'<dd class="s-(green|amber|red)"', page5),
            "and no colour is invented for it")

        print("\n10. the English build is English")
        en_out = work / "en.html"
        done = run(EN_FIXTURE, en_out, "--green-at", "1.0", "--amber-at", "0.95",
                   "--lang", "en",
                   cols={"kpi": "Case", "period": "Period", "value": "Value",
                         "target": "Target", "direction": "Direction", "unit": "Unit"},
                   title="Monthly report", source="Made-up example data",
                   requested_by="The quality team")
        en = en_out.read_text(encoding="utf-8")
        chk(done.returncode == 0, "the English build runs", (done.stderr or "")[-300:])
        chk('<html lang="en">' in en, "the page declares its language")
        chk(not any(c in en for c in "æøåÆØÅ"), "and carries none of the Norwegian letters")
        for word in (T["card_change"], T["status_green"], T["head_table"]):
            chk(word not in en, f"and not the Norwegian {word!r}")

        print("\n11. the mutation controls")
        m1 = work / "m1"
        m1.mkdir()
        tools = scratch(m1, ("        gap = signed(latest - target, lang, dec)",
                             "        gap = signed(target - latest, lang, dec)"))
        done = run(DATA, work / "m1.html", "--green-at", "1.0", "--amber-at", "0.95", tools=tools)
        chk(done.returncode == 0, "the gap mutation builds", (done.stderr or "")[-200:])
        chk(not gaps_are_latest_minus_target((work / "m1.html").read_text(encoding="utf-8"),
                                             series),
            "a reversed gap is caught by the gap check")

        m2 = work / "m2"
        m2.mkdir()
        tools = scratch(m2, ('    if direction == "down":\n'
                             '        return None if latest == 0 else target / latest',
                             '    if direction == "down":\n'
                             '        return None if target == 0 else latest / target'))
        done = run(DATA, work / "m2.html", "--green-at", "1.0", "--amber-at", "0.95", tools=tools)
        chk(done.returncode == 0, "the direction mutation builds", (done.stderr or "")[-200:])
        chk(not statuses_are_recomputed((work / "m2.html").read_text(encoding="utf-8"),
                                        series, direction, green, amber),
            "a status that ignores the direction is caught by the status check")

        m3 = work / "m3"
        m3.mkdir()
        tools = scratch(m3, ("        elif run:", "        if run:"))
        done = run(DATA, work / "m3.html", "--green-at", "1.0", "--amber-at", "0.95", tools=tools)
        chk(done.returncode == 0, "the break mutation builds", (done.stderr or "")[-200:])
        chk(not holes_break_the_line((work / "m3.html").read_text(encoding="utf-8"), series),
            "a line drawn through a missing month is caught by the break check")

        m4 = work / "m4"
        m4.mkdir()
        tools = scratch(m4, ("    if not entry[\"direction\"]:\n        verdict = t[\"no_direction\"]",
                             "    if False:\n        verdict = t[\"no_direction\"]"))
        done = run(nodir, work / "m4.html", "--green-at", "1.0", "--amber-at", "0.95",
                   tools=tools)
        chk(done.returncode == 0, "the direction refusal mutation builds",
            (done.stderr or "")[-200:])
        chk(not no_verdict_without_direction((work / "m4.html").read_text(encoding="utf-8")),
            "a verdict with no declared direction is caught by the no-verdict check")

        print("\n12. the committed example is the builder's own output")
        fresh = work / "fresh.html"
        run(DATA, fresh, "--green-at", "1.00", "--amber-at", "0.95")
        chk(fresh.read_bytes() == (EXAMPLE / "manedsrapport.html").read_bytes(),
            "a pinned rebuild equals the committed file byte for byte")

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
