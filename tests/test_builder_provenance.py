#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""test_builder_provenance.py — no builder writes the builder's OS user name into an artefact.

Both builders used to fall back to getpass.getuser() when --requested-by was left out, so
every rebuild stamped the login of whoever ran it into the provenance block of a file that
is then shared and committed. Example 03 shipped that way. The fallback is now a neutral
value, and the documented commands pass a role.

The OS user is forced to a canary through LOGNAME/USER/LNAME/USERNAME, the variables
getpass.getuser() reads first. A leak then shows up as the canary in the output, on any
machine, whatever the real login is.

Stdlib only, runs the real builders as subprocesses into a temp dir.

    python3 tests/test_builder_provenance.py
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSV = ROOT / "examples" / "01-hello-dashboard" / "salgsdata.csv"
CANARY = "canary-os-user-7f3a"
ENV = dict(os.environ, LOGNAME=CANARY, USER=CANARY, LNAME=CANARY, USERNAME=CANARY)

passed = failed = 0


def chk(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS {label}")
    else:
        failed += 1
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def build_rows(out: pathlib.Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_dashboard.py"), "--data", str(CSV),
         "--title", "t", "--dimension", "Produkt", "--measure", "Belop", "--time", "Maaned",
         "--out", str(out), *extra], capture_output=True, text=True, env=ENV, cwd=ROOT)


def build_cube(out: pathlib.Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_cube_dashboard.py"), "--data", str(CSV),
         "--title", "t", "--dims", "Region,Produkt", "--time", "Maaned",
         "--measures", "Belop:sum", "--out", str(out), *extra],
        capture_output=True, text=True, env=ENV, cwd=ROOT)


def requested_by(html: str) -> str:
    m = re.search(r"Requested by: *(.*)", html)
    return m.group(1).strip() if m else "<no Requested by line>"


def documented_commands(rel: str) -> list[str]:
    """Every builder invocation in a doc, with its backslash continuations joined."""
    lines = (ROOT / rel).read_text(encoding="utf-8").splitlines()
    out = []
    for i, line in enumerate(lines):
        if re.search(r"python3? +tools/build_(cube_)?dashboard\.py", line):
            block = [line]
            while block[-1].rstrip().endswith("\\") and i + len(block) < len(lines):
                block.append(lines[i + len(block)])
            out.append(" ".join(block))
    return out


def main() -> int:
    print("builder provenance: no OS user name, a role when one is given")
    print("─" * 62)
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        for name, build in (("rows", build_rows), ("cube", build_cube)):
            out = tmp / f"{name}.html"
            r = build(out)
            chk(f"{name}: builds without --requested-by", r.returncode == 0, r.stderr[-200:])
            html = out.read_text(encoding="utf-8") if out.exists() else ""
            chk(f"{name}: the OS user name is nowhere in the file", CANARY not in html)
            chk(f"{name}: provenance says 'not stated'", requested_by(html) == "not stated",
                requested_by(html))

            out = tmp / f"{name}-role.html"
            r = build(out, "--requested-by", "Analyseteamet")
            html = out.read_text(encoding="utf-8") if out.exists() else ""
            chk(f"{name}: --requested-by lands in provenance",
                requested_by(html) == "Analyseteamet", requested_by(html))
            chk(f"{name}: and the OS user name is still absent", CANARY not in html)

    # Committed examples must not carry a login either. A real login cannot be guessed,
    # so check the cube's META field, the one place it used to land, and the role.
    ex03 = (ROOT / "examples" / "03-cube-dashboard" / "transaksjoner.html").read_text(encoding="utf-8")
    chk("example 03: no built_by field left in META", '"built_by"' not in ex03)
    chk("example 03: provenance names a role", requested_by(ex03) == "Prosjekteier",
        requested_by(ex03))

    # The documented commands are what people copy. Each must pass a requester, or a
    # rebuild of a committed example silently drops it to 'not stated'.
    for rel in ("AGENTS.md", "README.md", "examples/03-cube-dashboard/README.md",
                "docs/07-portable-cube.md", "skills/tun-new/SKILL.md"):
        cmds = documented_commands(rel)
        chk(f"{rel}: has at least one builder command", bool(cmds))
        missing = [c[:70] for c in cmds if "--requested-by" not in c]
        chk(f"{rel}: every builder command passes --requested-by", not missing, str(missing))

    print("─" * 62)
    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
