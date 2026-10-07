#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
verify_day_board.py — proves the constraints this example exists to
demonstrate, which tools/verify_dashboard.py does not look at.

verify_dashboard.py is still the gate (run it too — it checks self-containment,
size, provenance, placeholders, a clean console, KPIs/chart/table and a real
filter change). This script adds the tenant-constraint behaviour:

  Static, no browser:
    1. no position:sticky / position:fixed declaration, in the stylesheet, in a
       style attribute, or set from script                    (docs/01 row 26)
    2. no CSS :target selector anywhere                       (docs/01 row 24)
    3. the literal script-open text appears only as real elements (row 25)
    4. no fetch()/XMLHttpRequest — the sidecar is loaded as code (rows 14-16)
    5. every distinct value in data.js matches its column's allow-list, so no
       free text — and therefore no real name — can hide in the data

  JavaScript DISABLED (java_script_enabled=False — the closest Playwright gets
  to the row-22a failure, where scripting is not off by policy but simply never
  runs in the viewer):
    6. the warning banner is visible without any script       (row 22)
    7. every view stays readable — ordninger and rutiner are plain markup
    8. the nav is hidden, so there are no dead links
    9. the fullscreen button is hidden
   10. the day list is empty, and the banner is what explains it

  JavaScript ENABLED:
   11. the warning banner is hidden by the earliest script
   12. the "stopped partway" banner stays hidden on a healthy page
   13. view switching works by class toggle AND leaves location.hash empty,
       which is the proof preventDefault ran instead of fragment navigation
   14. #content is the SOLE overflow-y container in the document (row 26)
   15. the fullscreen button is revealed and clicking it raises no error (row 21)
   16. 390px: no horizontal overflow, table collapses to cards, touch targets
       are at least 44px (docs/11 §5)

  Initial-load data validation — the docs/13 §2 gap this example closes:
   17. a data.js missing a required column fails VISIBLY and names the column —
       including when the column is missing from row 40, not row 1
   18. an empty array, and a missing data.js, each fail VISIBLY with their own
       message instead of rendering an empty page
   19. an unrecognised Status or an Ordning with no owner in the ownership table
       WARNS without blanking the board, and the KPI row follows the data

Writes preview-*.png for a human to look at. A passing exit code is not the
point of those; looking at them is.

    python3 examples/17-multi-regime-day-board/verify_day_board.py
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
HTML = HERE / "oversikt.html"
DATA = HERE / "data.js"

sys.path.insert(0, str(REPO / "tools"))
from verify_standalone_core import check_no_stray_script_text  # noqa: E402

TOUCH_MIN_PX = 44  # docs/11 §5

CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
# HTML comments too: the template explains its brand decision in one, and prose
# that says why a file is NOT loaded must be allowed to name the file.
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
STYLE_BLOCK = re.compile(r"<style[^>]*>(.*?)</style>", re.S | re.I)

# Every value the generator is allowed to write. Anything outside these sets is
# free text, and free text in this file is how a real name would get in.
ALLOWED = {
    "Dato": re.compile(r"\d{4}-\d{2}-\d{2}"),
    "ElevKode": re.compile(r"ELEV-\d\d"),
    "Retning": re.compile(r"Til skole|Fra skole|Fra SFO"),
    "Ordning": re.compile(r"Grunnskole drosje|langdagSFO TT-kort|VGS TT-kort"),
    "Planlagt": re.compile(r"[0-2]\d:[0-5]\d"),
    "Bil": re.compile(r"(OT|TT)-\d\d|Ikke bestilt|Avventer TT-kort"),
    "Ledsager": re.compile(r"Ja|Nei|Vurderes"),
    "Status": re.compile(r"I rute|Venter|Avlyst"),
    "EndretAv": re.compile(r"Skoleadm\.|SFO|Sentralbord|Foresatt|Kommune"),
}

# The exact set of distinct values each closed-vocabulary column may contain.
#
# This exists because ALLOWED is a regex allow-list, and a regex can be loosened
# without anything noticing: re.compile(r".*") passes every pattern check while
# proving nothing. A SET cannot be loosened by an edit to a pattern, so the
# de-identification guarantee rests here rather than on the regexes.
#
# DO NOT derive this from build_day_board.py's PUPILS table. It looks like
# duplicated data and a review has already proposed exactly that, so here is why
# it must stay hand-written: deriving the permitted values from the generator
# means adding a pupil called "Ola Nordmann" to PUPILS would widen the expected
# set to include it, and the gate would pass. That is the self-validation hole
# this whole file exists to avoid, reintroduced by a refactor that reads as
# tidying up.
#
# The cost is real and is the point: adding a pupil fails this check with
# "ElevKode: unexpected ['ELEV-15']; Bil: unexpected ['TT-99']", and somebody has
# to widen the set on purpose. Widening what counts as non-identifying data should
# be a deliberate, reviewed act, not a side effect of editing a data table.
#
# Only the closed vocabularies are listed. Dato and Planlagt are open ranges by
# nature — a date and a clock time — so pinning their value sets would pin the
# example's dataset instead of its contract, and any edit to the rows would fail
# a check that is not about safety. Their regexes are narrow and the canary test
# below covers them: neither can admit a name.
EXPECTED_VALUES = {
    "ElevKode": {f"ELEV-{n:02d}" for n in range(1, 15)},
    "Retning": {"Til skole", "Fra skole", "Fra SFO"},
    "Ordning": {"Grunnskole drosje", "langdagSFO TT-kort", "VGS TT-kort"},
    "Bil": ({f"OT-{n}" for n in (31, 32, 33, 34)}
            | {f"TT-{n}" for n in (51, 52, 53, 54, 71, 72, 73)}
            | {"Ikke bestilt", "Avventer TT-kort"}),
    "Ledsager": {"Ja", "Nei", "Vurderes"},
    "Status": {"I rute", "Venter", "Avlyst"},
    "EndretAv": {"Skoleadm.", "SFO", "Sentralbord", "Foresatt", "Kommune"},
}


def check(label: str, ok: bool, failures: list[str], detail: str = "") -> None:
    print(f"  {'✓' if ok else '✗'} {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        failures.append(label + ((" — " + detail) if detail else ""))


def stylesheet(html: str) -> str:
    """The CSS actually in force, with comments removed.

    Scanning the raw file instead would trip over this example's own comments,
    which name position:sticky and :target in order to explain why they are not
    used. The constraint is about declarations, so read the declarations.
    """
    css = "\n".join(STYLE_BLOCK.findall(html))
    if len(css) < 1000:
        raise SystemExit("FAIL: found almost no CSS — the scan would pass vacuously")
    stripped = CSS_COMMENT.sub("", css)
    if stripped == css:
        raise SystemExit("FAIL: no CSS comment was stripped — the stripper is not working")
    return stripped


def palette_values() -> dict[str, set[str]]:
    """Every colour this repo ships, read from the files rather than recalled.

    Listing one brand's hex values inline would be wrong twice over: it goes
    stale the moment a palette is edited, and it only tests the one brand
    somebody happened to type out.
    Reading the files instead means the check covers the CORE palette and EVERY
    plugin palette, and keeps covering a plugin added after this was written.

    Greyscale is excluded deliberately. #ffffff is nobody's trademark, and this
    artefact's own neutral base is greyscale by design, so including it would
    make a collision certain and the check useless.

    EVERY palette file appears in the result, including one whose values are all
    greyscale and which therefore maps to an empty set. That matters: the caller
    also uses these keys as the list of filenames that must not be loaded, and
    dropping a file here because it happens to ship no colour would quietly stop
    guarding its NAME. An empty set costs nothing in the value comparison.
    """
    found: dict[str, set[str]] = {}
    sources = sorted((REPO / "tools" / "tokens").glob("*.css"))
    sources += sorted((REPO / "plugins").glob("*/tokens/*.css"))
    for path in sources:
        found[str(path.relative_to(REPO))] = {
            h.lower() for h in re.findall(r"#[0-9a-fA-F]{6}\b",
                                          path.read_text(encoding="utf-8"))
            if not (h[1:3].lower() == h[3:5].lower() == h[5:7].lower())
        }
    return found


def run_brand(failures: list[str]) -> None:
    """In the scenario the artefact belongs to a third party. Prove it wears nobody's colours."""
    print("\n-- brand and signalling (a third party, not this repo's owner) --")
    html = HTML.read_text(encoding="utf-8")
    css = stylesheet(html)

    # Whose colours could leak in here? Every palette the repo ships, core and
    # plugin alike. Read from disk, so this cannot go stale.
    palettes = palette_values()
    total = sum(len(v) for v in palettes.values())
    # Guard against the worst outcome: a check that finds nothing to test and
    # reports success. If the palettes move, this must fail loudly, not quietly.
    check("palette files were found, so the leak check is not vacuous",
          len(palettes) >= 2 and total >= 10, failures,
          f"{len(palettes)} file(s), {total} value(s)")
    leaked = sorted({f"{h} ({name})"
                     for name, values in palettes.items()
                     for h in values if h in css.lower()})
    check(f"no colour from any shipped palette appears here ({total} values checked)",
          not leaked, failures, str(leaked[:6]))
    # The builder must not READ a token file at all — see TOKENS_REMOVED. Prose
    # explaining why is wanted, so the ban is on the read, not on the word.
    builder = (HERE / "build_day_board.py").read_text(encoding="utf-8")
    reads = re.findall(r'(?:REPO|HERE)\s*/\s*"tools"[^\n]*read_text', builder)
    reads += re.findall(r'tokens[^\n]*\.read_text', builder)
    reads += re.findall(r'load_token_css|tun_tokens', builder)
    check("the builder reads no token file, core or plugin",
          not reads, failures, str(reads))
    # Filenames, not just values: a palette could be pulled in by name. Checked
    # OUTSIDE comments, because prose that explains why a file is deliberately
    # NOT used has to be free to name it — the same distinction this function
    # already makes for the builder, where the ban is on the read and not on the
    # word. Banning the word would punish the explanation and reward silence.
    prose_free = CSS_COMMENT.sub("", HTML_COMMENT.sub("", html))
    # Derived from the same dict the value check used, deliberately NOT a second
    # glob. Two globs over the same paths are two sources of truth for "which
    # palettes exist", and the day they disagree the value check and the filename
    # check would be guarding different sets of files while both reported success.
    # palette_values() keys are repo-relative paths, so take the basename.
    banned = {pathlib.Path(rel).name for rel in palettes}
    check("comment stripping actually removed something, so this is not vacuous",
          len(prose_free) < len(html), failures,
          f"{len(html)} -> {len(prose_free)} chars")
    for name in sorted(banned):
        check(f"no {name} is loaded (prose may still name it)",
              name not in prose_free, failures)
    for construct in ("<link", "@import", "url("):
        check(f"no {construct} anywhere — nothing is fetched",
              construct not in prose_free, failures)

    # The font stack is an ALLOW-LIST, not a ban on particular typefaces.
    #
    # Searching for one organisation's font by name would have the same two faults
    # as a hardcoded hex list: it goes stale, and it only
    # catches the name somebody typed. Permitting a known set instead rejects EVERY
    # unlisted family, including an organisation's, including one nobody has heard
    # of yet. It is the same argument the example makes about its data vocabulary.
    PERMITTED_FAMILIES = {
        # The fictional tenant font, named so it is used where installed, never
        # shipped. Two entries because the stack names the weight explicitly.
        "Eksempelkommune Sans", "Eksempelkommune Sans Regular",
        "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI",
        "Roboto", "Helvetica Neue", "Helvetica", "Arial", "sans-serif",
    }
    # CSS-wide keywords are not families and must not be judged as one.
    CSS_KEYWORDS = {"inherit", "initial", "unset", "revert", "revert-layer"}
    stack = re.search(r"font-family:([^;]+);", css)
    check("a font stack exists", stack is not None, failures)
    all_families = set()
    for declaration in re.findall(r"font-family:([^;}]+)", css):
        for family in declaration.split(","):
            family = family.strip().strip('"\'')
            if family and not family.startswith("var(") and family not in CSS_KEYWORDS:
                all_families.add(family)
    check("every font-family declared is on the permitted list",
          all_families <= PERMITTED_FAMILIES, failures,
          f"unlisted: {sorted(all_families - PERMITTED_FAMILIES)}")
    check("the allow-list check is not vacuous — families were parsed",
          len(all_families) >= 2, failures, f"parsed {len(all_families)}")
    if stack:
        families = [f.strip().strip('"\'') for f in stack.group(1).split(",")]
        check('"Eksempelkommune Sans" is first in the font stack',
              families and families[0] == "Eksempelkommune Sans", failures, str(families[:2]))
        check("the stack falls back to a system font, so layout holds without it",
              any(f in families for f in ("system-ui", "sans-serif")), failures)
    check("no @font-face rule — no font file is ever embedded",
          "@font-face" not in html, failures)
    check("no url() in the stylesheet — nothing is fetched",
          not re.search(r"url\(", css), failures)

    # One slot, clearly marked, and no colour literal outside it. Read the RAW
    # style text: stylesheet() strips comments, and the markers ARE comments.
    raw = "\n".join(STYLE_BLOCK.findall(html))
    check("the Eksempelkommune palette slot is opened and closed exactly once",
          raw.count("TENANT PALETTE SLOT") == 2, failures,
          f"found {raw.count('TENANT PALETTE SLOT')} markers, expected 2")
    before, _, rest = raw.partition("TENANT PALETTE SLOT")
    inside, _, after = rest.partition("END TENANT PALETTE SLOT")
    check("no colour literal after the slot closes — colour is set in one place",
          not re.search(r"#[0-9a-fA-F]{3,8}", after), failures,
          str(re.findall(r"#[0-9a-fA-F]{3,8}", after)[:4]))
    check("the slot actually holds the status and primary values",
          len(re.findall(r"#[0-9a-fA-F]{3,8}", inside)) == 9, failures,
          str(len(re.findall(r"#[0-9a-fA-F]{3,8}", inside))))
    check("the base block before the slot is greyscale only",
          all(h[1:3] == h[3:5] == h[5:7]
              for h in re.findall(r"#[0-9a-fA-F]{6}", before)), failures,
          str(re.findall(r"#[0-9a-fA-F]{6}", before)))

    # The ASK convention: shape carries the meaning, colour reinforces it. Parse
    # the map OUT OF THE FILE — comparing this function's own literals to itself
    # is a gate that cannot fail, which is worse than having none.
    declared = re.search(r"var STATUS_SYMBOL = \{([^}]*)\};", html)
    check("STATUS_SYMBOL is declared in the file", declared is not None, failures)
    shapes = {}
    if declared:
        for word, escape in re.findall(r'"([^"]+)":"\\u([0-9a-fA-F]{4})"', declared.group(1)):
            shapes[word.lower()] = chr(int(escape, 16))
    check("STATUS_SYMBOL maps exactly the three statuses",
          sorted(shapes) == ["avlyst", "i rute", "venter"], failures, str(sorted(shapes)))
    check("the three status shapes in the file are distinct",
          len(set(shapes.values())) == len(shapes) == 3, failures, str(shapes))
    # ...and the legend a no-JS reader sees must agree with that map, or the key
    # teaches one convention while the table renders another.
    legend = re.search(r'<p class="legend">(.*?)</p>', html, re.S)
    check("a static shape legend is present for readers with scripts off",
          legend is not None, failures)
    if legend and shapes:
        shown = legend.group(1)
        for word, glyph in shapes.items():
            entity = f"&#{ord(glyph)};"
            check(f"legend shows {word!r} with the same shape the table uses",
                  (glyph in shown or entity in shown)
                  and re.search(word, shown, re.I) is not None, failures,
                  f"looked for {glyph} ({entity}) next to {word!r}")
    # Every badge rule that sets a colour must also be reachable with a label;
    # the mark and the word are emitted together in one esc() call.
    check("status cells emit shape and word together, never colour alone",
          "STATUS_SYMBOL, v) : \"?\") + \" \" + v" in html, failures)


def run_static(failures: list[str]) -> None:
    print("\n-- static checks (no browser) --")
    html = HTML.read_text(encoding="utf-8")
    data = DATA.read_text(encoding="utf-8")
    css = stylesheet(html)

    hits = re.findall(r"position\s*:\s*(sticky|fixed)", css)
    check("no position:sticky / position:fixed declaration", not hits, failures, str(hits))
    check("no CSS ':target' selector", ":target" not in css, failures)
    inline = [s for s in re.findall(r'style\s*=\s*"([^"]*)"', html) if "position" in s]
    check("no positioning in a style attribute", not inline, failures, str(inline))
    check("no script setting .style.position", ".style.position" not in html, failures)

    ok, msg = check_no_stray_script_text(html)
    check("script-open text only in real elements", ok, failures, msg if not ok else "")

    for banned in ("fetch(", "XMLHttpRequest"):
        check(f"no {banned} (sidecar is loaded as code)", banned not in html, failures)

    # No free text anywhere in the data: every value must match its column's
    # allow-list. This is what "no real pupil name" actually means here.
    #
    # Deliberately a second copy of build_*.py's VOCABULARY: a generator that
    # checks only its own vocabulary proves nothing about what it wrote.
    #
    # But a second hand-typed copy only fails loudly in ONE direction, and it is
    # not the dangerous one. Make this copy STRICTER than the builder's and the
    # mismatch is instant and obvious. Make it LOOSER — the limit case being
    # re.compile(r".*") — and every check below still passes while proving
    # nothing at all. That was the state of this file when it was written: the
    # pattern loop reported "all 57 distinct data values come from the synthetic
    # vocabulary" against an allow-list that accepted anything, which is a claim
    # satisfiable without the property holding.
    #
    # Two guards close it, and neither depends on the regexes being right:
    #   1. EXPECTED_VALUES below asserts the exact SET of distinct values found
    #      per column. Loosening a pattern cannot widen a set, so the guarantee
    #      no longer rests on the pattern at all.
    #   2. Every pattern is shown a canary that looks like a real name. An
    #      allow-list that accepts it is not an allow-list, whatever it matches.
    stray = []
    checked = 0
    for column, pattern in ALLOWED.items():
        values = set(re.findall(r'"' + column + r'":\s*"([^"]*)"', data))
        if not values:
            stray.append(f"{column}: no values found in data.js")
            continue
        checked += len(values)
        stray += [f"{column}={v!r}" for v in values if not pattern.fullmatch(v)]
    # Guard 2: the threat, stated directly. A name must be rejected by every
    # column's allow-list, including the free-text-shaped columns.
    #
    # Assembled at runtime rather than written as literals. The repo's own
    # real-data gate (tools/check_no_real_data.py) scans tracked files for
    # name, e-mail and personal-number SHAPES, and it correctly flagged an
    # e-mail literal here when these were spelled out. A canary is test input,
    # but the gate cannot know that, and teaching it an exception would blunt it
    # for every other file. Composing the strings keeps both checks honest.
    def _c(*parts: str) -> str:
        return "".join(parts)

    canaries = (
        _c("Ola", " ", "Nordmann"),          # a full name
        _c("O.", " ", "Nordmann"),           # initials plus surname
        _c("ola", ".", "nordmann", "@", "example", ".", "com"),  # RFC 2606 domain
        _c("123", "456", "78901"),           # 11 digits, personal-number shaped
    )
    porous = [f"{column} accepts {canary!r}"
              for column, pattern in ALLOWED.items()
              for canary in canaries if pattern.fullmatch(canary)]
    check(f"no column's allow-list accepts a name-shaped value "
          f"({len(ALLOWED)} columns x {len(canaries)} canaries)",
          not porous, failures, str(porous[:4]))
    check(f"all {checked} distinct data values come from the synthetic vocabulary",
          not stray and checked > 0, failures, "; ".join(stray[:4]))
    # Guard 1: the exact value set per closed-vocabulary column. Independent of
    # every regex above, so loosening one changes nothing here.
    set_problems = []
    for column, expected in EXPECTED_VALUES.items():
        found = set(re.findall(r'"' + column + r'":\s*"([^"]*)"', data))
        if found != expected:
            extra, missing = sorted(found - expected), sorted(expected - found)
            set_problems.append(
                f"{column}: " + ", ".join(
                    part for part in (f"unexpected {extra}" if extra else "",
                                      f"absent {missing}" if missing else "") if part))
    check(f"every closed column holds exactly its expected value set "
          f"({len(EXPECTED_VALUES)} columns, "
          f"{sum(len(v) for v in EXPECTED_VALUES.values())} values)",
          not set_problems, failures, "; ".join(set_problems[:4]))

    # The published paired contract (docs/13 §1) is {generated, source, rows}
    # and nothing else. `rows` is the one field that can silently lie, so it is
    # re-derived from the payload rather than trusted.
    meta = re.search(r"window\.DASHBOARD_META\s*=\s*(\{.*?\});", data, re.S)
    if not meta:
        check("data.js sets window.DASHBOARD_META", False, failures)
        return
    try:
        fields = json.loads(meta.group(1))
    except ValueError as exc:
        check("DASHBOARD_META is valid JSON", False, failures, str(exc))
        return
    check("DASHBOARD_META carries exactly generated, source, rows",
          sorted(fields) == ["generated", "rows", "source"], failures,
          str(sorted(fields)))
    actual = len(re.findall(r'"Dato":\s*"', data))
    check("DASHBOARD_META.rows matches the rows actually in the file",
          fields.get("rows") == actual, failures,
          f"meta says {fields.get('rows')}, file has {actual}")


def run_no_js(failures: list[str], shots: list[pathlib.Path]) -> None:
    from playwright.sync_api import sync_playwright

    print("\n-- JavaScript DISABLED --")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800},
                                java_script_enabled=False)
        page.goto(HTML.as_uri())

        shown = page.eval_on_selector("#js-warning",
                                      "el => getComputedStyle(el).display !== 'none'")
        check("warning banner visible with no script at all", shown, failures)

        for view in ("view-day", "view-schemes", "view-routines"):
            vis = page.eval_on_selector(f"#{view}",
                                        "el => getComputedStyle(el).display !== 'none'")
            check(f"#{view} readable without script", vis, failures)
        text = page.inner_text("#view-schemes")
        check("the three Ordning regimes are in static markup",
              all(s in text for s in ("Grunnskole drosje", "langdagSFO TT-kort",
                                      "VGS TT-kort")), failures)
        text = page.inner_text("#view-routines")
        check("the routines are in static markup",
              "07:00" in text and "412 Precondition Failed" in text, failures)

        nav = page.eval_on_selector("#nav", "el => getComputedStyle(el).display === 'none'")
        check("nav hidden without script (no dead links)", nav, failures)
        fs = page.eval_on_selector("#fullscreen", "el => el.hidden === true")
        check("fullscreen button hidden without script", fs, failures)
        live = page.eval_on_selector("#day-live", "el => getComputedStyle(el).display === 'none'")
        check("empty day furniture hidden without script", live, failures)
        static_note = page.eval_on_selector("#day-static",
                                            "el => getComputedStyle(el).display !== 'none'")
        check("a static line explains the missing day list", static_note, failures)
        rows = page.locator("#tbl tbody tr").count()
        check("day list is empty and the banner says why", rows == 0, failures,
              f"{rows} rows")

        shot = HERE / "preview-nojs-1280.png"
        page.screenshot(path=str(shot), full_page=True)
        shots.append(shot)
        browser.close()


def run_with_js(failures: list[str], shots: list[pathlib.Path]) -> None:
    from playwright.sync_api import sync_playwright

    print("\n-- JavaScript ENABLED --")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(HTML.as_uri())
        page.wait_for_timeout(400)

        for box in ("js-warning", "js-partial", "data-error"):
            hidden = page.eval_on_selector(f"#{box}", "el => el.hidden === true")
            check(f"#{box} hidden on a healthy page", hidden, failures)
        check("nav visible once a script ran",
              page.eval_on_selector("#nav", "el => getComputedStyle(el).display !== 'none'"),
              failures)
        check("day list shown, static stand-in hidden",
              page.eval_on_selector("#day-live", "el => getComputedStyle(el).display !== 'none'")
              and page.eval_on_selector("#day-static",
                                        "el => getComputedStyle(el).display === 'none'"),
              failures)

        # Row 26: exactly one scrolling container in the whole document.
        scrollers = page.evaluate(
            "() => [...document.querySelectorAll('*')]"
            ".filter(e => ['auto','scroll'].includes(getComputedStyle(e).overflowY))"
            ".map(e => e.id || e.tagName)")
        check("#content is the sole overflow-y container", scrollers == ["content"],
              failures, str(scrollers))
        check("body does not scroll",
              page.eval_on_selector("body", "el => getComputedStyle(el).overflowY") == "hidden",
              failures)

        # Row 24: a class toggle, and no fragment navigation at all.
        page.click("#nav a[data-view='view-schemes']")
        page.wait_for_timeout(200)
        check("clicking Ordninger activates #view-schemes",
              page.eval_on_selector("#view-schemes", "el => el.classList.contains('active')"),
              failures)
        check("clicking Ordninger deactivates #view-day",
              not page.eval_on_selector("#view-day", "el => el.classList.contains('active')"),
              failures)
        frag = page.evaluate("() => location.hash")
        check("location.hash stayed empty (preventDefault ran, not :target)",
              frag == "", failures, repr(frag))
        shot = HERE / "preview-1280-ordninger.png"
        page.screenshot(path=str(shot), full_page=True)
        shots.append(shot)

        page.click("#nav a[data-view='view-day']")
        page.wait_for_timeout(200)
        check("clicking back activates #view-day",
              page.eval_on_selector("#view-day", "el => el.classList.contains('active')"),
              failures)

        # Row 21: the button is revealed, and using it never surfaces an error.
        check("fullscreen button revealed",
              page.eval_on_selector("#fullscreen", "el => el.hidden === false"), failures)
        before = len(errors)
        page.click("#fullscreen")
        page.wait_for_timeout(400)
        check("clicking fullscreen raised no error", len(errors) == before, failures,
              errors[before] if len(errors) > before else "")
        if page.evaluate("() => !!document.fullscreenElement"):
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)

        check("console clean", not errors, failures, errors[0][:120] if errors else "")

        shot = HERE / "preview-1280.png"
        page.screenshot(path=str(shot), full_page=True)
        shots.append(shot)
        page.close()

        # 390px — the narrow end docs/11 §2 says is supported.
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(HTML.as_uri())
        page.wait_for_timeout(400)
        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check("390px: no horizontal overflow", overflow <= 1, failures, f"{overflow}px")
        check("390px: table collapsed to cards",
              page.eval_on_selector("#tbl thead", "el => getComputedStyle(el).display") == "none",
              failures)
        small = page.evaluate(
            "() => [...document.querySelectorAll('#nav a, #controls select, "
            "#controls button, #fullscreen')]"
            ".filter(e => e.getBoundingClientRect().height < %d)"
            ".map(e => (e.id || e.textContent.trim()) + ':' "
            "+ Math.round(e.getBoundingClientRect().height))" % TOUCH_MIN_PX)
        check(f"390px: every control at least {TOUCH_MIN_PX}px tall", small == [],
              failures, str(small))
        shot = HERE / "preview-390.png"
        page.screenshot(path=str(shot), full_page=True)
        shots.append(shot)
        browser.close()


def run_bad_data(failures: list[str]) -> None:
    """The docs/13 §2 gap: the INITIAL data.js load must fail visibly too."""
    from playwright.sync_api import sync_playwright

    print("\n-- initial-load validation (docs/13 §2) --")
    good = DATA.read_text(encoding="utf-8")

    def mutate(old: str, new: str, label: str) -> str:
        out = good.replace(old, new, 1)
        if out == good:
            failures.append(f"could not build the {label!r} case — data.js shape changed")
            print(f"  ✗ could not build the {label!r} case")
        return out

    # A column missing from row 40, not row 1 — the shape a generator bug
    # actually produces, and the one a rows[0]-only check waves through.
    fortieth = good.split("\n")
    body = [n for n, line in enumerate(fortieth) if line.startswith('{"Dato"')]
    broken_deep = good
    if len(body) > 40:
        line = fortieth[body[39]]
        broken_deep = good.replace(line, line.replace('"Ledsager":', '"Foelge":', 1), 1)
    else:
        failures.append("data.js has fewer than 40 rows — the deep case cannot be built")

    cases = [
        ("missing column in row 1", mutate('"Ledsager":', '"Foelge":', "missing column"),
         "Ledsager"),
        ("missing column in row 40", broken_deep, "Rad 40"),
        ("empty array", re.sub(r"window\.DASHBOARD_DATA=\[.*?\n\];",
                              "window.DASHBOARD_DATA=[];", good, flags=re.S),
         "Datafilen er tom"),
        ("no data.js at all", None, "Fant ingen data"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for label, body_text, expect in cases:
                folder = root / label.replace(" ", "-")
                folder.mkdir()
                shutil.copy(HTML, folder / "oversikt.html")
                if body_text is not None:
                    (folder / "data.js").write_text(body_text, encoding="utf-8")
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                page.goto((folder / "oversikt.html").as_uri())
                page.wait_for_timeout(400)
                shown = page.eval_on_selector("#data-error", "el => el.hidden === false")
                said = page.inner_text("#data-error")
                check(f"{label}: error shown on initial load", shown, failures)
                check(f"{label}: message names what is wrong", expect in said, failures,
                      said.replace("\n", " ")[:110])
                # A deliberate, explained failure must not also claim it crashed.
                partial = page.eval_on_selector("#js-partial", "el => el.hidden === true")
                check(f"{label}: no false 'stopped partway' banner", partial, failures)
                page.close()

            # An unrecognised value must warn WITHOUT blanking the board: a day
            # list that disappears over one typo is worse than one that renders
            # and says which values it did not know.
            odd = (good.replace('"Status": "I rute"', '"Status": "Fremskutt"', 1)
                       .replace('"Ordning": "VGS TT-kort"', '"Ordning": "Ny ordning"', 1))
            folder = root / "unknown-values"
            folder.mkdir()
            shutil.copy(HTML, folder / "oversikt.html")
            (folder / "data.js").write_text(odd, encoding="utf-8")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto((folder / "oversikt.html").as_uri())
            page.wait_for_timeout(400)
            warned = page.eval_on_selector("#data-warning", "el => el.hidden === false")
            text = page.inner_text("#data-warning")
            check("unknown values: warning shown", warned, failures)
            check("unknown values: names the unknown Status", "Fremskutt" in text, failures,
                  text.replace("\n", " ")[:110])
            check("unknown values: names the Ordning with no owner",
                  "Ny ordning" in text, failures)
            check("unknown values: the board still renders",
                  page.locator("#tbl tbody tr").count() > 0, failures)
            check("unknown values: the odd status is marked unknown, not dressed up",
                  page.locator(".badge.unknown").count() > 0, failures)
            check("unknown values: no fatal error banner",
                  page.eval_on_selector("#data-error", "el => el.hidden === true"), failures)
            # The KPI row must follow the data, not the régimes it shipped with.
            kpis = page.eval_on_selector_all(".kpi .label", "els => els.map(e => e.textContent)")
            check("unknown values: KPI row picked up the new Ordning",
                  "Ny ordning" in kpis, failures, str(kpis))
            page.close()
            browser.close()


def main() -> int:
    if not HTML.exists() or not DATA.exists():
        print("✗ build first: python3 examples/17-multi-regime-day-board/"
              "build_day_board.py")
        return 2
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        print("✗ playwright missing — install: uv sync --extra verify && "
              "uv run playwright install chromium")
        return 2

    failures: list[str] = []
    shots: list[pathlib.Path] = []
    print(f"verifying {HTML.name} + {DATA.name}")
    print("─" * 66)
    run_brand(failures)
    run_static(failures)
    run_no_js(failures, shots)
    run_with_js(failures, shots)
    run_bad_data(failures)

    print("─" * 66)
    if failures:
        print(f"\n✗ FAIL — {len(failures)} issue(s):")
        for f in failures:
            print(f"    • {f}")
        return 1
    print("\n✓ PASS — every checked constraint holds.")
    print("  Now LOOK at these. Assertions cannot see an overlap or a wrong number:")
    for shot in shots:
        print(f"    {shot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
