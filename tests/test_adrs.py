#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Every Architecture Decision Record is indexed, structured, and verifiable.

ADRs rot in two predictable ways: a new record is written without adding it to the index
(so nobody finds it), or a record omits its Enforcement section (so the decision turns into
folklore that drifts from the code). This stdlib-only gate checks both and includes a
mutation control so it cannot pass vacuously.

    python3 tests/test_adrs.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
ADR_DIR = ROOT / "docs" / "adr"
INDEX = ADR_DIR / "README.md"
TEMPLATE = ADR_DIR / "0000-template.md"
REQUIRED_SECTIONS = ("## Context", "## Decision", "## Consequences", "## Enforcement")
ADR_NAME = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")

CHECKS = 0
FAILED: list[str] = []


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'✓' if ok else '✗'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILED.append(what)


def check_adr_tree(adr_files: list[pathlib.Path], index_text: str) -> list[str]:
    problems: list[str] = []
    if not adr_files:
        return ["no numbered ADR files found"]
    for path in adr_files:
        if path.name not in index_text:
            problems.append(f"{path.name} is not listed in docs/adr/README.md")
        text = path.read_text(encoding="utf-8")
        if not re.search(r"^\- \*\*Status:\*\*\s*(Proposed|Accepted|Superseded by \d{4})\b", text, re.M):
            problems.append(f"{path.name} is missing a valid Status line")
        for heading in REQUIRED_SECTIONS:
            if heading not in text:
                problems.append(f"{path.name} is missing {heading}")
    return problems


def main() -> int:
    chk(ADR_DIR.is_dir(), "docs/adr/ exists")
    chk(INDEX.is_file(), "docs/adr/README.md exists")
    chk(TEMPLATE.is_file(), "docs/adr/0000-template.md exists")

    adrs = sorted(p for p in ADR_DIR.glob("*.md")
                  if ADR_NAME.match(p.name) and p.name != TEMPLATE.name)
    chk(len(adrs) >= 5, "numbered ADRs were found", f"{len(adrs)} file(s)")

    index_text = INDEX.read_text(encoding="utf-8")
    problems = check_adr_tree(adrs, index_text)
    chk(not problems, "every ADR is indexed and has Status, Context, Decision, Consequences, Enforcement",
        "; ".join(problems[:4]))

    # Reachability: AGENTS.md, CONTRIBUTING.md and docs/index.md point at docs/adr/README.md.
    for rel in ("AGENTS.md", "CONTRIBUTING.md", "docs/index.md"):
        body = (ROOT / rel).read_text(encoding="utf-8")
        chk("adr/README.md" in body, f"{rel} links to docs/adr/README.md")

    # Mutation controls: dropping a row from the index or passing an empty list must fail.
    victim = adrs[0].name
    dropped = check_adr_tree(adrs, index_text.replace(victim, "0000-removed.md"))
    chk(any(victim in p for p in dropped), "mutation: removing an ADR from the index is caught")
    chk(bool(check_adr_tree([], index_text)), "mutation: an empty ADR directory fails")

    print()
    if FAILED:
        print(f"FAIL: {len(FAILED)} of {CHECKS} checks failed")
        return 1
    print(f"PASS: {CHECKS} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
