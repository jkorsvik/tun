#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
generate_data.py — the synthetic source for the one-pager example.

    python3 examples/37-printable-onepager/generate_data.py

Seeded, stdlib only, and written to `salgsdata.csv` beside this file. Nothing here is real:
the product names are the generic ones the other examples use, and the figures are a seeded
walk with one deliberate jump so that "what moved" on the sheet has something true to say.
"""
from __future__ import annotations

import csv
import pathlib
import random

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "salgsdata.csv"

PRODUCTS = {
    # name: (base per month, monthly drift, the month the jump happens, jump factor)
    "Boliglån": (1_240_000, 1.03, None, 1.0),
    "Sparekonto": (980_000, 1.01, None, 1.0),
    "Kredittkort": (760_000, 0.99, None, 1.0),
    "Fondssparing": (540_000, 1.02, "2026-09", 1.34),
    "Bedriftskonto": (410_000, 1.00, None, 1.0),
    "Forsikring": (320_000, 1.01, "2026-09", 0.72),
}
MONTHS = [f"2026-{m:02d}" for m in range(1, 10)]


def main() -> int:
    rng = random.Random(20261024)
    rows = []
    for month_index, month in enumerate(MONTHS):
        for name, (base, drift, jump_month, factor) in PRODUCTS.items():
            value = base * (drift ** month_index)
            if month == jump_month:
                value *= factor
            value *= rng.uniform(0.97, 1.03)
            rows.append({
                "Maaned": month,
                "Produkt": name,
                "Antall": int(value / 12_500),
                "Belop": round(value),
            })
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["Maaned", "Produkt", "Antall", "Belop"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUT} ({len(rows)} rows, {len(MONTHS)} months, {len(PRODUCTS)} products)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
