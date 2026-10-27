#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_system_dark.py — the artefact follows the operating system's theme, or says why not.

Stdlib plus Playwright for the render half.

    python3 tests/test_system_dark.py

Why this exists
---------------
`docs/09` §4 left one blocker before dark mode could graduate out of the demo: whether a
theme choice persists per file under `file://` is unmeasured. That question only exists
because the demo chose dark with a *button*, and a button that forgets is worse than no
button.

A page can instead follow the setting the reader has already made in their operating
system. That needs no script, no storage and no toggle, which is exactly what a
self-contained file can do when scripting may not run at all (docs/11 §3c).

CSS has no way to share one declaration block between a media query and a selector, so
the dark declarations must appear twice in a shipped file. Two hand-maintained copies is
how a theme drifts, so `tun_tokens.auto_dark_css()` derives the second from
`theme-dark.css`, and this suite asserts the two are identical, that an explicit choice
still wins, and that the rendered page really does change. The failure it guards against
is silent: a media block that never applies looks exactly like a media block that works,
in any static view of the file.
"""
from __future__ import annotations

import pathlib
import re
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import tun_tokens as tok  # noqa: E402

passed = failed = 0


def chk(label, got, want):
    global passed, failed
    if got == want:
        print(f"  PASS {label}")
        passed += 1
    else:
        print(f"  FAIL {label}: got {got!r}, wanted {want!r}")
        failed += 1


print("the generated block is theme-dark.css, not a second copy that can drift")
dark_css = (tok.CORE_TOKENS / "theme-dark.css").read_text(encoding="utf-8")
source = tok.dark_declarations(dark_css)
auto = tok.auto_dark_css(dark_css)
chk("theme-dark.css declares a theme", len(source) > 10, True)
chk("the generator read the same properties in the same order",
    re.findall(r"(--[a-zA-Z0-9-]+):", auto.split("{", 2)[2]), [n for n, _ in source])
# Compare the values too, resolved to their written form rather than reformatted: a
# generator that quietly dropped or reordered a value is the drift this guards.
got_pairs = re.findall(r"(--[a-zA-Z0-9-]+):\s*([^;]+);", auto)
chk("every declaration matches the source exactly", got_pairs, [(n, v) for n, v in source])
chk("it is a screen-only prefers-color-scheme media query",
    auto.lstrip().splitlines()[3].strip(), "@media screen and (prefers-color-scheme: dark){")
chk("it applies only when the reader has chosen no theme",
    ":root:not([data-theme])" in auto, True)
chk("it never overrides an explicit choice",
    ':root[data-theme="light"]' in auto or ':root[data-theme="dark"]' in auto, False)

print("\nthe loader only adds it when the artefact asks")
css_off, _ = tok.load_token_css()
css_on, _ = tok.load_token_css(auto_dark=True)
# Match the rule, not the words: theme-dark.css mentions prefers-color-scheme in a
# comment, so a substring search would report the block present in a file without it.
MEDIA = "@media screen and (prefers-color-scheme: dark){"
chk("auto_dark off by default", MEDIA in css_off, False)
chk("auto_dark on adds it", MEDIA in css_on, True)
chk("the block comes after the theme it copies",
    css_on.index(MEDIA) > css_on.index(':root[data-theme="dark"]'), True)
try:
    tok.load_token_css(("status-semantic.css", "theme-light.css"), auto_dark=True)
    chk("auto_dark without the dark theme is refused", "no error", "a TokenError")
except SystemExit as exc:
    chk("auto_dark without the dark theme is refused",
        "theme-dark.css" in str(exc), True)

# --- the render half: does the page actually change? -----------------------------------
print("\na browser follows the system setting, and an explicit choice still wins")
try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - the repo's rule is to fail, never to skip
    print("  FAIL Playwright is not installed, so the render half cannot run")
    print("       uv sync --extra verify && uv run playwright install chromium")
    print("\n" + "-" * 66)
    print(f"{passed} passed, {failed + 1} failed")
    raise SystemExit(1)

DEMO = REPO / "examples" / "05-theme-toggle-demo" / "theme-toggle-demo.html"
chk("the demo is built with the system route",
    "@media screen and (prefers-color-scheme: dark){" in DEMO.read_text(encoding="utf-8"),
    True)


def freeze(page):
    """Stop transitions. The demo animates its background colour, so a measurement taken
    while it runs reports an in-between colour and not the theme that was chosen."""
    page.add_style_tag(content="*,*::before,*::after{transition:none!important;"
                               "animation:none!important}")


def rendered(page, scheme, theme=None):
    """The page's computed --bg and its body background under one colour scheme."""
    freeze(page)
    if theme is None:
        page.evaluate("document.documentElement.removeAttribute('data-theme')")
    else:
        page.evaluate("t => document.documentElement.setAttribute('data-theme', t)", theme)
    page.wait_for_timeout(120)
    return page.evaluate("""() => {
        const cs = getComputedStyle(document.documentElement);
        return {token: cs.getPropertyValue('--bg').trim(),
                body: getComputedStyle(document.body).backgroundColor};
    }""")


def rgb(value):
    """rgb()/rgba() from the browser to a 3-digit-normalised lowercase hex."""
    nums = [int(x) for x in value[value.index("(") + 1:value.index(")")].split(",")[:3]]
    return "#%02x%02x%02x" % tuple(nums)


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    seen = {}
    for scheme in ("light", "dark"):
        ctx = browser.new_context(color_scheme=scheme, viewport={"width": 1100, "height": 800})
        page = ctx.new_page()
        page.goto(f"file://{DEMO.resolve()}")
        seen[scheme] = rendered(page, scheme)
        if scheme == "dark":
            seen["dark_explicit_light"] = rendered(page, scheme, "light")
            seen["dark_explicit_dark"] = rendered(page, scheme, "dark")
        ctx.close()
    browser.close()

chk("the light page uses the light background",
    rgb(seen["light"]["body"]), seen["light"]["token"].lower())
chk("a dark system gives the dark background",
    rgb(seen["dark"]["body"]), seen["dark"]["token"].lower())
chk("the two backgrounds are different colours",
    seen["light"]["body"] != seen["dark"]["body"], True)
chk("choosing light on a dark system keeps light",
    rgb(seen["dark_explicit_light"]["body"]), rgb(seen["light"]["body"]))
chk("choosing dark on a dark system is dark",
    rgb(seen["dark_explicit_dark"]["body"]), rgb(seen["dark"]["body"]))

# --- mutation control -----------------------------------------------------------------
print("\nmutation control: a block that ignores the media query is caught")
mutated = auto.replace("@media screen and (prefers-color-scheme: dark){", "@media all{")
chk("the mutation applied", mutated != auto, True)
scratch = pathlib.Path(tempfile.mkdtemp(prefix="tun-sysdark-"))
try:
    body = DEMO.read_text(encoding="utf-8")
    broken = body.replace(auto, mutated)
    chk("the mutation landed in the page", broken != body, True)
    target = scratch / "broken.html"
    target.write_text(broken, encoding="utf-8")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(color_scheme="dark", viewport={"width": 1100, "height": 800})
        page = ctx.new_page()
        page.goto(f"file://{target.resolve()}")
        forced = rendered(page, "light")
        browser.close()
    chk("without the media query a light system is forced dark",
        rgb(forced["body"]), rgb(seen["dark"]["body"]))
finally:
    import shutil
    shutil.rmtree(scratch, ignore_errors=True)

# --- print is paper --------------------------------------------------------------------
# `prefers-color-scheme: dark` describes a DISPLAY. A page that honours it must not carry
# that choice onto paper: the @media print block in every template forces a white sheet, and
# a dark block declared without a `screen` guard comes later in the file and paints the ink
# light on it. Measured before the fix, printing from a dark system: rgb(247,245,239) ink on
# rgb(255,255,255) paper, at 1.02:1. Eight templates shipped that way.
print("\nthe dark route is a screen route: printing is paper, whatever the system says")
PRINT_PAGES = [
    REPO / "examples" / "45-smallmultiples" / "smaaflater.html",
    REPO / "examples" / "42-funnel" / "tratt.html",
    REPO / "examples" / "35-timeline" / "tidslinje.html",
]
chk("every template scopes its dark block to screen",
    [p.name for p in (REPO / "templates").glob("*.html")
     if "@media (prefers-color-scheme: dark)" in p.read_text(encoding="utf-8")], [])


def printed(path, scheme):
    """The ink and the paper, with the browser emulating the print medium."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(color_scheme=scheme, viewport={"width": 1100, "height": 800})
        page = ctx.new_page()
        page.goto(f"file://{path.resolve()}")
        page.emulate_media(media="print", color_scheme=scheme)
        page.wait_for_timeout(120)
        seen = page.evaluate("""() => { const b = getComputedStyle(document.body);
            return {ink: b.color, paper: b.backgroundColor}; }""")
        browser.close()
    return seen


for path in PRINT_PAGES:
    dark = printed(path, "dark")
    light = printed(path, "light")
    chk(f"{path.name}: printing from a dark system gives the light page's ink",
        dark["ink"], light["ink"])
    chk(f"{path.name}: and the same paper",
        dark["paper"], light["paper"])

# --- mutation control: drop the screen guard and the gate must see it -------------------
print("\nmutation control: a dark block without the screen guard is caught")
victim = PRINT_PAGES[0]
original = victim.read_text(encoding="utf-8")
broken = original.replace("@media screen and (prefers-color-scheme: dark){",
                          "@media (prefers-color-scheme: dark){")
chk("the mutation applied", broken != original, True)
scratch2 = pathlib.Path(tempfile.mkdtemp(prefix="tun-print-"))
try:
    target = scratch2 / victim.name
    target.write_text(broken, encoding="utf-8")
    caught = printed(target, "dark")
    chk("without the guard, printing from dark really does paint light ink on white paper",
        caught["ink"] != printed(victim, "dark")["ink"], True)
finally:
    import shutil as _shutil
    _shutil.rmtree(scratch2, ignore_errors=True)

print("\n" + "-" * 66)
print(f"{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
