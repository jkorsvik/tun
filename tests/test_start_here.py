#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""START-HERE.md must work for a new reader, not only in this checkout."""
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


def documented_build(text: str) -> list[str]:
    blocks = re.findall(r"```bash\n(.*?)```", text, flags=re.S)
    commands = [block[block.index("python3 tools/build_dashboard.py"):].replace("\\\n", " ").strip()
                for block in blocks if "python3 tools/build_dashboard.py" in block]
    assert len(commands) == 1, f"expected one dashboard build, found {len(commands)}"
    argv = shlex.split(commands[0])
    argv[0] = sys.executable
    return argv


def run(command: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(TZ="UTC", SOURCE_DATE_EPOCH="1792836000", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)


def main() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "[Start here](START-HERE.md)" in (ROOT / "README.md").read_text(encoding="utf-8")
    for expected in ("setup.py --tool claude", "setup.py --tool agents", "ChatGPT, Grok",
                     "not the tested Tún builders", "Split the data"):
        assert expected in text, f"quick start is missing {expected!r}"
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
        assert result.returncode == 0, result.stdout + result.stderr
        artefact = clean / "work/demo.html"
        assert artefact.is_file() and artefact.stat().st_size > 10_000
        html = artefact.read_text(encoding="utf-8")
        for expected in ("Salg per region og produkt 2026", "Eksempeldata (syntetisk)",
                         "Prosjekteier", "<html", "Region"):
            assert expected in html, f"the artefact is missing {expected!r}"
        assert not re.search(r"<script[^>]+src=", html, re.I)
        assert not re.search(r"<link[^>]+href=[\"']https?://", html, re.I)

        source = clean / "examples/01-hello-dashboard/salgsdata.csv"
        source.write_text("not,the,documented,input\n", encoding="utf-8")
        broken = run(argv, clean)
        assert broken.returncode != 0, "a damaged input did not stop the build"

    print("PASS: README route, clean-copy build, standalone output, AI routes and refusal control")


if __name__ == "__main__":
    main()
