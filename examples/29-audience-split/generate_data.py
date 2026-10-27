#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write the two extracts this example ships: one per audience.

Deterministic: no random seed, no clock. The point of the example is not the numbers
but the boundary between the two files, so the numbers are small enough to check by
hand and the split is visible in the row counts.

Run it, then build both dashboards with the commands in README.md.
"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ALL = HERE / "salg-alle.csv"
NORD = HERE / "salg-team-nord.csv"

HEADER = "Selger,Team,Produkt,Maaned,Belop"

# Team Nord is the audience that gets its own file; the other two teams must never
# appear in it. Names are made up and carry the team they belong to, so a leak is
# readable in a grep rather than something you have to reason about.
ROWS = [
    ("Kari Nordmann", "Nord", "Bolig", "2026-01", 412000),
    ("Kari Nordmann", "Nord", "Bolig", "2026-02", 388000),
    ("Kari Nordmann", "Nord", "Fritid", "2026-01", 152000),
    ("Kari Nordmann", "Nord", "Fritid", "2026-02", 161000),
    ("Ola Hansen", "Nord", "Bolig", "2026-01", 296000),
    ("Ola Hansen", "Nord", "Bolig", "2026-02", 305000),
    ("Ola Hansen", "Nord", "Fritid", "2026-01", 98000),
    ("Ola Hansen", "Nord", "Fritid", "2026-02", 104000),
    ("Ingrid Solberg", "Vest", "Bolig", "2026-01", 501000),
    ("Ingrid Solberg", "Vest", "Bolig", "2026-02", 477000),
    ("Ingrid Solberg", "Vest", "Fritid", "2026-01", 143000),
    ("Ingrid Solberg", "Vest", "Fritid", "2026-02", 138000),
    ("Petter Aas", "Vest", "Bolig", "2026-01", 268000),
    ("Petter Aas", "Vest", "Bolig", "2026-02", 274000),
    ("Petter Aas", "Vest", "Fritid", "2026-01", 87000),
    ("Petter Aas", "Vest", "Fritid", "2026-02", 92000),
    ("Mari Linde", "Sør", "Bolig", "2026-01", 355000),
    ("Mari Linde", "Sør", "Bolig", "2026-02", 362000),
    ("Mari Linde", "Sør", "Fritid", "2026-01", 121000),
    ("Mari Linde", "Sør", "Fritid", "2026-02", 118000),
    ("Jon Berg", "Sør", "Bolig", "2026-01", 233000),
    ("Jon Berg", "Sør", "Bolig", "2026-02", 241000),
    ("Jon Berg", "Sør", "Fritid", "2026-01", 76000),
    ("Jon Berg", "Sør", "Fritid", "2026-02", 81000),
]

AUDIENCE = "Nord"


def write(path: pathlib.Path, rows: list[tuple]) -> int:
    lines = [HEADER] + [",".join(str(c) for c in r) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(rows)


def main() -> None:
    narrow = [r for r in ROWS if r[1] == AUDIENCE]
    n_all = write(ALL, ROWS)
    n_narrow = write(NORD, narrow)
    total_all = sum(r[4] for r in ROWS)
    total_narrow = sum(r[4] for r in narrow)
    print(f"wrote {ALL.name}: {n_all} rows, {total_all} kr")
    print(f"wrote {NORD.name}: {n_narrow} rows, {total_narrow} kr")
    print(f"the narrow file holds {n_narrow / n_all:.0%} of the rows and "
          f"{total_narrow / total_all:.0%} of the total")
    outside = {r[0] for r in ROWS if r[1] != AUDIENCE}
    print(f"names that must not appear in {NORD.name}: {', '.join(sorted(outside))}")


if __name__ == "__main__":
    main()
