#!/usr/bin/env python3
"""Write the synthetic queue data for the small-multiples example.

Nine made-up service units, ten weeks, one number per unit per week: how many cases sat in
that unit's queue at the end of the week. Invented, seeded, and deliberately uneven:

  * one unit runs several times higher than the rest, so a page with per-panel axes would
    hide its size completely and every panel would look the same;
  * one unit is flat, one climbs steadily, one falls, one swings;
  * two unit-weeks are absent on purpose, so the reader can see a break in a line that is not
    a zero;
  * one unit has only six of the ten weeks, so its column of "periods" is visibly short.

Run it from the repository root:  python3 examples/45-smallmultiples/lag_data.py
"""
from __future__ import annotations

import pathlib
import random

WEEKS = [f"2026-W{w:02d}" for w in range(24, 34)]
UNITS = [
    "Enhet Nord", "Enhet Sor", "Enhet Ost", "Enhet Vest", "Enhet Midt",
    "Enhet Fjell", "Enhet Kyst", "Enhet Innafor", "Enhet Utkant",
]


def wave(base: float, swing: float, i: int, phase: float) -> int:
    import math
    return max(0, round(base + swing * math.sin(i / 1.7 + phase)))


def build(rng: random.Random) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for index, unit in enumerate(UNITS):
        for week_index, week in enumerate(WEEKS):
            if index == 0:                      # several times above the rest
                value = wave(152, 20, week_index, 0.4)
            elif index == 1:                    # climbs
                value = 30 + 6 * week_index + rng.randint(-2, 2)
            elif index == 2:                    # falls
                value = 88 - 5 * week_index + rng.randint(-2, 2)
            elif index == 3:                    # swings, period longer than a month
                value = wave(46, 26, week_index, 1.1)
            elif index == 4:                    # flat
                value = 24 + rng.randint(-1, 1)
            elif index == 5:                    # short series: only six of the ten weeks
                if week_index < 4:
                    continue
                value = 12 + week_index + rng.randint(-1, 1)
            elif index == 6:                    # a hole in the middle, on purpose
                if week_index in (3, 4):
                    continue
                value = wave(58, 12, week_index, 2.2)
            elif index == 7:
                value = 15 + week_index * 2
            else:
                value = 70 - week_index * 3
            rows.append((unit, week, str(max(0, value))))
    return rows


def main() -> int:
    rng = random.Random(45)
    rows = build(rng)
    out = pathlib.Path(__file__).resolve().parent / "ko.csv"
    lines = ["Enhet;Uke;Saker"] + [";".join(row) for row in rows]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} rows, {len(UNITS)} units, {len(WEEKS)} weeks -> {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
