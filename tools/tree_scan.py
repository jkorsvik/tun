#!/usr/bin/env python3
"""
tree_scan.py — resolve which files the tree-wide gates apply to, and what is known debt.

Stdlib only, like the rest of tools/. Imported by both tools/check_tree.py (the gate CI
and the pre-commit hook run) and tests/test_row_24_26_checks.py, so the gate and the
tests cannot disagree about scope or about which failures are already accepted.

Why this file exists
--------------------
Rows 24 and 26 of docs/01-tenant-constraints.md were measured, written down, and then
broken by four shipped files (#50). The checks that would have caught them existed in
tools/verify_standalone_core.py the whole time. Nothing ran them over the tree. A check
nobody runs is not a gate, and a gate that computes its own scope can pass *vacuously* —
which is worse than failing, because it manufactures assurance. So:

  * scope is git-tracked files, never a filesystem walk (rglob picked up gitignored build
    output under dashboards/ and work/, so the result depended on what the developer
    happened to have built locally);
  * scope is reported, not assumed — callers print the resolved count;
  * an empty scope is an error, never a pass.
"""
from __future__ import annotations

import os
import pathlib
import subprocess

REPO = pathlib.Path(__file__).resolve().parent.parent


def clean_env() -> dict:
    """Return os.environ without the GIT_* variables.

    Git hooks run with GIT_DIR and GIT_INDEX_FILE exported. Those override `git -C <path>`
    entirely, so a subprocess aimed at some other directory silently answers about the
    outer repository instead. That is not theoretical: the suite's own "an empty scope
    raises" assertion passed in a shell and failed inside the pre-commit hook, because
    `git -C <empty repo> ls-files` returned 18 paths belonging to this repo. Any gate that
    shells out to git from a hook has to scrub these, or its scope is whatever git was
    already pointed at.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


class ScopeError(RuntimeError):
    """Raised when the set of files to check cannot be resolved, or resolves to nothing.

    Never downgrade this to "nothing to do". An empty file list means the scope is
    broken, not that the tree is clean.
    """


def tracked_paths(repo: pathlib.Path = REPO, pattern: str | None = None) -> list[str]:
    """Return every git-tracked path, repo-relative, sorted.

    `pattern` is an optional git pathspec, for example "*.html". Raises ScopeError if git
    cannot be consulted or the list is empty, because an empty scope means the scope is
    broken rather than the tree being clean.
    """
    cmd = ["git", "-C", str(repo), "ls-files", "-z"]
    if pattern:
        cmd += ["--", pattern]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True,
                              env=clean_env())
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ScopeError(f"could not list tracked files via git: {exc}") from exc
    files = sorted(p for p in proc.stdout.split("\0") if p)
    if not files:
        raise ScopeError(
            f"resolved zero tracked files{f' matching {pattern}' if pattern else ''}"
            " — the scope is broken, not clean")
    return files


def tracked_html(repo: pathlib.Path = REPO) -> list[str]:
    """Return every git-tracked .html path, repo-relative, sorted."""
    return tracked_paths(repo, "*.html")


# ---------------------------------------------------------------------------
# Which checks apply to which files
# ---------------------------------------------------------------------------
# Templates ship {{TOKEN}} placeholders on purpose — that is what makes them
# templates. This is a design fact, not debt, so it is expressed as scope rather
# than as an allowlist: a new template must not have to be added to a debt list
# to be legal.
#
# Two shapes count as a template, because the repo uses both:
#   * anything under templates/          — the shared, reusable ones
#   * any *.template.html                — a template belonging to one example,
#                                          which lives beside the builder that
#                                          consumes it
# The second was missing, and an example's own template therefore failed a check
# it is definitionally exempt from. Naming the convention here keeps the debt
# list for real debt.
def placeholders_applies(rel: str) -> bool:
    if rel.startswith("templates/"):
        return False
    return not rel.endswith(".template.html")


def always(rel: str) -> bool:
    return True


# name -> (check function attribute on verify_standalone_core, scope predicate, doc row)
CHECKS: dict[str, tuple[str, object, str]] = {
    "self-contained": ("check_self_contained", always, "no external refs"),
    "placeholders":   ("check_no_leftover_placeholders", placeholders_applies, "no {{TOKEN}} left"),
    "stray-script":   ("check_no_stray_script_text", always, "row 25"),
    "target-nav":     ("check_no_target_driven_visibility", always, "row 24"),
    "pinned-header":  ("check_no_scroll_persistent_positioning", always, "row 26"),
}

# ---------------------------------------------------------------------------
# Known debt — the exact set of files already failing a check when the gate landed
# ---------------------------------------------------------------------------
# An exact set, not a "max N failures" budget. Two directions both fail the gate:
#   * a file failing a check that is not listed here  -> a new regression
#   * a file listed here that now passes              -> stale debt, delete the entry
# The second half matters as much as the first. A debt list nobody prunes silently
# becomes a permanent exemption, and then the gate is off for those paths forever.
#
# Row 25 (check_no_stray_script_text) is the live example of the very pattern #50 is
# about: the check existed for a while and nothing ran it over the tree, so five files
# accumulated debt unseen. Paid off in #45: the templates and generators stopped writing
# the literal tag in prose, and the five artefacts were rebuilt. Keep it empty.
KNOWN_DEBT: dict[str, set[str]] = {
    "self-contained": set(),
    "placeholders": set(),
    "stray-script": set(),
    "target-nav": set(),
    "pinned-header": set(),
}


def load_core():
    """Import tools/verify_standalone_core.py by path, without needing a package."""
    import importlib.util
    path = REPO / "tools" / "verify_standalone_core.py"
    spec = importlib.util.spec_from_file_location("verify_standalone_core", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ScopeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scan(repo: pathlib.Path = REPO) -> tuple[list[str], dict[str, set[str]]]:
    """Run every tree-wide check over every in-scope tracked file.

    Returns (files_checked, {check_name: set_of_failing_paths}).
    """
    core = load_core()
    files = tracked_html(repo)
    failing: dict[str, set[str]] = {name: set() for name in CHECKS}
    for rel in files:
        path = repo / rel
        if not path.exists():
            # Tracked but absent: a broken checkout or a mid-rebase state. Refuse to
            # quietly treat it as clean.
            raise ScopeError(f"tracked file is missing from the working tree: {rel}")
        html = path.read_text(encoding="utf-8", errors="replace")
        for name, (attr, applies, _row) in CHECKS.items():
            if not applies(rel):
                continue
            if not getattr(core, attr)(html)[0]:
                failing[name].add(rel)
    return files, failing


def diff_against_debt(
    failing: dict[str, set[str]],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Return (regressions, stale_debt) by comparing a scan to KNOWN_DEBT."""
    regressions = {n: failing[n] - KNOWN_DEBT.get(n, set()) for n in failing}
    stale = {n: KNOWN_DEBT.get(n, set()) - failing[n] for n in failing}
    return ({n: v for n, v in regressions.items() if v},
            {n: v for n, v in stale.items() if v})
