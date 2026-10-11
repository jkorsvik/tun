#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
verify_xlsx_from_file.py — proves xlsx-from-file.html actually reads a real .xlsx from
file://, in three real browser engines, not just that the file renders.

Rebuilds demo-workbook.xlsx fresh every run (build_workbook.py is deterministic — stdlib
zipfile, no cached state worth trusting), loads xlsx-from-file.html via a file:// URL,
drives the real <input type="file"> with Playwright's set_input_files (the same single
user gesture a person would make), and asserts against the rendered DOM:

  1. All 3 sheet names appear, in the order the workbook defines them.
  2. Row counts (header included) match exactly what build_workbook.py wrote.
  3. Specific cell values round-trip correctly:
       - a plain number survives (Pris = 12 for "Penn sort")
       - the explicit empty cell renders as empty, not "0" or "undefined"
       - a real Excel date serial decodes to the right ISO date
       - the æøå sheet name and æøå cell text are not mangled
  4. Zero browser console errors.

Runs this in Chromium, Firefox AND WebKit — not just one engine. Fails hard (exit != 0)
if Playwright is not importable, per repo convention: a verifier that reports success
without ever opening a browser is worse than one that reports nothing (see AGENTS.md,
tools/verify_dashboard.py).

    uv run --extra verify python examples/22-xlsx-from-file/verify_xlsx_from_file.py

Mutation self-check (confirms this verifier can actually fail, not just pass):

    python3 examples/22-xlsx-from-file/verify_xlsx_from_file.py --mutation-check

That temporarily breaks shared-string resolution in xlsx-from-file.html, re-runs the
Chromium checks expecting FAILURE, restores the original file, and reports what it saw.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.resolve().parents[1] / "tools"))
from verify_standalone_core import ENGINES, add_engines_arg  # noqa: E402
HTML = HERE / "xlsx-from-file.html"
XLSX = HERE / "demo-workbook.xlsx"

EXPECTED_SHEETS = [
    {"name": "Produkter", "row_count": 6},
    {"name": "Ordrer", "row_count": 5},
    {"name": "Kommentarer æøå", "row_count": 4},
]


def check(label: str, cond: bool, failures: list[str]) -> bool:
    print(f"    {'✓' if cond else '✗'} {label}")
    if not cond:
        failures.append(label)
    return cond


def ensure_workbook() -> None:
    sys.path.insert(0, str(HERE))
    import build_workbook  # noqa: E402

    build_workbook.build()


def run_engine(pw, engine_name: str, browser_type, failures: list[str]) -> float | None:
    print(f"\n-- {engine_name} --")
    browser = browser_type.launch()
    page = browser.new_page()
    console_errors: list[str] = []
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: console_errors.append(str(e)))

    page.goto(HTML.as_uri())
    page.set_input_files("#file-input", str(XLSX))
    try:
        page.wait_for_selector("#status.ok", timeout=15000)
    except Exception as exc:  # noqa: BLE001 - want the status text either way
        status_text = page.inner_text("#status") if page.query_selector("#status") else "?"
        check(f"page reached success status (saw: {status_text!r}, error: {exc})", False, failures)
        screenshot = HTML.with_name(f"{HTML.stem}.{engine_name}.verify.png")
        page.screenshot(path=str(screenshot), full_page=True)
        browser.close()
        return None

    sheets = page.evaluate(
        """
        () => Array.from(document.querySelectorAll('#output section')).map(section => {
          const table = section.querySelector('table');
          return {
            name: section.querySelector('h2').textContent,
            meta: section.querySelector('.sheet-meta').textContent,
            headers: Array.from(table.querySelectorAll('thead th')).map(th => th.textContent),
            rows: Array.from(table.querySelectorAll('tbody tr')).map(
              tr => Array.from(tr.querySelectorAll('td')).map(td => td.textContent)
            ),
          };
        })
        """
    )

    check(f"[{engine_name}] 3 sheets rendered", len(sheets) == len(EXPECTED_SHEETS), failures)
    for expected, actual in zip(EXPECTED_SHEETS, sheets):
        check(
            f"[{engine_name}] sheet name == {expected['name']!r} (got {actual['name']!r})",
            actual["name"] == expected["name"],
            failures,
        )
        check(
            f"[{engine_name}] {expected['name']!r} row count mentions {expected['row_count']}"
            f" (meta: {actual['meta']!r})",
            str(expected["row_count"]) in actual["meta"],
            failures,
        )

    # Sheet 1 "Produkter": the explicit empty cell + a plain number + a decoded date,
    # all on the same row ("Penn sort" has no Lagerbeholdning on purpose).
    produkter_rows = sheets[0]["rows"] if sheets else []
    penn_row = next((r for r in produkter_rows if len(r) > 1 and r[1] == "Penn sort"), None)
    check(f"[{engine_name}] 'Penn sort' row found in Produkter", penn_row is not None, failures)
    if penn_row is not None:
        check(f"[{engine_name}] Pris == '12' (number survived)", penn_row[2] == "12", failures)
        check(f"[{engine_name}] Lagerbeholdning is empty (explicit empty cell)", penn_row[3] == "", failures)
        check(f"[{engine_name}] SistOppdatert == '2024-01-10' (date decoded)", penn_row[4] == "2024-01-10", failures)

    # Sheet 2 "Ordrer": a number, an amount and a date on a named customer's row.
    ordrer_rows = sheets[1]["rows"] if len(sheets) > 1 else []
    ase_row = next((r for r in ordrer_rows if len(r) > 1 and r[1] == "Åse Lund"), None)
    check(f"[{engine_name}] 'Åse Lund' row found in Ordrer", ase_row is not None, failures)
    if ase_row is not None:
        check(f"[{engine_name}] Beløp == '899' for Åse Lund", ase_row[2] == "899", failures)
        check(f"[{engine_name}] Bestillingsdato == '2024-03-18' for Åse Lund", ase_row[3] == "2024-03-18", failures)

    # Sheet 3: the æøå sheet name already asserted above; also check the free-text æøå
    # cell content was not mangled by the text decoder.
    comment_rows = sheets[2]["rows"] if len(sheets) > 2 else []
    has_full_alphabet_row = any(
        len(r) > 1 and "æ Æ ø Ø å Å" in r[1] for r in comment_rows
    )
    check(f"[{engine_name}] æøå comment text intact", has_full_alphabet_row, failures)

    check(f"[{engine_name}] zero console errors", len(console_errors) == 0, failures)
    if console_errors:
        print(f"      first error: {console_errors[0][:200]}")

    timing_text = page.inner_text("#timing")
    match = re.search(r"på ([\d.]+) ms", timing_text)
    parse_ms = float(match.group(1)) if match else None
    print(f"    timing: {timing_text.strip()}")

    screenshot = HTML.with_name(f"{HTML.stem}.{engine_name}.verify.png")
    page.screenshot(path=str(screenshot), full_page=True)
    print(f"    screenshot: {screenshot.name}")

    browser.close()
    return parse_ms


def run_all_engines(pw, engines) -> tuple[list[str], dict[str, float | None]]:
    failures: list[str] = []
    timings: dict[str, float | None] = {}
    for name, browser_type in engines:
        timings[name] = run_engine(pw, name, browser_type, failures)
    return failures, timings


def mutation_check() -> int:
    """Break the parser on purpose, confirm the verifier fails, then restore the file."""
    original = HTML.read_text(encoding="utf-8")
    needle = "value = sharedStrings[Number(vEl.textContent)];"
    if needle not in original:
        print(f"✗ mutation anchor not found in {HTML.name} — cannot mutate", file=sys.stderr)
        return 2
    mutated = original.replace(needle, "value = 'MUTATED-' + vEl.textContent;")
    HTML.write_text(mutated, encoding="utf-8")
    print("Mutated shared-string resolution. Re-running checks in Chromium, expecting FAILURE...")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        HTML.write_text(original, encoding="utf-8")
        print("✗ playwright not installed — cannot run the mutation check", file=sys.stderr)
        return 1

    ensure_workbook()
    try:
        with sync_playwright() as pw:
            failures, _ = run_all_engines(pw, [("chromium", pw.chromium)])
    finally:
        HTML.write_text(original, encoding="utf-8")
        print(f"Restored {HTML.name} to its original content.")

    if failures:
        print(f"\n✓ mutation check PASSED: the verifier correctly failed "
              f"({len(failures)} check(s) failed when the parser was broken).")
        return 0
    print("\n✗ mutation check FAILED: the verifier reported success against a broken parser. "
          "That means the checks are not actually exercising shared-string resolution.")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mutation-check", action="store_true")
    add_engines_arg(ap, default=ENGINES)
    args = ap.parse_args()
    if args.mutation_check:
        return mutation_check()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "✗ FAIL — playwright not installed. The browser checks (render, console, "
            "sheet/cell assertions, screenshots) could not run, so this file has NOT "
            "been verified.\n  Install with: uv sync --extra verify && "
            "uv run playwright install chromium firefox webkit",
            file=sys.stderr,
        )
        return 1

    ensure_workbook()
    if not XLSX.exists():
        print(f"✗ {XLSX} still missing after build_workbook.build()", file=sys.stderr)
        return 2

    with sync_playwright() as pw:
        engines = [(name, getattr(pw, name)) for name in args.engines]
        failures, timings = run_all_engines(pw, engines)

    print("\n" + "─" * 60)
    print("Parse times (ms):")
    for name, ms in timings.items():
        print(f"  {name:<10} {ms if ms is not None else 'N/A'}")

    if failures:
        print(f"\n✗ FAIL — {len(failures)} check(s) failed:")
        for f in failures:
            print(f"    • {f}")
        return 1

    print(f"\n✓ PASS — {', '.join(args.engines)} parsed demo-workbook.xlsx correctly, "
          "zero console errors, screenshots written for human review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
