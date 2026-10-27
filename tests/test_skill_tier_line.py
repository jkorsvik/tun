#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Every user skill says what it costs before it does anything.

AGENTS.md: "Every skill states its tier and governance cost in its first reply. Nobody
should discover an admin approval chain at the end." That is a promise to the reader, and
until now three of the nine dashboard skills kept it and six did not, which is exactly the
kind of convention that rots: the author who wrote the skill knew the cost, so it never
occurred to them to write it down.

The line is one canonical form so a reader (and this test) can find it:

    **Tier and cost, for the first reply:** <what it costs>

and it belongs in the opening, before the first `## ` heading, because "first reply" means
before any work starts. `tun-feedback` already had this wording; the other eight user
skills and the three dev skills now state theirs in the same shape.

Stdlib only. The control at the end deletes the line from a copy and moves it below the
first heading in another copy, and requires both to be reported.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARKER = "**Tier and cost, for the first reply:**"

passed = failed = 0


def chk(label: str, ok: bool, detail: str = "", n: int | None = None) -> bool:
    global passed, failed
    if n is not None and n == 0:
        ok, detail = False, "resolved 0 items"
    if ok:
        passed += 1
        print(f"  PASS {label}" + (f" ({n})" if n is not None else ""))
    else:
        failed += 1
        print(f"  FAIL {label}" + (f": {detail}" if detail else ""))
    return ok


def skills() -> list[pathlib.Path]:
    return sorted(ROOT.glob("skills/*/SKILL.md")) + sorted(ROOT.glob("skills/dev/*/SKILL.md"))


def problems(text: str) -> list[str]:
    """What is wrong with one skill's tier line. Empty means it is fine."""
    out = []
    count = text.count(MARKER)
    if count == 0:
        return ["no tier line"]
    if count > 1:
        out.append(f"{count} tier lines, one is the rule")
    line_at = text.index(MARKER)
    heading = text.find("\n## ")
    if heading != -1 and line_at > heading:
        out.append("the tier line is below the first section, so it is not in the first reply")
    tail = text[line_at + len(MARKER):].split("\n\n")[0]
    flat = " ".join(tail.split())
    if len(flat) < 40:
        out.append(f"the cost is too short to mean anything ({len(flat)} chars)")
    if not re.search(r"\bnone\b|\bTier [123]\b", flat):
        out.append("the line names neither a tier nor 'none'")
    return out


def main() -> int:
    found = skills()
    chk("skills were found at all", bool(found), n=len(found))
    bad = []
    for skill in found:
        why = problems(skill.read_text(encoding="utf-8"))
        if why:
            bad.append(f"{skill.parent.name}: {', '.join(why)}")
    chk("every skill states its tier and cost before the first section", not bad,
        "; ".join(bad[:4]), n=len(found))

    # the mutation controls: the two ways this rule actually breaks
    sample = ROOT / "skills" / "tun-publish" / "SKILL.md"
    text = sample.read_text(encoding="utf-8")
    chk("the sample skill is clean before it is mutated", not problems(text))

    deleted = re.sub(r"\*\*Tier and cost, for the first reply:\*\*.*?(?=\n)", "", text, count=1)
    chk("a deleted tier line is reported",
        problems(deleted) == ["no tier line"], str(problems(deleted)))

    # below the first section
    paragraphs = text.split("\n\n")
    tier_idx = next(i for i, para in enumerate(paragraphs) if MARKER in para)
    tier_para = paragraphs[tier_idx]
    moved = "\n\n".join(para for i, para in enumerate(paragraphs) if i != tier_idx)
    heading_start = moved.index("\n## ")
    heading_end = moved.index("\n", heading_start + 1) + 1   # end of that heading line
    moved = (moved[:heading_end] + "\n" + tier_para + "\n" + moved[heading_end:])
    why = problems(moved)
    chk("a tier line moved below the first section is reported",
        any("not in the first reply" in w for w in why), str(why))

    # present, in place, but empty of content
    thin_paras = list(paragraphs)
    thin_paras[tier_idx] = MARKER + " Tier 1."
    thin = "\n\n".join(thin_paras)
    why = problems(thin)
    chk("a line that names a tier but says nothing is reported",
        any("too short" in w or "neither" in w for w in why), str(why))

    print("\n" + "-" * 60)
    print(f"PASS: {passed}  FAIL: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
