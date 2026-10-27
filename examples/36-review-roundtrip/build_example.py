#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
build_example.py — regenerate example 36 from nothing.

Stdlib only, no arguments, no network. Writes the data file, the annotated artefact, the
review block a reader would paste back, and the report that block produces. Running it
twice gives the same bytes: SOURCE_DATE_EPOCH pins both stamps.

The block is generated from the artefact's own identity, not typed in by hand, so the
committed `tilbakemelding.txt` always belongs to the committed `saksbehandling.html` — a
rebuild that changes the build stamp regenerates the block with it instead of leaving an
example that no longer resolves.

    python3 examples/36-review-roundtrip/build_example.py
"""
from __future__ import annotations

import csv
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = HERE / "saksbehandling.csv"
ARTEFACT = HERE / "saksbehandling.html"
PAYLOAD = HERE / "tilbakemelding.txt"
REPORT = HERE / "tilbakemelding.md"

sys.path.insert(0, str(ROOT / "tools"))
import read_review  # noqa: E402  the reader side of the round trip
import review_layer  # noqa: E402  owns the block format's header lines

# A synthetic month/enhet/sakstype/kanal grid. Deterministic, so the numbers in the
# README and in the committed report stay true.
MAANEDER = ("2026-01", "2026-02", "2026-03", "2026-04")
ENHETER = ("Nord", "Sør")
SAKSTYPER = ("Etterlevelse", "Rapportering", "Kundeklager")
KANALER = ("Nettbank", "Mobil", "Telefon", "E-post")


def write_data() -> None:
    rows = []
    for i, (m, e, s, k) in enumerate((m, e, s, k) for m in MAANEDER for e in ENHETER
                                    for s in SAKSTYPER for k in KANALER):
        antall = 18 + (i * 37) % 84
        kostnad = antall * (920 + (i * 53) % 640)
        rows.append({"Maaned": m, "Enhet": e, "Sakstype": s, "Kanal": k,
                     "Antall": antall, "Kostnad": kostnad})
    with DATA.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def build() -> None:
    env = dict(os.environ, SOURCE_DATE_EPOCH="1792836000")   # 2026-10-24 10:00 UTC
    cmd = [sys.executable, str(ROOT / "tools" / "build_dashboard.py"),
           "--data", str(DATA),
           "--title", "Saksbehandling: kostnad per sak",
           "--dimension", "Sakstype", "--measure", "Kostnad", "--time", "Maaned",
           "--filters", "Enhet,Sakstype,Kanal",
           "--source", "Syntetisk eksempeldata (saksbehandling.csv)",
           "--requested-by", "Enhetsleder",
           "--annotate",
           "--out", str(ARTEFACT)]
    subprocess.run(cmd, check=True, env=env)


def write_payload() -> None:
    """The block a reader hands back: a greeting, a quoted block, a signature."""
    art = read_review.artefact(ARTEFACT)
    cfg, data = art["config"], art["data"]
    keys, measure = cfg["keys"], cfg["measure"]

    def coord(row: dict) -> str:
        return " | ".join(read_review._display(row.get(k)) for k in keys)

    def value(row: dict) -> str:
        return read_review._display(row.get(measure))

    # Three ways a block lands: a row that resolves exactly, a row whose value does not
    # match what the file holds, and a row the file does not hold at all.
    exact = next(r for r in data if r["Enhet"] == "Nord" and r["Maaned"] == "2026-01")
    moved = next(r for r in data if r["Enhet"] == "Sør" and r["Maaned"] == "2026-03")
    gone = dict(next(r for r in data if r["Enhet"] == "Sør"), Enhet="Øst")

    head = review_layer.header_lines(title=cfg["title"], file=cfg["file"], built=cfg["built"],
                                   rows=cfg["rows"], source=cfg["source"], keys=keys,
                                   measure=measure)
    blocks = [
        [f"row: {coord(exact)}", f"value: {value(exact)}",
         "comment: Stemmer med det vi faktisk betalte i januar."],
        # The reader's own figure, from their invoice, not from the file. The report shows
        # both numbers and does not decide who is right.
        [f"row: {coord(moved)}", "value: 79 200",
         "comment: Dette er ikke tallet vi fikk oppgitt.",
         "Fakturaen fra mars sier noe annet."],            # wrapped by a mail client
        [f"row: {coord(gone)}", f"value: {value(gone)}",
         "comment: Denne enheten finnes ikke hos oss. Hvor kommer raden fra?"],
    ]
    body: list[str] = []
    for b in blocks:
        body += b + ["--"]
    body = body[:-1]                                       # no trailing separator
    quoted = head + ["--"] + body
    lines = ["Hei,", "", "jeg har sett gjennom tallene. Tre ting:", ""]
    lines += ["> " + ln if ln else ">" for ln in quoted]
    lines += ["", "Mvh", "Enhetsleder Nord"]
    PAYLOAD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def report() -> None:
    subprocess.run([sys.executable, str(ROOT / "tools" / "read_review.py"),
                    str(ARTEFACT), str(PAYLOAD), "--out", str(REPORT)], check=True)


if __name__ == "__main__":
    write_data()
    build()
    write_payload()
    report()
    print(f"example 36: {DATA.name}, {ARTEFACT.name}, {PAYLOAD.name}, {REPORT.name}")
