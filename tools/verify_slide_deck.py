#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Verify a self-contained HTML presentation in real browsers.

The verifier opens the artefact through file://, visits every slide, checks that
controls stay inside the viewport, exercises navigation and fullscreen behavior,
and writes screenshots plus contact sheets.

Run with:
    uv run --extra verify python tools/verify_slide_deck.py deck.html --out /tmp/deck-check
    (add --engines all for firefox too; the default is chromium and webkit)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_standalone_core import ENGINES, engines_arg  # noqa: E402

try:
    from playwright.sync_api import BrowserType, Page, sync_playwright
except ImportError:
    print("ERROR: Playwright is required. Run with: uv run --with playwright ...", file=sys.stderr)
    raise SystemExit(2)


VIEWPORTS = {
    "desktop-1600x900": (1600, 900, False),
    "desktop-1366x768": (1366, 768, False),
    "mobile-landscape-844x390": (844, 390, True),
    "mobile-portrait-390x844": (390, 844, True),
}


@dataclass
class Result:
    engine: str
    viewport: str
    slides: int
    fullscreen: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("deck", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Use Chromium only and the two mobile viewports.",
    )
    parser.add_argument(
        "--engines",
        type=engines_arg,
        default=None,
        metavar="LIST",
        help=f"comma-separated subset of {','.join(ENGINES)}, or all "
             "(default: chromium,webkit; chromium with --quick)",
    )
    return parser.parse_args()


def expected_counter_text(element: Any) -> str:
    target = float(element.get_attribute("data-to"))
    divisor_text = element.get_attribute("data-div")
    divisor = float(divisor_text) if divisor_text else 1.0
    suffix = element.get_attribute("data-suffix") or ""
    if divisor == 1:
        value = str(round(target))
    else:
        decimals = len(str(int(divisor))) - 1
        value = f"{target / divisor:.{decimals}f}".replace(".", ",")
    return value + suffix


def assert_inside_viewport(box: Optional[dict[str, float]], width: int, height: int, label: str) -> None:
    if box is None:
        raise AssertionError(f"{label}: element is not visible")
    if (
        box["x"] < -1
        or box["y"] < -1
        or box["x"] + box["width"] > width + 1
        or box["y"] + box["height"] > height + 1
    ):
        raise AssertionError(f"{label}: outside viewport {width}x{height}: {box}")


def verify_page(
    page: Page,
    deck_url: str,
    deck_path: Path,
    out: Path,
    engine: str,
    viewport_name: str,
    width: int,
    height: int,
) -> Result:
    page_errors: list[str] = []
    external_requests: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))

    def record_request(request: Any) -> None:
        if request.url.split("#", 1)[0] != deck_url.split("#", 1)[0]:
            external_requests.append(request.url)

    page.on("request", record_request)
    page.goto(deck_url)
    page.wait_for_timeout(150)

    slide_count = page.locator(".slide").count()
    if slide_count < 1:
        raise AssertionError(f"{engine}/{viewport_name}: no slides")

    assert_inside_viewport(
        page.locator("#controls").bounding_box(),
        width,
        height,
        f"{engine}/{viewport_name}/controls",
    )

    for index in range(slide_count):
        if index:
            page.locator("#nnext").click()
        page.wait_for_timeout(1250 if page.locator(".slide.active [data-to]").count() else 450)
        counter = page.locator("#counter").text_content()
        expected_counter = f"{index + 1} / {slide_count}"
        if counter != expected_counter:
            raise AssertionError(
                f"{engine}/{viewport_name}: expected {expected_counter!r}, got {counter!r}"
            )
        active = page.locator(".slide.active")
        if active.count() != 1:
            raise AssertionError(f"{engine}/{viewport_name}: expected one active slide")

        for numeric in active.locator("[data-to]").all():
            expected = expected_counter_text(numeric)
            actual = numeric.text_content()
            if actual != expected:
                raise AssertionError(
                    f"{engine}/{viewport_name}/slide-{index + 1}: "
                    f"animated value {actual!r}, expected {expected!r}"
                )

        screenshot = out / f"{engine}-{viewport_name}-slide-{index + 1:02d}.png"
        page.screenshot(path=str(screenshot))

    if not page.locator("#nnext").is_disabled():
        raise AssertionError(f"{engine}/{viewport_name}: Next is enabled on final slide")
    page.locator("#nprev").click()
    if page.locator("#counter").text_content() != f"{slide_count - 1} / {slide_count}":
        raise AssertionError(f"{engine}/{viewport_name}: Previous button failed")
    page.keyboard.press("Home")
    if page.locator("#counter").text_content() != f"1 / {slide_count}":
        raise AssertionError(f"{engine}/{viewport_name}: Home key failed")
    page.keyboard.press("End")
    if page.locator("#counter").text_content() != f"{slide_count} / {slide_count}":
        raise AssertionError(f"{engine}/{viewport_name}: End key failed")

    page.locator("#fullscreen").click()
    page.wait_for_timeout(200)
    fullscreen = page.evaluate(
        """() => ({
          active: !!(document.fullscreenElement || document.webkitFullscreenElement),
          fallback: document.querySelector('#toast').classList.contains('show') &&
                    document.querySelector('#toast').textContent.length > 0
        })"""
    )
    if not fullscreen["active"] and not fullscreen["fallback"]:
        raise AssertionError(f"{engine}/{viewport_name}: fullscreen failed without fallback")

    if page_errors:
        raise AssertionError(f"{engine}/{viewport_name}: JavaScript errors: {page_errors}")
    if external_requests:
        raise AssertionError(
            f"{engine}/{viewport_name}: external requests from {deck_path.name}: "
            + ", ".join(sorted(set(external_requests)))
        )

    return Result(
        engine=engine,
        viewport=viewport_name,
        slides=slide_count,
        fullscreen="entered" if fullscreen["active"] else "fallback",
    )


def build_contact_sheet(page: Page, out: Path, engine: str, viewport: str, slides: int) -> Path:
    cards = "".join(
        f'<figure><b>{index}</b><img src="{engine}-{viewport}-slide-{index:02d}.png"></figure>'
        for index in range(1, slides + 1)
    )
    html = out / f"{engine}-{viewport}-contact.html"
    html.write_text(
        "<!doctype html><meta charset=utf-8><style>"
        "*{box-sizing:border-box}body{margin:0;background:#111417;color:#fff;font:16px system-ui}"
        ".grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:8px}"
        "figure{margin:0;padding:6px;background:#202428}b{display:block;margin-bottom:4px}"
        "img{display:block;width:100%;height:auto}</style>"
        f'<div class="grid">{cards}</div>',
        encoding="utf-8",
    )
    page.goto(html.resolve().as_uri())
    target = out / f"{engine}-{viewport}-contact.png"
    page.screenshot(path=str(target), full_page=True)
    return target


def main() -> int:
    args = parse_args()
    deck = args.deck.resolve()
    if not deck.is_file():
        print(f"ERROR: deck not found: {deck}", file=sys.stderr)
        return 2
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    deck_url = deck.as_uri()
    results: list[Result] = []

    with sync_playwright() as playwright:
        names = args.engines or (("chromium",) if args.quick else ("chromium", "webkit"))
        engines: list[tuple[str, BrowserType]] = [(n, getattr(playwright, n)) for n in names]
        viewports = VIEWPORTS
        if args.quick:
            viewports = {name: value for name, value in VIEWPORTS.items() if "mobile" in name}

        for engine_name, browser_type in engines:
            browser = browser_type.launch()
            for viewport_name, (width, height, mobile) in viewports.items():
                page = browser.new_page(
                    viewport={"width": width, "height": height},
                    has_touch=mobile,
                    # Firefox has no mobile emulation and rejects is_mobile; touch stays on.
                    **({"is_mobile": mobile} if engine_name != "firefox" else {}),
                )
                result = verify_page(
                    page,
                    deck_url,
                    deck,
                    out,
                    engine_name,
                    viewport_name,
                    width,
                    height,
                )
                results.append(result)
                build_contact_sheet(page, out, engine_name, viewport_name, result.slides)
                page.close()
                print(
                    f"PASS {engine_name}/{viewport_name}: {result.slides} slides; "
                    f"fullscreen={result.fullscreen}"
                )
            browser.close()

    summary = {
        "deck": str(deck),
        "results": [result.__dict__ for result in results],
    }
    (out / "verification.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"PASS: screenshots and summary written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
