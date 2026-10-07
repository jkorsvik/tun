#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Check one built artefact at every viewport we claim to support.

`tools/verify_dashboard.py` and `tools/verify_standalone_core.py` each render at a
single desktop size (1440x1000 and 1200x900). `docs/11-responsiveness-and-browser-support.md`
says something stronger and normative: desktop, laptop, tablet and mobile are all
supported, both orientations must work without clipped or hidden content, and touch
is an equal input method with a 44x44 px minimum target. Nothing measured any of
that, so the claim was documentation only.

This tool measures it. It is deliberately a separate file rather than more code in
the two existing verifiers, because those own the "is this artefact publishable at
all" question and are under active change.

What it checks, per viewport:

  1. horizontal overflow  — scrollWidth wider than the viewport means clipped or
                            off-screen content, which docs/11 forbids outright.
  2. touch targets        — interactive elements smaller than 44x44 px, on the
                            touch-sized viewports only.
  3. screenshot           — one per viewport, for a human to actually look at.
                            A clean measurement is not a clean layout: look at
                            both viewports before calling it done.

It never reports success when it did not run. A missing Playwright is an error with
exit code 2, not a skip — see an earlier pull request for why that matters.

Usage:
    python3 tools/verify_viewports.py path/to/artefact.html [--out DIR] [--quiet]

Exit codes: 0 all viewports clean, 1 at least one finding, 2 could not run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# name, width, height, touch
VIEWPORTS = [
    ("conference", 1600, 900, False),
    ("laptop", 1366, 768, False),
    ("tablet-portrait", 768, 1024, True),
    ("tablet-landscape", 1024, 768, True),
    ("phone-portrait", 390, 844, True),
    ("phone-landscape", 844, 390, True),
]

MIN_TOUCH_PX = 44
# A few px of slack: sub-pixel layout and scrollbar-less rendering both wobble by ~1px.
OVERFLOW_SLACK_PX = 2

# Interactive things a finger has to hit. Kept explicit rather than clever so the
# rule is readable in a review.
# `label[for]` is deliberately absent. A label is clickable, but its text is
# normally 16px tall and that is not a defect — the control it points at is the
# real target, and it is measured. Including labels produced a finding on every
# touch viewport of every artefact, which is noise, and a noisy gate gets ignored
# exactly like a vacuous one.
INTERACTIVE_SELECTOR = (
    "a[href], button, input:not([type=hidden]), select, textarea, summary, "
    "[role=button], [role=tab], [role=checkbox], [role=switch], [tabindex]"
)

MEASURE_JS = """
(minPx) => {
  const doc = document.scrollingElement || document.documentElement;
  const small = [];
  const seen = new Set();
  for (const el of document.querySelectorAll(%r)) {
    const r = el.getBoundingClientRect();
    // Invisible or collapsed elements are not touch targets. A closed menu's
    // links are legitimately 0x0 and must not be reported.
    if (r.width === 0 || r.height === 0) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || cs.pointerEvents === 'none') continue;
    if (parseFloat(cs.opacity || '1') === 0) continue;
    if (r.width >= minPx && r.height >= minPx) continue;
    const label = (el.getAttribute('aria-label') || el.textContent || el.id || '')
      .trim().replace(/\\s+/g, ' ').slice(0, 40);
    const key = el.tagName.toLowerCase() + '|' + label + '|' +
                Math.round(r.width) + 'x' + Math.round(r.height);
    if (seen.has(key)) continue;
    seen.add(key);
    small.push({
      tag: el.tagName.toLowerCase(),
      label: label,
      w: Math.round(r.width * 10) / 10,
      h: Math.round(r.height * 10) / 10,
    });
  }
  return {
    scrollWidth: doc.scrollWidth,
    clientWidth: doc.clientWidth,
    innerWidth: window.innerWidth,
    smallTargets: small,
  };
}
""" % (INTERACTIVE_SELECTOR,)


def check(path: Path, out_dir: Path, quiet: bool) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright is not installed, so nothing was measured.")
        print("       install: uv sync --extra verify && uv run playwright install chromium")
        print("       This is an error, not a skip: a check that cannot run must not pass.")
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    url = path.resolve().as_uri()
    findings: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for name, w, h, touch in VIEWPORTS:
                page = browser.new_page(
                    viewport={"width": w, "height": h},
                    has_touch=touch,
                    is_mobile=touch,
                )
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(url)
                page.wait_for_timeout(700)  # let entry animations settle

                m = page.evaluate(MEASURE_JS, MIN_TOUCH_PX)
                shot = out_dir / f"{path.stem}.{name}.png"
                page.screenshot(path=str(shot), full_page=False)

                line = f"  {name:<17} {w}x{h}"
                overflow = m["scrollWidth"] - max(m["clientWidth"], m["innerWidth"])
                if overflow > OVERFLOW_SLACK_PX:
                    findings.append(
                        f"{name} ({w}x{h}): content is {overflow}px wider than the "
                        f"viewport — docs/11 forbids clipped or hidden content"
                    )
                    line += f"  ✗ overflows by {overflow}px"
                elif touch and m["smallTargets"]:
                    worst = m["smallTargets"][:4]
                    shown = ", ".join(
                        f"<{t['tag']}>{(' ' + t['label']) if t['label'] else ''} "
                        f"{t['w']}x{t['h']}"
                        for t in worst
                    )
                    more = len(m["smallTargets"]) - len(worst)
                    findings.append(
                        f"{name} ({w}x{h}): {len(m['smallTargets'])} interactive "
                        f"element(s) below {MIN_TOUCH_PX}x{MIN_TOUCH_PX}px — {shown}"
                        + (f", +{more} more" if more > 0 else "")
                    )
                    line += f"  ✗ {len(m['smallTargets'])} target(s) < {MIN_TOUCH_PX}px"
                else:
                    line += "  ✓"

                if errors:
                    findings.append(f"{name} ({w}x{h}): JavaScript error — {errors[0]}")
                    line += f"  ✗ JS error"

                if not quiet:
                    print(line)
                page.close()
        finally:
            browser.close()

    print()
    if findings:
        print(f"✗ FAIL — {len(findings)} finding(s) across {len(VIEWPORTS)} viewports:")
        for f in findings:
            print(f"    • {f}")
        print(f"\n  Screenshots in {out_dir}/ — look at them; a clean measurement is not a clean layout.")
        return 1

    print(f"✓ PASS — {len(VIEWPORTS)} viewports checked, no overflow, no undersized touch targets.")
    print(f"  Screenshots in {out_dir}/ — still look at them before sharing.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("artefact", type=Path, help="built .html file to check")
    ap.add_argument("--out", type=Path, default=None, help="screenshot directory (default: alongside the artefact)")
    ap.add_argument("--quiet", action="store_true", help="only print the verdict")
    args = ap.parse_args()

    if not args.artefact.is_file():
        print(f"ERROR: no such file: {args.artefact}")
        return 2

    out_dir = args.out or args.artefact.parent / "viewport-shots"
    return check(args.artefact, out_dir, args.quiet)


if __name__ == "__main__":
    sys.exit(main())
