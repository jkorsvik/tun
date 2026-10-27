#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Delete each fix that tests/test_dashboard_kpis_and_labels.py covers, and require it to notice.

Same method as tests/mutate_builder_null_measures.py: every mutation is applied to a COPY
of the tree in a temp dir, so a kill between "mutate" and "restore" cannot leave a mutated
tree behind. Each mutation must turn at least one check red, and only checks of the case
named for it (K1 the KPI cards, L1 the bar labels).

Most of the fixes are in the page, so the harness needs the browser half, in all three
engines. Without Playwright, or when the test skipped anything, it prints SKIP and exits 2:
a harness that could not look must not pass.

    uv run --extra verify python tests/mutate_dashboard_kpis_and_labels.py   # about two minutes
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mutate_builder_null_measures import SKIPPED, copy_tree  # noqa: E402

TEST = "tests/test_dashboard_kpis_and_labels.py"
BUILDER = "tools/build_dashboard.py"
TEMPLATE = "templates/single-file-dashboard.html"
STRINGS = "templates/i18n/single-file-dashboard.strings"
WITH_BROWSER = "uv run --extra verify python tests/mutate_dashboard_kpis_and_labels.py"

# (name, the case it must turn red, file, fixed text, the text with the fix taken out)
MUTATIONS = [
    ("K1 legacy cards get a new label", "K1", BUILDER,
     """'    { label: "' + t["kpi_rows"] + '", value: fmt(rows.length) },\\n'""",
     """'    { label: "' + t["kpi_label_rows"] + '", value: fmt(rows.length) },\\n'"""),
    ("K1 a rate keeps the mean per row", "K1", BUILDER,
     '    "rate": ("total", "per_period", "distinct"),',
     '    "rate": ("total", "per_period", "distinct", "mean"),'),
    ("K1 a rate accepts --kpis mean", "K1", BUILDER,
     '        if "mean" in kinds and args.measure_kind == "rate":', "        if False:"),
    ("K1 per_period accepted without --time", "K1", BUILDER,
     '        if "per_period" in kinds and not args.time:', "        if False:"),
    ("K1 an empty --kpis gives no cards", "K1", BUILDER,
     "        if not kinds:\n            sys.exit(", "        if False:\n            sys.exit("),
    ("K1 an amount drops the mean per row", "K1", BUILDER,
     '    "amount": ("total", "per_period", "distinct", "mean"),',
     '    "amount": ("total", "per_period", "distinct"),'),
    ("K1 an unknown card is not named", "K1", BUILDER,
     "            if k not in KPI_CARDS:", "            if False:"),
    ("K1 per_period divides by rows", "K1", BUILDER,
     '"(uniq(valued(rows, META.measure), META.timeColumn).length))"',
     '"(valued(rows, META.measure).length))"'),
    ("K1 the nb count label is the old one", "K1", STRINGS,
     "kpi_label_distinct = {dimension} (antall)\n", "kpi_label_distinct = Unike {dimension}\n"),
    ("K1 a label is not escaped", "K1", BUILDER,
     "json.dumps(html.escape(label, quote=False), ensure_ascii=False)",
     "json.dumps(label, ensure_ascii=False)"),
    ("L1 no sideways bars", "L1", TEMPLATE,
     "  if (data.some(d => String(d.key).length > 16)) return sideBars(",
     "  if (false) return sideBars("),
    ("L1 always sideways bars", "L1", TEMPLATE,
     "  if (data.some(d => String(d.key).length > 16)) return sideBars(",
     "  if (data.some(d => String(d.key).length > 0)) return sideBars("),
    ("L1 a cut name loses its tooltip", "L1", TEMPLATE,
     "title.textContent = full; t.appendChild(title);", "title.textContent = full;"),
    ("L1 no cap on the name column", "L1", TEMPLATE,
     "  const lw = Math.min(Math.round(W * 0.45), Math.max(...labels.map(width)));",
     "  const lw = Math.max(...labels.map(width));"),
    ("L1 always four value steps", "L1", TEMPLATE,
     "  const steps = Math.max(1, Math.min(4, Math.floor(iw / (width(probe) + 16))));",
     "  const steps = 4;"),
]


def failing(stdout: str) -> list[str]:
    return re.findall(r"^  FAIL ([KL]\d)\b", stdout, re.M)


def run(tree: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(tree / TEST)], capture_output=True, text=True,
                          cwd=tree, timeout=600)


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
        if re.search(r"^  SKIP ", r.stdout, re.M):
            return skip("the test skipped part of its browser half")
        ok = r.returncode == 0 and not failing(r.stdout)
        print(f"{'ok  ' if ok else 'BAD '} control: unmutated copy is green in every engine")
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
            ok = r.returncode != 0 and cases == [want]
            bad += not ok
            print(f"{'ok  ' if ok else 'BAD '} {name}: {len(failing(r.stdout))} check(s) red, "
                  f"in {cases or 'none'}")
    print(f"{len(MUTATIONS) - bad}/{len(MUTATIONS)} mutations caught, each by exactly the case named for it")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
