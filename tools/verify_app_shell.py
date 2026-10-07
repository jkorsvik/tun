#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
verify_app_shell.py — prove the row-26 app shell actually behaves, at runtime.

tools/verify_standalone_core.py's no-pinned-header check is static: it reads the CSS and
rejects the shape docs/01-tenant-constraints.md row 26 measured as broken. This file is
the other half — it opens the artefact in a real browser, scrolls it, and asserts the
header does not move and nothing gets painted over it. Static check says "not the bad
shape"; this says "and the good shape works".

Row 26 itself cannot be reproduced locally (it is a SharePoint-preview behaviour), so
this is NOT a test for row 26. It is a test that the replacement shell is correctly
built, which is the part a local browser CAN settle. Do not read a pass here as
clearance for the preview surface; that still needs a human (see row 26's own wording).

The vacuity guard is the point of this file, not a detail. The first version of this
check scrolled a container that had nothing to scroll, and reported "header did not move"
with total confidence. A scroll assertion on a page that fits its viewport proves
nothing. So: the viewport is shrunk until the container genuinely overflows, and if no
height produces overflow the run FAILS rather than passing quietly.

    python3 tools/verify_app_shell.py <path-to.html> [--header SEL] [--shell SEL]

Needs the verify extra:  uv sync --extra verify
"""
from __future__ import annotations

import argparse
import pathlib
import sys

# Heights tried in order until the shell overflows by MIN_SCROLL_ROOM. Widths stay
# desktop-ish on purpose: this checks the shell, not the responsive layout (that is
# tools/verify_viewports.py's job).
PROBE_HEIGHTS = (900, 600, 400, 300, 240, 200)
MIN_SCROLL_ROOM = 60

FIND_SHELL = """() => {
  const cands = [...document.querySelectorAll('*')].filter(e => {
    const s = getComputedStyle(e);
    return (s.overflowY === 'auto' || s.overflowY === 'scroll') &&
           e.scrollHeight > e.clientHeight + 4;
  });
  if (!cands.length) return null;
  cands.sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight));
  const e = cands[0];
  return e.id ? '#' + e.id : (e.className ? '.' + String(e.className).split(/\\s+/)[0] : e.tagName.toLowerCase());
}"""

FIND_HEADER = """() => {
  for (const sel of ['#topbar', 'header', '[role=banner]', '.topbar', '#header']) {
    const e = document.querySelector(sel);
    if (e && e.getBoundingClientRect().height > 0) return sel;
  }
  return null;
}"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--header", default=None, help="header selector (auto-detected if omitted)")
    ap.add_argument("--shell", default=None, help="scrolling-container selector (auto-detected)")
    ap.add_argument("--width", type=int, default=1200)
    args = ap.parse_args()

    path = pathlib.Path(args.path).resolve()
    if not path.exists():
        print(f"✗ not found: {path}")
        return 2

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("✗ playwright not installed — cannot verify the shell at runtime.")
        print("  This check cannot be skipped into a pass: install it (uv sync --extra verify).")
        return 2

    failures: list[str] = []
    print(f"verifying app shell: {path.name}")
    print("─" * 62)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": args.width, "height": PROBE_HEIGHTS[0]})
        page.goto(path.as_uri())
        page.wait_for_timeout(400)

        header_sel = args.header or page.evaluate(FIND_HEADER)
        if not header_sel:
            print("  ✗ no header found — pass --header, or this artefact has no app shell")
            browser.close()
            return 1
        print(f"  header             {header_sel}")

        # 1. The header must not be positioned. Row 26 rejected both fixed and sticky;
        #    the shell works precisely because the header needs no positioning at all.
        pos = page.eval_on_selector(header_sel, "e => getComputedStyle(e).position")
        if pos in ("fixed", "sticky"):
            failures.append(f"header computed position:{pos} — row 26 rejected both")
            print(f"  ✗ header position   {pos} (must be static/relative)")
        else:
            print(f"  ✓ header position   {pos}")

        # 2. Find a viewport where the shell genuinely overflows. Without this, every
        #    assertion below is vacuous.
        shell_sel = args.shell
        room = 0
        for height in PROBE_HEIGHTS:
            page.set_viewport_size({"width": args.width, "height": height})
            page.wait_for_timeout(150)
            sel = shell_sel or page.evaluate(FIND_SHELL)
            if not sel:
                continue
            geo = page.eval_on_selector(sel, "e => ({sh: e.scrollHeight, ch: e.clientHeight})")
            if geo["sh"] - geo["ch"] >= MIN_SCROLL_ROOM:
                shell_sel, room = sel, geo["sh"] - geo["ch"]
                print(f"  ✓ scrolling shell   {sel} — {room}px of scroll room at {args.width}x{height}")
                break
        if room < MIN_SCROLL_ROOM:
            print(f"  ✗ VACUOUS           no viewport in {PROBE_HEIGHTS} makes a container overflow by")
            print(f"                      {MIN_SCROLL_ROOM}px. Every scroll assertion would be")
            print("                      meaningless, so this is a FAIL, not a skip.")
            browser.close()
            return 1

        # 3. The document itself must not scroll. If it does, the header is riding on
        #    the page and row 26's whole failure mode is back.
        doc_scrolls = page.evaluate(
            "() => {const e = document.scrollingElement; return e.scrollHeight > e.clientHeight + 4;}"
        )
        if doc_scrolls:
            failures.append("the document scrolls — the shell must be the only scrolling area")
            print("  ✗ document scroll   document scrolls as well as the shell")
        else:
            print("  ✓ document scroll   body does not scroll; only the shell does")

        # 4. Scroll to the very bottom, then re-measure.
        before = page.eval_on_selector(header_sel, "e => e.getBoundingClientRect().bottom")
        page.eval_on_selector(shell_sel, "e => e.scrollTop = 1e7")
        page.wait_for_timeout(250)
        moved = page.eval_on_selector(shell_sel, "e => e.scrollTop")
        after = page.eval_on_selector(header_sel, "e => e.getBoundingClientRect().bottom")

        if moved < room - 2:
            failures.append(f"shell reached only {moved}px of {room}px — it did not really scroll")
            print(f"  ✗ scrolled          {moved}/{room}px")
        else:
            print(f"  ✓ scrolled          {moved}/{room}px (reached the bottom)")

        if abs(after - before) > 1:
            failures.append(f"header moved during scroll: bottom {before} -> {after}")
            print(f"  ✗ header stays      bottom {before} -> {after}")
        else:
            print(f"  ✓ header stays      bottom {before} through the whole scroll")

        # 5. The exact row-26 symptom: content painted on top of the header. Sample
        #    across the header's width, not just its centre, so a single wide element
        #    cannot hide behind one lucky probe point.
        #
        #    Form controls and buttons are not counted as intruders. examples/13 layers
        #    its hamburger/theme/info controls ON TOP of the topbar on purpose (they are
        #    body-level siblings so the CSS sibling combinator can reach the panels), and
        #    a control sitting in the header row is chrome, not content. Row 26's symptom
        #    was the page body covering the header. Anything skipped is printed, so the
        #    exemption is visible rather than silent.
        probe = page.evaluate(
            """(sel) => {
              const bar = document.querySelector(sel);
              const r = bar.getBoundingClientRect();
              const y = r.top + r.height / 2;
              const CHROME = 'input,label,button,[role=button],summary';
              const out = {intruders: [], chrome: []};
              for (const f of [0.1, 0.3, 0.5, 0.7, 0.9]) {
                const el = document.elementFromPoint(r.left + r.width * f, y);
                if (!el || el.closest(sel)) continue;
                const name = `${Math.round(f*100)}%: ${el.tagName.toLowerCase()}` +
                             (el.id ? '#' + el.id : '');
                (el.closest(CHROME) ? out.chrome : out.intruders).push(name);
              }
              return out;
            }""",
            header_sel,
        )
        if probe["chrome"]:
            print(f"  · chrome over bar   {', '.join(probe['chrome'])} (controls, not content — allowed)")
        if probe["intruders"]:
            failures.append(f"content painted over the header at {', '.join(probe['intruders'])}")
            print(f"  ✗ nothing on top    {', '.join(probe['intruders'])}")
        else:
            print("  ✓ nothing on top    no page content over the header, full width")

        shot = path.with_name(path.stem + ".shell-bottom.png")
        page.screenshot(path=str(shot))
        print(f"  ✓ screenshot        {shot.name} (scrolled to the bottom — look at it)")
        browser.close()

    print("─" * 62)
    if failures:
        print(f"\n✗ FAIL — {len(failures)} problem(s) in the app shell:")
        for f in failures:
            print(f"    • {f}")
        return 1
    print("\n✓ PASS — the shell scrolls correctly and the header stays put, in a LOCAL")
    print("  browser. Row 26 was measured in SharePoint's inline preview, which this")
    print("  cannot reach; a human still has to open it there once.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
