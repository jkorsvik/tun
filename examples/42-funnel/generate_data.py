#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write the synthetic application extract behind example 42: one row per record per stage.

Deterministic on purpose, so the committed `soknader.csv` is this script's output. Each record
writes one row for every stage it reached, which is what makes the funnel nested: reaching
Innstilt means the same record was written at Mottatt and Vurdert too. A record's furthest
stage comes from a hash of its own id, so no seed and no random module is involved and the file
is identical on any machine.

    python3 examples/42-funnel/generate_data.py
"""
from __future__ import annotations

import csv
import hashlib
import pathlib

OUT = pathlib.Path(__file__).resolve().parent / "soknader.csv"
HEADER = ["Soknadsnr", "Status"]
STAGES = ["Mottatt", "Vurdert", "Innstilt", "Utbetalt"]
RECORDS = 400
# Where the cohort thins out: this share of the records that reach a stage goes on to the
# next. Cumulative: Mottatt 400, Vurdert ~330, Innstilt ~277, Utbetalt ~217.
KEEP = {"Mottatt": 1.00, "Vurdert": 0.83, "Innstilt": 0.69, "Utbetalt": 0.54}


def draw_of(record: str) -> float:
    """A number in [0, 1) that depends only on the record's own id."""
    digest = hashlib.sha256(record.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def main() -> int:
    rows: list[list] = []
    reached = {stage: 0 for stage in STAGES}
    for i in range(1, RECORDS + 1):
        record = f"S-{i:04d}"
        draw = draw_of(record)
        for stage in STAGES:
            if draw >= KEEP[stage]:
                break                      # this record stopped before this stage
            rows.append([record, stage])
            reached[stage] += 1
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)
    print(f"wrote {OUT.name}: {len(rows)} rows, {RECORDS} records")
    for stage, n in reached.items():
        print(f"  {stage:<10} {n:>4}  {n / RECORDS * 100:5.1f} %")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
