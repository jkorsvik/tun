#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Writes the file you get from an API, and nothing else.

The shape is what a JSON endpoint actually returns: a wrapper object, a page of records,
numbers as numbers, a date as a string, and one field that is a list. Copying that into a
spreadsheet loses the nesting; the point of the example is that the gap between "what the
API sent" and "what the builder reads" is a fifteen-line flattener, not a rewrite.

The numbers are synthetic and deterministic: re-running this file gives the same bytes.
"""
import json
import pathlib

REGIONS = [("Nord", 1.0), ("Vest", 0.72), ("Sør", 0.55)]
PRODUCTS = ["Analysator", "Rapportør", "Vaktmester"]
CANALS = ["Web", "Partner"]


def main() -> None:
    orders = []
    n = 0
    for month in (1, 2, 3):
        for region, factor in REGIONS:
            for product in PRODUCTS:
                n += 1
                amount = int((120_000 + 37_000 * n % 90_000) * factor)
                orders.append({
                    "id": f"ORD-{1000 + n}",
                    "booked": f"2026-{month:02d}-{(n * 7) % 27 + 1:02d}",
                    "customer": {"region": region, "segment": "Bedrift" if n % 3 else "Offentlig"},
                    "lines": [{"product": product, "canal": CANALS[n % 2]}],
                    "amountNok": amount,
                    "currency": "NOK",
                })
    payload = {"page": 1, "pageSize": 27, "total": len(orders), "records": orders}
    pathlib.Path(__file__).with_name("ordrer.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ordrer.json: {len(orders)} records, {sum(o['amountNok'] for o in orders)} NOK")


if __name__ == "__main__":
    main()
