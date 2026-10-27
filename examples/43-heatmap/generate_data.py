#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Regenerate the synthetic extract behind examples/43-heatmap.

Deterministic: the same seed gives the same file on any machine, so the committed CSV and the
committed page can be rebuilt and compared byte for byte. Every figure is invented; nothing
here comes from a real case, a real unit or a real week.

    python3 examples/43-heatmap/generate_data.py

The shape is chosen to make the page's rules visible:

  * one unit is far busier than the rest, so the scale has a real top
  * one week is quiet for one unit only, which is a cell a reader should find
  * two cells are absent from the extract entirely, so the page has to hatch them instead of
    drawing a zero there
"""
from __future__ import annotations

import pathlib
import random

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "henvendelser.csv"

UNITS = ["Agder", "Innlandet", "Nordland", "Oslo", "Trondelag", "Vestland"]
WEEKS = [f"2026-W{week:02d}" for week in range(1, 9)]
LEVEL = {"Agder": 18, "Innlandet": 24, "Nordland": 14, "Oslo": 62, "Trondelag": 30,
         "Vestland": 41}
# One week where one unit's cases are handled elsewhere, and one where a campaign lands.
QUIET = {("Oslo", "2026-W04"): 0.25}
BUSY = {("Vestland", "2026-W06"): 1.9}
# Not in the extract at all: no cases, and nobody recorded any. Two different findings.
ABSENT = {("Nordland", "2026-W02"), ("Agder", "2026-W07")}


def main() -> int:
    rng = random.Random(43)
    rows = []
    for unit in UNITS:
        for week in WEEKS:
            if (unit, week) in ABSENT:
                continue
            base = LEVEL[unit]
            drift = 1 + 0.04 * WEEKS.index(week)          # a slightly busier quarter
            factor = QUIET.get((unit, week), BUSY.get((unit, week), 1.0))
            noise = rng.uniform(0.85, 1.15)
            rows.append((unit, week, max(0, round(base * drift * factor * noise))))
    OUT.write_text("Enhet,Uke,Antall\n" + "".join(f"{u},{w},{n}\n" for u, w, n in rows),
                   encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} rows, {len(UNITS)} units x {len(WEEKS)} weeks, "
          f"{len(ABSENT)} cells absent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
