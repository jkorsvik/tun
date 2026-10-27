#!/usr/bin/env python3
"""Write the synthetic extract the box plot example is built from.

One row per case: which unit handled it and how many days it took. Eight units, deliberately
different in level and in spread, and one of them with a tail of slow cases, because the tail
is what a box plot is for and a table of averages cannot show it.

A fixed pseudo-random sequence, not `random`: an example that changes between runs cannot be
checked against its own committed output.
"""
from __future__ import annotations

import pathlib

HERE = pathlib.Path(__file__).resolve().parent

# unit -> (how many cases, the typical number of days, the spread, how many slow ones)
UNITS = {
    "Nord": (46, 9, 2.1, 3),
    "Midt": (38, 12, 3.4, 2),
    "Vest": (52, 11, 2.6, 5),
    "Sør": (41, 14, 4.2, 3),
    "Øst": (58, 8, 1.8, 1),
    "Innlandet": (33, 16, 5.1, 4),
    "Trøndelag": (44, 10, 2.9, 2),
    "Nordvest": (29, 19, 6.3, 3),
}


def sequence(seed: int):
    """A small deterministic generator: same output on every machine, no imports."""
    state = seed

    def nxt() -> float:
        nonlocal state
        state = (1103515245 * state + 12345) % (2 ** 31)
        return state / (2 ** 31)

    return nxt


def main() -> int:
    out = HERE / "saksbehandlingstid.csv"
    lines = ["Enhet;Dager"]
    total = 0
    for index, (unit, (count, typical, spread, slow)) in enumerate(sorted(UNITS.items())):
        nxt = sequence(1000 + index)
        for i in range(count):
            # a value between 1 and about typical + 2 spread, in whole days
            raw = typical + (nxt() - 0.5) * 2 * spread
            days = max(1, round(raw))
            if i < slow:                     # a stated share of slow cases, not a random tail
                days += typical + 6 + i * 2
            lines.append(f"{unit};{days}")
            total += 1
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out} ({total} cases in {len(UNITS)} units)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
