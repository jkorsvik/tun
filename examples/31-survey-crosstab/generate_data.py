#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write survey-wide.csv: synthetic answers for the cross-tab example.

One row per respondent, one column per question. That shape is the whole point: a
cross-tab needs two answers known to come from the same person, and only the row
boundary says so.

Deterministic: no random seed, no clock. The pair Q1 x Q2 is written out as a matrix
rather than computed, so the file states the thing the rule is about: every
combination holds at least five answers, and the table is therefore printable. Q4 is
answered by nine people only, so Q3 x Q4 has cells under five and that table is
dropped instead of printed.
"""
import csv
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "survey-wide.csv"

SCALE = ["1 Helt uenig", "2 Uenig", "3 Verken", "4 Enig", "5 Helt enig"]
Q1 = "Jeg får svar på det jeg spør om"
Q2 = "Verktøyene jeg bruker passer til oppgaven"
Q3 = "Jeg vet hvem som bestemmer i saken"
Q4 = "Jeg har fått opplæring i verktøyene"
QUESTIONS = [Q1, Q2, Q3, Q4]
UNITS = ["Bemanning", "Innhold", "Teknisk", "Erfaring"]
ROLES = ["Leder", "Fag", "Stotte"]

# Rows are Q1 answers, columns are Q2 answers. Every cell is five or more, on purpose.
MATRIX = [
    [14, 12, 11, 10, 9],
    [12, 15, 13, 11, 9],
    [11, 13, 16, 12, 10],
    [10, 11, 12, 15, 11],
    [9, 9, 10, 11, 12],
]
Q4_ANSWERED_BY = 9          # a pair with cells under five, so one table must be dropped


def main() -> int:
    rows = []
    for a, line in enumerate(MATRIX):
        for b, count in enumerate(line):
            for _ in range(count):
                i = len(rows)
                answers = {Q1: SCALE[a], Q2: SCALE[b], Q3: SCALE[(i * 3) % 5]}
                if len(rows) < Q4_ANSWERED_BY:
                    answers[Q4] = SCALE[(i * 2) % 5]
                rows.append([UNITS[i % len(UNITS)], ROLES[(i // len(UNITS)) % len(ROLES)]]
                            + [answers.get(q, "") for q in QUESTIONS])
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Enhet", "Rolle"] + QUESTIONS)
        writer.writerows(rows)
    total = sum(sum(line) for line in MATRIX)
    assert total == len(rows), (total, len(rows))
    print(f"wrote {OUT.name} ({len(rows)} respondents, {Q4_ANSWERED_BY} answered Q4), synthetic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
