#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_onepager.py — the printable sheet: it builds, its numbers are the data's, and it is one page.

    python3 tests/test_onepager.py

Three halves, and the third is the one that matters:

  * the builder: what it computes, what it refuses, and that two builds agree;
  * the sheet: the provenance block, no script, no remote resource;
  * the page: tools/verify_print.py passes on the committed artefact, and FAILS when a
    sheet is too long or its type too small. A verifier nobody has seen fail is a verifier
    that may be structurally incapable of failing, so both mutations are run here, and each
    asserts the rule it should trip rather than only the exit code.
"""
from __future__ import annotations

import csv
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
EXAMPLE = ROOT / "examples" / "37-printable-onepager"
DATA = EXAMPLE / "salgsdata.csv"
ARTEFACT = EXAMPLE / "ett-ark.html"

PASSED = FAILED = 0


def chk(label: str, ok: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  ok   {label}")
    else:
        FAILED += 1
        print(f"  FAIL {label}" + (f" — {detail}" if detail else ""))


def build(out: pathlib.Path, *extra: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, SOURCE_DATE_EPOCH="1792836000")
    return subprocess.run(
        [sys.executable, str(TOOLS / "build_onepager.py"), "--data", str(DATA),
         "--title", "Salg per produkt, september 2026", "--dimension", "Produkt",
         "--measure", "Belop", "--period", "Maaned",
         "--source", "Syntetisk eksempeldata (salgsdata.csv)",
         "--requested-by", "Salgsavdelingen", "--out", str(out), *extra],
        capture_output=True, text=True, env=env)


def source_totals() -> tuple[dict[str, float], dict[str, float]]:
    """{category: total} for the last two periods, straight from the CSV."""
    per: dict[str, dict[str, float]] = {}
    with DATA.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            per.setdefault(row["Maaned"], {})
            per[row["Maaned"]][row["Produkt"]] = (
                per[row["Maaned"]].get(row["Produkt"], 0.0) + float(row["Belop"]))
    months = sorted(per)
    return per[months[-2]], per[months[-1]]


def visible(markup: str) -> str:
    """The text a reader sees, with tags and escapes undone enough to search."""
    text = re.sub(r"<[^>]+>", " ", markup)
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def main() -> int:
    before, latest = source_totals()
    total = sum(latest.values())
    change = 100.0 * (total - sum(before.values())) / sum(before.values())

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = pathlib.Path(tmp)

        print("the builder")
        out = tmpdir / "sheet.html"
        run = build(out)
        chk("it builds", run.returncode == 0, (run.stderr or run.stdout)[-400:])
        page = out.read_text(encoding="utf-8")
        text = visible(page)

        chk("the total is the data's own sum", f"{round(total):,}".replace(",", " ") in text
            or f"{round(total):,}".replace(",", "\u00a0") in text, f"expected {total:,.0f}")
        chk("the change is measured against the period before",
            f"{abs(change):.1f} %".replace(".", ".") in text.replace("\u00a0", " "),
            f"expected {change:+.1f} %")
        chk("the sheet says which period it prints", "2026-09" in text)
        chk("every category in the latest period is drawn", "Forsikring" in text
            and "Boliglån" in text)
        chk("what moved names the biggest riser", "Fondssparing" in text)
        chk("what moved carries both directions", "+38" in text.replace("\u2212", "-")
            and "\u2212" in text, text[text.find("Hva som endret"):][:220])

        chk("the period column is required to exist",
            build(tmpdir / "x.html", "--period", "FinnesIkke").returncode == 2)
        chk("--top is bounded", build(tmpdir / "y.html", "--top", "13").returncode == 2)
        bars_all = page.count('class="bar-row"')
        three = build(tmpdir / "z.html", "--top", "3")
        bars_three = ((tmpdir / "z.html").read_text(encoding="utf-8").count('class="bar-row"')
                      if three.returncode == 0 else -1)
        chk("--top changes how many bars are drawn",
            three.returncode == 0 and bars_all == 6 and bars_three == 3,
            f"all {bars_all}, --top 3 gave {bars_three}")

        print("the sheet")
        chk("it names its source, extract, build and requester",
            all(k in page for k in ("PROVENANCE", "Source data", "Extracted", "Built",
                                    "Requested by", "Rows")))
        chk("no script is loaded from a file", not re.search(r"<script[^>]+src=", page, re.I))
        chk("nothing is fetched over the network",
            not re.search(r"""(?:src|href)\s*=\s*["']https?://""", page, re.I))
        chk("the paper size is declared", re.search(r"@page\s*{[^}]*size\s*:\s*A4", page, re.I)
            is not None)
        chk("it stays small", out.stat().st_size < 200 * 1024, f"{out.stat().st_size} bytes")

        first = out.read_bytes()
        build(out)
        chk("two builds of the same data agree byte for byte", out.read_bytes() == first)

        en = tmpdir / "sheet-en.html"
        chk("the English build works too", build(en, "--lang", "en").returncode == 0)
        chk("and it is in English", "Source:" in visible(en.read_text(encoding="utf-8")))

        print("the page")
        if not ARTEFACT.is_file():
            chk("the committed artefact exists", False, str(ARTEFACT))
        else:
            ok = subprocess.run([sys.executable, str(TOOLS / "verify_print.py"), str(ARTEFACT)],
                                capture_output=True, text=True)
            chk("verify_print passes on the committed sheet", ok.returncode == 0,
                (ok.stdout or ok.stderr)[-400:])

        # Mutation 1: the failure this artefact exists to prevent. Three more bullets, or a
        # longer sentence, and the page silently becomes two.
        long_copy = tmpdir / "for-lang.html"
        long_copy.write_text(page.replace(
            '<footer>', '<div style="height:700px">mer</div><footer>'), encoding="utf-8")
        bad = subprocess.run([sys.executable, str(TOOLS / "verify_print.py"), str(long_copy)],
                            capture_output=True, text=True)
        chk("a sheet that grew past A4 is refused", bad.returncode == 1,
            (bad.stdout or bad.stderr)[-300:])
        chk("  and the rule that fires is the page length", "one page" in bad.stdout,
            bad.stdout[-300:])

        # Mutation 2: type below the floor. Printed, nobody can zoom it.
        tiny_copy = tmpdir / "for-lite.html"
        tiny_copy.write_text(page.replace("font-size:9pt", "font-size:6pt"), encoding="utf-8")
        small = subprocess.run([sys.executable, str(TOOLS / "verify_print.py"), str(tiny_copy)],
                              capture_output=True, text=True)
        chk("text under the floor is refused", small.returncode == 1,
            (small.stdout or small.stderr)[-300:])
        chk("  and the rule that fires is the type floor", "type floor" in small.stdout,
            small.stdout[-300:])

        # Mutation 3: a remote resource. A sheet that needs the network is not a sheet.
        net_copy = tmpdir / "for-nett.html"
        net_copy.write_text(page.replace(
            "</head>", '<link rel="stylesheet" href="https://example.invalid/x.css"></head>'),
            encoding="utf-8")
        net = subprocess.run([sys.executable, str(TOOLS / "verify_print.py"), str(net_copy)],
                            capture_output=True, text=True)
        chk("a remote resource is refused", net.returncode == 1, (net.stdout or net.stderr)[-300:])
        chk("  and the rule that fires is self-containment", "self-contained" in net.stdout,
            net.stdout[-300:])

    print("-" * 62)
    print(f"PASS: {PASSED}  FAIL: {FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
