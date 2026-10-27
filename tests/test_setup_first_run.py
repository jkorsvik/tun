#!/usr/bin/env python3
"""test_setup_first_run.py — a stranger's `python3 setup.py` works without RAIWork.

The repo is public. Someone who clones it has no RAIWork, so setup.py must not fail on it,
must not tell them to install it, and must not create ~/.raiwork on their machine. They
name their tool with --tool instead. A RAIWork user's run stays as it was.

Three runs of the real setup.py, each with a throwaway HOME:

  1. no ~/.raiwork, no --tool  -> exit 0, a hint to use --tool, no ~/.raiwork, no FAIL
  2. no ~/.raiwork, --tool claude -> skills in ~/.claude/skills, still no ~/.raiwork
  3. ~/.raiwork exists          -> skills in ~/.raiwork/skills, as before
  4. a stale --tool claude copy -> --check advises "--tool claude", and that repairs it

Stdlib only.

    python3 tests/test_setup_first_run.py
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]

passed = failed = 0


def chk(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS {label}")
    else:
        failed += 1
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def run(home: pathlib.Path, *args: str) -> tuple[int, str]:
    env = dict(os.environ, HOME=str(home), NO_COLOR="1")
    r = subprocess.run([sys.executable, str(REPO / "setup.py"), *args],
                       capture_output=True, text=True, env=env, timeout=300, cwd=REPO)
    return r.returncode, re.sub(r"\033\[[0-9;]*m", "", r.stdout + r.stderr)


def main() -> int:
    print("setup.py first run without RAIWork")
    print("─" * 62)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="tun-first-run-"))
    try:
        print("--- 1. no RAIWork, no --tool ---")
        home = tmp / "h1"
        home.mkdir()
        rc, out = run(home)
        chk("exits 0", rc == 0, f"rc={rc}\n{out[-600:]}")
        chk("creates no ~/.raiwork", not (home / ".raiwork").exists())
        chk("says how to install the skills (--tool claude)", "--tool claude" in out)
        chk("does not tell them to install RAIWork", "Install RAIWork" not in out)
        chk("no FAIL line", not re.search(r"^\s*FAIL\b", out, re.M),
            "\n".join(ln for ln in out.splitlines() if "FAIL" in ln)[:300])
        chk("does not say 'Open RAIWork'", "Open RAIWork" not in out)

        print("--- 2. no RAIWork, --tool claude ---")
        home = tmp / "h2"
        home.mkdir()
        rc, out = run(home, "--tool", "claude")
        chk("exits 0", rc == 0, f"rc={rc}\n{out[-600:]}")
        chk("tun-new installed for Claude Code",
            (home / ".claude" / "skills" / "tun-new" / "SKILL.md").is_file())
        chk("still creates no ~/.raiwork", not (home / ".raiwork").exists())

        print("--- 3. RAIWork installed ---")
        home = tmp / "h3"
        (home / ".raiwork").mkdir(parents=True)
        rc, out = run(home)
        chk("tun-new installed for RAIWork",
            (home / ".raiwork" / "skills" / "tun-new" / "SKILL.md").is_file(), out[-400:])
        chk("no hint to pick a tool", "no AI tool chosen" not in out)
        print("--- 4. a stale copy for another tool: the advice repairs it ---")
        home = tmp / "h4"
        home.mkdir()
        run(home, "--tool", "claude")
        skill = home / ".claude" / "skills" / "tun-new" / "SKILL.md"
        original = skill.read_text(encoding="utf-8")
        skill.write_text(original + "\nlocal change\n", encoding="utf-8")
        rc, out = run(home, "--tool", "claude", "--check")
        advice = [ln.strip()[2:] for ln in out.splitlines() if ln.strip().startswith("- python3 setup.py")]
        chk("--check reports the copy as stale", "stale" in out)
        chk("the advice names the tool", "python3 setup.py --tool claude" in advice, str(advice))
        if advice:
            run(home, *advice[0].split()[2:])
        chk("following the advice repairs the copy",
            skill.read_text(encoding="utf-8") == original)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("─" * 62)
    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
