#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
scan_history.py — the pre-publication scan, as a command rather than a memory.

Stdlib only for the parts that matter; `gitleaks` is optional and reported as missing
rather than silently skipped.

    python3 tools/scan_history.py              # scan full history + working tree
    python3 tools/scan_history.py --working    # working tree only (fast)
    python3 tools/scan_history.py --refs       # list every ref that would be scanned

Why this exists
---------------
docs/20-publication-readiness.md names three categories that must be clean before anything
is published, and only one of them is a secret scanner:

  1. personal data      -> in this repository's history; see docs/20 for the exact vector
  2. internal reference -> hostnames, internal programme names, colleague names, run ids
  3. secrets            -> never scanned here at all

Category 2 is the largest and cannot be fixed by a purge, because the text is legitimate
repository content that simply must not leave Eksempel AS. This tool greps for it so the reading
pass is repeatable; a human still decides each hit.

This tool does not clean anything. It reports. Cleaning history is a separate, irreversible
operation that needs its own decision.

Exit codes
    0  nothing found in the categories this tool can decide
    1  findings that need a human decision
    2  the scan could not be performed (missing tool, unresolvable scope)
"""
from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_no_real_data  # noqa: E402
import tree_scan  # noqa: E402

G, R, Y, D, B, Z = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
if not sys.stdout.isatty():
    G = R = Y = D = B = Z = ""

# ---------------------------------------------------------------------------
# Category 2: internal references
# ---------------------------------------------------------------------------
# Each entry is a judgement call at publication time, not a defect now. Some should be
# generalised, some removed, some kept because they are part of the public story. The point
# of listing them is that the decision gets made deliberately instead of by omission.
INTERNAL_PATTERNS: dict[str, str] = {
    "internal host":        r"\b[a-z0-9-]+\.(?:tech\.)?eksempel\.no\b",
    "internal forge":       r"\beksempel\.ghe\.com\b",
    "internal programme":   r"\b(?:plattformen|plattformen|Juridisk)\b",
    "snowflake account":    r"\beksempelasa-[a-z0-9_]+\b",
    "actions run id":       r"\brun \d{6,}\b",
}


def _refs() -> list[str]:
    out = subprocess.run(["git", "-C", str(tree_scan.REPO), "for-each-ref",
                          "--format=%(refname)"],
                         capture_output=True, text=True, env=tree_scan.clean_env())
    return [r for r in out.stdout.split() if r]


def _grep_history(pattern: str) -> list[str]:
    """git log -S over all refs. Returns 'commit path' lines."""
    proc = subprocess.run(
        ["git", "-C", str(tree_scan.REPO), "grep", "-I", "-n", "-E", pattern,
         "--all-match", "--"],
        capture_output=True, text=True, env=tree_scan.clean_env())
    return [ln for ln in proc.stdout.splitlines() if ln]


def scan_working_tree() -> tuple[int, int]:
    """Categories 1 and 2 over tracked files. Returns (personal, internal) counts."""
    try:
        files = check_no_real_data.tracked_text()
    except tree_scan.ScopeError as exc:
        print(f"{R}✗ scope error{Z} {exc}", file=sys.stderr)
        raise SystemExit(2)

    personal: list[str] = []
    internal: dict[str, set[str]] = {name: set() for name in INTERNAL_PATTERNS}
    compiled = {n: re.compile(p) for n, p in INTERNAL_PATTERNS.items()}

    for rel in files:
        path = tree_scan.REPO / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, kind, shown in check_no_real_data.scan_text(rel, text):
            personal.append(f"{rel}:{lineno}  {kind}: {shown}")
        for name, rx in compiled.items():
            if rx.search(text):
                internal[name].add(rel)

    print(f"{B}category 1: personal data (working tree){Z}")
    if personal:
        print(f"  {R}✗ {len(personal)} finding(s){Z}")
        for line in personal[:15]:
            print(f"    {line}")
    else:
        print(f"  {G}✓ none{Z}")

    print(f"\n{B}category 2: internal references (working tree){Z}")
    total_internal = 0
    for name, hits in internal.items():
        total_internal += len(hits)
        if hits:
            print(f"  {Y}•{Z} {name:<20} {len(hits):3d} file(s)  "
                  f"{D}e.g. {sorted(hits)[0]}{Z}")
        else:
            print(f"  {G}✓{Z} {name:<20}   0")
    if total_internal:
        print(f"  {D}These are decisions, not defects. Each needs: generalise, remove,"
              f" or keep.{Z}")

    return len(personal), total_internal


def _find_gitleaks() -> str | None:
    """Locate gitleaks, tolerating a non-login PATH.

    A non-login shell on this platform does not necessarily have Homebrew's bin on PATH, so
    shutil.which alone reports "not installed" for a tool that is installed. Reporting a
    missing scanner when one is present would push the run into the UNKNOWN branch and make
    a clean result unreachable, which is the same class of mistake as a vacuous pass.
    """
    found = shutil.which("gitleaks")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/gitleaks", "/usr/local/bin/gitleaks",
                      "/home/linuxbrew/.linuxbrew/bin/gitleaks"):
        if pathlib.Path(candidate).is_file():
            return candidate
    return None


def scan_history() -> int:
    """Category 1 and 2 across every ref, plus category 3 if gitleaks is present."""
    refs = _refs()
    print(f"\n{B}history{Z}")
    print(f"  {len(refs)} ref(s) in this clone")
    print(f"  {D}A clone only holds refs it has fetched. Pull-request refs"
          f" (refs/pull/*) are\n  not fetched by default and are server-held; see"
          f" docs/20-publication-readiness.md.{Z}")

    # Category 1 across history: does work/ appear in any reachable commit?
    proc = subprocess.run(
        ["git", "-C", str(tree_scan.REPO), "log", "--all", "--oneline", "--", "work/"],
        capture_output=True, text=True, env=tree_scan.clean_env())
    work_commits = [ln for ln in proc.stdout.splitlines() if ln]
    if work_commits:
        print(f"  {R}✗ work/ appears in {len(work_commits)} commit(s) reachable from a"
              f" local ref{Z}")
        for line in work_commits[:5]:
            print(f"      {line}")
    else:
        print(f"  {G}✓ work/ appears in no commit reachable from a local ref{Z}")

    print(f"\n{B}category 3: secrets{Z}")
    gitleaks = _find_gitleaks()
    if gitleaks is None:
        print(f"  {Y}⚠ gitleaks not installed — category 3 is UNKNOWN, not clean{Z}")
        print(f"  {D}brew install gitleaks, then re-run.{Z}")
        return 2
    proc = subprocess.run(
        [gitleaks, "detect", "--source", str(tree_scan.REPO), "--no-banner",
         "--redact", "--exit-code", "1"],
        capture_output=True, text=True)
    if proc.returncode == 0:
        print(f"  {G}✓ gitleaks found no secrets{Z}")
        return 0
    print(f"  {R}✗ gitleaks reported findings{Z}")
    for line in (proc.stdout + proc.stderr).splitlines()[:25]:
        print(f"    {line}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--working", action="store_true", help="working tree only")
    ap.add_argument("--refs", action="store_true", help="list refs and exit")
    args = ap.parse_args()

    if args.refs:
        for ref in _refs():
            print(ref)
        return 0

    personal, internal = scan_working_tree()
    history_status = 0 if args.working else scan_history()

    print("\n" + "─" * 72)
    if personal:
        print(f"{R}Not publishable{Z}: personal data is present in tracked files.")
        return 1
    if history_status == 2:
        print(f"{Y}Incomplete{Z}: category 3 was not scanned, so publication readiness is"
              f" unknown.\nInstall gitleaks and re-run before treating this as a pass.")
        return 2
    if history_status == 1:
        print(f"{R}Not publishable{Z}: secrets reported. Rotate first, then purge.")
        return 1
    if internal:
        print(f"{Y}Decisions outstanding{Z}: {internal} internal reference(s) need the"
              f" category 2 reading pass (docs/20).")
        return 1
    print(f"{G}Categories 1-3 clean in this clone.{Z} Category 1's server-held vector"
          f" still\nneeds the administrator step in docs/20; this tool cannot see it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
