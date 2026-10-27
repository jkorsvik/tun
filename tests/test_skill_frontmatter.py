#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_skill_frontmatter.py — every SKILL.md must load in every harness, not just a forgiving one.

The open Agent Skills format (agentskills.io/specification) is read by Claude Code, Codex,
Gemini CLI, Cursor, GitHub Copilot, VS Code, Goose, OpenCode and dozens more. Its reference
validator (skills-ref) parses the frontmatter as strict YAML. On 2026-10-08 four of our
twelve skills failed it: an unquoted ": " inside a description is a YAML mapping error, and
a flow list in metadata is rejected. RAIWork's own loader is lenient, so nothing here noticed.
A strict harness would have dropped those skills without a word.

This gate re-implements the part of the spec and of strict YAML that our files touch, in the
stdlib, so it runs in the pre-commit hook with nothing installed:

  - frontmatter between two '---' lines; only the spec's keys at top level
  - name: required, lowercase letters, digits and single hyphens, at most 64, equal to the
    folder name
  - description: required, non-empty, at most 1024 characters
  - every value is a plain one-line scalar with no ': ', no ' #', no leading YAML indicator
    and no flow collection, OR it is double-quoted with no '"' or '\\' inside (RAIWork shows
    a double-quoted value without its quotes; it does not show a block scalar '>-' correctly,
    so block scafagfelle are refused too)
  - metadata: a map of string values, two-space indented

The self-test feeds known-bad frontmatter through the same checker and requires each one to
fail with its own message and alone, so a deleted rule cannot hide behind a neighbouring one.
For the full check, run the reference validator:

    uvx --from 'git+https://github.com/agentskills/agentskills#subdirectory=skills-ref' \\
        skills-ref validate skills/<name>

    python3 tests/test_skill_frontmatter.py
    python3 tests/test_skill_frontmatter.py --mutation-check
"""
from __future__ import annotations

import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SPEC_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
INDICATORS = tuple("[]{}&*!|>%@`'\"#,?:") + ("- ",)


def check_value(where: str, raw: str) -> tuple[str | None, str | None]:
    """Return (value, error) for one scalar as written after 'key: '."""
    if raw.startswith('"'):
        if len(raw) < 2 or not raw.endswith('"'):
            return None, f"{where}: double-quoted value is not closed on its line"
        inner = raw[1:-1]
        if '"' in inner or "\\" in inner:
            return None, f"{where}: a double-quoted value may not hold '\"' or '\\'"
        return inner, None
    if raw in (">", ">-", "|", "|-", ">+", "|+"):
        return None, f"{where}: block scafagfelle are not read correctly by every harness; use one double-quoted line"
    if raw.startswith(("[", "{")):
        return None, f"{where}: flow collections are refused by the reference validator; write a string"
    if raw.startswith(INDICATORS):
        return None, f"{where}: a plain value may not start with a YAML indicator; double-quote it"
    if ": " in raw or raw.endswith(":"):
        return None, f"{where}: a plain value may not contain ': ' (strict YAML reads a mapping); double-quote it"
    if " #" in raw:
        return None, f"{where}: a plain value may not contain ' #' (YAML reads a comment); double-quote it"
    return raw, None


def check_frontmatter(text: str, folder: str) -> list[str]:
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return ["no frontmatter between two '---' lines at the top"]
    errors: list[str] = []
    fields: dict[str, str] = {}
    lines = m.group(1).split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip():
            continue
        top = re.match(r"([A-Za-z][A-Za-z0-9_-]*):(?: (.*))?$", line)
        if not top:
            errors.append(f"line not understood as 'key: value': {line[:60]!r}")
            continue
        key, raw = top.group(1), (top.group(2) or "").strip()
        if key not in SPEC_KEYS:
            errors.append(f"key '{key}' is not in the Agent Skills spec")
            continue
        if key == "metadata":
            if raw:
                errors.append("metadata: must be a map on the following lines")
            while i < len(lines) and lines[i].startswith("  "):
                sub = re.match(r"  ([A-Za-z][A-Za-z0-9_-]*): (.+)$", lines[i])
                if not sub:
                    errors.append(f"metadata: line not understood as '  key: value': {lines[i][:60]!r}")
                else:
                    _, err = check_value(f"metadata.{sub.group(1)}", sub.group(2).strip())
                    if err:
                        errors.append(err)
                i += 1
            continue
        value, err = check_value(key, raw)
        if err:
            errors.append(err)
            while i < len(lines) and lines[i].startswith("  "):  # the refused block's own lines
                i += 1
        else:
            fields[key] = value or ""
    name = fields.get("name")
    if "name" not in fields and not any(e.startswith("name:") for e in errors):
        errors.append("name: required")
    elif name is not None:
        if not NAME.fullmatch(name) or len(name) > 64:
            errors.append(f"name: '{name}' must be lowercase letters, digits and single hyphens, at most 64")
        elif name != folder:
            errors.append(f"name: '{name}' must equal the folder name '{folder}'")
    if "description" not in fields and not any(e.startswith("description:") for e in errors):
        errors.append("description: required")
    elif "description" in fields:
        d = fields["description"]
        if not d.strip():
            errors.append("description: must not be empty")
        elif len(d) > 1024:
            errors.append(f"description: {len(d)} characters, the spec allows 1024")
    return errors


GOOD = '---\nname: demo\ndescription: "Do a thing: carefully. Use when asked."\n---\n'
SELF_TEST = [  # (frontmatter, folder, the one message it must produce)
    ("---\nname: demo\ndescription: Draw it in one file: who does what.\n---\n", "demo",
     "a plain value may not contain ': '"),
    ("---\nname: demo\ndescription: ok\nmetadata:\n  tags: [a, b]\n---\n", "demo",
     "flow collections are refused"),
    ("---\nname: demo\ndescription: >-\n  folded\n---\n", "demo", "block scafagfelle are not read"),
    ("---\nname: demo\ndescription: \"say \"hi\" now\"\n---\n", "demo", "may not hold '\"'"),
    ("---\nname: Demo\ndescription: ok\n---\n", "Demo", "must be lowercase"),
    ("---\nname: demo\ndescription: ok\n---\n", "other", "must equal the folder name"),
    ("---\nname: demo\ndescription: " + "x" * 1025 + "\n---\n", "demo", "the spec allows 1024"),
    ("---\nname: demo\ndescription: ok\ntitle: x\n---\n", "demo", "not in the Agent Skills spec"),
    ("---\nname: demo\n---\n", "demo", "description: required"),
    ("---\nname: demo\ndescription: see #3 now\n---\n", "demo", "may not contain ' #'"),
    ("# no frontmatter\n", "demo", "no frontmatter"),
    ("---\nname: demo\ndescription: \"never closed\n---\n", "demo", "is not closed on its line"),
    ("---\nname: demo\ndescription: *star\n---\n", "demo", "may not start with a YAML indicator"),
    ("---\nname: demo\ndescription: ok\njust words\n---\n", "demo", "line not understood as 'key: value'"),
    ("---\nname: demo\ndescription: ok\nmetadata: x\n---\n", "demo", "must be a map on the following lines"),
    ("---\nname: demo\ndescription: ok\nmetadata:\n  - a\n---\n", "demo",
     "line not understood as '  key: value'"),
    ("---\ndescription: ok\n---\n", "demo", "name: required"),
    ("---\nname: demo\ndescription: \"\"\n---\n", "demo", "must not be empty"),
]


def mutation_check() -> int:
    """Delete each rule in turn; the self-test must notice every one."""
    import subprocess, tempfile
    lines = pathlib.Path(__file__).read_text(encoding="utf-8").split("\n")
    end = next(k for k, l in enumerate(lines) if l.startswith("GOOD = "))
    rules = [k for k, l in enumerate(lines[:end]) if 'return None, f"' in l or "errors.append(" in l]
    survived = []
    with tempfile.TemporaryDirectory() as tmp:
        for k in rules:
            mutant = lines[:]
            indent = mutant[k][: len(mutant[k]) - len(mutant[k].lstrip())]
            mutant[k] = indent + ("return raw, None" if "return None" in mutant[k] else "pass")
            f = pathlib.Path(tmp) / "mutant.py"
            f.write_text("\n".join(mutant).replace(
                "REPO = pathlib.Path(__file__).resolve().parents[1]", f"REPO = pathlib.Path({str(REPO)!r})"))
            if subprocess.run([sys.executable, str(f)], capture_output=True).returncode == 0:
                survived.append(f"line {k + 1}: {lines[k].strip()[:70]}")
    print(f"rules deleted one at a time: {len(rules)}, noticed: {len(rules) - len(survived)}")
    for s in survived:
        print(f"  SURVIVED {s}")
    if not rules:
        print("  FAIL found no rules to mutate; the harness checked nothing")
        return 1
    return 1 if survived else 0


def main() -> int:
    if "--mutation-check" in sys.argv:
        return mutation_check()
    failed = 0
    print("self-test (each bad case fails alone, with its own message)")
    if check_frontmatter(GOOD, "demo"):
        print(f"  FAIL a valid frontmatter was refused: {check_frontmatter(GOOD, 'demo')}")
        failed += 1
    for text, folder, want in SELF_TEST:
        got = check_frontmatter(text, folder)
        ok = len(got) == 1 and want in got[0]
        print(f"  {'PASS' if ok else 'FAIL'} {want}" + ("" if ok else f"  (got {got})"))
        failed += not ok

    skills = sorted(p for p in (REPO / "skills").rglob("SKILL.md"))
    print(f"skills ({len(skills)} found)")
    if not skills:
        print("  FAIL no SKILL.md found; the gate checked nothing")
        return 1
    for p in skills:
        errs = check_frontmatter(p.read_text(encoding="utf-8"), p.parent.name)
        rel = p.relative_to(REPO)
        print(f"  {'PASS' if not errs else 'FAIL'} {rel}")
        for e in errs:
            print(f"       {e}")
        failed += bool(errs)
    print("✓ PASS" if not failed else f"✗ FAIL — {failed} problem(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
