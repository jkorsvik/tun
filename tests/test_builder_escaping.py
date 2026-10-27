#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""What the caller types must not become markup or code.

ROADMAP A0b. The dashboard builder pasted its own arguments into the template: the
title into `<h1>` and `<title>`, a column name into a JavaScript string. So a title of
`<img src=x onerror=…>` ran script in a file people open in a tenant's document store,
and a column named `Navn "sitert"` ended the string literal it was pasted into and
stopped the page (`Unexpected identifier`).

Three assertions, on one hostile build, then a mutation that proves they can fail:

  1. the `<h1>` reads the title back, character for character;
  2. no element made of the title exists (nothing was parsed as markup);
  3. `META` is defined and `META.dimension` is the column name, so the JavaScript
     string survived a quote.

The mutation is not a patched copy of the test: it copies today's tree, strips the
four calls that make a value safe, rebuilds the same input, and requires the checks to
fail. A gate that cannot fail proves nothing, and this one shipped broken twice: once
because no mutation existed, and once because the mutant was pinned to `origin/main`,
so the day the fix merged the control could no longer fail. Any mutation that does not
land exactly once aborts the run instead of passing quietly.

    uv run --extra verify python tests/test_builder_escaping.py
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_dashboard.py"
ORIGINAL = BUILDER.read_text(encoding="utf-8")
TITLE = 'Salg <b>&"x" <img src=x onerror=alert(1)>'
COLUMN = 'Navn "sitert"'
SOURCE = 'fil med & og "tegn"'
REQUESTED_BY = "Test <i>"

checks = failed = 0


def check(ok: bool, what: str, detail: str = "") -> None:
    global checks, failed
    checks += 1
    print(f"  {'✓' if ok else '✗'} {what}" + ("" if ok else f" — {detail}"))
    if not ok:
        failed += 1


def build(builder: pathlib.Path, data: pathlib.Path, out: pathlib.Path,
          tools_dir: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    """Build with one builder. `tools_dir` is a tree to import from (tokens, i18n)."""
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin",
           "TUN_TOKENS": "", "PYTHONPATH": str(tools_dir) if tools_dir else ""}
    return subprocess.run(
        [sys.executable, str(builder), "--data", str(data), "--title", TITLE,
         "--dimension", COLUMN, "--measure", "Belop", "--time", "Maaned",
         "--source", SOURCE, "--requested-by", REQUESTED_BY, "--out", str(out)],
        capture_output=True, text=True, cwd=ROOT, env=env, timeout=120)


# The mutation is the bug itself, re-applied to today's source: each entry is the call
# that makes the value safe, and what the builder did before it existed. Pinning a commit
# instead (this test did, to `origin/main`) dies the day the fix merges: the mutant then
# carries the fix too and the control can never fail again.
MUTATIONS = (
    ("json.dumps(value, ensure_ascii=False)", "str(value)"),
    ("html.escape(args.title)", "str(args.title)"),
    ("html.escape(source_name)", "str(source_name)"),
    ('"DATA_META.source || " + json.dumps(source_name, ensure_ascii=False)',
     '"DATA_META.source || \\"" + source_name + "\\""'),
)


def mutated_builder(tmp: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path, list[str]]:
    """A copy of today's builder with every escaping call removed, in a tree it can run from.

    Returns the tree, the builder, and one line per mutation that applied."""
    tree = tmp / "mutant"
    for name in ("tools", "templates", "plugins"):
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, tree / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    builder = tree / "tools" / "build_dashboard.py"
    if not builder.is_file():
        return tree, builder, []
    source = builder.read_text(encoding="utf-8")
    applied, missing = [], []
    for old, new in MUTATIONS:
        count = source.count(old)
        if count != 1:
            missing.append(f"{old!r} appears {count} times")
        source = source.replace(old, new)
        applied.append(f"{old} -> {new}")
    if missing:
        # A mutation that did not land leaves the safe builder in place, and the control
        # then "passes" while proving nothing. Refuse to run it.
        sys.exit("error: the mutation did not apply: " + "; ".join(missing))
    builder.write_text(source, encoding="utf-8")
    return tree, builder, applied


def probe(page, path: pathlib.Path) -> dict:
    errors: list[str] = []
    dialogs: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page.goto(path.resolve().as_uri())
    page.wait_for_timeout(300)
    out = page.evaluate("""() => ({
        h1: document.querySelector('h1') ? document.querySelector('h1').textContent : null,
        injected: !!document.querySelector('h1 b, h1 img'),
        meta: (typeof META !== 'undefined') ? META.dimension : null,
        headers: [...document.querySelectorAll('#tbl thead th')].map(e => e.dataset.col),
        chart: !!document.querySelector('#chart1 svg text, #chart1 svg rect'),
    })""")
    out["errors"] = errors
    out["dialogs"] = dialogs
    return out


def assertions(name: str, got: dict) -> None:
    check(got["h1"] == TITLE, f"{name}: the heading reads the title back", repr(got["h1"])[:120])
    check(not got["injected"], f"{name}: nothing in the title became an element")
    check(got["meta"] == COLUMN, f"{name}: the column name survived its JavaScript string",
          repr(got["meta"]))
    check(COLUMN in got["headers"], f"{name}: the table header shows the column name",
          str(got["headers"]))
    check(not got["errors"], f"{name}: no page error", "; ".join(got["errors"])[:160])
    check(not got["dialogs"], f"{name}: nothing in the title ran script", str(got["dialogs"])[:120])


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ✗ playwright is not installed, so nothing was measured")
        print("    install: uv sync --extra verify && uv run playwright install chromium")
        return 1

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        data = tmp / "nasty.csv"
        data.write_text(f'{COLUMN},Maaned,Belop\nA,2026-01,10\nB,2026-02,20\n',
                        encoding="utf-8")
        new_out = tmp / "new.html"
        r = build(BUILDER, data, new_out)
        check(new_out.is_file(), "the hostile build succeeds", (r.stderr or r.stdout)[-200:])
        if not new_out.is_file():
            print(f"\n{checks - failed}/{checks} checks passed")
            return 1

        tree, mutant, applied = mutated_builder(tmp)
        old_out = tmp / "mutant.html"
        if mutant.is_file():
            check(mutant.read_text(encoding="utf-8") != ORIGINAL,
                  "mutation: the mutant builder is not today's builder",
                  f"{len(applied)} mutation(s) applied")
            build(mutant, data, old_out, tree / "tools")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            assertions("current", probe(page, new_out))
            page.close()
            if mutant.is_file() and old_out.is_file():
                page = browser.new_page()
                was = probe(page, old_out)
                page.close()
                fired = [k for k in ("h1", "injected", "meta", "errors", "dialogs")
                         if (was[k] != TITLE if k == "h1" else
                             was[k] is not None if k == "meta" else was[k])]
                check(bool(fired),
                      "mutation: the unescaped builder fails these checks, so the gate can fail",
                      f"the mutant survived; signals checked: {fired}")
            else:
                check(False, "mutation: the mutant builder could be built",
                      f"tree={tree} builder={mutant} out={old_out}")
            browser.close()

    print()
    print(f"{checks - failed}/{checks} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
