#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""One word for one thing, the part a machine can check (ROADMAP B6).

`docs/30-glossary.md` fixes the vocabulary. Half of it is judgement and only a reviewer can
check that, but the other half is spelling, and spelling drifts in silence: the repository
says "artefact" everywhere except in the filename of the document that defines the model,
and one word with a hyphen becomes two words the moment someone types quickly.

So this suite checks three mechanical things and states what it cannot check:

  1. the glossary defines each canonical term, so the words have one home
  2. the US spelling does not appear in this repository's own prose, outside two named
     exemptions: the document whose *filename* carries it, and the Atlassian product name
  3. "self contained" without the hyphen appears only inside a quoted source, where the
     quotation marks are the proof that the words are someone else's

Every check prints how many files it resolved and refuses to pass on an empty scan: a gate
that derives its own input list can pass while proving nothing, and this repository has
found that failure twice. Two mutation controls prove the scanner can say no.

Run: python3 tests/test_glossary.py
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
GLOSSARY = ROOT / "docs" / "30-glossary.md"

# The terms this page is the home of. A term removed from the glossary must be removed
# from here too, or the gate is naming a definition that no longer exists.
CANONICAL = ("artefact", "dashboard", "provenance block", "self-contained")

# Paths whose US spelling is deliberate, each with its reason stated in the glossary.
US_SPELLING_EXEMPT = {
    # Our own spelling debt, in a filename rather than a sentence. Named, not hidden.
    "docs/08-generic-artifact-model.md",
    # A vendored record of paths, not prose this repository writes.
    "tools/core_generic_baseline.json",
    # A task's build directory and the archive: not claims about the present.
    "internal/",
    "work/",
    "examples/",
    # The plugin bundles are shipped inside another organisation's tooling and name its
    # products; they are not this repository's voice either.
    "plugins/",
}

# The Atlassian route is exempt as a group, because in those files the word is a product
# name and its API keys, and the sentences around them are about the product too. That is a
# real hole in the scan, and it is worth its size: the alternative is a per-line whitelist
# that grows every time the product is mentioned.
ATLASSIAN_FILES = {
    "docs/22-plugin-contract.md",             # the plugin's tenant_facts key
    "docs/23-hosted-route-it-brief.md",       # the hosted route, measured on Artifacts
    "docs/26-hosting.md",                     # the backend comparison
    "docs/29-atlassian-artifacts.md",         # the measured product route
    "skills/tun-publish/SKILL.md",            # publishes there
    "tools/artifact_upload.py",               # calls its API
}
# The gate is about sentences. Code carries the word legitimately: an API key, a JSON
# field, a function name. So only the formats that hold prose written for a reader.
PROSE_SUFFIXES = (".md", ".html", ".strings", ".txt")

FAILURES: list[str] = []
CHECKS = 0


def check(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if ok:
        print(f"  \u2713 {what}")
    else:
        print(f"  \u2717 {what}" + (f"  [{detail}]" if detail else ""))
        FAILURES.append(what)


def tracked_files() -> list[str]:
    """Only files git tracks. A stray build output is not this repository's prose."""
    proc = subprocess.run(["git", "ls-files"], cwd=str(ROOT), capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit("test_glossary: not a git checkout, so the file list cannot be trusted")
    return [line for line in proc.stdout.splitlines() if line.strip()]


def exempt(path: str) -> bool:
    if path in ATLASSIAN_FILES:
        return True
    return any(path == p or path.startswith(p) for p in US_SPELLING_EXEMPT)


# Identifiers, not prose: a config key or a template placeholder may carry the US spelling
# because it is a name something else matches on. Backticked spans are stripped before the
# scan for the same reason a path is: the gate is about sentences.
CODE_SPAN = re.compile(r"`[^`]*`|\{\{[^}]*\}\}|\bARTIFACT_SPECIFIC_LINE\b")
PRODUCT_NAME = re.compile(r"atlassian[ -]artifacts|artifacts UI", re.IGNORECASE)
# A page that forbids a spelling has to be able to write it. Quoted, it is a citation of the
# wrong form, the same way a quoted source keeps its own words.
QUOTED = re.compile(r'"[^"]*"|\u201c[^\u201d]*\u201d')


def strip_exempt_paths(line: str) -> str:
    """Remove links to an exempt path before scanning a line.

    A document that links to `docs/08-generic-artifact-model.md` writes the US spelling,
    but it writes it inside a path, and the path is the exemption. Stripping it keeps the
    link legal without whitelisting the whole sentence around it.
    """
    line = CODE_SPAN.sub("<code>", line)
    line = PRODUCT_NAME.sub("<product>", line)
    line = QUOTED.sub("<quoted>", line)
    for path in US_SPELLING_EXEMPT:
        line = line.replace(path, "<exempt-path>")
        name = pathlib.Path(path)
        line = line.replace(name.name, "<exempt-path>")
        if name.suffix:
            # A document may name the file without its extension, as the layout list does.
            line = line.replace(name.stem, "<exempt-path>")
    return line


def scan_us_spelling(files: list[str]) -> list[str]:
    """`artifact` in prose. Case-insensitive, because the sentence-initial form drifts too."""
    hits = []
    pattern = re.compile(r"\bartifact", re.IGNORECASE)
    for rel in files:
        if exempt(rel) or not rel.endswith(PROSE_SUFFIXES):
            continue
        text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            if pattern.search(strip_exempt_paths(line)):
                hits.append(f"{rel}:{number}")
    return hits


def scan_self_contained(files: list[str]) -> list[str]:
    """`self contained` outside quotation marks. A quoted source keeps its spelling."""
    hits = []
    pattern = re.compile(r"self[\s-]+contained", re.IGNORECASE)
    for rel in files:
        if exempt(rel) or not rel.endswith(PROSE_SUFFIXES):
            continue
        text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            match = pattern.search(CODE_SPAN.sub("<code>", line))
            if match and "-" not in match.group(0):
                quoted = '"' in line or "\u201c" in line
                if not quoted:
                    hits.append(f"{rel}:{number}")
    return hits


def main() -> int:
    print("\n1. the glossary exists and holds every term")
    check(GLOSSARY.is_file(), "docs/30-glossary.md exists")
    if GLOSSARY.is_file():
        text = GLOSSARY.read_text(encoding="utf-8")
        for term in CANONICAL:
            check(f"**{term}" in text.lower() or f"**{term.title()}" in text,
                  f"the glossary defines {term!r}")

    files = tracked_files()
    check(len(files) > 100, "the file list resolved", f"{len(files)} tracked files")

    print("\n2. this repository writes artefact, not artifact")
    hits = scan_us_spelling(files)
    check(not hits, f"no US spelling in the prose of {len(files)} tracked files",
          ", ".join(hits[:6]))
    # The control: the scanner has to be able to fail, or the pass above means nothing.
    probe = ROOT / "docs" / "_glossary_probe.md"
    probe.write_text("an artifact in a sentence\n", encoding="utf-8")
    try:
        found = scan_us_spelling([str(probe.relative_to(ROOT))])
        check(found == ["docs/_glossary_probe.md:1"], "the scanner catches an injected hit",
              str(found))
    finally:
        probe.unlink()

    print("\n3. the property is self-contained, and a quotation keeps its own spelling")
    hits = scan_self_contained(files)
    check(not hits, "no unhyphenated use outside a quotation", ", ".join(hits[:6]))
    probe.write_text("the file is self contained\n", encoding="utf-8")
    try:
        found = scan_self_contained([str(probe.relative_to(ROOT))])
        check(found == ["docs/_glossary_probe.md:1"], "the scanner catches an injected hit",
              str(found))
        probe.write_text('a source said "self contained" and meant it\n', encoding="utf-8")
        check(not scan_self_contained([str(probe.relative_to(ROOT))]),
              "a quoted use is not a hit, so the gate does not punish citation")
    finally:
        probe.unlink()

    print("\n4. what this gate cannot do, stated rather than implied")
    check(True, "meaning is not checked here: a process diagram called a dashboard passes, "
                "and the reviewer catches it")

    print()
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} of {CHECKS} checks failed")
        for name in FAILURES:
            print(f"  - {name}")
        return 1
    print(f"PASS: {CHECKS} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
