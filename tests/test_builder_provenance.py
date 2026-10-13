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

The login has a second way in: a path. A brand plugin sets TUN_PALETTE to an absolute
path under the user's home directory, and the process diagram used to copy that path
into its provenance block verbatim. A canary in the environment cannot see that, because
the path carries the real home directory. So the palette checks also move HOME to a fake
directory named after the canary, put the palette there, and look for the home path in
every artefact all three builders make.

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
SPEC = ROOT / "examples" / "23-process-diagram" / "tun-workflow.process.txt"
EDITABLE = ROOT / "examples" / "24-editable-document" / "build_editable_document.py"
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


def build_rows(out: pathlib.Path, *extra: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_dashboard.py"), "--data", str(CSV),
         "--title", "t", "--dimension", "Produkt", "--measure", "Belop", "--time", "Maaned",
         "--out", str(out), *extra], capture_output=True, text=True, env=env or ENV, cwd=ROOT)


def build_cube(out: pathlib.Path, *extra: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_cube_dashboard.py"), "--data", str(CSV),
         "--title", "t", "--dims", "Region,Produkt", "--time", "Maaned",
         "--measures", "Belop:sum", "--out", str(out), *extra],
        capture_output=True, text=True, env=env or ENV, cwd=ROOT)


def build_process(out: pathlib.Path, spec: pathlib.Path = SPEC,
                  env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_process_diagram.py"), str(spec),
         "--out", str(out)], capture_output=True, text=True, env=env or ENV, cwd=ROOT)


def palette_line(html: str) -> str:
    m = re.search(r"Palette *: *(.*)", html)
    return m.group(1).strip() if m else "<no Palette line>"


def palette_under_fake_home(tmp: pathlib.Path) -> None:
    """Build every artefact with TUN_PALETTE pointing into a fake home directory.

    The home directory is named after the canary, so a leaked path shows up as the
    canary whatever form it takes. Two palettes: one in a subdirectory (the plugin
    case), and one directly in home, where its parent directory *is* the user name.
    """
    home = tmp / "Users" / CANARY
    neutral = (ROOT / "tools" / "tokens" / "palette-neutral.css").read_text(encoding="utf-8")
    nested = home / "brand-plugin" / "palette.css"
    flat = home / "palette.css"
    for p in (nested, flat):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(neutral, encoding="utf-8")
    base = {k: v for k, v in ENV.items() if not k.startswith("GIT_")}
    base.update(HOME=str(home), USERPROFILE=str(home))

    def leaks(html: str) -> list[str]:
        return [s for s in (str(home), home.as_posix(), CANARY, str(tmp)) if s in html]

    for palette in (nested, flat):
        env = dict(base, TUN_PALETTE=str(palette))
        where = palette.parent.name if palette is nested else "home"
        for name, build in (("rows", build_rows), ("cube", build_cube)):
            out = tmp / f"{name}-{where}.html"
            r = build(out, env=env)
            chk(f"{name}, TUN_PALETTE in {where}: builds", r.returncode == 0, r.stderr[-200:])
            html = out.read_text(encoding="utf-8") if out.exists() else ""
            chk(f"{name}, TUN_PALETTE in {where}: no home path in the file", not leaks(html),
                str(leaks(html)))

        out = tmp / f"process-{where}.html"
        r = build_process(out, env=env)
        chk(f"process, TUN_PALETTE in {where}: builds", r.returncode == 0, r.stderr[-200:])
        html = out.read_text(encoding="utf-8") if out.exists() else ""
        chk(f"process, TUN_PALETTE in {where}: no home path in the file", not leaks(html),
            str(leaks(html)))
        chk(f"process, TUN_PALETTE in {where}: provenance still names the override",
            palette_line(html).startswith("TUN_PALETTE=")
            and palette_line(html).endswith("palette.css"), palette_line(html))
        if palette is nested:
            chk("process: the plugin directory name stays, so the palette is identifiable",
                "brand-plugin/palette.css" in palette_line(html), palette_line(html))

    # The spec's own palette: header is the same path, written by the author instead.
    spec = tmp / "abs-palette.process.txt"
    spec.write_text(re.sub(r"(?m)^palette: .*$", f"palette: {nested}",
                           SPEC.read_text(encoding="utf-8")), encoding="utf-8")
    out = tmp / "process-spec.html"
    r = build_process(out, spec=spec, env=base)
    chk("process, absolute palette: in the spec: builds", r.returncode == 0, r.stderr[-200:])
    html = out.read_text(encoding="utf-8") if out.exists() else ""
    chk("process, absolute palette: in the spec: no home path in the file", not leaks(html),
        str(leaks(html)))
    chk("process, absolute palette: in the spec: provenance says spec:",
        palette_line(html).startswith("spec:"), palette_line(html))

    # Example 24 embeds the same label through its own builder. It writes to a fixed
    # path, so redirect OUT into the temp dir instead of rewriting the committed file.
    out = tmp / "editable.html"
    code = ("import importlib.util as u, pathlib; "
            f"s = u.spec_from_file_location('b', {str(EDITABLE)!r}); b = u.module_from_spec(s); "
            f"s.loader.exec_module(b); b.OUT = pathlib.Path({str(out)!r}); b.build()")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       env=dict(base, TUN_PALETTE=str(nested)), cwd=ROOT)
    chk("example 24, TUN_PALETTE in brand-plugin: builds", r.returncode == 0, r.stderr[-200:])
    html = out.read_text(encoding="utf-8") if out.exists() else ""
    chk("example 24, TUN_PALETTE in brand-plugin: no home path in the file",
        bool(html) and not leaks(html), str(leaks(html)))


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
    print("builder provenance: no OS user name or home path, a role when one is given")
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

        palette_under_fake_home(tmp)

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
