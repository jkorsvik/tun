#!/usr/bin/env python3
"""Write the synthetic enquiry-flow extract the Sankey example is built from.

Four incoming channels, two middle stages, two outcomes. Every middle node passes on exactly what
arrived, which is the property the builder checks and the picture depends on. The numbers are
hand-chosen so the balance is exact and visibly so: Svart receives 1150 and passes 1150,
Videresendt receives 570 and passes 570.

Hand-written, not generated: an example that changes between runs cannot be checked against its
own committed output.
"""
from __future__ import annotations

import csv
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

# from, to, enquiries. Svart: 620+410+120 = 1150 in, 980+170 out. Videresendt: 570 in, 570 out.
FLOWS = [
    ("Telefon", "Svart", 620),
    ("Telefon", "Videresendt", 180),
    ("Chat", "Svart", 410),
    ("Chat", "Videresendt", 60),
    ("Epost", "Videresendt", 240),
    ("Skjema", "Svart", 120),
    ("Skjema", "Videresendt", 90),
    ("Svart", "Løst", 980),
    ("Svart", "Eskalert", 170),
    ("Videresendt", "Løst", 400),
    ("Videresendt", "Eskalert", 170),
]


def main() -> int:
    out = HERE / "kanaler.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["Kanal", "Utfall", "Antall"])
        writer.writerows(FLOWS)
    total = sum(value for _s, _d, value in FLOWS[:7])
    print(f"wrote {out} ({len(FLOWS)} flows, {total} enquiries in)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
