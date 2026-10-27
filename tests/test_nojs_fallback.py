#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The file says something true with scripting blocked.

ROADMAP A3, docs/11 §3c. Quick Look on iOS and macOS — the engine behind tapping an HTML
attachment in Messages, Mail or Files — does not run JavaScript. Before this change the
dashboard showed a header, an empty KPI row, two empty chart boxes and an empty table: a
page that reads as broken even though nothing threw.

So the build writes the facts it already knew into the markup, and a canary class on
`<html>` decides which view is shown. The cube needs the same treatment for a worse
reason: without scripting it never decodes, so it showed the boot line forever. This test
opens both files the way a recipient would:

  1. scripting off: the static view is visible, the JS containers are not, the totals on
     screen equal the totals in the CSV, and no element renders under 14 px;
  2. scripting on: the static view is hidden and the live view is there instead;
  3. mutation: delete the canary `<script>` and the static view must appear — proving the
     class, not some accident of the markup, decides which view a reader gets.

    uv run --extra verify python tests/test_nojs_fallback.py
"""
from __future__ import annotations

import csv
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_dashboard.py"
CUBE_BUILDER = ROOT / "tools" / "build_cube_dashboard.py"
DATA = ROOT / "examples" / "01-hello-dashboard" / "salgsdata.csv"
ARGS = ["--title", "Salg per region og produkt 2026", "--dimension", "Produkt",
        "--measure", "Belop", "--time", "Maaned", "--filters", "Region,Produkt,Kanal",
        "--source", "Eksempeldata (syntetisk)", "--requested-by", "Prosjekteier"]

checks = failed = 0


def check(ok: bool, what: str, detail: str = "") -> None:
    global checks, failed
    checks += 1
    print(f"  {'✓' if ok else '✗'} {what}" + ("" if ok else f" — {detail}"))
    if not ok:
        failed += 1


def truth() -> tuple[int, float, int]:
    rows = list(csv.DictReader(DATA.open(encoding="utf-8")))
    total = sum(float(r["Belop"].replace(",", ".")) for r in rows)
    return len(rows), total, len({r["Produkt"] for r in rows})


def digit_groups(text: str) -> str:
    """Digits only: the static view groups with spaces and a comma, so compare the number,
    not the punctuation."""
    return re.sub(r"\D", "", text)



# ── the cube ────────────────────────────────────────────────────────────────
CUBE_ARGS = ["--dims", "region,kategori", "--time", "dato", "--time-grain", "month",
             "--measures", "belop:sum:kr,antall:sum", "--title", "Liten terning",
             "--requested-by", "Test"]
CUBE_CSV = """region,kategori,kanal,dato,belop,antall
Oslo,Mat,Nett,2026-01-05,120.5,3
Oslo,Reise,Nett,2026-01-19,80.0,1
Bergen,Mat,Filial,2026-02-02,45.25,2
Bergen,Reise,Filial,2026-02-16,300.0,5
"""


def cube_case(tmp: pathlib.Path, browsers: dict, sync_playwright) -> None:
    data = tmp / "cube.csv"
    data.write_text(CUBE_CSV, encoding="utf-8")
    out = tmp / "cube.html"
    r = subprocess.run([sys.executable, str(CUBE_BUILDER), "--data", str(data), *CUBE_ARGS,
                        "--out", str(out)],
                       capture_output=True, text=True, cwd=ROOT, timeout=120)
    check(out.is_file(), "the cube builds", (r.stderr or r.stdout)[-200:])
    if not out.is_file():
        return
    # The cube's own arithmetic: 4 rows, 2 regions x 2 categories x 2 months = 8 cells,
    # 4 of them filled, over three dimensions (the two plus the month).
    expect = {"4": "rows", "8": "cells", "3": "dimensions", "50%": "density"}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(java_script_enabled=False,
                                  viewport={"width": 390, "height": 900})
        page = ctx.new_page()
        page.goto(out.resolve().as_uri())
        page.wait_for_timeout(200)
        got = page.evaluate("""() => {
            const vis = el => el && getComputedStyle(el).display !== 'none';
            return {
                static_shown: vis(document.getElementById('nojs')),
                boot_shown: vis(document.getElementById('boot')),
                app_shown: vis(document.getElementById('app')),
                facts: [...document.querySelectorAll('#nojs dd')].map(d => d.textContent),
                dims: [...document.querySelectorAll('#nojs li')].map(l => l.textContent),
                overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
                min_font: Math.min(...[...document.querySelectorAll('#nojs *')]
                    .map(e => parseFloat(getComputedStyle(e).fontSize))),
            };
        }""")
        check(got["static_shown"], "cube, no JS: the static view is the page")
        check(not got["boot_shown"] and not got["app_shown"],
              "cube, no JS: the boot line and the app are hidden",
              f"boot={got['boot_shown']} app={got['app_shown']}")
        check([f.strip() for f in got["facts"]] == list(expect),
              "cube, no JS: rows, cells, dimensions and density match the cube's own arithmetic",
              f"{got['facts']} vs {list(expect)}")
        check(got["dims"] == ["region", "kategori", "dato"],
              "cube, no JS: the dimensions are named", str(got["dims"]))
        check(not got["overflow"], "cube, no JS: nothing overflows 390 px")
        check(got["min_font"] >= 13.99, "cube, no JS: no text under 14 px", f"{got['min_font']} px")
        ctx.close()

        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(out.resolve().as_uri())
        page.wait_for_timeout(900)
        live = page.evaluate("""() => ({
            static_shown: getComputedStyle(document.getElementById('nojs')).display !== 'none',
            app_shown: !document.getElementById('app').hidden,
        })""")
        check(not live["static_shown"] and live["app_shown"],
              "cube, with JS: the live view replaces the static one", str(live))
        check(not errors, "cube, with JS: no page error", str(errors)[:160])
        page.close()

        mutated = tmp / "cube-no-canary.html"
        mutated.write_text(re.sub(r'<script>document\.documentElement\.className\+=" js"</script>',
                                  "", out.read_text(encoding="utf-8"), count=1), encoding="utf-8")
        page = browser.new_page(viewport={"width": 390, "height": 900})
        page.goto(mutated.resolve().as_uri())
        page.wait_for_timeout(400)
        after = page.evaluate("""() => ({
            has_class: document.documentElement.classList.contains('js'),
            static_shown: getComputedStyle(document.getElementById('nojs')).display !== 'none',
        })""")
        check(not after["has_class"] and after["static_shown"],
              "cube, mutation: without the canary the file falls back to the static view",
              str(after))
        page.close()
        browser.close()

def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ✗ playwright is not installed, so nothing was measured")
        print("    install: uv sync --extra verify && uv run playwright install chromium")
        return 1

    rows, total, dims = truth()

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        out = tmp / "dash.html"
        r = subprocess.run([sys.executable, str(BUILDER), "--data", str(DATA), *ARGS,
                            "--out", str(out)],
                           capture_output=True, text=True, cwd=ROOT, timeout=120)
        check(out.is_file(), "the example builds", (r.stderr or r.stdout)[-200:])
        if not out.is_file():
            print(f"\n{checks - failed}/{checks} checks passed")
            return 1

        with sync_playwright() as p:
            browser = p.chromium.launch()

            # 1. the way Quick Look serves it
            ctx = browser.new_context(java_script_enabled=False,
                                      viewport={"width": 390, "height": 900})
            page = ctx.new_page()
            page.goto(out.resolve().as_uri())
            page.wait_for_timeout(200)
            got = page.evaluate("""() => {
                const vis = el => el && getComputedStyle(el).display !== 'none';
                const facts = [...document.querySelectorAll('#nojs dd')].map(d => d.textContent);
                return {
                    static_shown: vis(document.getElementById('nojs')),
                    kpis_shown: vis(document.getElementById('kpis')),
                    chart_shown: vis(document.querySelector('.grid')),
                    table_shown: vis(document.querySelector('.table-wrap')),
                    empty_cards: [...document.querySelectorAll('main>section.card')]
                        .filter(s => getComputedStyle(s).display !== 'none').length,
                    facts,
                    rows: document.querySelectorAll('#nojs tbody tr').length,
                    overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
                    min_font: Math.min(...[...document.querySelectorAll('#nojs *')]
                        .map(e => parseFloat(getComputedStyle(e).fontSize))),
                    text: document.body.innerText.length,
                };
            }""")
            check(got["static_shown"], "no JS: the static view is the page")
            check(not got["kpis_shown"] and not got["chart_shown"] and not got["table_shown"],
                  "no JS: the empty JS containers are hidden",
                  f"kpis={got['kpis_shown']} charts={got['chart_shown']} table={got['table_shown']}")
            check(got["empty_cards"] == 0, "no JS: no empty card is left behind",
                  str(got["empty_cards"]))
            # The static view shows one decimal, so compare at that precision.
            check(got["facts"] and digit_groups(got["facts"][0])
                  == digit_groups(f"{round(total, 1):.1f}"),
                  "no JS: the total matches the CSV",
                  f"{got['facts']} vs {total:.2f}")
            check(len(got["facts"]) > 1 and digit_groups(got["facts"][1]) == str(rows),
                  "no JS: the row count matches the CSV", str(got["facts"][1:2]))
            check(len(got["facts"]) > 2 and digit_groups(got["facts"][2]) == str(dims),
                  "no JS: the distinct dimension count matches the CSV", str(got["facts"][2:3]))
            check(got["rows"] > 0, "no JS: the first rows of the file are there", str(got["rows"]))
            check(not got["overflow"], "no JS: nothing overflows a 390 px screen")
            check(got["min_font"] >= 13.99, "no JS: no text under 14 px", f"{got['min_font']} px")
            check(got["text"] > 400, "no JS: the page still says something", f"{got['text']} chars")
            ctx.close()

            # 2. with scripting, the live view
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(out.resolve().as_uri())
            page.wait_for_selector("#kpis .kpi")
            live = page.evaluate("""() => ({
                static_shown: getComputedStyle(document.getElementById('nojs')).display !== 'none',
                kpis: document.querySelectorAll('#kpis .kpi').length,
                rows: document.querySelectorAll('#tbl tbody tr').length,
            })""")
            check(not live["static_shown"], "with JS: the static view is hidden")
            check(live["kpis"] == 4 and live["rows"] > 0, "with JS: the live view renders",
                  str(live))
            check(not errors, "with JS: no page error", str(errors)[:160])
            page.close()

            # 3. the mutation: without the canary, the class never lands
            mutated = tmp / "no-canary.html"
            mutated.write_text(re.sub(r'<script>document\.documentElement\.className\+=" js"</script>',
                                      "", out.read_text(encoding="utf-8"), count=1),
                               encoding="utf-8")
            page = browser.new_page(viewport={"width": 390, "height": 900})
            page.goto(mutated.resolve().as_uri())
            page.wait_for_timeout(400)
            after = page.evaluate("""() => ({
                has_class: document.documentElement.classList.contains('js'),
                static_shown: getComputedStyle(document.getElementById('nojs')).display !== 'none',
            })""")
            check(not after["has_class"] and after["static_shown"],
                  "mutation: without the canary the file falls back to the static view, so the "
                  "class is what decides", str(after))
            page.close()
            browser.close()

        cube_case(tmp, {}, sync_playwright)

    print()
    print(f"{checks - failed}/{checks} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
