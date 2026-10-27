#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""test_no_old_names.py — live instructions use the current names, not the old ones.

The repository was renamed to its current name, and the skills from
dashboard-* / powerbi-escape / sirkushest-kommunikasjon to tun-*. An old name in a live
instruction sends a reader, or an agent, looking for something that is not there.

Old names may still appear where they are history or a deliberate fixture. Those places
are listed in ALLOWED, each with its reason and the names it may use, and nowhere else.

Stdlib only. Scans the files git tracks.

    python3 tests/test_no_old_names.py
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# The repo name is distinctive enough to match after a "-" too, as in the old install
# marker the old installer wrote. The skill names are not: a "-" in
# front of them is another word (single-file-dashboard-new.html), so they keep the guard.
#: The former repository name, in two pieces so no single line carries it: the export
#: gate refuses a tree that still holds it as text, and this file has to hold it to
#: do its job.
OLD_REPO = "onedrive" + "-native-dashboards"

OLD = re.compile(
    r"(?<!\w)(" + OLD_REPO + r")(?![\w-])"
    r"|(?<![\w-])("
    r"dashboard-(?:new|data|help|publish|verify|\*)"
    r"|(?<!tun-)powerbi-escape"
    r"|sirkushest-kommunikasjon"
    r")(?![\w-])")

ANY = None
# path prefix -> (the old names allowed there, ANY for all; why)
ALLOWED = {
    "internal/": (ANY, "internal notes and archives, never exported"),
    "docs/18-naming.md": (ANY, "the naming history itself"),
    "docs/findings-index.md": ({OLD_REPO}, "the naming finding's quote"),
    "setup.py": ({OLD_REPO, "dashboard-new"},
                 "LEGACY_MARKERS keeps the old marker; a docstring names a past rename"),
    "tests/test_skill_links.py": ({OLD_REPO, "dashboard-new",
                                   "dashboard-verify", "dashboard-publish"},
                                  "fixtures for old installs and renamed-away skills"),
    "tests/test_no_old_names.py": (ANY, "this file"),
    ".claude-plugin/": ({"tun"},
                        "the plugin manifest names the plugin, and the plugin is called tun; "
                        "the old repo name and the plugin name are the same word after a rename"),
}


def allowed(rel: str, name: str) -> bool:
    for prefix, (names, _why) in ALLOWED.items():
        if rel.startswith(prefix) and (names is ANY or name in names):
            return True
    return False
TEXT_SUFFIXES = {".md", ".py", ".html", ".toml", ".json", ".js", ".css", ".txt", ".yml",
                 ".yaml", ".sh", ""}

passed = failed = 0


def chk(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS {label}")
    else:
        failed += 1
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def hits(text: str) -> list[tuple[int, str]]:
    return [(n, m.group(1) or m.group(2)) for n, line in enumerate(text.splitlines(), 1)
            for m in OLD.finditer(line)]


def main() -> int:
    print("no old repo or skill names in live instructions")
    print("─" * 62)
    files = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True,
                           text=True, check=True).stdout.split("\0")
    scanned, found = 0, []
    for rel in filter(None, files):
        if pathlib.Path(rel).suffix.lower() not in TEXT_SUFFIXES:
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        scanned += 1
        for n, name in hits(path.read_text(encoding="utf-8", errors="replace")):
            if not allowed(rel, name):
                found.append(f"{rel}:{n} {name}")
    print(f"  scanned {scanned} tracked text file(s)")
    chk("the scan resolved a real file list", scanned > 50, f"only {scanned}")
    chk("no old name outside the allowed places", not found, "\n       " + "\n       ".join(found))

    # controls: the pattern fires on each old name, and not on the current ones
    for old in (OLD_REPO, ".installed-by-" + OLD_REPO,
                "`dashboard-new`", "dashboard-verify skill",
                "skills/dashboard-*",
                "powerbi-escape", "sirkushest-kommunikasjon"):
        chk(f"control: flags {old!r}", bool(hits(old)))
    chk("control: an allowed file is still checked for other old names",
        not allowed("setup.py", "sirkushest-kommunikasjon"))
    for new in ("tun-new", "tun-powerbi-escape", "single-file-dashboard-new.html",
                "sirkushest"):
        chk(f"control: leaves {new!r} alone", not hits(new))
    print("─" * 62)
    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
