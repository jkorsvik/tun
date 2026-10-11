#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
verify_documented.py — run every verify command the examples document, in every engine.

A reader copies the command under an example's "verify" heading. This finds those
commands (examples/*/README.md and AGENTS.md, inside ``` fences, backslash
continuations joined), adds `--engines all` and runs each one. So the examples are
checked in Chromium, Firefox and WebKit, and a README whose command names a file that
no longer exists fails here instead of failing the reader.

    uv run --extra verify python tools/verify_documented.py [--engines LIST] [--list]

An example's own verifier (examples/<x>/verify_*.py) runs as documented; it knows
its file. A command whose artefact path is not under examples/ (a template such as
dashboards/<slug>.html) is printed as skipped, not run. Finding zero commands is a
failure: a gate that checked nothing must not pass.

Exit 0 = every documented command passed in every engine asked for.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from verify_standalone_core import ENGINES, add_engines_arg  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOL = re.compile(r"(?:^|/)(?:tools|examples/[^/]+)/(verify_[a-z_]+)\.py$")
SOURCES = ("AGENTS.md", "examples/*/README.md")


def fenced_lines(text: str) -> list[str]:
    """The lines inside ``` fences, with backslash continuations joined."""
    out: list[str] = []
    inside = False
    pending = ""
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            inside = not inside
            continue
        if not inside:
            continue
        line = pending + line.strip()
        if line.endswith("\\"):
            pending = line[:-1].rstrip() + " "
            continue
        pending = ""
        out.append(line)
    return out


def commands(root: pathlib.Path = ROOT) -> list[tuple[pathlib.Path, pathlib.Path, list[str]]]:
    """(doc, cwd, argv) for every documented verify command, argv starting at the tool."""
    found: list[tuple[pathlib.Path, pathlib.Path, list[str]]] = []
    for pattern in SOURCES:
        for doc in sorted(root.glob(pattern)):
            for line in fenced_lines(doc.read_text(encoding="utf-8")):
                try:
                    words = shlex.split(line, comments=True)
                except ValueError:
                    continue
                at = next((i for i, w in enumerate(words) if TOOL.search(w)), None)
                if at is None:
                    continue
                cwd = doc.parent if words[at].startswith("../") else root
                found.append((doc, cwd, words[at:]))
    return found


def set_flag(args: list[str], flag: str, value: str) -> None:
    """Give flag this value: replace the documented one, or add the flag."""
    if flag not in args:
        args += [flag, value]
    elif (i := args.index(flag)) + 1 < len(args):
        args[i + 1] = value
    else:
        args.append(value)


def failure_detail(output: str, root: pathlib.Path = ROOT) -> str:
    """What a failed command's log must show: the engine that was running, the
    frames in this repo (not the library's), then the last lines. A bare tail is
    all Playwright internals and does not say which engine broke."""
    lines = output.strip().splitlines()
    engine = [ln.strip() for ln in lines if ln.lstrip().startswith("· ")][-1:]
    frames = [ln.strip() for ln in lines
              if ln.lstrip().startswith('File "') and str(root) in ln and "site-packages" not in ln]
    return "\n      ".join(engine + frames[-4:] + lines[-12:])


def run(doc, cwd, argv, engines, tmp: pathlib.Path, n: int) -> tuple[str, str]:
    """Run one documented command. Returns (status, detail): PASS, FAIL or SKIP."""
    tool = (cwd / argv[0]).resolve()
    args = list(argv[1:])
    if not tool.is_file():
        return "FAIL", f"{doc.relative_to(ROOT)} documents {argv[0]}, which does not exist"
    artefacts = [a for a in args if a.endswith(".html")]
    if artefacts:
        target = (cwd / artefacts[0]).resolve()
        if ROOT / "examples" not in target.parents:
            return "SKIP", f"template path {artefacts[0]}"
        if not target.is_file():
            return "FAIL", f"{doc.relative_to(ROOT)} documents {artefacts[0]}, which does not exist"
    elif ROOT / "examples" not in tool.parents:
        return "SKIP", "no .html argument"          # an example's own verifier knows its file
    if "--out" in args:                       # keep screenshots out of /tmp and the tree
        set_flag(args, "--out", str(tmp / f"out-{n}"))
    set_flag(args, "--engines", ",".join(engines))
    r = subprocess.run([sys.executable, str(tool), *args], cwd=cwd,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return "FAIL", failure_detail(r.stdout + r.stderr)
    tail = (r.stdout + r.stderr).strip().splitlines()
    return "PASS", tail[-1] if tail else "(no output)"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_engines_arg(ap, default=ENGINES)
    ap.add_argument("--list", action="store_true", help="print the commands found and stop")
    args = ap.parse_args(argv)

    found = commands()
    print(f"documented verify commands: {len(found)} in {', '.join(SOURCES)}")
    for doc, _, words in found:
        print(f"  {doc.relative_to(ROOT)}: {' '.join(words)}")
    if not found:
        print("✗ FAIL: found no documented verify command, so nothing was checked")
        return 1
    if args.list:
        return 0

    print(f"\nrunning each in {', '.join(args.engines)}")
    print("─" * 62)
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    with tempfile.TemporaryDirectory() as td:
        for n, (doc, cwd, words) in enumerate(found):
            status, detail = run(doc, cwd, words, args.engines, pathlib.Path(td), n)
            counts[status] += 1
            name = pathlib.Path(words[0]).name
            print(f"  {status}  {name} {pathlib.Path(next((w for w in words if w.endswith('.html')), '?')).name}")
            if status != "PASS":
                print(f"      {detail}")
    print("─" * 62)
    print(f"{counts['PASS']} passed, {counts['FAIL']} failed, {counts['SKIP']} skipped")
    if counts["PASS"] == 0:
        print("✗ FAIL: no documented command actually ran")
        return 1
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
