#!/usr/bin/env python3
"""Write the synthetic plan the Gantt example is built from.

Twelve tasks of a made-up programme: a planned start and finish for each, and what actually
happened. Four finished on time or early, four finished late, two are still running, and two
have not started. That mix is the point of the example: a plan where everything went to
schedule proves nothing about the shape.

A fixed hand-written plan, not a generator: a plan is a document, and an example that changes
between runs cannot be checked against its own committed output.
"""
from __future__ import annotations

import csv
import datetime as dt
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

# task, planned start, planned finish, actual start, actual finish ("" while open)
PLAN = [
    ("Behovsavklaring", "2026-06-01", "2026-06-12", "2026-06-01", "2026-06-11"),
    ("Datakartlegging", "2026-06-08", "2026-06-26", "2026-06-09", "2026-07-03"),
    ("Løsningsskisse", "2026-06-22", "2026-07-10", "2026-07-06", "2026-07-21"),
    ("Sikkerhetsvurdering", "2026-07-06", "2026-07-24", "2026-07-08", "2026-07-24"),
    ("Prototyp", "2026-07-20", "2026-08-21", "2026-07-27", "2026-09-04"),
    ("Brukertest runde 1", "2026-08-24", "2026-09-04", "2026-09-07", "2026-09-11"),
    ("Datamodell", "2026-08-17", "2026-09-11", "2026-08-18", "2026-09-09"),
    ("Integrasjon", "2026-09-07", "2026-10-02", "2026-09-14", "2026-10-16"),
    ("Brukertest runde 2", "2026-10-05", "2026-10-16", "2026-10-19", ""),
    ("Opplæring", "2026-10-19", "2026-10-30", "2026-10-26", ""),
    ("Produksjonssetting", "2026-11-02", "2026-11-06", "", ""),
    ("Overlevering", "2026-11-09", "2026-11-13", "", ""),
]


def main() -> int:
    out = HERE / "fremdrift.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["Tiltak", "Planstart", "Planferdig", "Faktisk-start",
                         "Faktisk-ferdig"])
        writer.writerows(PLAN)
    finished = sum(1 for row in PLAN if row[4])
    print(f"wrote {out} ({len(PLAN)} tasks, {finished} finished)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
