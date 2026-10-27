#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Browser half of the feedback-link tests. Needs Playwright, and fails without it.

    zsh -lc 'uv run --extra verify python tests/test_feedback_link_browser.py'

Builds both dashboard shapes with and without --feedback-to, opens them from file://
in Chromium, and asserts on what a reader would actually send:

  1. with JavaScript on, the live href carries every snapshot field
  2. a script error after load is counted in the href at the moment of use
  3. with JavaScript off, the link is still visible and still the static href
  4. without the flag there is no link at all
  5. tools/verify_dashboard.py passes on every build, flagged or not

A gate that reports success without having opened a browser is worse than none
(tests/test_verify_gate_browser.py), so a missing Playwright is a FAIL here too.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(ROOT / "tests"))
from test_tun_feedback import build_cube, build_rows, run  # noqa: E402  same builds as the stdlib half
ISSUE = "https://forge.example/acme/tun/issues/new?labels=feedback"

PASS = FAIL = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def build(kind: str, out: pathlib.Path, target: str | None) -> subprocess.CompletedProcess:
    extra = ("--feedback-to", target) if target else ()
    return (build_rows if kind == "rows" else build_cube)(out, *extra)


def fields(href: str) -> tuple[str, dict[str, str]]:
    """(subject, {label: value}) from a mailto: or issue href."""
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
    subject = (q.get("subject") or q.get("title") or [""])[0]
    body = (q.get("body") or [""])[0].replace("\r\n", "\n")
    out = {}
    for line in body.splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            out[k] = v
    return subject, out


def main() -> int:
    print("feedback link in a real browser")
    print("─" * 62)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("playwright importable", False,
              "run with: uv run --extra verify python tests/test_feedback_link_browser.py")
        print(f"PASS: {PASS}  FAIL: {FAIL}")
        return 1

    with tempfile.TemporaryDirectory() as td, sync_playwright() as pw:
        tmp = pathlib.Path(td)
        browser = pw.chromium.launch()
        cases = [("rows", "rapport@example.org", "Salg test", "syntetisk"),
                 ("cube", ISSUE, "Kube test", "salgsdata.csv — ")]
        for kind, target, title, source in cases:
            plain, fb = tmp / f"{kind}.html", tmp / f"{kind}-fb.html"
            r1, r2 = build(kind, plain, None), build(kind, fb, target)
            check(f"{kind}: builds", r1.returncode == r2.returncode == 0, (r1.stderr + r2.stderr)[-200:])

            ctx = browser.new_context(viewport={"width": 1280, "height": 800})
            page = ctx.new_page()
            page.goto(fb.as_uri())
            page.wait_for_timeout(800)
            link = page.locator("#tun-feedback")
            link.focus()
            href = link.get_attribute("href") or ""
            subject, f = fields(href)
            ua = page.evaluate("navigator.userAgent")
            check(f"{kind}: live href points at the target",
                  href.startswith(("mailto:rapport@example.org?" if kind == "rows" else ISSUE + "&title=")), href[:60])
            check(f"{kind}: subject names the artefact", subject == f"Tilbakemelding: {title}", subject)
            want = {"Artefakt": title, "Protokoll": "file", "Visning": "lokal fil", "Nettleser": ua,
                    "Vindu": "1280x800 @1x", "JavaScript": "ja", "Skriptfeil": "0"}
            wrong = {k: f.get(k) for k, v in want.items() if f.get(k) != v}
            check(f"{kind}: every live snapshot field is right", not wrong, str(wrong))
            check(f"{kind}: build time and source come along",
                  bool(f.get("Bygget")) and f.get("Kilde", "").startswith(source), str(f)[:200])
            check(f"{kind}: mailto body uses CRLF, issue body LF",
                  ("%0D%0A" in href) == (kind == "rows"), href[-80:])

            page.evaluate("setTimeout(() => { throw new Error('test error'); }, 0)")
            page.wait_for_timeout(200)
            link.hover()
            check(f"{kind}: a later script error is counted at the moment of use",
                  fields(link.get_attribute("href") or "")[1].get("Skriptfeil") == "1")
            ctx.close()

            ctx = browser.new_context(java_script_enabled=False)
            page = ctx.new_page()
            page.goto(fb.as_uri())
            link = page.locator("#tun-feedback")
            static = fb.read_text(encoding="utf-8").split('id="tun-feedback" href="', 1)[1].split('"', 1)[0]
            check(f"{kind}: JS off, the link is visible", link.is_visible())
            check(f"{kind}: JS off, the href is the static one",
                  link.get_attribute("href") == static.replace("&amp;", "&"))
            check(f"{kind}: JS off, it says so", fields(link.get_attribute("href") or "")[1].get("JavaScript") == "nei")
            ctx.close()

            ctx = browser.new_context()
            page = ctx.new_page()
            page.goto(plain.as_uri())
            page.wait_for_timeout(500)
            check(f"{kind}: no flag, no link", page.locator("#tun-feedback").count() == 0)
            ctx.close()

            for f_ in (plain, fb):
                r = run([str(TOOLS / "verify_dashboard.py"), str(f_)])
                last = r.stdout.strip().splitlines()[-2] if r.stdout.strip() else ""
                check(f"{kind}: verify_dashboard passes on {f_.name}",
                      r.returncode == 0 and "✓ PASS" in r.stdout, last or r.stdout[-200:])
        browser.close()

    print("─" * 62)
    print(f"PASS: {PASS}  FAIL: {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
