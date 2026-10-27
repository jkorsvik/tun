#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_row_24_26_checks.py — prove the row-24 and row-26 gates in
tools/verify_standalone_core.py actually gate, and keep gating.

Why this file exists, and why it is larger than the two checks it tests:

Both gates encode a failure that CANNOT be reproduced locally. `:target` navigation
(row 24) and a `position:fixed` header (row 26) both work perfectly from `file://`, and
are broken only in SharePoint's inline file-preview. So there is no render assertion
available, no console error to catch, and no screenshot that looks wrong. A static text
check is the only mechanism that can catch either — which makes the check itself the
single point of failure, and makes "the suite is green" worth exactly nothing on its own.

Three things are therefore asserted for every fixture, not one:

  1. the right gate says NO                — the check under test returns False
  2. with the right reason                 — its message names the row and the mechanism
  3. and no OTHER gate says NO             — so a fixture cannot pass by tripping a
                                             neighbouring check on the way past

Plus a mutation pass at the end: each gate is deleted from a copy of the module source
and every fixture re-run. If a fixture still reports the same verdict with the gate
gone, that fixture was never testing the gate. That check has caught real theatre
before (an plattformen register suite where 9 of 15 gates could be deleted unnoticed), so it
is committed here rather than run once by hand.

Stdlib only, like the rest of the repo.

    python3 tests/test_row_24_26_checks.py
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
MODULE = REPO / "tools" / "verify_standalone_core.py"
sys.path.insert(0, str(REPO / "tools"))

import tree_scan  # noqa: E402
import verify_standalone_core as core  # noqa: E402

passed = failed = 0


def chk(label: str, got, want) -> None:
    global passed, failed
    if got == want:
        print(f"  PASS {label}")
        passed += 1
    else:
        trim = lambda v: (r if len(r := repr(v)) <= 140 else r[:137] + "...")
        print(f"  FAIL {label}: got {trim(got)}, wanted {trim(want)}")
        failed += 1


PROVENANCE = """<!-- PROVENANCE
     Source data: fixture
     Built: 2026-09-19
     Built by: tests/test_row_24_26_checks.py
-->"""


def doc(css: str, body: str = "<p>x</p>") -> str:
    return f"<!doctype html>\n<html lang=\"nb\">{PROVENANCE}<style>\n{css}\n</style>{body}</html>"


# The gate under test, and every other blocking gate in the module. "Fired alone" means
# the first one says False and all of these say True.
OTHER_GATES = {
    "self-contained": lambda h: core.check_self_contained(h)[0],
    "placeholders": lambda h: core.check_no_leftover_placeholders(h)[0],
    "stray-script": lambda h: core.check_no_stray_script_text(h)[0],
    "row24": lambda h: core.check_no_target_driven_visibility(h)[0],
    "row26": lambda h: core.check_no_scroll_persistent_positioning(h)[0],
}


def assert_fires_alone(label: str, html: str, gate: str, must_say: list[str]) -> None:
    """`gate` must reject; its message must contain every string in must_say; and every
    other gate must accept, so the fixture is unambiguous about what it proves."""
    fn = {
        "row24": core.check_no_target_driven_visibility,
        "row26": core.check_no_scroll_persistent_positioning,
    }[gate]
    ok, msg = fn(html)
    chk(f"{label}: {gate} rejects", ok, False)
    for needle in must_say:
        chk(f"{label}: message names {needle!r}", needle in msg, True)
    for name, other in OTHER_GATES.items():
        if name == gate:
            continue
        chk(f"{label}: {name} stays quiet (fired alone)", other(html), True)


def assert_all_clean(label: str, html: str) -> None:
    for name, gate in OTHER_GATES.items():
        chk(f"{label}: {name} accepts", gate(html), True)


# ---------------------------------------------------------------------------
# Row 24 — :target must not control visibility
# ---------------------------------------------------------------------------
print("row 24 — :target-driven visibility")

# The exact shape shipped in examples/13 before #50.
assert_fires_alone(
    "examples/13 shape",
    doc(".page{display:none}\n.page:target{display:block}\n#page-b:target ~ #page-a{display:none}"),
    "row24",
    ["row 24", ":checked"],
)
assert_fires_alone("visibility variant", doc("#a:target{visibility:visible}"), "row24", ["row 24"])
assert_fires_alone("opacity variant", doc("#a:target{opacity:1}"), "row24", ["row 24"])
assert_fires_alone("inside @media", doc("@media (min-width:40em){.p:target{display:block}}"), "row24", ["row 24"])

# Cosmetic :target is not a navigation mechanism and must stay legal, or the gate starts
# forbidding things row 24 never measured.
assert_all_clean("cosmetic :target (colour only)", doc("#a:target{color:red;outline:2px solid}"))
assert_all_clean("cosmetic :target (scroll-margin)", doc("#a:target{scroll-margin-top:4rem}"))

# Prose about the mechanism is not the mechanism — the row-25 docstring's own lesson,
# one level down. A CSS comment describing the unsafe rule must not trip the gate.
assert_all_clean("comment describing a :target rule", doc("/* .page:target{display:none} — unsafe, row 24 */\n.x{color:red}"))
assert_all_clean("comment inside a block", doc(".x{color:red /* :target;display:none */}"))

# ---------------------------------------------------------------------------
# Row 26 — no scroll-persistent pinned header
# ---------------------------------------------------------------------------
print("\nrow 26 — scroll-persistent positioning")

# Signal A: structural. Pinned element sized by a custom property, content compensating
# with padding built from the same property. This is examples/09/10/13's exact shape.
assert_fires_alone(
    "structural (var-linked compensation)",
    doc("#bar{position:fixed;top:0;min-height:var(--h)}\n#below{padding-top:calc(var(--h) + 1rem)}"),
    "row26",
    ["row 26", "flex"],
)
assert_fires_alone(
    "structural via padding shorthand",
    doc("#bar{position:fixed;top:0;min-height:var(--h)}\nmain{padding:calc(var(--h) + 1rem) 1rem 1rem}"),
    "row26",
    ["row 26"],
)
# Signal B: by name, even with no compensation anywhere.
assert_fires_alone("named #topbar", doc("#topbar{position:fixed;top:0}"), "row26", ["row 26"])
assert_fires_alone("named .site-header", doc(".site-header{position:sticky;top:0}"), "row26", ["row 26"])

# The carve-out that matters: sticky inside a bounded scroll container is row 26's own
# prescribed shape, not the case it rejected. templates/single-file-dashboard.html:136
# depends on this staying legal; it is an open probe item on #51, not a known defect.
assert_all_clean(
    "sticky th inside a bounded scroll container",
    doc(".table-wrap{max-height:26rem;overflow:auto}\nth{position:sticky;top:0;background:#fff}"),
)
assert_all_clean("fixed tooltip (not top-pinned)", doc(".tooltip{position:fixed;opacity:0}"))
assert_all_clean("fixed control at an offset", doc(".toggle{position:fixed;top:9px;right:9px}"))
assert_all_clean("comment describing a pinned header", doc("/* #topbar{position:fixed;top:0} was wrong */\n.x{color:red}"))

# ---------------------------------------------------------------------------
# The real tree — the set of offenders must be EXACTLY the known list
# ---------------------------------------------------------------------------
# Asserted as an exact set, not "no failures", for two reasons. It documents the debt
# while it is being paid down, commit by commit, so history shows the list emptying. And
# it fails on a NEW offender as loudly as on a regression in an old one, which "assert
# empty" would only do once the list reached empty.
#
# #50 named three files. The gate found a fourth (examples/07). That is the whole
# argument for having a gate rather than a careful reading.
print("\nthe real tree")

# Scope and the accepted-failure list both live in tools/tree_scan.py, because
# tools/check_tree.py runs the same gates in CI and in the pre-commit hook. When the list
# lived here as well, the two copies were free to disagree, and one of them did: this file
# said "five shipped files" in prose while listing seven, and that stale number was
# repeated into a GitHub comment before anyone re-ran the check. A count next to a list is
# derivable data stored twice. So no number is written down here any more — the list in
# tree_scan.KNOWN_DEBT is the only statement of it, and this suite asserts reality matches.
#
# What each entry means:
#   target-nav / pinned-header (rows 24, 26) are empty, and must stay empty. All four
#   files #50 found were converted on the same branch: examples/13 moved from :target to a
#   radio group, and examples/07/09/10/13 all moved to the row-26 flex shell.
#
#   stray-script (row 25) is NOT empty, and that is the point. The check has existed for a
#   while and nothing ran it across the tree, so violations accumulated unseen — the same
#   failure #50 is about, one more time. Each needs its own prose rewritten to stop writing
#   the literal characters. Tracked as debt, not fixed here. See #45.
tree_files, tree_failing = tree_scan.scan()
print(f"  scanning {len(tree_files)} tracked .html file(s)")

for name in ("target-nav", "pinned-header", "stray-script"):
    row = tree_scan.CHECKS[name][2]
    chk(f"{name} offenders are exactly the declared list ({row})",
        tree_failing[name], tree_scan.KNOWN_DEBT[name])

# The gates above share their scope with the thing they are testing, so the scope itself
# needs an assertion that does not go through tree_scan.scan(). An empty scope is the
# failure that makes every check above pass vacuously.
chk("scope is non-empty", bool(tree_files), True)
chk("scope is tracked files only — no gitignored build output",
    [f for f in tree_files if f.startswith(("work/", "dashboards/"))], [])

with tempfile.TemporaryDirectory() as tmp:
    # Scrub GIT_* here too: `git init` with GIT_DIR inherited from a hook initialises the
    # wrong thing. This assertion is the one that caught the leak in the first place.
    subprocess.run(["git", "init", "-q", tmp], check=True, env=tree_scan.clean_env())
    try:
        tree_scan.tracked_html(pathlib.Path(tmp))
        got = "returned normally"
    except tree_scan.ScopeError:
        got = "raised ScopeError"
    chk("an empty scope raises rather than reporting a clean tree", got,
        "raised ScopeError")

# The scope must be independent of whatever git environment the caller had. A pre-commit
# hook is exactly such a caller.
_leaky = dict(os.environ)
os.environ["GIT_DIR"] = str(REPO / ".git")
os.environ["GIT_INDEX_FILE"] = str(REPO / ".git" / "index")
try:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True, env=tree_scan.clean_env())
        try:
            tree_scan.tracked_html(pathlib.Path(tmp))
            got = "returned normally"
        except tree_scan.ScopeError:
            got = "raised ScopeError"
    chk("scope ignores an inherited GIT_DIR (the pre-commit hook case)", got,
        "raised ScopeError")
finally:
    os.environ.clear()
    os.environ.update(_leaky)

# templates/ ship {{TOKEN}} placeholders by design. That is expressed as scope, not as a
# debt entry, so a new template does not have to be allowlisted to be legal.
chk("the placeholder check skips templates/",
    tree_scan.placeholders_applies("templates/single-file-dashboard.html"), False)
chk("the placeholder check still applies to examples/",
    tree_scan.placeholders_applies("examples/01-hello-dashboard/salg-dashboard.html"), True)
# An example's own template is still a template. This shape was missing, so an
# example template failed a check it is definitionally exempt from, and the only
# way out looked like a debt entry.
chk("the placeholder check skips an example's own *.template.html",
    tree_scan.placeholders_applies(
        "examples/17-multi-regime-day-board/oversikt.template.html"), False)
chk("the exemption is the *.template.html suffix, not the word 'template'",
    tree_scan.placeholders_applies("examples/09-x/template-notes.html"), True)
chk("a built artefact beside a template is still checked",
    tree_scan.placeholders_applies(
        "examples/17-multi-regime-day-board/oversikt.html"), True)

# ---------------------------------------------------------------------------
# Mutation pass — delete each gate, confirm the fixtures notice
# ---------------------------------------------------------------------------
print("\nmutation pass — delete each gate, the suite must notice")

SOURCE = MODULE.read_text(encoding="utf-8")


def without_gate(name: str) -> object:
    """Return the module with `name`'s rejection path removed (every `return False` in
    that function becomes `return True`), exec'd into a fresh namespace."""
    start = SOURCE.index(f"def {name}(")
    rest = SOURCE[start:]
    end_rel = re.search(r"\n(?=\w|@)", rest[rest.index("\n"):])
    end = start + rest.index("\n") + (end_rel.start() if end_rel else len(rest))
    body = SOURCE[start:end]
    mutated = body.replace("return False, (", 'return True, ("MUTANT" or ').replace(
        "return False, ", 'return True, "MUTANT: '
    )
    if mutated == body:
        raise AssertionError(f"mutation produced no change in {name} — harness is broken")
    ns: dict = {}
    exec(SOURCE[:start] + mutated + SOURCE[end:], ns)  # noqa: S102 — test harness
    return ns


MUTATION_FIXTURES = {
    "check_no_target_driven_visibility": (
        doc(".page:target{display:block}"),
        "check_no_target_driven_visibility",
    ),
    "check_no_scroll_persistent_positioning": (
        doc("#topbar{position:fixed;top:0}"),
        "check_no_scroll_persistent_positioning",
    ),
}

for gate, (fixture_html, fn_name) in MUTATION_FIXTURES.items():
    # Sanity: the live gate rejects this fixture.
    live = getattr(core, fn_name)(fixture_html)[0]
    chk(f"{gate}: live gate rejects its fixture", live, False)
    # With the gate deleted, the same fixture must come back clean — proving the
    # fixture's verdict came from this gate and nothing else.
    mutant = without_gate(gate)
    chk(f"{gate}: deleting it makes the fixture pass (gate was load-bearing)",
        mutant[fn_name](fixture_html)[0], True)

print("─" * 66)
print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
