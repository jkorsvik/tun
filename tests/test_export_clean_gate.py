#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_export_clean_gate.py — prove the export gate gates, without naming what it guards.

Stdlib only.

    python3 tests/test_export_clean_gate.py

The real denylist is local and untracked (see tools/check_export_clean.py), so these
fixtures use an invented term, assembled at runtime, in a throwaway denylist. Every fixture asserts
the gate fires *and* fires alone, and that the log does not echo the matched text.
A gate that passes when it has nothing to check is reported as an error, not a pass.
"""
from __future__ import annotations

import io
import os
import pathlib
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import check_export_clean as gate  # noqa: E402

passed = failed = 0
TERM = "zyx" + "qorp"  # assembled, so this file does not contain it


def chk(label, got, want):
    global passed, failed
    ok = got == want
    passed += ok
    failed += not ok
    print(f"  {'PASS' if ok else 'FAIL'} {label}" + ("" if ok else f" — got {got!r}, want {want!r}"))


def run(root: pathlib.Path, denylist: pathlib.Path | None):
    args = ["--root", str(root)]
    if denylist is not None:
        args += ["--denylist", str(denylist)]
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = gate.main(args)
    return code, out.getvalue(), err.getvalue()


def tree(files: dict[str, bytes | str]) -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp(prefix="tun-export-gate-"))
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body if isinstance(body, bytes) else body.encode())
    return root


def findings(out: str) -> list[str]:
    return [line.split()[1] for line in out.splitlines() if line.strip().startswith("✗ ") and "FAIL" not in line]


tmp = pathlib.Path(tempfile.mkdtemp(prefix="tun-denylist-"))
deny = tmp / "deny.txt"
deny.write_text(f"# test\nperson\t{TERM}\n", encoding="utf-8")
clean = {"README.md": "hello\n", "data/x.csv": "a,b\n1,2\n"}

print("clean tree passes, and says how much it checked")
code, out, _ = run(tree(clean), deny)
chk("exit 0", code, 0)
chk("reports the file count", "checked 2 file(s)" in out, True)

print("\na planted term in text fires alone, with its line, redacted")
code, out, _ = run(tree({**clean, "docs/a.md": f"one\ntwo {TERM.upper()} three\n"}), deny)
chk("exit 1", code, 1)
chk("exactly one finding, labelled by the denylist", findings(out), ["person"])
chk("points at the line", "docs/a.md:2" in out, True)
chk("does not echo the term", TERM in out.lower(), False)

print("\na term in a path fires")
code, out, _ = run(tree({**clean, f"plugins/{TERM}/x.txt": "ok\n"}), deny)
chk("exit 1", code, 1)
chk("one path finding", ("(path)" in out, findings(out)), (True, ["person"]))

print("\na term inside binary bytes fires")
code, out, _ = run(tree({**clean, "img.png": b"\x89PNG\x00\x01" + TERM.encode() + b"\xff\x00"}), deny)
chk("exit 1", code, 1)
chk("one finding", findings(out), ["person"])

print("\nbuilt-in shapes fire without any denylist entry for them")
code, out, _ = run(tree({**clean, "a.md": "mail " + "someone" + "@" + "corp-internal.no\n"}), deny)
chk("e-mail fires alone", findings(out), ["email"])
code, out, _ = run(tree({**clean, "a.md": "contact x@example.com\n"}), deny)
chk("example.com is allowed", code, 0)
code, out, _ = run(tree({**clean, "a.md": "it was " + "run " + "12345678, job probe\n"}), deny)
chk("CI run id fires alone", findings(out), ["ci"])

print("\nthe gate refuses to pass when it cannot check")
code, _, err = run(tree(clean), tmp / "missing.txt")
chk("missing denylist exits 2", code, 2)
chk("and says why", "denylist not found" in err, True)
empty = tmp / "empty.txt"
empty.write_text("# only comments\n\n", encoding="utf-8")
code, _, err = run(tree(clean), empty)
chk("empty denylist exits 2", code, 2)
code, _, err = run(tree({}), deny)
chk("empty tree exits 2", code, 2)
chk("and says why", "no files in scope" in err, True)

print("\na git tree is scoped to tracked files, even under a hook's GIT_* env")
root = tree({**clean, "untracked.md": f"{TERM}\n"})
env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
subprocess.run(["git", "init", "-q", str(root)], check=True, env=env)
subprocess.run(["git", "-C", str(root), "add", "README.md", "data/x.csv"], check=True, env=env)
os.environ["GIT_DIR"] = str(REPO / ".git")
try:
    code, out, _ = run(root, deny)
finally:
    del os.environ["GIT_DIR"]
chk("untracked file is out of scope", code, 0)
chk("and only the 2 tracked files were checked", "checked 2 file(s)" in out, True)

print("\na copyright notice may name its holder; nothing else may")
ORG = "wvu" + "trel"
deny2 = tmp / "deny2.txt"
deny2.write_text(f"person\t{TERM}\norg\t{ORG}\n", encoding="utf-8")
code, out, _ = run(tree({**clean, "a.py": f"# Copyright (C) 2026 Ola {TERM.title()}\nx = 1\n"}), deny2)
chk("holder on the notice line passes", (code, findings(out)), (0, []))
code, out, _ = run(tree({**clean, "a.py": f"# SPDX-FileCopyrightText: 2026 Ola {TERM.title()}\n"}), deny2)
chk("SPDX notice form passes too", (code, findings(out)), (0, []))
code, out, _ = run(tree({**clean, "a.py": f"# Copyright (C) 2026 Ola {TERM.title()}\n# written by {TERM}\n"}), deny2)
chk("same name off the notice line fires alone, on its line", (code, findings(out), "a.py:2" in out), (1, ["person"], True))
code, out, _ = run(tree({**clean, "a.py": f"# Copyright (C) 2026 {ORG.upper()} AS\n"}), deny2)
chk("an organisation as holder is still caught", (code, findings(out)), (1, ["org"]))
code, out, _ = run(tree({**clean, "a.py": f"# Copyright (C) Ola {TERM}\n"}), deny2)
chk("a notice without a year is not a notice", (code, findings(out)), (1, ["person"]))

print("\na declared attribution region may credit people by name; nothing else is exempt")
S, E = "<!-- attribution:start -->", "<!-- attribution:end -->"
code, out, _ = run(tree({**clean, "A.md": f"{S}\nOla {TERM.title()} wrote it\n{E}\n"}), deny2)
chk("a person inside the region passes", (code, findings(out)), (0, []))
code, out, _ = run(tree({**clean, "A.md": f"{S}\nOla {TERM.title()}\n{E}\nthanks {TERM}\n"}), deny2)
chk("the same name after the region fires alone, on its line", (code, findings(out), "A.md:4" in out), (1, ["person"], True))
code, out, _ = run(tree({**clean, "A.md": f"{S}\nat {ORG.upper()} AS\n{E}\n"}), deny2)
chk("an organisation inside the region is still caught", (code, findings(out)), (1, ["org"]))
code, out, _ = run(tree({**clean, "A.md": f"{S}\nOla {TERM.title()}\n"}), deny2)
chk("an unterminated region exempts nothing", (code, findings(out)), (1, ["person"]))

print("\n" + "─" * 66)
print(f"{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
