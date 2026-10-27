#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
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
  3. text floor           — any text rendering under the floor, 14 px by default
                            (--text-floor, for an artefact that is a picture). docs/11 §1 asks for
                            readable text at every size, and the dashboard
                            template shipped 11 px axis labels until this check
                            existed: a character count in the chart code cannot
                            see the font, and nothing measured the result.
  4. screenshot           — one per viewport, for a human to actually look at.
                            A clean measurement is not a clean layout; see the
                            marketplace skill `eksempel-html-slides`'s VALIDATE.md,
                            whose two-viewport sweep this generalises.

It never reports success when it did not run. A missing Playwright is an error with
exit code 2, not a skip — see PR #28 for why that matters.

Usage:
    python3 tools/verify_viewports.py path/to/artefact.html [--out DIR] [--quiet] [--engines all]

Exit codes: 0 all viewports clean, 1 at least one finding, 2 could not run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_standalone_core import add_engines_arg  # noqa: E402

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

# The floor every page holds, and now every artefact too. docs/11 §1: small
# print is where a reader gives up. Measured as rendered pixels, because SVG
# text is declared in user units and scaled by the viewBox: 14 units at scale
# .83 is 11.6 px on screen, and a check reading the CSS value sees neither.
MIN_TEXT_PX = 14.0
# An artefact that is a picture with text in it — a swimlane drawing fitted to the
# frame, a slide whose SVG scales with the window — cannot hold 14 px at every width
# without abandoning the thing it exists to show. Such an artefact declares its own
# floor with --text-floor, and where the shrinking only becomes severe on a phone it
# also declares --text-floor-above so the floor is still enforced at the widths a
# reader actually reads. Both are printed on every run: a waiver that CI does not
# show is a waiver nobody reviews.
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
    // An inline <a> is a run of words inside a line of text, not a control: what the
    // reader taps is the line box, whose height is the text's. Forcing prose links to
    // 44 px would break every paragraph, which is why the same guidance exempts them.
    // A link styled as a block, a pill or a list row (a nav item, a card link) is
    // still measured, and so is every button, input and select.
    if (el.tagName === 'A' && cs.display === 'inline') continue;
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
  // Text floor. Every element that owns a text node, not only leaves: a
  // paragraph holding a link is the paragraph's size that matters, and SVG text
  // is scaled by its viewBox, so the declared size is not the rendered size.
  const SVGNS = 'http://www.w3.org/2000/svg';
  let smallest = Infinity, smallestWhere = '';
  for (const el of document.querySelectorAll('body *')) {
    const owns = Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
    if (!owns) continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    let scale = 1;
    if (el.namespaceURI === SVGNS) {
      const m = el.getScreenCTM();
      scale = m ? Math.hypot(m.a, m.b) : 1;
    }
    const px = parseFloat(cs.fontSize) * scale;
    if (px < smallest) {
      smallest = px;
      smallestWhere = el.tagName.toLowerCase() +
        (el.getAttribute('class') ? '.' + el.getAttribute('class').split(' ')[0] : '') +
        ' "' + el.textContent.trim().replace(/\\s+/g, ' ').slice(0, 24) + '"';
    }
  }

  return {
    scrollWidth: doc.scrollWidth,
    clientWidth: doc.clientWidth,
    innerWidth: window.innerWidth,
    smallTargets: small,
    smallestText: isFinite(smallest) ? Math.round(smallest * 100) / 100 : null,
    smallestWhere: smallestWhere,
  };
}
""" % (INTERACTIVE_SELECTOR,)


def check(path: Path, out_dir: Path, quiet: bool, engines: tuple[str, ...],
          text_floor: float = MIN_TEXT_PX, floor_above: int = 0) -> int:
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
        for engine in engines:
            if len(engines) > 1 and not quiet:
                print(f"  · {engine}")
            browser = getattr(p, engine).launch()
            try:
                for name, w, h, touch in VIEWPORTS:
                    page = browser.new_page(
                        viewport={"width": w, "height": h},
                        has_touch=touch,
                        # Firefox has no mobile emulation and rejects is_mobile; touch stays on.
                        **({"is_mobile": touch} if engine != "firefox" else {}),
                    )
                    errors: list[str] = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.goto(url)
                    page.wait_for_timeout(700)  # let entry animations settle

                    m = page.evaluate(MEASURE_JS, MIN_TOUCH_PX)
                    tag = "" if engine == "chromium" else f".{engine}"
                    shot = out_dir / f"{path.stem}{tag}.{name}.png"
                    page.screenshot(path=str(shot), full_page=False)

                    line = f"  {name:<17} {w}x{h}"
                    where = f"{name} ({w}x{h})" + (f" [{engine}]" if len(engines) > 1 else "")
                    overflow = m["scrollWidth"] - max(m["clientWidth"], m["innerWidth"])
                    # The SVG scale factor rounds: a panel 0.07 % narrower than its
                    # viewBox reports 13.99 px for 14 px text. The tolerance is far
                    # below the 1 px that would matter, and the reason is the same one
                    # tun-site's verify-recipient.py records.
                    floored = w >= floor_above
                    if (floored and m["smallestText"] is not None
                            and m["smallestText"] < text_floor - 0.05):
                        findings.append(
                            f"{where}: text renders at {m['smallestText']:.3f} px in "
                            f"{m['smallestWhere']} — the floor is {text_floor:g} px"
                        )
                        line += f"  ✗ {m['smallestText']:g} px text"
                    if overflow > OVERFLOW_SLACK_PX:
                        findings.append(
                            f"{where}: content is {overflow}px wider than the "
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
                            f"{where}: {len(m['smallTargets'])} interactive "
                            f"element(s) below {MIN_TOUCH_PX}x{MIN_TOUCH_PX}px — {shown}"
                            + (f", +{more} more" if more > 0 else "")
                        )
                        line += f"  ✗ {len(m['smallTargets'])} target(s) < {MIN_TOUCH_PX}px"
                    else:
                        line += "  ✓"

                    if errors:
                        findings.append(f"{where}: JavaScript error — {errors[0]}")
                        line += f"  ✗ JS error"

                    if not quiet:
                        print(line)
                    page.close()
            finally:
                browser.close()

    print()
    if findings:
        print(f"✗ FAIL — {len(findings)} finding(s) across {len(VIEWPORTS)} viewports "
              f"({', '.join(engines)}):")
        for f in findings:
            print(f"    • {f}")
        print(f"\n  Screenshots in {out_dir}/ — look at them; a clean measurement is not a clean layout.")
        return 1

    floor_note = f"nothing under {text_floor:g} px"
    if floor_above:
        floor_note += f" at {floor_above} px and wider (declared floor)"
    print(f"✓ PASS — {len(VIEWPORTS)} viewports checked in {', '.join(engines)}, "
          f"no overflow, no undersized touch targets, {floor_note}.")
    print(f"  Screenshots in {out_dir}/ — still look at them before sharing.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("artefact", type=Path, help="built .html file to check")
    ap.add_argument("--out", type=Path, default=None, help="screenshot directory (default: alongside the artefact)")
    ap.add_argument("--quiet", action="store_true", help="only print the verdict")
    ap.add_argument("--text-floor", type=float, default=MIN_TEXT_PX, metavar="PX",
                    help=f"smallest rendered text this artefact claims (default {MIN_TEXT_PX:g}); "
                         "declare it in the artefact's README with the reason")
    ap.add_argument("--text-floor-above", type=int, default=0, metavar="PX",
                    help="enforce the text floor only at viewports at least this wide "
                         "(default 0 = every viewport). Overflow and touch targets are "
                         "still checked everywhere")
    add_engines_arg(ap)
    args = ap.parse_args()

    if not args.artefact.is_file():
        print(f"ERROR: no such file: {args.artefact}")
        return 2

    out_dir = args.out or args.artefact.parent / "viewport-shots"
    return check(args.artefact, out_dir, args.quiet, args.engines,
                 args.text_floor, args.text_floor_above)


if __name__ == "__main__":
    sys.exit(main())
