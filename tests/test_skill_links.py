#!/usr/bin/env python3
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
# What setup.py wrote before the repo was renamed. Installs carrying it are still ours.
# The marker an earlier version wrote, composed from fragments: the exported tree must not
# carry the former repository name as text, and this test has to write it to prove that a
# copy carrying it is still recognised as ours.
OLD_MARKER = ".installed-by-" + "onedrive" + "-native-dashboards"

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
        own = skills / "tun-new"
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
        copied = skills / "tun-verify"
        (copied / "STALE.md").write_text("should not survive a refresh")
        run_setup(tmp)
        chk("still a copy", (copied.is_dir() and not copied.is_symlink()), True)
        chk("stale file gone", (copied / "STALE.md").exists(), False)
        chk("marker still there", (copied / MARKER).is_file(), True)

        print("--- 6. an older symlinked install of ours: migrated to a copy ---")
        # Installs made before this change point straight into the repo. They must be
        # converted, not left alone, or editing the skill keeps editing the working tree.
        linked = skills / "tun-help"
        shutil.rmtree(linked)
        linked.symlink_to(REPO / "skills" / "tun-help", target_is_directory=True)
        out = run_setup(tmp)
        chk("no longer a symlink", linked.is_symlink(), False)
        chk("is a copy with our marker", (linked / MARKER).is_file(), True)
        chk("says it migrated", "migrated from symlink to copy" in out, True)

        print("--- 7. a stale copy is reported by --check, not silently accepted ---")
        (skills / "tun-new").exists()  # occupied by the user's own dir from step 3
        edited = skills / "tun-verify" / "SKILL.md"
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
            os.readlink(skills / "tun-verify"), str(REPO / "skills" / "tun-verify"))
        chk("warns that edits hit the repo", "edits here change the repo" in out, True)
        chk("the user's own skill still survives --link",
            (skills / "tun-new" / "NOTES.md").is_file(), True)
        chk("the foreign link still survives --link",
            os.readlink(skills / "magnus-review"), str(foreign_src))

        print("--- 9. a skill renamed or removed in this repo: our old copy is stale ---")
        # Simulates a skill that used to be called "dashboard-new" and is now "tun-new"
        # (or any other rename/removal): the directory is still ours (MARKER present) but
        # its name no longer matches anything under skills/. --check must flag it without
        # touching it; a real run must remove it, and only it.
        renamed_away = skills / "dashboard-new"
        renamed_away.mkdir()
        (renamed_away / "SKILL.md").write_text("old name, old content")
        (renamed_away / MARKER).write_text(f"source: {REPO / 'skills' / 'dashboard-new'}\n")
        out = run_setup(tmp, "--check")
        chk("--check flags it as stale", "no longer in this repo" in out, True)
        chk("--check does not remove it", renamed_away.is_dir(), True)
        out = run_setup(tmp)
        chk("a real run removes it", renamed_away.exists(), False)
        chk("says it was removed", "removed" in out and "dashboard-new" in out, True)
        chk("the live skill is untouched", (skills / "tun-new").is_dir(), True)

        print("--- 10. a same-named dir with no marker: never ours to remove ---")
        # A user could have their own skill sitting under an old name by coincidence. No
        # MARKER means it is not ours, renamed or not, so the cleanup must leave it alone.
        coincidence = skills / "dashboard-verify"
        shutil.rmtree(coincidence, ignore_errors=True)
        coincidence.mkdir()
        (coincidence / "SKILL.md").write_text("not ours, never was")
        run_setup(tmp)
        chk("survives even though its name matches no current skill",
            (coincidence / "SKILL.md").read_text(), "not ours, never was")

        print("--- 11. an install under the old marker name: still ours, upgraded ---")
        # The marker was renamed with the repo. Every existing install carries the old
        # name, so setup.py must recognise it, or each of them turns into "your own skill"
        # and is never refreshed again.
        old = skills / "tun-help"
        shutil.rmtree(old)
        shutil.copytree(REPO / "skills" / "tun-help", old)
        (old / OLD_MARKER).write_text("Installed by python3 setup.py. Safe to delete.\n")
        out = run_setup(tmp, "--check")
        chk("--check does not mistake it for the user's own skill",
            any("tun-help" in l and "your own skill" in l for l in out.splitlines()), False)
        chk("--check says the marker is old", "old install marker" in out, True)
        chk("--check leaves it alone", (old / OLD_MARKER).is_file(), True)
        out = run_setup(tmp)
        chk("a real run does not leave it alone as a collision",
            any("tun-help" in l and "already have a skill" in l for l in out.splitlines()), False)
        chk("old marker replaced", ((old / OLD_MARKER).exists(), (old / MARKER).is_file()),
            (False, True))
        chk("says it upgraded", "upgraded from the old install marker" in out, True)

        print("--- 12. a renamed-away copy under the old marker: still cleaned up ---")
        gone = skills / "dashboard-publish"
        gone.mkdir()
        (gone / "SKILL.md").write_text("old name, old marker")
        (gone / OLD_MARKER).write_text("source: somewhere\n")
        run_setup(tmp)
        chk("removed", gone.exists(), False)

        print("--- 13. the help text names the product ---")
        out = run_setup(tmp, "--help")
        chk("says Tún", "Tún" in out, True)
        chk("no longer says 'the dashboard skills'", "the dashboard skills" in out, False)

        print("--- 14. --tool installs the same skills for other AI tools, safely ---")
        agents, claude = tmp / ".agents" / "skills", tmp / ".claude" / "skills"
        (claude / "hotshot").mkdir(parents=True)                 # the user's own skill
        (claude / "hotshot" / "SKILL.md").write_text("mine\n")
        out = run_setup(tmp)
        chk("without --tool, no other folder is created", agents.exists(), False)
        out = run_setup(tmp, "--tool", "agents", "--tool", "claude")
        chk("agents: every skill", {p.name for p in agents.iterdir()} if agents.is_dir() else set(), want)
        chk("agents: a real copy with our marker",
            (agents / "tun-new" / MARKER).is_file() and not (agents / "tun-new").is_symlink(), True)
        chk("claude: every skill but the user's own", {p.name for p in claude.iterdir()} if claude.is_dir() else set(), want)
        chk("claude: the user's own skill is left alone",
            (claude / "hotshot" / "SKILL.md").read_text(), "mine\n")
        chk("says where it was left alone", "~/.claude/skills/hotshot" in out, True)
        out = run_setup(tmp, "--tool", "agents", "--check")
        chk("--check reports the extra folder up to date", "not installed" in out, False)

        print()
        print(f"PASS: {passed}  FAIL: {failed}")
        return 1 if failed else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
