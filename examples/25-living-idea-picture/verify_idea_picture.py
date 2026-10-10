#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
verify_idea_picture.py — proves the living idea picture moves, can be explored and
stays readable, with no script, in Chromium, Firefox and WebKit, from a file:// URL.

  1. The page passes the generic static checks (tools/verify_standalone_core.py) and has
     no <script> element at all: everything below is CSS.
  2. Desktop shows the wide picture and not the tall one; at 390 px the reverse, with
     no sideways scrolling.
  3. Packets travel: a packet is somewhere else at 2.0 s than at 0.8 s (CSS offset-path).
  4. Each lens lights its own groups and dims the rest, and opens its own panel.
  5. Verten + SharePoint: the SharePoint line shows, no other host line does, and the
     word SharePoint on the ground is lit.
  6. The Killbox panel names all four detours it turns into one file.
  7. Playback: at 1.5 s step 1 is lit and step 2 is dim; at 4.5 s the reverse, and the
     caption shown matches the step.
  8. Reduced motion: no packet shows, no animation runs, and playback shows all four
     captions as a still list.
  9. Zero page errors and zero console errors.

    uv run --extra verify python examples/25-living-idea-picture/verify_idea_picture.py
    uv run --extra verify python examples/25-living-idea-picture/verify_idea_picture.py --mutation-check

Mutations are applied to copies in a temporary directory; the built file is never touched.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
HTML = HERE / "idea-picture.html"
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))
import verify_standalone_core as core  # noqa: E402
from build_idea_picture import HOSTS, LENSES  # noqa: E402

ENGINES = ("chromium", "firefox", "webkit")
SEEK = "t => document.getAnimations().forEach(a => { a.pause(); a.currentTime = t; })"
OPACITY = "sel => [...document.querySelectorAll(sel)].map(e => +getComputedStyle(e).opacity)"
DIM = .16


def check(label: str, cond: bool, failures: list[str], engine: str) -> None:
    print(f"    {'✓' if cond else '✗'} {label}")
    if not cond:
        failures.append(f"{engine}: {label}")


def run_engine(pw, engine: str, html: pathlib.Path, failures: list[str]) -> None:
    print(f"  {engine}")
    browser = getattr(pw, engine).launch()
    errors: list[str] = []

    def page(**kw):
        p = browser.new_page(**kw)
        p.set_default_timeout(5000)
        p.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        p.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        p.goto(html.as_uri())
        return p

    try:
        _checks(page, engine, failures)
    except Exception as exc:  # a crash is a failed check, never a traceback that hides the rest
        check(f"ran to the end (crashed: {type(exc).__name__}: {str(exc).splitlines()[0]})",
              False, failures, engine)
    finally:
        browser.close()
    check("no page or console errors" + (f" ({errors[:2]})" if errors else ""), not errors,
          failures, engine)


def _checks(page, engine, failures) -> None:
    desk = page(viewport={"width": 1100, "height": 1700})
    check("desktop: wide picture shown", desk.is_visible(".lv-wide"), failures, engine)
    check("desktop: tall picture hidden", not desk.is_visible(".lv-tall"), failures, engine)

    def pk_x(t):
        desk.evaluate(SEEK, t)
        return desk.evaluate("() => document.querySelector('.lv-wide .pk-w-out').getBoundingClientRect().x")
    x1, x2 = pk_x(800), pk_x(2000)
    check(f"motion: a packet moves along its arrow ({x1:.0f} → {x2:.0f} px)", x2 - x1 > 20,
          failures, engine)

    phone = page(viewport={"width": 390, "height": 844})
    check("phone: tall picture shown", phone.is_visible(".lv-tall"), failures, engine)
    check("phone: wide picture hidden", not phone.is_visible(".lv-wide"), failures, engine)
    check("phone: no sideways scrolling",
          phone.evaluate("() => document.documentElement.scrollWidth <= innerWidth"), failures, engine)

    still = page(viewport={"width": 1100, "height": 1700}, reduced_motion="reduce")
    for lens in LENSES:
        still.click(f"label[for=lv-{lens}]")
        lit = still.evaluate(OPACITY, f".lv-wide .g.l-{lens}")
        dim = still.evaluate(OPACITY, f".lv-wide .g:not(.l-{lens}):not(.s0)")
        check(f"lens {lens}: its {len(lit)} groups lit, the other {len(dim)} dimmed",
              bool(lit) and all(o == 1 for o in lit) and bool(dim) and all(o <= DIM + .01 for o in dim),
              failures, engine)
        check(f"lens {lens}: its panel is the one shown",
              still.is_visible(f".lv-p-{lens}")
              and still.locator(".lv-p:visible").count() == 1, failures, engine)

    still.click("label[for=lv-host]")
    still.click("label[for=lv-h-sp]")
    shown = [h for h in HOSTS if still.is_visible(f".lv-ht-{h}")]
    check("host SharePoint: only its line shows", shown == ["sp"], failures, engine)
    weight = still.evaluate("() => getComputedStyle(document.querySelector('.lv-wide .h-sp')).fontWeight")
    check("host SharePoint: its name on the ground is lit", str(weight) in ("700", "bold"),
          failures, engine)

    still.click("label[for=lv-kill]")
    kill_text = " ".join(still.text_content(".lv-p-kill").split())
    check("killbox panel names the four detours it replaces",
          all(w in kill_text for w in ("PPTX", "Excel", "Word", "Power BI", "én fil")),
          failures, engine)

    check("reduced motion: no packet shows", still.locator(".pk:visible").count() == 0,
          failures, engine)
    still.click("label[for=lv-play]")
    check("reduced motion: no animation runs", still.evaluate("() => document.getAnimations().length") == 0,
          failures, engine)
    check("reduced motion: playback shows all four captions",
          all(still.is_visible(f".lv-cap .c{i}") for i in (1, 2, 3, 4)), failures, engine)

    desk.click("label[for=lv-play]")
    for t, on, off in ((1500, 1, 2), (4500, 2, 1)):
        desk.evaluate(SEEK, t)
        lit = desk.evaluate(OPACITY, f".lv-wide .s{on}")
        dim = desk.evaluate(OPACITY, f".lv-wide .s{off}")
        cap_on = desk.evaluate(OPACITY, f".lv-cap .c{on}")[0]
        cap_off = desk.evaluate(OPACITY, f".lv-cap .c{off}")[0]
        check(f"playback {t / 1000:.1f} s: step {on} lit, step {off} dim, caption {on} shown",
              all(o > .95 for o in lit) and all(o < .3 for o in dim) and cap_on > .95 and cap_off < .05,
              failures, engine)


def verify(html: pathlib.Path) -> list[str]:
    from playwright.sync_api import sync_playwright
    failures: list[str] = []
    text = html.read_text(encoding="utf-8")
    print("  static")
    check("no <script> element", "<script" not in text.lower(), failures, "static")
    for name, fn in (("self-contained", core.check_self_contained),
                     ("placeholders", core.check_no_leftover_placeholders),
                     ("provenance", core.check_provenance),
                     ("no :target nav", core.check_no_target_driven_visibility),
                     ("no pinned header", core.check_no_scroll_persistent_positioning)):
        ok, msg = fn(text)
        check(f"core check {name}" + ("" if ok else f" ({msg})"), ok, failures, "static")
    with sync_playwright() as pw:
        for engine in ENGINES:
            run_engine(pw, engine, html, failures)
    return failures


MUTATIONS = {
    "lens dimming outranks the lighting":
        ("#lv-all:not(:checked)~.lv-stage .g{opacity:.16}",
         ".lv-r[name=lv-lens]:not(#lv-all):checked~.lv-stage .g{opacity:.16}"),
    "phone picture hidden on desktop": (".lv-stage .lv-tall{display:none}", ".lv-tall{display:none}"),
    "packets follow their arrows": (".lv .pk-w-out{offset-path:path(", ".lv .pk-w-out{--off:path("),
    "playback phases": ("#lv-play:checked~.lv-stage .s2{animation:lv-step 12s linear infinite;"
                        "animation-delay:-9s}",
                        "#lv-play:checked~.lv-stage .s2{animation:lv-step 12s linear infinite;"
                        "animation-delay:0s}"),
    "reduced motion hides packets": ("  .lv .pk{display:none}\n", "\n"),
    "chosen host lit on the ground": ("#lv-host:checked~#lv-h-sp:checked~.lv-stage .h-sp{", ".unused{"),
}


def mutation_check() -> int:
    original = HTML.read_text(encoding="utf-8")
    missed = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, (needle, repl) in MUTATIONS.items():
            if original.count(needle) != 1:
                print(f"✗ mutation anchor for '{name}' found {original.count(needle)} times")
                return 2
            mutant = pathlib.Path(tmp) / HTML.name
            mutant.write_text(original.replace(needle, repl), encoding="utf-8")
            print(f"=== mutation: {name}")
            failures = verify(mutant)
            print(f"--> {'caught' if failures else 'MISSED'} ({len(failures)} failing check(s))")
            if not failures:
                missed.append(name)
    if missed:
        print(f"✗ mutations not caught: {missed}")
        return 1
    print(f"✓ all {len(MUTATIONS)} mutations caught")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--mutation-check", action="store_true")
    if ap.parse_args().mutation_check:
        return mutation_check()
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("✗ FAIL — playwright not installed. Install with: uv sync --extra verify && "
              "uv run playwright install chromium firefox webkit", file=sys.stderr)
        return 1
    failures = verify(HTML)
    print()
    if failures:
        print(f"✗ FAIL — {len(failures)} check(s) failed")
        return 1
    print("✓ PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
