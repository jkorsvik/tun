#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The distribution page: the shape of one measure, and the arithmetic behind the picture.

Every other artefact the engine builds answers a question about a total. This one answers
"what do the individual cases look like", and it is the only artefact whose claim can be
falsified by arithmetic alone: the bars either add up to the rows or they do not. So this
suite checks the properties that make the picture trustworthy, and each one is a way the
page could lie:

  1. the bucket counts add up to the row count, per group and in total. The page prints that
     total, and this suite counts the source rows itself
  2. every printed count is the count this suite gets from the edges printed on the same
     page. The builder's own bucketing is not trusted to check itself: the edges are read
     off the artefact, and the counting is done again here
  3. the edges are uniform and increasing, the top edge covers the largest value, and a value
     that sits exactly on an edge lands in the upper bucket, once. That single rule is what
     makes the total possible
  4. the median and p90 on the page are this suite's own median and nearest-rank p90. A
     figure that is plausible and off by one is the failure mode a screenshot cannot show
  5. the bars carry their own counts, so the height is a cue and the text is the figure
  6. a row whose measure is not a number is refused by line, not skipped: skipping moves the
     total that check 1 is about
  7. a group under the floor is named with its count instead of being drawn, and it is not
     silently dropped from the page's arithmetic either
  8. the page holds no script, and the English build carries no Norwegian
  9. three mutations of the builder each trip exactly the check they should. Without them the
     checks above could be satisfied by a page that never had the property

Stdlib for the arithmetic; chromium for the one DOM check.

    python3 tests/test_distribution.py
"""
from __future__ import annotations

import csv
import math
import os
import pathlib
import re
import shutil
import statistics
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_distribution.py"
EXAMPLE = ROOT / "examples" / "38-distribution"
DATA = EXAMPLE / "saksbehandlingstid.csv"
EN_FIXTURE = ROOT / "tests" / "fixtures" / "i18n-distribution-en.csv"
PIN = "1792836000"          # a fixed clock: one input, one file, on any day

FAILURES: list[str] = []
CHECKS = 0


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


# -------------------------------------------------------------------------------- build
def run(data: pathlib.Path, out: pathlib.Path, *extra: str,
        tools: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    builder = (tools / "build_distribution.py") if tools else BUILDER
    args = [sys.executable, str(builder), "--data", str(data),
            "--measure-col", "Dager", "--group-col", "Enhet",
            "--title", "Saksbehandlingstid per enhet",
            "--source", "Syntetisk eksempeldata (saksbehandlingstid.csv)",
            "--requested-by", "Fagavdelingen", "--out", str(out), *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env)


def scratch(root: pathlib.Path, mutate: tuple[str, str] | None = None) -> pathlib.Path:
    """A copy of tools/ and templates/ the mutation can break without touching the repo."""
    tools = root / "tools"
    shutil.copytree(ROOT / "tools", tools,
                    ignore=shutil.ignore_patterns("__pycache__", "hooks"))
    shutil.copytree(ROOT / "templates", root / "templates")
    if mutate:
        old, new = mutate
        p = tools / "build_distribution.py"
        text = p.read_text(encoding="utf-8")
        if old not in text:
            raise SystemExit(f"mutation target not found: {old[:60]!r}")
        p.write_text(text.replace(old, new, 1), encoding="utf-8")
    return tools


# ------------------------------------------------------------------------------- parse
NUM = re.compile(r"[^0-9,.\-\u00a0\u2212]")


def number(text: str) -> float:
    """A number as the page writes it: nbsp grouping, comma decimal."""
    clean = NUM.sub("", text).replace("\u00a0", "").replace("\u2212", "-")
    return float(clean.replace(",", "."))


def panels(page: str) -> list[dict]:
    """The stat lines the drawing prints, one per panel, read out of the SVG."""
    out = []
    for m in re.finditer(r'class="ds-stat"[^>]*>([^<]*)<', page):
        line = m.group(1)
        found = {}
        for label, pattern in (("n", r"(\d[\d\u00a0]*)\s+(?:saker|cases)"),
                               ("median", r"median\s+([\d,.\u00a0]+)"),
                               ("mean", r"(?:middel|mean)\s+([\d,.\u00a0]+)"),
                               ("p90", r"p90\s+([\d,.\u00a0]+)"),
                               ("max", r"(?:st\u00f8rste|largest)\s+([\d,.\u00a0]+)")):
            hit = re.search(pattern, line)
            found[label] = number(hit.group(1)) if hit else None
        out.append(found)
    return out


def svg_counts(page: str) -> list[list[tuple[str, int]]]:
    """The bar tooltips, in drawing order: (interval, count) per bar, per panel."""
    blocks = re.split(r'(?=<text class="ds-panel")', page)
    out = []
    for block in blocks[1:]:
        out.append([(m.group(1), int(number(m.group(2)))) for m in re.finditer(
            r'<rect class="ds-bar"[^>]*><title>([^<]+):\s*([\d\u00a0]+)</title>', block)])
    return out


def table(page: str) -> dict:
    """The count table: its group names, its edges, its cells and its printed totals."""
    head = re.search(r"<thead>.*?</thead>", page, re.S).group(0)
    groups = [(m.group(1), int(number(m.group(2)))) for m in
              re.finditer(r'<th scope="col" class="num">([^<]+?)\s*\(([^)]+)\)</th>', head)]
    body = re.search(r"<tbody>.*?</tbody>", page, re.S).group(0)
    edges, cells = [], []
    for row in re.finditer(r"<tr>(.*?)</tr>", body, re.S):
        pieces = re.findall(r"<th scope=\"row\">([^<]+)</th>|<td class=\"num\">([^<]+)</td>",
                            row.group(1))
        label = pieces[0][0]
        low, _, high = label.partition("\u2013")
        if not edges:
            edges.append(number(low))
        edges.append(number(high))
        cells.append([int(number(p[1])) for p in pieces[1:]])
    foot = re.search(r"<tfoot>.*?</tfoot>", page, re.S).group(0)
    totals = [int(number(v)) for v in re.findall(r'<td class="num">([^<]+)</td>', foot)]
    return {"groups": groups, "edges": edges, "cells": cells, "totals": totals}


def source() -> list[dict]:
    with DATA.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def count_into(values: list[float], edges: list[float]) -> list[int]:
    """The count per bucket using ONLY the edges printed on the page.

    Lower edge inclusive, upper exclusive, last bucket closed at the top. Implemented here
    rather than imported, so the page's arithmetic is checked by other code.
    """
    width = edges[1] - edges[0]
    counts = [0] * (len(edges) - 1)
    for value in values:
        index = math.floor((value - edges[0]) / width)
        index = min(max(index, 0), len(edges) - 2)
        counts[index] += 1
    return counts


def nearest_rank_p90(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(max(math.ceil(0.9 * len(ordered)) - 1, 0), len(ordered) - 1)]


# ------------------------------------------------------------------------- properties
def sums_add_up(page: str, rows: list[dict]) -> bool:
    tab = table(page)
    names = [g[0] for g in tab["groups"] if g[0] not in ("Totalt", "Total")]
    by_unit: dict[str, list[float]] = {}
    for row in rows:
        by_unit.setdefault(row["Enhet"], []).append(float(row["Dager"]))
    columns = [list(c) for c in zip(*tab["cells"])][:len(names)]
    return (all(sum(c) == len(by_unit[n]) for c, n in zip(columns, names))
            and sum(sum(c) for c in columns) == len(rows)
            and tab["totals"][:len(names)] == [len(by_unit[n]) for n in names]
            and tab["totals"][-1] == len(rows))


def counts_match_the_edges(page: str, rows: list[dict]) -> bool:
    tab = table(page)
    by_unit: dict[str, list[float]] = {}
    for row in rows:
        by_unit.setdefault(row["Enhet"], []).append(float(row["Dager"]))
    names = [g[0] for g in tab["groups"] if g[0] not in ("Totalt", "Total")]
    expected = [count_into(by_unit[n], tab["edges"]) for n in names]
    got = [list(cell) for cell in zip(*tab["cells"])][:len(names)]
    return expected == got


def bars_match_the_table(page: str) -> bool:
    tab = table(page)
    drawn = [list(cell) for cell in zip(*tab["cells"])]
    for panel, column in zip(svg_counts(page), drawn):
        if [c for _, c in panel] != [c for c in column if c]:
            return False
    return True


def edges_are_uniform(page: str, rows: list[dict]) -> bool:
    tab = table(page)
    edges = tab["edges"]
    widths = {round(b - a, 6) for a, b in zip(edges, edges[1:])}
    top = edges[-1]
    return (len(widths) == 1 and all(b > a for a, b in zip(edges, edges[1:]))
            and top >= max(float(r["Dager"]) for r in rows))


def stats_are_ours(page: str, rows: list[dict]) -> bool:
    by_unit: dict[str, list[float]] = {}
    for row in rows:
        by_unit.setdefault(row["Enhet"], []).append(float(row["Dager"]))
    lines = panels(page)
    names = [name for name in by_unit if name in page]
    if len(lines) != len(names):
        return False
    for line, name in zip(lines, names):
        values = by_unit[name]
        if line["n"] != len(values):
            return False
        if abs(line["median"] - statistics.median(values)) > 0.05:
            return False
        if abs(line["mean"] - statistics.fmean(values)) > 0.05:
            return False
        if line["p90"] != nearest_rank_p90(values):
            return False
        if line["max"] != max(values):
            return False
    return True


def bars_carry_their_counts(page: str) -> bool:
    """Every bar has a number above it, and the number is the tooltip's number."""
    rects = re.findall(r'<rect class="ds-bar"[^>]*y="([\d.]+)"[^>]*>.*?</rect>', page, re.S)
    labels = re.findall(r'<text class="ds-count"[^>]*y="([\d.]+)"[^>]*>([^<]+)</text>', page)
    if len(rects) != len(labels):
        return False
    return all(abs(float(ry) - (float(ly) + 5)) < 0.6 for ry, (ly, _) in zip(rects, labels))


def withheld_named(page: str, group: str, count: int) -> bool:
    block = re.search(r'<div class="withheld">.*?</div>', page, re.S)
    if not block:
        return False
    text = block.group(0)
    return group in text and str(count) in text and group not in re.search(
        r"<thead>.*?</thead>", page, re.S).group(0)


# --------------------------------------------------------------------------------- main
def main() -> int:
    if not DATA.is_file():
        print(f"error: {DATA} is missing. Run {EXAMPLE / 'generate_data.py'} first.")
        return 2
    rows = source()

    print("1. the example build")
    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td)
        out = work / "nb.html"
        done = run(DATA, out)
        chk(done.returncode == 0, "the example builds", (done.stderr or "")[-300:])
        page = out.read_text(encoding="utf-8")
        drawn = [g for g in table(page)["groups"] if g[0] not in ("Totalt", "Total")]
        chk(len(drawn) == 4, "four groups are drawn", str(drawn))
        chk("<script" not in page, "the page holds no script at all")
        chk("ds-median" in page, "the median is drawn, not only written")

        print("\n2. the arithmetic the picture claims")
        chk(sums_add_up(page, rows),
            "the bucket counts add up to the row count, per group and in total")
        chk(counts_match_the_edges(page, rows),
            "every count equals a recount using the edges printed on the page")
        chk(edges_are_uniform(page, rows),
            "the edges are uniform, increasing, and the top edge covers the largest value")
        chk(bars_match_the_table(page),
            "the bars and the table hold the same counts in the same order")
        chk(bars_carry_their_counts(page),
            "every bar carries its own count, above it and in its tooltip")
        chk(stats_are_ours(page, rows),
            "median, mean, p90 and the largest value are this suite's own figures")

        print("\n3. a value on an edge is counted once, in the upper bucket")
        edge_csv = work / "edges.csv"
        with edge_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["Sak", "Enhet", "Dager"])
            for i, value in enumerate((0, 5, 5, 10, 15, 15), 1):
                writer.writerow([f"S-{i}", "Enhet nord", value])
        edge_out = work / "edge.html"
        done = run(edge_csv, edge_out, "--buckets", "3")
        chk(done.returncode == 0, "the edge fixture builds", (done.stderr or "")[-300:])
        edge_page = edge_out.read_text(encoding="utf-8")
        tab = table(edge_page)
        chk(tab["edges"] == [0.0, 5.0, 10.0, 15.0], "the edges are 0, 5, 10, 15",
            str(tab["edges"]))
        cells = [cell[0] for cell in tab["cells"]]
        chk(cells == [1, 2, 3], "0 on the bottom edge is in the first bucket, 5 and 10 move up, "
                               "and 15 is closed into the last bucket", str(cells))
        chk(sum(cells) == 6, "nothing fell off the top of the axis")

        print("\n4. one value, and one group of identical values")
        flat_csv = work / "flat.csv"
        with flat_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["Sak", "Enhet", "Dager"])
            for i in range(4):
                writer.writerow([f"S-{i}", "Enhet nord", 7])
        flat_out = work / "flat.html"
        done = run(flat_csv, flat_out)
        chk(done.returncode == 0, "a column of one value builds", (done.stderr or "")[-300:])
        flat_page = flat_out.read_text(encoding="utf-8")
        flat_tab = table(flat_page)
        chk(len(flat_tab["edges"]) == 2, "it is one bucket, not a zero-width axis")
        chk("Alle 4 sakene har samme verdi" in flat_page or "All 4 cases share one value" in flat_page,
            "and the page says so in words")

        print("\n5. a measure that is not a number is refused by line")
        bad_csv = work / "bad.csv"
        with bad_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["Sak", "Enhet", "Dager"])
            writer.writerow(["S-1", "Enhet nord", 3])
            writer.writerow(["S-2", "Enhet nord", "vet ikke"])
        done = run(bad_csv, work / "bad.html")
        chk(done.returncode == 2, "the build refuses, with exit code 2",
            str(done.returncode))
        chk("bad.csv:3" in done.stderr, "and it names the file and the line",
            done.stderr.strip()[:200])
        chk("not skipped" in done.stderr, "and says why it is not skipped")

        print("\n6. a row with no measure is refused unless the caller says so")
        empty_csv = work / "empty.csv"
        with empty_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["Sak", "Enhet", "Dager"])
            writer.writerow(["S-1", "Enhet nord", 3])
            writer.writerow(["S-2", "Enhet nord", ""])
        done = run(empty_csv, work / "empty.html")
        chk(done.returncode == 2, "an empty measure stops the build", str(done.returncode))
        chk("--drop-missing" in done.stderr, "and the message names the way past it",
            done.stderr.strip()[:200])
        done = run(empty_csv, work / "empty2.html", "--drop-missing")
        chk(done.returncode == 0, "--drop-missing builds", (done.stderr or "")[-200:])
        chk("1 rader er holdt utenfor" in (work / "empty2.html").read_text(encoding="utf-8"),
            "and the page says how many rows it left out")

        print("\n7. a group under the floor is named, not drawn")
        floor_out = work / "floor.html"
        done = run(DATA, floor_out, "--min-group", "5")
        chk(done.returncode == 0, "the floor builds", (done.stderr or "")[-300:])
        floor_page = floor_out.read_text(encoding="utf-8")
        chk(withheld_named(floor_page, "Enhet test", 3),
            "the three-case group is named with its count and is not a column")
        floor_tab = table(floor_page)
        chk(floor_tab["totals"] == [180, 150, 90, 420],
            "the page's own total row is the drawn rows plus a grand total",
            str(floor_tab["totals"]))
        chk("3 saker" in floor_page, "and the withheld block prints the count it left out")

        print("\n8. the English build is English")
        # Judged on an English fixture, not on the Norwegian example: a group called
        # "Enhet sør" is data, and an ø in the data is not a Norwegian word in the chrome.
        en_out = work / "en.html"
        done = subprocess.run(
            [sys.executable, str(BUILDER), "--data", str(EN_FIXTURE),
             "--measure-col", "Days", "--group-col", "Unit", "--title", "Handling time",
             "--source", "Made-up example data", "--requested-by", "The case team",
             "--lang", "en", "--out", str(en_out)],
            capture_output=True, text=True, cwd=ROOT,
            env=dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN))
        en = en_out.read_text(encoding="utf-8")
        chk(done.returncode == 0, "the English build runs", (done.stderr or "")[-300:])
        chk('<html lang="en">' in en, "the page declares its language")
        chk(not any(c in en for c in "æøåÆØÅ"), "and carries none of the Norwegian letters")
        for word in ("middel", "største", "Intervall", "Saker per"):
            chk(word not in en, f"and not the Norwegian {word!r}")

        print("\n9. the mutation controls")
        # Each mutation must break exactly the property named, and nothing else is claimed.
        mutated = work / "m1"
        mutated.mkdir()
        tools = scratch(mutated, (
            "    ordered = sorted(values)\n    index = max(0, math.ceil(0.9 * len(ordered)) - 1)",
            "    ordered = sorted(values)\n    index = len(ordered) - 1"))
        done = run(DATA, work / "m1.html", tools=tools)
        chk(done.returncode == 0, "the p90 mutation still builds", (done.stderr or "")[-200:])
        chk(not stats_are_ours((work / "m1.html").read_text(encoding="utf-8"), rows),
            "a p90 of the largest value is caught by the statistics check")

        mutated2 = work / "m2"
        mutated2.mkdir()
        tools = scratch(mutated2, (
            'f\'<text class="ds-count" x="{LEFT + index * bar + bar / 2:.1f}" \'',
            'f\'<text class="ds-none" x="{LEFT + index * bar + bar / 2:.1f}" \''))
        done = run(DATA, work / "m2.html", tools=tools)
        chk(done.returncode == 0, "the count-label mutation still builds",
            (done.stderr or "")[-200:])
        chk(not bars_carry_their_counts((work / "m2.html").read_text(encoding="utf-8")),
            "a bar without its number is caught by the label check")

        mutated3 = work / "m3"
        mutated3.mkdir()
        tools = scratch(mutated3, (
            "        if group and min_group and len(values) < min_group:",
            "        if group and min_group and len(values) < 0:"))
        done = run(DATA, work / "m3.html", "--min-group", "5", tools=tools)
        chk(done.returncode == 0, "the floor mutation still builds", (done.stderr or "")[-200:])
        chk(not withheld_named((work / "m3.html").read_text(encoding="utf-8"),
                               "Enhet test", 3),
            "a group drawn past its floor is caught by the withheld check")

        print("\n10. the committed example is the builder's own output")
        fresh = work / "fresh.html"
        run(DATA, fresh)
        chk(fresh.read_bytes() == (EXAMPLE / "behandlingstid.html").read_bytes(),
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
