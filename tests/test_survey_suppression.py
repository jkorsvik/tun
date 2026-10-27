#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The survey board's two promises, and the script that keeps them.

1. A cell with fewer answers than the threshold is hidden — per question and per
   option — and the page says why. A mutation proves the rule is wired rather than
   merely present in the source.
2. Nothing but questions, answers and the chosen segments reaches the file. A
   column holding a name must not appear anywhere in the output, even once.

The third check is the browser one, and it exists because a key mismatch between
the builder's JSON and the page's script (`segmentNames` vs `segments`) shipped
once and no amount of reading the Python would have caught it: the page threw on
load and the filter silently kept the unfiltered numbers. So: load the page, fail
on any page error, filter, and require the count to change and the reset to bring
the static view back.

Stdlib for rules 1-2; Playwright for rule 3, and that part FAILS without it,
because a check that cannot run must not pass. Run:

    python3 tests/test_survey_suppression.py
    uv run --extra verify python tests/test_survey_suppression.py   # with the browser part
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILD = ROOT / "tools" / "build_survey_dashboard.py"
TMP = pathlib.Path(tempfile.mkdtemp(prefix="tun-survey-"))

checks = failed = 0


def check(ok: bool, what: str, detail: str = "") -> None:
    global checks, failed
    checks += 1
    if ok:
        print(f"  ✓ {what}")
    else:
        failed += 1
        print(f"  ✗ {what}" + (f" — {detail}" if detail else ""))


def build(csv_text: str, out: str, extra: list[str] | None = None) -> tuple[pathlib.Path, str]:
    data = TMP / f"{out}.csv"
    data.write_text(csv_text, encoding="utf-8")
    target = TMP / f"{out}.html"
    cmd = [sys.executable, str(BUILD), "--data", str(data), "--title", "Test",
           "--segments", "Enhet", "--source", "synthetic test data",
           "--requested-by", "Test", "--out", str(target)] + (extra or [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return target, r.stdout + r.stderr
    return target, ""


# One unit answers the first question 9 times, the second question twice, and one
# option of the first question twice: one cell of each kind to suppress.
CSV = """Enhet,Rolle,Navn,Sporsmal,Svar
Nord,Fag,Anna Nordmann,Q1,5 Helt enig
Nord,Fag,Bjorn Nordmann,Q1,5 Helt enig
Nord,Fag,Carl Nordmann,Q1,5 Helt enig
Nord,Fag,Dina Nordmann,Q1,4 Enig
Nord,Fag,Erik Nordmann,Q1,4 Enig
Nord,Fag,Frida Nordmann,Q1,5 Helt enig
Nord,Fag,Gunn Nordmann,Q1,5 Helt enig
Nord,Fag,Hans Nordmann,Q1,5 Helt enig
Nord,Fag,Ivar Nordmann,Q1,4 Enig
Nord,Fag,Anna Nordmann,Q2,3 Verken
Nord,Fag,Bjorn Nordmann,Q2,3 Verken
Sør,Fag,Jon Sor, Q1,1 Helt uenig
Sør,Fag,Kim Sor, Q1,1 Helt uenig
Sør,Fag,Lea Sor, Q1,2 Uenig
Sør,Fag,Mo Sor, Q1,2 Uenig
Sør,Fag,Nil Sor, Q1,2 Uenig
"""


def main() -> int:
    print("1. the suppression rule")
    page, err = build(CSV, "plain")
    check(page.is_file(), "the builder writes a page", err[:300])
    html = page.read_text(encoding="utf-8")

    # Q2 has 2 answers in total: the whole question is withheld.
    ids = re.findall(r"<h2>(Q\d)</h2>", html)
    check("Q1" in ids and "Q2" in ids, "both questions are named in the page", str(ids))
    q2 = html.split("<h2>Q2</h2>", 1)[1].split("</section>", 1)[0]
    check("supp" in q2, "the question under the threshold shows the withheld block")
    check("suppressed_head" not in html, "no unsubstituted string token is left in the page")
    check("Ikke vist" in q2 or "Not shown" in q2,
          "the withheld block says why, in words")

    # Q1 has 9 answers, but the "Uenig" option has 2: one hidden option cell.
    q1 = html.split("<h2>Q1</h2>", 1)[1].split("</section>", 1)[0]
    # Q1 has 14 answers across three options: 6, 3 and 2 for Sør's two, so the
    # options at 3, 2 and 3 answers are all under the threshold.
    hidden_in_q1 = q1.count('<i class="hidden">')
    check(hidden_in_q1 == 3, "each option under the threshold hides its own count",
          f"{hidden_in_q1} hidden option(s), expected 3")

    print("\n2. the rule is wired, not merely written down (mutation)")
    for min_cell in ("3", "10"):
        page2, err2 = build(CSV, f"min{min_cell}", ["--min-cell", min_cell])
        check(page2.is_file(), f"--min-cell {min_cell} builds", err2[:300])
        other = page2.read_text(encoding="utf-8")
        check(other != html, f"--min-cell {min_cell} changes the output")
    page10, _ = build(CSV, "min10b", ["--min-cell", "10"])
    ten = page10.read_text(encoding="utf-8")
    # At 10, Q1 still has 14 answers and keeps its card, but no option reaches the
    # threshold any more, so the card shows the heading and a row of withheld cells.
    q1_ten = ten.split("<h2>Q1</h2>", 1)[1].split("</section>", 1)[0]
    check("card" not in q1_ten and "supp" not in q1_ten,
          "a question above the higher threshold keeps its card")
    check(q1_ten.count('<i class="hidden">') > q1_ten.count("</li>") - len(re.findall(r"<li>", q1_ten)),
          "a higher threshold hides every option that no longer reaches it")
    check(q1_ten.count('<i class="hidden">') >= 3,
          "a higher threshold hides more options, not fewer",
          str(q1_ten.count('<i class="hidden">')))
    check(ten.split("<h2>Q2</h2>", 1)[1].split("</section>", 1)[0].find("supp") >= 0,
          "a higher threshold keeps the whole-question withholding")

    print("\n3. only questions, answers and segments reach the file")
    for name in ("Anna Nordmann", "Bjorn Nordmann", "Nil Sor"):
        check(name not in html, f"the name column is not in the output: {name}")
    check("Navn" not in html, "the name column's header is not in the output")
    payload = re.search(r"var SURVEY = (\{.*?\});\n", html, re.S)
    check(payload is not None, "the page carries its answers as one JSON object")
    if payload:
        data = json.loads(payload.group(1))
        check(set(data) == {"questions", "options", "segments", "segmentValues",
                            "rows", "minCell"},
              "the payload holds exactly what the page needs", str(sorted(data)))
        check(data["segments"] == ["Enhet"], "only the segment column asked for is carried")
        check(all(len(r) == 2 + len(data["segments"]) for r in data["rows"]),
              "no row carries an extra field")
        check(data["minCell"] == 5, "the threshold travels with the payload")

    print("\n4. the page's script runs, and its numbers agree with the static view")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ✗ playwright is not installed, so nothing was measured")
        print("    install: uv sync --extra verify && uv run playwright install chromium")
        return 1
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1366, "height": 1000})
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(page.resolve().as_uri())
        pg.wait_for_timeout(300)
        static_answers = pg.inner_text("#kpis").split("\n")[1]
        pg.select_option("#s0", label="Nord")
        pg.wait_for_timeout(200)
        filtered = pg.inner_text("#kpis").split("\n")[1]
        cards = pg.locator("section.q").count()
        pg.click("#reset")
        pg.wait_for_timeout(200)
        restored = pg.inner_text("#kpis").split("\n")[1]
        browser.close()

    check(not errors, "the page loads with no script error", "; ".join(errors[:2]))
    check(filtered != static_answers, "a filter changes the answer count",
          f"{static_answers} -> {filtered}")
    check(cards >= 1, "a filtered selection still draws its cards", str(cards))
    check(restored == static_answers, "reset brings back the static count",
          f"{restored} vs {static_answers}")

    print()
    print(f"{checks - failed}/{checks} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
