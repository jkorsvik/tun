#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Prove any AI agent pointed at the webpage or the repo finds the install recipe and verbs.

Covers four things that otherwise drift silently:

1. `llms.txt` and `START-HERE.md` exist, name every supported `--tool` target (including
   `auto`, `claude`, `agents`, `cursor`, `windsurf` and the Windows `py -3` spelling),
   name every user-facing `tun-*` verb in `skills/`, and tell the agent to introduce Tún
   and keep the folder boundary.
2. `templates/showcase.html` (which becomes `https://jkorsvik.github.io/tun/index.html`)
   places the AI bootstrap panel *before* `{{CARDS}}` so web-fetching agents see it within
   the first few kilobytes instead of truncating inside megabytes of base64 screenshots,
   and `.github/workflows/pages.yml` publishes `llms.txt` and `START-HERE.md` to `_site/`.
3. `plugin/manifest.json` lists every skill directory in `skills/` and `skills/dev/` so a
   newly added verb or contributor skill cannot be omitted from the manifest.
4. Mutation controls prove each check fails when a verb, manifest entry or bootstrap block
   is removed.

Stdlib only, no browser.

    python3 tests/test_agent_bootstrap.py
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECKS = 0
FAILURES: list[str] = []


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    mark = "\u2713" if ok else "\u2717"
    print(f"  {mark} {what}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


def project_verbs() -> list[str]:
    return sorted(
        p.name for p in (ROOT / "skills").iterdir()
        if p.is_dir() and p.name != "dev" and (p / "SKILL.md").is_file()
    )


def dev_skills() -> list[str]:
    return sorted(
        p.name for p in (ROOT / "skills" / "dev").iterdir()
        if p.is_dir() and (p / "SKILL.md").is_file()
    )


def missing_verbs(text: str, verbs: list[str]) -> list[str]:
    return [v for v in verbs if v not in text]


def manifest_missing(manifest_doc: dict, want: set[str]) -> tuple[list[str], list[str]]:
    listed = {item["name"] for item in manifest_doc.get("contents", {}).get("skills", [])}
    return sorted(want - listed), sorted(listed - want)


def showcase_bootstrap_ok(html_text: str) -> bool:
    cards_at = html_text.find("{{CARDS}}")
    guide_at = html_text.find('class="agent-guide"')
    llms_at = html_text.find("llms.txt")
    return 0 < guide_at < cards_at and 0 < llms_at < cards_at and guide_at < 25_000


def main() -> int:
    verbs = project_verbs()
    devs = dev_skills()
    chk(len(verbs) >= 11, "discovered project verb skills", f"got {len(verbs)}")
    chk(len(devs) >= 6, "discovered dev skills", f"got {len(devs)}")

    llms_path = ROOT / "llms.txt"
    start_path = ROOT / "START-HERE.md"
    copilot_path = ROOT / ".github" / "copilot-instructions.md"
    pages_path = ROOT / ".github" / "workflows" / "pages.yml"
    showcase_path = ROOT / "templates" / "showcase.html"
    strings_path = ROOT / "templates" / "i18n" / "showcase.strings"
    manifest_path = ROOT / "plugin" / "manifest.json"

    for p in (llms_path, start_path, copilot_path, pages_path, showcase_path, manifest_path):
        chk(p.is_file(), f"{p.relative_to(ROOT)} exists")

    llms = llms_path.read_text(encoding="utf-8")
    start = start_path.read_text(encoding="utf-8")
    copilot = copilot_path.read_text(encoding="utf-8")
    pages = pages_path.read_text(encoding="utf-8")
    showcase = showcase_path.read_text(encoding="utf-8")
    strings = strings_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    print("\n1. llms.txt and START-HERE.md cover every tool target and every verb")
    for label, body in (("llms.txt", llms), ("START-HERE.md", start)):
        gone = missing_verbs(body, verbs)
        chk(not gone, f"{label} names all {len(verbs)} user-facing verbs", ", ".join(gone))
        for token in ("setup.py --tool auto", "setup.py --tool claude",
                      "setup.py --tool agents", "setup.py --tool cursor",
                      "setup.py --tool windsurf", "py -3",
                      "https://github.com/jkorsvik/tun", "https://jkorsvik.github.io/tun/"):
            chk(token in body, f"{label} includes {token!r}")

    chk("AGENTS.md" in copilot and "START-HERE.md" in copilot and "llms.txt" in copilot,
        ".github/copilot-instructions.md routes Copilot to START-HERE.md, llms.txt and AGENTS.md")

    print("\n2. the Explorer webpage surfaces AI bootstrap before the embedded cards")
    chk(showcase_bootstrap_ok(showcase),
        "showcase.html places .agent-guide and llms.txt link before {{CARDS}} (< 25 KB)")
    chk("setup.py --tool auto" in strings and "tun-new" in strings and "py -3" in strings,
        "showcase.strings carries the cross-platform setup command and verbs in both languages")
    chk("llms.txt" in pages and "START-HERE.md" in pages,
        "pages.yml copies llms.txt and START-HERE.md to the published site")

    print("\n3. plugin/manifest.json stays in lockstep with skills/ and skills/dev/")
    want_all = set(verbs) | set(devs)
    absent, extra = manifest_missing(manifest, want_all)
    chk(not absent and not extra,
        "plugin/manifest.json lists every project and dev skill",
        f"missing={absent}, extra={extra}")
    for entry in manifest["contents"]["skills"]:
        skill_md = ROOT / entry["path"] / "SKILL.md"
        chk(skill_md.is_file(), f"manifest skill path resolves: {entry['path']}")

    print("\n4. mutation controls prove each check can fail")
    chk(missing_verbs(llms.replace("tun-review", "removed"), verbs) == ["tun-review"],
        "mutation a: dropping a verb from llms.txt is caught")
    chk(not showcase_bootstrap_ok(showcase.replace('class="agent-guide"', 'class="other"')),
        "mutation b: removing .agent-guide from showcase.html is caught")
    mutated_manifest = {
        "contents": {"skills": [s for s in manifest["contents"]["skills"] if s["name"] != "tun-host"]}
    }
    chk(manifest_missing(mutated_manifest, want_all) == (["tun-host"], []),
        "mutation c: omitting a skill from plugin/manifest.json is caught")

    print()
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} of {CHECKS} checks failed")
        return 1
    print(f"PASS: {CHECKS} of {CHECKS} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
