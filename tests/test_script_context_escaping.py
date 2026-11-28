#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""A value in a script context cannot end the script element.

`json.dumps` makes a string safe as JSON and says nothing about the HTML parser.
A CSV cell holding `</script><img src=x onerror=...>` closes the data block where
it is written raw, and the rest of the cell becomes markup. This is the sibling of
`test_dashboard_escapes_data.py`: that test proves a value is safe in `innerHTML`,
this one proves it is safe in a `<script>` element. Its payload cannot close a
script, which is why it passed while this defect was live.

The gate is static and needs no browser: the number of real `</script>` closers in
a hostile build must equal the number in a benign build of the same builder, the
payload must not appear as raw markup, and the escaped `\\u003c` form must be
present. Run it on the tree before `tools/build_*.py` used `as_script_json` and
four of these checks fail, which is the mutation evidence for this gate.
"""
from __future__ import annotations

import csv
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
PAYLOAD = "</script><img src=x onerror=alert(1)>"
PASS = FAIL = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def run(script: str, args: list[str], out: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOLS / script), *args, "--out", str(out)],
                          capture_output=True, text=True, cwd=ROOT, timeout=120)


def write_csv(path: pathlib.Path, head: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(head)
        writer.writerows(rows)


def verdict(label: str, clean: pathlib.Path, hostile: pathlib.Path) -> None:
    good = clean.read_text(encoding="utf-8")
    bad = hostile.read_text(encoding="utf-8")
    check(f"{label}: build wrote a file", bool(bad))
    check(f"{label}: same number of </script> closers as a benign build",
          bad.count("</script>") == good.count("</script>"),
          f"{bad.count('</script>')} hostile vs {good.count('</script>')} benign")
    check(f"{label}: payload is not raw markup", "<img" not in bad)
    check(f"{label}: payload is present in escaped form", "\\u003c/script" in bad)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)

        # Dashboard: a plain cell, the source line, and a filter column name.
        write_csv(tmp / "clean.csv", ["Region", "Produkt", "Belop", "Maaned"],
                 [["Oslo", "A", "100", "2026-01"]])
        write_csv(tmp / "cell.csv", ["Region", "Produkt", "Belop", "Maaned"],
                 [[PAYLOAD, "A", "100", "2026-01"]])
        write_csv(tmp / "col.csv", ["Region", "Produkt", "Belop", "Maaned", PAYLOAD],
                 [["Oslo", "A", "100", "2026-01", "x"]])

        dash = ["--title", "T", "--dimension", "Produkt", "--measure", "Belop",
                "--time", "Maaned", "--filters", "Region,Produkt",
                "--requested-by", "r"]
        run("build_dashboard.py", ["--data", str(tmp / "clean.csv"), *dash,
                                   "--source", "s"], tmp / "dash-clean.html")
        run("build_dashboard.py", ["--data", str(tmp / "cell.csv"), *dash,
                                   "--source", "s"], tmp / "dash-cell.html")
        run("build_dashboard.py", ["--data", str(tmp / "clean.csv"), *dash,
                                   "--source", PAYLOAD], tmp / "dash-source.html")
        col_dash = ["--title", "T", "--dimension", "Produkt", "--measure", "Belop",
                    "--time", "Maaned", "--filters", "Region,Produkt," + PAYLOAD,
                    "--requested-by", "r"]
        run("build_dashboard.py", ["--data", str(tmp / "col.csv"), *col_dash,
                                   "--source", "s"], tmp / "dash-col.html")

        verdict("dashboard cell", tmp / "dash-clean.html", tmp / "dash-cell.html")
        verdict("dashboard source", tmp / "dash-clean.html", tmp / "dash-source.html")
        verdict("dashboard column", tmp / "dash-clean.html", tmp / "dash-col.html")

        # Survey: a free-text answer can hold the payload.
        head = ["Enhet", "Sporsmal", "Svar"]
        write_csv(tmp / "survey-clean.csv", head, [["Oslo", "Q", "3 Verken"]])
        write_csv(tmp / "survey-evil.csv", head, [[PAYLOAD, "Q", "3 Verken"]])
        surv = ["--title", "S", "--segments", "Enhet", "--question-col", "Sporsmal",
                "--answer-col", "Svar"]
        run("build_survey_dashboard.py", ["--data", str(tmp / "survey-clean.csv"), *surv],
            tmp / "survey-clean.html")
        run("build_survey_dashboard.py", ["--data", str(tmp / "survey-evil.csv"), *surv],
            tmp / "survey-evil.html")
        verdict("survey cell", tmp / "survey-clean.html", tmp / "survey-evil.html")

        # Cube: the dimension name is written into META.
        write_csv(tmp / "cube-clean.csv", ["Team", "Maaned", "Belop"],
                  [["A", "2026-01", "10"], ["B", "2026-02", "20"]])
        write_csv(tmp / "cube-evil.csv", [PAYLOAD, "Maaned", "Belop"],
                  [["A", "2026-01", "10"], ["B", "2026-02", "20"]])
        cube = ["--time", "Maaned", "--time-grain", "month", "--measures", "Belop:sum",
                "--title", "T", "--requested-by", "r"]
        run("build_cube_dashboard.py", ["--data", str(tmp / "cube-clean.csv"),
                                        "--dims", "Team", *cube], tmp / "cube-clean.html")
        run("build_cube_dashboard.py", ["--data", str(tmp / "cube-evil.csv"),
                                        "--dims", PAYLOAD, *cube], tmp / "cube-evil.html")
        verdict("cube dimension", tmp / "cube-clean.html", tmp / "cube-evil.html")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
