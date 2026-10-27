#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Example 30: the JSON in, the CSV out, and the page built from them agree.

A dashboard whose numbers nobody re-derives is a picture. This suite reads ordrer.json,
computes the row count and the total, and requires both to appear in the artefact, so a CSV
left stale by an edited generator, or an HTML edited by hand, fails here. The last check is
the flattener's own guard: one line per order is asserted, so a two-line order must stop it.
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile

EX = pathlib.Path(__file__).resolve().parent.parent / "examples" / "30-json-to-dashboard"
passed = failed = 0


def chk(label, got, want=True):
    global passed, failed
    if got == want:
        passed += 1
        print(f"  PASS {label}")
    else:
        failed += 1
        print(f"  FAIL {label}: got {got!r}, wanted {want!r}")


def main():
    payload = json.loads((EX / "ordrer.json").read_text(encoding="utf-8"))
    records = payload["records"]
    total = sum(r["amountNok"] for r in records)
    chk("the payload says how many it holds", payload["total"], len(records))
    chk("27 records, 3 363 390 NOK", (len(records), total), (27, 3_363_390))

    csv_rows = (EX / "salg.csv").read_text(encoding="utf-8").strip().splitlines()
    chk("the CSV has a header plus every record", len(csv_rows), len(records) + 1)
    chk("the CSV columns are the builder's", csv_rows[0], "Maaned,Region,Produkt,Kanal,Belop")
    chk("the CSV sums to the JSON",
        sum(int(r.split(",")[-1]) for r in csv_rows[1:]), total)
    chk("months are cut to a month", sorted({r.split(",")[0] for r in csv_rows[1:]}),
        ["2026-01", "2026-02", "2026-03"])

    html = (EX / "ordrer.html").read_text(encoding="utf-8")
    flat = re.sub(r"[ \u00a0]", "", html)
    chk("the page carries the total", str(total) in flat)
    chk("the page carries the row count", '"rows":27' in flat or "27 rader" in html)
    chk("the page names its source", "ordrer.json" in html)
    chk("the page carries its provenance", "Prosjekteier" in html)

    # the guard: two lines on one order must stop the flattener, not drop revenue
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        broken = json.loads(json.dumps(payload))
        broken["records"][0]["lines"].append({"product": "Rapportør", "canal": "Web"})
        (tmp / "ordrer.json").write_text(json.dumps(broken), encoding="utf-8")
        (tmp / "flatten.py").write_text((EX / "flatten.py").read_text(encoding="utf-8"),
                                        encoding="utf-8")
        r = subprocess.run([sys.executable, str(tmp / "flatten.py")],
                           capture_output=True, text=True)
        chk("a two-line order stops the flattener", r.returncode != 0)
        chk("and it names the order", records[0]["id"] in (r.stdout + r.stderr))

    print("\n" + "-" * 60)
    print(f"PASS: {passed}  FAIL: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
