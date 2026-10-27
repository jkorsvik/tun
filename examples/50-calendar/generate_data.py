#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write the synthetic day-by-day extract the calendar example is built from.

Three hundred and sixty-five days of one made-up year: a weekday rhythm (busier Tuesday to
Thursday), a quiet weekend, a summer lull, two single-day peaks, twelve missing days and a
handful of days that recorded exactly zero. That mix is the point of the example: the missing
days and the zeros have to look different, and a flat series would prove nothing.

A fixed arithmetic sequence, not `random`: an example that changes between runs cannot be
checked against its own committed output.
"""
from __future__ import annotations

import csv
import datetime as dt
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
YEAR = 2026
# Days that carry no row at all: a measurement nobody took is not a zero.
MISSING = {(1, 3), (1, 4), (2, 17), (4, 6), (5, 1), (6, 22), (7, 13), (8, 14), (9, 5),
           (10, 12), (11, 2), (12, 24)}
# Days that recorded exactly zero: a real measurement.
ZERO = {(1, 10), (3, 21), (8, 2), (11, 21), (12, 31)}
# Two single-day peaks, so the ten-highest table has something to find.
PEAK = {(3, 11): 96, (9, 24): 88}


def main() -> int:
    out = HERE / "hendelser.csv"
    rows = []
    day = dt.date(YEAR, 1, 1)
    index = 0
    while day.year == YEAR:
        key = (day.month, day.day)
        index += 1
        if key not in MISSING:
            weekday = day.weekday()
            base = 18 + 6 * (0 if weekday <= 3 else 1 if weekday == 4 else -1)
            if day.month in (7,):                      # a summer lull
                base -= 8
            wobble = (index * 37) % 11 - 5             # deterministic, between -5 and 5
            value = max(0, base + wobble)
            if day.weekday() >= 5:
                value = max(0, value - 10)
            if key in PEAK:
                value = PEAK[key]
            if key in ZERO:
                value = 0
            rows.append((day.isoformat(), value))
        day += dt.timedelta(days=1)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["Dato", "Antall"])
        writer.writerows(rows)
    print(f"wrote {out} ({len(rows)} days, {len(MISSING)} missing, {len(ZERO)} zero)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
