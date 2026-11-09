#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""START-HERE.md is the shortest path into Tún, so its commands must run as written.

The test copies only the files a new user needs into a temporary directory, runs the documented
build command there, and checks the resulting file. It uses no repository state from the
checkout and writes nothing into it. The browser half remains verify_dashboard.py's job; this
suite proves the route, its inputs and the standalone shape of the output.

Mutation control: damage the copied input CSV and require the same command to fail.
"""
from __future__ import annotations

import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "START-HERE.md"


def fail(message: str) -> None:
    raise AssertionError(message)


def documented_build(text: str) -> list[str]:
    blocks = re.findall(r"```bash\n(.*?)```", text, flags=re.S)
    commands = [line.strip() for block in blocks for line in block.splitlines()
                if "tools/build_dashboard.py" in line]
    if len(commands) != 1:
        fail(f"expected one dashboard build command, found {len(commands)}")
    argv = shlex.split(commands[0])
    argv[0] = sys.executable
    return argv


def run(command: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(TZ="UTC", SOURCE_DATE_EPOCH="1792836000", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)


def main() -> None:
    text = DOC.read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "[Start here](START-HERE.md)" in readme, "README does not route a new reader here"
    assert "different audiences need different rows" in text, "the data-boundary rule is missing"
    argv = documented_build(text)

    with tempfile.TemporaryDirectory(prefix="tun-start-here-") as tmp:
        clean = pathlib.Path(tmp)
        for name in ("tools", "templates"):
            shutil.copytree(ROOT / name, clean / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(ROOT / "examples/01-hello-dashboard",
                        clean / "examples/01-hello-dashboard",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.png"))

        result = run(argv, clean)
        if result.returncode:
            fail(f"the documented build failed:\n{result.stdout}\n{result.stderr}")
        artefact = clean / "start-here.html"
        assert artefact.is_file() and artefact.stat().st_size > 10_000, "no substantial HTML file"
        html = artefact.read_text(encoding="utf-8")
        for expected in ("Salg per region og produkt 2026", "Synthetic example data",
                         "Project owner", "<html", "Region"):
            assert expected in html, f"the artefact is missing {expected!r}"
        assert not re.search(r"<script[^>]+src=", html, re.I), "a script is loaded externally"
        assert not re.search(r"<link[^>]+href=[\"']https?://", html, re.I), "CSS is loaded externally"

        source = clean / "examples/01-hello-dashboard/salgsdata.csv"
        source.write_text("not,the,documented,input\n", encoding="utf-8")
        broken = run(argv, clean)
        assert broken.returncode != 0, "a damaged input did not stop the build"

    print("PASS: README routes here, the one build command works in a clean copy, "
          "the file is standalone, and a damaged input fails")


if __name__ == "__main__":
    main()
