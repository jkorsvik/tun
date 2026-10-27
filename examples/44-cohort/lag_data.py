#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate the synthetic cohort extract. Deterministic: same seed, same file.

No real data of any kind: invented account numbers and invented visit dates. The point of
the example is the shape of the grid, and a shape needs a believable drop-off rather than a
plausible customer.
"""
import pathlib
import random

random.seed(20261025)

MONTHS = ["2025-09", "2025-10", "2025-11", "2025-12",
          "2026-01", "2026-02", "2026-03", "2026-04", "2026-05"]


def days_in(month: str) -> int:
    year, mon = (int(part) for part in month.split("-"))
    table = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    return 29 if mon == 2 and leap else table[mon - 1]


rows = []
account = 10000
for start_month, started in enumerate([38, 52, 61, 44, 71, 58, 66, 49, 57]):
    month = MONTHS[start_month]
    # Each cohort is smaller than the one before it in the middle of the period: a rising
    # intake makes the grid read as growth even when every cohort behaves the same.
    for _ in range(started):
        account += 1
        day = random.randint(1, days_in(month))
        rows.append((f"K{account}", f"{month}-{day:02d}"))
        # Roughly 55 % come back in month 1, then a flatter tail.
        alive = random.random() < 0.55
        for offset in range(1, len(MONTHS) - start_month):
            if not alive:
                break
            if random.random() < (0.72 if offset < 3 else 0.86):
                later = MONTHS[start_month + offset]
                visits = 1 if random.random() < 0.8 else 2
                for _ in range(visits):
                    rows.append((f"K{account}",
                                 f"{later}-{random.randint(1, days_in(later)):02d}"))
            else:
                alive = False

random.shuffle(rows)
out = pathlib.Path(__file__).with_name("kunder.csv")
out.write_text("Kunde;Dato\n" + "\n".join(f"{a};{d}" for a, d in rows) + "\n",
               encoding="utf-8")
print(f"{len(rows)} rows, {len({a for a, _ in rows})} accounts -> {out.name}")
