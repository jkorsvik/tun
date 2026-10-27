#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate the synthetic sick-leave data for example 26.

    python3 examples/26-kpi-board/generate_data.py

Writes `sykefravaer.csv` next to this file: 8 units, 18 months, a headcount and
a count of sick-leave days. Stdlib only and seeded, so the file is reproducible
to the byte and the example's numbers do not move between runs.

Why this data and not sales: a rate is the case the dashboard builder's
`--measure-kind rate` exists for, and the awkward one to get right. Sick-leave
days add up across months and units (which is what makes them chartable), but
dividing the total by the row count would produce "average days per row", a
number with no meaning. That is exactly the trap the flag removes, so the
example can show the difference instead of describing it.

The numbers are invented. Every unit name is generic on purpose: no real
organisasjon, no real person, and nothing that could be mistaken for a real
reporting line.
"""
from __future__ import annotations

import csv
import pathlib
import random

OUT = pathlib.Path(__file__).with_name("sykefravaer.csv")

UNITS = [
    ("Enhet nord", "Kundeservice"),
    ("Enhet sor", "Kundeservice"),
    ("Enhet ost", "Kundeservice"),
    ("Enhet vest", "Kundeservice"),
    ("Skade nord", "Skade"),
    ("Skade sor", "Skade"),
    ("Verksted", "Bil"),
    ("Stab", "Stab"),
]

MONTHS = [f"{year}-{month:02d}" for year in (2025, 2026) for month in range(1, 13)][:18]


def main() -> int:
    rng = random.Random(26)  # the example number, so the data is stable
    rows = []
    for unit, section in UNITS:
        # Each unit has its own level and its own drift, so the chart has shape
        # rather than noise: the point of the example is the flag, not the data.
        headcount = rng.choice([18, 24, 31, 42, 55])
        level = rng.uniform(1.2, 2.8)
        for i, month in enumerate(MONTHS):
            seasonal = 0.55 if month.endswith(("01", "02", "11")) else 0.0
            days = max(0.0, headcount * (level + seasonal + rng.uniform(-0.35, 0.35)))
            rows.append({
                "Enhet": unit,
                "Seksjon": section,
                "Maaned": month,
                "Ansatte": headcount,
                "Sykefravaersdager": round(days, 1),
            })

    with OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    total = sum(row["Sykefravaersdager"] for row in rows)
    print(f"wrote {OUT.name}: {len(rows)} rows, {total:,.1f} sick-leave days")
    print("  synthetic: seeded, stdlib only, no real unit or person")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
