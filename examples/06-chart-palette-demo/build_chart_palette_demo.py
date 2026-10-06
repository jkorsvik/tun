#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
build_chart_palette_demo.py — generates chart-palette-demo.html

Companion artefact to docs/10-chart-colour-palettes.md. Renders the same
synthetic dataset across the eight Chart.js chart types covered in that
document's §2, with a palette switcher per colour family (qualitative /
sequential / diverging) and a light/dark toggle — so rule C ("no swatch is
reused unmodified between backgrounds") and rule E/F ("measure the contrast
that will actually be on screen") can be checked by eye, and rule E's 3:1
non-text-contrast target is computed LIVE against whichever background is
selected, not asserted in prose.

STATUS: experimental demo, like examples/05-theme-toggle-demo/. Proves the
palettes are usable across chart types. Does NOT decide whether Chart.js
itself replaces the hand-rolled SVG charts in templates/*.html — see
docs/10-chart-colour-palettes.md's opening note. Does NOT pick a winning
palette — that is left to whoever looks at this demo next.

Vendors Chart.js (examples/06-chart-palette-demo/vendor/chart.umd.min.js,
Chart.js 4.4.0 UMD build, ~205 KB) and inlines it at build time, same
never-fetched-by-the-shipped-file rule tools/tokens/*.css already follows.
No CDN reference anywhere in the output — verified by
tools/verify_standalone_core.py's remote-subresource check.

    python3 build_chart_palette_demo.py

No dependencies beyond the standard library.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
REPO_ROOT = HERE.parent.parent
OUT = HERE / "chart-palette-demo.html"

BUILT = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")



def read_vendor(name: str) -> str:
    return (HERE / "vendor" / name).read_text(encoding="utf-8")


sys.path.insert(0, str(REPO_ROOT / "tools"))
import tun_tokens  # noqa: E402

# Tokens come from tools/tun_tokens.py: it resolves which palette is active, validates
# that it defines all eight slots core's theme files consume, and inlines them in the
# documented load order. Core pins the neutral palette deliberately -- see that module's
# palette_path() for why an installed plugin does not win by default.
TOKEN_CSS, TOKEN_SOURCE = tun_tokens.load_token_css(("status-semantic.css", "theme-light.css", "theme-dark.css"))

CHARTJS_JS = read_vendor("chart.umd.min.js")

# ---------------------------------------------------------------------------
# Palette data. Hex values are from the published sources cited in
# docs/10-chart-colour-palettes.md §3 — not re-derived here. Kept as data in
# this build script, not promoted to tools/tokens/, per that document's §4:
# promoting them would imply Chart.js is the decided charting approach for
# production templates, which has not been decided.
# ---------------------------------------------------------------------------
PALETTES = {
    "qualitative": {
        "okabeito": {
            "label": "Okabe\u2013Ito (8)",
            "colors": ["#E69F00", "#56B4E9", "#009E73", "#F0E442",
                       "#0072B2", "#D55E00", "#CC79A7", "#999999"],
            "names": ["Oransje", "Himmelbl\u00e5", "Bl\u00e5gr\u00f8nn", "Gul",
                      "Bl\u00e5", "Vermillion (r\u00f8doransje)", "R\u00f8dlilla",
                      "Gr\u00e5 (erstatning for sort)"],
            "namesOfficial": True,
            "source": "Okabe, M. og Ito, K. (2002/2008), \u00abColor Universal Design (CUD)\u00bb",
            "description": (
                "Utviklet spesifikt for \u00e5 v\u00e6re skillbar for de vanligste formene for "
                "fargesynsvariasjon (protanopi og deuteranopi). Fargenavnene er de originale fra "
                "kildepublikasjonen \u2014 det er den eneste paletten i denne oversikten med offisielt "
                "navngitte farger. Regnes som en de-facto standard i vitenskapelig visualisering."
            ),
        },
        "set2": {
            "label": "ColorBrewer Set2 (8)",
            "colors": ["#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3",
                       "#a6d854", "#ffd92f", "#e5c494", "#b3b3b3"],
            "names": ["Sj\u00f8gr\u00f8nn", "Laksoransje", "Duebl\u00e5", "Orkid\u00e9rosa",
                      "Gulgr\u00f8nn", "Gyllengul", "Lys brun", "Gr\u00e5"],
            "namesOfficial": False,
            "source": "ColorBrewer (Cynthia Brewer, Penn State University), colorbrewer2.org",
            "description": (
                "Opprinnelig utviklet for kartografi, senere adoptert bredt i datavisualisering. "
                "En dempet, kvalitativ palett som ColorBrewer selv klassifiserer som "
                "fargesynsvariasjon-trygg. Fargenavnene under er beskrivende \u2014 ikke offisielle, "
                "kun lagt til for lesbarhet i denne tabellen."
            ),
        },
        "tableau10": {
            "label": "Tableau 10 \u2014 reference only, see caveat",
            "colors": ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
                       "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC"],
            "names": ["Bl\u00e5", "Oransje", "R\u00f8d", "Teal", "Gr\u00f8nn",
                      "Gul", "Lilla", "Rosa", "Brun", "Gr\u00e5"],
            "namesOfficial": False,
            "source": "Tableau Software, standardpalett fra 2016-oppdateringen",
            "description": (
                "Mye brukt og gjenkjennelig i forretningsrapportering, men \u2014 i motsetning til de "
                "to andre kategoriske palettene her \u2014 ikke systematisk par-for-par testet for "
                "fargesynsvariasjon av opphavspart. Tatt med som referansepunkt for sammenligning, "
                "ikke som anbefalt standard. Fargenavn er beskrivende, ikke offisielle."
            ),
        },
    },
    "sequential": {
        "viridis": {
            "label": "Viridis (8)",
            "colors": ["#440154", "#46327E", "#365C8D", "#277F8E",
                       "#1FA187", "#4AC16D", "#A0DA39", "#FDE725"],
            "names": ["M\u00f8rk fiolett (0 %)", "Indigo (14 %)", "Bl\u00e5 (29 %)",
                      "Petroleumsbl\u00e5 (43 %)", "Gr\u00f8nn-turkis (57 %)", "Gr\u00f8nn (71 %)",
                      "Limegr\u00f8nn (86 %)", "Gul (100 %)"],
            "namesOfficial": False,
            "source": "matplotlib (St\u00e9fan van der Walt og Nathaniel Smith, 2015), evenly sampled",
            "description": (
                "Perseptuelt jevnt fargekart utviklet som fargesynsvariasjon-trygg erstatning for "
                "regnb\u00f8ge-fargekart i vitenskapelig visualisering, n\u00e5 standard i store deler av "
                "det \u00f8kosystemet. Fargene under er 8 jevnt fordelte punkter p\u00e5 et kontinuerlig "
                "fargekart, ikke diskrete kategorier \u2014 navnene angir posisjon i prosent."
            ),
        },
        "cividis": {
            "label": "Cividis (9)",
            "colors": ["#00204D", "#05366E", "#404D6B", "#60646F", "#7C7B78",
                       "#9B9477", "#BCAF6F", "#E0CB5D", "#FFEA46"],
            "names": ["Marinebl\u00e5 (0 %)", "M\u00f8rk st\u00e5lbl\u00e5 (12,5 %)", "Gr\u00e5bl\u00e5 (25 %)",
                      "Bl\u00e5gr\u00e5 (37,5 %)", "Gr\u00e5, n\u00f8ytral (50 %)", "Gr\u00e5beige (62,5 %)",
                      "Oliv-gul (75 %)", "Gyllen (87,5 %)", "Gul (100 %)"],
            "namesOfficial": False,
            "source": "Nu\u00f1ez, Anderton og Renslow (2018)",
            "description": (
                "Optimalisert spesifikt for de to vanligste formene for fargesynsvariasjon ved \u00e5 "
                "begrense fargekartet til en luminansbane som oppfattes likt uavhengig av "
                "fargesynstype. Den strengeste sekvensielle kandidaten i denne oversikten \u2014 "
                "f\u00f8rstevalg der fargesynsvariasjon er et hardt krav, ikke bare en anbefaling."
            ),
        },
    },
    "diverging": {
        "prgn": {
            "label": "PRGn (7) \u2014 purple\u2013green",
            "colors": ["#762a83", "#af8dc3", "#e7d4e8", "#f7f7f7",
                       "#d9f0d3", "#7fbf7b", "#1b7837"],
            "names": ["M\u00f8rk lilla", "Lilla", "Lys lilla", "Nullpunkt (n\u00e6r hvit)",
                      "Lys gr\u00f8nn", "Gr\u00f8nn", "M\u00f8rk gr\u00f8nn"],
            "namesOfficial": False,
            "source": "ColorBrewer, colorbrewer2.org",
            "description": (
                "Divergerende palett med lilla i \u00e9n ende og gr\u00f8nn i den andre, n\u00e6r-hvitt "
                "nullpunkt i midten. Klassifisert som fargesynsvariasjon-trygg av ColorBrewer. "
                "Merk: gr\u00f8nn-enden kan visuelt kollidere med statusfargen for positivt "
                "(Moss, se tools/tokens/status-semantic.css) \u2014 se PuOr som alternativ."
            ),
        },
        "puor": {
            "label": "PuOr (7) \u2014 purple\u2013orange",
            "colors": ["#b35806", "#e08214", "#fdb863", "#f7f7f7",
                       "#b2abd2", "#8073ac", "#542788"],
            "names": ["M\u00f8rk oransje", "Oransje", "Lys oransje", "Nullpunkt (n\u00e6r hvit)",
                      "Lys lilla", "Lilla", "M\u00f8rk lilla"],
            "namesOfficial": False,
            "source": "ColorBrewer, colorbrewer2.org",
            "description": (
                "Divergerende palett med oransje i \u00e9n ende og lilla i den andre. Alternativ til "
                "PRGn uten gr\u00f8nn \u2014 relevant der gr\u00f8nn er reservert til status/merkevare "
                "(se docs/09-usability-and-navigation-principles.md \u00a73). Ogs\u00e5 klassifisert som "
                "fargesynsvariasjon-trygg av ColorBrewer."
            ),
        },
    },
}

CAT_LABELS = ["Nord", "S\u00f8r", "\u00d8st", "Vest", "Midt", "Innlandet"]
CAT_VALUES = [42, 78, 55, 90, 33, 61]
CAT_SERIES_LABELS = ["Q1", "Q2", "Q3", "Q4", "Q5"]
CAT_SERIES = {
    "Nord":      [10, 14, 18, 22, 19],
    "S\u00f8r":       [30, 28, 35, 40, 44],
    "\u00d8st":       [15, 20, 17, 25, 30],
    "Vest":      [50, 48, 55, 60, 58],
    "Midt":      [8, 12, 10, 15, 20],
    "Innlandet": [25, 22, 28, 26, 31],
}
CAT_SCATTER = {
    "Nord":      [[10, 10], [12, 13], [9, 8], [11, 12], [13, 9]],
    "S\u00f8r":       [[30, 15], [32, 18], [28, 13], [31, 16], [29, 19]],
    "\u00d8st":       [[20, 30], [22, 33], [18, 28], [21, 31], [19, 34]],
    "Vest":      [[40, 35], [42, 38], [38, 33], [41, 36], [39, 39]],
    "Midt":      [[15, 45], [17, 48], [13, 43], [16, 46], [14, 49]],
    "Innlandet": [[35, 5],  [37, 8],  [33, 3],  [36, 6],  [34, 9]],
}

DATA_JSON = json.dumps({
    "palettes": PALETTES,
    "catLabels": CAT_LABELS,
    "catValues": CAT_VALUES,
    "catSeriesLabels": CAT_SERIES_LABELS,
    "catSeries": CAT_SERIES,
    "catScatter": CAT_SCATTER,
}, ensure_ascii=False)

print(f"chart.js vendor size: {len(CHARTJS_JS)} bytes")

# ---------------------------------------------------------------------------
# HTML template. Plain string with __PLACEHOLDER__ tokens, not an f-string —
# the embedded CSS/JS below is full of literal { } and an f-string would
# need every one of them doubled (see interactive-standalone-html skill's
# "Vanlige fallgruver" for the same trap). .replace() avoids that entirely.
# ---------------------------------------------------------------------------
TEMPLATE = """<!DOCTYPE html>
<!--
  Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
  This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
  or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
  COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
  under terms of your choice, provided the Origin Notice is preserved.
  SPDX-License-Identifier: AGPL-3.0-or-later
-->
<html lang="nb">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chart.js fargepalett-demo</title>
<!--
  Chart.js fargepalett-demo
  PROVENANCE
    Source data : none — synthetic regional counts, not a real report
    Built       : __BUILT__
    Companion to: docs/10-chart-colour-palettes.md
    Built by    : RAIWork
    Repo        : tun
    Made with   : Tún — tun.community
    Generator   : examples/06-chart-palette-demo/build_chart_palette_demo.py
    Chart.js    : 4.4.0 UMD, vendored in vendor/chart.umd.min.js, inlined below
  STATUS: experimental demo, NOT a production template, and does NOT decide
  whether Chart.js replaces the hand-rolled SVG charts in templates/*.html.
  See docs/10-chart-colour-palettes.md for what this does and does not prove.
  Tier 1, STANDALONE: fully self-contained, no server, no CDN.
-->
<style>
__TOKEN_CSS__

  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,Arial,system-ui,sans-serif;
    font-size:1rem;line-height:1.5;transition:background .15s,color .15s}
  header{background:var(--brand-dark);color:var(--palette-on-dark);
    padding:1.25rem 2rem;display:flex;justify-content:space-between;align-items:flex-start;gap:1rem}
  header h1{margin:0;font-size:1.4rem;line-height:1.9rem;font-weight:500}
  header .meta{opacity:.85;font-size:.8rem;line-height:1.4rem;margin-top:.4rem;max-width:44rem}
  #theme-toggle{padding:.5rem .9rem;border:1px solid var(--palette-on-dark);border-radius:.25rem;
    background:transparent;color:var(--palette-on-dark);font-family:inherit;font-size:.875rem;
    cursor:pointer;white-space:nowrap;flex-shrink:0}
  #theme-toggle:hover{background:var(--palette-on-dark);color:var(--brand-dark)}
  #theme-toggle:focus-visible{outline:2px solid var(--palette-accent-light);outline-offset:2px}
  .tabs{display:flex;gap:.5rem;background:var(--panel);padding:.75rem 2rem;border-bottom:1px solid var(--line);
    flex-wrap:wrap}
  .tabbtn{padding:.5rem .9rem;border:1px solid var(--line);border-radius:.25rem;
    background:var(--bg);font-family:inherit;font-size:.875rem;cursor:pointer;color:var(--ink)}
  .tabbtn:hover{border-color:var(--brand);color:var(--brand)}
  .tabbtn.active{background:var(--brand);color:var(--palette-surface);border-color:var(--brand)}
  .tabbtn:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
  main{padding:1.5rem 2rem;max-width:74rem;margin:0 auto}
  .tabpage{display:none}
  .tabpage.active{display:block}
  .palette-row{display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;margin:0 0 .5rem}
  .palette-row label{font-size:.85rem;color:var(--muted)}
  .palette-row select{font-family:inherit;font-size:.875rem;padding:.35rem .5rem;border:1px solid var(--line);
    border-radius:.25rem;background:var(--bg);color:var(--ink)}
  .palette-desc{font-size:.85rem;color:var(--ink);max-width:56rem;margin:0 0 .75rem;line-height:1.55}
  .palette-desc .src{color:var(--muted);font-size:.78rem;display:block;margin-top:.2rem}
  .rule-note{font-size:.8rem;color:var(--muted);margin:0 0 1rem;max-width:56rem}
  .ref-table{width:100%;border-collapse:collapse;margin:0 0 1.75rem;font-size:.85rem}
  .ref-table caption{text-align:left;font-weight:600;color:var(--ink);padding:0 0 .35rem;font-size:.95rem}
  .ref-table th,.ref-table td{padding:.4rem .6rem;border-bottom:1px solid var(--line);text-align:left}
  .ref-table th{color:var(--muted);font-weight:600;font-size:.75rem;text-transform:uppercase;letter-spacing:.03em}
  .ref-table td.num{font-variant-numeric:tabular-nums}
  .ref-swatch{display:inline-block;width:1.1rem;height:1.1rem;border-radius:.2rem;
    border:1px solid rgba(128,128,128,.4);vertical-align:middle;margin-right:.4rem}
  .ref-hex{font-family:ui-monospace,Consolas,monospace;font-size:.8rem;color:var(--muted)}
  .ref-pass{color:var(--ok);font-weight:600}
  .ref-fail{color:var(--bad);font-weight:600}
  .ref-caveat{background:var(--panel);border-left:.2rem solid var(--palette-accent);padding:.5rem .75rem;
    font-size:.8rem;color:var(--muted);margin:0 0 1.75rem;max-width:56rem}
  .swatches{display:flex;flex-wrap:wrap;gap:.5rem;margin:0 0 1.25rem}
  .swatch{display:flex;align-items:center;gap:.4rem;background:var(--panel);border:1px solid var(--line);
    border-radius:.25rem;padding:.3rem .55rem;font-size:.78rem;font-variant-numeric:tabular-nums}
  .sw-box{width:1rem;height:1rem;border-radius:.2rem;border:1px solid rgba(128,128,128,.4);display:inline-block;
    flex-shrink:0}
  .sw-ratio.pass{color:var(--ok);font-weight:600}
  .sw-ratio.fail{color:var(--bad);font-weight:600}
  .chart-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1.25rem;margin-bottom:1rem}
  .chart-card{background:var(--panel);border:1px solid var(--line);border-radius:.375rem;padding:.75rem}
  .chart-card h3{margin:0 0 .5rem;font-size:.85rem;font-weight:600;color:var(--muted);
    text-transform:uppercase;letter-spacing:.03em}
  .chart-card .wrap{position:relative;height:250px}
  .chart-card canvas{width:100%!important;height:100%!important}
  .note{background:var(--panel);border:1px dashed var(--line);border-radius:.25rem;padding:1rem;
    font-size:.875rem;color:var(--muted);margin-top:1.5rem}
  .note code{color:var(--ink)}
  .about p{max-width:52rem}
  .about code{background:var(--panel);padding:.1rem .3rem;border-radius:.2rem}
  @media print{.tabs,#theme-toggle{display:none}}
</style>
</head>
<body>
<header>
  <div>
    <h1>Chart.js fargepalett-demo</h1>
    <div class="meta">Samme syntetiske datasett i 8 diagramtyper &middot; sammenligner tre trygge
      palettfamilier &middot; kontrasttall under er beregnet live mot bakgrunnen som faktisk vises,
      ikke pastet inn. Se docs/10-chart-colour-palettes.md.</div>
  </div>
  <button type="button" id="theme-toggle" aria-pressed="false">&#127769; M&oslash;rkt tema</button>
</header>
<nav class="tabs">
  <button class="tabbtn" data-tab="categorical">Kategorisk</button>
  <button class="tabbtn" data-tab="sequential">Sekvensiell</button>
  <button class="tabbtn" data-tab="diverging">Divergerende</button>
  <button class="tabbtn" data-tab="palettes">Paletter (full oversikt)</button>
  <button class="tabbtn" data-tab="about">Om denne demoen</button>
</nav>
<main>

  <section id="tab-categorical" class="tabpage">
    <div class="palette-row">
      <label for="sel-qual">Palett:</label>
      <select id="sel-qual">
        <option value="okabeito">Okabe&ndash;Ito (8)</option>
        <option value="set2">ColorBrewer Set2 (8)</option>
        <option value="tableau10">Tableau 10 &mdash; referanse, se forbehold</option>
      </select>
    </div>
    <p class="palette-desc" id="qual-desc"></p>
    <p class="rule-note">Regel B: trygg maks er lavere for sirkel/doughnut/polar area (~6, farge er
      eneste kanal) enn for bar/line (~6&ndash;8). Regel D: bar/pie/doughnut/polar har kant rundt
      hvert segment; scatter har punktform som ekstra kanal i tillegg til farge.</p>
    <div class="swatches" id="cat-swatches"></div>
    <div class="chart-grid">
      <div class="chart-card"><h3>Bar</h3><div class="wrap"><canvas id="c-bar"></canvas></div></div>
      <div class="chart-card"><h3>Pie</h3><div class="wrap"><canvas id="c-pie"></canvas></div></div>
      <div class="chart-card"><h3>Doughnut</h3><div class="wrap"><canvas id="c-doughnut"></canvas></div></div>
      <div class="chart-card"><h3>Polar area</h3><div class="wrap"><canvas id="c-polar"></canvas></div></div>
      <div class="chart-card"><h3>Line (6 serier)</h3><div class="wrap"><canvas id="c-line"></canvas></div></div>
      <div class="chart-card"><h3>Area (6 serier, fylt)</h3><div class="wrap"><canvas id="c-area"></canvas></div></div>
      <div class="chart-card"><h3>Radar (6 serier)</h3><div class="wrap"><canvas id="c-radar"></canvas></div></div>
      <div class="chart-card"><h3>Scatter (6 grupper + punktform)</h3><div class="wrap"><canvas id="c-scatter"></canvas></div></div>
      <div class="chart-card"><h3>Bubble (farge=kategori, radius=verdi)</h3><div class="wrap"><canvas id="c-bubble"></canvas></div></div>
    </div>
  </section>

  <section id="tab-sequential" class="tabpage">
    <div class="palette-row">
      <label for="sel-seq">Palett:</label>
      <select id="sel-seq">
        <option value="viridis">Viridis (8)</option>
        <option value="cividis">Cividis (9) &mdash; strengest for fargesvakhet</option>
      </select>
    </div>
    <p class="palette-desc" id="seq-desc"></p>
    <p class="rule-note">Regel A: sekvensiell brukes for ordnet, kontinuerlig data i &eacute;n retning
      &mdash; syntetiske &laquo;intensitet&raquo;-bins her, ikke reelle m&aring;linger.</p>
    <div class="swatches" id="seq-swatches"></div>
    <div class="chart-grid">
      <div class="chart-card"><h3>Bar &mdash; ordnede bins</h3><div class="wrap"><canvas id="c-seq"></canvas></div></div>
    </div>
  </section>

  <section id="tab-diverging" class="tabpage">
    <div class="palette-row">
      <label for="sel-div">Palett:</label>
      <select id="sel-div">
        <option value="prgn">PRGn (7) &mdash; lilla&ndash;gr&oslash;nn</option>
        <option value="puor">PuOr (7) &mdash; lilla&ndash;oransje</option>
      </select>
    </div>
    <p class="palette-desc" id="div-desc"></p>
    <p class="rule-note">Bevisst utelatt: r&oslash;d&ndash;gr&oslash;nn divergerende skala (f.eks. RdYlGn)
      &mdash; en interpolert skala g&aring;r gjennom nettopp det fargeparet som feiler for deuteranopi,
      selv om endepunktene hver for seg er trygge. Se docs/10 &sect;3.</p>
    <div class="swatches" id="div-swatches"></div>
    <div class="chart-grid">
      <div class="chart-card"><h3>Bar &mdash; avvik fra nullpunkt</h3><div class="wrap"><canvas id="c-div"></canvas></div></div>
    </div>
  </section>

  <section id="tab-palettes" class="tabpage">
    <h2>Paletter &mdash; full oversikt</h2>
    <p class="palette-desc">Referansetabell for alle farger i alle syv paletter over: navn, hex-kode
      og m&aring;lt kontrast mot b&aring;de lys og m&oslash;rk bakgrunn (uavhengig av hvilket tema
      siden st&aring;r i n&aring;). Ment for utskrift/deling med de som skal gi tilbakemelding p&aring;
      selve fargevalgene, ikke bare de som ser p&aring; diagrammene.</p>
    <div id="palette-reference"></div>
  </section>

  <section id="tab-about" class="tabpage about">
    <h2>Om denne demoen</h2>
    <p>F&oslash;lger opp <code>docs/10-chart-colour-palettes.md</code>. Beviser tre ting, ikke mer:
      at de tre palettfamiliene (kategorisk / sekvensiell / divergerende) fra det dokumentet fungerer
      p&aring; tvers av alle &aring;tte diagramtyper Chart.js st&oslash;tter, at kontrastregnestykket i
      regel E/F (WCAG 2.2, 1.4.11 &mdash; 3:1 for grafiske elementer) kan regnes ut live i nettleseren
      i stedet for p&aring;st&aring;s, og at lys/m&oslash;rk-bryteren fra
      <code>examples/05-theme-toggle-demo/</code> fungerer sammen med chart-farger, ikke bare
      sidekrom.</p>
    <p>Avgj&oslash;r <strong>ikke</strong>: om Chart.js erstatter de handskrevne SVG-diagrammene i
      <code>templates/single-file-dashboard.html</code> og <code>templates/cube-dashboard.html</code>
      &mdash; m&aring;lt, ikke antatt: de bruker i dag egne <code>barChart()</code>/<code>lineChart()</code>
      SVG-funksjoner, ikke Chart.js. Avgj&oslash;r heller ikke hvilken palett som blir standard &mdash;
      denne siden er for &aring; sammenligne kandidater, ikke for &aring; kr&oslash;ne en vinner.</p>
    <p>&Aring;pne punkter (se docs/10 &sect;&laquo;Open items&raquo;): ingen ekte
      fargesynsvariasjon-simulator er kj&oslash;rt mot dette enn&aring; &mdash; 3:1-kontrast er
      n&oslash;dvendig, ikke tilstrekkelig, for at to kategorier skal forbli visuelt skilt under
      deuteranopi/protanopi/tritanopi. Tableau 10 st&aring;r som referanse, ikke anbefaling, av
      samme grunn.</p>
    <p><strong>Paletter (full oversikt)</strong>-fanen er lagt til for &aring; kunne deles med de som
      skal gi tilbakemelding p&aring; selve fargevalgene uten at de m&aring; tolke diagrammene
      f&oslash;rst: navn, hex og m&aring;lt
      kontrast mot begge bakgrunner for alle syv paletter, samlet p&aring; &eacute;n side.</p>
    <div class="note">
      Byggetidspunkt: __BUILT__ &middot; generert av <code>build_chart_palette_demo.py</code>,
      aldri h&aring;ndskrevet &middot; Chart.js 4.4.0 vendret i <code>vendor/</code> og inlinet ved bygg,
      aldri lastet av denne filen ved &aring;pning.
    </div>
  </section>

</main>
<script>
__CHARTJS_JS__
</script>
<script>
  var DATA = __DATA_JSON__;
  var STATE = { qual: "okabeito", seq: "viridis", div: "prgn", theme: "light", tab: "categorical" };
  var CHARTS = {};
  var LIGHT_INK = "#000000", LIGHT_LINE = "#ebebeb";
  var DARK_INK = "#FFF8EE", DARK_LINE = "#33496B";  // same neutral slate as --line in theme-dark.css
  var LIGHT_BORDER = "#FFFFFF", DARK_BORDER = "#101828";
  var POINT_STYLES = ["circle", "triangle", "rect", "rectRot", "star", "cross"];

  function killChart(id) {
    if (CHARTS[id]) { CHARTS[id].destroy(); delete CHARTS[id]; }
  }

  function hexToRgb(hex) {
    var h = hex.replace("#", "");
    if (h.length === 3) { h = h[0]+h[0]+h[1]+h[1]+h[2]+h[2]; }
    var num = parseInt(h.substring(0,6), 16);
    return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
  }

  function relLuminance(rgb) {
    function lin(c) { c = c / 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }
    return 0.2126 * lin(rgb.r) + 0.7152 * lin(rgb.g) + 0.0722 * lin(rgb.b);
  }

  function contrastRatio(hex, bgHex) {
    var L1 = relLuminance(hexToRgb(hex));
    var L2 = relLuminance(hexToRgb(bgHex));
    var lighter = Math.max(L1, L2), darker = Math.min(L1, L2);
    return (lighter + 0.05) / (darker + 0.05);
  }

  function currentBgHex() {
    return STATE.theme === "dark" ? "#1B2A4A" : "#FFFFFF"; // --eksempel-navy / --eksempel-white, see theme-*.css
  }

  function renderSwatchStrip(containerId, colors, labels) {
    var el = document.getElementById(containerId);
    if (!el) return;
    var bg = currentBgHex();
    var html = "";
    for (var i = 0; i < colors.length; i++) {
      var ratio = contrastRatio(colors[i], bg);
      var pass = ratio >= 3;
      var label = labels && labels[i] !== undefined ? labels[i] : (i + 1);
      html += '<span class="swatch"><span class="sw-box" style="background:' + colors[i] + '"></span>' +
        '<span>' + label + '</span>' +
        '<span class="sw-ratio ' + (pass ? "pass" : "fail") + '">' + ratio.toFixed(2) + ':1 mot bg ' +
        (pass ? "\\u2713" : "\\u2717") + '</span></span>';
    }
    el.innerHTML = html;
  }

  function applyChartDefaults() {
    var ink = STATE.theme === "dark" ? DARK_INK : LIGHT_INK;
    var line = STATE.theme === "dark" ? DARK_LINE : LIGHT_LINE;
    Chart.defaults.color = ink;
    Chart.defaults.borderColor = line;
    Chart.defaults.font.family = "Arial, system-ui, sans-serif";
  }

  function commonOpts(title) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: { display: true, text: title },
        legend: { position: "bottom", labels: { boxWidth: 11, font: { size: 11 } } }
      }
    };
  }

  function segBorder() { return STATE.theme === "dark" ? DARK_BORDER : LIGHT_BORDER; }

  // Chart.js's radial scale (used by radar/polarArea) draws its tick labels on an
  // opaque light backdrop by default, regardless of page theme — invisible against a
  // light backdrop on a dark card unless overridden per theme. Not covered by
  // Chart.defaults.color/borderColor (those only reach cartesian axes + legend/title).
  function radialScaleOpts() {
    var ink = STATE.theme === "dark" ? DARK_INK : LIGHT_INK;
    var line = STATE.theme === "dark" ? DARK_LINE : LIGHT_LINE;
    return { r: {
      ticks: { color: ink, backdropColor: "transparent" },
      grid: { color: line },
      angleLines: { color: line },
      pointLabels: { color: ink }
    } };
  }

  function buildCategorical() {
    var pal = DATA.palettes.qualitative[STATE.qual].colors;
    var labels = DATA.catLabels, values = DATA.catValues;
    var colorFor = function(i) { return pal[i % pal.length]; };

    killChart("c-bar");
    CHARTS["c-bar"] = new Chart(document.getElementById("c-bar"), {
      type: "bar",
      data: { labels: labels, datasets: [{ label: "Verdi", data: values,
        backgroundColor: labels.map(function(_, i) { return colorFor(i); }),
        borderColor: labels.map(function(_, i) { return colorFor(i); }), borderWidth: 1 }] },
      options: commonOpts("Bar")
    });

    killChart("c-pie");
    CHARTS["c-pie"] = new Chart(document.getElementById("c-pie"), {
      type: "pie",
      data: { labels: labels, datasets: [{ data: values,
        backgroundColor: labels.map(function(_, i) { return colorFor(i); }),
        borderColor: segBorder(), borderWidth: 2 }] },
      options: commonOpts("Pie")
    });

    killChart("c-doughnut");
    CHARTS["c-doughnut"] = new Chart(document.getElementById("c-doughnut"), {
      type: "doughnut",
      data: { labels: labels, datasets: [{ data: values,
        backgroundColor: labels.map(function(_, i) { return colorFor(i); }),
        borderColor: segBorder(), borderWidth: 2 }] },
      options: commonOpts("Doughnut")
    });

    killChart("c-polar");
    CHARTS["c-polar"] = new Chart(document.getElementById("c-polar"), {
      type: "polarArea",
      data: { labels: labels, datasets: [{ data: values,
        backgroundColor: labels.map(function(_, i) { return colorFor(i) + "CC"; }),
        borderColor: labels.map(function(_, i) { return colorFor(i); }) }] },
      options: Object.assign(commonOpts("Polar area"), { scales: radialScaleOpts() })
    });

    var lineDatasets = labels.map(function(region, i) {
      return { label: region, data: DATA.catSeries[region], borderColor: colorFor(i),
        backgroundColor: colorFor(i) + "55", fill: false, tension: 0.25, pointRadius: 3 };
    });
    killChart("c-line");
    CHARTS["c-line"] = new Chart(document.getElementById("c-line"), {
      type: "line", data: { labels: DATA.catSeriesLabels, datasets: lineDatasets },
      options: commonOpts("Line (6 serier)")
    });

    var areaDatasets = labels.map(function(region, i) {
      return { label: region, data: DATA.catSeries[region], borderColor: colorFor(i),
        backgroundColor: colorFor(i) + "55", fill: true, tension: 0.25, pointRadius: 0 };
    });
    killChart("c-area");
    CHARTS["c-area"] = new Chart(document.getElementById("c-area"), {
      type: "line", data: { labels: DATA.catSeriesLabels, datasets: areaDatasets },
      options: commonOpts("Area (6 serier, fylt)")
    });

    var radarDatasets = labels.map(function(region, i) {
      return { label: region, data: DATA.catSeries[region], borderColor: colorFor(i),
        backgroundColor: colorFor(i) + "33", pointRadius: 2 };
    });
    killChart("c-radar");
    CHARTS["c-radar"] = new Chart(document.getElementById("c-radar"), {
      type: "radar", data: { labels: DATA.catSeriesLabels, datasets: radarDatasets },
      options: Object.assign(commonOpts("Radar (6 serier)"), { scales: radialScaleOpts() })
    });

    var scatterDatasets = labels.map(function(region, i) {
      return { label: region,
        data: DATA.catScatter[region].map(function(p) { return { x: p[0], y: p[1] }; }),
        backgroundColor: colorFor(i), pointStyle: POINT_STYLES[i % POINT_STYLES.length], pointRadius: 6 };
    });
    killChart("c-scatter");
    CHARTS["c-scatter"] = new Chart(document.getElementById("c-scatter"), {
      type: "scatter", data: { datasets: scatterDatasets }, options: commonOpts("Scatter (farge + punktform)")
    });

    var bubbleDatasets = labels.map(function(region, i) {
      return { label: region, data: [{ x: (i + 1) * 10, y: values[i] / 2, r: values[i] / 6 }],
        backgroundColor: colorFor(i) + "BB" };
    });
    killChart("c-bubble");
    CHARTS["c-bubble"] = new Chart(document.getElementById("c-bubble"), {
      type: "bubble", data: { datasets: bubbleDatasets }, options: commonOpts("Bubble (farge=kategori, radius=verdi)")
    });

    renderSwatchStrip("cat-swatches", pal.slice(0, labels.length), labels);
  }

  function buildSequential() {
    var pal = DATA.palettes.sequential[STATE.seq].colors;
    var n = pal.length;
    var labels = [], values = [];
    for (var i = 0; i < n; i++) {
      labels.push(String(i + 1));
      values.push(Math.round(10 + i * (90 / (n - 1))));
    }
    killChart("c-seq");
    CHARTS["c-seq"] = new Chart(document.getElementById("c-seq"), {
      type: "bar",
      data: { labels: labels, datasets: [{ label: "Intensitet (syntetisk)", data: values,
        backgroundColor: pal, borderColor: pal, borderWidth: 1 }] },
      options: commonOpts("Sekvensiell \\u2014 ordnede bins")
    });
    renderSwatchStrip("seq-swatches", pal, labels);
  }

  function buildDiverging() {
    var pal = DATA.palettes.diverging[STATE.div].colors;
    var n = pal.length;
    var half = Math.floor(n / 2);
    var labels = [], values = [];
    for (var i = 0; i < n; i++) {
      var d = i - half;
      labels.push((d > 0 ? "+" : "") + d);
      values.push(d * 10);
    }
    killChart("c-div");
    CHARTS["c-div"] = new Chart(document.getElementById("c-div"), {
      type: "bar",
      data: { labels: labels, datasets: [{ label: "Avvik fra nullpunkt (syntetisk)", data: values,
        backgroundColor: pal, borderColor: pal, borderWidth: 1 }] },
      options: commonOpts("Divergerende \\u2014 avvik fra basislinje")
    });
    renderSwatchStrip("div-swatches", pal, labels);
  }

  function buildActiveTab() {
    if (STATE.tab === "categorical") buildCategorical();
    else if (STATE.tab === "sequential") buildSequential();
    else if (STATE.tab === "diverging") buildDiverging();
    else if (STATE.tab === "palettes") buildPaletteReference();
  }

  function paletteDescHtml(fam, key) {
    var p = DATA.palettes[fam][key];
    var caveat = p.namesOfficial ? "" : ' <span class="src">(fargenavn er beskrivende, ikke offisielle)</span>';
    return "<strong>" + p.label + "</strong> \\u2014 " + p.description +
      '<span class="src">Kilde: ' + p.source + "." + caveat + "</span>";
  }

  function updateDesc(elId, fam, key) {
    var el = document.getElementById(elId);
    if (el) el.innerHTML = paletteDescHtml(fam, key);
  }

  var PALETTE_REF_BUILT = false;
  function buildPaletteReference() {
    if (PALETTE_REF_BUILT) return;
    PALETTE_REF_BUILT = true;
    var LIGHT_BG = "#FFFFFF", DARK_BG = "#1B2A4A"; // --eksempel-white / --eksempel-navy
    var FAM_LABEL = { qualitative: "Kategorisk", sequential: "Sekvensiell", diverging: "Divergerende" };
    var out = "";
    ["qualitative", "sequential", "diverging"].forEach(function(fam) {
      out += "<h3>" + FAM_LABEL[fam] + "</h3>";
      Object.keys(DATA.palettes[fam]).forEach(function(key) {
        var p = DATA.palettes[fam][key];
        out += '<p class="palette-desc">' + paletteDescHtml(fam, key) + "</p>";
        out += '<table class="ref-table"><caption>' + p.label + '</caption><thead><tr>' +
          "<th>Farge</th><th>Navn</th><th>Hex</th>" +
          "<th>Kontrast mot lys bg (#FFFFFF)</th><th>Kontrast mot m\\u00f8rk bg (#1B2A4A)</th>" +
          "</tr></thead><tbody>";
        p.colors.forEach(function(hex, i) {
          var rL = contrastRatio(hex, LIGHT_BG), rD = contrastRatio(hex, DARK_BG);
          var passL = rL >= 3, passD = rD >= 3;
          out += "<tr><td><span class=\\"ref-swatch\\" style=\\"background:" + hex + "\\"></span></td>" +
            "<td>" + (p.names ? p.names[i] : "\\u2014") + "</td>" +
            '<td class="ref-hex">' + hex.toUpperCase() + "</td>" +
            '<td class="num ' + (passL ? "ref-pass" : "ref-fail") + '">' + rL.toFixed(2) + ":1 " +
            (passL ? "\\u2713" : "\\u2717") + "</td>" +
            '<td class="num ' + (passD ? "ref-pass" : "ref-fail") + '">' + rD.toFixed(2) + ":1 " +
            (passD ? "\\u2713" : "\\u2717") + "</td></tr>";
        });
        out += "</tbody></table>";
      });
    });
    out += '<p class="ref-caveat">Kontrasttallene er WCAG 2.2-forholdstall (relativ luminans), regnet ut ' +
      "av samme funksjon som brukes p\\u00e5 de andre fanene \\u2014 ikke limt inn manuelt. 3:1 er WCAG " +
      "1.4.11-grensen for grafiske elementer (ikke tekst). En verdi under grensen betyr at nettopp den " +
      "fargen \\u2014 mot nettopp den bakgrunnen \\u2014 b\\u00f8r unng\\u00e5s for tynne linjer/sm\\u00e5 " +
      "punkter, ikke at hele paletten er ubrukelig der.</p>";
    document.getElementById("palette-reference").innerHTML = out;
  }

  function showTab(id, btn) {
    document.querySelectorAll(".tabpage").forEach(function(p) { p.classList.remove("active"); });
    document.querySelectorAll(".tabbtn").forEach(function(b) { b.classList.remove("active"); });
    document.getElementById("tab-" + id).classList.add("active");
    if (btn) btn.classList.add("active");
    STATE.tab = id;
    buildActiveTab();
  }

  document.querySelectorAll(".tabbtn").forEach(function(btn, i) {
    if (i === 0) btn.classList.add("active");
    btn.addEventListener("click", function() { showTab(btn.dataset.tab, btn); });
  });
  document.getElementById("tab-categorical").classList.add("active");

  document.getElementById("sel-qual").addEventListener("change", function(e) {
    STATE.qual = e.target.value; updateDesc("qual-desc", "qualitative", STATE.qual); buildCategorical();
  });
  document.getElementById("sel-seq").addEventListener("change", function(e) {
    STATE.seq = e.target.value; updateDesc("seq-desc", "sequential", STATE.seq); buildSequential();
  });
  document.getElementById("sel-div").addEventListener("change", function(e) {
    STATE.div = e.target.value; updateDesc("div-desc", "diverging", STATE.div); buildDiverging();
  });
  updateDesc("qual-desc", "qualitative", STATE.qual);
  updateDesc("seq-desc", "sequential", STATE.seq);
  updateDesc("div-desc", "diverging", STATE.div);


  (function themeToggle() {
    var KEY = "chart-palette-demo:theme";
    var btn = document.getElementById("theme-toggle");
    function apply(theme) {
      STATE.theme = theme;
      document.documentElement.setAttribute("data-theme", theme);
      btn.textContent = theme === "dark" ? "\\u2600\\ufe0f Lyst tema" : "\\ud83c\\udf19 M\\u00f8rkt tema";
      btn.setAttribute("aria-pressed", String(theme === "dark"));
      applyChartDefaults();
      buildActiveTab();
    }
    var saved = "light";
    try { saved = localStorage.getItem(KEY) || "light"; } catch (e) { /* file:// may block storage */ }
    document.documentElement.setAttribute("data-theme", saved);
    STATE.theme = saved;
    btn.textContent = saved === "dark" ? "\\u2600\\ufe0f Lyst tema" : "\\ud83c\\udf19 M\\u00f8rkt tema";
    btn.setAttribute("aria-pressed", String(saved === "dark"));
    btn.addEventListener("click", function() {
      var next = STATE.theme === "dark" ? "light" : "dark";
      apply(next);
      try { localStorage.setItem(KEY, next); } catch (e) { /* see docs/09 open item */ }
    });
  })();

  applyChartDefaults();
  buildCategorical();
</script>
</body>
</html>
"""

html = (TEMPLATE
        .replace("__TOKEN_CSS__", TOKEN_CSS)
        .replace("__CHARTJS_JS__", CHARTJS_JS)
        .replace("__DATA_JSON__", DATA_JSON)
        .replace("__BUILT__", BUILT))

OUT.write_text(html, encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
print("next: python3 ../../tools/verify_standalone_core.py " + str(OUT))
