#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
check_export_clean.py — refuse an export that still carries identifying text.

Stdlib only. Run it over the tree you are about to hand to someone else:

    python3 tools/check_export_clean.py                 # this checkout's tracked files
    python3 tools/check_export_clean.py --root ../out   # any other tree (git or plain dir)

Why the terms are not in this file
----------------------------------
The thing being searched for is identifying by definition: names of people, the
organisation, internal hosts, internal programme names. A tracked list of those terms
would leak exactly what the gate exists to keep out. So the terms live in a local,
untracked file, one case-insensitive regex per line:

    $TUN_DENYLIST, or else ~/.config/tun/denylist.txt

    # comment
    label<TAB>regex

A missing or empty denylist is an error, never a pass. A gate that silently checks
nothing is worse than no gate.

What it reads
-------------
Every file in scope, as bytes, decoded leniently, so a term inside an image's metadata
or a minified vendor file is found too. File *paths* are checked as well: a directory
named after a person is as identifying as a sentence. Text drawn as pixels inside a
screenshot cannot be read here; regenerate screenshots from clean sources instead.

Findings are printed as label + file:line + a redacted match, so the log does not
become a second copy of what it found.

Exit codes: 0 clean, 1 findings, 2 the check could not run.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys

DEFAULT_DENYLIST = pathlib.Path.home() / ".config" / "tun" / "denylist.txt"

# Generic shapes that are never identifying to list here, checked on every run.
BUILTIN = [
    ("email", r"\b[A-Za-z0-9._%+-]+@(?!example\.(?:com|org|net)\b)[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b"),
    ("ci run id", r"\brun \d{6,}\b"),
]

# The gate itself names the shapes above; its own source is not an export risk.
SELF = "tools/check_export_clean.py"


def load_denylist(path: pathlib.Path) -> list[tuple[str, re.Pattern]]:
    if not path.is_file():
        raise SystemExit(f"✗ denylist not found: {path}\n"
                         "  Set TUN_DENYLIST or create ~/.config/tun/denylist.txt. "
                         "Refusing to report clean without one.")
    rules = []
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        label, sep, rx = line.partition("\t")
        if not sep:
            label, rx = "term", line
        try:
            rules.append((label.strip(), re.compile(rx.strip(), re.IGNORECASE)))
        except re.error as e:
            raise SystemExit(f"✗ denylist line {n} is not a valid regex: {e}")
    if not rules:
        raise SystemExit(f"✗ denylist is empty: {path}. Refusing to report clean.")
    return rules


def list_files(root: pathlib.Path) -> list[str]:
    # A git hook exports GIT_DIR/GIT_INDEX_FILE, which override `git -C` entirely.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    if (root / ".git").exists():
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                             capture_output=True, env=env)
        if out.returncode != 0:
            raise SystemExit(f"✗ git ls-files failed in {root}: {out.stderr.decode().strip()}")
        return [p for p in out.stdout.decode().split("\0") if p]
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")
                  if p.is_file() and ".git" not in p.relative_to(root).parts)


#: A copyright notice names its holder on purpose: that is attribution, not a leak.
#: Only the "person" label is exempt, and only on the notice line itself, so the same
#: name anywhere else in the file is still caught, and an organisation named as holder
#: is still caught. Line count is preserved so reported line numbers stay right.
COPYRIGHT_LINE = re.compile(r"(?mi)^[^\n]*\b(?:Copyright \(C\)|SPDX-FileCopyrightText:)[ \t]*\d{4}\b[^\n]*$")
NOTICE_EXEMPT = ("person",)


def strip_copyright_lines(text: str) -> str:
    return COPYRIGHT_LINE.sub("", text)


def redact(s: str) -> str:
    s = s.strip()
    return s[:1] + "…" * min(len(s) - 1, 3) + f"({len(s)})" if s else "(empty)"


def scan(root: pathlib.Path, rules) -> tuple[int, list[tuple[str, str, int, str]]]:
    files = list_files(root)
    if not files:
        raise SystemExit(f"✗ no files in scope under {root}. Refusing to report clean.")
    hits = []
    for rel in files:
        for label, rx in rules:
            for m in rx.finditer(rel):
                hits.append((label, rel, 0, redact(m.group(0))))
        if rel == SELF:
            continue
        p = root / rel
        if not p.is_file():
            continue
        text = p.read_bytes().decode("utf-8", errors="ignore")
        noticed = strip_copyright_lines(text)
        for label, rx in rules:
            subject = noticed if label in NOTICE_EXEMPT else text
            for m in rx.finditer(subject):
                line = subject.count("\n", 0, m.start()) + 1
                hits.append((label, rel, line, redact(m.group(0))))
    return len(files), hits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=None, help="tree to check (default: this repository)")
    ap.add_argument("--denylist", default=os.environ.get("TUN_DENYLIST") or str(DEFAULT_DENYLIST))
    args = ap.parse_args(argv)

    root = pathlib.Path(args.root).resolve() if args.root else pathlib.Path(__file__).resolve().parents[1]
    try:
        rules = load_denylist(pathlib.Path(args.denylist).expanduser())
        rules += [(label, re.compile(rx, re.IGNORECASE)) for label, rx in BUILTIN]
        n, hits = scan(root, rules)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2

    for label, rel, line, shown in hits:
        where = f"{rel} (path)" if line == 0 else f"{rel}:{line}"
        print(f"  ✗ {label:<10} {where}  {shown}")
    print("─" * 72)
    verdict = "✓ PASS" if not hits else f"✗ FAIL — {len(hits)} finding(s)"
    print(f"{verdict}: checked {n} file(s) against {len(rules)} pattern(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
