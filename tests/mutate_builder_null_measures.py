#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Delete each fix that tests/test_builder_null_measures.py covers, and require it to notice.

Every mutation is applied to a COPY of the tree (tools/, templates/, tests/, plugins/,
examples/) in a temp dir, so a kill between "mutate" and "restore" cannot leave a
mutated tree behind. Each one must turn
at least one check red, and only checks of the cases named for it. Most fixes belong to
one case. The note and the average serve both B1 (a NULL) and B2 (an empty CSV cell), so
both cases must notice those. A red case that is not named means the case under test was
not the one that noticed.

Most of the fixes are in the page, so the harness needs the browser half. Without
Playwright it prints SKIP and exits 2: a harness that could not look must not pass.

    uv run --extra verify python tests/mutate_builder_null_measures.py   # a minute or two
"""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST = "tests/test_builder_null_measures.py"
BUILDER = "tools/build_dashboard.py"
TEMPLATE = "templates/single-file-dashboard.html"
COPIED = ("tools", "templates", "tests", "plugins", "examples")
SKIPPED = 2   # exit code when the browser half cannot run
WITH_BROWSER = "uv run --extra verify python tests/mutate_builder_null_measures.py"

# (name, the cases it must turn red, file, fixed text, the text before the fix)
MUTATIONS = [
    ("B1 numeric check on rows[0] again", ("B1",), BUILDER,
     "    if not is_numeric_column(rows, args.measure):",
     "    if not isinstance(rows[0].get(args.measure), (int, float)):"),
    ("B1 hint list from rows[0] again", ("B1",), BUILDER,
     "{', '.join(c for c in cols if is_numeric_column(rows, c)) or '(none found)'}",
     "{', '.join(c for c in cols if isinstance(rows[0].get(c), (int, float))) or '(none found)'}"),
    ("B1 numeric check ignores a text value", ("B1",), BUILDER,
     "return bool(values) and all(isinstance(v, (int, float)) and not isinstance(v, bool)\n"
     "                                for v in values)",
     "return bool(values) and any(isinstance(v, (int, float)) and not isinstance(v, bool)\n"
     "                                for v in values)"),
    ("B1+B2 no note about rows without a value", ("B1", "B2"), BUILDER,
     "    if no_value:\n", "    if False:\n"),
    ("B1 charts sum NULL as 0 again", ("B1",), TEMPLATE,
     "for (const r of valued(rows, measure)) m.set(r[key], (m.get(r[key]) || 0) + val(r[measure]));",
     "for (const r of rows) m.set(r[key], (m.get(r[key]) || 0) + (Number(r[measure]) || 0));"),
    ("B1+B2 average over all rows again", ("B1", "B2"), TEMPLATE,
     "  const avg = n ? total / n : 0;", "  const avg = rows.length ? total / rows.length : 0;"),
    ("B1 table decides numeric on rows[0] again", ("B1",), TEMPLATE,
     "  const isNum = c => numCols.has(c);",
     '  const isNum = c => rows.length && typeof rows[0][c] === "number";'),
    ("B2 coerce_numbers writes 0 again", ("B2",), BUILDER,
     'row[col] = _parse_num(row[col]) if row[col] not in (None, "") else None',
     'row[col] = _parse_num(row[col]) if row[col] not in (None, "") else 0'),
    ("B2 page CSV reader writes 0 again", ("B2",), TEMPLATE,
     'rows.forEach(r => r[col] = r[col] === "" ? null : parseNum(r[col]));',
     'rows.forEach(r => r[col] = r[col] === "" ? 0 : parseNum(r[col]));'),
    ("B3 fixed tools/ path again", ("B3",), BUILDER,
     '    print("  next: python3 " + _shell_arg(_verifier_path()) + " " + _shell_arg(args.out.as_posix()))',
     '    print("  next: python3 tools/verify_dashboard.py " + str(args.out))'),
    ("B3 always absolute", ("B3",), BUILDER,
     "        return verifier.relative_to(pathlib.Path.cwd().resolve()).as_posix()",
     "        return verifier.as_posix()"),
    ("B3 no quoting", ("B3",), BUILDER,
     """    return f'"{arg}"' if " " in arg else arg""", "    return arg"),
]


def failing(stdout: str) -> list[str]:
    return re.findall(r"^  FAIL (B\d):", stdout, re.M)


def run(tree: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(tree / TEST)], capture_output=True, text=True,
                          cwd=tree, timeout=600)


def copy_tree(dest: pathlib.Path) -> None:
    for part in COPIED:
        shutil.copytree(ROOT / part, dest / part, ignore=shutil.ignore_patterns("__pycache__"))


def skip(why: str) -> int:
    print(f"SKIP {why}. No mutation was run, so nothing is proven. Run: {WITH_BROWSER}")
    return SKIPPED


def main() -> int:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return skip("playwright not installed")
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        base = pathlib.Path(td) / "control"
        copy_tree(base)
        r = run(base)
        if r.returncode == 0 and re.search(r"^  SKIP ", r.stdout, re.M):
            return skip("the test skipped its browser half")
        ok = r.returncode == 0 and not failing(r.stdout)
        print(f"{'ok  ' if ok else 'BAD '} control: unmutated copy is green with the browser half")
        if not ok:
            print(r.stdout[-600:] + r.stderr[-300:])
            return 1
        for i, (name, want, rel, fixed, before) in enumerate(MUTATIONS):
            tree = pathlib.Path(td) / f"m{i}"
            copy_tree(tree)
            f = tree / rel
            text = f.read_text(encoding="utf-8")
            if text.count(fixed) != 1:
                print(f"BAD  {name}: expected the fixed text once in {rel}, found {text.count(fixed)}")
                bad += 1
                continue
            f.write_text(text.replace(fixed, before), encoding="utf-8")
            r = run(tree)
            cases = sorted(set(failing(r.stdout)))
            n = len(failing(r.stdout))
            ok = r.returncode != 0 and cases == sorted(want)
            bad += not ok
            print(f"{'ok  ' if ok else 'BAD '} {name}: {n} check(s) red, in {cases or 'none'}")
    print(f"{len(MUTATIONS) - bad}/{len(MUTATIONS)} mutations caught, each by exactly the cases named for it")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
