#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_gate_coverage.py — is every shipped artefact actually measured by something?

ROADMAP C5. `tools/verify_documented.py` reads the verify command out of each README and
runs it, which is how the public CI measures the text floors and the accessibility rules on
every artefact this repository ships. Two things can go wrong with that arrangement and
neither is visible from a green run:

  * the runner finds no commands at all and exits 0, proving nothing;
  * a shipped artefact is named by no documented command, so nothing measures it and its
    floor is whatever its builder happened to emit. That is how a 13 px block reached a
    green `check_all` in #166: `check_all` does not run `verify_documented` (it needs a
    browser, three engines and minutes), and on the internal forge the `gates` job skips by
    design, so between the two nothing local looked.

This suite renders nothing. It checks the *coverage* of the runner, which is the part that
can be checked in a second, and leaves the rendering to the runner itself. What it cannot
do is prove a measurement passed; only `verify_documented` does that.

The artefacts below are the debt that remains. Each carries
a reason, and an entry that goes stale (the file disappears, or someone documents it) fails,
so the list can only shrink. A new artefact with no documented verify command fails at once.

    python3 tests/test_gate_coverage.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import verify_documented as documented  # noqa: E402

# Why a shipped artefact is named by no documented verify command. A reason, not a shrug:
# "it was already there" is how a gap becomes permanent.
KNOWN_UNDOCUMENTED = {
    "examples/16-embedding-mode-comparison-poc/embedding-mode-comparison-poc.html":
        "the README names it but runs no verify command; the embedding question is answered "
        "in docs/11",
    "examples/22-xlsx-from-file/xlsx-from-file.html":
        "measured by examples/22-xlsx-from-file/verify_xlsx_from_file.py, which locates the "
        "file itself, so no documented command names it",
    "examples/27-survey-board/survey-en.html":
        "the same build as survey.html with --lang en, and the README verifies that one",
    "examples/34-folder-index/saker-dashboard.html":
        "one of the three artefacts the index example lists; the README verifies the index, "
        "and tests/test_folder_index.py builds its own copies from scratch",
    "examples/34-folder-index/saker-register.html":
        "one of the three artefacts the index example lists; see saker-dashboard.html",
    "examples/34-folder-index/saker-sammenligning.html":
        "one of the three artefacts the index example lists; see saker-dashboard.html",
    "examples/31-survey-crosstab/survey-crosstab.html":
        "tests/test_survey_crosstab.py builds it and walks it in a browser, so the shipped "
        "copy is a fixture for that suite rather than a documented artefact",
}

CHECKS = FAILED = 0


def chk(ok: bool, what: str, detail: str = "") -> bool:
    global CHECKS, FAILED
    CHECKS += 1
    print(f"  {'✓' if ok else '✗'} {what}" + ("" if ok else f" — {detail}"))
    if not ok:
        FAILED += 1
    return ok


def named_by_commands(commands) -> tuple[set[str], list[str]]:
    """(file names a documented command names, the paths that do not resolve).

    A command is written relative to the README that carries it: most start `python3
    tools/...` from the repository root, and two start `../../tools/...` from inside their
    own example directory. Both are legal, so a word is resolved against the README's own
    directory first and against the root second. Reading only the root reported two
    artefacts as missing that are right there.
    """
    named, missing = set(), []
    for entry in commands:
        base = pathlib.Path(entry[1])
        words = entry[2] if isinstance(entry[2], (list, tuple)) else [entry[2]]
        for word in words:
            word = str(word)
            if not word.endswith(".html"):
                continue
            path = base / word
            if not path.exists():
                path = ROOT / word
            named.add(path.name)
            if not path.exists():
                missing.append(word)
    return named, missing


def shipped() -> list[pathlib.Path]:
    """Every built .html under examples/, minus the ones that are not documents."""
    out = []
    for p in sorted((ROOT / "examples").rglob("*.html")):
        if p.name.endswith(".template.html") or p.name.endswith(".fragment.html"):
            continue
        out.append(p)
    return out


def audit(named: set[str], files: list[pathlib.Path]) -> tuple[list[str], list[str]]:
    """(shipped but named by nothing and not on the list, entries that have gone stale)."""
    unmeasured, stale = [], []
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        if p.name not in named and rel not in KNOWN_UNDOCUMENTED:
            unmeasured.append(rel)
    for rel in KNOWN_UNDOCUMENTED:
        path = ROOT / rel
        if not path.exists():
            stale.append(f"{rel}: gone")
        elif path.name in named:
            stale.append(f"{rel}: now documented, so the entry must go")
    return unmeasured, stale


def main() -> int:
    print("gate coverage: is every shipped artefact measured by something?")
    print("─" * 78)

    commands = documented.commands()
    chk(len(commands) >= 20, "the documented commands are found",
        f"only {len(commands)}: a runner that finds none measures nothing")
    named, missing = named_by_commands(commands)
    chk(not missing, "every artefact a documented command names exists", ", ".join(missing))
    chk(len(named) >= 20, "the documented set is larger than the undocumented one",
        f"{len(named)} named")

    files = shipped()
    chk(len(files) >= 30, "the shipped artefacts are found", f"only {len(files)}")
    unmeasured, stale = audit(named, files)
    chk(not unmeasured,
        "every shipped artefact is named by a documented command, or listed with a reason",
        "; ".join(unmeasured))
    chk(not stale, "no entry on the list has gone stale", "; ".join(stale))
    # Counted over files, not names: two examples both ship an `oversikt.html`, so a name
    # named once covers two files and a name-based total would not add up.
    measured = [p for p in files if p.name in named]
    debt = [p for p in files if p.name not in named]
    chk(len(measured) + len(debt) == len(files),
        "the accounting adds up", f"{len(measured)} + {len(debt)} != {len(files)}")
    chk(len(debt) == len(KNOWN_UNDOCUMENTED),
        "every unmeasured file is on the list, once", f"{len(debt)} file(s), "
        f"{len(KNOWN_UNDOCUMENTED)} entry(ies)")
    print(f"       {len(measured)} of {len(files)} shipped artefact(s) measured by one of "
          f"{len(commands)} documented command(s); {len(debt)} carried as debt with a reason")

    # Mutation controls: each rule is shown to fail when its subject is wrong.
    print("\n  mutation controls")
    ghost = ROOT / "examples" / "99-not-there" / "ny.html"
    unmeasured_m, _ = audit(named, files + [ghost])
    chk("examples/99-not-there/ny.html" in unmeasured_m,
        "a new artefact nothing verifies is reported", str(unmeasured_m))
    saved_key = next(iter(KNOWN_UNDOCUMENTED))
    saved = KNOWN_UNDOCUMENTED[saved_key]
    KNOWN_UNDOCUMENTED["examples/99-not-there/ny.html"] = "invented"
    _, stale_m = audit(named, files)
    chk(any("99-not-there" in s for s in stale_m),
        "an entry pointing at nothing is reported", str(stale_m))
    del KNOWN_UNDOCUMENTED["examples/99-not-there/ny.html"]
    KNOWN_UNDOCUMENTED[saved_key] = saved
    chk(len(KNOWN_UNDOCUMENTED) == len(set(KNOWN_UNDOCUMENTED)) == 7,
        "the list is back as it was", str(len(KNOWN_UNDOCUMENTED)))

    print("─" * 78)
    print(f"{CHECKS - FAILED} of {CHECKS} checks passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
