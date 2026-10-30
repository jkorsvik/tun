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


def run(doc, cwd, argv, engines, tmp: pathlib.Path, n: int) -> tuple[str, str, pathlib.Path | None]:
    """Run one documented command. Returns (status, detail, artefact): PASS, FAIL or SKIP."""
    tool = (cwd / argv[0]).resolve()
    args = list(argv[1:])
    if not tool.is_file():
        return "FAIL", f"{doc.relative_to(ROOT)} documents {argv[0]}, which does not exist", None
    artefacts = [a for a in args if a.endswith(".html")]
    if artefacts:
        target = (cwd / artefacts[0]).resolve()
        if ROOT / "examples" not in target.parents:
            return "SKIP", f"template path {artefacts[0]}", None
        if not target.is_file():
            return "FAIL", f"{doc.relative_to(ROOT)} documents {artefacts[0]}, which does not exist", None
    elif ROOT / "examples" not in tool.parents:
        return "SKIP", "no .html argument", None   # an example's own verifier knows its file
    for flag in ("--out", "--output"):       # keep screenshots out of /tmp and the tree
        if flag in args:
            set_flag(args, flag, str(tmp / f"out-{n}"))
    set_flag(args, "--engines", ",".join(engines))
    r = subprocess.run([sys.executable, str(tool), *args], cwd=cwd,
                       capture_output=True, text=True)
    target = (cwd / artefacts[0]).resolve() if artefacts else None
    if r.returncode != 0:
        return "FAIL", failure_detail(r.stdout + r.stderr), target
    tail = (r.stdout + r.stderr).strip().splitlines()
    return "PASS", tail[-1] if tail else "(no output)", target


VIEWPORTS_TOOL = "verify_viewports.py"


def viewport_sweep(artefacts: dict[pathlib.Path, str], engines, tmp: pathlib.Path) -> tuple[int, int]:
    """docs/11's responsive claim, for every artefact no README already sweeps.

    A README that documents `verify_viewports.py` has already stated the floor that
    artefact holds (a fitted drawing holds 12 px, a dense slide card 9), so those are
    left alone: running the default floor over them would contradict the README. Every
    other verified artefact gets swept here at the default floor, which is how the
    touch minimum and the text floor stop being documentation only.

    Returns (checked, failed).
    """
    tool = ROOT / "tools" / VIEWPORTS_TOOL
    if not tool.is_file():
        print(f"\n✗ FAIL: {VIEWPORTS_TOOL} is missing, so the sweep could not run")
        return 0, 1
    checked = failed = 0
    for n, (artefact, doc) in enumerate(sorted(artefacts.items())):
        if not artefact.is_file():
            continue
        out = tmp / f"viewports-{n}"
        r = subprocess.run([sys.executable, str(tool), str(artefact),
                            "--engines", ",".join(engines), "--out", str(out), "--quiet"],
                           cwd=ROOT, capture_output=True, text=True)
        checked += 1
        ok = r.returncode == 0
        failed += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  {VIEWPORTS_TOOL} {artefact.name}"
              f"   (floor 14 px, default; documented by {doc})")
        if not ok:
            print(f"      {failure_detail(r.stdout + r.stderr)}")
    return checked, failed


A11Y_TOOL = "verify_a11y.py"


def a11y_sweep(artefacts: dict[pathlib.Path, str], engines) -> tuple[int, int]:
    """ROADMAP A10: the accessibility rules, for every verified artefact.

    Same shape as `viewport_sweep`, and for the same reason: the artefacts this gate
    covers are the ones some README already verifies, so a new example is covered by
    being documented rather than by being added to a list here. One engine is enough,
    because none of the six rules is a layout question; `--engines` still passes through
    so a caller can ask for all three.

    Returns (checked, failed).
    """
    tool = ROOT / "tools" / A11Y_TOOL
    if not tool.is_file():
        print(f"\n✗ FAIL: {A11Y_TOOL} is missing, so the sweep could not run")
        return 0, 1
    checked = failed = 0
    for artefact, doc in sorted(artefacts.items()):
        if not artefact.is_file():
            continue
        r = subprocess.run([sys.executable, str(tool), str(artefact),
                            "--engines", "chromium", "--quiet"],
                           cwd=ROOT, capture_output=True, text=True)
        checked += 1
        ok = r.returncode == 0
        failed += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  {A11Y_TOOL} {artefact.name}"
              f"   (chromium, six rules; documented by {doc})")
        if not ok:
            print(f"      {failure_detail(r.stdout + r.stderr)}")
    return checked, failed


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
    swept: dict[pathlib.Path, str] = {}
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        for n, (doc, cwd, words) in enumerate(found):
            status, detail, artefact = run(doc, cwd, words, args.engines, tmp, n)
            counts[status] += 1
            name = pathlib.Path(words[0]).name
            print(f"  {status}  {name} {pathlib.Path(next((w for w in words if w.endswith('.html')), '?')).name}")
            if status != "PASS":
                print(f"      {detail}")
            if artefact and status != "FAIL":
                swept[artefact] = str(doc.relative_to(ROOT))
        # A README that documents the viewport tool has stated that artefact's own floor.
        declared = {art for doc, cwd, words in found
                    if pathlib.Path(words[0]).name == VIEWPORTS_TOOL
                    for art in [(cwd / next(w for w in words if w.endswith(".html"))).resolve()]}
        outstanding = {a: d for a, d in swept.items() if a not in declared}
        print(f"\nviewports: {len(outstanding)} artefact(s) no README sweeps, at the default floor")
        checked, vfailed = viewport_sweep(outstanding, args.engines, tmp)
        print(f"\naccessibility: {len(swept)} verified artefact(s), six rules each")
        acheked, afailed = a11y_sweep(swept, args.engines)
    print("─" * 62)
    print(f"{counts['PASS']} passed, {counts['FAIL']} failed, {counts['SKIP']} skipped; "
          f"viewports swept {checked}, {vfailed} failed; "
          f"accessibility swept {acheked}, {afailed} failed")
    if counts["PASS"] == 0:
        print("✗ FAIL: no documented command actually ran")
        return 1
    return 1 if (counts["FAIL"] or vfailed or afailed) else 0


if __name__ == "__main__":
    sys.exit(main())
