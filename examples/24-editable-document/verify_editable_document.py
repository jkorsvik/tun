#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
verify_editable_document.py — proves the edit mode in editable-document.html works, and
that the copy it saves is a correct artefact in its own right. Rendering is not enough:
the claim is "edit, save, reopen, edit again", so that is what this does.

In Chromium, Firefox and WebKit, from a file:// URL:

  1. Without JavaScript the tools stay hidden and the memo reads normally.
  2. With JavaScript the tools appear, and the status line counts the yellow fields.
  3. "Rediger" makes the memo editable. Clicking a yellow field selects it, so typing
     replaces the hint; the field loses its marking, and gets it back if the hint returns.
  4. Pasting rich text inserts plain text only (Chromium: synthetic clipboard events).
  5. Ctrl+S downloads a copy, named like the open file, holding the edit, the remaining
     yellow fields, and none of the live edit state (contenteditable, the editing class,
     visible tools, an enabled save button, the live status text).
  6. The copy passes the generic static checks (tools/verify_standalone_core.py), and
     reopened, works again: tools appear, the count is right, editing switches on, and
     emptying a field removes the element (an engine behaviour the README states).
  7. In a replica of SharePoint's inline preview (a blob: iframe with
     sandbox="allow-scripts", docs/01 row 28), where downloads are blocked, no editing is
     offered: the tools stay hidden and the strip says to download the file instead.
  8. Zero page errors and zero console errors throughout.

    uv run --extra verify python examples/24-editable-document/verify_editable_document.py

Mutation self-check (each mutation must make at least one check fail):

    python3 examples/24-editable-document/verify_editable_document.py --mutation-check

Mutations are applied to copies in a temporary directory. The committed file is never
touched, so an interrupted run cannot leave a broken file behind.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
HTML = HERE / "editable-document.html"
sys.path.insert(0, str(REPO / "tools"))
import verify_standalone_core as core  # noqa: E402

FILL_TOTAL = 5
TYPED = "Økonomiavdelingen"

# docs/01 row 28: hurtigvisning renders the file as <iframe src="blob:…" sandbox="allow-scripts">.
PREVIEW_ORIGIN = "https://preview.invalid"
PREVIEW_PARENT = """<!doctype html><meta charset="utf-8"><body style="margin:0"><script>
fetch('/memo.html').then(r => r.text()).then(t => {
  const f = document.createElement('iframe');
  f.src = URL.createObjectURL(new Blob([t], {type: 'text/html'}));
  f.setAttribute('sandbox', 'allow-scripts');
  f.style.cssText = 'width:100vw;height:100vh;border:0';
  document.body.appendChild(f);
});
</script>"""

SELECT_CONTENTS = ("el => { const r = document.createRange(); r.selectNodeContents(el);"
                   " const s = getSelection(); s.removeAllRanges(); s.addRange(r); }")
SYNTHETIC_PASTE = ("() => { const dt = new DataTransfer();"
                   " dt.setData('text/html', '<b>fet</b> tekst');"
                   " dt.setData('text/plain', 'ren tekst');"
                   " document.getElementById('doc').dispatchEvent("
                   "   new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }")


def check(label: str, cond: bool, failures: list[str], engine: str) -> None:
    print(f"    {'✓' if cond else '✗'} {label}")
    if not cond:
        failures.append(f"{engine}: {label}")


def run_engine(pw, engine: str, html: pathlib.Path, workdir: pathlib.Path,
               failures: list[str]) -> None:
    print(f"  {engine}")
    browser = getattr(pw, engine).launch()
    errors: list[str] = []

    def watch(page):
        page.set_default_timeout(5000)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" else None)
        return page

    try:
        _checks(browser, watch, errors, engine, html, workdir, failures)
    except Exception as exc:  # a crash is a failed check, never a traceback that hides the rest
        check(f"ran to the end (crashed: {type(exc).__name__}: {str(exc).splitlines()[0]})",
              False, failures, engine)
    finally:
        browser.close()


def _checks(browser, watch, errors, engine, html, workdir, failures) -> None:
    nojs = watch(browser.new_context(java_script_enabled=False).new_page())
    nojs.goto(html.as_uri())
    check("no JS: tools hidden", not nojs.is_visible("#tools"), failures, engine)
    check("no JS: memo visible", nojs.is_visible("h1"), failures, engine)
    nojs_status = nojs.text_content("#status")

    page = watch(browser.new_context(accept_downloads=True).new_page())
    page.goto(html.as_uri())
    check("JS: tools visible", page.is_visible("#tools"), failures, engine)
    check(f"JS: status counts {FILL_TOTAL} fields",
          f"{FILL_TOTAL} gule felt" in page.text_content("#status"), failures, engine)

    page.click("#b-edit")
    check("edit: memo is contenteditable", page.get_attribute("#doc", "contenteditable") == "true",
          failures, engine)
    first = page.locator("#doc .fill").first.element_handle()
    first.click()
    page.keyboard.type(TYPED)
    check("edit: click selects the field, typing replaces the hint",
          first.text_content() == TYPED, failures, engine)
    check("edit: filled field loses its marking",
          page.locator("#doc .fill").count() == FILL_TOTAL - 1, failures, engine)
    second = page.locator("#doc .fill").first.element_handle()
    second_hint = second.text_content()
    second.click()
    page.keyboard.type("x")
    second.evaluate(SELECT_CONTENTS)
    page.keyboard.type(second_hint)
    check("edit: a field typed back to its hint is yellow again",
          page.locator("#doc .fill").count() == FILL_TOTAL - 1, failures, engine)
    check(f"edit: status counts {FILL_TOTAL - 1} fields",
          f"{FILL_TOTAL - 1} gule felt" in page.text_content("#status"), failures, engine)
    check("edit: save is enabled", page.is_enabled("#b-save"), failures, engine)

    if engine == "chromium":
        page.locator("#doc h1").evaluate(
            "el => { const r = document.createRange(); r.selectNodeContents(el); r.collapse(false);"
            " const s = getSelection(); s.removeAllRanges(); s.addRange(r); }")
        page.evaluate(SYNTHETIC_PASTE)
        h1 = page.inner_html("#doc h1")
        check("paste: plain text inserted, markup dropped",
              "ren tekst" in h1 and "<b>" not in h1, failures, engine)

    with page.expect_download() as dl:
        page.keyboard.press("Control+s")
    download = dl.value
    saved = workdir / f"{engine}-{download.suggested_filename}"
    download.save_as(saved)
    check("save: copy named like the open file", download.suggested_filename == html.name,
          failures, engine)
    text = saved.read_text(encoding="utf-8")
    tags = lambda tag: re.findall(rf"<{tag}\b[^>]*>", text)  # noqa: E731
    article = (tags("article") or [""])[0]
    tools = next((t for t in tags("div") if 'id="tools"' in t), "")
    save_btn = next((t for t in tags("button") if 'id="b-save"' in t), "")
    body = (tags("body") or [""])[0]
    check("copy: holds the edit", TYPED in text, failures, engine)
    check(f"copy: {FILL_TOTAL - 1} yellow fields left", text.count('class="fill"') == FILL_TOTAL - 1,
          failures, engine)
    check("copy: not contenteditable", "contenteditable" not in article, failures, engine)
    check("copy: no editing class", "editing" not in body, failures, engine)
    check("copy: tools hidden", "hidden" in tools, failures, engine)
    check("copy: save disabled", "disabled" in save_btn, failures, engine)
    check("copy: footer stamped", "Sist redigert" in text, failures, engine)
    for name, fn in (("self-contained", core.check_self_contained),
                     ("placeholders", core.check_no_leftover_placeholders),
                     ("provenance", core.check_provenance),
                     ("no stray script", core.check_no_stray_script_text),
                     ("no :target nav", core.check_no_target_driven_visibility),
                     ("no pinned header", core.check_no_scroll_persistent_positioning)):
        ok, msg = fn(text)
        check(f"copy: core check {name}" + ("" if ok else f" ({msg})"), ok, failures, engine)

    again = watch(browser.new_context().new_page())
    again.goto(saved.as_uri())
    check("reopen: tools visible", again.is_visible("#tools"), failures, engine)
    check(f"reopen: status counts {FILL_TOTAL - 1} fields",
          f"{FILL_TOTAL - 1} gule felt" in again.text_content("#status"), failures, engine)
    again.click("#b-edit")
    check("reopen: editing switches on", again.get_attribute("#doc", "contenteditable") == "true",
          failures, engine)
    last = again.locator("#doc .fill").last.element_handle()
    last.evaluate(SELECT_CONTENTS)
    again.keyboard.press("Backspace")
    check("reopen: emptying a field removes the element (README claim)",
          last.evaluate("el => !el.isConnected"), failures, engine)

    again_nojs = watch(browser.new_context(java_script_enabled=False).new_page())
    again_nojs.goto(saved.as_uri())
    check("reopen, no JS: tools hidden", not again_nojs.is_visible("#tools"), failures, engine)
    check("reopen, no JS: status is the static text, not the live one",
          again_nojs.text_content("#status") == nojs_status, failures, engine)

    memo = html.read_text(encoding="utf-8")
    preview_ctx = browser.new_context()
    preview_ctx.route(f"{PREVIEW_ORIGIN}/**", lambda route: route.fulfill(
        body=memo if route.request.url.endswith("/memo.html") else PREVIEW_PARENT,
        content_type="text/html"))
    preview = watch(preview_ctx.new_page())
    preview.goto(f"{PREVIEW_ORIGIN}/")
    preview.wait_for_function("() => document.querySelector('iframe')")
    frame = None
    for _ in range(50):  # until the script inside the frame has run, one way or the other
        frame = next((f for f in preview.frames if f.url.startswith("blob:")), None)
        settled = frame and frame.query_selector("#status") and (
            frame.is_visible("#tools") or "Forhåndsvisning" in frame.text_content("#status"))
        if settled:
            break
        preview.wait_for_timeout(100)
    check("preview replica: memo readable", bool(frame) and frame.is_visible("h1"), failures, engine)
    check("preview replica: no edit tools offered", bool(frame) and not frame.is_visible("#tools"),
          failures, engine)
    check("preview replica: strip says to download and open from disk",
          bool(frame) and "Last ned filen" in frame.text_content("#status"), failures, engine)

    check("no page or console errors" + (f" ({errors[:2]})" if errors else ""), not errors,
          failures, engine)


def verify(html: pathlib.Path, engines=core.ENGINES) -> list[str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ✗ playwright not installed. A verifier that never opened a browser has proved nothing.\n"
              "    uv sync --extra verify && uv run playwright install chromium firefox webkit")
        return ["playwright not installed"]
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        for engine in engines:
            run_engine(pw, engine, html, pathlib.Path(tmp), failures)
    return failures


# Each mutation removes one behaviour the README claims. If the suite still passes with it
# removed, the suite was not testing that behaviour.
MUTATIONS = {
    "no-JS hiding rule": ("[hidden]{display:none!important}", ""),
    "tools revealed by script": ("tools.hidden=false;", ""),
    "field marking follows its text":
        ("f.classList.toggle('fill', f.textContent===h);", ";"),
    "field re-marked when the hint returns":
        ("f.classList.toggle('fill', f.textContent===h);",
         "if(f.textContent!==h) f.classList.remove('fill');"),
    "click selects the whole field": ("s.removeAllRanges(); s.addRange(r);", ""),
    "plain-text paste": ("getData('text/plain')", "getData('text/html')"),
    "copy built from the opened page, not the live one":
        ("new DOMParser().parseFromString(pristine, 'text/html')", "document.cloneNode(true)"),
    "copy carries the edited memo": ("copy.getElementById('doc').innerHTML=doc.innerHTML;", ""),
    "no editing offered in a sandboxed preview":
        ("if(window.self!==window.top && self.origin==='null'){", "if(false){"),
}


def mutation_check() -> int:
    original = HTML.read_text(encoding="utf-8")
    survivors = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, (needle, repl) in MUTATIONS.items():
            if original.count(needle) != 1:
                print(f"✗ mutation {name!r}: needle found {original.count(needle)} times, expected 1")
                return 1
            mutant = pathlib.Path(tmp) / HTML.name
            mutant.write_text(original.replace(needle, repl), encoding="utf-8")
            print(f"\n=== mutation: {name}")
            caught = verify(mutant, engines=("chromium",))
            print(f"--> {'caught' if caught else 'SURVIVED'} ({len(caught)} failing check(s))")
            if not caught:
                survivors.append(name)
    print()
    if survivors:
        print(f"✗ {len(survivors)} of {len(MUTATIONS)} mutation(s) survived: {survivors}")
        return 1
    print(f"✓ all {len(MUTATIONS)} mutations caught")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mutation-check", action="store_true")
    ap.add_argument("--html", type=pathlib.Path, default=HTML)
    core.add_engines_arg(ap, default=core.ENGINES)
    args = ap.parse_args()
    if args.mutation_check:
        return mutation_check()
    print(f"verifying edit mode: {args.html.name}")
    failures = verify(args.html.resolve(), args.engines)
    print()
    if failures:
        print(f"✗ FAIL: {len(failures)} check(s)")
        for f in failures:
            print(f"    {f}")
        return 1
    print("✓ PASS. Now look at the screenshots in the README; a check cannot see layout.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
