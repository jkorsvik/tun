#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write the fixed, synthetic task-space example. No random input and no real data."""
from pathlib import Path
import csv

ROWS = [
    ("question", "Spørsmål", "Question", "Start med leseren, beslutningen og kilden. Det er den egentlige inndaten.", "Start with the reader, the decision and the source. That is the real input.", -2.4, 0.9, 0.0),
    ("data", "Data", "Data", "Et regneark, en CSV eller et spørreresultat. Behold uttrekket og opphavet.", "A spreadsheet, CSV or query result. Keep the extract and its provenance.", -1.45, -0.75, 0.9),
    ("skill", "Skill", "Skill", "En Markdown-skill bærer metoden, grensene og kontrollene.", "A Markdown skill carries the method, constraints and checks.", -0.65, 1.25, -0.6),
    ("build", "Bygg", "Build", "Vanlig HTML, CSS og JavaScript blir et dokument eller verktøy som virker.", "Plain HTML, CSS and JavaScript become a working document or tool.", 0.35, 0.0, 0.0),
    ("verify", "Kontroller", "Verify", "Åpne resultatet som en leser. Kontroller tall, samspill og leveringsvei.", "Open the result as a reader. Check the numbers, interaction and delivery path.", 1.35, 1.05, 0.7),
    ("share", "Del", "Share", "Bruk en mappe eller lenke. Mottakeren trenger ingen ny plattform.", "Use a folder or link. The recipient needs no new platform.", 2.2, -0.75, -0.7),
    ("reader", "Leser", "Reader", "Utforsk, presenter, bestem eller fortsett arbeidet inne i filen.", "Explore, present, decide or continue the work inside the file.", 2.8, 0.65, 0.0),
]
FIELDS = ["Step", "Title_nb", "Title_en", "Description_nb", "Description_en", "X", "Y", "Z"]


def main() -> None:
    target = Path(__file__).with_name("trinn.csv")
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(FIELDS)
        writer.writerows(ROWS)
    print(f"wrote {target} ({len(ROWS)} synthetic steps)")


if __name__ == "__main__":
    main()
