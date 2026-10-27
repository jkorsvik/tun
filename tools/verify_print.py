#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Measure an artefact that is meant to be printed on one sheet of A4.

The other verifiers measure a screen: a viewport, a scroll, a touch target. A one-pager has
none of that, and its characteristic failure is different. It does not break. It grows. A
sentence runs long, a fifth bullet is added, a chart gets one more bar, and the page that was
one page becomes two, with the footer alone on the second one. Nobody notices on screen,
because on screen everything scrolls.

So this measures the printed page, in print media, at A4:

  1. one page      — the document's height fits the A4 page box at 96 dpi, and the PDF
                     Chromium produces really is one page. Measured twice on purpose: the
                     height is what the CSS says, the PDF is what the printer gets.
  2. nothing spills — no element reaches past the right edge or below the page box, which is
                     where a wide table and a long word both end up.
  3. the sheet fills — the sheet occupies the whole page. A sheet that stops at 60 % is a
                     page with an empty third, which prints as a mistake.
  4. type floor    — every text run renders at least `--text-floor-px` (default 12 px, which
                     is 9 pt at 96 dpi). A printed page cannot be zoomed.
  5. self-contained — no script file, no remote resource, no network: the sheet must print
                     from a folder with no connection.

What it does NOT check, and says so on every run: ink coverage and greyscale legibility
beyond contrast, page bleed and printer margins of a specific device, fonts embedded, and
whether the numbers are right. Those need a printer and a person.

Usage:
    python3 tools/verify_print.py path/to/sheet.html [--engines chromium] [--text-floor-px 12]

Exit codes: 0 no findings, 1 at least one finding, 2 could not run.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_standalone_core import add_engines_arg  # noqa: E402

# A4 at 96 dpi: 210 mm x 297 mm. The page box the CSS declares with @page size:A4.
A4_W = 794
A4_H = 1123
SLACK = 1.0          # a hairline of sub-pixel rounding is not a second page

PROBE_JS = r"""
(floor) => {
  const out = {findings: [], notes: {}};
  const de = document.documentElement;
  const sheet = document.querySelector(".sheet") || document.body;
  const box = sheet.getBoundingClientRect();

  out.notes.height = Math.round(de.scrollHeight);
  out.notes.width = Math.round(de.scrollWidth);
  out.notes.sheetH = Math.round(box.height);
  out.notes.sheetW = Math.round(box.width);

  /* Everything a printer can paint, measured where it lands, not where its parent says. */
  let lowest = 0, rightmost = 0, lowestWho = "", rightWho = "";
  document.querySelectorAll(".sheet *").forEach(el => {
    if (!el.textContent.trim() && el.tagName !== "IMG") return;
    const r = el.getBoundingClientRect();
    if (!r.width && !r.height) return;
    if (r.bottom > lowest) { lowest = r.bottom; lowestWho = el.className || el.tagName; }
    if (r.right > rightmost) { rightmost = r.right; rightWho = el.className || el.tagName; }
  });
  out.notes.lowest = Math.round(lowest);
  out.notes.lowestWho = String(lowestWho);
  out.notes.rightmost = Math.round(rightmost);
  out.notes.rightWho = String(rightWho);

  /* The type floor: the smallest *rendered* size, which is why an SVG viewBox and a CSS
     transform both count against it. */
  let smallest = Infinity, smallWho = "";
  const walker = document.createTreeWalker(sheet, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const text = walker.currentNode.nodeValue.trim();
    if (!text) continue;
    const el = walker.currentNode.parentElement;
    if (!el) continue;
    const size = parseFloat(getComputedStyle(el).fontSize);
    if (size < smallest) { smallest = size; smallWho = el.className || el.tagName; }
  }
  out.notes.smallest = smallest === Infinity ? 0 : Math.round(smallest * 100) / 100;
  out.notes.smallWho = String(smallWho);

  if (out.notes.height > A4_H + 1) out.findings.push({
    rule: "one page",
    detail: `the document is ${out.notes.height} px tall, past the ${A4_H} px page box: it prints on a second page`});
  if (out.notes.width > A4_W + 1) out.findings.push({
    rule: "one page",
    detail: `the document is ${out.notes.width} px wide, past the ${A4_W} px page box`});
  if (lowest > A4_H + 1) out.findings.push({
    rule: "nothing spills",
    detail: `"${out.notes.lowestWho}" reaches ${out.notes.lowest} px, below the page box`});
  if (rightmost > A4_W + 1) out.findings.push({
    rule: "nothing spills",
    detail: `"${out.notes.rightWho}" reaches ${out.notes.rightmost} px, past the right edge`});
  if (box.height < A4_H - 2) out.findings.push({
    rule: "the sheet fills",
    detail: `the sheet is ${out.notes.sheetH} px of a ${A4_H} px page, so the page has an empty strip`});
  if (out.notes.smallest && out.notes.smallest < floor) out.findings.push({
    rule: "type floor",
    detail: `${out.notes.smallest} px text in "${out.notes.smallWho}": the floor is ${floor} px`});
  return out;
}
""".replace("A4_H", str(A4_H)).replace("A4_W", str(A4_W))

# A PDF's page tree states how many leaves it holds. Chromium writes it uncompressed, and a
# count from the file the printer is given is the only proof that the CSS height did not lie.
PDF_PAGES = re.compile(rb"/Type\s*/Pages[^>]*?/Count\s+(\d+)", re.S)

NOT_CHECKED = ("ink coverage and greyscale legibility beyond contrast, bleed and the "
               "non-printable margin of a particular printer, embedded fonts, and whether "
               "the numbers are right")


def static_findings(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    out = []
    if not re.search(r"@page\s*{[^}]*size\s*:\s*A4", text, re.I):
        out.append({"rule": "A4 declared",
                    "detail": "no `@page{size:A4}`: the printer decides the paper, not the file"})
    if re.search(r"<script[^>]+src=", text, re.I):
        out.append({"rule": "self-contained",
                    "detail": "a script is loaded from a file: printing from a folder without "
                              "it changes the page"})
    remote = re.findall(r"""(?:src|href)\s*=\s*["'](https?://[^"']+)""", text, re.I)
    remote += re.findall(r"""url\(\s*["']?(https?://[^)"']+)""", text, re.I)
    if remote:
        out.append({"rule": "self-contained",
                    "detail": f"a remote resource is referenced: {remote[0]}"})
    return out


def check(path: Path, engines: tuple[str, ...], quiet: bool, floor: float) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright is not installed, so nothing was measured.")
        print("       install: uv sync --extra verify && uv run playwright install chromium")
        print("       This is an error, not a skip: a check that cannot run must not pass.")
        return 2

    findings = static_findings(path)
    for f in findings:
        print(f"    {f['rule']:<16} {f['detail']}")

    url = path.resolve().as_uri()
    total = len(findings)
    with sync_playwright() as p:
        for engine in engines:
            browser = getattr(p, engine).launch()
            try:
                page = browser.new_page(viewport={"width": A4_W, "height": A4_H})
                page.goto(url)
                page.emulate_media(media="print")
                page.wait_for_timeout(300)
                result = page.evaluate(PROBE_JS, floor)
                pdf = page.pdf(format="A4", print_background=True)
            finally:
                browser.close()
            notes = result["notes"]
            pages = PDF_PAGES.search(pdf)
            page_count = int(pages.group(1)) if pages else 0
            if page_count == 0:
                result["findings"].append({
                    "rule": "one page",
                    "detail": "the PDF states no page count, so the printed length is unproven"})
            elif page_count > 1:
                result["findings"].append({
                    "rule": "one page",
                    "detail": f"the PDF is {page_count} pages, not one"})
            total += len(result["findings"])
            if not quiet:
                print(f"  · {engine}: {notes['width']}x{notes['height']} px of "
                      f"{A4_W}x{A4_H}, {page_count} PDF page(s), smallest text "
                      f"{notes['smallest']} px in \"{notes['smallWho']}\"")
            for f in result["findings"]:
                print(f"    {f['rule']:<16} {f['detail']}")

    if not quiet:
        print(f"\n  not checked here: {NOT_CHECKED}.")
        print("  a green run means one A4 page with nothing spilled and no text under the "
              "floor, not 'a good one-pager'.")
    return 0 if total == 0 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("artefact", type=Path, help="the built .html file")
    ap.add_argument("--quiet", action="store_true", help="only print findings")
    ap.add_argument("--text-floor-px", type=float, default=12.0, metavar="PX",
                    help="smallest allowed rendered text (default 12 px, which is 9 pt)")
    add_engines_arg(ap)
    args = ap.parse_args(argv)

    if not args.artefact.is_file():
        print(f"ERROR: no such file: {args.artefact}")
        return 2
    print(f"verify_print: {args.artefact}")
    code = check(args.artefact, tuple(args.engines), args.quiet, args.text_floor_px)
    print("verify_print: " + ("PASS" if code == 0 else "FINDINGS" if code == 1 else "ERROR"))
    return code


if __name__ == "__main__":
    sys.exit(main())
