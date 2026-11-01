#!/usr/bin/env python3
"""End-to-end checks for the consolidated Tún Explorer, in Chromium and WebKit."""
from __future__ import annotations

import json
import pathlib
import re
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = ROOT / "examples" / "54-showcase" / "oversikt.html"
TASK = ROOT / "examples" / "55-task-space" / "arbeidsflyt.html"
CHECKS = 0


def ok(condition: bool, message: str) -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(message)


def static_checks() -> None:
    text = PAGE.read_text(encoding="utf-8")
    slugs = re.findall(r'data-slug="([^"]+)"', text)
    ok(len(slugs) == 50, f"expected 50 examples, found {len(slugs)}")
    ok(len(set(slugs)) == len(slugs), "duplicate example slug")
    ok("55-task-space" in slugs, "the 3D example is not in the Explorer")
    for key in ("all", "explore", "explain", "process", "scale", "native"):
        ok(f'data-path="{key}"' in text, f"missing guided path {key}")
    for feature in ("stage-expand", "stage-download", "stage-share", "stage-progress", "stage-recipe", "stage-prev", "stage-next"):
        ok(f'id="{feature}"' in text, f"missing stage feature {feature}")
    ok("55-task-space" in text, "the task-space payload is not embedded")


def browser_checks() -> None:
    from playwright.sync_api import sync_playwright
    url = PAGE.as_uri()
    with sync_playwright() as pw:
        for engine in ("chromium", "webkit"):
            browser = getattr(pw, engine).launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url, wait_until="load")
            ok("task space" in page.locator("#stage-title").text_content().lower(),
               "the initial stage is not the task space")
            ok(page.locator("#stage-frame").content_frame.locator(".task-label").count() == 7,
               "the initial 3D stage did not render its steps")
            for path in ("all", "explore", "explain", "process", "scale", "native"):
                page.locator(f'[data-path="{path}"]').click()
                ok(page.locator("#stage-title").text_content().strip() != "",
                   f"path {path} resolved no example")
                ok(page.locator("#stage-pos").text_content().strip() != "",
                   f"path {path} has no position")
                ok(page.locator("#stage-progress").evaluate("el => el.style.width !== ''"),
                   f"path {path} has no progress")
            page.wait_for_function("!document.querySelector('.stage').classList.contains('switching')")
            page.goto(url + "?path=scale&example=03", wait_until="load")
            ok("cube" in page.locator("#stage-title").text_content().lower(), "deep link failed")
            page.locator("#stage-expand").click()
            ok(page.locator("#viewer").is_visible(), "full-screen did not open")
            page.locator("#shut").click()
            page.goto(url, wait_until="load")
            with tempfile.TemporaryDirectory() as raw:
                with page.expect_download() as pending:
                    page.locator("#stage-download").click()
                target = pathlib.Path(raw) / "task.html"
                pending.value.save_as(target)
                ok(target.read_bytes() == TASK.read_bytes(), "download is not byte-exact")
            page.locator('[data-lang="en"]').click()
            ok(page.locator('[data-path="all"]').text_content() == "All possibilities",
               "language switch did not update the guided paths")
            page.locator("#stage-share").click()
            page.wait_for_function("document.querySelector('#stage-share').textContent === 'Copied'", timeout=2500)
            page.screenshot(path=str(pathlib.Path.home() / ".raiwork" / "tmp" / f"explorer-{engine}-desktop.png"))
            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(url, wait_until="load")
            ok(page.evaluate("document.scrollingElement.scrollWidth <= innerWidth"),
               "mobile Explorer overflows horizontally")
            stage = page.locator(".stage-top").bounding_box()
            ok(stage["x"] >= 0 and stage["x"] + stage["width"] <= 390,
               "mobile stage header is clipped")
            page.screenshot(path=str(pathlib.Path.home() / ".raiwork" / "tmp" / f"explorer-{engine}-mobile.png"))
            ok(not errors, f"{engine} console errors: {errors}")
            page.close()
            context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
            plain = context.new_page(); plain.goto(url)
            ok(plain.locator("#stage-empty").is_visible(), "no-JS stage explanation is missing")
            ok(plain.locator("#grid .card").count() == 50, "no-JS collection is incomplete")
            context.close()
            browser.close()


def main() -> int:
    static_checks()
    browser_checks()
    print(json.dumps({"checks": CHECKS, "engines": ["chromium", "webkit"],
                      "paths": 6, "download": "byte-exact", "result": "PASS"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
