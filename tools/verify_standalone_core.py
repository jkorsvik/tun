#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
verify_standalone_core.py — the generic-layer checks any standalone-HTML artefact can
run, regardless of specialisation (dashboards, docs, simulations, process diagrams, ...).

Adopted per docs/08-generic-artifact-model.md ("External consumers") and listed in
docs/14-generic-layer-manifest.md as safe to vendor into other repos. Imported by
tools/verify_dashboard.py, which adds dashboard-only DOM assertions on top — this module
does not know what a dashboard is and must stay that way.

Checks:
  1. self-contained     — no external http(s) subresource references
  2. size                — within the Tier 1 budget
  3. no leftover placeholders — no unsubstituted {{TOKEN}} left in the shipped HTML
  4. provenance          — a traceability comment block is present (source, built,
                            built by — see templates/_generic-provenance-block.html)
  5. no stray "<script"  — docs/01-tenant-constraints.md row 25
  6. no :target-driven visibility — docs/01-tenant-constraints.md row 24
  7. no scroll-persistent positioning — docs/01-tenant-constraints.md row 26
  8. console-clean render — renders from file:// without a console/page error
  9. screenshot           — written for human review

Checks 5-7 all encode the same class of fact: a mechanism that works perfectly from
file:// and is nonetheless disabled or broken in SharePoint's inline file-preview. None
of them can be proven by a local headless render, which is exactly why they are static
text checks and not render assertions.

Run standalone:
    python3 tools/verify_standalone_core.py <path-to.html> [--engines chromium,firefox,webkit]

Or import the check functions from another verifier (see tools/verify_dashboard.py for
the pattern) to add specialisation-specific checks on top without duplicating these.

Exit 0 = the generic core passed. This does NOT mean "safe to publish" for any given
specialisation — a dashboard also needs tun-verify's own checks; a process diagram
or other artefact needs whatever its own specialisation defines, if anything.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

SIZE_WARN_MB = 20
SIZE_FAIL_MB = 50

REMOTE_SUBRESOURCE = re.compile(
    r"""<(?:script|link|img|iframe|source)\b[^>]*?
        (?:src|href)\s*=\s*["'](https?://|//)""",
    re.IGNORECASE | re.VERBOSE,
)

PLACEHOLDER = re.compile(r"\{\{[A-Z0-9_]+\}\}")

# A shared file opens in whatever browser the reader has: Chrome and Edge are chromium,
# Safari is webkit, Firefox is its own engine. Every verify tool takes --engines from
# here. The default stays chromium, so a laptop with one browser installed can still
# verify; CI passes all three.
ENGINES = ("chromium", "firefox", "webkit")
DEFAULT_ENGINES = ("chromium",)


def engines_arg(value: str) -> tuple[str, ...]:
    """argparse type for --engines: a comma-separated subset of ENGINES, or 'all'."""
    if value == "all":
        return ENGINES
    names = tuple(dict.fromkeys(n.strip() for n in value.split(",") if n.strip()))
    unknown = [n for n in names if n not in ENGINES]
    if not names or unknown:
        raise argparse.ArgumentTypeError(
            f"choose from {','.join(ENGINES)} or all, got {value!r}")
    return names


def add_engines_arg(ap: argparse.ArgumentParser,
                    default: tuple[str, ...] = DEFAULT_ENGINES) -> None:
    ap.add_argument("--engines", type=engines_arg, default=default, metavar="LIST",
                    help=f"comma-separated subset of {','.join(ENGINES)}, or all "
                         f"(default: {','.join(default)})")


def shot_path(path: pathlib.Path, suffix: str, engine: str) -> pathlib.Path:
    """Screenshot name per engine. chromium keeps the name the docs already use."""
    stem = path.stem if engine == "chromium" else f"{path.stem}.{engine}"
    return path.with_name(stem + suffix)


def label_failures(failures: list[str], mark: int, engine: str,
                   engines: tuple[str, ...]) -> None:
    """Prefix the failures one engine added (from index mark) with its name, so a
    three-engine run says which browser broke. One engine: leave the text alone."""
    if len(engines) > 1:
        failures[mark:] = [f"{engine}: {f}" for f in failures[mark:]]


def check_self_contained(html: str) -> tuple[bool, str]:
    """No remote http(s) subresource — the offline/portability promise."""
    remote = REMOTE_SUBRESOURCE.findall(html)
    if remote:
        return False, f"{len(remote)} remote subresource(s) — breaks the offline promise"
    return True, "no external subresources"


def check_size(path: pathlib.Path) -> tuple[str, str, float]:
    """Returns (level, message, size_mb) where level is 'ok' | 'warn' | 'fail'."""
    size_mb = path.stat().st_size / 1_048_576
    if size_mb > SIZE_FAIL_MB:
        return "fail", f"{size_mb:.1f} MB exceeds the {SIZE_FAIL_MB} MB Tier 1 ceiling", size_mb
    if size_mb > SIZE_WARN_MB:
        return "warn", f"{size_mb:.1f} MB above the {SIZE_WARN_MB} MB comfort budget", size_mb
    return "ok", f"{size_mb:.2f} MB", size_mb


def check_no_leftover_placeholders(html: str) -> tuple[bool, str]:
    """A shipped file with an unsubstituted {{TOKEN}} means the build half-failed.

    Generic because the {{TOKEN}} substitution convention is not dashboard-specific —
    prosessflyt-verktoy's build.py uses the identical {{TITLE}}/{{VTAG_HTML}}
    convention in engine/shell_head.html.
    """
    leftover = sorted(set(PLACEHOLDER.findall(html)))
    if leftover:
        return False, f"unsubstituted placeholders: {', '.join(leftover)}"
    return True, "all substituted"


def check_provenance(html: str) -> tuple[bool, str]:
    """A traceability comment block is present.

    Generic because AGENTS.md's "provenance is mandatory" rule is stated for this whole
    repo's output, not just dashboards, and docs/08's artifact-audit proposal lists
    "provenance block present" as a Layer-1 (generic) principle. The marker text itself
    (PROVENANCE / Source data / Built) is deliberately free of dashboard vocabulary —
    see templates/_generic-provenance-block.html.
    """
    if "PROVENANCE" in html and "Source data" in html and "Built" in html:
        return True, "block intact"
    return False, "block missing or altered — numbers/output cannot be traced back"


def check_no_stray_script_text(html: str) -> tuple[bool, str]:
    """No literal "<script" substring anywhere outside a real <script> element —
    including inside an HTML comment, never executed by any browser.

    Generic because this is a SharePoint-preview-sandbox behaviour, not specific to
    any one artifact type: docs/01-tenant-constraints.md row 25 documents a real case
    (`en kollega-kollega/saksrom`, 2026-09-15) where a page's own documentation comment
    contained the prose "lastet via <script src> fra sidecar-filer" — plain text,
    inert, inside `<!-- -->`. That page's OWN one-line inline script (unrelated to the
    comment) never executed either, and removing only the two comment phrases with
    that literal text — zero other changes — fixed the file completely. Working
    theory: a content-scanning layer in front of the preview does a naive raw-text
    search for "<script", not a real HTML parse, and disables scripting for the whole
    page if it finds more occurrences than it expects. Uses a real HTML tokenizer
    (`html.parser`), not a regex substitution, specifically because an earlier
    same-evening attempt at this check used non-greedy `<script>.*?</script>` removal
    and could be fooled into pairing a stray opening tag with an unrelated real
    closing tag much further down the file, hiding the exact bug it was meant to
    catch — see `en kollega-kollega/saksrom` git history for that false-negative.
    """
    from html.parser import HTMLParser

    class _Counter(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=False)
            self.n = 0

        def handle_starttag(self, tag: str, attrs: list) -> None:
            if tag.lower() == "script":
                self.n += 1

    counter = _Counter()
    counter.feed(html)
    raw_positions = [m.start() for m in re.finditer(r"<script", html, re.IGNORECASE)]
    if len(raw_positions) > counter.n:
        lines = [html.count("\n", 0, pos) + 1 for pos in raw_positions]
        return False, (
            f'found "<script" {len(raw_positions)} time(s) but only {counter.n} are '
            f"real <script> elements (line(s): {', '.join(str(l) for l in lines)}) — "
            "at least one occurrence is stray text, e.g. in a comment (see "
            "docs/01-tenant-constraints.md row 25)"
        )
    return True, f'all {counter.n} "<script" occurrence(s) are real elements'


def _css_rules(html: str) -> list[tuple[str, str, int]]:
    """Every (selector, declaration-block, line-number) pair in the document's <style>
    elements.

    Uses `html.parser` to pull the stylesheet text out rather than a regex over the whole
    document, for the same reason check_no_stray_script_text does: a regex that pairs an
    opening tag with a closing tag it does not own is exactly how the row-25 check was
    fooled once already.

    The rule scan itself is deliberately a simple brace scanner, not a CSS parser. It
    cannot match a `{` inside a selector, which CSS does not allow anyway, and it steps
    over at-rule wrappers (`@media … { .a{…} }`) on its own, because the wrapper's own
    "block" contains a `{` and therefore never matches — the inner rule does.
    """
    from html.parser import HTMLParser

    class _StyleCollector(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=False)
            self._in_style = False
            self.blocks: list[tuple[str, int]] = []

        def handle_starttag(self, tag: str, attrs: list) -> None:
            if tag.lower() == "style":
                self._in_style = True

        def handle_endtag(self, tag: str) -> None:
            if tag.lower() == "style":
                self._in_style = False

        def handle_data(self, data: str) -> None:
            if self._in_style:
                self.blocks.append((data, self.getpos()[0]))

    collector = _StyleCollector()
    collector.feed(html)

    rules: list[tuple[str, str, int]] = []
    for css, start_line in collector.blocks:
        # Blank out /* … */ comments in place, preserving newlines so reported line
        # numbers stay true. Without this, a comment sitting between two rules is
        # absorbed into the next rule's selector (making messages unreadable), and —
        # worse — a comment that merely *describes* `position:fixed` or `:target`
        # inside a declaration block would trip the checks below. Same class of bug as
        # the one row 25's docstring describes: prose about a mechanism is not the
        # mechanism.
        css = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), css, flags=re.DOTALL)
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
            selector = " ".join(match.group(1).split())
            line = start_line + css.count("\n", 0, match.start(1))
            rules.append((selector, match.group(2), line))
    return rules


VISIBILITY_PROPS = re.compile(r"(?:^|;)\s*(display|visibility|opacity)\s*:", re.IGNORECASE)


def check_no_target_driven_visibility(html: str) -> tuple[bool, str]:
    """No CSS `:target` selector may control whether something is visible.

    Generic because this is a SharePoint-preview-sandbox behaviour, not specific to any
    one artifact type. docs/01-tenant-constraints.md row 24: fragment navigation does not
    occur in that surface at all — clicking `<a href="#page-x">` never makes `#page-x`
    the `:target`, even though JavaScript itself runs there (row 25). A page that hides
    every section except the current `:target` therefore renders one fixed section and
    cannot be navigated, with no error of any kind.

    This is the single hardest failure in this file to catch any other way: `:target`
    works flawlessly from `file://`, so a local headless render — including the one at
    the bottom of this module — passes it every time. examples/13's own verifier proved
    exactly that before #50.

    `:target` for anything cosmetic (a highlight colour, a scroll offset) is untouched;
    only `display`, `visibility` and `opacity` are treated as "controls visibility".
    """
    offenders = [
        (sel, line)
        for sel, decls, line in _css_rules(html)
        if ":target" in sel.lower() and VISIBILITY_PROPS.search(";" + decls)
    ]
    if offenders:
        detail = "; ".join(f"{sel} (line {line})" for sel, line in offenders[:3])
        more = f" and {len(offenders) - 3} more" if len(offenders) > 3 else ""
        return False, (
            f"{len(offenders)} rule(s) hide/show content via :target — {detail}{more}. "
            "Fragment navigation never fires in SharePoint's inline preview "
            "(docs/01-tenant-constraints.md row 24); use <input type=radio> + :checked, "
            "which needs no fragment navigation"
        )
    return True, "no :target controls visibility"


HEADER_ISH = re.compile(r"(?:^|[^a-z])(?:top-?bar|header|masthead|app-?bar|nav-?bar)\b", re.IGNORECASE)
CUSTOM_PROP = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)")
TOP_PINNED = re.compile(r"(?:^|;)\s*top\s*:\s*0(?:[a-z%]*)?\s*(?:;|$)", re.IGNORECASE)
POSITIONED = re.compile(r"(?:^|;)\s*position\s*:\s*(fixed|sticky)\s*(?:;|$)", re.IGNORECASE)
COMPENSATION = re.compile(r"(?:^|;)\s*(padding-top|padding|margin-top|margin)\s*:\s*([^;]+)", re.IGNORECASE)


def check_no_scroll_persistent_positioning(html: str) -> tuple[bool, str]:
    """No `position:fixed`/`sticky` header pinned to the top of a scrolling page.

    Generic because this is a SharePoint-preview-sandbox behaviour. docs/01-tenant-
    constraints.md row 26: a header that must stay visible while the rest of the page
    scrolls overlapped the content on every page switch, with `position:sticky` and
    again with `position:fixed` plus a measured `padding-top` on the sibling content.
    What worked was an app shell with no positioning property at all — a non-scrolling
    `<body>` as a 100vh flex column, the header as a plain flex row, and the content
    area as the *sole* `overflow-y:auto` container.

    Two independent signals, both narrow on purpose:

      A. structural — a `position:fixed|sticky; top:0` rule whose height comes from a
         custom property, and some other rule compensating with padding/margin built
         from that same custom property. This is the exact shape row 26 rejected.
      B. by name — a `position:fixed|sticky; top:0` rule whose selector names a header
         (topbar/header/masthead/appbar/navbar).

    What this deliberately does NOT flag, because row 26 did not test it and this repo
    does not assume: `position:sticky` on an element inside a bounded scroll container,
    such as `th` inside `.table-wrap{max-height:26rem;overflow:auto}` in
    templates/single-file-dashboard.html. That shape is closer to row 26's own
    prescribed fix than to the case it rejected, and is an open probe item on #51 —
    not a known defect.

    Known evasion: a header pinned with a literal `top:56px`/`padding-top:56px` and a
    selector named nothing header-like passes both signals. This check encodes a
    measured signature, not a proof of absence. Row 26 was found by a human opening the
    file, and that remains the only way to find the next one.
    """
    rules = _css_rules(html)

    pinned: list[tuple[str, int, set[str]]] = []
    for sel, decls, line in rules:
        if not (POSITIONED.search(";" + decls) and TOP_PINNED.search(";" + decls)):
            continue
        height_vars = {
            var
            for prop, value in re.findall(r"(?:^|;)\s*(min-height|height)\s*:\s*([^;]+)", ";" + decls, re.IGNORECASE)
            for var in CUSTOM_PROP.findall(value)
        }
        pinned.append((sel, line, height_vars))

    if not pinned:
        return True, "no top-pinned fixed/sticky element"

    pinned_vars = {var for _, _, vars_ in pinned for var in vars_}
    compensators = [
        (sel, line)
        for sel, decls, line in rules
        for _prop, value in COMPENSATION.findall(";" + decls)
        if pinned_vars & set(CUSTOM_PROP.findall(value))
    ]

    named = [(sel, line) for sel, line, _ in pinned if HEADER_ISH.search(sel)]

    reasons: list[str] = []
    if compensators:
        pin = next(f"{s} (line {l})" for s, l, v in pinned if v & pinned_vars)
        comp = ", ".join(f"{s} (line {l})" for s, l in compensators[:2])
        reasons.append(f"{pin} is top-pinned and {comp} compensates with padding/margin from the same custom property")
    if named:
        reasons.append("header-named top-pinned rule(s): " + ", ".join(f"{s} (line {l})" for s, l in named[:2]))

    if reasons:
        return False, (
            "; ".join(reasons)
            + ". Both position:sticky and position:fixed overlapped content in "
            "SharePoint's inline preview (docs/01-tenant-constraints.md row 26); use a "
            "non-scrolling 100vh flex shell with one overflow-y:auto content area"
        )
    return True, f"{len(pinned)} top-pinned rule(s), none header-like or compensated"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    add_engines_arg(ap)
    args = ap.parse_args()
    path = pathlib.Path(args.path).resolve()
    if not path.exists():
        print(f"✗ not found: {path}")
        return 2

    html = path.read_text(encoding="utf-8", errors="replace")
    failures: list[str] = []
    warnings: list[str] = []

    print(f"verifying (generic core only) {path.name}")
    print("─" * 60)

    ok, msg = check_self_contained(html)
    print(f"  {'✓' if ok else '✗'} self-contained     {msg}")
    if not ok:
        failures.append(msg)

    level, msg, _ = check_size(path)
    icon = {"ok": "✓", "warn": "⚠", "fail": "✗"}[level]
    print(f"  {icon} size               {msg}")
    if level == "fail":
        failures.append(msg)
    elif level == "warn":
        warnings.append(msg)

    ok, msg = check_no_leftover_placeholders(html)
    print(f"  {'✓' if ok else '✗'} placeholders       {msg}")
    if not ok:
        failures.append(msg)

    ok, msg = check_provenance(html)
    print(f"  {'✓' if ok else '⚠'} provenance         {msg}")
    if not ok:
        warnings.append(msg)

    ok, msg = check_no_stray_script_text(html)
    print(f"  {'✓' if ok else '✗'} no-stray-script    {msg}")
    if not ok:
        failures.append(msg)

    ok, msg = check_no_target_driven_visibility(html)
    print(f"  {'✓' if ok else '✗'} no-target-nav      {msg}")
    if not ok:
        failures.append(msg)

    ok, msg = check_no_scroll_persistent_positioning(html)
    print(f"  {'✓' if ok else '✗'} no-pinned-header   {msg}")
    if not ok:
        failures.append(msg)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        failures.append("playwright not installed — the render and console checks could "
                        "not run, so this file has NOT been verified. Install with: "
                        "uv sync --extra verify && uv run playwright install chromium")
        print("  ✗ render             BLOCKED — playwright not installed, browser checks "
              "could not run")
        return _report(failures, warnings)

    with sync_playwright() as pw:
        for engine in args.engines:
            print(f"  · {engine}")
            mark = len(failures)
            shot = shot_path(path, ".verify-core.png", engine)
            browser = getattr(pw, engine).launch()
            page = browser.new_page(viewport={"width": 1200, "height": 900})
            errors: list[str] = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(path.as_uri())
            page.wait_for_timeout(800)

            if errors:
                failures.append(f"{len(errors)} console error(s): {errors[0][:160]}")
                print(f"  ✗ console            {len(errors)} error(s): {errors[0][:80]}")
            else:
                print("  ✓ console            clean")

            page.screenshot(path=str(shot), full_page=True)
            print(f"  ✓ screenshot         {shot.name}")
            browser.close()
            label_failures(failures, mark, engine, args.engines)

    return _report(failures, warnings, shot_path(path, ".verify-core.png", args.engines[0]))


def _report(failures, warnings, shot=None) -> int:
    print("─" * 60)
    for w in warnings:
        print(f"  warn: {w}")
    if failures:
        print(f"\n✗ FAIL — {len(failures)} blocking issue(s) in the generic core.")
        for f in failures:
            print(f"    • {f}")
        return 1
    print("\n✓ PASS — generic core only. A dashboard also needs tun-verify's"
          " KPI/chart/table/interactivity checks; a non-dashboard artefact needs"
          " whatever its own specialisation defines, if anything.")
    if shot:
        print(f"  Review the screenshot: {shot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
