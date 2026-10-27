#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""A chart drawn while its frame had no size must redraw once the frame gets one.

Measured 2026-10-12 (docs/29-atlassian-artifacts.md): a Tún file embedded in a Confluence page
through an Atlassian Artifacts embed runs its script while the frame is 0 x 0, and the frame
later gets its real size without firing a single `resize` event. Both chart templates measured
their cards at boot, fell back to a fixed width when they read 0, and redrew only on `resize`.
So the charts kept the fallback drawing width and were scaled to the real card: text drawn for
640 px shown in a 500 px card, or the other way around. Nothing errors; it is just wrong.

This reproduces the measured behaviour locally, both halves of it: the artefact loads inside an
`<iframe>` that is `display:none`, so it boots at 0 x 0, and is then shown. Locally, showing a
frame DOES fire `resize` inside it, which would hide the bug, so an init script swallows every
`resize` event in the artefact before its own scripts run. That is exactly what the host did:
size arrived, `resize` never fired. After that, every chart's viewBox width must equal its
rendered width.

A control run without the swallowing confirms the setup itself is sound.

Needs Playwright and Chromium, and FAILS without them: a browser check that reports success
without a browser is worse than none (AGENTS.md, verification gate).

    python3 tests/test_chart_width_after_hidden_load.py
"""
from __future__ import annotations

import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASES = [
    # (label, artefact, CSS selector of the chart SVGs)
    ("single-file dashboard", ROOT / "examples" / "01-hello-dashboard" / "salg-dashboard.html",
     "#chart1, #chart2"),
    ("cube dashboard", ROOT / "examples" / "03-cube-dashboard" / "transaksjoner.html",
     "#charts svg, #trend svg"),
]
FRAME_W, FRAME_H = 1100, 900
TOLERANCE_PX = 2

PASS = FAIL = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


HOST = """<!doctype html><meta charset="utf-8">
<iframe id="f" src="{name}" style="display:none;width:{w}px;height:{h}px;border:0"></iframe>"""

MEASURE = """sel => [...document.querySelectorAll(sel)].map(s => ({
  id: s.id || s.parentElement.id,
  vb: s.viewBox && s.viewBox.baseVal ? Math.round(s.viewBox.baseVal.width) : null,
  px: Math.round(s.getBoundingClientRect().width)
}))"""


def drawn(inner, sel: str, budget_ms: int = 8000, step_ms: int = 50) -> tuple[list, int]:
    """Poll until the artefact's boot has drawn every chart, whatever width it drew at.

    The boot used to get a flat 1500 ms before the frame was shown. Under load it can be
    slower, and then the ResizeObserver callback runs before the charts exist and never
    fires again, so the fallback width stays for good — the other half of the flake. Wait
    for the drawing, not for a stopwatch.
    """
    waited = 0
    charts = inner.evaluate(MEASURE, sel)
    while waited < budget_ms:
        if charts and all(c["vb"] is not None for c in charts):
            return charts, waited
        inner.page.wait_for_timeout(step_ms)
        waited += step_ms
        charts = inner.evaluate(MEASURE, sel)
    return charts, waited


def settle(inner, sel: str, budget_ms: int = 8000, step_ms: int = 100) -> tuple[list, int]:
    """Poll until every chart is drawn for its rendered width, or the budget runs out.

    The old version slept a fixed 1500 ms and measured once, which is a guess about how
    long a boot plus a ResizeObserver callback plus a requestAnimationFrame takes on a
    loaded machine — the reason this suite failed about once in eight runs. The property
    being checked is that the artefact converges, not that it converges within a chosen
    window, so poll and report how long it took.
    """
    waited = 0
    charts = inner.evaluate(MEASURE, sel)
    while waited < budget_ms:
        if charts and all(c["vb"] is not None and c["px"] > 0
                          and abs(c["vb"] - c["px"]) <= TOLERANCE_PX for c in charts):
            return charts, waited
        inner.page.wait_for_timeout(step_ms)
        waited += step_ms
        charts = inner.evaluate(MEASURE, sel)
    return charts, waited


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("FAIL: Playwright is not installed. Install with "
              "`uv sync --extra verify && uv run playwright install chromium`.")
        return 1

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="tun-hidden-load-"))
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:  # browser binary missing
                print(f"FAIL: Chromium could not start ({e.__class__.__name__}). "
                      "Run `uv run playwright install chromium`.")
                return 1
            # Installed in every frame before any of the artefact's own scripts run.
            SWALLOW = ("window.addEventListener('resize', e => e.stopImmediatePropagation(), true);"
                       "window.__swallowed = true;")
            # (mode, swallow resize?, disable the fix?, the charts are expected to be right?)
            runs = [("as the host behaves (no resize event)", True, False, True),
                    ("control: resize fires", False, False, True),
                    ("mutant: ResizeObserver disabled", True, True, False)]
            for (mode, swallow, mutate, expect_ok), (label, art, sel) in [(r, c) for r in runs for c in CASES]:
                label = f"{label}, {mode}"
                print(f"{label}: {art.relative_to(ROOT)}")
                if not art.is_file():
                    check(f"{label}: artefact exists", False, str(art))
                    continue
                src = art.read_text(encoding="utf-8")
                if mutate:
                    hook = 'typeof ResizeObserver === "function"'
                    check(f"{label}: the fix is where the mutant expects it", src.count(hook) == 1)
                    src = src.replace(hook, "false")
                name = ("mutant-" if mutate else "") + art.name
                (tmp / name).write_text(src, encoding="utf-8")
                host = tmp / f"host-{name}"
                host.write_text(HOST.format(name=name, w=FRAME_W, h=FRAME_H), encoding="utf-8")
                ctx = browser.new_context(viewport={"width": FRAME_W + 40, "height": FRAME_H + 40})
                if swallow:
                    ctx.add_init_script(SWALLOW)
                page = ctx.new_page()
                page.goto(host.as_uri())
                frame = page.frame_locator("#f")
                frame.locator(sel.split(",")[0].strip()).first.wait_for(state="attached", timeout=15000)
                inner = page.frames[1]
                _, boot_ms = drawn(inner, sel)  # boot finishes while the frame is still 0 x 0
                hidden_w = inner.evaluate("innerWidth")
                check(f"{label}: booted while the frame had no width (innerWidth {hidden_w}, "
                      f"drawn after {boot_ms} ms)", hidden_w == 0)
                page.evaluate("document.getElementById('f').style.display = 'block'")
                charts, waited = settle(inner, sel, budget_ms=8000 if expect_ok else 2000)
                check(f"{label}: found the charts ({len(charts)})", len(charts) >= 2, str(charts))
                right = [c["vb"] is not None and c["px"] > 0 and abs(c["vb"] - c["px"]) <= TOLERANCE_PX
                         for c in charts]
                detail = (f"settled after {waited} ms; "
                          + ", ".join(f"#{c['id'] or '?'} viewBox {c['vb']} vs {c['px']}" for c in charts))
                if expect_ok:
                    check(f"{label}: every chart drawn for its real width ({detail})", all(right))
                else:
                    check(f"{label}: the suite notices the missing fix ({detail})", not all(right))
                ctx.close()
            browser.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"PASS: {PASS}  FAIL: {FAIL}")
    return 0 if FAIL == 0 and PASS > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
