#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
check_tree.py — run the tenant-constraint gates over every tracked .html in the repo.

Stdlib only. No browser, no install, runs anywhere Python 3.9+ runs.

    python3 tools/check_tree.py            # check, print a table, exit 1 on regression
    python3 tools/check_tree.py --quiet    # only print problems (for the git hook)
    python3 tools/check_tree.py --list     # print the resolved scope and exit

This is the piece that was missing when four shipped files broke rows 24 and 26. The checks in
tools/verify_standalone_core.py already existed; they only ever ran against one file a
human chose to point them at, so four shipped files broke rows 24 and 26 unnoticed. This
runs them across the whole tree, in CI and in a pre-commit hook.

Exit codes
    0  no regressions (known debt may still be present, and is reported)
    1  a regression, or stale debt that should be pruned
    2  the scope could not be resolved — treated as a failure, never as "nothing to do"
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_no_real_data  # noqa: E402
import tree_scan  # noqa: E402

G, R, Y, D, B, Z = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
if not sys.stdout.isatty():
    G = R = Y = D = B = Z = ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quiet", action="store_true",
                    help="print only problems and the one-line summary")
    ap.add_argument("--list", action="store_true",
                    help="print the resolved file scope and exit")
    args = ap.parse_args()

    try:
        if args.list:
            for rel in tree_scan.tracked_html():
                print(rel)
            return 0
        files, failing = tree_scan.scan()
    except tree_scan.ScopeError as exc:
        # Deliberately exit non-zero. An unresolvable or empty scope is the failure mode
        # that makes a gate pass vacuously, so it must never look like success.
        print(f"{R}✗ scope error{Z} {exc}", file=sys.stderr)
        return 2

    regressions, stale = tree_scan.diff_against_debt(failing)

    # Real and personal data is a tree-wide gate too, so it belongs in the same run rather
    # than in a second command people have to remember. tools/check_no_real_data.py stays
    # runnable on its own for the detailed, redacted report.
    try:
        data_text_files = check_no_real_data.tracked_text()
        all_tracked = tree_scan.tracked_paths()
    except tree_scan.ScopeError as exc:
        print(f"{R}✗ scope error{Z} {exc}", file=sys.stderr)
        return 2
    shape_hits: list[tuple[str, int, str, str]] = []
    for rel in data_text_files:
        path = tree_scan.REPO / rel
        if not path.exists():
            continue
        for lineno, kind, shown in check_no_real_data.scan_text(
                rel, path.read_text(encoding="utf-8", errors="replace")):
            shape_hits.append((rel, lineno, kind, shown))
    location_hits = [
        rel for rel in all_tracked
        if pathlib.Path(rel).suffix.lower() in check_no_real_data.DATA_SUFFIXES
        and not check_no_real_data.data_file_is_allowed(rel)
    ]

    if not args.quiet:
        print(f"{B}tenant-constraint gates over the tracked tree{Z}")
        print(f"  scope: {len(files)} tracked .html file(s)")
        print("─" * 72)
        width = max(len(n) for n in tree_scan.CHECKS)
        for name, (_attr, applies, row) in tree_scan.CHECKS.items():
            in_scope = [f for f in files if applies(f)]
            bad = failing[name]
            debt = bad & tree_scan.KNOWN_DEBT.get(name, set())
            new = bad - debt
            if new:
                icon, colour, note = "✗", R, f"{len(new)} NEW"
            elif debt:
                icon, colour, note = "•", Y, f"{len(debt)} known debt"
            else:
                icon, colour, note = "✓", G, "clean"
            print(f"  {colour}{icon}{Z} {name:<{width}}  {D}{row:<16}{Z}"
                  f" {len(in_scope):2d} checked  {colour}{note}{Z}")
        icon, colour, note = (("✗", R, f"{len(shape_hits)} finding(s)") if shape_hits
                              else ("✓", G, "clean"))
        print(f"  {colour}{icon}{Z} {'personal-data':<{width}}  {D}{'shapes':<16}{Z}"
              f" {len(data_text_files):2d} checked  {colour}{note}{Z}")
        icon, colour, note = (("✗", R, f"{len(location_hits)} unexpected") if location_hits
                              else ("✓", G, f"{len(check_no_real_data.ALLOWED_DATA)} allowed"))
        print(f"  {colour}{icon}{Z} {'data-files':<{width}}  {D}{'locations':<16}{Z}"
              f" {len(all_tracked):2d} checked  {colour}{note}{Z}")
        print("─" * 72)

    if regressions:
        print(f"\n{R}✗ FAIL{Z} — {sum(len(v) for v in regressions.values())}"
              " new violation(s):")
        for name, paths in regressions.items():
            row = tree_scan.CHECKS[name][2]
            print(f"\n  {B}{name}{Z} ({row})")
            for p in sorted(paths):
                print(f"    • {p}")
        print(f"\n  Fix the file, or — if it is genuinely accepted debt — add it to"
              f" KNOWN_DEBT\n  in tools/tree_scan.py with a reason and an issue"
              f" reference.")

    if stale:
        print(f"\n{Y}✗ FAIL{Z} — known debt that now passes. Prune it, or the gate stays"
              " off\n  for these paths forever:")
        for name, paths in stale.items():
            print(f"\n  {B}{name}{Z}")
            for p in sorted(paths):
                print(f"    • {p}  {D}(remove from KNOWN_DEBT in tools/tree_scan.py){Z}")

    if shape_hits or location_hits:
        print(f"\n{R}✗ FAIL{Z} — real or personal data in tracked files."
              f"\n  Run 'python3 tools/check_no_real_data.py' for the redacted detail.")
        for rel, lineno, kind, shown in shape_hits[:10]:
            print(f"    {rel}:{lineno}  {kind}: {shown}")
        for rel in location_hits[:10]:
            print(f"    {rel}  (data file outside an expected location)")

    # The core/plugin boundary is its own tool because it carries a baseline file, but it
    # runs from here so there is still one command to remember. See docs/22-plugin-contract.md.
    boundary = subprocess.run(
        [sys.executable, str(pathlib.Path(__file__).with_name("check_core_is_generic.py")),
         "--quiet"], capture_output=True, text=True, env=tree_scan.clean_env())
    if boundary.returncode != 0:
        print(f"\n{R}✗ FAIL{Z} — core/plugin boundary:")
        for line in (boundary.stdout + boundary.stderr).splitlines():
            if line.strip():
                print(f"  {line}")

    if regressions or stale or shape_hits or location_hits or boundary.returncode != 0:
        return 1

    total_debt = sum(len(v) for v in tree_scan.KNOWN_DEBT.values())
    if total_debt:
        print(f"\n{G}✓ PASS{Z} — no new violations across {len(files)} tracked file(s)."
              f"\n  {Y}{total_debt} known violation(s) remain{Z}, listed in"
              f" tools/tree_scan.py.")
    else:
        print(f"\n{G}✓ PASS{Z} — {len(files)} tracked file(s) clean, no known debt left.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
