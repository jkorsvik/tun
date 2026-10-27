#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write survey.csv: synthetic answers for the survey-board example.

Deterministic: no random seed, no clock. The shares move with the unit on purpose,
so filtering the board changes the picture; one unit answers one question only
twice, so the suppression rule has something to hide.
"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "survey.csv"

QUESTIONS = [
    "Jeg får svar på det jeg spør om",
    "Verktøyene jeg bruker passer til oppgaven",
    "Jeg vet hvem som bestemmer i saken",
    "Overgangen mellom enheter er smidig",
    "Jeg bruker under en time på å finne tallene",
]
SCALE = ["1 Helt uenig", "2 Uenig", "3 Verken", "4 Enig", "5 Helt enig"]
UNITS = ["Bemanning", "Innhold", "Teknisk", "Erfaring"]
ROLES = ["Leder", "Fag", "Stotte"]
# How many answers per unit and question; Extrakey makes the small cell.
PLAN = {
    ("Bemanning", "Leder"): 4, ("Bemanning", "Fag"): 6, ("Bemanning", "Stotte"): 3,
    ("Innhold", "Leder"): 5, ("Innhold", "Fag"): 9, ("Innhold", "Stotte"): 4,
    ("Teknisk", "Leder"): 3, ("Teknisk", "Fag"): 8, ("Teknisk", "Stotte"): 5,
    ("Erfaring", "Leder"): 2, ("Erfaring", "Fag"): 7, ("Erfaring", "Stotte"): 4,
}
# A different centre of gravity per unit, so a filter moves the numbers.
LEAN = {"Bemanning": 1, "Innhold": 0, "Teknisk": 2, "Erfaring": 1}


def main() -> int:
    rows = []
    for qi, question in enumerate(QUESTIONS):
        for unit in UNITS:
            for role in ROLES:
                count = PLAN[(unit, role)]
                if unit == "Erfaring" and qi == 4:
                    count = min(count, 2)      # a cell the board must hide
                for i in range(count):
                    pick = (LEAN[unit] + qi + i + (1 if role == "Leder" else 0)) % len(SCALE)
                    rows.append([unit, role, question, SCALE[pick]])
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        fh.write("Enhet,Rolle,Sporsmal,Svar\n")
        for r in rows:
            fh.write(",".join(r) + "\n")
    print(f"wrote {OUT} ({len(rows)} answers, synthetic)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
