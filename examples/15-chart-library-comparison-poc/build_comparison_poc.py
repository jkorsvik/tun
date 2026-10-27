#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
build_comparison_poc.py — generates chart-library-comparison-poc.html

Follow-up to issue #30, but the opposite starting assumption from
examples/13/14: THIS page requires JavaScript, on purpose — it exists to put
three charting approaches side by side and let the difference actually be
seen, not just described:

  1. Chart.js (JavaScript, <canvas>) — the same vendored build examples/06 uses.
  2. Hand-rolled (pure CSS/SVG, no JS) — the exact techniques proven in
     examples/14-chart-emulation-nojs-poc/ (ported here, not re-invented).
  3. Matplotlib (Python, build-time only) — static SVGs written once by
     generate_matplotlib_charts.py, inlined here as plain text. The shipped
     HTML never imports matplotlib; only the SVG text it already produced.

Same six-region synthetic dataset and the same Okabe–Ito palette in all three,
defined once in shared_data.py, so "side by side" is an honest comparison and
not three different inputs dressed up to look comparable.

Sections on the page (see README.md for the full write-up of each):
  1. Bar (vertical) and Donut, three ways, same data.
  2. A feature/gap comparison table across the three approaches.
  3. Filtering: a real JS-driven filter next to a real CSS-only
     pre-rendered-variants filter, so the trade-off is visible, not asserted.
  4. Matplotlib "snacks": a Norway choropleth (six real fylker standing in for
     the six synthetic regions — see the mapping table for exactly which),
     and a print/PDF export button (window.print() + @media print), tested to
     actually capture canvas + CSS + inlined SVG together.

    python3 generate_matplotlib_charts.py   # only if mpl-svg/ needs regenerating
    python3 build_comparison_poc.py

No dependencies beyond the standard library — matplotlib is only needed by
generate_matplotlib_charts.py, a separate, optional step (see pyproject.toml's
"charts" extra).
"""
from __future__ import annotations

import datetime
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
REPO_ROOT = HERE.parent.parent
OUT = HERE / "chart-library-comparison-poc.html"

sys.path.insert(0, str(HERE))
from shared_data import LABELS, PALETTE, REGION_TO_FYLKE, VALUES, color_for

BUILT = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")



sys.path.insert(0, str(REPO_ROOT / "tools"))
import tun_tokens  # noqa: E402

# Tokens come from tools/tun_tokens.py: it resolves which palette is active, validates
# that it defines all eight slots core's theme files consume, and inlines them in the
# documented load order. Core pins the neutral palette deliberately -- see that module's
# palette_path() for why an installed plugin does not win by default.
TOKEN_CSS, TOKEN_SOURCE = tun_tokens.load_token_css(("status-semantic.css", "theme-light.css"))
CHARTJS_JS = (HERE / "vendor" / "chart.umd.min.js").read_text(encoding="utf-8")


_SVG_COUNT = [0]


def read_mpl_svg(name: str) -> str:
    text = (HERE / "mpl-svg" / name).read_text(encoding="utf-8")
    # Drop the XML/DOCTYPE preamble matplotlib writes — this SVG is being
    # inlined into an existing HTML document, not served standalone.
    if "<svg" in text:
        text = "<svg" + text.split("<svg", 1)[1]
    # matplotlib numbers its internals from 1 in every file: figure_1, axes_1, patch_1.
    # Three charts inlined into one page therefore define id="figure_1" three times, and
    # a duplicate id silently breaks every url(#...) reference and aria-labelledby that
    # points at one of them. `verify_a11y.py` found 40 of them. Prefix per chart.
    _SVG_COUNT[0] += 1
    prefix = f"mpl{_SVG_COUNT[0]}-"
    ids = set(re.findall(r'id="([^"]+)"', text))
    for old_id in sorted(ids, key=len, reverse=True):
        text = text.replace(f'id="{old_id}"', f'id="{prefix}{old_id}"')
        text = text.replace(f'url(#{old_id})', f'url(#{prefix}{old_id})')
        text = text.replace(f'href="#{old_id}"', f'href="#{prefix}{old_id}"')
    return text


def fmt(n: float) -> str:
    s = f"{n:.2f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


# ---------------------------------------------------------------------------
# Hand-rolled CSS chart builders — ported verbatim from
# examples/14-chart-emulation-nojs-poc/build_chart_emulation_poc.py, not
# re-derived. Kept local to this example rather than imported across example
# folders, matching the rest of examples/ (each folder is self-contained so
# one can change without silently affecting another already-shipped demo).
# ---------------------------------------------------------------------------
def legend_html(labels: list[str]) -> str:
    chips = "".join(
        f'<span class="legend-chip"><span class="legend-swatch" style="background:{color_for(i)}"></span>{lab}</span>'
        for i, lab in enumerate(labels)
    )
    return f'<div class="legend">{chips}</div>'


def build_handrolled_bar_vertical(labels: list[str], values: list[int]) -> str:
    maxv = max(values) if values else 1
    cols = []
    for i, (lab, val) in enumerate(zip(labels, values)):
        pct = val / maxv * 100
        color = color_for(LABELS.index(lab))
        cols.append(
            f'<div class="vbar-col"><span class="vbar-value">{val}</span>'
            f'<div class="vbar-fill" style="height:{fmt(pct)}%;background:{color}"></div>'
            f'<span class="vbar-label">{lab}</span></div>'
        )
    return f'<div class="vbar-chart">{"".join(cols)}</div>'


def build_handrolled_donut(labels: list[str], values: list[int]) -> str:
    total = sum(values) or 1
    stops = []
    acc = 0.0
    for i, (lab, val) in enumerate(zip(labels, values)):
        color = color_for(LABELS.index(lab))
        start = acc / total * 100
        acc += val
        end = acc / total * 100
        stops.append(f"{color} {fmt(start)}% {fmt(end)}%")
    gradient = ", ".join(stops)
    return (
        '<div class="pie-wrap"><div class="pie-circle" style="background:conic-gradient('
        + gradient + ')"><div class="doughnut-hole"></div></div></div>' + legend_html(labels)
    )


# ---------------------------------------------------------------------------
# Filter definitions shared by the JS and CSS filter demos in section 3 — same
# three options, same underlying data, so the two techniques are compared on
# identical ground, not on different filters that happen to look similar.
# ---------------------------------------------------------------------------
AVG = sum(VALUES) / len(VALUES)
FILTERS = {
    "all": ("Alle regioner", LABELS, VALUES),
    "over": (
        f"Over snittet ({AVG:.0f})",
        [l for l, v in zip(LABELS, VALUES) if v > AVG],
        [v for v in VALUES if v > AVG],
    ),
    "under": (
        f"Under snittet ({AVG:.0f})",
        [l for l, v in zip(LABELS, VALUES) if v <= AVG],
        [v for v in VALUES if v <= AVG],
    ),
}

STYLE = """
""" + TOKEN_CSS + """

*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"Eksempel AS",-apple-system,BlinkMacSystemFont,Arial,system-ui,sans-serif;
  font-size:1rem;line-height:1.55}
header{background:var(--brand-dark);color:var(--palette-on-dark);padding:1.5rem 2rem}
header h1{margin:0;font-size:1.5rem;font-weight:500}
header .meta{opacity:.85;font-size:.85rem;line-height:1.5;margin-top:.5rem;max-width:56rem}
header code{background:rgba(255,255,255,.12);padding:.05rem .3rem;border-radius:.2rem}
nav.section-nav{display:flex;flex-wrap:wrap;gap:1.2rem;background:var(--panel);
  padding:.75rem 2rem;border-bottom:1px solid var(--line);font-size:.85rem;position:sticky;top:0;z-index:5}
/* A nav item is a touch target on a phone, so it is 44 px tall itself rather than
   relying on the bar's padding to lift it over the floor (docs/11 section 1). */
nav.section-nav a{color:var(--brand);text-decoration:none;font-weight:600;
  display:inline-flex;align-items:center;min-height:2.75rem}
nav.section-nav a:hover{text-decoration:underline}
main{padding:1.5rem 2rem;max-width:80rem;margin:0 auto}
section{margin-bottom:3rem;padding-top:.5rem;scroll-margin-top:3.2rem}
section h2{border-bottom:2px solid var(--line);padding-bottom:.4rem}
section > p.intro{max-width:60rem;color:var(--muted)}
h3.chart-type-heading{margin:1.5rem 0 .6rem;font-size:1rem}
.compare-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1.25rem;margin-bottom:1rem}
.compare-card{background:var(--panel);border:1px solid var(--line);border-radius:.375rem;padding:1rem}
.compare-card h4{margin:0 0 .3rem;font-size:.85rem;font-weight:600}
.compare-card .impl-tag{display:inline-block;font-size:.68rem;padding:.1rem .4rem;border-radius:.2rem;
  margin-bottom:.6rem;font-weight:600;text-transform:uppercase;letter-spacing:.02em}
.impl-tag.js{background:#e3edfb;color:#1a4b8c}
.impl-tag.handrolled{background:#e3f5ea;color:#0a6b39}
.impl-tag.mpl{background:#fdeee0;color:#9a4b00}
.compare-card canvas{max-width:100%}
.chart-canvas-wrap{position:relative;height:190px}
.chart-canvas-wrap canvas{width:100% !important;height:100% !important}
.compare-card svg{max-width:100%;height:auto;display:block;margin:0 auto}
/* hand-rolled chart primitives, ported from examples/14 */
.legend{display:flex;flex-wrap:wrap;gap:.4rem .8rem;margin-top:.6rem;font-size:.78rem;color:var(--muted)}
.legend-chip{display:inline-flex;align-items:center;gap:.3rem}
.legend-swatch{width:.7rem;height:.7rem;border-radius:.15rem;display:inline-block;flex-shrink:0}
.vbar-chart{display:flex;align-items:flex-end;gap:.7rem;height:170px;padding:0 .25rem}
.vbar-col{display:flex;flex-direction:column;align-items:center;justify-content:flex-end;flex:1;height:100%;min-width:0}
.vbar-fill{width:65%;border-radius:.25rem .25rem 0 0;min-height:2px}
.vbar-value{font-size:.72rem;margin-bottom:.25rem;font-variant-numeric:tabular-nums}
.vbar-label{font-size:.72rem;color:var(--muted);margin-top:.35rem;text-align:center;white-space:normal;line-height:1.2}
.pie-wrap{display:flex;justify-content:center;padding:.5rem 0}
.pie-circle{width:150px;height:150px;border-radius:50%;position:relative}
.doughnut-hole{position:absolute;inset:28px;border-radius:50%;background:var(--panel)}
/* section 2 table */
table.compare-table{width:100%;border-collapse:collapse;font-size:.85rem;margin-bottom:1rem}
table.compare-table th,table.compare-table td{padding:.55rem .7rem;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
table.compare-table th{background:var(--panel);font-size:.78rem;text-transform:uppercase;letter-spacing:.02em;color:var(--muted)}
table.compare-table td.yes{color:var(--ok)}
table.compare-table td.no{color:var(--bad)}
table.compare-table td.partial{color:#9a6b00}
/* Measured in WebKit at 390 px and 768 px (2026-10-24): the native select renders
   150 x 22 px there, because WebKit ignores padding, border and min-height on a
   native control. The 44 px touch floor is docs/11 section 1, and the cube hits it the
   same way: drop the native look, draw the box and the chevron ourselves. */
.filter-block select{appearance:none;-webkit-appearance:none;
  min-height:2.75rem;padding:.5rem 2.25rem .5rem .75rem;
  background-image:linear-gradient(45deg,transparent 50%,currentColor 50%),
    linear-gradient(135deg,currentColor 50%,transparent 50%);
  background-position:calc(100% - 1.1rem) 50%,calc(100% - .75rem) 50%;
  background-size:.35rem .35rem,.35rem .35rem;background-repeat:no-repeat}
/* The comparison table is 628 px of content in a 390 px viewport: it scrolls inside
   its own box rather than pushing the page sideways (docs/11 forbids content clipped
   or hidden by the viewport, not content a reader can scroll). */
table.compare-table{display:block;overflow-x:auto;max-width:100%}
@media (max-width:40rem){
  main{padding:1.25rem 1rem}
  nav.section-nav{padding:.6rem 1rem;gap:.8rem}
  header{padding:1.25rem 1rem}
}
/* section 3 filter demos */
.filter-compare{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:1.5rem}
.filter-block{background:var(--panel);border:1px solid var(--line);border-radius:.375rem;padding:1.2rem}
.filter-block h3{margin-top:0}
.filter-block select{font-family:inherit;font-size:.875rem;padding:.4rem .6rem;border:1px solid var(--line);
  border-radius:.25rem;background:var(--bg);color:var(--ink);margin-bottom:1rem}
.css-filter-tabs{display:flex;gap:.4rem;margin-bottom:1rem;flex-wrap:wrap}
.css-filter-tabs label{padding:.35rem .7rem;border:1px solid var(--line);border-radius:1rem;font-size:.8rem;
  cursor:pointer;user-select:none}
.cf-radio{position:absolute;opacity:0;pointer-events:none}
.cf-radio:focus-visible + label{outline:2px solid var(--brand);outline-offset:1px}
#cf-all:checked ~ .css-filter-tabs label[for="cf-all"],
#cf-over:checked ~ .css-filter-tabs label[for="cf-over"],
#cf-under:checked ~ .css-filter-tabs label[for="cf-under"]{background:var(--brand);color:#fff;border-color:var(--brand)}
.cf-variant{display:none}
#cf-all:checked ~ #variant-all{display:block}
#cf-over:checked ~ #variant-over{display:block}
#cf-under:checked ~ #variant-under{display:block}
.note{background:var(--panel);border:1px dashed var(--line);border-radius:.25rem;padding:1rem;
  font-size:.875rem;color:var(--muted);margin-top:1rem}
.note code{color:var(--ink)}
/* section 4 */
.map-layout{display:flex;gap:2rem;flex-wrap:wrap;align-items:flex-start}
.map-layout svg{max-width:280px;height:auto}
table.mapping-table{border-collapse:collapse;font-size:.82rem}
table.mapping-table th,table.mapping-table td{padding:.4rem .6rem;border-bottom:1px solid var(--line);text-align:left}
#export-pdf-btn{font-family:inherit;font-size:.9rem;padding:.6rem 1.1rem;border-radius:.3rem;border:none;
  background:var(--brand);color:#fff;cursor:pointer;margin:.5rem 0;
  /* WebKit computes a padded button at 36.2 px here, below the 44 px touch floor. */
  min-height:2.75rem}
#export-pdf-btn:hover{filter:brightness(1.08)}
@media print{
  nav.section-nav,#export-pdf-btn,.filter-block select,.css-filter-tabs{display:none !important}
  * {-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;color-adjust:exact !important}
  section{margin-bottom:1.2rem;page-break-inside:avoid}
  .compare-row{page-break-inside:avoid}
  .cf-variant{display:block !important}
}
"""

# ---------------------------------------------------------------------------
# Section 1 — same two chart types, three implementations, same data/palette.
# ---------------------------------------------------------------------------
def compare_row(chart_type: str, canvas_id: str, handrolled_html: str, mpl_svg_name: str) -> str:
    return f"""
  <div class="compare-row">
    <div class="compare-card">
      <span class="impl-tag js">JavaScript</span>
      <h4>Chart.js</h4>
      <div class="chart-canvas-wrap"><canvas id="{canvas_id}" role="img" aria-label="{chart_type} — Chart.js"></canvas></div>
    </div>
    <div class="compare-card">
      <span class="impl-tag handrolled">Ingen JS</span>
      <h4>Håndrullet (CSS/SVG)</h4>
      {handrolled_html}
    </div>
    <div class="compare-card">
      <span class="impl-tag mpl">Byggetid, ingen JS</span>
      <h4>Matplotlib (Python)</h4>
      {read_mpl_svg(mpl_svg_name)}
    </div>
  </div>
"""


SECTION_1 = f"""
<section id="sec-1">
  <h2>1. Samme diagram, tre implementasjoner</h2>
  <p class="intro">Samme seks regioner, samme tall, samme Okabe&ndash;Ito-palett
    (<code>shared_data.py</code>) &mdash; kjørt gjennom tre helt forskjellige
    teknikker. Chart.js tegner til et <code>&lt;canvas&gt;</code> med JavaScript som
    kjører i din nettleser akkurat nå. Den håndrullede versjonen er nøyaktig samme
    CSS/SVG-teknikk som ble bevist i <code>examples/14-chart-emulation-nojs-poc/</code>
    &mdash; ingen JavaScript i det hele tatt. Matplotlib-versjonen er en statisk SVG
    generert av Python <em>før</em> denne siden noensinne ble åpnet &mdash; se
    <code>generate_matplotlib_charts.py</code>.</p>

  <h3 class="chart-type-heading">Søyle (vertikal)</h3>
  {compare_row("bar-vertical", "cjs-bar-vertical", build_handrolled_bar_vertical(LABELS, VALUES), "bar-vertical.svg")}

  <h3 class="chart-type-heading">Donut</h3>
  {compare_row("donut", "cjs-donut", build_handrolled_donut(LABELS, VALUES), "donut.svg")}
</section>
"""

SECTION_2 = """
<section id="sec-2">
  <h2>2. Sammenligningstabell &mdash; hva er faktisk testet og dokumentert så langt</h2>
  <p class="intro">Ikke en generell påstand om hva bibliotekene <em>kan</em> gjøre i teorien
    &mdash; en oversikt over hva som er bygget og verifisert i dette repoet
    (<code>examples/06</code>, <code>examples/13</code>, <code>examples/14</code>, denne
    siden), pluss egenskaper undersøkt i research men ikke selv bygget her (markert).</p>
  <table class="compare-table">
    <thead><tr><th>Egenskap</th><th>Chart.js (JS)</th><th>Håndrullet (CSS/SVG)</th><th>Matplotlib (Python)</th></tr></thead>
    <tbody>
      <tr><td>Krever JavaScript i nettleseren</td>
        <td class="no">Ja, alltid</td>
        <td class="yes">Nei, aldri</td>
        <td class="yes">Nei &mdash; kun ved bygging, ikke i nettleseren</td></tr>
      <tr><td>Diagramtyper testet i dette repoet</td>
        <td>9 (<code>examples/06</code>)</td>
        <td>12 (<code>examples/14</code>) &mdash; inkl. scatter/bubble via SVG</td>
        <td>2 + Norgeskart (denne siden) &mdash; ikke bredt testet ennå</td></tr>
      <tr><td>Spredning/boble (vilkårlig punktplassering)</td>
        <td class="yes">Ja</td>
        <td class="partial">Kun via SVG, ikke ren CSS &mdash; se <code>examples/14</code></td>
        <td class="yes">Ja (samme prinsipp som håndrullet SVG, men modent bibliotek)</td></tr>
      <tr><td>Hover-tooltip / zoom</td>
        <td class="yes">Ja, innebygd</td>
        <td class="no">Nei &mdash; statisk</td>
        <td class="no">Nei &mdash; statisk (mpld3 kan bygge bro, ikke testet her)</td></tr>
      <tr><td>Live filtrering uten ny sidevisning</td>
        <td class="yes">Ja &mdash; se seksjon 3</td>
        <td class="partial">Kun forhåndsberegnede varianter &mdash; se seksjon 3</td>
        <td class="no">Nei &mdash; krever ny byggekjøring</td></tr>
      <tr><td>Filstørrelse lagt til per side</td>
        <td>~205 KB (vendret <code>chart.umd.min.js</code>, delt av alle diagrammer)</td>
        <td>~0 &mdash; bare CSS/HTML som allerede lastes</td>
        <td>Noen KB per diagram (SVG-tekst), men et Norgeskart med ekte grenser kan bli 100&ndash;150&nbsp;KB</td></tr>
      <tr><td>Byggeavhengighet</td>
        <td>Ingen (vendret JS-fil sjekket inn i repoet)</td>
        <td>Ingen (Python standardbibliotek)</td>
        <td>Matplotlib må installeres for å <em>regenerere</em> SVG-ene (<code>uv sync --extra charts</code>) &mdash; selve sidebygget trenger den ikke</td></tr>
      <tr><td>Tekstgjengivelse i SVG</td>
        <td>N/A (canvas, ikke SVG)</td>
        <td>Ekte <code>&lt;text&gt;</code>, arver sidens CSS-font</td>
        <td>Valgfritt: ekte <code>&lt;text&gt;</code> (denne siden) <em>eller</em> tekst-som-vektorbane (fontuavhengig, standardvalg i Matplotlib) &mdash; se README</td></tr>
      <tr><td>Fargekilde</td>
        <td>Håndkopierte hex-verdier (<code>shared_data.py</code>)</td>
        <td>Håndkopierte hex-verdier (samme fil)</td>
        <td>Samme håndkopierte verdier her, men Matplotlib har Viridis/Cividis <em>som referanseimplementasjon</em> &mdash; ikke utnyttet i denne demoen ennå</td></tr>
      <tr><td>Lisens</td>
        <td>MIT</td>
        <td>Ingen &mdash; vår egen kode</td>
        <td>PSF-basert, BSD-kompatibel, ikke copyleft</td></tr>
      <tr><td>Tilgjengelighet (skjermleser)</td>
        <td class="partial">Krever manuelt ARIA-arbeid, ikke gjort i <code>examples/06</code></td>
        <td class="partial"><code>role="img"</code>/<code>aria-label</code> lagt til i <code>examples/14</code>, ikke en full løsning</td>
        <td class="no">Ikke undersøkt her</td></tr>
    </tbody>
  </table>
  <p class="note">Radene merket <span class="partial">gult</span> er ikke et blankt nei/ja &mdash;
    se cellenes forklaring. Denne tabellen oppdateres etter hvert som flere diagramtyper og
    egenskaper faktisk testes, ikke ved å anta at et bibliotek som løste ett tilfelle løser alle.</p>
</section>
"""

def _filter_variant_html(key: str) -> str:
    _, labels, values = FILTERS[key]
    return f'<div class="cf-variant" id="variant-{key}">{build_handrolled_bar_vertical(labels, values)}</div>'


SECTION_3 = f"""
<section id="sec-3">
  <h2>3. Filtrering: JavaScript vs. CSS &mdash; designforslag</h2>
  <p class="intro">Samme tre filtervalg, samme data, to helt forskjellige teknikker.
    Bytt filter i begge boksene og sammenlign hva som faktisk skjer.</p>
  <div class="filter-compare">

    <div class="filter-block">
      <h3>JavaScript-filtrering</h3>
      <select id="js-filter-select" aria-label="Filtrer regioner">
        <option value="all">Alle regioner</option>
        <option value="over">Over snittet ({AVG:.0f})</option>
        <option value="under">Under snittet ({AVG:.0f})</option>
      </select>
      <div class="chart-canvas-wrap"><canvas id="cjs-filter-bar" role="img" aria-label="Filtrert søylediagram — Chart.js"></canvas></div>
      <p class="note">Ett datasett i minnet. JavaScript endrer <code>chart.data</code> og
        kaller <code>chart.update()</code> &mdash; ingen ny markup lages, chart-objektet
        tegner seg selv på nytt. Skalerer til hvilket som helst antall filterverdier eller
        en fritekst-terskel brukeren selv skriver inn.</p>
    </div>

    <div class="filter-block">
      <h3>CSS-filtrering (design forslag, ingen JS)</h3>
      <input class="cf-radio" type="radio" name="cssfilter" id="cf-all" checked>
      <input class="cf-radio" type="radio" name="cssfilter" id="cf-over">
      <input class="cf-radio" type="radio" name="cssfilter" id="cf-under">
      <div class="css-filter-tabs">
        <label for="cf-all">Alle regioner</label>
        <label for="cf-over">Over snittet ({AVG:.0f})</label>
        <label for="cf-under">Under snittet ({AVG:.0f})</label>
      </div>
      {_filter_variant_html("all")}
      {_filter_variant_html("over")}
      {_filter_variant_html("under")}
      <p class="note">Tre helt ferdige diagrammer ligger allerede i HTML-en fra byggetidspunktet
        (<code>build_comparison_poc.py</code> kaller <code>build_handrolled_bar_vertical()</code>
        tre ganger). Radioknappen bytter bare hvilket som <em>vises</em>, med ren CSS
        (<code>:checked ~</code>). Null JavaScript, men skalerer kun til et antall
        forhåndskjente filterverdier &mdash; en fritekst-terskel brukeren skriver inn er
        <strong>ikke</strong> mulig med denne teknikken, siden hver variant må eksistere
        ferdig bygget i markupen.</p>
    </div>

  </div>
  <p class="note"><strong>Når velge hva:</strong> CSS-varianten passer når filtervalgene er få
    og kjent på forhånd (som her: tre faste kategorier) &mdash; da er den et ekte null-JS-alternativ,
    jf. <code>examples/13</code>. Den vokser lineært i filstørrelse med antall varianter
    (N ganger dataene, N ganger markupen), så den passer dårlig til mange eller
    kontinuerlige filterverdier (en dato-glidebryter, et fritekstsøk) &mdash; der er
    JavaScript-varianten det eneste reelle alternativet.</p>
</section>
"""

def _mapping_table_rows() -> str:
    rows = []
    for i, lab in enumerate(LABELS):
        fylke_display = REGION_TO_FYLKE[lab].split(" - ")[0]
        rows.append(
            f'<tr><td><span class="legend-swatch" style="background:{color_for(i)};display:inline-block;'
            f'width:.7rem;height:.7rem;border-radius:.15rem;margin-right:.4rem"></span>{lab}</td>'
            f"<td>{fylke_display}</td><td>{VALUES[i]}</td></tr>"
        )
    return "".join(rows)


SECTION_4 = f"""
<section id="sec-4">
  <h2>4. Matplotlib-snacks</h2>

  <h3 class="chart-type-heading">Norgeskart (choropleth)</h3>
  <p class="intro">Samme seks tall som resten av siden, farget over seks <strong>ekte</strong>
    norske fylkesgrenser &mdash; en diagramtype ingen av de andre to tilnærmingene har vist
    her ennå. Se README.md for full ærlighet om hvor grensen mellom syntetisk og ekte går.</p>
  <div class="map-layout">
    <div>{read_mpl_svg("norway-map.svg")}</div>
    <table class="mapping-table">
      <thead><tr><th>Syntetisk region</th><th>Ekte fylke brukt</th><th>Verdi</th></tr></thead>
      <tbody>{_mapping_table_rows()}</tbody>
    </table>
  </div>
  <p class="note"><strong>Ærlighet om denne koblingen:</strong> "Nord/Sør/Øst/Vest/Midt/Innlandet"
    er de samme syntetiske, oppdiktede etikettene som er brukt i hele denne demo-serien siden
    <code>examples/06</code> &mdash; de er ikke ekte norske landsdeler. For dette kartet er hver
    én koblet til ett faktisk fylke som navnemessig eller geografisk passer rimelig godt
    (Nord&rarr;Nordland, Vest&rarr;Vestland, Midt&rarr;Trøndelag, Innlandet&rarr;Innlandet er
    de tydeligste; Sør&rarr;Agder og Øst&rarr;Østfold er rimelige, ikke unike valg). Kartet
    viser bare disse seks av Norges 15 fylker &mdash; resten av landet er bevisst tomt, ikke
    manglende data.</p>

  <h3 class="chart-type-heading">Eksporter til PDF</h3>
  <p class="intro">Én knapp, ingen ekstra bibliotek (ikke html2canvas/jsPDF) &mdash; bruker
    nettleserens egen utskriftsmotor (<code>window.print()</code>) pluss
    <code>@media print</code>-regler som skjuler kontroller og tvinger frem bakgrunnsfarger
    utskriftsmotoren ellers dropper som standard. Fanger opp alle tre diagramtypene fra
    seksjon 1 (canvas rasteriseres som det står akkurat da; håndrullet og Matplotlib er
    allerede vektor), og viser alle tre filtervariantene fra seksjon 3 samtidig i utskriften
    &mdash; ikke bare den som var valgt på skjermen.</p>
  <button type="button" id="export-pdf-btn" onclick="window.print()">Eksporter til PDF</button>
  <p class="note">Alternativet vurdert og valgt bort: <code>html2canvas</code> + <code>jsPDF</code>
    (to ekstra JS-biblioteker) kan lage en nedlastbar <code>.pdf</code>-fil direkte uten
    utskriftsdialogen, men er mer skjørt (kjente problemer med gradienter og
    "tainted canvas") og trekker inn vekt denne siden ikke trenger &mdash; se README.md.</p>
</section>
"""

import json as _json

DATA_JSON = _json.dumps({
    "labels": LABELS,
    "values": VALUES,
    "palette": PALETTE,
    "filters": {k: {"label": v[0], "labels": v[1], "values": v[2]} for k, v in FILTERS.items()},
}, ensure_ascii=False)

SCRIPT = """
<script>
""" + CHARTJS_JS + """
</script>
<script>
  var DATA = """ + DATA_JSON + """;

  function colorsFor(labels) {
    return labels.map(function(lab) { return DATA.palette[DATA.labels.indexOf(lab)]; });
  }

  // --- Section 1: Chart.js versions of the same two chart types ---
  new Chart(document.getElementById("cjs-bar-vertical"), {
    type: "bar",
    data: { labels: DATA.labels, datasets: [{ data: DATA.values, backgroundColor: colorsFor(DATA.labels) }] },
    options: { responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { display: false } } }
  });

  new Chart(document.getElementById("cjs-donut"), {
    type: "doughnut",
    data: { labels: DATA.labels, datasets: [{ data: DATA.values, backgroundColor: colorsFor(DATA.labels), borderColor: "#fff", borderWidth: 2 }] },
    options: { responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 10 } } } } }
  });

  // --- Section 3: JavaScript-driven filter — one Chart.js instance, data swapped in place ---
  var filterChart = new Chart(document.getElementById("cjs-filter-bar"), {
    type: "bar",
    data: { labels: DATA.filters.all.labels,
      datasets: [{ data: DATA.filters.all.values, backgroundColor: colorsFor(DATA.filters.all.labels) }] },
    options: { responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } },
      animation: { duration: 300 } }
  });

  document.getElementById("js-filter-select").addEventListener("change", function(e) {
    var f = DATA.filters[e.target.value];
    filterChart.data.labels = f.labels;
    filterChart.data.datasets[0].data = f.values;
    filterChart.data.datasets[0].backgroundColor = colorsFor(f.labels);
    filterChart.update();
  });
</script>
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="nb">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chart-bibliotek sammenligning &mdash; Chart.js vs. h&aring;ndrullet vs. Matplotlib</title>
<!--
  Chart-bibliotek sammenligning: Chart.js vs. h\u00e5ndrullet CSS/SVG vs. Matplotlib
  PROVENANCE
    Source data : none — same synthetic regional counts as examples/06/13/14
    Built       : __BUILT__
    Companion to: issue #30, examples/06-chart-palette-demo/,
                  examples/13-js-free-standalone-poc/, examples/14-chart-emulation-nojs-poc/
    Built by    : RAIWork
    Repo        : tun
    Generator   : examples/15-chart-library-comparison-poc/build_comparison_poc.py
  STATUS: exploratory/diagnostic POC. Unlike examples/13/14, this page DOES require
  JavaScript — see module docstring for why: it exists to compare a JS approach
  against two no-JS approaches side by side, not to prove a no-JS pattern itself.
  Tier 1, STANDALONE: fully self-contained, no server, no CDN.
-->
<style>
__STYLE__
</style>
</head>
<body>
<header>
  <h1>Chart-bibliotek sammenligning: Chart.js vs. h&aring;ndrullet vs. Matplotlib</h1>
  <div class="meta">Denne siden krever JavaScript &mdash; med vilje, i motsetning til
    <code>examples/13</code>/<code>14</code>. Se de fire seksjonene under, eller
    hopp direkte via lenkene.</div>
</header>
<nav class="section-nav">
  <a href="#sec-1">1. Samme diagram, tre implementasjoner</a>
  <a href="#sec-2">2. Sammenligningstabell</a>
  <a href="#sec-3">3. Filtrering: JS vs. CSS</a>
  <a href="#sec-4">4. Matplotlib-snacks</a>
</nav>
<main>
__SECTION_1__
__SECTION_2__
__SECTION_3__
__SECTION_4__
</main>
__SCRIPT__
</body>
</html>
"""

html = (
    TEMPLATE.replace("__STYLE__", STYLE)
    .replace("__SECTION_1__", SECTION_1)
    .replace("__SECTION_2__", SECTION_2)
    .replace("__SECTION_3__", SECTION_3)
    .replace("__SECTION_4__", SECTION_4)
    .replace("__SCRIPT__", SCRIPT)
    .replace("__BUILT__", BUILT)
)

OUT.write_text(html, encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
print("next: python3 ../../tools/verify_standalone_core.py " + str(OUT))
