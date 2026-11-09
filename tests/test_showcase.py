#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The showcase stays fresh, opens every compressed example, and reads without JavaScript.

The freshness mutation uses a different valid gzip representation of the SAME page. It must
pass, proving that the gate compares decoded content rather than compressed bytes. A changed
source, a missing card and a corrupt payload must then fail. In both installed engines the
native path opens and advances the dialog; with DecompressionStream removed, the inline
fallback must reproduce every selected source document exactly.
"""
from __future__ import annotations

import base64
import gzip
import pathlib
import re
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
import build_showcase  # noqa: E402
import i18n  # noqa: E402

SHOWCASE = ROOT / "examples" / "54-showcase" / "oversikt.html"
LIVE = re.compile(r'data-live="([^"]+)"')
CHECKS = FAILED = 0


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS, FAILED
    CHECKS += 1
    print(f"  {'✓' if ok else '✗'} {what}" + ("" if ok else f" — {detail}"))
    if not ok:
        FAILED += 1


def freshness(showcase: pathlib.Path, examples: pathlib.Path) -> tuple[int, str]:
    run = subprocess.run(
        [sys.executable, str(TOOLS / "check_showcase_fresh.py"),
         "--showcase", str(showcase), "--examples", str(examples)],
        cwd=ROOT, capture_output=True, text=True, timeout=60)
    return run.returncode, (run.stdout + run.stderr).strip()


def static_checks() -> tuple[list[str], list[str]]:
    text = SHOWCASE.read_text(encoding="utf-8")
    payloads = LIVE.findall(text)
    examples = [e for e in (build_showcase.read_example(p)
                            for p in sorted(SHOWCASE.parent.parent.iterdir()) if p.is_dir())
                if e and e["dir"].resolve() != SHOWCASE.parent.resolve() and e["page"]]
    chk(len(payloads) == len(examples) and bool(payloads),
        f"all {len(examples)} selected live examples are present", str(len(payloads)))
    chk(all(p.startswith(build_showcase.LIVE_PREFIX) for p in payloads),
        "every live payload is marked as gzip")
    decoded = [build_showcase.inline_siblings(e["page"]).decode("utf-8") for e in examples]
    actual = [build_showcase.decode_live(p).decode("utf-8") for p in payloads]
    chk(actual == decoded, "each payload equals its own selected source page")
    packed = sum(len(p) for p in payloads)
    plain = sum(len(base64.b64encode(s.encode("utf-8"))) for s in decoded)
    chk(packed < plain * 0.5, "gzip base64 is less than half the plain base64 size",
        f"{packed} vs {plain} characters")
    chk('id="start-example" href="#example-01"' in text and 'id="example-01"' in text,
        "the primary action and its no-JavaScript target exist")
    cards = {number: re.search(rf'<li class="card" id="example-{number}".*?</li>', text, re.S).group()
             for number in ("17", "28")}
    photos = [re.search(r'data:image/jpeg;base64,([^"]+)', card).group(1) for card in cards.values()]
    chk(photos[0] != photos[1], "same-named pages keep their own photographs")
    defined = set(re.findall(r'(--[a-z0-9-]+)\s*:', text))
    used = set(re.findall(r'var\((--[a-z0-9-]+)\)', text))
    chk(not used - defined, "every gallery CSS variable is defined", str(sorted(used - defined)))
    tables = i18n.load_all("showcase")
    chk(tables["nb"]["start_example"] == "Åpne det første eksempelet"
        and tables["en"]["start_example"] == "Open the first example",
        "the primary action is explicit in Norwegian and English")

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        examples = tmp / "examples"
        source_dir = examples / "01-one"
        source_dir.mkdir(parents=True)
        (source_dir / "README.md").write_text("# One\n\nA synthetic freshness fixture.\n",
                                             encoding="utf-8")
        source = source_dir / "one.html"
        raw = b"<!DOCTYPE html><title>Same decoded page</title>"
        source.write_bytes(raw)
        showcase = tmp / "gallery.html"
        # Different valid gzip bytes, identical decoded content: this is the contract.
        alternative = "gzip:" + base64.b64encode(gzip.compress(raw, compresslevel=1, mtime=0)).decode("ascii")
        chk(alternative != build_showcase.encode_live(raw),
            "the freshness fixture really has different compressed bytes")
        card = '<li class="card" id="example-01" data-live="{}" data-num="01"></li>'
        showcase.write_text(card.format(alternative), encoding="utf-8")
        code, out = freshness(showcase, examples)
        chk(code == 0, "freshness compares decoded content, not compressed bytes", out)
        source.write_bytes(raw + b"<p>stale</p>")
        code, out = freshness(showcase, examples)
        chk(code == 1 and "payload differs" in out, "a changed source makes freshness fail", out)
        source.write_bytes(raw)
        other = examples / "02-two"
        other.mkdir()
        (other / "README.md").write_text("# Two\n\nA second fixture.\n", encoding="utf-8")
        (other / "two.html").write_text("<p>not embedded</p>", encoding="utf-8")
        code, out = freshness(showcase, examples)
        chk(code == 1 and "example 02: no card" in out,
            "a new example without a gallery card makes freshness fail", out)
        showcase.write_text('<li class="card" id="example-01" data-live="gzip:not-base64" data-num="01"></li>',
                            encoding="utf-8")
        code, out = freshness(showcase, examples)
        chk(code == 1 and "not valid" in out, "a corrupt compressed payload fails loudly", out)
    return payloads, decoded


def wait_decoded(page) -> None:
    page.wait_for_function("""() => {
      const big = document.getElementById('big');
      const error = document.getElementById('decode-error');
      return big.srcdoc.length > 0 || !error.hidden;
    }""")


def browser_checks(payloads: list[str], expected: list[str]) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        chk(False, "Playwright is installed; no browser result can be inferred without it")
        return

    with sync_playwright() as p:
        for engine in ("chromium", "webkit"):
            browser = getattr(p, engine).launch()
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            errors: list[str] = []
            remote: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("request", lambda r: remote.append(r.url) if r.url.startswith(("http:", "https:")) else None)
            page.goto(SHOWCASE.resolve().as_uri())
            chk(page.locator("#start-example").inner_text() == "Åpne det første eksempelet",
                f"{engine}: the primary action starts in Norwegian")
            page.click("#start-example")
            wait_decoded(page)
            chk(page.locator("#viewer").evaluate("d => d.open")
                and "eksempel 01" in page.locator("#pos").inner_text(),
                f"{engine}: the primary action opens example 01 in the existing dialog")
            chk(page.locator("#big").evaluate("f => f.srcdoc") == expected[0],
                f"{engine}: native decompression reproduces the first source page")
            # Several quick selections must not let an older async decode win the frame.
            page.evaluate("for (let i = 0; i < 5; i++) document.getElementById('next').click()")
            wait_decoded(page)
            chk("eksempel 06" in page.locator("#pos").inner_text()
                and page.locator("#big").evaluate("f => f.srcdoc") == expected[5],
                f"{engine}: rapid dialog navigation keeps the last selected page")
            page.click("#shut")
            page.click('[data-lang="en"]')
            chk(page.locator("#start-example").inner_text() == "Open the first example",
                f"{engine}: the primary action switches to English")
            page.evaluate("document.getElementById('example-01').setAttribute('data-live', 'gzip:not-base64')")
            page.click("#start-example")
            page.locator("#decode-error").wait_for(state="visible")
            chk(page.locator("#decode-error").is_visible(),
                f"{engine}: malformed base64 shows the decode error instead of throwing")
            chk(not errors, f"{engine}: native decoding has no JavaScript error", str(errors))
            chk(not remote, f"{engine}: gallery and preview make no network request", str(remote[:3]))
            page.close()

            # Force the fallback through the same public UI. Do not call its private function:
            # the reader, the dialog and every payload are the measured surface.
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.add_init_script("Object.defineProperty(window, 'DecompressionStream', {value: undefined});")
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(SHOWCASE.resolve().as_uri())
            chk(page.evaluate("typeof DecompressionStream") == "undefined",
                f"{engine}: the native decompression API is really absent")
            started = time.monotonic()
            page.click("#start-example")
            wait_decoded(page)
            first_ms = (time.monotonic() - started) * 1000
            mismatches: list[str] = []
            for index, wanted in enumerate(expected):
                if index:
                    page.evaluate("document.getElementById('next').click()")
                    wait_decoded(page)
                if not page.locator("#decode-error").evaluate("e => e.hidden"):
                    mismatches.append(f"{index + 1}: decode error")
                    continue
                got = page.locator("#big").evaluate("f => f.srcdoc")
                if got != wanted:
                    mismatches.append(f"{index + 1}: {len(got)} != {len(wanted)} characters")
            elapsed = (time.monotonic() - started) * 1000
            chk(not mismatches,
                f"{engine}: fallback reproduces all {len(expected)} pages through the dialog "
                f"(first {first_ms:.0f} ms, all {elapsed:.0f} ms)", ", ".join(mismatches[:5]))
            # These two embedded decks emit the same error on 7d4c78a without compression.
            # Keep that pre-existing artefact limitation separate from this decoder contract.
            unexpected = [e for e in errors if e != "Permission policy 'Fullscreen' check failed for document with origin ''."]
            chk(not unexpected, f"{engine}: fallback adds no JavaScript error beyond the baseline "
                "fullscreen permission errors", str(unexpected))
            page.close()
            browser.close()

        # Quick Look's route: no script, but the content and the primary target still work.
        browser = p.chromium.launch()
        context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
        page = context.new_page()
        page.goto(SHOWCASE.resolve().as_uri())
        chk(len(page.locator("body").inner_text()) > 10000,
            "no JavaScript: the cards and repository index remain readable")
        page.click("#start-example")
        chk(page.evaluate("location.hash") == "#example-01"
            and not page.locator("#viewer").evaluate("d => d.open"),
            "no JavaScript: the primary action moves to example 01's readable card")
        context.close()
        browser.close()


def main() -> int:
    print("showcase: compressed payload contract, dialog and no-JavaScript route")
    payloads, decoded = static_checks()
    browser_checks(payloads, decoded)
    print(f"{CHECKS - FAILED}/{CHECKS} checks passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
