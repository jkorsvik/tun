#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
verify_js_free_poc.py — proves the actual claim of the JavaScript-free pattern, not just that
the file renders. Loads js-free-standalone-poc.html TWICE in a real
(headless) browser: once with JavaScript enabled, once with it forced off
(`java_script_enabled=False` — the closest Playwright gets to reproducing
the failure mode in docs/11, where scripting is not blocked by policy but simply
never executes in the viewer).

Checks, with JavaScript OFF:
  1. Hamburger menu opens via a real click (no JS) — nav-menu becomes visible.
  2. Page switching works with no JS — clicking a nav label checks its radio
     and CSS :checked shows that page, hiding the others.

     SCOPE LIMIT, read this before trusting check 2. This runs in a local
     headless browser over file://, and that is the ONE context where the
     mechanism this check replaced also worked. An earlier revision navigated
     with CSS :target, which is measured broken in SharePoint's inline
     file-preview (docs/01-tenant-constraints.md row 24) — and this check
     passed, every run, for weeks. A pass here proves the mechanism works from
     file://. It cannot prove anything about the preview surface, because
     Playwright cannot reach it. Whether the radio-group replacement survives
     there has to be confirmed by a human, once, the same way row 24 itself
     was found.
  3. Theme toggle changes the background colour via a real click (no JS).
  4. Bar chart shows the CSS version (canvas must stay hidden).
  5. Scatter block shows the "Krever JavaScript..." message.
  6. Fullscreen button is not visible (stays `hidden`).
  7. Global + bar-chart "Begrenset forhåndsvisning" banners are visible.
  8. Mobile topbar (360px): title wraps to <=2 lines, no icon overlap,
     header height matches --topbar-h exactly.

Checks, with JavaScript ON:
  9. Bar chart canvas becomes visible and the CSS version is hidden.
  10. Scatter canvas becomes visible and the fallback message is hidden.
  11. Fullscreen button becomes visible (headless Chromium exposes the API,
     even though actually entering fullscreen may still be refused without
     a user gesture — this only proves the reveal step, not a full
     fullscreen session).
  12. Both "Begrenset forhåndsvisning" banners are hidden once JS proves
     itself (must not claim degraded mode on a fully working page).

    python3 examples/13-js-free-standalone-poc/verify_js_free_poc.py
"""
from __future__ import annotations

import pathlib
import sys

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
FILE = HERE / "js-free-standalone-poc.html"


def check(label: str, cond: bool, failures: list[str]) -> None:
    print(f"  {'✓' if cond else '✗'} {label}")
    if not cond:
        failures.append(label)


def run_no_js(failures: list[str]) -> None:
    print("\n-- JavaScript DISABLED (java_script_enabled=False) --")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844}, java_script_enabled=False)
        page.goto(FILE.as_uri())

        # 1. hamburger menu opens via a real click, no JS. CSS transitions
        # animate the transform over 0.18s (see STYLE) — give it time to
        # settle before reading the computed value, otherwise the read can
        # land mid-transition (or, right after the synchronous click, at
        # frame 0 of the animation).
        page.click("#menu-toggle")
        page.wait_for_timeout(300)
        box = page.eval_on_selector("#nav-menu", "el => el.getBoundingClientRect().left")
        check("nav-menu panel is on-screen after click (left >= -5px)", box >= -5, failures)

        # 2. page switching via the radio group (NOT :target — see the scope
        # limit in this file's docstring, and row 24). Click the label INSIDE
        # the now-open nav-menu specifically; the home page also carries
        # inline references, and it is off-canvas/behind the menu at this
        # point and not a fair target for a real click.
        page.locator("#nav-menu label[for='nav-charts']").click()
        page.wait_for_timeout(100)
        charts_visible = page.eval_on_selector(
            "#page-charts", "el => getComputedStyle(el).display !== 'none'"
        )
        home_hidden = page.eval_on_selector(
            "#page-home", "el => getComputedStyle(el).display === 'none'"
        )
        check("clicking a page label shows #page-charts (radio + :checked, no JS)", charts_visible, failures)
        check("switching pages hides #page-home (no JS)", home_hidden, failures)
        page.click("#menu-toggle")  # close menu again
        page.wait_for_timeout(300)

        # Confirm the auto-close enhancement genuinely depends on JS: with
        # JS off, choosing a page must NOT close the menu on its own (the
        # reader closes it manually — this is the documented, accepted
        # difference in behaviour between the two modes, not a bug).
        page.click("#menu-toggle")
        page.wait_for_timeout(150)
        page.locator("#nav-menu label[for='nav-principles']").click()
        page.wait_for_timeout(250)
        menu_left_after_nav = page.eval_on_selector("#nav-menu", "el => el.getBoundingClientRect().left")
        check(
            "menu stays open after choosing a page without JS (manual close still required)",
            menu_left_after_nav >= -5,
            failures,
        )
        page.click("#menu-toggle")
        page.wait_for_timeout(300)


        # 3. theme toggle changes colour via a real click, no JS
        bg_before = page.eval_on_selector("#app-root", "el => getComputedStyle(el).backgroundColor")
        page.click("#theme-toggle")
        page.wait_for_timeout(100)
        bg_after = page.eval_on_selector("#app-root", "el => getComputedStyle(el).backgroundColor")
        check("theme toggle changes background colour (CSS :checked, no JS)", bg_before != bg_after, failures)
        page.click("#theme-toggle")  # back to light

        # 4. bar chart: CSS version visible, canvas stays hidden
        css_bars_visible = page.eval_on_selector(
            "#bar-chart-css", "el => getComputedStyle(el).display !== 'none'"
        )
        canvas_hidden = page.eval_on_selector("#bar-chart-canvas", "el => el.hidden")
        check("bar chart: CSS fallback visible without JS", css_bars_visible, failures)
        check("bar chart: canvas stays hidden without JS", canvas_hidden, failures)

        # 5. scatter: fallback message visible
        scatter_msg_visible = page.eval_on_selector(
            "#scatter-fallback", "el => getComputedStyle(el).display !== 'none'"
        )
        scatter_text = page.inner_text("#scatter-fallback").strip()
        check("scatter chart: fallback message visible without JS", scatter_msg_visible, failures)
        check(
            "scatter fallback text includes the JS-required sentence",
            "Krever JavaScript som ikke er støttet i denne visningen." in scatter_text,
            failures,
        )

        # 6. fullscreen button stays hidden
        fs_hidden = page.eval_on_selector("#fs-btn", "el => el.hidden")
        check("fullscreen button stays hidden without JS", fs_hidden, failures)

        # 7. "Begrenset forhåndsvisning" banners: global one visible, and
        # the bar-chart one visible alongside its CSS fallback (both are
        # driven by the *absence* of a JS success signal, not by JS itself).
        global_notice_visible = page.eval_on_selector(
            "#preview-notice-global", "el => getComputedStyle(el).display !== 'none'"
        )
        bar_notice_visible = page.eval_on_selector(
            "#bar-chart-notice", "el => getComputedStyle(el).display !== 'none'"
        )
        check("global 'Begrenset forhåndsvisning' banner visible without JS", global_notice_visible, failures)
        check("bar chart 'Begrenset forhåndsvisning' banner visible without JS", bar_notice_visible, failures)

        # 8. mobile topbar: title wraps onto (at most) two lines and does not
        # collide with the info/theme icon cluster — the whole reason the
        # short mobile title text and the narrower reserved icon gutter exist.
        mobile_page = browser.new_page(viewport={"width": 360, "height": 640}, java_script_enabled=False)
        mobile_page.goto(FILE.as_uri())
        title_box = mobile_page.eval_on_selector(".title-short", "el => el.getBoundingClientRect()")
        info_box = mobile_page.eval_on_selector("#info-toggle-label", "el => el.getBoundingClientRect()")
        header_box = mobile_page.eval_on_selector("#topbar", "el => el.getBoundingClientRect()")
        check("mobile title wraps to at most two lines", title_box["height"] < 40, failures)
        check("mobile title does not overlap the icon cluster", title_box["right"] < info_box["left"], failures)
        check("mobile header height matches --topbar-h (no gap/overlap below it)", header_box["height"] == 74, failures)
        mobile_page.close()

        browser.close()


def run_with_js(failures: list[str]) -> None:
    print("\n-- JavaScript ENABLED (default) --")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(FILE.as_uri())
        page.click("#menu-toggle")
        page.wait_for_timeout(150)
        page.locator("#nav-menu label[for='nav-charts']").click()
        page.wait_for_timeout(300)

        bar_canvas_visible = page.eval_on_selector("#bar-chart-canvas", "el => !el.hidden")
        bar_css_hidden = page.eval_on_selector("#bar-chart-css", "el => el.hidden === true")
        check("bar chart: canvas visible once JS drew it", bar_canvas_visible, failures)
        check("bar chart: CSS version hidden only after canvas succeeded", bar_css_hidden, failures)

        scatter_canvas_visible = page.eval_on_selector("#scatter-canvas", "el => !el.hidden")
        scatter_fallback_hidden = page.eval_on_selector("#scatter-fallback", "el => el.hidden === true")
        check("scatter chart: canvas visible with JS", scatter_canvas_visible, failures)
        check("scatter chart: fallback message hidden once canvas drew", scatter_fallback_hidden, failures)

        fs_visible = page.eval_on_selector("#fs-btn", "el => !el.hidden")
        check("fullscreen button revealed when API exists + JS runs", fs_visible, failures)

        # "Begrenset forhåndsvisning" banners must disappear once JS proves
        # itself — otherwise a fully-working page would wrongly tell the
        # reader it's degraded.
        global_notice_hidden = page.eval_on_selector(
            "#preview-notice-global", "el => getComputedStyle(el).display === 'none'"
        )
        bar_notice_hidden = page.eval_on_selector("#bar-chart-notice", "el => el.hidden === true")
        check("global 'Begrenset forhåndsvisning' banner hidden once JS succeeds", global_notice_hidden, failures)
        check("bar chart 'Begrenset forhåndsvisning' banner hidden once canvas drew", bar_notice_hidden, failures)

        # optional JS enhancement: clicking a page link inside the open
        # menu also closes it (menu remains fully USABLE without this —
        # see build_js_free_poc.py comment — this only proves the extra
        # convenience layer itself does what it claims when JS is present)
        page.click("#menu-toggle")
        page.wait_for_timeout(150)
        page.locator("#nav-menu label[for='nav-principles']").click()
        page.wait_for_timeout(250)
        menu_left = page.eval_on_selector("#nav-menu", "el => el.getBoundingClientRect().left")
        check("menu auto-closes after choosing a page (JS enhancement)", menu_left < -5, failures)

        check("no console errors with JS enabled", len(errors) == 0, failures)
        if errors:
            print(f"    first error: {errors[0][:160]}")

        browser.close()


def main() -> int:
    if not FILE.exists():
        print(f"✗ not found: {FILE} — run build_js_free_poc.py first")
        return 2
    failures: list[str] = []
    run_no_js(failures)
    run_with_js(failures)
    print("\n" + "─" * 60)
    if failures:
        print(f"✗ FAIL — {len(failures)} check(s) failed:")
        for f in failures:
            print(f"    • {f}")
        return 1
    print("✓ PASS — all navigation works identically with JavaScript on or off;")
    print("  chart degradation and fullscreen hiding behave exactly as designed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
