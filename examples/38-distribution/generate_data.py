#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The example's source data, generated rather than typed, so it can be regenerated.

    python3 examples/38-distribution/generate_data.py

Writes `saksbehandlingstid.csv` next to this file: one row per case, with the unit that
handled it and the number of days it took.

The shape is the point of the example. Real case-handling times are not symmetric: most
cases finish quickly, a few take a very long time, and the mean sits well above the median
because of those few. That is what makes a total or an average the wrong summary, so the
generator draws from a lognormal rather than a bell curve. A bell curve would have made the
example's own argument invisible.

The seed is fixed, so the file is reproducible byte for byte and a diff means the generator
changed, not the weather.

Stdlib only, like everything else in tools/.
"""
from __future__ import annotations

import csv
import math
import pathlib
import random

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "saksbehandlingstid.csv"
FIELDS = ("Sak", "Enhet", "Dager")

# name -> (how many cases, median days, spread, longest allowed)
# The spread is the sigma of the log: 0.55 is a tight unit, 0.95 a unit with a real tail.
UNITS = (
    ("Enhet nord", 180, 4.0, 0.55, 45),
    ("Enhet sør", 150, 3.0, 0.75, 30),
    ("Enhet vest", 90, 7.0, 0.95, 60),
    ("Enhet test", 3, 6.0, 0.40, 20),
)


def main() -> int:
    rng = random.Random(38)
    rows = []
    number = 0
    for name, count, median, sigma, ceiling in UNITS:
        mu = math.log(median)
        for _ in range(count):
            number += 1
            days = round(math.exp(mu + sigma * rng.gauss(0, 1)))
            days = max(1, min(ceiling, days))
            rows.append({"Sak": f"S-{number:04d}", "Enhet": name, "Dager": days})
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUT} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
