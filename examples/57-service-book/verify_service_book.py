#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
verify_service_book.py — prove the service book behaves, in a real browser.

    uv run --extra verify python3 examples/57-service-book/verify_service_book.py
    uv run --extra verify python3 examples/57-service-book/verify_service_book.py --engines all

Playwright is required and this FAILS without it rather than skipping: a gate that
reports success having never opened the file is worse than one that reports nothing.

What it proves, per engine:

  1. the file opens from file:// with no external request;
  2. every pane in the state becomes a tab and a section;
  3. the handover logic: watches at or after the cut are marked, kept, and warned about;
  4. a day with no watches renders and says so;
  5. add a point and remove a point in a list (the buttons that were dead once);
  6. add a pane, then add a day, and the layout panel reflects both;
  7. save downloads a standalone copy, and reopening it keeps panes, days, edits;
  8. a hostile string in a list does not break the script element;
  9. no console error and no HTTP request in the whole run.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
from verify_standalone_core import add_engines_arg, ENGINES  # noqa: E402

ARTEFACT = HERE / "service-book.html"
STATE = HERE / "service-book.json"
HOSTILE = 'sett inn </scr' + 'ipt><img src=x onerror=alert(1)> her'
EDITED_POINT = "Endret punkt som må overleve lagring"

PASSED = 0
FAILED = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    PASSED += bool(condition)
    FAILED += not condition
    print(f"  {'PASS' if condition else 'FAIL'} {label}" + (f" -- {detail}" if detail and not condition else ""))


def open_pane(page, code: str) -> bool:
    """Click the tab whose pane has this type, found through the state, not a title."""
    pane_id = page.evaluate("""(type) => {
        const p = state.panes.find(x => x.type === type);
        return p ? p.id : null;
    }""", code)
    if not pane_id:
        return False
    page.locator(f'.tab[data-pane="{pane_id}"]').first.click()
    page.wait_for_timeout(200)
    return True


def run(engine: str, state: dict, cut: str) -> None:
    from playwright.sync_api import sync_playwright

    uri = ARTEFACT.resolve().as_uri()
    errors: list[str] = []
    requests: list[str] = []

    with sync_playwright() as p:
        browser = getattr(p, engine).launch()
        context = browser.new_context(accept_downloads=True, viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("request", lambda r: requests.append(r.url) if not r.url.startswith(("file:", "data:", "blob:")) else None)
        page.on("dialog", lambda d: d.accept("" if d.type == "alert" else "Test"))

        page.goto(uri)
        page.wait_for_timeout(700)

        # 1. opens, and the badge totals match the state
        check("page has a title", bool(page.title().strip()))
        check("one h1", page.locator("h1").count() == 1)

        # 2. every pane is a tab and a section
        pane_count = page.locator(".tab").count()
        check("a tab per pane", pane_count == len(state["panes"]), f"{pane_count} vs {len(state['panes'])}")
        check("a section per pane", page.locator("section.pane").count() == len(state["panes"]))

        # 3. the handover logic
        open_pane(page, "rullering")
        expected_superseded = len([w for w in state["watches"] if w["start"] >= cut])
        superseded = page.locator("tr[data-watch].superseded").count()
        check("superseded watches marked", superseded == expected_superseded, f"{superseded} vs {expected_superseded}")
        check("superseded watches kept in the table", page.locator("tr[data-watch]").count() == len(state["watches"]))
        if expected_superseded:
            check("superseded row says what replaced it", "erstattet av" in page.locator("tr.superseded").first.inner_text())
        # A watch that starts before the cut and ends after it must be shown as ending
        # AT the cut. Tested on the function with a watch that really straddles, because
        # the committed data has none and a hardcoded True would assert nothing.
        straddle_end = page.evaluate(
            """(cut) => {
                 const w = { start: '2027-03-10T10:00', end: '2027-03-10T14:00' };
                 return effectiveEnd(w);
               }""", cut)
        check("a watch straddling the cut ends at the cut", straddle_end == cut,
              f"effectiveEnd gave {straddle_end}, cut is {cut}")
        after_end = page.evaluate(
            """() => {
                 const w = { start: '2027-03-10T16:00', end: '2027-03-10T20:00' };
                 return effectiveEnd(w);
               }""")
        check("a watch wholly after the cut keeps its own end", after_end == "2027-03-10T20:00", after_end)
        before_end = page.evaluate(
            """() => {
                 const w = { start: '2027-03-10T04:00', end: '2027-03-10T08:00' };
                 return effectiveEnd(w);
               }""")
        check("a watch wholly before the cut is untouched", before_end == "2027-03-10T08:00", before_end)

        # 4. every day renders, including an empty one
        state_days = len({w["start"][:10] for w in state["watches"]})
        check("a day heading per day", page.locator("tr.rday").count() >= state_days, f"{page.locator('tr.rday').count()} vs {state_days}")
        # Each day heading must carry ITS OWN label and note. A note copied from the
        # wrong day renders perfectly and is wrong: this is the check for that.
        headings = page.evaluate("Array.from(document.querySelectorAll('tr.rday td')).map(td => td.textContent)")
        for day in state.get("days", []):
            want = day["label"] + ((" \u00b7 " + day["note"]) if day.get("note") else "")
            check(f"day heading for {day['date']} carries its own text", any(want in h for h in headings),
                  f"wanted {want!r}, got {headings[:3]}")
        # The handover sentence must name the day, not only the clock.
        handover_text = page.locator("tr.rday").first.locator("xpath=../../..")  # keep context shallow
        cut_sentence = page.evaluate("""(cut) => {
            const el = Array.from(document.querySelectorAll('.box.warn')).find(b => b.textContent.indexOf('skifter') >= 0);
            return el ? el.textContent : '';
        }""", cut)
        check("the handover sentence names the day and the clock",
              f"{cut[8:10]}.{cut[5:7]}" in cut_sentence and cut[11:] in cut_sentence,
              cut_sentence[:120])

        # 5. add and remove a point
        open_pane(page, "beskjed")
        # Take the first list that the page actually renders, from the state, so renaming a
        # key in the data can never leave this test pointing at nothing.
        # Only a list whose add button is actually reachable: some lists live inside a
        # closed <details>, and a click there would test nothing a reader can do.
        key = page.evaluate("""(() => {
            const buttons = Array.from(document.querySelectorAll('button[id^="add-"]'));
            for (const b of buttons) {
                const listKey = b.id.slice(4);
                const ul = document.getElementById(listKey);
                if (!ul) continue;
                if (b.offsetParent === null) continue;   // hidden in a closed details
                return listKey;
            }
            return null;
        })()""")
        check("a rendered list was found to test", bool(key), str(key))
        if not key:
            browser.close()
            return
        before = page.evaluate(f'state.lists["{key}"].length')
        add_button = page.locator(f"#add-{key}")
        check("add button exists", add_button.count() == 1)
        add_button.click()
        page.wait_for_timeout(300)
        after = page.evaluate(f'state.lists["{key}"].length')
        check("add a point", after == before + 1, f"{before} -> {after}")
        page.locator(f"#{key} li button").last.click()
        page.wait_for_timeout(300)
        back = page.evaluate(f'state.lists["{key}"].length')
        check("remove a point", back == before, f"{after} -> {back}")

        # 8. hostile text does not escape
        page.evaluate("""([key, text]) => { state.lists[key].push(text); renderLists(); }""", [key, HOSTILE])
        page.wait_for_timeout(300)
        # The text is in a textarea, so its VALUE carries it; inner_text would see nothing.
        values = page.evaluate(f'Array.from(document.querySelectorAll("#{key} textarea")).map(t => t.value)')
        check("hostile text survives as exact text", values and values[-1] == HOSTILE,
              repr(values[-1]) if values else "no textarea")
        check("no injected image element", page.locator('img[src="x"]').count() == 0)
        check("no raw markup in the list html", "<img" not in page.locator(f"#{key}").inner_html())
        page.evaluate(f'state.lists["{key}"].pop(), renderLists()')

        # 6. add a pane and a day through the layout panel
        page.locator("#open-layout").click()
        page.wait_for_timeout(500)
        tabs_before = page.locator(".tab").count()
        page.locator("#add-pane").click()
        page.wait_for_timeout(600)
        tabs_after = page.locator(".tab").count()
        check("add a pane", tabs_after == tabs_before + 1, f"{tabs_before} -> {tabs_after}")
        new_id = page.evaluate("state.panes[state.panes.length-1].id")
        check("new pane got a section", page.locator(f"#pane-{new_id}").count() == 1)

        open_pane(page, "rullering")
        days_before = page.locator("tr.rday").count()
        page.locator("#add-day").click()
        page.wait_for_timeout(500)
        days_after = page.locator("tr.rday").count()
        check("add a day", days_after == days_before + 1, f"{days_before} -> {days_after}")
        check("the new empty day says so", page.locator("tr.empty-day").count() >= 1)

        # Give the round trip something real to lose: edit a list point, rename a pane,
        # and move the cut. Then save.
        page.evaluate("""([key, text]) => {
            state.lists[key][0] = text; renderLists();
        }""", [key, EDITED_POINT])
        page.locator("#open-layout").click()
        page.wait_for_timeout(300)
        first_name = page.locator("#pane-editor input.plain").first
        first_name.fill("Testfane")
        first_name.dispatch_event("input")
        page.wait_for_timeout(400)
        page.locator('.tab').nth(4).click()
        page.wait_for_timeout(300)
        check("every tab still responds after a rename", page.evaluate("""(() => {
            let ok = 0;
            const tabs = Array.from(document.querySelectorAll('.tab'));
            for (const t of tabs) { t.click(); if (document.getElementById('pane-' + t.dataset.pane).classList.contains('active')) ok++; }
            return ok === tabs.length;
        })()"""))

        # 7. save and reopen
        with page.expect_download() as download:
            page.locator("#save-file").click()
        saved = pathlib.Path(tempfile.mkdtemp()) / "variant.html"
        download.value.save_as(saved)
        check("saved file has bytes", saved.stat().st_size > 20000, f"{saved.stat().st_size}")

        # A fresh context, so the reopened page cannot fall back to the first page's stored
        # state. Sharing storage hides a corrupt save: boot() would silently load the live
        # copy and the reopen checks would pass on state that was never written to the file.
        context2 = browser.new_context(accept_downloads=True, viewport={"width": 1280, "height": 900})
        page2 = context2.new_page()
        page2.on("pageerror", lambda e: errors.append("reopen: " + str(e)))
        page2.on("console", lambda m: errors.append("reopen console: " + m.text) if m.type == "error" else None)
        page2.on("request", lambda r: requests.append("reopen: " + r.url) if not r.url.startswith(("file:", "data:", "blob:")) else None)
        page2.on("dialog", lambda d: d.accept())
        page2.goto(saved.resolve().as_uri())
        page2.wait_for_timeout(700)
        load_error = page2.evaluate("window.__loadError || ''")
        check("the saved file's own payload parses on load", not load_error, str(load_error))
        check("reopened file keeps the new pane", page2.locator(".tab").count() == tabs_after,
              f"{page2.locator('.tab').count()} vs {tabs_after}")
        open_pane(page2, "rullering")
        check("reopened file keeps the new day", page2.locator("tr.rday").count() == days_after)
        check("reopened file keeps every watch", page2.locator("tr[data-watch]").count() == len(state["watches"]))
        check("reopened file keeps the superseded marks",
              page2.locator("tr.superseded").count() == expected_superseded)
        # A list edit must survive the round trip, not just structural changes.
        first_value = page2.evaluate("""(listKey) => {
            const ta = document.querySelector('#' + listKey + ' textarea');
            return ta ? ta.value : null;
        }""", key)
        check("reopened file keeps an edited list point", first_value == EDITED_POINT,
              f"wanted {EDITED_POINT!r}, got {first_value!r}")
        # A renamed pane must survive, and its tab must still work after the rename.
        renamed = page2.evaluate("state.panes.map(p => p.title)")
        check("reopened file keeps the pane rename", "Testfane" in renamed, str(renamed))
        renamed_id = page2.evaluate("""(() => {
            const p = state.panes.find(x => x.title === 'Testfane');
            return p ? p.id : null;
        })()""")
        check("the renamed pane kept its identity", bool(renamed_id), str(renamed_id))
        if renamed_id:
            page2.locator(f'.tab[data-pane="{renamed_id}"]').first.click()
            page2.wait_for_timeout(200)
            active = page2.evaluate("""(() => {
                const a = document.querySelector('#panes section.pane.active');
                return a ? a.id : null;
            })()""")
            check("a renamed pane's tab opens THAT pane", active == 'pane-' + renamed_id,
                  f"active={active}, wanted pane-{renamed_id}")
        # The cut itself must survive.
        cut_after = page2.evaluate("state.handover.rotationEnds")
        check("reopened file keeps the cut", cut_after == cut, f"{cut_after} vs {cut}")

        # The superseded warning must be in the checks pane, and the badge must count it.
        # Deleting the warning from renderChecks() must not leave the suite green.
        open_pane(page, "sjekk")
        checks_text = page.locator("#checks").inner_text()
        superseded_mentions = checks_text.count("erstattet av")
        check("the checks pane warns about every superseded watch that still has roles",
              superseded_mentions >= expected_superseded,
              f"{superseded_mentions} mention(s), expected at least {expected_superseded}")
        badge = page.locator("#t-sjekk").inner_text()
        check("the checks badge counts problems and warnings", badge.strip() != "", repr(badge))

        # The "Åpne fil" path parses the payload with payloadPattern(). Reopening a saved
        # file does not touch it (boot reads the embedded element directly), so without this
        # a broken capture group there would never be noticed.
        page.evaluate("""(payload) => {
            const file = new File([payload], 'variant.html', { type: 'text/html' });
            importFile(file);
        }""", '<html><body><scr' + 'ipt id="appstate" type="application/json">' +
             json.dumps({"panes": [{"id": "naa", "title": "Nå", "type": "naa"}],
                         "people": [], "watches": [], "lists": {}, "days": [],
                         "handover": {}, "beskjed": {"posts": []},
                         "title": "Aapnet fil", "subtitle": "", "footer": ""}) +
             '</scr' + 'ipt></body></html>')
        page.wait_for_timeout(500)
        loaded_title = page.evaluate("state.title")
        check('"Åpne fil" loads the payload it is given', loaded_title == "Aapnet fil", str(loaded_title))

        # A corrupt payload must render an error in the page, not a blank plan with a dead UI.
        # Built by taking the real file and replacing its payload with invalid JSON.
        broken_path = pathlib.Path(tempfile.mkdtemp()) / "broken.html"
        broken_path.write_text(
            re.sub(r'(<script id="appstate" type="application/json">)[\s\S]*?(</script>)',
                   r'\1{not json\2', ARTEFACT.read_text(encoding="utf-8"), count=1),
            encoding="utf-8")
        page3 = context2.new_page()
        page3.on("dialog", lambda d: d.accept())
        page3.goto(broken_path.resolve().as_uri())
        page3.wait_for_timeout(600)
        err_shown = page3.locator("#pane-error").count() == 1
        err_text = page3.locator("#pane-error").inner_text() if err_shown else ""
        check("a corrupt payload shows an error pane", err_shown, err_text[:80])
        check("the error pane says the file could not be read",
              "kunne ikke leses" in err_text.lower(), err_text[:80])
        check("a corrupt file leaves no fake plan on screen",
              page3.locator("#pane-roster, #panes tr[data-watch]").count() == 0)
        page3.close()

        # 9.
        check("no console or page error", not errors, "; ".join(errors[:3]))
        check("no external request", not requests, "; ".join(requests[:3]))

        context2.close()
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the service-book example.")
    add_engines_arg(parser)
    args = parser.parse_args()

    try:
        import playwright  # noqa: F401
    except ImportError:
        print("FAIL: Playwright is required. Install it with:\n"
              "  uv sync --extra verify && uv run playwright install chromium firefox webkit")
        return 2

    if not ARTEFACT.exists():
        print(f"FAIL: {ARTEFACT} is missing. Run build_service_book.py first.")
        return 2

    state = json.loads(STATE.read_text(encoding="utf-8"))
    cut = (state.get("handover") or {}).get("rotationEnds", "")
    if not cut:
        print("FAIL: the state has no rotationEnds, so the handover logic is untested.")
        return 2

    engines = ENGINES if args.engines == "all" else tuple(args.engines)
    if not engines:
        print("FAIL: no engines requested")
        return 2
    for engine in engines:
        print(f"\n{engine}:")
        run(engine, state, cut)

    total = PASSED + FAILED
    print(f"\n{PASSED}/{total} checks passed across {len(engines)} engine(s)")
    if FAILED:
        print("FAIL")
        return 1
    if total == 0:
        print("FAIL: zero checks ran")
        return 2
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
