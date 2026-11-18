#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build, check, or open the shared synthetic AI recipe dashboard."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "docs/ai-recipes/fixtures"
DEFAULT = ROOT / "work/ai-recipes/tun-recipe.html"
SOURCE = "Synthetic Tún recipe fixture (excuses.csv)"


def reference(target: Path, expected: dict) -> None:
    fixture = FIXTURES / "excuses.csv"
    with fixture.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    filtered = [row for row in rows if row["Category"] == expected["filter"]]
    facts = len(rows), sum(int(row["Count"]) for row in rows), len(filtered), sum(int(row["Count"]) for row in filtered)
    if facts != tuple(expected[key] for key in ("rows", "total", "filtered_rows", "filtered_total")):
        raise ValueError("Fixture does not match the expected row counts and totals")
    env = {k: v for k, v in os.environ.items() if not k.startswith("TUN_")}
    env.update(SOURCE_DATE_EPOCH="1769947200", PYTHONUTF8="1")
    subprocess.run([sys.executable, str(ROOT / "tools/build_dashboard.py"), "--data", str(fixture),
                    "--lang", "en", "--title", expected["title"], "--dimension", "Category",
                    "--measure", "Count", "--time", "Month", "--filters", "Category",
                    "--kpis", "total,rows,distinct", "--mode", "bundled", "--source", SOURCE,
                    "--requested-by", "Tún recipe reader",
                    "--out", str(target)], env=env, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    text = target.read_text(encoding="utf-8")
    # Identify the recipe, fixture, and exact builder output independently of Git availability.
    fixture_digest = hashlib.sha256(fixture.read_text(encoding="utf-8").encode()).hexdigest()
    stamp = (f"Tún AI recipe contract: {expected['contract']}; "
             f"fixture SHA-256: {fixture_digest}; "
             f"canonical output SHA-256: {hashlib.sha256(text.encode()).hexdigest()}")
    target.write_bytes(text.replace("<!DOCTYPE html>", f"<!DOCTYPE html>\n<!-- {stamp} -->", 1).encode())


def check(candidate: Path, expected: dict) -> None:
    with tempfile.TemporaryDirectory() as folder:
        fresh = Path(folder) / expected["filename"]
        reference(fresh, expected)
        received = candidate.read_text(encoding="utf-8")
        if received != fresh.read_text(encoding="utf-8"):
            raise ValueError("Not the canonical file for this toolkit and fixture. Rebuild with the same toolkit or download the original HTML again.")
    if "PROVENANCE" not in received or "Made with   : Tún — tun.community" not in received:
        raise ValueError("Missing Tún provenance or Origin Notice")
    print(f"Static PASS: {expected['rows']} rows, total {expected['total']}, exact canonical content and Origin Notice. Browser not checked by this step.")


def browser(candidate: Path, expected: dict) -> None:
    try:
        from playwright.sync_api import Error, expect, sync_playwright
    except ImportError as exc:
        raise ValueError("Browser check blocked: provision Playwright and Chromium as shown in the verification guide.") from exc
    requests = []
    errors = []
    try:
        with sync_playwright() as pw:
            instance = pw.chromium.launch()
            context = instance.new_context(offline=True, service_workers="block", viewport={"width": 1440, "height": 1000})
            entry = candidate.as_uri()

            def allowed(url):
                return url == entry or urlsplit(url).scheme in ("data", "blob")

            context.route("**/*", lambda route: route.continue_() if allowed(route.request.url) else route.abort())
            page = context.new_page()
            page.on("request", lambda request: requests.append(request.url) if not allowed(request.url) else None)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.goto(entry, timeout=15000)
            expect(page.get_by_role("heading", name=expected["title"], exact=True)).to_be_visible()
            total = page.locator("#kpis .kpi .value").first
            rows = page.locator("#tbl tbody tr")
            expect(total).to_have_text(str(expected["total"]))
            expect(rows).to_have_count(expected["rows"])
            expect(page.locator("#chart1 .bar").first).to_be_visible()
            page.locator("#f_Category").select_option(label=expected["filter"])
            expect(total).to_have_text(str(expected["filtered_total"]))
            expect(rows).to_have_count(expected["filtered_rows"])
            page.locator("#reset").click()
            expect(total).to_have_text(str(expected["total"]))
            expect(rows).to_have_count(expected["rows"])
            shot = candidate.with_suffix(".verify.png")
            page.screenshot(path=shot, full_page=True, animations="disabled")
            instance.close()
    except (Error, AssertionError) as exc:
        raise ValueError(f"Chromium could not verify the file: {exc}") from exc
    if errors or requests:
        raise ValueError(f"Offline browser failed: {len(errors)} page/console error(s), {len(requests)} external request(s)")
    print(f"Browser PASS: Chromium file:// offline, filter and reset work, zero external requests and errors. Inspect {shot} before sharing.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    modes.add_parser("build", help=f"build {DEFAULT.relative_to(ROOT)}")
    for mode in ("check", "browser"):
        sub = modes.add_parser(mode)
        sub.add_argument("html", type=Path, nargs="?", default=DEFAULT)
    args = parser.parse_args()
    try:
        expected = json.loads((FIXTURES / "expected-assertions.json").read_text(encoding="utf-8"))
        if args.mode == "build":
            with tempfile.TemporaryDirectory() as folder:
                generated = Path(folder) / expected["filename"]
                reference(generated, expected)
                DEFAULT.parent.mkdir(parents=True, exist_ok=True)
                DEFAULT.write_bytes(generated.read_bytes())
            print(f"Built {DEFAULT}. This is a synthetic dashboard, not a browser verification result.")
        else:
            candidate = args.html.resolve()
            check(candidate, expected)
            if args.mode == "browser":
                browser(candidate, expected)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
