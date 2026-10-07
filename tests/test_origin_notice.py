#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Origin Notice is a licence condition, so it has to be gated.

COPYING.ARTEFACT-EXCEPTION grants the permission that makes Tún useful: a generated
artefact may be conveyed under any terms. Since version 1.1 that permission is
*conditional* on one thing, under AGPLv3 section 7(b): the artefact keeps the Origin
Notice naming Tún and where to find the project.

A condition nobody checks is a condition that quietly dies. The notice lives in the
templates, because that is where a generated artefact inherits it from, so this test
asserts every template that carries a provenance block also carries the notice.

It also asserts the notice on every built example HTML in the repository: they are
Generated Artefacts, rebuilt under version 1.1, and a sample that cannot show the notice
cannot meet the condition its own header promises.

Run: python3 tests/test_origin_notice.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
EXCEPTION = ROOT / "COPYING.ARTEFACT-EXCEPTION"

# What the notice must contain to satisfy the Exception: the project name, and where the
# project can be found. Both, or the notice does not do its job.
NAME = "Tún"
HOME = "tun.community"
LABEL = "Made with"

passed = 0
failed: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed
    if ok:
        passed += 1
    else:
        failed.append(f"{name}: {detail}")


def main() -> int:
    templates = sorted(TEMPLATES.glob("*.html"))
    if not templates:
        print("FAIL: no templates found — this test cannot pass vacuously", file=sys.stderr)
        return 1

    # A template only needs the notice if it writes a provenance block at all.
    with_provenance = [p for p in templates if "PROVENANCE" in p.read_text(encoding="utf-8")]
    if not with_provenance:
        print("FAIL: no template carries a provenance block; the notice has no home",
              file=sys.stderr)
        return 1

    for p in with_provenance:
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(ROOT)
        check(f"{rel} has the label", LABEL in text,
              f'missing "{LABEL}" line in the provenance block')
        check(f"{rel} names the project", NAME in text, f'notice does not name "{NAME}"')
        check(f"{rel} says where to find it", HOME in text,
              f'notice does not state "{HOME}"')

    # Every built example HTML is a Generated Artefact and must carry the notice on one
    # line, label included. "Laget med" is the Norwegian label used by hand-built pages.
    import subprocess, os
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "*.html"], capture_output=True,
                             text=True, check=True, env=env).stdout.split()
    built = [r for r in tracked if not r.startswith("templates/") and "/vendor/" not in r
             and not r.endswith(".template.html")]
    if len(built) < 10:
        print(f"FAIL: only {len(built)} built example(s) found — scope is broken", file=sys.stderr)
        return 1
    for rel in built:
        lines = (ROOT / rel).read_text(encoding="utf-8").splitlines()
        notice = [l for l in lines if (LABEL in l or "Laget med" in l) and NAME in l and HOME in l]
        check(f"{rel} carries the Origin Notice", bool(notice),
              "no single line with the label, the project name and where to find it")

    # The Exception itself must still define the condition. If someone drops condition
    # 1(b), this test would otherwise keep enforcing a requirement that no longer exists.
    exc = EXCEPTION.read_text(encoding="utf-8") if EXCEPTION.exists() else ""
    check("the Exception defines the Origin Notice", "Origin Notice" in exc,
          "COPYING.ARTEFACT-EXCEPTION no longer defines an Origin Notice")
    check("the Exception conditions the grant on it",
          "the Origin Notice is preserved" in exc,
          "condition 1(b) is gone — the templates would be enforcing nothing")
    check("the Exception keeps it non-visible-by-default",
          "does not have to be visible" in exc,
          "the notice became an advertising requirement; that is a different licence")

    print(f"  templates gated: {len(with_provenance)} of {len(templates)}; built examples gated: {len(built)}")
    for f in failed:
        print(f"  FAIL {f}")
    print(f"PASS: {passed}  FAIL: {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
