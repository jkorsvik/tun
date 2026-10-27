#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
verify_topbar_demo.py — interaction check for topbar-pattern-demo.html.

tools/verify_standalone_core.py only proves the file is self-contained,
within size budget, and renders without a console error. It does not click
anything. This script exists because issue #15's whole point is whether the
hamburger/info/fullscreen controls actually respond -- so this specifically:

  1. clicks the hamburger button and asserts the nav menu becomes visible
     and the overlay opens
  2. clicks a second nav item and asserts the page content actually swaps
     and the active-item indicator moves
  3. clicks the info button and asserts the info panel opens (and the menu
     closes -- only one overlay panel open at a time)
  4. clicks outside (the overlay) and asserts everything closes
  5. clicks the fullscreen button and asserts document.fullscreenElement
     is set, then toggles it back off

Every assertion is against real DOM state after a real click in a real
(headless) browser -- not against the HTML source.

    python3 verify_topbar_demo.py

Does NOT test issue #15 section 5 (opening from an actual Teams message on
an actual phone) -- that cannot be done from this sandbox. This only proves
the pattern works in a standards-compliant desktop browser engine, which is
the precondition for that mobile test being worth running at all.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))
from verify_standalone_core import add_engines_arg, label_failures, shot_path  # noqa: E402

HTML = pathlib.Path(__file__).parent / "topbar-pattern-demo.html"


def check(label: str, condition: bool, failures: list[str]) -> None:
    mark = "✓" if condition else "✗"
    print(f"  {mark} {label}")
    if not condition:
        failures.append(label)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_engines_arg(ap)
    args = ap.parse_args()
    failures: list[str] = []

    with sync_playwright() as p:
        for engine in args.engines:
            print(f"  · {engine}")
            mark = len(failures)
            browser = getattr(p, engine).launch()
            page = browser.new_page(viewport={"width": 390, "height": 780})  # mobile-ish
            page.goto(HTML.as_uri())
            page.wait_for_function("window.__TOPBAR_DEMO_READY__ === true")

            print("1. hamburger opens the menu")
            page.click("#hamburger-btn")
            check("nav-menu has .open", page.eval_on_selector("#nav-menu", "el => el.classList.contains('open')"), failures)
            check("overlay has .open", page.eval_on_selector("#overlay", "el => el.classList.contains('open')"), failures)
            check("hamburger aria-expanded=true", page.get_attribute("#hamburger-btn", "aria-expanded") == "true", failures)

            print("2. clicking a nav item swaps content and moves the active marker")
            page.click("[data-target='section-b']")
            check("section-b visible", page.eval_on_selector("#section-b", "el => getComputedStyle(el).display") == "block", failures)
            check("home hidden", page.eval_on_selector("#home", "el => getComputedStyle(el).display") == "none", failures)
            check("section-b marked active", page.eval_on_selector("[data-target='section-b']", "el => el.classList.contains('active')"), failures)
            check("menu closed after nav click", not page.eval_on_selector("#nav-menu", "el => el.classList.contains('open')"), failures)

            print("3. info button opens the info panel (and menu stays closed)")
            page.click("#info-btn")
            check("info-panel has .open", page.eval_on_selector("#info-panel", "el => el.classList.contains('open')"), failures)
            check("nav-menu NOT open at the same time", not page.eval_on_selector("#nav-menu", "el => el.classList.contains('open')"), failures)

            print("4. explicit close button (✕) closes the info panel")
            page.click("#info-panel .close-btn")
            check("info-panel closed via close button", not page.eval_on_selector("#info-panel", "el => el.classList.contains('open')"), failures)
            check("overlay closed via close button", not page.eval_on_selector("#overlay", "el => el.classList.contains('open')"), failures)

            print("4b. click genuinely outside the panel (bottom-left corner) also closes it")
            page.click("#info-btn")
            page.mouse.click(10, 770)  # bottom-left corner of the 390x780 viewport, well clear of the right-anchored panel
            check("info-panel closed via outside click", not page.eval_on_selector("#info-panel", "el => el.classList.contains('open')"), failures)

            print("5. fullscreen button toggles document.fullscreenElement")
            page.click("#fs-btn")
            page.wait_for_timeout(200)
            is_fs = page.evaluate("() => !!document.fullscreenElement")
            check("fullscreen entered after click", is_fs, failures)
            if is_fs:
                page.click("#fs-btn")
                page.wait_for_timeout(200)
                check("fullscreen exited after second click", not page.evaluate("() => !!document.fullscreenElement"), failures)
            else:
                print("    (skipped exit-check: headless launch likely blocked requestFullscreen -- see note below)")

            page.screenshot(path=str(shot_path(HTML, ".interaction-check.png", engine)))

            # --- separate page: simulate an environment with NO Fullscreen API at
            # all (e.g. the in-app WebView Teams-on-mobile testing surfaced for
            # issue #15, where document.documentElement.requestFullscreen threw
            # an uncaught error that the host app displayed to the user as a
            # "Script error" banner). Confirms the fix actually degrades
            # gracefully instead of merely not being exercised by the happy path
            # above.
            print("6. graceful degradation when Fullscreen API is entirely absent")
            page2 = browser.new_page(viewport={"width": 390, "height": 780})
            page2.add_init_script(
                "delete Element.prototype.requestFullscreen; delete Document.prototype.exitFullscreen;"
                "Object.defineProperty(document, 'fullscreenEnabled', {get: () => false});"
            )
            console_errors = []
            page2.on("pageerror", lambda e: console_errors.append(str(e)))
            page2.goto(HTML.as_uri())
            page2.wait_for_function("window.__TOPBAR_DEMO_READY__ === true")
            check("fs-btn disabled when API absent", page2.get_attribute("#fs-btn", "disabled") is not None, failures)
            # force a click through even though disabled, to prove the handler
            # itself is also safe (defence in depth, not just the disabled attribute)
            page2.evaluate("document.getElementById('fs-btn').removeAttribute('disabled'); document.getElementById('fs-btn').click();")
            page2.wait_for_timeout(100)
            check("no uncaught page error after clicking fs-btn without the API", len(console_errors) == 0, failures)
            page2.close()
            browser.close()
            label_failures(failures, mark, engine, args.engines)

    print("─" * 60)
    if failures:
        print(f"✗ FAIL — {len(failures)} interaction check(s) failed: {failures}")
        return 1
    print("✓ PASS — all interaction checks passed against real DOM state in a real browser engine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
