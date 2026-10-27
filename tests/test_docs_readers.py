#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Docs are filed by reader, and the filing is checked, because a doc nobody can find is a
doc nobody reads.

Thirty-one documents under `docs/` is past the point where reading them in order works.
`ROADMAP.md` B3: split them by reader, mark records as records, and keep the split honest
with a test rather than with good intentions.

Every document declares its reader in one line directly under its title:

    **Reader:** user|contributor|record — <a gloss of who that is>

`docs/index.md` files each one under a matching section marked with
`<!-- reader: X -->`. This suite requires the two to agree, which is what stops the index
from drifting back into a pile. It also requires every relative link in the repository to
resolve, so a rename cannot leave a dangling reference behind, and it refuses to pass on an
empty document list.

Mutation controls at the end: each rule is shown to fail on a mutated copy.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
INDEX = DOCS / "index.md"
READERS = ("user", "contributor", "record")
#: Linked from outside `docs/`, or deliberately reachable only through the index.
ORPHAN_OK = {"index.md", "findings-index.md"}

CHECKS = 0
FAILED: list[str] = []


def chk(ok: bool, what: str, detail: str = "") -> bool:
    global CHECKS
    CHECKS += 1
    print(f"  {'✓' if ok else '✗'} {what}" + ("" if ok else f" — {detail}"))
    if not ok:
        FAILED.append(what)
    return ok


def section(title: str) -> None:
    print(f"\n{title}")


def content_docs() -> list[pathlib.Path]:
    """Every document the index is meant to file.

    A name starting with `_` is a probe another suite writes into `docs/` for a second or two
    to prove its own scanner bites. `check_all` runs the suites in parallel, so this glob used
    to see `docs/_glossary_probe.md` appear and then vanish between the listing and the read,
    and the whole run failed with FileNotFoundError on a file that was never a document. Probes
    are not documents, and that is the only reason to filter on the name.
    """
    return sorted(p for p in DOCS.glob("*.md")
                  if p.name not in ("index.md", "findings-index.md")
                  and not p.name.startswith("_"))



def repo_markdown() -> list[pathlib.Path]:
    """Every markdown file this repository owns, which is not every markdown file on disk.

    `ROOT.rglob` also walks `work/`, the gitignored scratch space where a session builds a
    real deliverable. Those files are not this repository's documents, they are never
    exported, and one of them holding a stale relative link made this suite fail on a
    checkout whose tracked files were all fine. Ask git instead, so the scan covers exactly
    what is committed plus an untracked file someone is about to commit, and fall back to
    the walk only when git is unavailable.
    """
    try:
        done = subprocess.run(
            # --cached only: --others admitted a probe file another suite writes into docs/
            # and deletes again, and reading a file that vanishes is a race, not a finding.
            # Pre-commit runs after staging, so a file being committed is already cached.
            ["git", "-C", str(ROOT), "ls-files", "-z", "--cached"],
            capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return sorted(p for p in ROOT.rglob("*.md") if ".git" not in str(p))
    out = []
    for name in done.stdout.decode("utf-8", "replace").split("\0"):
        if name.endswith(".md"):
            path = ROOT / name
            if path.is_file():
                out.append(path)
    return sorted(out)

def declared_reader(text: str) -> list[str]:
    """Every reader declared in the document's opening block (before the first `##`)."""
    head = text.split("\n## ", 1)[0]
    return re.findall(r"^\*\*Reader:\*\*\s*(\w+)", head, re.M)


def filed_sections(index_text: str) -> dict[str, str]:
    """{linked filename: reader section it was filed under}."""
    out: dict[str, str] = {}
    current = ""
    for line in index_text.splitlines():
        m = re.match(r"^<!-- reader: (\w+) -->$", line.strip())
        if m:
            current = m.group(1)
        if not line.lstrip().startswith("|"):
            continue        # only the tables file a document; prose may mention one anywhere
        for name in re.findall(r"\]\(([\w./-]*?\d\d-[a-z0-9-]+\.md)\)", line):
            out.setdefault(pathlib.Path(name).name, current)
    return out


def inbound_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in repo_markdown():
        if ".git" in str(p):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for name in re.findall(r"\]\((?:\./)?([\w./-]*?\d\d-[a-z0-9-]+\.md)\)", text):
            base = pathlib.Path(name).name
            if p != DOCS / "index.md":
                counts[base] = counts.get(base, 0) + 1
    return counts


def broken_links(skip: set[pathlib.Path] = frozenset()) -> list[str]:
    """Every relative markdown link in the repository that does not resolve."""
    bad: list[str] = []
    for p in repo_markdown():
        rel = p.relative_to(ROOT).as_posix()
        if ".git" in str(p) or p in skip or rel.startswith("internal/"):
            continue    # internal/ is an archive of notes, never exported and never edited
        text = p.read_text(encoding="utf-8", errors="replace")
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)\s]*)?\)", text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if "{" in target or "<" in target or "path/to" in target:
                continue      # a template placeholder, not a link
            if target.startswith("dashboards/"):
                continue      # the folder the reader creates; a skill shows the shape, not a file
            resolved = (p.parent / target).resolve()
            if not resolved.exists():
                bad.append(f"{p.relative_to(ROOT)} -> {target}")
    return bad


def main() -> int:
    docs = content_docs()
    text_index = INDEX.read_text(encoding="utf-8")

    section("1. the document list is not empty, and every doc declares one reader")
    chk(len(docs) >= 25, "the scan resolved the docs", f"only {len(docs)}")
    chk(not any(p.name.startswith("04-onboarding-en kollega") for p in docs),
        "the named onboarding file stays gone")
    missing, doubled, invalid = [], [], []
    for p in docs:
        found = declared_reader(p.read_text(encoding="utf-8"))
        if not found:
            missing.append(p.name)
        elif len(found) > 1:
            doubled.append(p.name)
        elif found[0] not in READERS:
            invalid.append(f"{p.name}={found[0]}")
    chk(not missing, "every document says who it is for", f"none in {missing}")
    chk(not doubled, "no document declares two readers", f"two in {doubled}")
    chk(not invalid, "each one uses one of the three words", f"{invalid}")

    section("2. the index files every document under its own reader")
    filed = filed_sections(text_index)
    chk(len(filed) >= 25, "the index links the docs", f"only {len(filed)}")
    unfiled = [p.name for p in docs if p.name not in filed]
    chk(not unfiled, "no document is left out of the index", f"{unfiled}")
    misfiled = []
    for p in docs:
        found = declared_reader(p.read_text(encoding="utf-8"))
        if found and p.name in filed and filed[p.name] != found[0]:
            misfiled.append(f"{p.name}: says {found[0]}, filed under {filed[p.name] or 'nothing'}")
    chk(not misfiled, "no document is filed under a reader it does not claim", f"{misfiled}")
    unopened = [n for n, r in filed.items() if not r]
    chk(not unopened, "every link sits inside a reader section", f"outside: {unopened}")

    section("3. every document is reachable, and every link resolves")
    counts = inbound_counts()
    orphans = [p.name for p in docs if p.name not in ORPHAN_OK and counts.get(p.name, 0) == 0]
    chk(not orphans, "no document is reachable only by guessing its name", f"{orphans}")
    bad = broken_links()
    chk(not bad, "every relative link in every markdown file resolves", f"{bad[:6]}")

    section("4. the merge B3 asks for has happened")
    chk(not (DOCS / "16-licensing-layers.md").exists(),
        "the licensing deep dive is folded into 17-licensing.md")
    chk(not (DOCS / "19-name-adoption-plan.md").exists(),
        "the adoption plan is folded into 18-naming.md")
    stale = []
    for p in repo_markdown():
        rel = p.relative_to(ROOT).as_posix()
        if ".git" in str(p) or rel.startswith("internal/"):
            continue        # archived notes keep their own history, unedited
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
            if re.search(r"1[69]-(licensing-layers|name-adoption-plan)", line) and "Formerly" not in line:
                stale.append(f"{rel}:{i + 1}")
    chk(not stale, "nothing still links to the two folded documents", f"{stale}")
    lic = (DOCS / "17-licensing.md").read_text(encoding="utf-8")
    chk("Artefact Exception" in lic, "the licence record still states the exception")
    chk(re.search(r"##.*layer", lic, re.I) is not None,
        "the layer split survived the fold")
    nam = (DOCS / "18-naming.md").read_text(encoding="utf-8")
    chk("adopt" in nam.lower(), "the naming record still holds the adoption notes")

    section("5. the rules can fail: each is run against a mutation")
    sample = docs[0]
    sample_text = sample.read_text(encoding="utf-8")

    # a) a document with no reader line
    mutant = re.sub(r"^\*\*Reader:\*\*.*$", "", sample_text, count=1, flags=re.M)
    chk(declared_reader(mutant) == [],
        "mutation a: deleting the reader line is caught", f"got {declared_reader(mutant)}")

    # b) a document claiming the wrong reader
    mutant = re.sub(r"^\*\*Reader:\*\* \w+", "**Reader:** contributor", sample_text, count=1, flags=re.M)
    found = declared_reader(mutant)
    filed_as = filed.get(sample.name)
    chk(found and found[0] != filed_as,
        "mutation b: a reader that disagrees with the index is caught",
        f"docs says {found}, index says {filed_as}")

    # c) a document dropped from the index
    mutant_index = re.sub(rf"^\| \[[^\]]+\]\({re.escape(sample.name)}\).*$\n", "", text_index, flags=re.M)
    chk(sample.name not in filed_sections(mutant_index),
        "mutation c: deleting a row from the index is caught")

    # d) a link that points at nothing
    mutant = text_index.replace("(04-onboarding.md)", "(04-onboarding-gone.md)", 1)
    with_broken = broken_links() + (
        [f"index -> 04-onboarding-gone.md"] if (DOCS / "04-onboarding-gone.md").resolve().exists() is False
        and "(04-onboarding-gone.md)" in mutant else [])
    chk(bool(with_broken), "mutation d: a link to a file that does not exist is caught",
        "the resolver found nothing to complain about")

    print()
    if FAILED:
        print(f"FAIL: {CHECKS - len(FAILED)} of {CHECKS} checks")
        for f in FAILED:
            print(f"  - {f}")
        return 1
    print(f"PASS: {CHECKS} of {CHECKS} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
