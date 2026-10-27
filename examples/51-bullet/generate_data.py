#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write the synthetic coverage extract the bullet chart example is built from.

Fourteen units, each with a coverage percentage and the target it was given. Six sit behind
their target, one sits exactly on it, and seven are ahead, so the picture has all three cases
in it. The targets differ per unit on purpose: a shared target would make the picture a bar
chart with a single line across it, which is the shape this one exists to avoid.

Hand-written, not generated: an example that changes between runs cannot be checked against
its own committed output.
"""
from __future__ import annotations

import csv
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

# unit, coverage in percent, target in percent
ROWS = [
    ("Nord", 92.4, 90.0),
    ("Midt", 88.1, 90.0),
    ("Vest", 95.0, 92.0),
    ("Sør", 79.6, 88.0),
    ("Øst", 97.2, 95.0),
    ("Innlandet", 84.3, 90.0),
    ("Trøndelag", 90.0, 90.0),
    ("Nordvest", 71.8, 85.0),
    ("Sørvest", 93.5, 91.0),
    ("Aust", 86.7, 88.0),
    ("Fjell", 82.2, 86.0),
    ("Kyst", 98.1, 94.0),
    ("Dal", 89.4, 89.0),
    ("Vidde", 76.5, 84.0),
]


def main() -> int:
    out = HERE / "dekning.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["Enhet", "Dekning", "Maal"])
        writer.writerows(ROWS)
    behind = sum(1 for _unit, value, target in ROWS if value < target)
    print(f"wrote {out} ({len(ROWS)} units, {behind} behind target)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
