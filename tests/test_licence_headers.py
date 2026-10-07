#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_licence_headers.py — every source file states its licence, and every Artefact
Runtime file states the Artefact Exception.

Stdlib only.

    python3 tests/test_licence_headers.py

The Exception applies only to files that "carry a notice placed by the copyright holder"
(COPYING.ARTEFACT-EXCEPTION). A runtime file without that notice silently falls outside
it, and documents built from it are then plain AGPL works. Nothing else would notice.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
passed = failed = 0


def chk(label, got, want):
    global passed, failed
    ok = got == want
    passed += ok
    failed += not ok
    print(f"  {'PASS' if ok else 'FAIL'} {label}" + ("" if ok else f" — got {got!r}, want {want!r}"))


def is_runtime(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return ((rel.startswith("templates/") and name.endswith(".html")) or name.endswith(".css")
            or name.endswith(".template.html") or name == "tun_tokens.py"
            or (name.endswith(".py") and name.startswith("build")))


def is_source(rel: str) -> bool:
    return rel.endswith(".py") or rel.startswith("tools/hooks/") or is_runtime(rel)


def head(rel: str) -> str:
    return "\n".join((REPO / rel).read_text(encoding="utf-8").splitlines()[:15])


env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
files = subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True,
                       check=True, env=env).stdout.split()
# internal/ never leaves the forge (export.sh removes it), so it carries no licence header.
files = [f for f in files if not f.startswith("internal/")]
sources = [f for f in files if is_source(f)]
runtime = [f for f in sources if is_runtime(f)]
print(f"scope: {len(sources)} source file(s), {len(runtime)} of them Artefact Runtime")
chk("scope is not empty", len(sources) > 40 and len(runtime) > 15, True)

missing_spdx = [f for f in sources if "SPDX-License-Identifier: AGPL-3.0-or-later" not in head(f)]
chk("every source file carries the AGPL SPDX line", missing_spdx, [])
missing_holder = [f for f in sources if "Copyright (C) 2026 " not in head(f)]
chk("every source file names a copyright holder", missing_holder, [])
missing_exc = [f for f in runtime if "Artefact Exception v1.1" not in head(f)
               or "Origin Notice is preserved" not in head(f)]
chk("every runtime file states the Exception and its condition", missing_exc, [])
built = [f for f in files if f.endswith(".html") and not f.startswith("templates/")
         and "/vendor/" not in f and not f.endswith(".template.html")]
chk("built examples found", len(built) >= 10, True)
missing_built = [f for f in built if "Artefact Exception v1.1" not in head(f)
                 or "SPDX-License-Identifier: AGPL-3.0-or-later" not in head(f)]
chk("every built example carries the runtime header", missing_built, [])
wrong_exc = [f for f in sources if not is_runtime(f) and "part of its Artefact Runtime" in head(f)]
chk("toolkit files do not claim the Exception", wrong_exc, [])

print("\n" + "─" * 66)
print(f"{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
