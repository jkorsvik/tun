#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""test_setup_browser_probe.py — setup.py finds Playwright where it is, and never FAILs on it.

Playwright is an optional extra that normally lives in the repo's uv environment, not in
the python3 that runs setup.py. setup.py used to import it in-process only, so it printed
"FAIL playwright" on a machine where `uv run --extra verify` renders fine.

Three cases, with the interpreter's own Playwright hidden by a shadow package on
PYTHONPATH (it raises ImportError, also in every child Python), and `uv` replaced by a
spy script on PATH that logs its arguments and exits with a chosen code:

  1. uv's environment can render  -> OK, "(the uv environment)", asked with --no-sync
  2. uv's environment cannot      -> WARN with the install command, never FAIL
  3. no uv environment at all     -> WARN, and uv is never asked (it would create .venv)

Stdlib only, throwaway HOME. The spy is a POSIX shell script, so on Windows this
reports SKIP.

    python3 tests/test_setup_browser_probe.py
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
FIX = "uv sync --extra verify && uv run playwright install chromium"

passed = failed = 0


def chk(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS {label}")
    else:
        failed += 1
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def playwright_line(out: str) -> str:
    """The status line for Playwright, colour codes removed, or "" if there is none."""
    plain = re.sub(r"\033\[[0-9;]*m", "", out)
    lines = [ln.strip() for ln in plain.splitlines()
             if re.match(r"\s*(OK|WARN|FAIL)\b.*playwright", ln)]
    return lines[0] if lines else ""


def main() -> int:
    print("setup.py browser probe: this Python, then the uv environment")
    print("─" * 62)
    if os.name == "nt":
        print("  SKIP the uv spy is a POSIX shell script. Run this on macOS or Linux.")
        print("0 passed, 0 failed, 1 skipped")
        return 0

    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        (tmp / "home" / ".raiwork" / "skills").mkdir(parents=True)
        shadow = tmp / "shadow" / "playwright"
        shadow.mkdir(parents=True)
        (shadow / "__init__.py").write_text('raise ImportError("hidden by the test")\n')
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        log = tmp / "uv.log"
        spy = bin_dir / "uv"
        spy.write_text(f'#!/bin/sh\necho "$*" >> "{log}"\nexit ${{FAKE_UV_RC:-1}}\n')
        spy.chmod(0o755)
        venv_marker = tmp / "env"
        venv_marker.mkdir()

        def run(rc: int, with_env: bool) -> str:
            env = {k: v for k, v in os.environ.items()
                   if k not in ("UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV")}
            env.update(HOME=str(tmp / "home"), PYTHONPATH=str(tmp / "shadow"),
                       PATH=f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
                       FAKE_UV_RC=str(rc))
            if with_env:
                env["UV_PROJECT_ENVIRONMENT"] = str(venv_marker)
            log.unlink(missing_ok=True)
            # A copy of setup.py, so REPO/.venv of this checkout cannot answer for it.
            work = tmp / "repo"
            shutil.rmtree(work, ignore_errors=True)
            work.mkdir()
            shutil.copy2(REPO / "setup.py", work / "setup.py")
            (work / "skills" / "dev").mkdir(parents=True)
            r = subprocess.run([sys.executable, str(work / "setup.py"), "--check"],
                               capture_output=True, text=True, env=env, timeout=300)
            return r.stdout + r.stderr

        # control: the shadow really hides Playwright from a child Python
        r = subprocess.run([sys.executable, "-c", "import playwright"], capture_output=True,
                           env=dict(os.environ, PYTHONPATH=str(tmp / "shadow")))
        chk("control: the shadow package hides Playwright", r.returncode != 0)

        print("--- 1. the uv environment can render ---")
        out = run(0, with_env=True)
        line = playwright_line(out)
        chk("reports OK", line.startswith("OK"), line)
        chk("says it came from the uv environment", "uv environment" in line, line)
        asked = log.read_text() if log.exists() else ""
        chk("asked uv with --no-sync (installs nothing)", "run --no-sync" in asked, asked[:120])

        print("--- 2. the uv environment cannot render ---")
        out = run(1, with_env=True)
        line = playwright_line(out)
        chk("reports WARN, not FAIL", line.startswith("WARN"), line)
        chk("no FAIL line for playwright anywhere", not re.search(r"FAIL.*playwright", out))
        chk("gives the install command", FIX in out)

        print("--- 3. no uv environment exists ---")
        out = run(0, with_env=False)
        line = playwright_line(out)
        chk("reports WARN", line.startswith("WARN"), line)
        chk("uv was never asked (it would create a .venv)", not log.exists(),
            log.read_text()[:120] if log.exists() else "")
        chk("--check created no .venv", not (tmp / "repo" / ".venv").exists())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("─" * 62)
    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
