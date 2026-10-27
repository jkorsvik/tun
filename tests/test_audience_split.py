#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The audience boundary of examples/29-audience-split, as a gate rather than a promise.

AGENTS.md rule 1: the security boundary is the folder, not a filter expression. Two
people who need different numbers get two files, from two extracts, built the same way.
That rule is only worth anything if somebody checks the files rather than the intent, so
this test builds both dashboards from the example's own CSVs and reads the inlined rows
back out of each page.

Stdlib only, temp directory only, no browser. The mutation control at the end appends a
foreign row to a *copy* of the narrow extract and requires the same check to fail, so a
test that passes because it looks at nothing cannot pass here.
"""
import csv
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "29-audience-split"
AUDIENCE = "Nord"

passed = failed = 0


def chk(label: str, ok: bool, detail: str = "", n: int | None = None) -> bool:
    global passed, failed
    if n is not None and n == 0:
        ok, detail = False, "checked 0 items"
    if ok:
        passed += 1
        print(f"  PASS {label}" + (f" ({n})" if n is not None else ""))
    else:
        failed += 1
        print(f"  FAIL {label}" + (f": {detail}" if detail else ""))
    return ok


def read_csv(path: pathlib.Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def build(csv_path: pathlib.Path, out: pathlib.Path, title: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_dashboard.py"),
         "--data", str(csv_path), "--title", title,
         "--dimension", "Produkt", "--measure", "Belop", "--time", "Maaned",
         "--filters", "Produkt",
         "--source", f"Syntetiske salgstall (generate_data.py) - {csv_path.name}",
         "--requested-by", "Test", "--out", str(out)],
        capture_output=True, text=True, cwd=ROOT)


def rows_of(page: pathlib.Path) -> list[dict]:
    """The page inlines its own rows; read them back instead of trusting the build log."""
    m = re.search(r"DASHBOARD_DATA=(\[.*?\]);", page.read_text(encoding="utf-8"), re.S)
    if not m:
        raise SystemExit(f"no DASHBOARD_DATA in {page.name}")
    return json.loads(m.group(1))


def main() -> int:
    wide_csv, narrow_csv = EX / "salg-alle.csv", EX / "salg-team-nord.csv"
    if not narrow_csv.exists():
        print("run generate_data.py in examples/29-audience-split first")
        return 2
    wide_rows, narrow_rows = read_csv(wide_csv), read_csv(narrow_csv)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        wide_out, narrow_out = tmp / "alle.html", tmp / "team-nord.html"
        rw = build(wide_csv, wide_out, "Salg, alle team")
        rn = build(narrow_csv, narrow_out, "Salg, team Nord")
        chk("the wide extract builds", rw.returncode == 0, rw.stderr[-300:])
        chk("the narrow extract builds", rn.returncode == 0, rn.stderr[-300:])
        if not (wide_out.exists() and narrow_out.exists()):
            return 1

        wide_page = wide_out.read_text(encoding="utf-8")
        narrow_page = narrow_out.read_text(encoding="utf-8")

        # 1 ---- the narrow file holds only its own rows
        wide_data, narrow_data = rows_of(wide_out), rows_of(narrow_out)
        chk("the narrow page carries exactly the narrow extract's rows",
            len(narrow_data) == len(narrow_rows) == 8,
            f"page {len(narrow_data)}, csv {len(narrow_rows)}", n=len(narrow_data))
        chk("the wide page carries exactly the wide extract's rows",
            len(wide_data) == len(wide_rows) == 24,
            f"page {len(wide_data)}, csv {len(wide_rows)}", n=len(wide_data))
        foreign_teams = sorted({r["Team"] for r in wide_rows if r["Team"] != AUDIENCE})
        chk("every row in the narrow page belongs to the audience",
            all(r["Team"] == AUDIENCE for r in narrow_data),
            str(sorted({r["Team"] for r in narrow_data})), n=len(narrow_data))
        chk("the wide page really does hold the other teams",
            {r["Team"] for r in wide_data} == {AUDIENCE, *foreign_teams},
            str(sorted({r["Team"] for r in wide_data})), n=len(foreign_teams))

        # 2 ---- and their names are not anywhere in the file, not just in the rows
        foreign_names = sorted({r["Selger"] for r in wide_rows if r["Team"] != AUDIENCE})
        leaked = [n for n in foreign_names if n in narrow_page]
        chk("no name from another team appears anywhere in the narrow file",
            not leaked, ", ".join(leaked), n=len(foreign_names))
        present = [n for n in foreign_names if n in wide_page]
        chk("... and the same names are found in the wide file, so that check is not blind",
            len(present) == len(foreign_names),
            f"{len(present)} of {len(foreign_names)}", n=len(present))

        # 3 ---- the totals are each file's own, derived from the CSV, never hard-coded
        def total(rows: list[dict]) -> int:
            return sum(int(r["Belop"]) for r in rows)

        chk("the narrow page's rows sum to the narrow extract's total",
            sum(int(r["Belop"]) for r in narrow_data) == total(narrow_rows),
            f"{sum(int(r['Belop']) for r in narrow_data)} vs {total(narrow_rows)}")
        chk("the wide page's rows sum to the wide extract's total",
            sum(int(r["Belop"]) for r in wide_data) == total(wide_rows),
            f"{sum(int(r['Belop']) for r in wide_data)} vs {total(wide_rows)}")
        chk("the two files disagree about the total, which is why they are two files",
            total(narrow_rows) != total(wide_rows))

        # 4 ---- the mutation control: a wrong split must fail the check above
        bad_csv = tmp / "salg-feil.csv"
        extra = next(r for r in wide_rows if r["Team"] != AUDIENCE)
        with narrow_csv.open(encoding="utf-8", newline="") as fh:
            text = fh.read()
        bad_csv.write_text(text + ",".join(extra[k] for k in
                                           ("Selger", "Team", "Produkt", "Maaned", "Belop")) + "\n",
                           encoding="utf-8")
        bad_out = tmp / "feil.html"
        rb = build(bad_csv, bad_out, "Salg, feil uttrekk")
        chk("the mutation builds (so the control tests the check, not the builder)",
            rb.returncode == 0, rb.stderr[-300:])
        bad_data = rows_of(bad_out)
        bad_page = bad_out.read_text(encoding="utf-8")
        chk("the mutation is caught: a foreign row in the extract reaches the page",
            any(r["Team"] != AUDIENCE for r in bad_data),
            str(sorted({r["Team"] for r in bad_data})), n=len(bad_data))
        chk("... and its name is now visible in the file, so check 2 would fire",
            extra["Selger"] in bad_page, extra["Selger"])

    print("-" * 60)
    print(f"PASS: {passed}  FAIL: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
