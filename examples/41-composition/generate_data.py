#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write the synthetic staffing extract behind example 41: hours per task, per quarter.

Deterministic on purpose, so the committed `bemanning.csv` is this script's output and every
figure on the page can be re-derived from it. Each category-quarter is written as two rows,
because a composition that reads one row per category instead of the sum answers a different
question.

    python3 examples/41-composition/generate_data.py
"""
from __future__ import annotations

import csv
import pathlib

OUT = pathlib.Path(__file__).resolve().parent / "bemanning.csv"
HEADER = ["Kvartal", "Oppgave", "Timer"]

# Hours per task per quarter, for a made-up team whose workload falls over the year. The mix
# is the point: Saksbehandling loses hours (4 800 to 4 100) and takes a bigger share of the
# total anyway (40,0 % to 42,7 %), because the total falls faster. That divergence is what the
# page names in words.
HOURS = {
    "2026-Q1": {
        "Saksbehandling": 4_800,
        "Møter": 1_800,
        "Bistand": 1_500,
        "Rapportering": 1_200,
        "Systemforvaltning": 900,
        "Opplæring": 600,
        "Reisetid": 480,
        "Internkontroll": 300,
        "Kursadministrasjon": 240,
        "Diverse": 180,
    },
    "2026-Q2": {
        "Saksbehandling": 4_620,
        "Møter": 1_650,
        "Bistand": 1_320,
        "Rapportering": 1_100,
        "Systemforvaltning": 880,
        "Opplæring": 550,
        "Reisetid": 440,
        "Internkontroll": 220,
        "Kursadministrasjon": 132,
        "Diverse": 88,
    },
    "2026-Q3": {
        "Saksbehandling": 4_500,
        "Møter": 1_530,
        "Bistand": 1_224,
        "Rapportering": 918,
        "Systemforvaltning": 816,
        "Opplæring": 510,
        "Reisetid": 408,
        "Internkontroll": 153,
        "Kursadministrasjon": 82,
        "Diverse": 59,
    },
    "2026-Q4": {
        "Saksbehandling": 4_100,
        "Møter": 1_450,
        "Bistand": 1_050,
        "Rapportering": 800,
        "Systemforvaltning": 760,
        "Opplæring": 800,
        "Reisetid": 240,
        "Internkontroll": 240,
        "Kursadministrasjon": 110,
        "Diverse": 50,
    },
}


def split(value: int) -> list[int]:
    """One figure as two rows: 70 per cent and the rest, so a first-row read is visibly wrong."""
    first = round(value * 0.7)
    return [first, value - first]


def main() -> int:
    rows: list[list] = []
    for quarter, tasks in HOURS.items():
        for task, hours in tasks.items():
            for part in split(hours):
                rows.append([quarter, task, part])
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)
    print(f"wrote {OUT.name}: {len(rows)} rows")
    for quarter, tasks in HOURS.items():
        print(f"  {quarter}: {sum(tasks.values()):,} hours".replace(",", " "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
