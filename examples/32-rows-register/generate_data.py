#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate the synthetic register: 1,200 deviation cases, no real data anywhere.

Seeded, so a rebuild is the same bytes. The shape is the one a register actually gets:
an id nobody searches for, three short labels, a date, a status, and two numbers — one of
which is sometimes empty, because "no amount" is a real value and the page has to sort it
last rather than as zero.
"""
import csv
import pathlib
import random

HERE = pathlib.Path(__file__).resolve().parent
UNITS = ["Kundeservice", "Fag", "IT", "HR", "Okonomi", "Innkjop", "Salg", "Drift"]
CATS = ["Manglende kvittering", "Feil belop", "Duplikat", "Ugyldig konto",
        "Manglende godkjenning", "Feil periode", "Ufullstendig bilag", "Avvikende mva"]
STATUS = ["Apent", "Under behandling", "Lukket", "Venter pa svar"]


def main() -> int:
    random.seed(20261025)
    out = HERE / "avvik.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Saksnummer", "Enhet", "Avvik", "Mottatt", "Status", "Dager",
                         "Belop", "Saksbehandler"])
        for n in range(1, 1201):
            month = random.choice(["01", "02", "03", "04", "05", "06", "07", "08", "09"])
            day = random.randint(10, 28)
            status = random.choices(STATUS, weights=[3, 3, 5, 1])[0]
            dager = random.randint(1, 120) if status != "Lukket" else random.randint(1, 40)
            belop = "" if random.randint(0, 1) else f"{random.randint(120, 98000)}"
            writer.writerow([f"AV-2026{month}{day:02d}-{n:04d}", random.choice(UNITS),
                             random.choice(CATS), f"2026-{month}-{day:02d}", status, dager,
                             belop, f"Saksbehandler {random.randint(1, 9)}"])
    print(f"wrote {out} ({out.stat().st_size} bytes, 1200 rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
