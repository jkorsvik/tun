#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Browser smoke for the local app and its file:// snapshot.

Requires Playwright only for verification. The application has no dependencies.
"""
from __future__ import annotations

import argparse
import contextlib
import pathlib
import sys
import tempfile
import threading
import time

from playwright.sync_api import expect, sync_playwright

from app import Store, export_snapshot, make_server

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
from verify_standalone_core import add_engines_arg  # noqa: E402

PASSED = 0
FAILED = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    PASSED += bool(condition)
    FAILED += not condition
    print(f"  {'PASS' if condition else 'FAIL'} {label}" + (f" — {detail}" if detail and not condition else ""))


@contextlib.contextmanager
def running(store: Store):
    store.initialize()
    store.seed()
    server = make_server(store, port=0, quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}", server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def no_overflow(page) -> bool:
    return page.evaluate("document.scrollingElement.scrollWidth <= window.innerWidth")


def smoke_engine(playwright, engine: str, output: pathlib.Path) -> None:
    print(f"\n{engine}: live validation, writes, responsive layout and snapshot")
    with tempfile.TemporaryDirectory() as raw:
        store = Store(pathlib.Path(raw) / "decisions.db")
        with running(store) as (base, _server):
            browser = getattr(playwright, engine).launch()
            try:
                context = browser.new_context(viewport={"width": 1280, "height": 900})
                page = context.new_page()
                requests: list[str] = []
                errors: list[str] = []
                page.on("request", lambda request: requests.append(request.url))
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base, wait_until="networkidle")
                check(f"{engine}: three seed decisions render", page.locator("article.decision").count() == 3)
                check(f"{engine}: desktop has no horizontal overflow", no_overflow(page))

                held = []

                def hold_open(route):
                    if route.request.url.endswith("status=open"):
                        held.append(route)  # Release only after the newer render is visible.
                    else:
                        route.continue_()

                page.route("**/api/decisions?status=*", hold_open)
                page.select_option("#status-filter", "open")
                page.select_option("#status-filter", "completed")
                expect(page.locator("#summary")).to_have_text("1 decision shown")
                check(f"{engine}: the stale response is really held until after the fresh render",
                      len(held) == 1)
                held[0].continue_()
                time.sleep(0.2)
                check(f"{engine}: a slower old response cannot replace the latest filter",
                      page.locator("#summary").inner_text() == "1 decision shown"
                      and page.locator("article.decision").count() == 1)
                page.unroute("**/api/decisions?status=*", hold_open)
                page.select_option("#status-filter", "all")
                expect(page.locator("#summary")).to_have_text("3 decisions shown")

                page.locator("#create-button").click()
                expect(page.locator("#decision-error")).to_have_text("Decision is required.")
                expect(page.locator("#owner-error")).to_have_text("Owner is required.")
                check(f"{engine}: server validation reaches the form",
                      page.locator("#decision-error").inner_text() == "Decision is required."
                      and page.locator("#owner-error").inner_text() == "Owner is required.")

                title = f"Smoke decision {engine}"
                page.locator("#decision").fill(title)
                page.locator("#action").fill("Export the changed log as a read-only snapshot")
                page.locator("#owner").fill("Browser smoke")
                page.locator("#due_date").fill("2027-01-15")
                page.locator("#create-button").click()
                card = page.locator("article.decision", has_text=title)
                card.wait_for()
                check(f"{engine}: create updates the shared list", card.count() == 1)
                card.locator(".complete-button").click()
                card.locator(".status-completed").wait_for()
                check(f"{engine}: complete updates status", card.locator(".status-completed").inner_text() == "Completed")
                check(f"{engine}: no JavaScript exception", not errors, "; ".join(errors))

                desktop = output / f"live-{engine}-desktop.png"
                page.screenshot(path=str(desktop), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                check(f"{engine}: phone has no horizontal overflow", no_overflow(page))
                heights = page.locator("button:visible, input:visible, select:visible").evaluate_all(
                    "nodes => nodes.map(node => node.getBoundingClientRect().height)")
                check(f"{engine}: visible controls meet the 44 px touch floor",
                      bool(heights) and min(heights) >= 44, str(heights))
                mobile = output / f"live-{engine}-phone.png"
                page.screenshot(path=str(mobile), full_page=True)
                context.close()

                external = [url for url in requests if url.startswith(("http://", "https://"))
                            and not url.startswith(base + "/")]
                check(f"{engine}: live app makes no external HTTP request", not external, str(external))

                snapshot = pathlib.Path(raw) / "snapshot.html"
                export_snapshot(store, snapshot, "Browser smoke")
                static_context = browser.new_context(
                    viewport={"width": 1280, "height": 900}, java_script_enabled=False)
                static_page = static_context.new_page()
                static_requests: list[str] = []
                static_page.on("request", lambda request: static_requests.append(request.url))
                static_page.goto(snapshot.as_uri(), wait_until="load")
                check(f"{engine}: snapshot has all four rows with JavaScript disabled",
                      static_page.locator("article.snapshot-decision").count() == 4)
                check(f"{engine}: snapshot contains the newly completed decision",
                      static_page.locator("article.decision", has_text=title).locator(".status-completed").count() == 1)
                check(f"{engine}: snapshot has no write controls or script",
                      static_page.locator("script, form, button").count() == 0)
                static_shot = output / f"snapshot-{engine}.png"
                static_page.screenshot(path=str(static_shot), full_page=True)
                static_page.set_viewport_size({"width": 390, "height": 844})
                check(f"{engine}: snapshot phone has no horizontal overflow", no_overflow(static_page))
                static_external = [url for url in static_requests if url.startswith(("http://", "https://"))]
                check(f"{engine}: snapshot makes no HTTP request", not static_external, str(static_external))
                static_context.close()
                print(f"  screenshots: {desktop}, {mobile}, {static_shot}")
            finally:
                browser.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_engines_arg(parser)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.expanduser().absolute()
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        for engine in args.engines:
            smoke_engine(playwright, engine, output)
    print(f"\n{PASSED} passed, {FAILED} failed; screenshots: {output}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
