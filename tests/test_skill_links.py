#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_skill_links.py — prove setup.py's skill installer never destroys someone else's skill.

install_skills() decides whether to replace or preserve a path in ~/.raiwork/skills. Getting
that wrong deletes the user's only copy of a skill they wrote, or silently moves authority
for a global tool into this project checkout. Both happened during development, which is why
these branches are pinned by tests.

It also installs by COPY rather than by symlink, and the difference is load-bearing: a
symlinked skill is the same file as a tracked file in this checkout, so editing the skill
edits the repo on whatever branch is checked out. The copy path, the drift report that keeps
a copy from going stale unnoticed, and the migration from an older symlinked install are all
pinned here too.

Stdlib only, like the rest of the repo. Runs against a throwaway HOME; touches nothing real.

    python3 tests/test_skill_links.py
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
MARKER = ".installed-by-tun"

passed = failed = 0


def chk(label: str, got, want) -> None:
    global passed, failed
    if got == want:
        print(f"  PASS {label}")
        passed += 1
    else:
        trim = lambda v: (r if len(r := repr(v)) <= 120 else r[:117] + "...")
        print(f"  FAIL {label}: got {trim(got)}, wanted {trim(want)}")
        failed += 1


def run_setup(home: pathlib.Path, *flags: str) -> str:
    """Run setup.py with HOME redirected. --check would not install, so run it for real."""
    env = dict(os.environ, HOME=str(home))
    r = subprocess.run([sys.executable, str(REPO / "setup.py"), *flags],
                       capture_output=True, text=True, env=env, cwd=REPO)
    return r.stdout + r.stderr


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        skills = tmp / ".raiwork" / "skills"
        skills.mkdir(parents=True)

        print("--- 1. fresh: every repo skill is installed as a copy, both groups ---")
        out = run_setup(tmp)
        want = {p.name for p in (REPO / "skills").iterdir() if p.is_dir() and p.name != "dev"}
        want |= {p.name for p in (REPO / "skills" / "dev").iterdir() if p.is_dir()}
        chk("all installed", {p.name for p in skills.iterdir()}, want)
        chk("installed as a real directory, not a symlink",
            (skills / "hotshot").is_dir() and not (skills / "hotshot").is_symlink(), True)
        chk("marker written so a later run knows it is ours",
            (skills / "hotshot" / MARKER).is_file(), True)
        chk("marker names its source",
            str(REPO / "skills" / "dev" / "hotshot") in (skills / "hotshot" / MARKER).read_text(), True)
        chk("supporting file copied",
            (skills / "writing-for-agents" / "SKILL-MECHANICS.md").is_file(), True)
        chk("no skill is a symlink",
            [p.name for p in skills.iterdir() if p.is_symlink()], [])

        print("--- 2. idempotent: second run reports already installed, rewrites nothing ---")
        stamp = (skills / "hotshot" / "SKILL.md").stat().st_mtime_ns
        out = run_setup(tmp)
        chk("file not rewritten", (skills / "hotshot" / "SKILL.md").stat().st_mtime_ns, stamp)
        chk("says already installed", "already installed" in out, True)

        print("--- 3. user's own real directory: MUST survive ---")
        own = skills / "dashboard-new"
        shutil.rmtree(own)
        own.mkdir()
        (own / "SKILL.md").write_text("mine")
        (own / "NOTES.md").write_text("keep me")
        out = run_setup(tmp)
        chk("content untouched", (own / "SKILL.md").read_text(), "mine")
        chk("extra file kept", (own / "NOTES.md").is_file(), True)
        chk("warns about the collision", "already have a skill with this name" in out, True)

        print("--- 4. foreign symlink (e.g. the dotfiles repo's): MUST survive ---")
        foreign_src = tmp / "dotfiles" / "skills" / "magnus-review"
        foreign_src.mkdir(parents=True)
        (foreign_src / "SKILL.md").write_text("from dotfiles")
        link = skills / "magnus-review"
        shutil.rmtree(link)
        link.symlink_to(foreign_src, target_is_directory=True)
        out = run_setup(tmp)
        chk("still points at dotfiles", os.readlink(link), str(foreign_src))
        chk("content is dotfiles'", (link / "SKILL.md").read_text(), "from dotfiles")
        chk("reports who provides it", "provided by" in out, True)
        # Must not appear in the "To fix" list: deferring to another owner is correct, not
        # a problem. Scoped to this skill — an unrelated collision from step 3 is still listed.
        chk("no fix suggested for it",
            any("magnus-review" in l for l in out.splitlines() if l.strip().startswith("-")), False)

        print("--- 5. our own earlier copy (marker present): refreshed, not preserved ---")
        copied = skills / "dashboard-verify"
        (copied / "STALE.md").write_text("should not survive a refresh")
        run_setup(tmp)
        chk("still a copy", (copied.is_dir() and not copied.is_symlink()), True)
        chk("stale file gone", (copied / "STALE.md").exists(), False)
        chk("marker still there", (copied / MARKER).is_file(), True)

        print("--- 6. an older symlinked install of ours: migrated to a copy ---")
        # Installs made before this change point straight into the repo. They must be
        # converted, not left alone, or editing the skill keeps editing the working tree.
        linked = skills / "dashboard-help"
        shutil.rmtree(linked)
        linked.symlink_to(REPO / "skills" / "dashboard-help", target_is_directory=True)
        out = run_setup(tmp)
        chk("no longer a symlink", linked.is_symlink(), False)
        chk("is a copy with our marker", (linked / MARKER).is_file(), True)
        chk("says it migrated", "migrated from symlink to copy" in out, True)

        print("--- 7. a stale copy is reported by --check, not silently accepted ---")
        (skills / "dashboard-new").exists()  # occupied by the user's own dir from step 3
        edited = skills / "dashboard-verify" / "SKILL.md"
        edited.write_text(edited.read_text() + "\n<!-- edited in place -->\n")
        out = run_setup(tmp, "--check")
        chk("reports the drift", "stale" in out, True)
        chk("tells you how to fix it", "python3 setup.py" in out, True)
        chk("--check changed nothing", "<!-- edited in place -->" in edited.read_text(), True)
        run_setup(tmp)
        chk("a real run repairs it", "<!-- edited in place -->" in edited.read_text(), False)

        print("--- 8. --link is opt-in and does what it says ---")
        out = run_setup(tmp, "--link")
        chk("now a symlink into the repo",
            os.readlink(skills / "dashboard-verify"), str(REPO / "skills" / "dashboard-verify"))
        chk("warns that edits hit the repo", "edits here change the repo" in out, True)
        chk("the user's own skill still survives --link",
            (skills / "dashboard-new" / "NOTES.md").is_file(), True)
        chk("the foreign link still survives --link",
            os.readlink(skills / "magnus-review"), str(foreign_src))

        print()
        print(f"PASS: {passed}  FAIL: {failed}")
        return 1 if failed else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
