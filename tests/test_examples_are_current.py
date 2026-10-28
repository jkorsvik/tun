#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Every committed example must equal a rebuild of itself.

The class this closes: a template or a builder changes, an artefact that came from
it is never rebuilt, and the repo keeps shipping a page built from code that no
longer exists. It has happened three times: a table-pan rule that reached nineteen
templates but not one example, a pareto page one line behind, and a partial whose
licence header was inlined into two KPI pages.

The README is the source of truth for how an artefact is built, so this reads the
build commands out of it, runs each with a fixed clock into a temp directory, and
compares the bytes.

Three rules keep it honest:

  * EVERY build command, and EVERY --out inside it. One example's README can
    document several artefacts (examples/26-kpi-board builds two pages), and
    comparing only the first one hid a stale page behind a fresh one.
  * a fixed clock, both stamps. SOURCE_DATE_EPOCH and TZ are what make a rebuild
    comparable; without them every artefact differs by its build time.
  * it refuses to pass on an empty list, and it keeps going after the first
    difference, because a check that stops at the first error reports one fact
    when there are five.

    python3 tests/test_examples_are_current.py
    python3 tests/test_examples_are_current.py --mutation-control
"""
from __future__ import annotations

import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PIN = "1792836000"
BASH = re.compile(r"```bash\n(.*?)```", re.S)

#: Named, not silently dropped. Each entry says why a rebuild is not comparable.
SKIP = {
    "54-showcase": "assembles every other example and needs a browser to photograph them",
    "03-cube-dashboard": "its input CSV is generated at full size and is deliberately not committed",
}


def tracked(root: pathlib.Path, rel: str) -> bool:
    out = subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch", rel],
                         capture_output=True, text=True)
    return out.returncode == 0


def build_commands(readme: pathlib.Path) -> list[str]:
    """Every documented build command in the README, continuations joined."""
    commands: list[str] = []
    for block in BASH.findall(readme.read_text(encoding="utf-8", errors="replace")):
        if "build_" not in block:
            continue
        current: list[str] = []
        for line in block.splitlines():
            stripped = line.rstrip()
            current.append(stripped.rstrip("\\").strip())
            if stripped.endswith("\\"):
                continue
            sentence = " ".join(part for part in current if part)
            current = []
            if not sentence or sentence.startswith("#"):
                continue
            if "build_" in sentence and "--out" in sentence:
                commands.append(sentence)
    return commands


def outs_of(command: str) -> list[str]:
    """Every --out path in one command, not just the first."""
    words = shlex.split(command)
    return [words[i + 1] for i, w in enumerate(words) if w == "--out" and i + 1 < len(words)]


def compare(root: pathlib.Path, out_rel: str, words: list[str], quiet: bool) -> str | None:
    """Rebuild one artefact into a temp dir. None when it matches, else a verdict."""
    with tempfile.TemporaryDirectory() as tmp:
        rebuilt = pathlib.Path(tmp) / pathlib.Path(out_rel).name
        argv = list(words)
        argv[argv.index("--out") + 1] = str(rebuilt)
        if argv and argv[0] in ("python3", "python"):
            argv[0] = sys.executable
        env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
        run = subprocess.run(argv, cwd=root, capture_output=True, text=True, env=env)
        if run.returncode != 0:
            last = run.stderr.strip().splitlines()[-1][:110] if run.stderr.strip() else "build failed"
            return f"broke: {out_rel}: {last}"
        if not rebuilt.is_file():
            return f"broke: {out_rel}: the command wrote no artefact"
        if rebuilt.read_bytes() != (root / out_rel).read_bytes():
            return f"stale: {out_rel}"
        if not quiet:
            print(f"  ok   {out_rel}")
        return None


def run(root: pathlib.Path, quiet: bool = False) -> int:
    examples = root / "examples"
    if not examples.is_dir():
        print("FAIL: no examples directory")
        return 1

    checked = 0
    skipped: list[tuple[str, str]] = []
    problems: list[str] = []

    for folder in sorted(p for p in examples.iterdir() if p.is_dir()):
        readme = folder / "README.md"
        if not readme.is_file():
            skipped.append((folder.name, "no README to take a build command from"))
            continue
        if folder.name in SKIP:
            skipped.append((folder.name, SKIP[folder.name]))
            continue
        commands = build_commands(readme)
        if not commands:
            skipped.append((folder.name, "no fenced bash build command in its README"))
            continue

        compared_here = 0
        for command in commands:
            # A quoted title is one argument. Splitting on whitespace turns
            # --title "Henvendelser per arsak" into four and argparse refuses it.
            words = shlex.split(command)
            inputs = [t for t in words if t.endswith((".csv", ".json")) and not t.startswith("-")]
            for out_rel in outs_of(command):
                if not tracked(root, out_rel):
                    skipped.append((folder.name, f"{out_rel} is not committed"))
                    continue
                missing = [t for t in inputs if not (root / t).is_file()]
                if missing:
                    skipped.append((folder.name, f"input not in the tree: {missing[0]}"))
                    continue
                untracked = [t for t in inputs if not tracked(root, t)]
                if untracked:
                    skipped.append((folder.name, f"input is generated, not committed: {untracked[0]}"))
                    continue
                checked += 1
                compared_here += 1
                verdict = compare(root, out_rel, words, quiet)
                if verdict:
                    problems.append(verdict)
        if not compared_here:
            skipped.append((folder.name, "no comparable artefact in its build commands"))

    print(f"rebuilt and compared: {checked} artefact(s)")
    print(f"skipped: {len(skipped)}")
    for name, why in skipped:
        print(f"  - {name}: {why}")
    for row in problems:
        print(f"  ✗ {row}")

    if not checked:
        print("FAIL: nothing was compared, so this gate proves nothing")
        return 1
    if problems:
        print(f"FAIL: {len(problems)} artefact(s) do not match their own pinned rebuild")
        return 1
    print(f"PASS: every compared artefact equals its own pinned rebuild ({checked})")
    return 0


def mutation_control() -> int:
    """Prove the gate sees a SECOND --out and keeps going past the first difference.

    A two-output README is exactly the case that hid a stale page: the first
    artefact matched, so the gate called the example current. Build a throwaway
    tree with a README that names two artefacts, make the second one stale, and
    require the gate to read both and to fail.
    """
    failures = 0

    def chk(what: str, got, want) -> None:
        nonlocal failures
        if got != want:
            print(f"  ✗ {what}: got {got!r}, want {want!r}")
            failures += 1
        else:
            print(f"  ok   {what}")

    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        ex = root / "examples" / "99-mutation"
        ex.mkdir(parents=True)
        builder = root / "tools" / "build_two.py"
        builder.parent.mkdir(parents=True)
        # Writes its --word into its --out file: deterministic, no clock involved.
        builder.write_text(
            "import argparse, pathlib\n"
            "p = argparse.ArgumentParser()\n"
            "p.add_argument('--out'); p.add_argument('--word')\n"
            "a = p.parse_args()\n"
            "pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)\n"
            "pathlib.Path(a.out).write_text(a.word, encoding='utf-8')\n", encoding="utf-8")
        (ex / "README.md").write_text(
            "```bash\n"
            "python3 tools/build_two.py --word first --out examples/99-mutation/a.html\n"
            "python3 tools/build_two.py --word second --out examples/99-mutation/b.html\n"
            "```\n", encoding="utf-8")
        (ex / "a.html").write_text("first", encoding="utf-8")
        (ex / "b.html").write_text("STALE", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)

        commands = build_commands(ex / "README.md")
        chk("both build commands are read", len(commands), 2)
        chk("both --out paths are found", [o for c in commands for o in outs_of(c)],
            ["examples/99-mutation/a.html", "examples/99-mutation/b.html"])

        verdicts = [compare(root, o, shlex.split(c), quiet=True)
                    for c in commands for o in outs_of(c)]
        chk("the fresh artefact matches", verdicts[0], None)
        chk("the stale one is named", verdicts[1], "stale: examples/99-mutation/b.html")
        chk("the gate fails the tree", run(root, quiet=True), 1)

    print(f"mutation control: {'PASS' if not failures else 'FAIL'} ({failures} problem(s))")
    return 0 if not failures else 1


if __name__ == "__main__":
    if "--mutation-control" in sys.argv:
        raise SystemExit(mutation_control())
    raise SystemExit(run(ROOT))
