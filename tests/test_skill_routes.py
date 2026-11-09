#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Is every artefact kind reachable from a skill, and do the skills still name real flags?

A builder that no SKILL.md names is an artefact nobody is routed to. It passes every other
gate in this repository: it builds, it has an example, a suite measures it, the ROADMAP says
"done". Nothing fails, and the person who asks "can this show what overlaps" is told no.

That happened. Five builders with examples and suites were named by no skill at all
(`build_index`, `build_onepager`, `build_slide_deck`, `build_survey_dashboard`,
`build_timeline`), and the prose in `skills/tun-review/SKILL.md` referred to "the timeline and
slide-deck builders" as things the reader already had a route to.

Two checks, and both are needed:

  * every `tools/build_*.py` is named by at least one skill, except a debt list that can only
    shrink. An entry that goes stale (someone adds the route) fails, so the list cannot rot;
  * every `--flag` a skill prints for a builder exists in that builder's own argparse. A route
    that documents a flag the tool never had is worse than no route: it is an instruction that
    fails in the hands of the reader.

`tun-host` has no builder, so the last section also pins its hand-offs from `tun-help` and
`tun-publish`, its architecture link, and the hosting and security boundaries it must keep.

Stdlib only, no browser.

    python3 tests/test_skill_routes.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
TOOLS = ROOT / "tools"

# Builders deliberately named by no skill: they are not artefacts, they are called by the
# others. A reason, not a shrug.
NOT_A_ROUTE = {
    "build_size.py": "a post-build size check the builders call, never something a user asks for",
    "build_stamp.py": "the provenance clock the builders share, never invoked on its own",
}

FLAG = re.compile(r"(--[a-z][a-z0-9-]+)")

CHECKS = 0
FAILURES: list[str] = []


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


def builders() -> list[pathlib.Path]:
    return sorted(p for p in TOOLS.glob("build_*.py"))


def skill_files() -> list[pathlib.Path]:
    return sorted(SKILLS.glob("*/SKILL.md"))


def route_text(name: str, texts: dict[pathlib.Path, str]) -> list[tuple[pathlib.Path, str]]:
    """Every skill that names this builder, with the fenced bash blocks that name it."""
    found = []
    for path, text in texts.items():
        if name not in text:
            continue
        for block in re.findall(r"```bash\n(.*?)```", text, re.S):
            if name in block:
                found.append((path, block))
    return found


def hosting_route_gaps(help_text: str, publish_text: str) -> list[str]:
    """The two hand-offs that make the non-builder hosting skill reachable."""
    gaps = []
    if "`tun-host`" not in help_text:
        gaps.append("tun-help does not route hosting requests to tun-host")
    if "`tun-host`" not in publish_text:
        gaps.append("tun-publish does not hand real web origins and backends to tun-host")
    return gaps


def flags_of(builder: pathlib.Path) -> set[str]:
    """The long options the builder's argparse actually declares.

    `--lang` is added by the shared helper rather than by the builder, so a scan for
    add_argument() alone would call a real flag imaginary and the route would be "fixed" to
    stop mentioning the one option every builder has.
    """
    source = builder.read_text(encoding="utf-8")
    found = set(re.findall(r'add_argument\("(--[a-z][a-z0-9-]*)"', source))
    if "i18n.add_lang_argument(" in source:
        found.add("--lang")
    return found


def main() -> int:
    texts = {p: p.read_text(encoding="utf-8") for p in skill_files()}
    found_builders = builders()

    print("\n1. the scan sees the real tree, and would notice if it did not")
    chk(len(texts) >= 8, "every skill file was read", f"{len(texts)} file(s)")
    chk(len(found_builders) >= 15, "every builder was found", f"{len(found_builders)} builder(s)")
    chk(all(len(t) > 200 for t in texts.values()), "no skill file came back empty")

    print("\n2. every builder is reachable from a skill")
    unrouted = [b.name for b in found_builders
                if b.name not in NOT_A_ROUTE and not route_text(b.name, texts)]
    chk(not unrouted, "no artefact kind is missing a route", ", ".join(unrouted))
    for b in found_builders:
        if b.name in NOT_A_ROUTE:
            continue
        routes = route_text(b.name, texts)
        chk(bool(routes), f"{b.name} is named by a skill with a runnable block",
            "named in prose but in no bash block" if routes == [] else "")

    print("\n3. the debt list is still debt")
    for name, reason in NOT_A_ROUTE.items():
        path = TOOLS / name
        chk(path.exists(), f"{name} still exists", reason)
        chk(not route_text(name, texts),
            f"{name} is still named by no skill, so its entry is still needed", reason)

    print("\n4. every flag a skill prints exists in that builder")
    checked = 0
    for b in found_builders:
        declared = flags_of(b)
        if not declared:
            continue
        for path, block in route_text(b.name, texts):
            for flag in FLAG.findall(block):
                checked += 1
                if flag not in declared:
                    chk(False, f"{b.name}: {path.parent.name} documents a real flag",
                        f"{flag} is not in {b.name}'s argparse")
    chk(checked >= 40, "the flag scan found the routes it was meant to read", f"{checked} flag(s)")

    print("\n5. the checks would fail if the routes went away")
    # A builder nobody names must be reported.
    probe = TOOLS / "build_zzz_probe.py"
    probe.write_text("print()\n", encoding="utf-8")
    try:
        seen = builders()
        unrouted = [p.name for p in seen
                    if p.name not in NOT_A_ROUTE and not route_text(p.name, texts)]
        chk("build_zzz_probe.py" in unrouted,
            "a new builder with no route is reported at once", str(unrouted[-2:]))
    finally:
        probe.unlink()

    # A route that disappears must be reported.
    victim = "build_cohort.py"
    stripped = {p: t.replace(victim, "build_the_thing") for p, t in texts.items()}
    unrouted = [b.name for b in found_builders
                if b.name not in NOT_A_ROUTE and not route_text(b.name, stripped)]
    chk(victim in unrouted, "deleting a route is reported", str(unrouted))

    # An empty skill tree must fail loudly rather than pass vacuously.
    chk(not route_text("build_cohort.py", {}), "an empty skill tree routes nothing")

    print("\n6. hosting requests reach tun-host, with the app boundary intact")
    help_path = SKILLS / "tun-help" / "SKILL.md"
    publish_path = SKILLS / "tun-publish" / "SKILL.md"
    host_path = SKILLS / "tun-host" / "SKILL.md"
    doc_path = ROOT / "docs" / "35-hosting-and-functional-apps.md"
    help_text = texts[help_path]
    publish_text = texts[publish_path]
    host_text = host_path.read_text(encoding="utf-8")
    doc_text = doc_path.read_text(encoding="utf-8")
    chk(not hosting_route_gaps(help_text, publish_text),
        "tun-help and tun-publish both hand hosting requests to tun-host",
        "; ".join(hosting_route_gaps(help_text, publish_text)))
    chk("../../docs/35-hosting-and-functional-apps.md" in host_text,
        "tun-host links its architecture and host checks")
    chk(all(target in doc_text for target in
            ("08-generic-artifact-model.md", "23-hosted-route-it-brief.md"))
        and "connected" in host_text,
        "the new guide preserves the existing artefact-model and hosted-route boundaries")
    chk(all(term in host_text for term in
            ("read-only snapshot", "Static interactive app", "Backend application", "Hybrid")),
        "tun-host names the snapshot, static, backend and hybrid routes")
    chk(all(host in doc_text for host in
            ("GitHub Pages", "Cloudflare static assets", "Azure Static Web Apps",
             "Ordinary static file server")),
        "the architecture covers the four static host shapes")
    chk(all(rule in doc_text for rule in
            ("The folder boundary remains for shared static data",
             "No hidden row-level security", "Nothing secret goes to the browser")),
        "the architecture keeps the access and secret boundaries explicit")
    chk("No server, backend framework, database or job runner enters the toolkit core" in doc_text,
        "the architecture keeps servers out of the toolkit core")

    stripped_help = help_text.replace("`tun-host`", "`tun-removed`")
    chk(hosting_route_gaps(stripped_help, publish_text) ==
        ["tun-help does not route hosting requests to tun-host"],
        "deleting the tun-help hand-off is reported")
    stripped_publish = publish_text.replace("`tun-host`", "`tun-removed`")
    chk(hosting_route_gaps(help_text, stripped_publish) ==
        ["tun-publish does not hand real web origins and backends to tun-host"],
        "deleting the tun-publish hand-off is reported")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failed of {CHECKS} checks:")
        for item in FAILURES:
            print(f"  - {item}")
        return 1
    print(f"{CHECKS} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
