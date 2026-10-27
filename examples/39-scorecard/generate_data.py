#!/usr/bin/env python3
"""The example's source data, generated rather than typed, so it can be regenerated.

    python3 examples/39-scorecard/generate_data.py

Writes `manedstall.csv` next to this file: one row per measure per period, with the target
and the direction the measure is judged in.

Two things are deliberate:

* **the measures move in different directions.** Digital share climbs, handling time drifts
  up, the number of complaints jumps one month and comes back. A scorecard where everything
  improves is a demo, not an example: the page has to hold a red line beside a green one.
* **one series has a hole.** `Antall klager` has no figure for July, because a real extract
  does sometimes miss a month and the page must show a break rather than draw a line through
  it.

The seed is fixed, so the file is reproducible byte for byte.

Stdlib only, like everything else in tools/.
"""
from __future__ import annotations

import csv
import pathlib
import random

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "manedstall.csv"
FIELDS = ("KPI", "Periode", "Verdi", "Mal", "Retning", "Enhet")

# Thirteen periods, not twelve: the latest one then has the same month a year earlier in
# the file, which is the comparison a scorecard is read for.
PERIODS = [f"{year}-{month:02d}"
           for year, month in [(2025, m) for m in range(10, 13)] +
                              [(2026, m) for m in range(1, 11)]]

# name, unit, direction, target, first value, monthly drift, noise, decimals, missing periods
MEASURES = (
    ("Kundetilfredshet", "poeng", "opp", 78.0, 74.0, 0.45, 0.9, 0, ()),
    ("Saksbehandlingstid", "dager", "ned", 5.0, 4.2, 0.14, 0.30, 1, ()),
    ("Svartid telefoni", "sekund", "ned", 40.0, 34.0, 1.35, 4.0, 0, ()),
    ("Digital andel", "prosent", "opp", 80.0, 67.0, 1.25, 1.0, 0, ()),
    ("Avvik lukket innen frist", "prosent", "opp", 95.0, 91.0, 0.15, 3.2, 0, ()),
    ("Sykefravær", "prosent", "ned", 4.5, 4.6, 0.03, 0.45, 1, ()),
    ("Antall klager", "antall", "ned", 120.0, 104.0, 0.6, 22.0, 0, ("2026-07",)),
)


def main() -> int:
    rng = random.Random(39)
    rows = []
    for name, unit, direction, target, first, drift, noise, decimals, missing in MEASURES:
        for index, period in enumerate(PERIODS):
            # A level per period, not an accumulating walk: a random walk over a year drifts
            # far enough to make the figures implausible, and a demo whose numbers are silly
            # teaches the reader to distrust the page.
            value = first + drift * index + rng.gauss(0, noise)
            if period in missing:
                continue
            rows.append({"KPI": name, "Periode": period,
                         "Verdi": f"{value:.{decimals}f}".replace(".", ","),
                         "Mal": f"{target:.{decimals}f}".replace(".", ","),
                         "Retning": direction, "Enhet": unit})
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUT} ({len(rows)} rows, {len(MEASURES)} measures, {len(PERIODS)} periods)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
