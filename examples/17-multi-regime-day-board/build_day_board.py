#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
build_day_board.py — generates oversikt.html + data.js for
examples/17-multi-regime-day-board.

Nothing in the output is hand-written (docs/08-generic-artifact-model.md): the
markup comes from oversikt.template.html, the rows come
from the table below, and both are written by this script.

The subject is an invented scenario: a fictional school, Eksempelskolen, in a
fictional municipality, Eksempelkommune, which runs pupil transport under THREE
régimes with THREE different owners. No real school or municipality is behind
it. That structure is the point of the example; see README.md.

ALL DATA IS SYNTHETIC, and the build proves it rather than promising it. Every
value in every column must match its column's allow-list in VOCABULARY below,
so free text — and therefore a name — cannot enter the data at all. That is an
allow-list rather than a deny-list of particular names, which is why it also
holds against identifiers nobody thought to forbid.

Nine columns, one row per pupil per leg per day:
    Dato ElevKode Retning Ordning Planlagt Bil Ledsager Status EndretAv

Run:
    python3 examples/17-multi-regime-day-board/build_day_board.py

Then verify (both must be run — the first is the repo gate, the second adds the
JS-off and viewport checks this example exists to demonstrate):
    python3 tools/verify_dashboard.py examples/17-multi-regime-day-board/oversikt.html
    python3 examples/17-multi-regime-day-board/verify_day_board.py
"""
from __future__ import annotations

import datetime
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
TEMPLATE = HERE / "oversikt.template.html"
OUT_HTML = HERE / "oversikt.html"
OUT_DATA = HERE / "data.js"

sys.path.insert(0, str(REPO / "tools"))
from verify_standalone_core import (  # noqa: E402
    check_no_leftover_placeholders,
    check_no_stray_script_text,
    check_provenance,
)

TITLE = "Skoletransport \u2014 dagsoversikt"
# Short on purpose: at 390px a two-line subtitle pushed the header to 190px,
# a quarter of the screen. The full sentence is in the footer instead.
SUBTITLE = "M\u00f8nstereksempel \u2014 syntetiske data"
SOURCE_DESCRIPTION = "Syntetisk eksempeldata (ingen virkelige elever)"
EXTRACT_TIMESTAMP = "2026-09-19 06:40"
REQUESTED_BY = "Skoleadministrasjonen"

COLUMNS = ["Dato", "ElevKode", "Retning", "Ordning", "Planlagt", "Bil",
           "Ledsager", "Status", "EndretAv"]

# What each column is allowed to contain. Checked over every generated row, so
# a typo fails the build rather than reaching data.js. verify_*.py restates this
# independently on the written file — deliberately a second copy, because a
# generator that checks only its own vocabulary proves nothing about what it
# actually wrote.
#
# Be precise about what that second copy does and does not buy, because an
# earlier version of this comment overclaimed it. Two hand-typed copies fail
# loudly in ONE direction only: make the verifier's copy STRICTER and the
# mismatch is immediate. Make it LOOSER and nothing notices — the limit case,
# re.compile(r".*"), passes every pattern check while proving nothing. The
# verifier therefore does not rely on its patterns alone: it also asserts the
# exact SET of values found per closed column, which no pattern edit can widen,
# and it feeds every pattern a name-shaped canary that an allow-list must reject.
# See EXPECTED_VALUES in verify_day_board.py.
VOCABULARY = {
    "Dato": r"\d{4}-\d{2}-\d{2}",
    "ElevKode": r"ELEV-\d\d",
    "Retning": r"Til skole|Fra skole|Fra SFO",
    "Ordning": r"Grunnskole drosje|langdagSFO TT-kort|VGS TT-kort",
    "Planlagt": r"[0-2]\d:[0-5]\d",
    "Bil": r"(OT|TT)-\d\d|Ikke bestilt|Avventer TT-kort",
    "Ledsager": r"Ja|Nei|Vurderes",
    "Status": r"I rute|Venter|Avlyst",
    "EndretAv": r"Skoleadm\.|SFO|Sentralbord|Foresatt|Kommune",
}

TOKENS_REMOVED = """This example deliberately reads NO token file at all — not
even the core one.

That is a deliberate third case, and it is why the example is here. docs/22
gives two: core ships a neutral palette in tools/tokens/palette-neutral.css,
and a brand plugin may provide its own. Both assume the artefact belongs to the
organisation whose repo this is. In this scenario it does not: the board is
built for a third party with its own brand, which this repository does not have.

So loading EITHER palette would dress one organisation's artefact in another
organisation's colours: a licensing question wearing a styling question's
clothes. The values below are neutral functional defaults with measured
contrast, they are nobody's brand, and they sit in ONE marked slot so a real
tenant palette can replace them in a single edit.

The seam is the same seam. Read the slot as an unresolved plugin: the artefact
declares what it needs, names the file that would satisfy it, and records the
absence instead of papering over it.
"""

# Neutral base. Plain greyscale on purpose: a low-stimulus day board reads better
# on a wall display, and greyscale is not identifiable as anyone's palette.
BASE_PALETTE = {
    "--surface":        ("#ffffff", "page background"),
    "--surface-sunken": ("#f7f7f7", "KPI cards, panels, table stripes"),
    "--line":           ("#e6e6e6", "hairlines"),
    # #c9c9c9 read nicer and was 1.66:1 on white — WCAG 2.2 1.4.11 wants 3:1
    # for a control boundary. The gate below caught it; this is the fix.
    "--line-strong":    ("#8c8c8c", "control borders"),
    "--ink":            ("#2b2b2b", "body text"),
    "--ink-muted":      ("#5f5f5f", "secondary text, axis labels"),
}

# ONE slot. Every value is a placeholder chosen for measured contrast, and none is
# any organisation's colour. Inventing a plausible "kommuneblaa" would be inventing
# a brand, which is worse than leaving the slot visibly unresolved. See README §5.
TENANT_SLOT_PALETTE = {
    "--primary":            ("#3f4b54", "chart bars, KPI rule, focus accents"),
    "--primary-dark":       ("#2b343a", "header band"),
    "--status-positive":    ("#1d6f42", "i rute — green circle"),
    "--status-positive-bg": ("#eef6f1", "i rute — badge tint"),
    "--status-warning":     ("#8a5a00", "venter — yellow triangle, darkened to read"),
    "--status-warning-bg":  ("#fdf4e3", "venter — badge tint"),
    "--status-negative":    ("#a52121", "avvik/avlyst — red square"),
    "--status-negative-bg": ("#fbeeee", "avvik/avlyst — badge tint"),
    "--status-neutral":     ("#5f5f5f", "unrecognised value"),
}

# Contrast pairs the build refuses to ship without. WCAG 2.2: 4.5:1 for text,
# 3:1 for a non-text boundary or graphic. Measured, never recalled — a palette
# edit that breaks readability fails the build with the ratio it got.
CONTRAST_GATE = [
    ("--ink", "--surface", 4.5), ("--ink", "--surface-sunken", 4.5),
    ("--ink-muted", "--surface", 4.5), ("--ink-muted", "--surface-sunken", 4.5),
    ("--surface", "--primary-dark", 4.5),
    ("--status-positive", "--surface", 4.5),
    ("--status-positive", "--status-positive-bg", 4.5),
    ("--status-warning", "--surface", 4.5),
    ("--status-warning", "--status-warning-bg", 4.5),
    ("--status-negative", "--surface", 4.5),
    ("--status-negative", "--status-negative-bg", 4.5),
    ("--status-neutral", "--surface", 4.5),
    ("--primary", "--surface", 3.0), ("--line-strong", "--surface", 3.0),
]

ORD_GS = "Grunnskole drosje"
ORD_SFO = "langdagSFO TT-kort"
ORD_VGS = "VGS TT-kort"

# Which role maintains a row by default. Deliberately different per regime —
# that difference is the whole point of the example.
STANDARD_EIER = {ORD_GS: "Skoleadm.", ORD_SFO: "SFO", ORD_VGS: "Skoleadm."}

DATES = ["2026-09-14", "2026-09-15", "2026-09-16"]

# (ElevKode, Ordning, Ledsager, Bil, [(Retning, Planlagt), ...])
PUPILS = [
    ("ELEV-01", ORD_GS, "Nei", "OT-31", [("Til skole", "07:50"), ("Fra skole", "14:10")]),
    ("ELEV-02", ORD_GS, "Ja", "OT-31", [("Til skole", "07:50"), ("Fra skole", "14:10")]),
    ("ELEV-03", ORD_GS, "Nei", "OT-32", [("Til skole", "08:00"), ("Fra skole", "14:10")]),
    ("ELEV-04", ORD_GS, "Vurderes", "OT-32", [("Til skole", "08:00"), ("Fra skole", "14:40")]),
    ("ELEV-05", ORD_GS, "Ja", "OT-33", [("Til skole", "08:10"), ("Fra skole", "14:40")]),
    ("ELEV-06", ORD_GS, "Nei", "OT-33", [("Til skole", "08:10"), ("Fra skole", "14:40")]),
    ("ELEV-07", ORD_GS, "Nei", "OT-34", [("Til skole", "08:20"), ("Fra skole", "15:10")]),
    ("ELEV-08", ORD_SFO, "Ja", "TT-51", [("Til skole", "07:50"), ("Fra SFO", "16:10")]),
    ("ELEV-09", ORD_SFO, "Nei", "TT-52", [("Til skole", "08:00"), ("Fra SFO", "16:10")]),
    ("ELEV-10", ORD_SFO, "Vurderes", "TT-53", [("Til skole", "08:10"), ("Fra SFO", "16:40")]),
    ("ELEV-11", ORD_SFO, "Nei", "TT-54", [("Til skole", "08:20"), ("Fra SFO", "16:40")]),
    ("ELEV-12", ORD_VGS, "Nei", "TT-71", [("Til skole", "07:50"), ("Fra skole", "15:10")]),
    ("ELEV-13", ORD_VGS, "Nei", "TT-72", [("Til skole", "08:20"), ("Fra skole", "15:10")]),
    ("ELEV-14", ORD_VGS, "Ja", "TT-73", [("Til skole", "08:00"), ("Fra skole", "15:40")]),
]

# Deviations from the plan, keyed (Dato, ElevKode, Retning). Each one is a case
# the three regimes handle through a different owner — which is why the day
# board cannot be one flat list.
OVERRIDES = {
    # Sickness: SMS before 07:00, school cancels both legs.
    ("2026-09-15", "ELEV-03", "Til skole"): {"Status": "Avlyst", "EndretAv": "Foresatt"},
    ("2026-09-15", "ELEV-03", "Fra skole"): {"Status": "Avlyst", "EndretAv": "Skoleadm."},
    # Same-day change phoned in to the switchboard; new time not confirmed yet.
    ("2026-09-16", "ELEV-06", "Fra skole"): {"Status": "Venter", "Planlagt": "15:10",
                                             "EndretAv": "Sentralbord"},
    # langdagSFO: the parents order the taxi themselves, so the school cannot
    # book this one — it can only show that it is not booked.
    ("2026-09-15", "ELEV-10", "Fra SFO"): {"Status": "Venter", "Bil": "Ikke bestilt",
                                           "EndretAv": "Foresatt"},
    ("2026-09-16", "ELEV-09", "Fra SFO"): {"Status": "Venter", "Bil": "Ikke bestilt",
                                           "EndretAv": "Foresatt"},
    # VGS: TT-kort renewal pending at the kommune.
    ("2026-09-14", "ELEV-12", "Til skole"): {"Status": "Venter", "Bil": "Avventer TT-kort",
                                             "EndretAv": "Kommune"},
    # Collected by a parent instead.
    ("2026-09-14", "ELEV-11", "Fra SFO"): {"Status": "Avlyst", "EndretAv": "Foresatt"},
    # Ledsager under assessment by SFO for one leg only.
    ("2026-09-14", "ELEV-04", "Til skole"): {"Ledsager": "Vurderes", "EndretAv": "SFO"},
}


def _luminance(hex_colour: str) -> float:
    """WCAG 2.2 relative luminance of an #rrggbb colour."""
    parts = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in parts]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(fg: str, bg: str) -> float:
    a, b = _luminance(fg), _luminance(bg)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def render_palette_css() -> str:
    """Emit the :root colour block, gated on measured WCAG contrast.

    Nothing here is read from a brand file. See TOKENS_REMOVED for why, and the
    README's open item 3 for what replaces the slot values.
    """
    palette = {**BASE_PALETTE, **TENANT_SLOT_PALETTE}
    failures = []
    measured = {}
    for fg, bg, minimum in CONTRAST_GATE:
        ratio = contrast_ratio(palette[fg][0], palette[bg][0])
        measured[(fg, bg)] = ratio
        if ratio < minimum:
            failures.append(f"{fg} on {bg} is {ratio:.2f}:1, needs {minimum}:1")
    if failures:
        raise SystemExit("FAIL: palette does not meet WCAG 2.2:\n  - "
                         + "\n  - ".join(failures))

    lines = ["    /* Neutral base — plain greyscale, not an organisation's palette. */"]
    for name, (value, role) in BASE_PALETTE.items():
        lines.append(f"    {name}:{value}; /* {role} */")
    lines += [
        "",
        "    /* ▼▼▼ TENANT PALETTE SLOT — THE ONLY PLACE COLOUR IS SET ▼▼▼",
        "       Every value below is a NEUTRAL PLACEHOLDER. None of them is any",
        "       organisation's colour, and inventing one would be inventing a brand.",
        "       Replace these nine values — and nothing else in the stylesheet —",
        "       when a tenant supplies its real palette. build_day_board.py",
        "       re-measures contrast on every build and refuses to ship a pair below",
        "       WCAG 2.2, so a brand-accurate palette that cannot be read fails the",
        "       build rather than the user. */",
    ]
    for name, (value, role) in TENANT_SLOT_PALETTE.items():
        lines.append(f"    {name}:{value}; /* {role} */")
    lines.append("    /* ▲▲▲ END TENANT PALETTE SLOT ▲▲▲ */")
    lines.append("")
    lines.append("    /* Contrast measured at build time, not recalled:")
    for (fg, bg), ratio in measured.items():
        lines.append(f"         {fg} on {bg}: {ratio:.2f}:1")
    lines.append("       ...all at or above the WCAG 2.2 minimum for their use. */")
    return "\n".join(lines)


def build_rows() -> list[dict]:
    rows = []
    for date in DATES:
        for kode, ordning, ledsager, bil, legs in PUPILS:
            for retning, planlagt in legs:
                row = {
                    "Dato": date,
                    "ElevKode": kode,
                    "Retning": retning,
                    "Ordning": ordning,
                    "Planlagt": planlagt,
                    "Bil": bil,
                    "Ledsager": ledsager,
                    "Status": "I rute",
                    "EndretAv": STANDARD_EIER[ordning],
                }
                row.update(OVERRIDES.get((date, kode, retning), {}))
                rows.append({k: row[k] for k in COLUMNS})
    return rows


def check_rows(rows: list[dict]) -> None:
    """The example claims coverage; prove it rather than assert it."""
    problems = []
    for want in (ORD_GS, ORD_SFO, ORD_VGS):
        if not any(r["Ordning"] == want for r in rows):
            problems.append(f"no rows for Ordning {want!r}")
    for want in ("Til skole", "Fra skole", "Fra SFO"):
        if not any(r["Retning"] == want for r in rows):
            problems.append(f"no rows for Retning {want!r}")
    for want in ("I rute", "Venter", "Avlyst"):
        if not any(r["Status"] == want for r in rows):
            problems.append(f"no rows with Status {want!r}")
    for want in ("Ja", "Nei", "Vurderes"):
        if not any(r["Ledsager"] == want for r in rows):
            problems.append(f"no rows with Ledsager {want!r}")
    # All nine columns, every row. Checking only the five that carry the
    # example's story would let a typo into Bil, Planlagt, Dato or EndretAv.
    for number, row in enumerate(rows, start=1):
        if sorted(row) != sorted(COLUMNS):
            problems.append(f"row {number} has columns {sorted(row)}, "
                            f"expected {sorted(COLUMNS)}")
            continue
        for column, pattern in VOCABULARY.items():
            if not re.fullmatch(pattern, str(row[column])):
                problems.append(f"row {number}: {column}={row[column]!r} is outside "
                                f"the synthetic vocabulary /{pattern}/")
    # Every override must have matched a real leg, or the case it documents is
    # silently absent from the data.
    keys = {(r["Dato"], r["ElevKode"], r["Retning"]) for r in rows}
    for key in OVERRIDES:
        if key not in keys:
            problems.append(f"override {key} matched no leg — dead entry")
    if problems:
        raise SystemExit("FAIL: synthetic data is wrong:\n  - " + "\n  - ".join(problems[:20]))


def write_data_js(rows: list[dict], extract: str) -> None:
    # One JSON object per line: still a single JS assignment, but a diff shows
    # which leg changed instead of one 16 KB line.
    body_rows = ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    meta = json.dumps(
        {"generated": extract, "source": SOURCE_DESCRIPTION, "rows": len(rows)},
        ensure_ascii=False,
    )
    body = (
        "// data.js \u2014 datafilen for oversikt.html. Bytt ut denne filen, og alle som\n"
        "// \u00e5pner oversikten ser nye tall. Oversikten selv endres ikke.\n"
        "//\n"
        "// GENERERT AV build_day_board.py \u2014 ikke rediger for hand.\n"
        "// SYNTETISKE DATA. Ingen virkelige elever, ingen virkelige initialer.\n"
        f"// Uttrekk {extract}. {len(rows)} rader. Kolonner: {', '.join(COLUMNS)}.\n"
        "//\n"
        "// Lest av oversikt.html som kode, ikke som data: en fil som \u00e5pnes lokalt\n"
        "// f\u00e5r ikke lese en vanlig nabofil i det hele tatt \u2014 se\n"
        "// docs/01-tenant-constraints.md rad 14-16.\n"
        "window.DASHBOARD_DATA=[\n"
        f"{body_rows}\n"
        "];\n"
        f"window.DASHBOARD_META={meta};\n"
    )
    OUT_DATA.write_text(body, encoding="utf-8")


def write_html(rows: list[dict], build_stamp: str) -> None:
    html = TEMPLATE.read_text(encoding="utf-8")
    substitutions = {
        "{{TITLE}}": TITLE,
        "{{SUBTITLE}}": SUBTITLE,
        "{{SOURCE_DESCRIPTION}}": SOURCE_DESCRIPTION,
        "{{EXTRACT_TIMESTAMP}}": EXTRACT_TIMESTAMP,
        "{{BUILD_TIMESTAMP}}": build_stamp,
        "{{REQUESTED_BY}}": REQUESTED_BY,
        "{{ROW_COUNT}}": str(len(rows)),
        "{{PALETTE_CSS}}": render_palette_css(),
        "{{REQUIRED_COLS_JSON}}": json.dumps(COLUMNS, ensure_ascii=False),
    }
    for token, value in substitutions.items():
        if token not in html:
            raise SystemExit(f"FAIL: {token} is not in {TEMPLATE.name} — "
                             "the builder would ship a value nobody uses")
        html = html.replace(token, value)

    # Build-time gates. A generator that ships a half-substituted file, or one
    # that fails the tenant's script scan, has not built anything usable.
    for ok, msg in (check_no_leftover_placeholders(html),
                    check_provenance(html),
                    check_no_stray_script_text(html)):
        if not ok:
            raise SystemExit(f"FAIL: {msg}")
    OUT_HTML.write_text(html, encoding="utf-8")


def main() -> int:
    build_stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = build_rows()
    check_rows(rows)
    write_data_js(rows, EXTRACT_TIMESTAMP)
    write_html(rows, build_stamp)

    kinds = {}
    for row in rows:
        kinds[row["Ordning"]] = kinds.get(row["Ordning"], 0) + 1
    print(f"wrote {OUT_DATA.name}   {OUT_DATA.stat().st_size / 1024:.1f} KB  "
          f"{len(rows)} rader")
    print(f"wrote {OUT_HTML.name}  {OUT_HTML.stat().st_size / 1024:.1f} KB")
    print(f"  {len(PUPILS)} elevkoder, {len(DATES)} datoer, "
          f"{len(OVERRIDES)} avvik fra planen")
    for name, count in sorted(kinds.items()):
        print(f"  {count:3d} rader  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
