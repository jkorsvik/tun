#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write the synthetic revenue table for the rank-change example.

Twelve invented products over two invented quarters, with the four shapes a rank chart has to
survive, planted on purpose:

  * one product climbs four places and one falls five, so the movement sentence has something
    true to say;
  * one product leaves before the second quarter and one arrives in it, so the page has to draw
    a stub instead of a line that would claim a move nobody made;
  * two products hold exactly the same revenue in the first quarter, so the ranks are 1, 1, 3
    and the page has to say so;
  * one product falls one place while growing, which is the case a rank-only chart gets wrong.

Run it from the repository root:  python3 examples/46-rank-change/lag_data.py
"""
from __future__ import annotations

import pathlib

Q1, Q2 = "2026-K1", "2026-K2"

# (product, first quarter, second quarter). None means the product is not there that quarter.
# The values are chosen so that the four cases below are true of the file, not just intended:
# Vestavind climbs four places, Kystlett falls five, Dalforet falls one place while its revenue
# grows 22 per cent, Vestavind and Sorfjell Pro hold exactly the same revenue in the first
# quarter (so the ranks read 1, 1, 3 style), Sommertilbudet leaves and Hostkampanje arrives.
ROWS: list[tuple[str, int | None, int | None]] = [
    ("Fjordtjenesten", 4_820_000, 5_140_000),      # first in both, and grows
    ("Vestavind", 1_950_000, 3_450_000),           # rank 6 to rank 2: climbs four
    ("Havbruk Pluss", 3_960_000, 3_180_000),       # rank 2 to rank 3
    ("Nordlys Avtale", 3_100_000, 2_900_000),      # rank 3 to rank 4
    ("Innlandet Basis", 2_400_000, 2_500_000),     # rank 5 in both, while growing
    ("Sorfjell Pro", 1_950_000, 2_350_000),        # tied with Vestavind first, then rank 6
    ("Tinde Mini", 1_600_000, 1_900_000),          # rank 8 to rank 7
    ("Breavtale", 1_240_000, 1_750_000),           # rank 9 to rank 8
    ("Kystlett", 2_860_000, 1_700_000),            # rank 4 to rank 9: falls five
    ("Polarpakken", 620_000, 1_250_000),           # rank 11 to rank 10
    ("Dalforet", 980_000, 1_200_000),              # rank 10 to rank 11 while GROWING
    ("Sommertilbudet", 410_000, None),             # gone by the second quarter
    ("Hostkampanje", None, 900_000),               # arrives in the second quarter
]


def main() -> int:
    out = pathlib.Path(__file__).resolve().parent / "produkter.csv"
    lines = ["Produkt;Kvartal;Omsetning"]
    for product, first, second in sorted(ROWS):
        if first is not None:
            lines.append(f"{product};{Q1};{first}")
        if second is not None:
            lines.append(f"{product};{Q2};{second}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(lines) - 1} rows, {len(ROWS)} products, 2 quarters -> {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
