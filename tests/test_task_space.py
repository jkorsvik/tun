#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Independent checks for the CSV-driven task space, including three mutation controls."""
from __future__ import annotations

import csv
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_task_space.py"
DATA = ROOT / "examples" / "55-task-space" / "trinn.csv"
ARTEFACT = ROOT / "examples" / "55-task-space" / "arbeidsflyt.html"
PIN = "1792836000"
CHECKS = 0


def ok(condition: bool, message: str) -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(message)


def source_rows() -> list[dict]:
    with DATA.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def project(pos: list[float]) -> tuple[float, float]:
    x, y, z = pos
    return 400 + x * 110 + z * 35, 205 - y * 82 + z * 24


def audit(page: str, rows: list[dict]) -> None:
    match = re.search(r"var tasks=(.*?),root=document\.documentElement", page, re.S)
    ok(match is not None, "task payload is missing")
    tasks = json.loads(match.group(1))
    ok(len(tasks) == len(rows) == 7, "the payload does not have all seven steps")
    for task, row in zip(tasks, rows):
        ok(task["step"] == row["Step"], "step order changed")
        ok(task["label"] == row["Title_nb"], "Norwegian label differs from the CSV")
        ok(task["text"] == row["Description_nb"], "Norwegian description differs from the CSV")
        ok(task["pos"] == [float(row[axis]) for axis in ("X", "Y", "Z")], "payload coordinate changed")
    circles = re.findall(r'<circle class="fb-node" cx="([\d.]+)" cy="([\d.]+)"', page)
    ok(len(circles) == len(rows), "the fallback lost a node")
    for (cx, cy), row in zip(circles, rows):
        expected = project([float(row[axis]) for axis in ("X", "Y", "Z")])
        ok((float(cx), float(cy)) == (round(expected[0], 1), round(expected[1], 1)),
           "fallback geometry differs from the source coordinate")
    table = re.findall(r'<tr data-step="([^"]+)"><td>\d+</td><td>.*?</td><td>.*?</td>'
                       r'<td class="num" data-x="([^"]+)">.*?</td>'
                       r'<td class="num" data-y="([^"]+)">.*?</td>'
                       r'<td class="num" data-z="([^"]+)">.*?</td></tr>', page, re.S)
    ok(len(table) == len(rows), "the table does not carry every step")
    for (step, x, y, z), row in zip(table, rows):
        ok(step == row["Step"], "table step differs")
        ok([float(x), float(y), float(z)] == [float(row[axis]) for axis in ("X", "Y", "Z")],
           "table coordinate differs from the CSV")
    ok('document.documentElement.className += " js"' in page, "the no-JS canary is missing")
    ok("html.js.no-webgl .fallback{display:block}" in page, "the no-WebGL selector regressed")


def build(data: pathlib.Path, out: pathlib.Path, lang: str = "nb") -> subprocess.CompletedProcess:
    env = dict(os.environ, SOURCE_DATE_EPOCH=PIN, TZ="UTC")
    title = "Fra spørsmål til leser" if lang == "nb" else "From question to reader"
    source = "Syntetisk arbeidsflyt (trinn.csv)" if lang == "nb" else "Synthetic workflow (trinn.csv)"
    return subprocess.run([sys.executable, str(BUILDER), "--data", str(data), "--step", "Step",
                           "--label", "Title", "--description", "Description", "--x", "X", "--y", "Y", "--z", "Z",
                           "--title", title, "--source", source, "--requested-by", "Prosjekteier",
                           "--lang", lang, "--out", str(out)], capture_output=True, text=True, env=env)


def write_variant(path: pathlib.Path, rows: list[dict]) -> None:
    fields = ["Step", "Title_nb", "Title_en", "Description_nb", "Description_en", "X", "Y", "Z"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def static_and_mutations() -> None:
    rows = source_rows()
    page = ARTEFACT.read_text(encoding="utf-8")
    audit(page, rows)
    view = re.search(r'viewBox="0 0 (\d+) 410"', page)
    minimum = re.search(r'\.fallback-svg\{[^}]*min-width:([\d.]+)rem', page)
    ok(view and minimum and float(minimum.group(1)) * 16 == int(view.group(1)),
       "fallback drawing width can shrink its 14 px labels below the floor")
    with tempfile.TemporaryDirectory() as raw:
        work = pathlib.Path(raw)
        rebuilt = work / "rebuilt.html"
        result = build(DATA, rebuilt)
        ok(result.returncode == 0, result.stderr)
        ok(rebuilt.read_bytes() == ARTEFACT.read_bytes(), "the pinned example is not reproducible")
        english = work / "english.html"
        result = build(DATA, english, "en")
        ok(result.returncode == 0, result.stderr)
        text = english.read_text(encoding="utf-8")
        ok('lang="en"' in text and "Question" in text and "Start with the reader" in text,
           "the English build did not use the English columns")

        variants = []
        duplicate = [dict(row) for row in rows]
        duplicate[1]["Step"] = duplicate[0]["Step"]
        variants.append(("duplicate step id", duplicate, "duplicate step id"))
        overlap = [dict(row) for row in rows]
        for axis in ("X", "Y", "Z"):
            overlap[1][axis] = overlap[0][axis]
        variants.append(("duplicate coordinate", overlap, "already occupies"))
        outside = [dict(row) for row in rows]
        outside[2]["X"] = "3.5"
        variants.append(("outside display volume", outside, "outside [-3, 3]"))
        for name, variant, expected in variants:
            path = work / (name.replace(" ", "-") + ".csv")
            write_variant(path, variant)
            result = build(path, work / "refused.html")
            ok(result.returncode != 0 and expected in result.stderr, f"refusal missing for {name}: {result.stderr}")

        mutations = [
            (page.replace('cx="136.0"', 'cx="999.0"', 1), "fallback geometry"),
            (page.replace('data-x="-2.4"', 'data-x="-9.9"', 1), "table coordinate"),
            (page.replace('document.documentElement.className += " js";', "", 1), "canary"),
        ]
        for index, (mutated, expected) in enumerate(mutations, 1):
            ok(mutated != page, f"mutation {index} did not apply")
            try:
                audit(mutated, rows)
            except AssertionError as error:
                ok(expected in str(error), f"mutation {index} hit the wrong check: {error}")
            else:
                raise AssertionError(f"mutation {index} was not detected")


def browser_checks() -> None:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width, height in ((1280, 900), (390, 844)):
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(ARTEFACT.as_uri(), wait_until="load")
            ok(page.locator(".task-label").count() == 7, "the live view lost a task label")
            page.locator(".task-label").nth(4).click()
            ok(page.locator("#step-title").text_content() == "Kontroller", "task selection failed")
            ok(page.evaluate("document.scrollingElement.scrollWidth <= innerWidth"), "page overflow")
            labels = page.locator(".task-label")
            for i in range(labels.count()):
                box = labels.nth(i).bounding_box()
                ok(box["width"] > 0 and box["x"] >= 0 and box["x"] + box["width"] <= width,
                   f"task label {i} is clipped at width {width}")
            ok(not errors, f"browser errors: {errors}")
            page.close()
        context = browser.new_context(java_script_enabled=False)
        page = context.new_page(); page.goto(ARTEFACT.as_uri())
        ok(page.locator(".fallback-svg").is_visible(), "no-JS fallback is not visible")
        ok(page.locator("tbody tr").count() == 7, "no-JS table is incomplete")
        context.close()
        context = browser.new_context()
        context.add_init_script("const original=HTMLCanvasElement.prototype.getContext;"
                                "HTMLCanvasElement.prototype.getContext=function(type,...args){"
                                "if(type==='webgl')return null;return original.call(this,type,...args)}")
        page = context.new_page(); page.goto(ARTEFACT.as_uri())
        ok(page.locator("html").evaluate("el => el.classList.contains('no-webgl')"),
           "no-WebGL class did not fire")
        ok(page.locator(".fallback-svg").is_visible(), "no-WebGL fallback is not visible")
        context.close()
        browser.close()


def main() -> int:
    static_and_mutations()
    browser_checks()
    print(f"{CHECKS} checks passed, including 3 mutation controls and 3 refusal cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
