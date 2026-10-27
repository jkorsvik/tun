#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Generate mock transaction data for the cube example.

Stdlib only, deterministic (fixed seed), so anyone can reproduce the measurements in
docs/07-portable-cube.md without access to real data.

    python3 examples/03-cube-dashboard/generate_data.py               # 4 000 000 rows
    python3 examples/03-cube-dashboard/generate_data.py --rows 100000 # quick run

Writes transaksjoner.csv next to this script. That file is gitignored — it is ~200 MB
at the default size. The point of the example is that the *dashboard* is 0.81 MB.
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import random

REGIONER = ["Oslo", "Viken", "Vestland", "Rogaland", "Trøndelag",
            "Innlandet", "Agder", "Nordland", "Troms", "Møre og Romsdal"]
KATEGORIER = ["Dagligvare", "Restaurant", "Transport", "Klær", "Elektronikk",
              "Helse", "Apotek", "Bolig", "Sport", "Kultur", "Reise", "Bensin"]
KANALER = ["Kort fysisk", "Kort nett", "Vipps", "Apple Pay", "Faktura"]
ALDER = ["18-25", "26-35", "36-45", "46-55", "56-65", "66+"]

# Per-category typical basket size (kr), so the mock data is not uniform noise.
SNITT = {"Dagligvare": 420, "Restaurant": 610, "Transport": 260, "Klær": 890,
         "Elektronikk": 2400, "Helse": 540, "Apotek": 310, "Bolig": 3100,
         "Sport": 760, "Kultur": 350, "Reise": 4200, "Bensin": 680}
# Seasonal lift by month index (1-12): December up, January down.
SESONG = [0.92, 0.90, 0.97, 1.00, 1.04, 1.02, 1.06, 1.01, 0.99, 1.03, 1.09, 1.31]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=4_000_000)
    ap.add_argument("--start", default="2024-01-01")
    ap.add_argument("--months", type=int, default=32)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rnd = random.Random(args.seed)
    start = dt.date.fromisoformat(args.start)
    days = (start.replace(year=start.year + args.months // 12,
                          month=(start.month - 1 + args.months % 12) % 12 + 1) - start).days
    out = pathlib.Path(__file__).parent / "transaksjoner.csv"

    with out.open("w", encoding="utf-8", newline="") as fh:
        fh.write("dato,region,kategori,kanal,aldersgruppe,antall,belop\n")
        for _ in range(args.rows):
            d = start + dt.timedelta(days=rnd.randrange(days))
            kat = rnd.choice(KATEGORIER)
            # weekend lift on leisure spend
            lift = SESONG[d.month - 1] * (1.18 if d.weekday() >= 5 and kat in
                                          ("Restaurant", "Kultur", "Sport", "Reise") else 1.0)
            belop = max(15.0, rnd.gauss(SNITT[kat] * lift, SNITT[kat] * 0.45))
            antall = 1 if rnd.random() < 0.82 else rnd.randrange(2, 6)
            fh.write(f"{d.isoformat()},{rnd.choice(REGIONER)},{kat},"
                     f"{rnd.choice(KANALER)},{rnd.choice(ALDER)},{antall},{belop:.2f}\n")

    mb = out.stat().st_size / 1e6
    print(f"{out.name}: {args.rows:,} rows, {mb:.0f} MB")
    print("\nnow build the dashboard:\n"
          "  python3 tools/build_cube_dashboard.py \\\n"
          f"      --data {out} \\\n"
          "      --dims region,kategori,kanal,aldersgruppe \\\n"
          "      --time dato --time-grain month \\\n"
          '      --measures "belop:sum:kr,antall:sum" \\\n'
          '      --title "Transaksjonsoversikt 2024–2026" \\\n'
          '      --requested-by "Prosjekteier" \\\n'
          "      --out examples/03-cube-dashboard/transaksjoner.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
