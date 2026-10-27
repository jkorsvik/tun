#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The cube lets a reader take the numbers out, and what it gives them is true.

A reader who has just filtered a cube to the three regions they own will want those
numbers in Excel. Before this, the only way out was retyping the table, which is how a
dashboard becomes a screenshot with extra steps.

The export is the aggregated view, not the rows: the same cells the charts and the
detail tables were drawn from, under the selection that is applied, with the source and
the selection written into the file. A CSV that outlives the page and does not say where
it came from is a number nobody can trace back (AGENTS.md, provenance is mandatory).

What is checked, and each check looks at a real file downloaded from a real browser:

  1. the button           present, visible, and at least 44 px tall
  2. the file             downloads on click, named for the cube and the build date
  3. provenance           the first three lines name the source, the build, the selection
  4. shape                one header row, then every dimension's every value, then a total
  5. arithmetic           each dimension's values sum to the total; the total row is the
                          same aggregate the KPI shows; the filtered export agrees too
  6. numbers              decimal comma, no thousands separator, so a spreadsheet reads
                          numbers rather than text (en: the other way around)
  7. the filter           a chip click reaches the file: one value for that dimension,
                          the smaller total, and the selection line names it
  8. no scripting         the app and its export stay out of the way, the facts print
  9. mutation             a template that formats with toLocaleString must be caught by
                          check 6, or check 6 proves nothing

Needs Playwright and Chromium, and FAILS without them (AGENTS.md rule 3).

    python3 tests/test_cube_csv_export.py
"""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
DATA = REPO / "examples" / "01-hello-dashboard" / "salgsdata.csv"
DIMS = "Region,Produkt,Kanal"
TIME = "Maaned"

passed = 0
failed = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS {label}" + (f" ({detail})" if detail else ""))
    else:
        failed += 1
        print(f"  FAIL {label}" + (f" ({detail})" if detail else ""))


def build(out: pathlib.Path, lang: str = "nb", tools: pathlib.Path | None = None) -> None:
    cmd = [sys.executable, str((tools or REPO) / "tools" / "build_cube_dashboard.py"),
           "--data", str(DATA), "--title", "Salg per region, produkt og kanal",
           "--dims", DIMS, "--measure", "Belop", "--time", TIME,
           "--source", "Eksempeldata (syntetisk) - salgsdata.csv",
           "--requested-by", "Analyseteamet", "--lang", lang, "--out", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       cwd=str(tools or REPO))
    if r.returncode != 0:
        raise SystemExit(f"build failed:\n{r.stdout}\n{r.stderr}")


def lines_of(text: str) -> list[list[str]]:
    """Split the file as a reader would: the blank line after the header block stays,
    so the table has a known address (the line after it) rather than a guessed one."""
    # splitlines, not a hard-coded "\r\n": the exporter writes CRLF, and a text read
    # translates it, so a reader that names one separator reads the whole file as a
    # single line on the other. It keeps the blank line, which is the table's address.
    body = text.lstrip("\ufeff").splitlines()
    sep = ";" if ";" in body[4] else ","
    return [[split(ln, sep)] if ln == "" else split(ln, sep) for ln in body]


def split(line: str, sep: str) -> list[str]:
    """A small RFC 4180 reader: enough for what the exporter can write."""
    out, cell, quoted, i = [], "", False, 0
    while i < len(line):
        c = line[i]
        if quoted:
            if c == '"' and i + 1 < len(line) and line[i + 1] == '"':
                cell += '"'; i += 2; continue
            if c == '"':
                quoted = False; i += 1; continue
            cell += c; i += 1; continue
        if c == '"':
            quoted = True; i += 1; continue
        if c == sep:
            out.append(cell); cell = ""; i += 1; continue
        cell += c; i += 1
    out.append(cell)
    return out


NUM_NB = re.compile(r"^-?\d+(,\d{1,2})?$")
NUM_EN = re.compile(r"^-?\d+(\.\d{1,2})?$")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("FAIL: Playwright is not installed, so the export was never downloaded.")
        print("      install it with: uv sync --extra verify && uv run playwright install chromium")
        return 1

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="tun-cube-csv-"))
    nb = tmp / "cube.html"
    en = tmp / "cube-en.html"
    build(nb)
    build(en, lang="en")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(accept_downloads=True)

        def take(url: pathlib.Path) -> tuple[str, str]:
            page.goto(url.as_uri())
            page.wait_for_selector("#csv", state="visible", timeout=15000)
            return read_now()

        def read_now() -> tuple[str, str]:
            """Download whatever the page holds right now, without reloading it."""
            with page.expect_download(timeout=15000) as info:
                page.click("#csv")
            d = info.value
            return d.suggested_filename, pathlib.Path(d.path()).read_text(encoding="utf-8")

        # 1. the button is there, and it is a touch target
        page.goto(nb.as_uri())
        page.wait_for_selector("#csv", state="visible", timeout=15000)
        box = page.locator("#csv").bounding_box()
        check("the export button is visible and labelled",
              page.locator("#csv").inner_text().strip() != "")
        check("the export button is at least 44 px tall, the touch floor",
              bool(box) and box["height"] >= 44, f'{box["height"]:.0f} px' if box else "no box")
        page.emulate_media(media="print")
        check("print drops the button with the other controls",
              page.locator("#csv").is_hidden())
        page.emulate_media(media="screen")

        # 2-3. the download, its name, and what it says about itself
        name_nb, text_nb = take(nb)
        check("clicking the button downloads a file", name_nb.endswith(".csv"), name_nb)
        check("the file is named for the cube and the build date",
              name_nb.startswith("kube-") and re.search(r"\d{4}-\d{2}-\d{2}\.csv$", name_nb) is not None,
              name_nb)
        check("the file starts with a byte-order mark, so Excel reads UTF-8",
              text_nb.startswith("\ufeff"))
        rows_nb = lines_of(text_nb)
        check("the source is written into the first line",
              rows_nb[0][0].startswith("#") and "salgsdata.csv" in rows_nb[0][0], rows_nb[0][0])
        check("the build stamp and the requester are in the second line",
              "Bygget" in rows_nb[1][0] and "Analyseteamet" in rows_nb[1][0], rows_nb[1][0])
        check("the selection is stated next to the source",
              "Utvalg" in rows_nb[2][0] and "alle" in rows_nb[2][0], rows_nb[2][0][:70] + "...")
        check("a blank line separates the header block from the table", rows_nb[3] == [[""]])

        # 4. shape: header, every value of every dimension, one total
        head = rows_nb[4]
        check("the header names the five columns",
              len(head) == 5 and head[0] == "Dimensjon" and head[2] == "Belop", ";".join(head))
        table = rows_nb[5:]
        for dim in DIMS.split(",") + [TIME]:
            got = {r[1] for r in table if r[0] == dim}
            want = set(page.evaluate("d => META.labels[d]", dim))
            check(f"dimension {dim} exports exactly its values", got == want,
                  f"{len(got)} of {len(want)}")
        check("no value appears twice within a dimension",
              all(len([r for r in table if r[0] == dim]) ==
                  len({r[1] for r in table if r[0] == dim}) for dim in DIMS.split(",") + [TIME]))
        check("the last line is the total, and only it", 
              sum(1 for r in table if r[1] == "" and r[0] in ("Totalt", "Total")) == 1
              and table[-1][0] == "Totalt", table[-1][0])

        # 5. arithmetic against the same aggregate the page shows
        total_page = page.evaluate("window.__TOTAL__")
        rows_page = page.evaluate("window.__ROWS__")

        def num(cell: str) -> float:
            return float(cell.replace(" ", "").replace("\u00a0", "").replace(",", "."))

        total_csv = num(table[-1][3])
        check("the total row carries the page's own total",
              abs(total_csv - total_page) <= max(0.01, abs(total_page) * 1e-9),
              f"{total_csv} vs {total_page}")
        check("the total row carries the page's row count",
              num(table[-1][4]) == rows_page, f"{table[-1][4]} vs {rows_page}")
        for dim in DIMS.split(",") + [TIME]:
            s = sum(num(r[3]) for r in table if r[0] == dim)
            check(f"{dim} sums to the same total as the KPI",
                  abs(s - total_page) <= max(0.01, abs(total_page) * 1e-9), f"{s:.2f}")

        # 6. numbers a spreadsheet can read
        bad = [r[3] for r in table if not NUM_NB.match(r[3])]
        check("every value is a plain number with a decimal comma",
              not bad, f"{len(bad)} bad, first {bad[:2]}")
        check("a value over 1000 has no thousands separator",
              not any("." in r[3] for r in table if len(r[3]) > 4), 
              next((r[3] for r in table if len(r[3]) > 4), "none over 1000"))

        # 7. the filter reaches the file
        page.locator('.chips[data-dim="Region"] .chip').first.click()
        page.wait_for_timeout(200)
        name_f, text_f = read_now()
        rows_f = lines_of(text_f)
        table_f = rows_f[5:]
        picked = [r for r in table_f if r[0] == "Region"]
        check("a filter shrinks the file to the selected value", len(picked) == 1, f"{len(picked)}")
        check("the filtered file says which value is selected",
              "Region = " in rows_f[2][0] and "alle" not in rows_f[2][0].split(";")[0],
              rows_f[2][0][:70])
        check("the filtered total is smaller than the unfiltered one",
              num(table_f[-1][3]) < total_csv,
              f"{num(table_f[-1][3])} < {total_csv}")

        # 6b. the other locale writes the other way around
        name_en, text_en = take(en)
        rows_en = lines_of(text_en)
        check("en names the file for the cube too", name_en.startswith("cube-"), name_en)
        check("en separates with commas and writes a decimal point",
              ";" not in rows_en[4] and rows_en[4][0] == "Dimension", ",".join(rows_en[4]))
        en_table = rows_en[5:]
        check("en values use a point, never a comma",
              not [r[3] for r in en_table if not NUM_EN.match(r[3])],
              next((r[3] for r in en_table if not NUM_EN.match(r[3])), "all clean"))

        # 8. no scripting: the export must not be the only way to the facts
        nojs = browser.new_context(java_script_enabled=False)
        np = nojs.new_page()
        np.goto(nb.as_uri())
        np.wait_for_timeout(400)
        check("without scripting the app stays hidden",
              np.locator("#app").is_hidden())
        # inner_text is the RENDERED text, and the headings are uppercased by CSS,
        # so the comparison is case-insensitive; the digits prove the facts were
        # computed at build time and are not an empty shell.
        nojs_text = np.locator("#nojs").inner_text()
        check("without scripting the pre-rendered facts are readable",
              "dimensjoner" in nojs_text.lower() and bool(re.search(r"\d", nojs_text)),
              nojs_text.replace("\n", " | ")[:80])
        nojs.close()

        browser.close()

    # 9. the mutation: a formatter that groups thousands must be caught by check 6
    mut = tmp / "mut"
    mut.mkdir()
    shutil.copytree(REPO / "tools", mut / "tools")
    shutil.copytree(REPO / "templates", mut / "templates")
    tpl = mut / "templates" / "cube-dashboard.html"
    src = tpl.read_text(encoding="utf-8")
    broken = src.replace('return String(n).replace(".", "{{T:dec}}");',
                         'return n.toLocaleString("{{T:num_locale}}");')
    if broken == src:
        check("the mutation applied to the formatter", False, "csvNumber not found")
    else:
        check("the mutation applied to the formatter", True)
        tpl.write_text(broken, encoding="utf-8")
        mut_html = tmp / "mut.html"
        build(mut_html, tools=mut)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(accept_downloads=True)
            page.goto(mut_html.as_uri())
            page.wait_for_selector("#csv", state="visible", timeout=15000)
            with page.expect_download(timeout=15000) as info:
                page.click("#csv")
            text = pathlib.Path(info.value.path()).read_text(encoding="utf-8")
            browser.close()
        rows_m = lines_of(text)[5:]
        bad_m = [r[3] for r in rows_m if not NUM_NB.match(r[3])]
        check("the mutation is caught: text-formatted numbers fail check 6", bool(bad_m),
              f"{len(bad_m)} caught, first {bad_m[:1]}")

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nPASS: {passed}  FAIL: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
