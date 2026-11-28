#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
generate_data.py — the initial state of the service-book example.

Stdlib only. Deterministic: the tables below fully determine the output, so the
committed `service-book.json` regenerates byte for byte on any platform.

    python3 examples/57-service-book/generate_data.py

The scenario is invented: a three-day staffed information desk at a fictional
conference venue. Every person is a ROLE, not a name. That is deliberate — a role
label cannot accidentally resemble a real person, and it makes the example safe to
put on a public page.
"""
from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "service-book.json"

# Invented venue, invented event, invented people. No real operation, no real unit.
TITLE = "Servicebok · Informasjonsdisk Fjordhallen"
SUBTITLE = "Tre dager · alle tider Europe/Oslo · syntetisk eksempel"

# Roles rather than names: Desk A, Desk B ... Post 1, Post 2 ...
PEOPLE = [
    ("Desk A", "Skift 1"),
    ("Desk B", "Skift 1"),
    ("Desk C", "Skift 1"),
    ("Desk D", "Skift 2"),
    ("Desk E", "Skift 2"),
    ("Desk F", "Skift 2"),
    ("Desk G", "Skift 3"),
    ("Desk H", "Skift 3"),
    ("Desk I", "Skift 3"),
    ("Desk J", "Skift 4"),
    ("Desk K", "Skift 4"),
    ("Desk L", "Skift 4"),
    ("Reserve 1", "Reserve"),
    ("Reserve 2", "Reserve"),
]

# Three full days of four-hour watches, three roles per watch.
CREW = [
    ("Desk A", "Desk B", "Desk C"),
    ("Desk D", "Desk E", "Desk F"),
    ("Desk G", "Desk H", "Desk I"),
    ("Desk J", "Desk K", "Desk L"),
    ("Desk A", "Desk E", "Desk H"),
    ("Desk B", "Desk F", "Desk I"),
    ("Desk C", "Desk D", "Desk G"),
    ("Desk A", "Desk F", "Desk K"),
    ("Desk B", "Desk G", "Desk L"),
    ("Desk C", "Desk H", "Desk J"),
    ("Desk A", "Desk D", "Desk I"),
    ("Desk B", "Desk E", "Desk J"),
    ("Desk C", "Desk F", "Desk K"),
    ("Desk A", "Desk G", "Desk L"),
    ("Desk B", "Desk H", "Desk I"),
    ("Desk C", "Desk D", "Desk J"),
    ("Desk A", "Desk E", "Desk K"),
    ("Desk B", "Desk F", "Desk L"),
]

DAYS = [
    {"date": "2027-03-08", "label": "Mandag 8.3", "note": "oppstartsdag"},
    {"date": "2027-03-09", "label": "Tirsdag 9.3", "note": "full rullering"},
    {"date": "2027-03-10", "label": "Onsdag 10.3", "note": "faste poster fra 12.00"},
]

# The mid-period switch: from 12.00 on the last day the rotation stops and fixed
# posts take over. This is the logic the example exists to show.
ROTATION_ENDS = "2027-03-10T12:00"


def main() -> int:
    people = []
    ids = {}
    for index, (name, lag) in enumerate(PEOPLE, start=1):
        pid = "p%d" % index
        ids[name] = pid
        people.append({
            "id": pid,
            "name": name,
            "lag": lag,
            "note": "",
            "reserve": lag == "Reserve",
        })

    watches = []
    for index, crew in enumerate(CREW, start=1):
        watches.append({
            "id": "w%d" % index,
            "crew": [ids[name] for name in crew],
            "note": "",
        })

    # Assign absolute times: four-hour watches running continuously from the first day.
    from datetime import datetime, timedelta, timezone
    start = datetime(2027, 3, 8, 0, 0, tzinfo=timezone.utc)
    for index, watch in enumerate(watches):
        begin = start + timedelta(hours=4 * index)
        watch["start"] = begin.strftime("%Y-%m-%dT%H:%M")
        watch["end"] = (begin + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M")

    # Fixed posts that take over at the rotation cut.
    posts = [
        {"id": "v1", "name": "Hovedinngang · vest", "radio": "Kanal 1", "places": 1, "at": "12.00", "people": [ids["Desk A"]]},
        {"id": "v2", "name": "Hovedinngang · øst", "radio": "Kanal 1", "places": 1, "at": "12.00", "people": [ids["Desk B"]]},
        {"id": "v3", "name": "Informasjonsdisk", "radio": "Kanal 2", "places": 2, "at": "12.00", "people": [ids["Desk C"], ids["Desk D"]]},
        {"id": "v4", "name": "Utstillingshall · runde", "radio": "Kanal 2", "places": 1, "at": "12.30", "people": [ids["Desk E"]]},
    ]

    state = {
        "schema": 1,
        "sourceRevision": "2027-03-08-synthetic",
        "title": TITLE,
        "subtitle": SUBTITLE,
        "footer": (
            "Syntetisk eksempeldata. Roller, ikke personer. Ingen telefonnumre, "
            "koder eller tilgangsnøkler finnes i dette dokumentet."
        ),
        "panes": [
            {"id": "naa", "title": "Nå", "type": "naa", "badge": True},
            {"id": "rullering", "title": "Rullering", "heading": "Gjeldende vaktliste", "type": "rullering", "badge": True},
            {"id": "poster", "title": "Poster", "heading": "Faste poster", "type": "posts", "badge": True},
            {"id": "folk", "title": "Folk", "heading": "Folk", "type": "folk", "badge": True},
            {"id": "beskjed", "title": "Beskjed", "heading": "Beskjed", "type": "beskjed"},
            {"id": "regler", "title": "Regler", "heading": "Regler", "type": "instruks"},
            {"id": "sjekk", "title": "Sjekk", "heading": "Sjekk", "type": "sjekk", "badge": True},
        ],
        "days": DAYS,
        "people": people,
        "watches": watches,
        "beskjed": {"from": "12.00 onsdag 10.3", "posts": posts},
        "handover": {
            "rotationEnds": ROTATION_ENDS,
            "replacedBy": "Faste poster",
            "changed": "Rulleringsvaktene etter 10.3 kl. 12.00 er str\u00f8ket.",
            "unchanged": "Navnene p\u00e5 de faste postene er uendret.",
            "undecided": [
                "Hva de p\u00e5 vakt gj\u00f8r i overgangen mellom rullering og faste poster.",
                "Hvilke oppgaver reservene har etter at de faste postene er satt.",
            ],
        },
        "lists": {
            "beskjed-bakgrunn": [
                "Tredagers arrangement i Fjordhallen med publikum, utstillere og leverand\u00f8rer.",
            ],
            "beskjed-oppgave": [
                "Holde hovedinngangene betjent, drive informasjonsdisken og g\u00e5 runder i utstillingshallen.",
            ],
            "beskjed-bemanning": [
                "To roller p\u00e5 hovedinngang, to p\u00e5 informasjonsdisk, \u00e9n p\u00e5 runde.",
                "Reservene brukes bare ved frafall.",
            ],
            "utstyr": [
                "Refleksvest brukes av alle som g\u00e5r runder.",
                "Radio testes ved skiftstart.",
            ],
            "orden": [
                "Ingen g\u00e5r av f\u00f8r avl\u00f8ser er p\u00e5 plass.",
                "P\u00e5troppende m\u00f8ter ti minutter f\u00f8r skiftet.",
            ],
            "klargjoring": [
                "Utstyr til neste vakt ligger klart.",
                "Radioene er testet f\u00f8r overlevering.",
            ],
            "plan": [],
            "forhold": ["Publikum sluses gjennom hovedinngang vest."],
            "spesielt": ["Ingen slippes inn uten billett eller utstillerpass."],
            "kontakter": ["Vaktmester", "Arrangementsleder", "Førstehjelp"],
            "kommunikasjon": [
                "Kanal 1 for inngang, kanal 2 for disk og runder.",
                "Telefonnumre og koder st\u00e5r ikke i dette dokumentet.",
            ],
            "open": [],
        },
    }

    OUT.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
                   encoding="utf-8", newline="")
    print("wrote %s (%d bytes, %d people, %d watches, %d posts)"
          % (OUT.relative_to(HERE.parent.parent), OUT.stat().st_size,
             len(state["people"]), len(state["watches"]), len(posts)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
