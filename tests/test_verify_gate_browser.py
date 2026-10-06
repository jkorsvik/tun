#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_verify_gate_browser.py — a verify tool may not report success without a browser.

Both verify tools used to treat a missing Playwright as a warning: they printed
"⚠ render SKIPPED", then "✓ PASS — safe to publish", and exited 0. Every check that
needs a browser — does it render, did JS run, is the console clean, does a filter
re-render, what does the screenshot look like — was skipped, and the caller was told
the file was safe to send to a colleague. Playwright is an optional extra in
pyproject.toml, so a default install produced that verdict every single time.

A gate that reports success having never opened the file is worse than one that
reports nothing: it manufactures assurance. AGENTS.md rule 3 says the artefact must be
opened in a real browser before anything is published, and
skills/dashboard-verify/SKILL.md already said a skipped render is not a pass. The code
said the opposite of both.

This pins the branch shut. It does not need Playwright to be absent on this machine:
a shim package first on PYTHONPATH makes `from playwright.sync_api import ...` raise
ImportError deterministically, so the negative path is tested either way.

Scope is deliberately this one property. The wider gate work — telling a local sidecar
apart from a remote dependency, and not counting a commented-out tag as either — is
covered by its own 26-assertion suite.

Stdlib only, like the rest of the repo. Touches nothing outside a temp directory.

    python3 tests/test_verify_gate_browser.py
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
TOOLS = [
    REPO / "tools" / "verify_dashboard.py",
    REPO / "tools" / "verify_standalone_core.py",
]

passed = 0
failed = 0


def chk(label: str, got, want) -> None:
    global passed, failed
    if got == want:
        passed += 1
        print(f"  ok   {label}")
    else:
        failed += 1
        print(f"  FAIL {label}\n         got:  {got!r}\n         want: {want!r}")


def _no_playwright_dir(root: pathlib.Path) -> pathlib.Path:
    """A directory that shadows playwright with a module which refuses to import."""
    pkg = root / "shim" / "playwright"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        'raise ImportError("playwright blocked by test_verify_gate_browser.py")\n',
        encoding="utf-8",
    )
    return root / "shim"


def _run(tool: pathlib.Path, target: pathlib.Path, shim: pathlib.Path | None):
    env = {"PATH": "/usr/bin:/bin", "HOME": str(target.parent)}
    if shim is not None:
        env["PYTHONPATH"] = str(shim)
    return subprocess.run(
        [sys.executable, str(tool), str(target)],
        capture_output=True, text=True, env=env, timeout=60,
    )


# A file with nothing wrong in it that static checks can see: no remote references, no
# unsubstituted placeholders, provenance present, no row-24/25/26 offence. With a
# browser it verifies; the whole point is that without one it must not.
CLEAN = """<!doctype html>
<html lang="no"><head><meta charset="utf-8"><title>t</title></head>
<body>
<!-- PROVENANCE
     Source data : none — fixture
     Built       : fixture
-->
<div class="kpi">1</div>
<script>document.title = "ran";</script>
</body></html>
"""


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="verify-gate-browser-"))
    try:
        shim = _no_playwright_dir(tmp)
        work = tmp / "work"
        work.mkdir()
        target = work / "clean.html"
        target.write_text(CLEAN, encoding="utf-8")

        print("no browser available — neither tool may report success")
        for tool in TOOLS:
            r = _run(tool, target, shim)
            out = r.stdout + r.stderr
            # A crash also exits non-zero, so assert the tool reached its own verdict.
            # Otherwise "exits non-zero" would pass for the wrong reason.
            chk(f"{tool.name} does not crash", "Traceback" in r.stderr, False)
            chk(f"{tool.name} exits non-zero", r.returncode != 0, True)
            chk(f"{tool.name} prints no PASS line", "✓ PASS" in out, False)
            chk(f"{tool.name} says the browser checks were blocked",
                "BLOCKED" in out, True)
            chk(f"{tool.name} names the install command",
                "playwright install chromium" in out, True)
            chk(f"{tool.name} does not call it merely skipped",
                "SKIPPED — playwright" in out, False)

        print("\nmutation control — revert the guard and this suite must notice")
        # Same tools, with the failure downgraded back to a warning. If the suite still
        # passes against that, it is not testing the guard.
        mutant_dir = tmp / "mutant"
        mutant_dir.mkdir()
        for tool in TOOLS:
            src = tool.read_text(encoding="utf-8")
            mutated = src.replace(
                'failures.append("playwright not installed',
                'warnings.append("playwright not installed',
            )
            chk(f"{tool.name} guard text found to mutate", mutated != src, True)
            copy = mutant_dir / tool.name
            copy.write_text(mutated, encoding="utf-8")
            for helper in ("verify_standalone_core.py",):
                if not (mutant_dir / helper).exists():
                    (mutant_dir / helper).write_text(
                        (REPO / "tools" / helper).read_text(encoding="utf-8"),
                        encoding="utf-8",
                    )
            r = _run(copy, target, shim)
            chk(f"{tool.name} mutant reports success (so the guard is load-bearing)",
                r.returncode == 0, True)
    finally:
        pass

    print("\n" + "─" * 66)
    print(f"PASS: {passed}  FAIL: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
