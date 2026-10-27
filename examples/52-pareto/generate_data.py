#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write the synthetic enquiry extract the Pareto example is built from.

Twenty-two categories of enquiry, of which the first five carry most of the volume and the last
seventeen are a long tail of one-off reasons. That shape is the point of the example: a flat
distribution would make a Pareto look like a bar chart, and the fold only earns its place when
there really is a tail.

Hand-written counts, not a generator: an example that changes between runs cannot be checked
against its own committed output.
"""
from __future__ import annotations

import csv
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

# reason, enquiries in the period. The tail is deliberately many-and-small.
ROWS = [
    ("Fakturafeil", 412),
    ("Glemt passord", 388),
    ("Endre adresse", 265),
    ("Leveringsstatus", 241),
    ("Feil i app", 196),
    ("Bestille nytt kort", 118),
    ("Avtale om betaling", 96),
    ("Sperre kort", 74),
    ("Feil beløp", 61),
    ("Dobbeltbetaling", 47),
    ("Endre navn", 33),
    ("Eldre sak gjenåpnet", 28),
    ("Mangler kvittering", 22),
    ("Feil konto", 18),
    ("Kansellere avtale", 14),
    ("Bestille kontoutskrift", 11),
    ("Flytte abonnement", 9),
    ("Feil i nettbank", 7),
    ("Endre e-post", 5),
    ("Purring", 4),
    ("Klage på ventetid", 3),
    ("Annet", 2),
]


def main() -> int:
    out = HERE / "henvendelser.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["Arsak", "Antall"])
        writer.writerows(ROWS)
    total = sum(count for _label, count in ROWS)
    print(f"wrote {out} ({len(ROWS)} reasons, {total} enquiries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
