#!/usr/bin/env python3
"""End-to-end checks for the consolidated Tún Explorer, in Chromium and WebKit."""
from __future__ import annotations

import json
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_showcase  # noqa: E402

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
    ok('class="primary"' in text and "https://github.com/jkorsvik/tun" in text,
       "the hero does not offer both getting started and source code")
    ok("CONTRIBUTING.md" in text and 'id="stage-source"' in text,
       "the gallery has no contribution route or example source link")
    for leaked in ("https://example.com/tun/issues", "[issue #", "Rører ikke", "Eksempel AS-branding"):
        ok(leaked not in text, f"internal note leaked into the public gallery: {leaked}")
    payloads = re.findall(r'data-live="([^"]+)"', text)
    ok(len(payloads) == 50 and all(p.startswith("gzip:") for p in payloads),
       "every live example must use the gzip payload contract")
    first = build_showcase.read_example(ROOT / "examples/01-hello-dashboard")
    ok(build_showcase.decode_live(payloads[0]) == build_showcase.inline_siblings(first["page"]),
       "the first gzip payload does not decode to its source page")
    template = (ROOT / "templates" / "showcase.html").read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "35-visual-identity.md").read_text(encoding="utf-8")
    brand_values = ("#030a07", "#07150f", "#0d2b21", "#b4c6bb", "#effcf4", "#c1d3c9", "#f7f7f5")
    ok(all(value in template for value in brand_values), "the Explorer is missing a shared Tún brand value")
    ok(all(value in guide for value in brand_values), "the style guide is missing a shared Tún brand value")
    ok('class="explorer-brand"' in template and "M4 15 10 20 21 4" in template,
       "the Explorer does not carry the shared Tún mark")
    ok("#7fa8e0" not in template and "#1b2a4a" not in template,
       "the old generic blue identity is still in the Explorer")
    ok("#55d68a" not in template, "the bright mint glow is back in the Explorer")


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
            ok(page.locator("#stage-pos").text_content().strip().endswith("01"),
               "the Explorer does not start with example 01")
            ok(page.locator("#stage-prev").is_disabled() and not page.locator("#stage-next").is_disabled(),
               "the first example has the wrong navigation state")
            ok(page.locator("#stage-source").get_attribute("href").endswith("/examples/01-hello-dashboard"),
               "the example source link is wrong")
            page.goto(url + "?example=55", wait_until="load")
            labels = page.locator("#stage-frame").content_frame.locator(".task-label")
            labels.first.wait_for()
            ok(labels.count() == 7,
               "the 3D example did not render its steps")
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
            page.wait_for_function("document.fullscreenElement===document.documentElement", timeout=2500)
            ok(page.evaluate("document.fullscreenElement===document.documentElement"),
               f"{engine}: Full screen did not enter the browser Fullscreen API")
            page.locator("#viewer").wait_for(state="visible")
            ok(page.evaluate("!!document.elementFromPoint(innerWidth/2,innerHeight/2).closest('#viewer')"),
               f"{engine}: the fullscreen page covers the dialog and intercepts clicks")
            box = page.locator("#viewer").bounding_box()
            ok(box["width"] >= 1440 * 0.8 and box["height"] >= 1000 * 0.8,
               "full-screen dialog is too small on desktop")
            ok("03" in page.locator("#pos").text_content(), "full-screen opened the wrong example")
            page.locator("#big").content_frame.get_by_text("Transaksjonsoversikt", exact=False).first.wait_for()
            page.locator("#big").element_handle().content_frame().wait_for_load_state("load")
            ok("transaksjonsoversikt" in page.locator("#big").content_frame.locator("body").inner_text().lower(),
               "full-screen did not render the cube")
            page.screenshot(path=str(pathlib.Path.home() / ".raiwork" / "tmp" / f"explorer-{engine}-fullscreen.png"))
            page.keyboard.press("Escape")
            page.locator("#viewer").wait_for(state="hidden", timeout=2500)
            ok(not page.locator("#viewer").is_visible(), "Escape did not close full-screen")
            ok(page.evaluate("document.activeElement.id") == "stage-expand",
               "full-screen did not return focus to its opener")
            page.locator("#stage-expand").click()
            page.locator("#big").content_frame.get_by_text("Transaksjonsoversikt", exact=False).first.wait_for()
            page.locator("#big").element_handle().content_frame().wait_for_load_state("load")
            page.evaluate("window._dialogTestMessages=[];window.addEventListener('message',e=>window._dialogTestMessages.push(e.data))")
            page.locator("#big").content_frame.get_by_role("button", name="Nullstill filtre", exact=True).click()
            page.locator("#big").content_frame.get_by_role("button", name="Nullstill filtre", exact=True).press("Escape")
            page.locator("#viewer").wait_for(state="hidden", timeout=2500)
            diagnostic = page.evaluate("JSON.stringify({active:document.activeElement.id,messages:window._dialogTestMessages})")
            ok(not page.locator("#viewer").is_visible(), f"{engine}: Escape inside the artefact did not close full-screen: {diagnostic}")
            page.locator("#stage-expand").click()
            page.locator("#next").click()
            ok("04" in page.locator("#pos").text_content(), "full-screen Next did not advance")
            page.locator("#next").focus()
            page.keyboard.press("ArrowRight")
            ok("05" in page.locator("#pos").text_content(), "full-screen ArrowRight did not advance")
            page.locator("#shut").click()
            page.goto(url + "?example=55", wait_until="load")
            with tempfile.TemporaryDirectory() as raw:
                with page.expect_download() as pending:
                    page.locator("#stage-download").click()
                target = pathlib.Path(raw) / "task.html"
                pending.value.save_as(target)
                ok(target.read_bytes() == TASK.read_bytes(), "download is not byte-exact")
            page.locator('[data-lang="en"]').click()
            ok(page.locator('[data-path="all"]').text_content() == "All possibilities",
               "language switch did not update the guided paths")
            ok(page.locator(".hero-actions a.primary").get_attribute("href") == "https://tun.community/en/#first",
               "the getting-started link did not follow the language")
            page.locator("#stage-share").click()
            page.wait_for_function("document.querySelector('#stage-share').textContent === 'Copied'", timeout=2500)
            page.screenshot(path=str(pathlib.Path.home() / ".raiwork" / "tmp" / f"explorer-{engine}-desktop.png"))
            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(url, wait_until="load")
            ok(page.locator(".hero-actions a.primary").is_visible(), "mobile hides the start action")
            ok(page.locator(".hero-actions a").nth(1).is_visible(), "mobile hides the source action")
            ok(page.evaluate("document.scrollingElement.scrollWidth <= innerWidth"),
               "mobile Explorer overflows horizontally")
            stage = page.locator(".stage-top").bounding_box()
            ok(stage["x"] >= 0 and stage["x"] + stage["width"] <= 390,
               "mobile stage header is clipped")
            page.locator("#stage-expand").click()
            page.locator("#viewer").wait_for(state="visible")
            page.wait_for_function("const p=document.querySelector('#pos').getBoundingClientRect(),b=document.querySelector('#prev').getBoundingClientRect();p.bottom<=b.top+1", timeout=2500)
            mobile_box = page.locator("#viewer").bounding_box()
            ok(mobile_box["width"] >= 390 * 0.9 and mobile_box["height"] >= 844 * 0.8,
               "full-screen dialog is too small on mobile")
            ok(mobile_box["x"] >= 0 and mobile_box["x"] + mobile_box["width"] <= 390,
               "full-screen dialog overflows the phone viewport")
            pos_box = page.locator("#pos").bounding_box()
            prev_box = page.locator("#prev").bounding_box()
            ok(pos_box["y"] + pos_box["height"] <= prev_box["y"] + 1,
               "mobile full-screen position and controls are cramped together")
            ok("01" in page.locator("#pos").text_content(), "mobile full-screen opened the wrong example")
            page.locator("#next").click()
            ok("02" in page.locator("#pos").text_content(), "mobile full-screen Next did not advance")
            page.screenshot(path=str(pathlib.Path.home() / ".raiwork" / "tmp" / f"explorer-{engine}-mobile-fullscreen.png"))
            page.locator("#shut").click()
            ok(not page.locator("#viewer").is_visible(), "mobile Close did not dismiss full-screen")
            page.wait_for_timeout(350)
            page.screenshot(path=str(pathlib.Path.home() / ".raiwork" / "tmp" / f"explorer-{engine}-mobile.png"))
            page.evaluate("document.documentElement.requestFullscreen=undefined")
            page.locator("#stage-expand").click()
            page.locator("#viewer").wait_for(state="visible")
            ok(page.locator("#viewer").is_visible() and not page.evaluate("!!document.fullscreenElement"),
               f"{engine}: modal fallback did not open without Fullscreen API support")
            page.locator("#shut").click()
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
