#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Injected dialogs and unbalanced script tags must fail the verifier (#26).

`tools/verify_dashboard.py` used to report a clean file while the page ran an injected
`onerror=alert(1)`. Two holes made that possible: the row-25 text check counted
`<script` openings, so an injected `</script>` was invisible to it, and the browser
half listened to `console` and `pageerror` but not to `dialog`.

This suite builds a real dashboard from the committed example data, then attacks a
copy by hand. The surgery does not rely on the builder being vulnerable: it replaces
a JSON string value in `window.DASHBOARD_DATA` with `</script><img src=x
onerror=alert(1)>` and keeps the JSON string valid. A second fixture adds an
`<svg onload=alert(1)>` with no stray closing tag at all, which proves the dialog
handler is load-bearing on its own.

The gate is narrow on purpose. It sees a dialog and a script tag that cannot be
paired. An injected `<img onerror="fetch(...)">` runs with no dialog, no console
error and balanced tags, and this gate would not catch it. The dialog handler
also observes only 1200 ms in `verify_dashboard.py` and 800 ms in the core
verifier, so a `setTimeout(() => alert(1), 2000)` passes as `✓ dialog none` and
`✓ PASS`; that was measured on a file with a 2-second delayed alert.

Needs Playwright, like the other browser suites, and fails rather than skipping
without it.

    uv run --extra verify python tests/test_verify_dialog.py
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_dashboard.py"
VERIFIER = ROOT / "tools" / "verify_dashboard.py"
DATA = ROOT / "examples" / "01-hello-dashboard" / "salgsdata.csv"
ARGS = [
    "--data", str(DATA),
    "--title", "Salg per region og produkt 2026",
    "--dimension", "Produkt",
    "--measure", "Belop",
    "--time", "Maaned",
    "--filters", "Region,Produkt,Kanal",
    "--source", "Eksempeldata (syntetisk) - salgsdata.csv",
    "--requested-by", "Prosjekteier",
]
PAYLOAD = "</script><img src=x onerror=alert(1)>"
DIALOG_ONLY = '<svg onload="alert(1)"></svg>'

passed = 0
failed = 0


def chk(label: str, got, want) -> None:
    global passed, failed
    if got == want:
        print(f"  PASS {label}")
        passed += 1
    else:
        print(f"  FAIL {label}\n         got:  {got!r}\n         want: {want!r}")
        failed += 1


def run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, timeout=240)


def verify(path: pathlib.Path) -> subprocess.CompletedProcess:
    return run([sys.executable, str(VERIFIER), str(path)])


def inject_into_data(html: str) -> str:
    """Replace one JSON string value in window.DASHBOARD_DATA with the payload.

    The replacement is a valid JSON string. It is not a valid HTML script body:
    the browser closes the script at the injected end tag and parses the `<img>`
    after it as a real element.
    """
    marker = "window.DASHBOARD_DATA="
    start = html.index(marker) + len(marker)
    end = html.index("</script>", start)
    block = html[start:end]
    rows, _ = json.JSONDecoder().raw_decode(block)
    hostile = json.dumps(PAYLOAD, ensure_ascii=False)
    for row in rows:
        for value in row.values():
            if not isinstance(value, str) or not value:
                continue
            for dumped in (json.dumps(value, ensure_ascii=False), json.dumps(value)):
                if dumped in block:
                    return (html[:start]
                            + block.replace(dumped, hostile, 1)
                            + html[end:])
    raise AssertionError("no JSON string value found in window.DASHBOARD_DATA")


def main() -> int:
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("ERROR: playwright is not installed, so nothing was measured.")
        print("       uv sync --extra verify && uv run playwright install chromium")
        return 2

    with tempfile.TemporaryDirectory(prefix="verify-dialog-") as td:
        tmp = pathlib.Path(td)
        clean = tmp / "clean.html"
        built = run([sys.executable, str(BUILDER), *ARGS, "--out", str(clean)])
        print("a clean build verifies")
        chk("the builder exits 0", built.returncode, 0)
        if built.returncode != 0:
            print(built.stdout + built.stderr)
            print(f"\nPASS: {passed}  FAIL: {failed}")
            return 1
        chk("the clean file is written", clean.is_file(), True)

        clean_html = clean.read_text(encoding="utf-8")
        clean_run = verify(clean)
        clean_out = clean_run.stdout + clean_run.stderr
        chk("the clean file exits 0", clean_run.returncode, 0)
        chk("the clean file prints PASS", "✓ PASS" in clean_out, True)
        chk("the clean file reports balanced script tags",
            "✓ script-balance" in clean_out, True)
        chk("the clean file reports no dialog", "✓ dialog" in clean_out, True)

        print("\nthe specified surgery: a stray closing tag and its dialog")
        injected = tmp / "injected.html"
        injected.write_text(inject_into_data(clean_html), encoding="utf-8")
        injected_html = injected.read_text(encoding="utf-8")
        chk("the surgery adds exactly one closing script tag",
            injected_html.count("</script>") - clean_html.count("</script>"), 1)

        bad_run = verify(injected)
        bad_out = bad_run.stdout + bad_run.stderr
        chk("the injected file exits non-zero", bad_run.returncode != 0, True)
        chk("it fails the script balance check", "✗ script-balance" in bad_out, True)
        chk("it says a stray end tag closed a script early",
            "had no open script" in bad_out, True)
        chk("it fails on the dialog", "injected dialog: 1" in bad_out, True)
        chk("it prints no PASS line", "✓ PASS" in bad_out, False)

        print("\nthe dialog alone: no stray tag, so the balance check cannot see it")
        dialog = tmp / "dialog-only.html"
        dialog_html = clean_html.replace(
            "</body>", DIALOG_ONLY + "\n</body>", 1)
        chk("the dialog fixture changed the file", dialog_html != clean_html, True)
        dialog.write_text(dialog_html, encoding="utf-8")

        dialog_run = verify(dialog)
        dialog_out = dialog_run.stdout + dialog_run.stderr
        chk("the dialog fixture exits non-zero", dialog_run.returncode != 0, True)
        chk("its script tags still balance", "✓ script-balance" in dialog_out, True)
        chk("it fails on the dialog", "injected dialog: 1" in dialog_out, True)
        chk("it prints no PASS line", "✓ PASS" in dialog_out, False)

    print("\n" + "─" * 66)
    print(f"PASS: {passed}  FAIL: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
