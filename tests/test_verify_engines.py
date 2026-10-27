#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_verify_engines.py — every verify tool can run in Chromium, Firefox and WebKit.

Stdlib only; launches no browser.

    python3 tests/test_verify_engines.py

A reader opens a shared file in whatever browser they have, so the verify tools take
--engines (tools/verify_standalone_core.py) and CI runs the documented commands in all
three engines (tools/verify_documented.py). Both halves can rot quietly: a new tool that
calls pw.chromium.launch() verifies one engine and still prints PASS, and a runner that
finds no commands checks nothing and still exits 0. These assertions catch both.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import verify_documented as documented  # noqa: E402
import verify_standalone_core as core  # noqa: E402

passed = failed = 0


def chk(label, got, want):
    global passed, failed
    if got == want:
        print(f"  PASS {label}")
        passed += 1
    else:
        print(f"  FAIL {label}: got {got!r}, wanted {want!r}")
        failed += 1


def rejects(value: str) -> bool:
    try:
        core.engines_arg(value)
    except argparse.ArgumentTypeError:
        return True
    return False


print("--engines parsing")
chk("all means the three engines", core.engines_arg("all"), ("chromium", "firefox", "webkit"))
chk("a subset keeps its order", core.engines_arg("webkit,chromium"), ("webkit", "chromium"))
chk("spaces and repeats are dropped", core.engines_arg(" firefox , firefox "), ("firefox",))
chk("an unknown engine is refused", rejects("chromium,safari"), True)
chk("an empty list is refused", rejects(" , "), True)
chk("the default is chromium alone", core.DEFAULT_ENGINES, ("chromium",))

print("screenshots and failure labels")
p = pathlib.Path("/x/deck.html")
chk("chromium keeps the documented name", core.shot_path(p, ".verify.png", "chromium").name,
    "deck.verify.png")
chk("other engines get their own file", core.shot_path(p, ".verify.png", "webkit").name,
    "deck.webkit.verify.png")
f1 = ["old", "new"]
core.label_failures(f1, 1, "firefox", ("chromium", "firefox"))
chk("several engines: only the new failures are labelled", f1, ["old", "firefox: new"])
f2 = ["old", "new"]
core.label_failures(f2, 1, "chromium", ("chromium",))
chk("one engine: the text is left alone", f2, ["old", "new"])

print("every tool that opens a browser takes the shared --engines")
tools = sorted((REPO / "tools").glob("verify_*.py")) + sorted(REPO.glob("examples/*/verify_*.py"))
launching = [t for t in tools if ".launch()" in t.read_text(encoding="utf-8")]
chk("found the browser-launching tools and example verifiers", len(launching) >= 12, True)
for t in launching:
    src = t.read_text(encoding="utf-8")
    name = t.relative_to(REPO)
    hard = re.findall(r"\.(chromium|firefox|webkit)\.launch\(", src)
    chk(f"{name}: no hard-coded engine launch", hard, [])
    chk(f"{name}: uses the shared --engines parser",
        "add_engines_arg" in src or "engines_arg" in src, True)
    chk(f"{name}: keeps no engine list of its own",
        re.search(r"^ENGINES\s*=", src, re.M) is None or t.name == "verify_standalone_core.py", True)

print("the documented commands the CI runs")
found = documented.commands()
chk("finds documented commands (a runner with none checks nothing)", len(found) >= 10, True)
names = {pathlib.Path(words[0]).stem for _, _, words in found}
for tool in ("verify_dashboard", "verify_standalone_core", "verify_slide_deck",
             "verify_process_diagram", "verify_viewports", "verify_nojs_fallback",
             "verify_app_shell"):
    chk(f"covers {tool}", tool in names, True)
example_verifiers = {t.stem for t in REPO.glob("examples/*/verify_*.py")}
chk("covers every example's own verifier", sorted(example_verifiers - names), [])
fence = "x\n```bash\npython3 tools/verify_x.py \\\n  a.html \\\n  --out o\n```\npython3 tools/verify_y.py b.html\n"
for given, want in ((["a.html"], ["a.html", "--engines", "all"]),
                    (["a.html", "--engines", "webkit"], ["a.html", "--engines", "all"]),
                    (["a.html", "--engines"], ["a.html", "--engines", "all"])):
    got = list(given)
    documented.set_flag(got, "--engines", "all")
    chk(f"set_flag {given}", got, want)
root = pathlib.Path("/repo")
log = "\n".join(["  · chromium", "  ✓ fine", "  · webkit",
                 'Traceback (most recent call last):',
                 '  File "/repo/examples/13/verify_x.py", line 232, in run_with_js',
                 '  File "/venv/lib/python3.12/site-packages/playwright/_impl/x.py", line 9, in f',
                 *[f"  call log {i}" for i in range(14)]])
detail = documented.failure_detail(log, root).split("\n      ")
chk("failure names the engine that was running last", detail[0], "· webkit")
chk("failure keeps this repo's frame and drops the library's",
    [d for d in detail if d.startswith("File")], ['File "/repo/examples/13/verify_x.py", line 232, in run_with_js'])
chk("failure still ends with the last twelve lines", detail[-12:], [f"  call log {i}" for i in range(2, 14)])
chk("joins continuations, reads only fenced lines", documented.fenced_lines(fence),
    ["python3 tools/verify_x.py a.html --out o"])

print("\n" + "-" * 66)
print(f"{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
