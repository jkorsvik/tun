#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write the timeline example's source rows. Deterministic, stdlib only.

Invented milestones for an invented programme, on purpose: the example is about the drawing,
and a real plan would carry a real owner's name and dates that go stale in a week.

What the rows are chosen to exercise:

  * **overlaps**, including three things running at once, because that is the question a
    timeline answers and a date column does not
  * **a one-day row**, so the smallest bar is provably visible rather than a hairline
  * **rows that start before and end after another group's rows**, so the axis is shared
  * **a group with one row**, so a group band is not assumed to hold a crowd

Run: python3 examples/35-timeline/generate_data.py
"""
from __future__ import annotations

import pathlib

HERE = pathlib.Path(__file__).parent

# Task, Start, End, Group, Owner, Status
ROWS = [
    ("Behovsavklaring", "2026-08-17", "2026-09-04", "Utredning", "Forretning", "Ferdig"),
    ("Datakartlegging", "2026-08-24", "2026-09-18", "Utredning", "Data", "Ferdig"),
    ("Arkitekturvalg", "2026-09-07", "2026-09-25", "Utredning", "Arkitektur", "Ferdig"),
    ("Risikovurdering", "2026-09-21", "2026-10-02", "Utredning", "Risiko", "Pagaende"),
    ("Datamodell", "2026-09-28", "2026-10-23", "Bygg", "Data", "Pagaende"),
    ("Innlesning", "2026-10-05", "2026-11-13", "Bygg", "Data", "Pagaende"),
    ("Tjenestelag", "2026-10-12", "2026-11-27", "Bygg", "Utvikling", "Pagaende"),
    ("Tilgangsstyring", "2026-11-02", "2026-11-20", "Bygg", "Sikkerhet", "Planlagt"),
    ("Presentasjonslag", "2026-11-16", "2026-12-18", "Bygg", "Utvikling", "Planlagt"),
    ("Test: ytelse", "2026-12-07", "2026-12-11", "Utproving", "Test", "Planlagt"),
    ("Test: sikkerhet", "2026-12-14", "2026-12-18", "Utproving", "Sikkerhet", "Planlagt"),
    ("Godkjenning", "2027-01-11", "2027-01-15", "Utproving", "Forretning", "Planlagt"),
    ("Overlevering", "2027-01-25", "2027-01-29", "Utproving", "Programmet", "Planlagt"),
]
HEADER = "Task,Start,End,Group,Owner,Status"


def main() -> int:
    lines = [HEADER] + [",".join(row) for row in ROWS]
    out = HERE / "milepaeler.csv"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(ROWS)} rows, "
          f"{len({r[3] for r in ROWS})} groups, "
          f"{min(r[1] for r in ROWS)} to {max(r[2] for r in ROWS)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
