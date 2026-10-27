#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
verify_nojs_fallback.py — prove the §3c no-JS fallback actually shows something.

Quick Look (iOS 13+/macOS) disables JavaScript when previewing an HTML file sent as a
Messages/Mail/Files attachment — deliberate Apple platform behaviour, not fixable from
inside the file (see docs/11-responsiveness-and-browser-support.md §3c). A dashboard
that follows the §3b/§3c pattern must still show *something* meaningful in that state:
a canary-gated warning banner at minimum, ideally real pre-rendered static facts.

This is a headless simulation of exactly that restriction — a Chromium context with
`java_script_enabled=False` — not a visual guess about whether the CSS "should" work.

    python3 tools/verify_nojs_fallback.py dashboards/some-dashboard.html [more.html ...] [--engines all]

Exit 0 = every file shows non-trivial static content with JS off. Non-zero = at least
one file would render as an apparently-blank/broken page in Quick Look.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from verify_standalone_core import DEFAULT_ENGINES, add_engines_arg  # noqa: E402

MIN_VISIBLE_CHARS = 80  # below this, a Quick Look viewer sees an effectively blank page


def check_nojs_fallback(html_path: pathlib.Path, shots_dir: pathlib.Path | None = None,
                        engines: tuple[str, ...] = DEFAULT_ENGINES) -> list[str]:
    """Load html_path with JavaScript disabled in each engine; return failure strings."""
    from playwright.sync_api import sync_playwright

    failures: list[str] = []
    with sync_playwright() as pw:
        for engine in engines:
            browser = getattr(pw, engine).launch()
            ctx = browser.new_context(java_script_enabled=False,
                                       viewport={"width": 1200, "height": 800})
            page = ctx.new_page()
            page.goto(html_path.resolve().as_uri())
            page.wait_for_timeout(300)
            body_text = page.inner_text("body")
            if shots_dir is not None:
                shots_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(shots_dir / f"{html_path.stem}.{engine}.png"))
            visible_chars = len(body_text.strip())
            if visible_chars < MIN_VISIBLE_CHARS:
                failures.append(
                    f"{html_path.name} ({engine}): only {visible_chars} visible chars with JS "
                    f"disabled (need >= {MIN_VISIBLE_CHARS}) — a Quick Look viewer would "
                    f"see an effectively blank page"
                )
            ctx.close()
            browser.close()
    return failures


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", metavar="FILE.html")
    add_engines_arg(ap)
    args = ap.parse_args(argv)

    all_failures: list[str] = []
    for arg in args.files:
        path = pathlib.Path(arg)
        if not path.exists():
            all_failures.append(f"{arg}: file does not exist")
            continue
        failures = check_nojs_fallback(path, engines=args.engines)
        if failures:
            all_failures.extend(failures)
        else:
            print(f"PASS  {path.name}  shows static content with JS disabled "
                  f"({', '.join(args.engines)})")

    if all_failures:
        print("FAIL")
        for f in all_failures:
            print(f"  \u2717 {f}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
