#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write the two extracts this example compares. Deterministic, stdlib only.

The numbers are invented and small on purpose: the point of the example is the shape of the
answer, not the size of the CSV. Two properties are deliberate and load-bearing:

  * **a key appears more than once before the build.** `forrige.csv` has 11 rows for 6
    regions, so "summed per key" is provable rather than assumed. A builder that took the
    first row per key would print a different, plausible-looking answer.
  * **each extract has a key the other does not.** `Nordvest` stops reporting and `Sørvest`
    starts. That is what makes "new" and "gone" real rows in the artefact instead of a
    sentence in a document.

Run: python3 examples/33-comparison/generate_data.py
"""
from __future__ import annotations

import pathlib

HERE = pathlib.Path(__file__).parent

# region -> [(channel, amount)] before, then after. Summed per region by the builder.
BEFORE = {
    "Nord": [("Butikk", 412000), ("Nett", 286000)],
    "Vest": [("Butikk", 338000), ("Nett", 201000)],
    "Midt": [("Butikk", 244000), ("Nett", 143000)],
    "Sør": [("Butikk", 197000), ("Nett", 121000)],
    "Øst": [("Butikk", 512000), ("Nett", 404000)],
    "Nordvest": [("Butikk", 88000)],
}
AFTER = {
    "Nord": [("Butikk", 455000), ("Nett", 301000)],
    "Vest": [("Butikk", 329000), ("Nett", 214000)],
    "Midt": [("Butikk", 251000), ("Nett", 150000)],
    "Sør": [("Butikk", 164000), ("Nett", 109000)],
    "Øst": [("Butikk", 498000), ("Nett", 441000)],
    "Sørvest": [("Butikk", 63000)],
}


def write(path: pathlib.Path, data: dict[str, list[tuple[str, int]]]) -> None:
    lines = ["Region,Kanal,Omsetning"]
    for region, rows in data.items():
        for channel, amount in rows:
            lines.append(f"{region},{channel},{amount}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(lines) - 1} rows, {len(data)} regions)")


if __name__ == "__main__":
    write(HERE / "forrige.csv", BEFORE)
    write(HERE / "denne.csv", AFTER)
