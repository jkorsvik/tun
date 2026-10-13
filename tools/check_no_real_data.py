#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
check_no_real_data.py — refuse to commit real data or personal data.

Stdlib only. No browser, no install.

    python3 tools/check_no_real_data.py           # scan tracked files
    python3 tools/check_no_real_data.py --list    # print the resolved scope and exit

Why this exists
---------------
Working a real case inside a toolkit repository is useful and dangerous: one `git add -A`
in a shared checkout is enough to put a survey export with names and e-mail addresses on
main. A history rewrite does not fully undo that, because a server-held pull-request ref
can keep serving the files, and nothing in a clone can delete it. Prevention is the only
cheap fix.

`.gitignore` alone is not enough, because a directory tends to be ignored only *after* it
leaks. This is the check that does not depend on remembering.

Two independent rules, because they fail differently:

  1. Shape:    text that looks like personal data anywhere in a tracked file.
  2. Location: a data file tracked outside a place where synthetic data is expected.

Rule 2 is the one that catches a real export with an innocent shape. Rule 1 is the one that
catches a contact address pasted into prose.

Findings are reported redacted. A gate that prints the personal data it found has moved the
problem into the log rather than solved it.

Exit codes
    0  nothing found
    1  at least one finding
    2  the scope could not be resolved, or resolved empty (never reported as clean)
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tree_scan  # noqa: E402

G, R, Y, D, B, Z = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
if not sys.stdout.isatty():
    G = R = Y = D = B = Z = ""

# Binary or generated formats where a text scan means nothing.
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".mov", ".xlsx", ".xls",
}

# ---------------------------------------------------------------------------
# Rule 2: where a tracked data file is allowed to be
# ---------------------------------------------------------------------------
# Every entry needs a reason. "It was already there" is not one: that is exactly how the
# leak happened. If a new entry cannot be justified in one line, the data does not belong
# in the repository.
DATA_SUFFIXES = {".csv", ".tsv", ".json", ".geojson", ".ndjson", ".parquet", ".xlsx", ".xls"}

ALLOWED_DATA: dict[str, str] = {
    "examples/01-hello-dashboard/salgsdata.csv":
        "synthetic sales figures, written by hand for the hello example",
    "examples/15-chart-library-comparison-poc/data/fylker-6.geojson":
        "public county geometry, no personal or commercial content",
    "plugin/manifest.json":
        "configuration, not data",
    ".claude-plugin/plugin.json":
        "configuration, not data: Claude Code requires this exact path",
    ".claude-plugin/marketplace.json":
        "configuration, not data: Claude Code requires this exact path",
    "tools/core_generic_baseline.json":
        "gate state: file paths and match counts for the core boundary ratchet, no content",
}


def data_file_is_allowed(rel: str) -> bool:
    if rel in ALLOWED_DATA:
        return True
    # A plugin manifest and a plugin's tenant facts are configuration, not data, and both are
    # named by the contract's layout (docs/22-plugin-contract.md) rather than chosen per
    # plugin. Recognising the shape means a new plugin does not have to be allowlisted to be
    # legal, which is the same reasoning that makes templates/ a scope rule rather than a debt
    # entry. Only those two names, and only at the plugin's root.
    parts = rel.split("/")
    if len(parts) == 3 and parts[0] == "plugins" and parts[2] in ("manifest.json", "tenant-facts.json"):
        return True
    # The same holds for the manifest of a plugin's RAIWork Marketplace bundle, which the
    # Marketplace requires at the bundle root under exactly this name.
    if len(parts) == 5 and parts[0] == "plugins" and parts[2:] == ["raiwork", "bundle", "manifest.json"]:
        return True
    # A generator beside the data means the data is reproducible, so it is synthetic by
    # construction. This is how examples/03 keeps a 207 MB extract out of git.
    return False


# ---------------------------------------------------------------------------
# Rule 1: shapes that indicate personal data
# ---------------------------------------------------------------------------
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_NO = re.compile(r"\+47[\s-]?(?:\d[\s-]?){8}\b")
DIGITS_9 = re.compile(r"(?<!\d)\d{9}(?!\d)")
DIGITS_11 = re.compile(r"(?<!\d)\d{11}(?!\d)")

# Domains that cannot belong to a person: reserved-for-documentation names (RFC 2606) and
# the obvious local ones. `tun.community` is the project's own domain: an address there is a
# published role address (hei@, no personal mailbox), and it appears in the docs and on the
# landing page on purpose. Listing the domain, not a literal address, so a second role
# address does not need a second exemption; a personal mailbox is not created there.
NON_PERSON_DOMAINS = {
    "example.com", "example.org", "example.net", "example.edu",
    "localhost", "invalid", "test", "domain.com",
    "tun.community",
}


HEX_DIGIT = set("0123456789abcdefABCDEF")


def _inside_hex_digest(line: str, start: int, end: int) -> bool:
    """True when the digits sit inside a hash, not in text: a run of at least 32 hex
    characters that also holds a letter a-f, like a sha256 pin. One in eleven 9-digit runs
    inside a digest passes the orgnr checksum, so every re-pin would trip the gate. A
    number written in text ("Orgnr 123456789", "NO123456789MVA") is still caught."""
    lo, hi = start, end
    while lo > 0 and line[lo - 1] in HEX_DIGIT:
        lo -= 1
    while hi < len(line) and line[hi] in HEX_DIGIT:
        hi += 1
    token = line[lo:hi]
    return len(token) >= 32 and any(c in "abcdefABCDEF" for c in token)


def _orgnr_valid(number: str) -> bool:
    """Norwegian organisation number: nine digits, mod-11 with weights 3,2,7,6,5,4,3,2.

    The checksum is what makes this usable as a gate. A bare nine-digit regex fires on
    coordinates and identifiers: examples/15's geojson contains 884287641, which is not a
    valid organisation number, while a real organisation's registry number is. Such a number
    is deliberately not written here, because this gate scans its own source.
    """
    if len(number) != 9 or not number.isdigit():
        return False
    weights = (3, 2, 7, 6, 5, 4, 3, 2)
    total = sum(int(d) * w for d, w in zip(number[:8], weights))
    check = 11 - (total % 11)
    if check == 11:
        check = 0
    return check != 10 and check == int(number[8])


def _fnr_valid(number: str) -> bool:
    """Norwegian national identity number: eleven digits, two mod-11 control digits.

    Both control digits plus a plausible day and month are required. Without the checksum
    this pattern fires on timestamps and long integers.
    """
    if len(number) != 11 or not number.isdigit():
        return False
    day, month = int(number[0:2]), int(number[2:4])
    # D-numbers add 40 to the day; H-numbers add 40 to the month.
    if not (1 <= day <= 71 and 1 <= month <= 52):
        return False
    w1 = (3, 7, 6, 1, 8, 9, 4, 5, 2)
    w2 = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    k1 = 11 - (sum(int(d) * w for d, w in zip(number[:9], w1)) % 11)
    if k1 == 11:
        k1 = 0
    k2 = 11 - (sum(int(d) * w for d, w in zip(number[:10], w2)) % 11)
    if k2 == 11:
        k2 = 0
    return k1 < 10 and k2 < 10 and k1 == int(number[9]) and k2 == int(number[10])


def redact(value: str) -> str:
    """Show enough to locate it, not enough to leak it.

    The domain is redacted as well as the local part. When respondents are companies, the
    domain *is* the identifying half: printing `g***@somecompany.no` names the company as
    surely as the full address does. The public suffix is kept because it is not identifying and helps tell a
    Norwegian address from a foreign one.
    """
    if "@" in value:
        local, _, domain = value.partition("@")
        name, dot, tld = domain.rpartition(".")
        return f"{local[:1]}***@{name[:1]}***{dot}{tld}"
    return f"{value[:2]}***{value[-1:]} ({len(value)} digits)"


def scan_text(rel: str, text: str) -> list[tuple[int, str, str]]:
    """Return [(line number, kind, redacted value)] for one file."""
    findings: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in EMAIL.finditer(line):
            value = match.group(0)
            before = line[:match.start()]
            # Not addresses: URL userinfo and scp-style git remotes.
            #   ssh://git@host/x.git      -> the match is preceded by "//"
            #   git@example.com:org/repo  -> the match is followed by ":"
            if before.endswith("//"):
                continue
            if line[match.end():match.end() + 1] == ":":
                continue
            if value.rpartition("@")[2].lower() in NON_PERSON_DOMAINS:
                continue
            findings.append((lineno, "e-mail address", redact(value)))
        for match in PHONE_NO.finditer(line):
            findings.append((lineno, "Norwegian phone number", redact(match.group(0))))
        for match in DIGITS_9.finditer(line):
            if _orgnr_valid(match.group(0)) and not _inside_hex_digest(line, *match.span()):
                findings.append((lineno, "organisation number", redact(match.group(0))))
        for match in DIGITS_11.finditer(line):
            if _fnr_valid(match.group(0)) and not _inside_hex_digest(line, *match.span()):
                findings.append((lineno, "national identity number", redact(match.group(0))))
    return findings


# ---------------------------------------------------------------------------
# Reusable by example builders (rule 1 inverted: prove the data IS synthetic)
# ---------------------------------------------------------------------------
def assert_synthetic(rows: list[dict], columns: tuple[str, ...],
                     vocabulary: dict[str, str], *, context: str = "data") -> None:
    """Fail unless every row matches a declared synthetic vocabulary.

    Lifted from examples/17's builder, which already refused to write a data file whose
    values fell outside a per-column allowlist. Kept here so every builder shares one
    implementation instead of each example growing its own.

    An allowlist is the right shape for generated data: it states what the values may be,
    so a real value that happens to look ordinary still fails. A denylist cannot do that.
    """
    problems: list[str] = []
    for number, row in enumerate(rows, start=1):
        if sorted(row) != sorted(columns):
            problems.append(f"row {number} has columns {sorted(row)}, "
                            f"expected {sorted(columns)}")
            continue
        for column, pattern in vocabulary.items():
            if not re.fullmatch(pattern, str(row[column])):
                problems.append(f"row {number}: {column} is outside the synthetic "
                                f"vocabulary /{pattern}/")
    if problems:
        raise SystemExit(f"FAIL: {context} is not synthetic:\n  - "
                         + "\n  - ".join(problems[:20]))


# ---------------------------------------------------------------------------
def tracked_text(repo: pathlib.Path = tree_scan.REPO) -> list[str]:
    """Every tracked file worth reading as text. Raises ScopeError on an empty scope."""
    files = tree_scan.tracked_paths(repo)
    keep = [f for f in files if pathlib.Path(f).suffix.lower() not in SKIP_SUFFIXES]
    if not keep:
        raise tree_scan.ScopeError(
            "resolved zero tracked text files — the scope is broken, not clean")
    return keep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="print the scope and exit")
    ap.add_argument("--quiet", action="store_true", help="print only findings")
    args = ap.parse_args()

    try:
        files = tracked_text()
        all_tracked = tree_scan.tracked_paths()
    except tree_scan.ScopeError as exc:
        print(f"{R}✗ scope error{Z} {exc}", file=sys.stderr)
        return 2

    if args.list:
        for rel in files:
            print(rel)
        return 0

    shape_findings: list[tuple[str, int, str, str]] = []
    for rel in files:
        path = tree_scan.REPO / rel
        if not path.exists():
            raise SystemExit(f"tracked file missing from the working tree: {rel}")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"{Y}⚠{Z} could not read {rel}: {exc}", file=sys.stderr)
            continue
        for lineno, kind, shown in scan_text(rel, text):
            shape_findings.append((rel, lineno, kind, shown))

    location_findings = [
        rel for rel in all_tracked
        if pathlib.Path(rel).suffix.lower() in DATA_SUFFIXES
        and not data_file_is_allowed(rel)
    ]

    if not args.quiet:
        print(f"{B}real-data gate{Z}")
        print(f"  scope: {len(files)} tracked text file(s), "
              f"{len(all_tracked)} tracked file(s) total")
        print("─" * 72)
        icon, colour = ("✗", R) if shape_findings else ("✓", G)
        print(f"  {colour}{icon}{Z} personal-data shapes   "
              f"{len(shape_findings)} finding(s)")
        icon, colour = ("✗", R) if location_findings else ("✓", G)
        print(f"  {colour}{icon}{Z} data-file locations    "
              f"{len(location_findings)} unexpected file(s)  "
              f"{D}({len(ALLOWED_DATA)} allowed){Z}")
        print("─" * 72)

    if shape_findings:
        print(f"\n{R}✗ FAIL{Z} — personal-data shapes found (values redacted):")
        for rel, lineno, kind, shown in shape_findings:
            print(f"    {rel}:{lineno}  {kind}: {shown}")
        print("\n  If this is genuinely not personal data, make the pattern narrower or"
              "\n  add the specific exclusion with a reason. Do not widen the gate.")

    if location_findings:
        print(f"\n{R}✗ FAIL{Z} — data file(s) tracked outside an expected location:")
        for rel in location_findings:
            print(f"    {rel}")
        print("\n  Real extracts belong outside git: work/ and dashboards/ are ignored."
              "\n  If this file is synthetic, add it to ALLOWED_DATA in"
              " tools/check_no_real_data.py\n  with a one-line reason, or better, ship the"
              " generator and leave the data untracked\n  (see examples/03).")

    if shape_findings or location_findings:
        return 1
    if not args.quiet:
        print(f"\n{G}✓ PASS{Z} — no personal-data shapes, no unexpected data files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
