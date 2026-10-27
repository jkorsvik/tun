#!/usr/bin/env python3
"""Write the synthetic extract the scatter example is built from.

One row per unit: how long the unit takes to answer (minutes) and what its customers score it
(0-100). Deliberately not a straight line, and deliberately holding one unit that sits apart
from the rest, because the point of the picture is that a reader can find it.

Fixed values, not a random draw: an example that changes between runs cannot be checked
against its own committed output.
"""
from __future__ import annotations

import pathlib

HERE = pathlib.Path(__file__).resolve().parent

# (unit, minutes to first answer, satisfaction 0-100, area)
ROWS = [
    ("Nord-Troms", 4, 88, "Nord"),
    ("Salten", 6, 84, "Nord"),
    ("Helgeland", 7, 82, "Nord"),
    ("Ofoten", 9, 79, "Nord"),
    ("Lofoten", 11, 77, "Nord"),
    ("Vesterålen", 13, 74, "Nord"),
    ("Innherred", 5, 71, "Midt"),
    ("Namdal", 8, 73, "Midt"),
    ("Fosen", 12, 68, "Midt"),
    ("Gauldal", 16, 66, "Midt"),
    ("Orkdal", 19, 62, "Midt"),
    ("Hallingdal", 6, 69, "Sør"),
    ("Numedal", 10, 67, "Sør"),
    ("Setesdal", 14, 64, "Sør"),
    ("Aust-Agder", 17, 61, "Sør"),
    ("Vest-Telemark", 21, 58, "Sør"),
    ("Midt-Buskerud", 24, 55, "Sør"),
    # The one that sits apart: slow to answer and still scored high. A scatter exists to put
    # a unit like this on the page, because a table of averages hides it.
    ("Hardangervidda", 38, 81, "Sør"),
]


def main() -> int:
    out = HERE / "enheter.csv"
    lines = ["Enhet;Svartid;Tilfredshet;Omrade"]
    lines += [f"{name};{minutes};{score};{area}" for name, minutes, score, area in ROWS]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(ROWS)} units)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
