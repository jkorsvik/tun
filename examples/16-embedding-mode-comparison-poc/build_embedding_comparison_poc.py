#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
build_embedding_comparison_poc.py — generates embedding-mode-comparison-poc.html
and its paired sidecar, paired-data.js.

Diagnostic tool, not a design pattern demo. Grew out of a real incident
(issue #39, 15. sept. 2026): a saksrom case file rendered a misleading "no data"
message when opened via SharePoint's own inline file-preview pane ("hurtigvisning"
in the document library — single click, NOT a download, NOT the `/preview`
embed.aspx viewer already covered by tenant-constraints.md row 4). Two theories
were floated and disproved before the real cause was found with two clean A/B
tests run directly against the live tenant, same click path, repeated:

  - Embedded (inline <script>), single-line JSON-style string data -> WORKED
  - Embedded, same content but built from ~35 lines of "text" + "text" +
    string concatenation -> FAILED (blank/misleading), even though the file is
    100% valid JS (`node --check` clean) and renders perfectly from `file://`
    in a real (Playwright) browser
  - Paired (`<script src="./data.js">`), single-line data -> FAILED in the same
    preview, but worked fine opened directly from a synced OneDrive folder

This file turns that one-off investigation into a standing, reusable tool: drop
it in any SharePoint document library, open it the same way (single click,
inline preview — not "Open" / not a download), and read off which panels turned
green. No need to build ad hoc POCs from scratch next time this class of bug is
suspected.

Four panels, not three — the fourth (B) is the confirmed bug itself, included so
this file can reproduce the actual incident on demand, not just show the
recommended pattern:

  A. Embedded + JavaScript, single-line data              — recommended pattern
  B. Embedded + JavaScript, multi-line string concatenation — CONFIRMED to fail
     in SharePoint's inline preview; kept here deliberately so the failure can
     be reproduced on demand instead of only living in an issue thread
  C. Embedded, no JavaScript required at all               — always safe
  D. Paired (`<script src>`)                                — CONFIRMED to fail
     in SharePoint's inline preview regardless of data format

All four panels show IDENTICAL text content, so a viewer can visually confirm
"same data, different embedding method, different result" without reading code.

Run this to (re)generate the two output files. Do not hand-edit the .html.
"""
from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

# Identical content in every panel — the multi-paragraph shape is deliberate,
# it is exactly the kind of prose (pasted from documents/emails) that tends to
# get hand-formatted as multi-line concatenation by a human or an LLM.
TEXT = (
    "Dette er identisk eksempeltekst i alle fire rutene under, satt sammen av flere "
    "avsnitt \u2014 opprinnelig valgt fordi flerlinjes strengsammensetting mistenktes \u00e5 "
    "knekke embedded data i SharePoints innebygde forh\u00e5ndsvisning 15. september 2026; "
    "den mistanken er tilbakevist samme kveld (se rad 23 i tenant-constraints.md).\n\n"
    "Andre avsnitt f\u00f8lger her. Hvis dette avsnittet vises i alle fire rutene, virker "
    "ingenting av det denne siden tester \u00e5 skille mellom \u2014 se README.md."
)

TEXT_JSON = json.dumps(TEXT, ensure_ascii=False)

# Panel B: the confirmed-risky pattern, built the same way the real incident's
# summary.js was — physical line breaks with a trailing `+` on each line.
_b_parts = TEXT.split(". ")
PANEL_B_JS_LINES = []
for i, part in enumerate(_b_parts):
    suffix = ". " if i < len(_b_parts) - 1 else ""
    PANEL_B_JS_LINES.append(json.dumps(part + suffix, ensure_ascii=False))
PANEL_B_CONCAT = " +\n    ".join(PANEL_B_JS_LINES)

PAIRED_DATA_JS = f"window.PANEL_D_DATA = {TEXT_JSON};\n"

HTML = f"""<!DOCTYPE html>
<html lang="no">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>16 \u2014 Embedding-modus sammenligning (issue #39)</title>
<style>
:root{{
  --ink:#182430; --ink2:#5b6b7a; --line:#d8dee5; --bg:#f4f6f9; --panel:#fff;
  --ok:#007b5e; --ok-bg:#e9f8f4; --bad:#dc2a2a; --bad-bg:#fdeeee;
  --warn:#9a3412; --warn-bg:#fff7ed;
}}
*{{box-sizing:border-box;}}
body{{font-family:-apple-system,"Segoe UI",Arial,sans-serif;background:var(--bg);color:var(--ink);
  max-width:64rem;margin:0 auto;padding:1.5rem;line-height:1.55;}}
h1{{font-size:1.25rem;margin-bottom:0.25rem;}}
.intro{{background:var(--panel);border:1px solid var(--line);border-radius:0.5rem;padding:1rem 1.25rem;
  font-size:0.9rem;color:var(--ink2);margin-bottom:1.5rem;}}
.intro code{{background:#eef1f4;padding:0.1rem 0.3rem;border-radius:0.25rem;color:var(--ink);}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(20rem,1fr));gap:1rem;}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:0.5rem;padding:1.25rem;}}
.card h2{{margin-top:0;font-size:1rem;}}
.tag{{display:inline-block;font-size:0.7rem;font-weight:700;text-transform:uppercase;
  letter-spacing:0.03em;padding:0.15rem 0.5rem;border-radius:1rem;margin-bottom:0.5rem;}}
.tag.recommended{{background:var(--ok-bg);color:var(--ok);}}
.tag.risky{{background:var(--bad-bg);color:var(--bad);box-shadow:inset 0 0 0 1px var(--bad);}}
.tag.safe{{background:var(--ok-bg);color:var(--ok);}}
.tag.paired{{background:var(--warn-bg);color:var(--warn);}}
.status{{font-weight:700;padding:0.5rem 0.75rem;border-radius:0.375rem;margin:0.5rem 0;font-size:0.85rem;}}
.status.pending{{background:#f0f0f0;color:var(--ink2);}}
.status.ok{{background:var(--ok-bg);color:var(--ok);}}
.status.fail{{background:var(--bad-bg);color:var(--bad);box-shadow:inset 0 0 0 1px var(--bad);}}
.content{{font-size:0.85rem;white-space:pre-wrap;border-top:1px solid var(--line);padding-top:0.75rem;margin-top:0.5rem;}}
footer{{margin-top:2rem;font-size:0.75rem;color:var(--ink2);border-top:1px solid var(--line);padding-top:0.75rem;}}
</style>
</head>
<body>
<main>
<h1>16 \u2014 Embedding-modus sammenligning</h1>
<div class="intro">
  Diagnoseverktøy, ikke et designmønster å kopiere. Bygget etter et ekte brudd
  (<a href="https://example.com/tun/issues/39">issue #39</a>,
  15. sept. 2026): en fil viste feilaktig "ingen data funnet" åpnet via SharePoints
  innebygde filforhåndsvisning (enkeltklikk "hurtigvisning" i dokumentbiblioteket
  \u2014 ikke nedlasting, ikke <code>/preview</code> embed.aspx-vieweren fra rad 4).
  <br><br>
  <strong>Slik brukes filen:</strong> last den opp til et SharePoint-bibliotek,
  åpne den på nøyaktig samme måte som forårsaket problemet (ett enkelt klikk,
  ikke "Åpne", ikke nedlasting) \u2014 og les av hvilke ruter under som ble grønne.
  Alle fire ruter viser IDENTISK tekstinnhold; kun embedding-metoden og
  linjeformateringen i JavaScript-en varierer.
  <br><br>
  <strong>Oppdatering, samme kveld:</strong> ruteforsøket under viste at BÅDE rute A
  og B kjører helt fint \u2014 flerlinjes strengsammensetting var aldri årsaken (den
  første, forhastede konklusjonen er tilbakevist, se rad 23 i
  <code>docs/01-tenant-constraints.md</code>). Bisecting av selve sideskallet
  (ikke dataene) fant tre andre, uavhengige, faktisk bekreftede årsaker \u2014 se rad
  24\u201326 i samme dokument: (1) bokstavelig "&lt;script"-tekst hvor som helst i
  filen, selv i en kommentar, slår av all skriptkjøring for hele siden, (2)
  fragment-navigasjon (<code>&lt;a href="#..."&gt;</code>) er blokkert i samme
  forhåndsvisning \u2014 bruk et JavaScript-klikklytter i stedet, (3)
  <code>position:sticky</code> og <code>position:fixed</code> er begge upålitelige
  der \u2014 bruk et ikke-rullende app-skall med \u00e9n dedikert rullende beholder i
  stedet. Full historikk: <code>en kollega-kollega/saksrom</code>
  <code>docs/04-hosting-og-dedup.md</code> Trinn E\u2013H.
</div>
<div class="grid">

  <div class="card">
    <span class="tag recommended">Anbefalt mønster</span>
    <h2>A \u2014 Embedded, ettlinjes data</h2>
    <div id="statusA" class="status pending">Laster \u2026</div>
    <div id="panelA" class="content"></div>
  </div>

  <div class="card">
    <span class="tag safe">Mistanke tilbakevist</span>
    <h2>B \u2014 Embedded, flerlinjes strengsammensetting</h2>
    <div id="statusB" class="status pending">Laster \u2026</div>
    <div id="panelB" class="content"></div>
  </div>

  <div class="card">
    <span class="tag safe">Alltid trygt</span>
    <h2>C \u2014 Embedded, ingen JavaScript nødvendig</h2>
    <div class="status ok">&#10003; Statisk HTML \u2014 krever ingen script</div>
    <div class="content">{TEXT}</div>
  </div>

  <div class="card">
    <span class="tag paired">Paired</span>
    <h2>D \u2014 Paired (<code>script src</code>)</h2>
    <div id="statusD" class="status pending">Laster \u2026</div>
    <div id="panelD" class="content"></div>
  </div>

</div>
</main>
<footer>
  Data identisk i alle fire ruter (se <code>build_embedding_comparison_poc.py</code>,
  <code>TEXT</code>-konstanten). Rute D krever <code>paired-data.js</code> i samme mappe
  \u2014 kopier begge filer sammen, aldri bare HTML-filen alene.
</footer>

<!-- ====== Rute A: embedded, ettlinjes ====== -->
<script>window.PANEL_A_DATA = {TEXT_JSON};</script>

<!-- ====== Rute B: embedded, flerlinjes strengsammensetting (den bekreftede risikoen) ====== -->
<script>
window.PANEL_B_DATA =
    {PANEL_B_CONCAT};
</script>

<!-- ====== Rute D: paired, egen fil ====== -->
<script src="./paired-data.js"></script>

<!-- ====== Felles rendering-logikk for alle tre JS-avhengige ruter ====== -->
<script>
function paint(id, statusId, value) {{
  var el = document.getElementById(id);
  var st = document.getElementById(statusId);
  if (value) {{
    el.textContent = value;
    st.textContent = "\\u2713 JavaScript kj\\u00f8rte, data lastet korrekt";
    st.className = "status ok";
  }} else {{
    st.textContent = "\\u2717 Data IKKE lastet \\u2014 samme symptom som issue #39";
    st.className = "status fail";
  }}
}}
paint("panelA", "statusA", window.PANEL_A_DATA);
paint("panelB", "statusB", window.PANEL_B_DATA);
paint("panelD", "statusD", window.PANEL_D_DATA);
</script>
</body>
</html>
"""

(HERE / "embedding-mode-comparison-poc.html").write_text(HTML, encoding="utf-8")
(HERE / "paired-data.js").write_text(PAIRED_DATA_JS, encoding="utf-8")
print("bygget embedding-mode-comparison-poc.html + paired-data.js")
