#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Tún authors
"""Every row in docs/findings-index.md must point to a file that still holds its anchor.

Run: python3 tests/test_findings_index.py
Fails loudly on zero rows, so a broken parser cannot pass vacuously.
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "docs" / "findings-index.md"
ROW = re.compile(r"^\| (F\d{3}(?: F\d{3})*) \| (.+?) \| \[`[^`]+`\]\(([^)]+)\) \| (``? .+? ``?|`[^`]+`) \|$")


def anchor_text(cell: str) -> str:
    cell = cell.strip()
    if cell.startswith("`` "):
        return cell[3:-3]
    return cell[1:-1]


def check(index_text: str, root: pathlib.Path) -> tuple[int, list[str]]:
    rows, errs, seen = 0, [], set()
    for n, line in enumerate(index_text.splitlines(), 1):
        if not line.startswith("| F"):
            continue
        m = ROW.match(line)
        if not m:
            errs.append(f"line {n}: row does not parse")
            continue
        rows += 1
        ids, _, home, cell = m.groups()
        for i in ids.split():
            if i in seen:
                errs.append(f"line {n}: {i} listed twice")
            seen.add(i)
        target = (root / "docs" / home).resolve()
        if not target.is_file():
            errs.append(f"line {n}: {home} does not exist")
            continue
        if anchor_text(cell) not in target.read_text(encoding="utf-8"):
            errs.append(f"line {n}: anchor not found in {home}: {anchor_text(cell)!r}")
    if rows == 0:
        errs.append("no rows parsed: the index or the parser is broken")
    return rows, errs


def main() -> int:
    rows, errs = check(INDEX.read_text(encoding="utf-8"), ROOT)
    # Mutation controls: the check must notice a missing anchor and a missing file.
    good = INDEX.read_text(encoding="utf-8")
    first = next(l for l in good.splitlines() if l.startswith("| F"))
    broken_anchor = good.replace(first, first.rsplit("|", 2)[0] + "| `zz-no-such-anchor-zz` |", 1)
    broken_file = re.sub(r"\]\(([^)]+)\)", "](no-such-file.md)", good, count=1)
    ctl = [("missing anchor", broken_anchor), ("missing file", broken_file), ("empty index", "# nothing\n")]
    for name, text in ctl:
        _, e = check(text, ROOT)
        if not e:
            errs.append(f"mutation control '{name}' was NOT caught")
    print(f"checked {rows} index rows, {len(ctl)} mutation controls")
    for e in errs:
        print("  ✗", e)
    print("✓ PASS" if not errs else f"✗ FAIL: {len(errs)} problem(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
