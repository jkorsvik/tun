#!/usr/bin/env python3
"""The Origin Notice is a licence condition, so it has to be gated.

COPYING.ARTEFACT-EXCEPTION grants the permission that makes Tún useful: a generated
artefact may be conveyed under any terms. Since version 1.1 that permission is
*conditional* on one thing, under AGPLv3 section 7(b): the artefact keeps the Origin
Notice naming Tún and where to find the project.

A condition nobody checks is a condition that quietly dies. The notice lives in the
templates, because that is where a generated artefact inherits it from, so this test
asserts every template that carries a provenance block also carries the notice.

It deliberately does NOT assert the notice on built examples. Artefacts produced before
version 1.1 do not have it, and retrofitting a claim into an old artefact would be
dishonest about when it was made.

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

    print(f"  templates gated: {len(with_provenance)} of {len(templates)}")
    for f in failed:
        print(f"  FAIL {f}")
    print(f"PASS: {passed}  FAIL: {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
