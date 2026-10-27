#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Empty measure values, and the verify hint, in tools/build_dashboard.py.

Three bugs, found by handing a Snowflake result to the builder (one case each):

  B1  the numeric check on --measure looked only at rows[0]. A NULL in the first row
      (normal in a query result) stopped the build, although every other value was a
      number. The rule is now the non-empty values of the column. Rows with no value
      stay in the table and are left out of the charts, never drawn as 0.
  B2  coerce_numbers() turned every empty cell of a numeric column into 0, which moves
      the average. Empty stays empty (None), in the builder and in the page's own CSV
      reader, and the page leaves it out of the average.
  B3  the build printed `python3 tools/verify_dashboard.py <out>`. In the installed
      plugin the tools live in skills/tun-new/engine/tools/, so that command failed.

Every case runs the real builder as a subprocess on a fixture written to a temp dir.
The page half opens the built file from a file:// URL. Without Playwright it is
reported as SKIP with the command to run, and the static half still runs.

    python3 tests/test_builder_null_measures.py
    uv run --extra verify python tests/test_builder_null_measures.py   # with the browser half
"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
BUILDER = TOOLS / "build_dashboard.py"
WITH_BROWSER = "uv run --extra verify python tests/test_builder_null_measures.py"

sys.path.insert(0, str(TOOLS))
import build_dashboard  # noqa: E402

PASS = FAIL = SKIP = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def skip(label: str) -> None:
    global SKIP
    SKIP += 1
    print(f"  SKIP {label} — playwright not installed. Run: {WITH_BROWSER}")


def build(builder: pathlib.Path, data: pathlib.Path, out: pathlib.Path, *extra: str,
          measure: str, dimension: str, cwd: pathlib.Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(builder), "--data", str(data), "--title", "t",
         "--dimension", dimension, "--measure", measure, "--out", str(out),
         "--source", "fixture", "--requested-by", "test", *extra],
        capture_output=True, text=True, cwd=cwd, timeout=120)


def open_page(browser, path: pathlib.Path):
    page = browser.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(path.resolve().as_uri())
    page.wait_for_selector("#kpis .kpi")
    return page, errors


def kpi_values(page) -> list[str]:
    return page.locator("#kpis .kpi .value").all_inner_texts()


def fmt(page, n: float) -> str:
    """The page's own number format, so the comparison does not depend on the locale."""
    return page.evaluate("n => META.numberFormat.format(n)", n)


# ── fixtures ─────────────────────────────────────────────────────────────────
MONTHS = [f"{y}-{m:02d}" for y in (2024, 2025, 2026) for m in range(1, 13)]
REGIONS = ("Oslo", "Vestland", "Nordland")


def snowflake_rows() -> list[dict]:
    """36 rows shaped like a Snowflake result. Only rows[0] has a NULL measure, and it
    is the only row for its month and its region, so a NULL drawn as 0 shows up as an
    extra bar and an extra point."""
    rows = [{"MAANED": m, "FYLKE": REGIONS[i % 3], "NOK_PER_PERSON": 1000 + 10 * i}
            for i, m in enumerate(MONTHS)]
    rows[0]["FYLKE"] = "Tomt"
    rows[0]["NOK_PER_PERSON"] = None
    return rows


def case_b1(tmp: pathlib.Path, browser) -> None:
    print("\nB1: a NULL measure in rows[0] does not stop the build")
    rows = snowflake_rows()
    data = tmp / "b1.json"
    data.write_text(json.dumps(rows), encoding="utf-8")
    out = tmp / "b1.html"
    r = build(BUILDER, data, out, "--time", "MAANED", "--filters", "FYLKE",
              measure="NOK_PER_PERSON", dimension="FYLKE")
    check("B1: builds", r.returncode == 0, (r.stdout + r.stderr).strip()[-200:])
    note = ("  note: 1 of 36 rows have no 'NOK_PER_PERSON' value. They show empty in the "
            "table and are left out of the charts and the average.")
    check("B1: says how many rows have no value", note in r.stdout.splitlines(),
          r.stdout.strip()[-300:])

    # The hint list had the same rows[0] flaw: NOK_PER_PERSON was missing from it.
    r = build(BUILDER, data, tmp / "b1-text.html", measure="FYLKE", dimension="FYLKE")
    check("B1: a text measure is still rejected",
          r.returncode != 0 and "--measure 'FYLKE' is not numeric" in r.stderr, r.stderr[-200:])
    check("B1: and the hint names the numeric column whose rows[0] is NULL",
          r.stderr.rstrip().endswith("pick a numeric one from: NOK_PER_PERSON"), r.stderr[-200:])

    # Deciding on the non-empty values must not loosen the check.
    bad = [dict(x) for x in rows]
    bad[5]["NOK_PER_PERSON"] = "n/a"
    data_bad = tmp / "b1-bad.json"
    data_bad.write_text(json.dumps(bad), encoding="utf-8")
    r = build(BUILDER, data_bad, tmp / "b1-bad.html", measure="NOK_PER_PERSON", dimension="FYLKE")
    check("B1: one text value among numbers is still rejected",
          r.returncode != 0 and "--measure 'NOK_PER_PERSON' is not numeric" in r.stderr,
          f"exit={r.returncode} {r.stderr[-200:]}")
    empty = [dict(x, NOK_PER_PERSON=None) for x in rows]
    data_empty = tmp / "b1-empty.json"
    data_empty.write_text(json.dumps(empty), encoding="utf-8")
    r = build(BUILDER, data_empty, tmp / "b1-empty.html", measure="NOK_PER_PERSON", dimension="FYLKE")
    check("B1: a column with no values at all is still rejected",
          r.returncode != 0 and "--measure 'NOK_PER_PERSON' is not numeric" in r.stderr,
          f"exit={r.returncode} {r.stderr[-200:]}")

    if browser is None:
        skip("B1: the page leaves the NULL row out of both charts")
        return
    if not out.exists():
        check("B1: page checks need the built file", False, "the build failed above")
        return
    page, errors = open_page(browser, out)
    bars = page.locator("#chart1 rect.bar").count()
    labels = page.locator("#chart1 text").all_inner_texts()
    check("B1: bar chart has the 3 regions with values, no bar for the NULL row",
          bars == 3 and "Tomt" not in labels, f"bars={bars} labels={labels}")
    dots = page.locator("#chart2 circle.dot").count()
    check("B1: line chart has 35 points, none for the NULL month", dots == 35, f"dots={dots}")
    # 35 values 1010..1350, mean 1180. Dividing by 36 rows would give 1147.
    avg = kpi_values(page)[3]
    check("B1: the average is over the 35 values", avg == fmt(page, 1180), f"avg={avg!r}")
    th = page.locator('#tbl th[data-col="NOK_PER_PERSON"]').get_attribute("class") or ""
    check("B1: the table still treats the column as numeric", "num" in th.split(), f"class={th!r}")
    check("B1: no page errors", not errors, str(errors)[:200])
    page.close()


def case_b2(tmp: pathlib.Path, browser) -> None:
    print("\nB2: an empty cell in a numeric column stays empty, not 0")
    rows = [{"Region": "A", "Belop": "10", "Kode": "x"}, {"Region": "A", "Belop": "", "Kode": ""},
            {"Region": "B", "Belop": "20", "Kode": "y"}, {"Region": "B", "Belop": None, "Kode": "z"}]
    got = build_dashboard.coerce_numbers([dict(r) for r in rows])
    check("B2: coerce_numbers keeps empty as None in a numeric column",
          [r["Belop"] for r in got] == [10, None, 20, None], str([r["Belop"] for r in got]))
    check("B2: and leaves a text column alone", [r["Kode"] for r in got] == ["x", "", "y", "z"],
          str([r["Kode"] for r in got]))

    # rows[0] has a value, so this case does not depend on the B1 fix.
    data = tmp / "b2.csv"
    with data.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["Region", "Belop"])
        w.writeheader()
        w.writerows({"Region": r["Region"], "Belop": r["Belop"] or ""} for r in rows)
    out = tmp / "b2.html"
    r = build(BUILDER, data, out, measure="Belop", dimension="Region")
    check("B2: builds", r.returncode == 0, (r.stdout + r.stderr).strip()[-200:])
    check("B2: the build counts the 2 empty cells",
          any(ln.startswith("  note: 2 of 4 rows have no 'Belop' value.")
              for ln in r.stdout.splitlines()), r.stdout.strip()[-300:])

    if browser is None:
        skip("B2: the page shows empty cells empty and leaves them out of the average")
        return
    if not out.exists():
        check("B2: page checks need the built file", False, "the build failed above")
        return
    page, errors = open_page(browser, out)
    total, _, _, avg = kpi_values(page)
    check("B2: the total is 30", total == fmt(page, 30), f"total={total!r}")
    # (10 + 20) / 2. With the empty cells as 0 it is (10 + 0 + 20 + 0) / 4 = 7.5.
    check("B2: the average is 15, over the 2 values", avg == fmt(page, 15), f"avg={avg!r}")
    col = page.evaluate("""() => {
        const i = [...document.querySelectorAll('#tbl th')].findIndex(th => th.dataset.col === 'Belop');
        return [...document.querySelectorAll('#tbl tbody tr')].map(tr => tr.children[i].textContent);
    }""")
    check("B2: the table shows the empty cells empty, last", col == [fmt(page, 20), fmt(page, 10), "", ""],
          str(col))
    # The page has its own CSV reader (drag a file in, or paired mode with DASHBOARD_CSV).
    # It promises the builder's rule, so it must keep empty as empty too.
    parsed = page.evaluate("() => parseCSV('Region,Belop\\nA,10\\nB,\\n').map(r => r.Belop)")
    check("B2: the page's own CSV reader keeps empty as null", parsed == [10, None], str(parsed))
    check("B2: no page errors", not errors, str(errors)[:200])
    page.close()


def next_command(stdout: str) -> list[str]:
    """The `next:` command the build printed, split the way a shell would (double quotes only)."""
    lines = [ln for ln in stdout.splitlines() if ln.startswith("  next: ")]
    if len(lines) != 1:
        return []
    return [a or b for a, b in re.findall(r'"([^"]*)"|(\S+)', lines[0][len("  next: "):])]


def case_b3(tmp: pathlib.Path, browser) -> None:
    print("\nB3: the printed verify command works where the builder is installed")
    data = ROOT / "examples" / "01-hello-dashboard" / "salgsdata.csv"
    args = ("--time", "Maaned")

    # Repo layout, run from the repo root as AGENTS.md does: the hint is unchanged.
    out = tmp / "b3-repo.html"
    r = build(BUILDER, data, out, *args, measure="Belop", dimension="Produkt")
    cmd = next_command(r.stdout)
    check("B3: repo layout still prints python3 tools/verify_dashboard.py <out>",
          cmd == ["python3", "tools/verify_dashboard.py", str(out)], str(cmd))

    # Installed plugin layout (raiwork-tun-plugin): the engine sits in
    # skills/tun-new/engine/, and the agent runs from the user's working folder.
    # Both paths hold a space, as a OneDrive folder does on Windows.
    engine = tmp / "Skill dir" / "skills" / "tun-new" / "engine"
    for part in ("tools", "templates"):
        shutil.copytree(ROOT / part, engine / part, ignore=shutil.ignore_patterns("__pycache__"))
    work = tmp / "Mitt arbeid"
    work.mkdir()
    rel_out = pathlib.Path("dashboards") / "salg.html"
    r = build(engine / "tools" / "build_dashboard.py", data, rel_out, *args,
              measure="Belop", dimension="Produkt", cwd=work)
    check("B3: plugin layout builds", r.returncode == 0, (r.stdout + r.stderr).strip()[-200:])
    cmd = next_command(r.stdout)
    verifier = (engine / "tools" / "verify_dashboard.py").resolve()
    check("B3: the printed verifier path is the engine's own verifier",
          len(cmd) == 3 and cmd[0] == "python3"
          and (work / cmd[1]).resolve() == verifier, f"{cmd} vs {verifier}")
    check("B3: the printed artefact path is the built file",
          len(cmd) == 3 and (work / cmd[2]).resolve() == (work / rel_out).resolve(), str(cmd))
    # Run it as printed. A wrong path fails before the verifier prints anything.
    if len(cmd) == 3:
        v = subprocess.run([sys.executable, *cmd[1:]], capture_output=True, text=True,
                           cwd=work, timeout=180)
        check("B3: and running it reaches the verifier",
              f"verifying {rel_out.name}" in v.stdout and "can't open file" not in v.stderr,
              (v.stdout + v.stderr).strip()[:200])


CASES = (case_b1, case_b2, case_b3)


def main() -> int:
    print("builder: empty measure values, and the verify hint")
    print("─" * 62)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        if sync_playwright is None:
            for case in CASES:
                case(tmp, None)
        else:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                try:
                    for case in CASES:
                        case(tmp, browser)
                finally:
                    browser.close()

    print("─" * 62)
    tail = f"  SKIP: {SKIP} (browser half; run: {WITH_BROWSER})" if SKIP else ""
    print(f"PASS: {PASS}  FAIL: {FAIL}{tail}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
