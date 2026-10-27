#!/usr/bin/env python3
"""
test_hooks_are_live.py — prove the git hooks can actually run.

Stdlib only.

    python3 tests/test_hooks_are_live.py

Why this exists
---------------
`tools/hooks/pre-push` was committed without the execute bit. Git silently ignores a
hook it cannot execute: no warning, no error, no output. The hook was present, tracked,
readable, correct, and dead. It was found by chance, because the throwaway repo used to
test it had `chmod +x` applied to its own copy, so the test passed against a file that
was executable only in the test.

That is the whole bug class this repo keeps meeting: a gate that appears installed and
checks nothing. So the hooks need a gate of their own, and it has to assert the property
git actually uses — the recorded file mode in the index — not the presence of the file.

It also runs each hook against the exact stdin git supplies, and asserts the refusal, so
a hook that stops refusing is caught as well as a hook that cannot start.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
HOOKS = REPO / "tools" / "hooks"

passed = failed = 0


def chk(label, got, want):
    global passed, failed
    if got == want:
        print(f"  PASS {label}")
        passed += 1
    else:
        print(f"  FAIL {label}: got {got!r}, wanted {want!r}")
        failed += 1


def git(*args: str) -> str:
    """Run git with GIT_* scrubbed, so this behaves the same inside a hook as out of one.
    A hook exports GIT_DIR and GIT_INDEX_FILE, which override -C and would make these
    answers describe the wrong repository."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True, env=env).stdout.strip()


EXPECTED_HOOKS = ("pre-commit", "pre-push")

print("the hooks exist and git records them as executable")
# git stores the mode in the index. 100644 means git will refuse to run it, no matter
# what the working tree's permissions happen to be on this machine.
index = {}
for line in git("ls-files", "-s", "tools/hooks").splitlines():
    mode, _sha, _stage_path = line.split(None, 2)
    index[_stage_path.split("\t", 1)[1]] = mode

for name in EXPECTED_HOOKS:
    rel = f"tools/hooks/{name}"
    chk(f"{name} is tracked", rel in index, True)
    chk(f"{name} is mode 100755 in the index (git will run it)",
        index.get(rel), "100755")
    chk(f"{name} is executable in the working tree",
        os.access(HOOKS / name, os.X_OK), True)

print("\nthe integration branch is discovered, not hardcoded")
for name in EXPECTED_HOOKS:
    text = (HOOKS / name).read_text(encoding="utf-8")
    chk(f"{name} reads origin/HEAD", "refs/remotes/origin/HEAD" in text, True)
    # A hook that falls back to "allow" when origin/HEAD is unset protects nothing in a
    # fresh clone, which is exactly where protection is most likely to be missing.
    chk(f"{name} falls back to a branch name, not to allowing everything",
        "PROTECTED=main" in text, True)

print("\npre-push refuses every route to the integration branch")
sha = git("rev-parse", "HEAD")
base = git("rev-parse", "origin/main") or sha


def pre_push(remote_ref: str, local_sha: str = None) -> int:
    """Invoke pre-push with the stdin git actually sends:
    <local ref> <local sha> <remote ref> <remote sha>"""
    line = f"refs/heads/work {local_sha or sha} {remote_ref} {base}\n"
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(
        [str(HOOKS / "pre-push"), "origin", "https://example.com/x.git"],
        input=line, capture_output=True, text=True, cwd=str(REPO), env=env).returncode


ZERO = "0" * 40
chk("push to refs/heads/main is refused", pre_push("refs/heads/main") == 1, True)
chk("deleting main is refused", pre_push("refs/heads/main", ZERO) == 1, True)
chk("pushing a feature branch is allowed",
    pre_push("refs/heads/feat/thing"), 0)
chk("pushing a tag is allowed", pre_push("refs/tags/v1"), 0)

print("\npre-commit refuses a commit on the integration branch")
# Asserted by reading the guard rather than by making a commit: a test that commits to
# main to prove commits to main are blocked is one bug away from doing the thing it is
# checking against.
pc = (HOOKS / "pre-commit").read_text(encoding="utf-8")
chk("pre-commit compares HEAD's branch against the protected one",
    'if [ "$BRANCH" = "$PROTECTED" ]' in pc, True)
chk("pre-commit exits non-zero on that path",
    pc.split('if [ "$BRANCH" = "$PROTECTED" ]')[1].split("fi")[0].count("exit 1"), 1)
chk("pre-commit tells the user how to recover the staged work",
    "git switch -c" in pc, True)

print("\nsetup.py installs the hooks by pointing core.hooksPath at them")
setup = (REPO / "setup.py").read_text(encoding="utf-8")
chk("setup.py sets core.hooksPath", "core.hooksPath" in setup, True)
# hooksPath is per-repo config shared by every worktree, and it is relative, so a branch
# without tools/hooks/ has hooks "enabled" pointing at nothing and git treats that as no
# hooks, silently.
chk("setup.py points it at tools/hooks", "tools/hooks" in setup, True)

print("\n" + "-" * 66)
print(f"{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
