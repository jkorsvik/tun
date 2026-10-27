#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Is the dark theme measured on the pages that actually have one?

`tools/verify_a11y.py` measured every artefact in the light scheme, and `verify_documented`
still runs it that way. So a page that carries a `prefers-color-scheme` block was verified in
the colours half its readers never see. The theming work measured its token pairs, but nothing
measured a dark *page*, and the difference is not academic: the first run of this gate found
that `examples/05-theme-toggle-demo` shipped the system route and then disarmed it, because its
script set `data-theme="light"` on every load. A dark-mode reader got a white page, and the
documentation said the opposite. That is now fixed in the demo, and this suite is why it was
noticed.

What is checked:

  * the pages that answer the media query are found, and there is at least one that follows the
    system with no script. A gate that finds nothing must not report success;
  * for a page that follows the system, the rendered colours really do differ between the two
    schemes, and `verify_a11y --dark` passes;
  * for a page that disarms the media query with its own toggle, the disarm is deliberate and
    named here with a reason, and its dark colours are measured with `verify_a11y --theme dark`
    so they are not left unmeasured either;
  * a page whose dark block does break contrast is caught by the dark run and NOT by the light
    one, which is the whole point of the flag.

    uv run --extra verify python3 tests/test_dark_scheme_gate.py
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
EXAMPLES = ROOT / "examples"

# Pages that carry a prefers-color-scheme block and then set data-theme on load, so the block
# never applies. Each needs a reason, and a page that starts doing this without one fails.
DISARMED_OK = {
    "examples/06-chart-palette-demo/chart-palette-demo.html":
        "a palette proof-of-concept whose dark declarations exist to be measured by "
        "tools/check_token_contrast.py, not to theme the page; its toggle is the point",
    "examples/10-consolidated-standalone-demo/consolidated-standalone-demo.html":
        "the consolidated demo keeps an explicit default so its three sections render "
        "identically; the system route is demonstrated in 05",
}

# Artefacts that must NOT, and why. The failure this records is the opposite of the one
# REQUIRED_FOLLOWERS records: a surface where following the reader's system setting would
# override a choice the artefact's own author made, or where there is no screen to follow.
# Each entry is checked twice: the file exists, and it really carries no media query. An
# entry that quietly gains one is a lie in a comment, and this list is meant to be a fact.
LIGHT_BY_DESIGN = {
    "examples/37-printable-onepager/ett-ark.html":
        "one A4 sheet. It is read on paper or as a PDF, and its @media print rule forces "
        "white. A dark screen preview would be a preview of something that cannot be printed.",
    "examples/18-portable-slide-deck/maalebandet.html":
        "a projected deck. Its own palette is the design: a dark teal stage, a paper slide, "
        "and slides the author marked .slide.dark to invert on purpose. Following the "
        "reader's setting would override that choice on every slide at once.",
    "examples/21-slide-deck-detail-overlay/detail-overlay-pattern.html":
        "the same deck pattern with a detail overlay, same reason.",
}

# Every shipped template is accounted for here. A template either carries `{{TOKEN_CSS}}`
# (and so follows the reader's system setting) or is named below with a reason. This list was
# added after the rollout was described as complete from the memory of what had merged: nine
# templates written in the same days still carried nine to fourteen colour variables of their
# own, and no gate asked. An entry is deleted when its template gains the seam, so the list
# is a measurement of what is left, and the permanent entries are the two surfaces that will
# never take it.
SEAM_PENDING = {
    "templates/onepager.html":
        "an A4 sheet whose @media print rule forces white. Its artefact is on LIGHT_BY_DESIGN "
        "for the same reason, and a dark screen preview would preview something unprintable.",
    "templates/showcase.html":
        "an index of other artefacts, not one of them. Its chrome is two surfaces, one "
        "accent and one line colour, carried inline so the page reads as a catalogue beside "
        "the pages it lists; it has no chart mark, table row or palette to hand to the seam.",
    "templates/portable-slide-deck.html":
        "a projected deck. Its palette is the design, with .slide.dark chosen per slide by the "
        "author, so following the reader's setting would override that choice everywhere.",
}

# Artefacts that MUST follow the system setting. A gate that only measures the pages which
# happen to carry a media query cannot notice a builder that never gained one, and that is
# the failure mode this list exists for: the process diagram shipped for months as a white
# page to every reader whose operating system is dark, and every gate was green because the
# question was never asked of it. Adding a builder here is the point at which its dark
# surface is measured, so the list grows with the rollout and never shrinks.
REQUIRED_FOLLOWERS = {
    "examples/23-process-diagram/tun-workflow.html":
        "the columns drawing; its six lane roles need a dark ramp of their own",
    "examples/23-process-diagram/fem-roller.html":
        "the same builder in its rows layout, five lanes",
    "examples/34-folder-index/index.html":
        "the folder front page; its header band and card links pick a slot by a light role",
    "examples/27-survey-board/survey.html":
        "the survey board; its distribution bar is painted by script, so its five blocks are "
        "the categorical series, and the header band is the usual light-role pick",
    "examples/31-survey-crosstab/survey-crosstab.html":
        "the same builder with cross-tabs",
    "examples/35-timeline/tidslinje.html":
        "the timeline; its bar fill is a mark on a card and its group heading is 14 px SVG "
        "text, both re-pointed in the template's dark block",
    "examples/33-comparison/sammenligning.html":
        "the comparison; its header band picks a slot by a light role, and its status colours "
        "come from the theme instead of from hexes chosen for white",
    "examples/01-hello-dashboard/salg-dashboard.html":
        "the flagship dashboard; it carried forty hand-written the design system values and ten palette "
        "names painted directly, and its KPI figures lettered --brand-dark on a --panel card",
    "examples/28-one-dataset-three-artefacts/kube.html":
        "the cube; its four card surfaces painted a raw white and its form controls inherited "
        "the browser's own button text, which does not follow a theme",
    "examples/39-scorecard/manedsrapport.html":
        "the scorecard; its header band lettered --brand-dark on its own fill, its status words "
        "Fire Red as TEXT, and its weekly sparklines drawn against a --brand-dark target line "
        "that is the darkest surface in dark",
    "examples/40-waterfall/bro.html":
        "the waterfall; its header band lettered --brand-dark on its own fill, its tags and "
        "column headers a --brand-dark ink on a --brand-soft wash, and each total drawn as a "
        "level rule in a colour that is the darkest surface in dark",
    "examples/53-sankey/kanaler.html":
        "the sankey; its header band lettered --brand-dark on its own fill, the ribbons a "
        "translucent --brand, the node bars in --brand-dark which the template re-points to "
        "--ink in dark so a bar cannot vanish into the panel, and its labels haloed in --panel",
    "examples/52-pareto/arsaker.html":
        "the pareto; its header band lettered --brand-dark on its own fill, the bars in --brand, "
        "the folded tail a --brand-soft wash, and the cumulative line in --ink so it is a second "
        "series rather than a shade of the first",
    "examples/51-bullet/dekning.html":
        "the bullet chart; its header band lettered --brand-dark on its own fill, the track a "
        "--brand-soft wash, the bar in --brand (or --bad when behind), and the target mark in "
        "--ink so it reads as a line rather than as a verdict",
    "examples/50-calendar/kalender.html":
        "the calendar; its band fills and their inks are generated per theme by the builder, "
        "and the header band is lettered --brand-dark on its own fill",
    "examples/49-gantt/fremdrift.html":
        "the gantt; its header band lettered --brand-dark on its own fill, the plan bar an "
        "outline and the actual bar a fill in --brand, and the today rule in --muted so it "
        "reads as a reference rather than an alarm",
    "examples/48-boxplot/boksplott.html":
        "the box plot; its header band lettered --brand-dark on its own fill, its median line "
        "stroked in --brand-dark, which is the darkest surface in dark, and its gridlines and "
        "column headers the usual light-role pair",
    "examples/47-scatter/spredning.html":
        "the scatter; its header band lettered --brand-dark on its own fill, its column headers "
        "a --brand-dark ink on a --brand-soft wash, and its gridlines and fit line greys chosen "
        "to sit quietly on white",
    "examples/45-smallmultiples/smaaflater.html":
        "the small multiples; its header band lettered --brand-dark on its own fill, its column "
        "headers a --brand-dark ink on a --brand-soft wash, and its panel gridlines a grey chosen "
        "to sit quietly on white",
    "examples/46-rank-change/rang.html":
        "the rank change; its header band lettered --brand-dark on its own fill, its SVG headings "
        "and values filled with --brand-dark (the darkest surface in dark), and its flat "
        "connector a grey chosen for a white panel",
    "examples/43-heatmap/varmekart.html":
        "the heatmap; its header band lettered --brand-dark on its own fill, its column headers a "
        "--brand-dark ink on a --brand-soft wash, and its five bands a ramp mixed into white, "
        "where blue is 1.31:1 against a dark panel",
    "examples/42-funnel/tratt.html":
        "the funnel; its header band lettered --brand-dark on its own fill, its column headers a "
        "--brand-dark ink on a --brand-soft wash, and its warning card a Fire Red wash chosen "
        "for a white page",
    "examples/38-distribution/behandlingstid.html":
        "the distribution; its header band lettered --brand-dark on its own fill, its column "
        "headers a --brand-dark ink on a --brand-soft wash, and its median rule drawn in a "
        "colour that is the darkest surface in the dark theme",
    "examples/41-composition/sammensetning.html":
        "the composition; its header band lettered --brand-dark on its own fill, its tags and "
        "column headers a --brand-dark ink on a --brand-soft wash, and its four categorical "
        "bands needed a ramp chosen for a dark panel rather than the light one",
    "examples/44-cohort/kohort.html":
        "the cohort grid; its header band lettered --brand-dark on a --brand-dark fill, its row "
        "headers lettered --brand-dark on a --brand-soft wash, and its not-yet cells a grey hatch",
    "examples/32-rows-register/register.html":
        "the row register; its header band picks a slot by a light role, and it carries the "
        "only band lettered with --on-brand-soft",
}

FAILURES: list[str] = []
CHECKS = 0


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


def dark_pages() -> list[pathlib.Path]:
    """Every built page that answers prefers-color-scheme, found by reading the page itself."""
    found = []
    for path in sorted(EXAMPLES.rglob("*.html")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "prefers-color-scheme" in text:
            found.append(path)
    return found


def probe(path: pathlib.Path, scheme: str, theme: str = "") -> dict:
    """The rendered colours, and whether the page set its own theme attribute."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1366, "height": 768},
                                    color_scheme=scheme)
            page.goto(path.resolve().as_uri())
            page.wait_for_timeout(250)
            if theme:
                page.evaluate("(name) => document.documentElement.setAttribute("
                              "'data-theme', name)", theme)
                page.wait_for_timeout(150)
            return page.evaluate("""() => {
              const b = getComputedStyle(document.body);
              const h = getComputedStyle(document.querySelector('header') || document.body);
              return {attr: document.documentElement.getAttribute('data-theme'),
                      bg: b.backgroundColor, ink: b.color, head: h.backgroundColor};
            }""")
        finally:
            browser.close()


def a11y(path: pathlib.Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOLS / "verify_a11y.py"), str(path), *extra],
                          capture_output=True, text=True, cwd=ROOT)


def main() -> int:
    pages = dark_pages()

    print("\n0. an artefact that stays light says so, and is telling the truth")
    chk(len(LIGHT_BY_DESIGN) >= 2, "the light-by-design list is populated", str(len(LIGHT_BY_DESIGN)))
    for rel, why in LIGHT_BY_DESIGN.items():
        path = ROOT / rel
        chk(path.is_file(), f"{rel} exists")
        chk(len(why) >= 40, f"{rel} carries a reason someone can weigh, not a word", why)
        if path.is_file():
            chk("prefers-color-scheme" not in path.read_text(encoding="utf-8"),
                f"{rel} really carries no media query, so the reason still applies")
    overlap = set(LIGHT_BY_DESIGN) & set(REQUIRED_FOLLOWERS)
    chk(not overlap, "no artefact is on both lists", str(sorted(overlap)))

    print("\n0b. every shipped template is either seam-carrying or accounted for")
    templates = sorted(p for p in (ROOT / "templates").glob("*.html")
                       if not p.name.startswith("_"))
    chk(len(templates) >= 15, "the template scan found the templates",
        f"{len(templates)}: {[p.name for p in templates]}")
    for path in templates:
        rel = str(path.relative_to(ROOT))
        carries = "{{TOKEN_CSS}}" in path.read_text(encoding="utf-8")
        if carries:
            chk(rel not in SEAM_PENDING,
                f"{path.name}: carries the seam, so it must not be listed as pending",
                "delete its SEAM_PENDING entry")
        else:
            chk(rel in SEAM_PENDING,
                f"{path.name}: not on the seam, so it is named in SEAM_PENDING with a reason",
                "add it with a reason, or give it the seam")
    for rel, why in SEAM_PENDING.items():
        path = ROOT / rel
        chk(path.is_file(), f"{rel} exists")
        chk(len(why) >= 40, f"{rel} carries a reason someone can weigh, not a word", why)
        if path.is_file():
            chk("{{TOKEN_CSS}}" not in path.read_text(encoding="utf-8"),
                f"{rel} really has no seam yet, so the entry is not stale",
                "it carries the seam now: delete the entry")

    print("\n1. the scan finds the pages that carry a dark theme")
    chk(len(pages) >= 3, "at least a few pages answer prefers-color-scheme",
        f"{len(pages)}: {[p.name for p in pages]}")

    print("\n2. each page is either following the system or disarming it on purpose")
    following, disarmed = [], []
    for page in pages:
        seen = probe(page, "light")
        if seen["attr"] is None:
            following.append(page)
        else:
            disarmed.append((page, seen["attr"]))
    chk(bool(following), "at least one page follows the system with no script",
        f"every page disarmed itself: {[str(p) for p in pages]}")
    # The ratchet: a builder on this list may not stop following the system, and may not
    # quietly disappear from the scan either.
    following_rel = {str(p.relative_to(ROOT)) for p in following}
    for rel in REQUIRED_FOLLOWERS:
        chk(rel in following_rel,
            f"{rel}: follows the system setting (required)",
            "it carries no prefers-color-scheme block, or it disarms it")
    for page, attr in disarmed:
        rel = str(page.relative_to(ROOT))
        chk(rel in DISARMED_OK,
            f"{page.name}: disarming the media query is a decision with a reason",
            f"it set data-theme={attr!r} and is not listed in DISARMED_OK")
    for rel in DISARMED_OK:
        stale = (not (ROOT / rel).exists()
                 or "prefers-color-scheme" not in (ROOT / rel).read_text(encoding="utf-8"))
        chk(not stale, f"{rel} still exists and still carries the media query",
            "the entry went stale")

    print("\n3. a page that follows the system really does change colour")
    for page in following:
        light = probe(page, "light")
        dark = probe(page, "dark")
        chk(light["bg"] != dark["bg"] or light["ink"] != dark["ink"],
            f"{page.name}: the colours change when the system is dark",
            f"light {light['bg']}/{light['ink']} == dark {dark['bg']}/{dark['ink']}")

    print("\n4. the six rules pass in the scheme each reader gets")
    for page in following:
        result = a11y(page, "--dark")
        chk(result.returncode == 0, f"{page.name}: verify_a11y --dark passes",
            str(result.stdout.strip().splitlines()[-1:]))
    for page, _attr in disarmed:
        result = a11y(page, "--theme", "dark")
        chk(result.returncode == 0, f"{page.name}: verify_a11y --theme dark passes",
            str(result.stdout.strip().splitlines()[-1:]))

    print("\n5. a broken dark block is caught in dark, and only in dark")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        victim = following[0]
        broken = tmp / victim.name
        shutil.copy2(victim, broken)
        # One appended rule, so the mutation applies whatever the page's own tokens are called.
        broken.write_text(
            broken.read_text(encoding="utf-8").replace(
                "</body>",
                "<style>@media (prefers-color-scheme: dark){"
                "*{background-color:#111 !important;color:#121212 !important}}</style></body>"),
            encoding="utf-8")
        dark_run = a11y(broken, "--dark")
        light_run = a11y(broken)
        chk(dark_run.returncode == 1, "the dark run finds the broken contrast",
            str(dark_run.stdout.strip().splitlines()[-1:]))
        chk(light_run.returncode == 0,
            "and the light run does not, because the page is only broken in dark",
            str(light_run.stdout.strip().splitlines()[-1:]))

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failed of {CHECKS} checks:")
        for item in FAILURES:
            print(f"  - {item}")
        return 1
    print(f"{CHECKS} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
