#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ordrer.json -> salg.csv, the four columns a dashboard needs.

This is the whole lesson of the example, so it stays short enough to read in one screen and
says out loud what it is dropping: the payload wrapper becomes the row count, `booked` is
cut to its month, and `lines` is one element per order in this data, so taking [0] is named
as an assumption rather than hidden.

Stdlib only, no arguments: run it next to the JSON it flattens.
"""
import csv
import json
import pathlib

here = pathlib.Path(__file__).resolve().parent
payload = json.loads((here / "ordrer.json").read_text(encoding="utf-8"))
rows = []
for order in payload["records"]:
    if len(order["lines"]) != 1:
        raise SystemExit(f"{order['id']}: {len(order['lines'])} lines, this script assumes one")
    rows.append({
        "Maaned": order["booked"][:7],
        "Region": order["customer"]["region"],
        "Produkt": order["lines"][0]["product"],
        "Kanal": order["lines"][0]["canal"],
        "Belop": order["amountNok"],
    })

with (here / "salg.csv").open("w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(f"salg.csv: {len(rows)} rows from {payload['total']} records, "
      f"{sum(r['Belop'] for r in rows)} NOK")
