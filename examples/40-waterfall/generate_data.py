#!/usr/bin/env python3
"""Write the synthetic extract behind example 40: one product-month per row, in kroner.

Deterministic on purpose: the committed `omsetning.csv` is this script's output, so the
example can be regenerated and the numbers on the page re-derived from it. Every
product-month is split into two transaction rows, because a bridge that takes the first row
per contributor instead of the sum answers a different question, and the example should be
able to show that.

    python3 examples/40-waterfall/generate_data.py
"""
from __future__ import annotations

import csv
import pathlib

OUT = pathlib.Path(__file__).resolve().parent / "omsetning.csv"
HEADER = ["Måned", "Produkt", "Omsetning"]

# Product, September, October. None means the product has no figure in that month: it is
# sold for the first time, or it stopped. Both are real steps in a bridge.
MONTHS = {
    "September": {
        "Boliglån": 4_820_000,
        "Forsikring": 2_310_000,
        "Fond": 1_780_000,
        "Betalingskort": 1_260_000,
        "Sparekonto": 940_000,
        "Billån": 720_000,
        "Kontantkort": 155_000,
        "Gavekort": 84_000,
        "Valuta": 62_000,
    },
    "Oktober": {
        "Boliglån": 5_240_000,
        "Forsikring": 2_145_000,
        "Fond": 2_090_000,
        "Betalingskort": 1_180_000,
        "Sparekonto": 1_310_000,
        "Billån": 690_000,
        "Grønt lån": 260_000,
        "Gavekort": 79_000,
        "Valuta": 61_000,
    },
    # A third month, so the example also shows what the builder does with rows outside the
    # two periods it is asked about: they are counted and named, never silently folded in.
    "August": {
        "Boliglån": 4_610_000,
        "Forsikring": 2_280_000,
        "Fond": 1_650_000,
        "Betalingskort": 1_190_000,
        "Sparekonto": 880_000,
        "Billån": 740_000,
        "Gavekort": 91_000,
        "Valuta": 58_000,
    },
}


def split(value: int) -> list[int]:
    """One figure as two transaction rows.

    The first row is 60 per cent of the figure, so a bridge that reads one row per
    contributor instead of the sum is visibly wrong rather than plausibly wrong.
    """
    first = round(value * 0.6)
    return [first, value - first]


def main() -> int:
    rows: list[list] = []
    for month, products in MONTHS.items():
        for product, total in products.items():
            for part in split(total):
                rows.append([month, product, part])
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)
    opening = sum(MONTHS["September"].values())
    closing = sum(MONTHS["Oktober"].values())
    print(f"wrote {OUT.name}: {len(rows)} rows")
    print(f"September {opening:,} -> Oktober {closing:,} ({closing - opening:+,})"
          .replace(",", " "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
