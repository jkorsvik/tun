#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""test_i18n.py: every builder speaks `--lang en|nb`, and `nb` is exactly what it was.

What is checked, and what each check counts (a check that looks at zero items fails):

  1. tables      every strings table has the same keys in nb and en; every {{T:key}} in a
                 template exists; every key is used; no en value holds a character that
                 would break the HTML, JavaScript string or comment it is pasted into.
  2. builds      every builder builds with --lang en and with --lang nb.
  3. nb frozen   the nb build of each case has the sha256 of the build made before the
                 tables existed (clock frozen, so one input gives one file).
  4. en clean    the en build of an English fixture has <html lang="en">, none of the
                 letters æøåÆØÅ, and none of the nb strings from its tables.
  5. mutations   a damaged copy of the tables must be noticed: a deleted en key stops the
                 build, and an nb string or an æ pasted into en is flagged by check 4.
                 Without these, checks 1 and 4 could be satisfied by deleting them.

Stdlib only. Runs the real builders as subprocesses.

    python3 tests/test_i18n.py                    # run the checks
    python3 tests/test_i18n.py --dump DIR [--tools DIR]
                                                  # write the nb builds, print their sha256
                                                  # (--tools: an older copy of tools/, with the
                                                  # declared nb changes applied to its output)
    python3 tests/test_i18n.py --dump-adv [--tools DIR]
                                                  # the same for the section 6 probes
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import i18n  # noqa: E402

CSV = ROOT / "examples" / "01-hello-dashboard" / "salgsdata.csv"
SPEC = ROOT / "examples" / "23-process-diagram" / "tun-workflow.process.txt"
FX_CSV = ROOT / "tests" / "fixtures" / "i18n-sales-en.txt"
FX_SPEC = ROOT / "tests" / "fixtures" / "i18n-process-en.process.txt"
TEMPLATES = ROOT / "templates"

# Runs a builder with the clock frozen, so one input gives one output on any day. Passed
# with -c, so no file lands in the repo. The builders stamp "now" into the provenance block.
SHIM = r"""
import datetime as _dt, runpy, sys
_FIXED = _dt.datetime(2026, 1, 2, 3, 4, 5)
class _Frozen(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return _FIXED.replace(tzinfo=tz) if tz else _FIXED
_dt.datetime = _Frozen
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""

DASH = "build_dashboard.py"
CUBE = "build_cube_dashboard.py"
PROC = "build_process_diagram.py"
DECK = "build_slide_deck.py"      # no input data: the starter deck, so the case has no source

# name -> (builder, input file, arguments, files written, strings tables the page uses).
# {out} is the temp dir, {in} the input as copied there (name kept, mtime fixed).
SALES = ["--title", "Salg per region og produkt 2026", "--dimension", "Produkt",
         "--measure", "Belop", "--time", "Maaned", "--requested-by", "Prosjekteier"]
FX_SALES = ["--title", "Sales by region and product 2026", "--dimension", "Product",
            "--measure", "Amount", "--time", "Month", "--requested-by", "The sales team",
            "--source", "Made-up example data"]
DASH_T = ["single-file-dashboard"]
CUBE_T = ["cube-dashboard"]
FB = ["_feedback-link"]
CASES = {
    # the repo's own examples, Norwegian data: the nb output must not move
    "dash-bundled": (DASH, CSV, SALES + ["--filters", "Region,Produkt,Kanal",
                                         "--out", "{out}/dash-bundled.html"],
                     ["dash-bundled.html"], DASH_T),
    "dash-paired": (DASH, CSV, SALES + ["--filters", "Region,Produkt,Kanal", "--mode", "paired",
                                        "--out", "{out}/paired/dash.html"],
                    ["paired/dash.html", "paired/data.js"], DASH_T),
    "dash-feedback": (DASH, CSV, ["--title", "Salg per region og produkt 2026",
                                  "--dimension", "Produkt", "--measure", "Belop",
                                  "--time", "Maaned", "--requested-by", "Prosjekteier",
                                  "--feedback-to", "hei@example.org",
                                  "--out", "{out}/dash-feedback.html"],
                      ["dash-feedback.html"], DASH_T + FB),
    "cube": (CUBE, CSV, ["--dims", "Region,Produkt,Kanal", "--time", "Maaned",
                         "--measures", "Belop:sum:kr,Antall:sum", "--title", "Transaksjonsoversikt",
                         "--requested-by", "Analyseteamet", "--out", "{out}/cube.html"],
             ["cube.html"], CUBE_T),
    "cube-feedback": (CUBE, CSV, ["--dims", "Region,Produkt", "--time", "Maaned",
                                  "--measures", "Belop:sum,Antall:sum",
                                  "--title", "Transaksjonsoversikt", "--requested-by", "Analyseteamet",
                                  "--feedback-to", "https://example.org/org/repo/issues/new",
                                  "--out", "{out}/cube-feedback.html"],
                      ["cube-feedback.html"], CUBE_T + FB),
    "process": (PROC, SPEC, ["{in}", "--out", "{out}/process.html"], ["process.html"],
                ["process-diagram"]),
    # English fixtures: the en output is judged on these, and nb is frozen on them too
    "fx-dash": (DASH, FX_CSV, FX_SALES + ["--filters", "Region,Product,Channel",
                                          "--feedback-to", "hei@example.org",
                                          "--out", "{out}/fx-dash.html"],
                ["fx-dash.html"], DASH_T + FB),
    "fx-dash-paired": (DASH, FX_CSV, FX_SALES + ["--mode", "paired", "--out", "{out}/fxp/dash.html"],
                       ["fxp/dash.html", "fxp/data.js"], DASH_T),
    "fx-dash-notime": (DASH, FX_CSV, ["--title", "Sales", "--dimension", "Product",
                                      "--measure", "Amount", "--out", "{out}/fx-dash-notime.html"],
                       ["fx-dash-notime.html"], DASH_T),
    "fx-cube": (CUBE, FX_CSV, ["--dims", "Region,Product,Channel", "--time", "Month",
                               "--measures", "Amount:sum:kr,Count:sum", "--title", "Sales",
                               "--requested-by", "The sales team",
                               "--feedback-to", "https://example.org/org/repo/issues/new",
                               "--out", "{out}/fx-cube.html"],
                ["fx-cube.html"], CUBE_T + FB),
    "fx-process": (PROC, FX_SPEC, ["{in}", "--out", "{out}/fx-process.html"], ["fx-process.html"],
                   ["process-diagram"]),
    "fx-deck": (DECK, None, ["--out", "{out}/fx-deck.html"], ["fx-deck.html"],
                ["portable-slide-deck"]),
}

# sha256 of the nb build of each file, made with the export branch's own builders and
# templates (licence headers, neutral palette) as they were on a9cca83, before any strings
# table existed, plus the one deliberate change below. Rebuilt on every run, so a change to
# nb output anywhere (a template, a builder, a table) shows up here as a changed hash.
# The pins were taken from the old builders and proved equal to the builds with the tables:
# `--dump DIR --tools OLD_TOOLS` writes the old output, `--dump DIR` the current nb output.
# The deck had no starter builder: its baseline is the sha256 of templates/portable-slide-deck.html
# on that commit with its placeholders filled the way the builder fills them (title "Portable
# presentasjon", source "none (starter deck)", requested by "not stated", clock frozen).
# The one deliberate change to nb output since then: the dashboard footer and its build
# comment no longer name the tool that ran the builder (decision D7, 2026-10-09). The six
# dashboard hashes below include it. The second deliberate change is accessibility (G08,
# 2026-10-10, found by axe 4.14): --muted in tools/tokens/theme-light.css went from #737373
# (4.46:1 on --panel, under WCAG AA) to #666666 (5.4:1), which also reaches the process
# diagrams; the table wrapper became a focusable named region; and the KPI and chart grids
# stopped forcing a minimum wider than a 375px phone. Applying these pairs to the old
# builders' output must give the current nb output; that is how the pins were proved
# (old builders: the export branch at 1856e1f), and the pairs stay here so the next re-pin
# can be proved the same way.
# The third is the chart size (2026-10-10), described at its pairs. On the same date the
# slide deck changed for axe (landmarks, contrast): its hash is re-pinned with no pair,
# because no probe in section 6 builds a deck.
# The fourth (2026-10-12) is how the dashboard treats an empty measure value, the fifth
# (2026-10-12) the sideways bar chart for long names, and the sixth (2026-10-13) the chart
# redraw when a frame gets its size without a resize event. Each is described at its pairs.
# The seventh (2026-10-13) is the cube's lang attribute, at its pair.
DELIBERATE_NB_CHANGES = [
    (b"Selvstendig dashboard bygget av RAIWork", "Selvstendig dashboard laget med T\u00fan".encode()),
    (b"Tallene er bygget inn i denne filen. Be RAIWork om <code>tun-data</code> for \\u00e5 oppdatere.",
     b"Tallene er bygget inn i denne filen. Oppdater dem med <code>tun-data</code>."),
    (b"Built by    : RAIWork skill `tun-new`", "Built by    : T\u00fan skill `tun-new`".encode()),
    (b"--muted:      #737373;               /* neutral grey: labels, axis text (4.7:1 on white) */",
     b"--muted:      #666666;               /* neutral grey: labels, axis text (5.7:1 on white, 5.4:1 on --panel) */"),
    (b"--muted:      #737373;\n", b"--muted:      #666666;\n"),   # the process builder drops comments
    (b"repeat(auto-fit,minmax(12rem,1fr));", b"repeat(auto-fit,minmax(min(17rem,100%),1fr));"),
    (b".kpi{background:var(--panel);", b".kpi{min-width:0;background:var(--panel);"),
    (b"repeat(auto-fit,minmax(26rem,1fr));gap", b"repeat(auto-fit,minmax(min(26rem,100%),1fr));gap"),
    (b'<h2>Detaljer <span id="rowcount"', b'<h2 id="details-title">Detaljer <span id="rowcount"'),
    (b'<div class="table-wrap"><table id="tbl">',
     b'<div class="table-wrap" role="region" aria-labelledby="details-title" tabindex="0"><table id="tbl">'),
    # Third (2026-10-10): the charts draw in the card's own pixels instead of a fixed
    # 640-wide viewBox, so 11 px axis text no longer shrinks to 6 px on a 375 px phone,
    # and they redraw on resize. Derived from a line diff of the old and new builds;
    # applying these to the old build gives the new one byte for byte.
    (b'\n/* ---------- SVG bar chart -------------------------------------------------- */\n',
     b'\n/* ---------- chart size ----------------------------------------------------- */\n/* Draw in the card\'s own pixels, so 11 px text stays 11 px. A fixed 640-wide\n   viewBox scaled to a 330 px phone card drew it at 6 px. */\nfunction chartSize(svg) {\n  const w = Math.round(svg.getBoundingClientRect().width) || 640;\n  const W = Math.max(280, w), H = 300;\n  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);\n  return [W, H];\n}\n\n/* ---------- SVG bar chart -------------------------------------------------- */\n'),
    (b'function barChart(svgId, data, opts) {\n  const svg = $(svgId); const W = 640, H = 300;\n',
     b'function barChart(svgId, data, opts) {\n  const svg = $(svgId); const [W, H] = chartSize(svg);\n'),
    (b'  svg.innerHTML = "";\n  if (!data.length) { svg.innerHTML = \'<text x="320" y="150" text-anchor="middle" class="axis-label">Ingen data</text>\'; return; }\n',
     b'  svg.innerHTML = "";\n  if (!data.length) { svg.innerHTML = `<text x="${W / 2}" y="150" text-anchor="middle" class="axis-label">Ingen data</text>`; return; }\n'),
    (b'function lineChart(svgId, data) {\n  const svg = $(svgId); const W = 640, H = 300;\n',
     b'function lineChart(svgId, data) {\n  const svg = $(svgId); const [W, H] = chartSize(svg);\n'),
    (b'  svg.innerHTML = "";\n  if (data.length < 2) { svg.innerHTML = \'<text x="320" y="150" text-anchor="middle" class="axis-label">For f\xc3\xa5 punkter</text>\'; return; }\n',
     b'  svg.innerHTML = "";\n  if (data.length < 2) { svg.innerHTML = `<text x="${W / 2}" y="150" text-anchor="middle" class="axis-label">For f\xc3\xa5 punkter</text>`; return; }\n'),
    (b'    svg.appendChild(c);\n    const step = Math.ceil(data.length / 10);\n',
     b'    svg.appendChild(c);\n    const step = Math.ceil(data.length / Math.max(2, Math.floor(iw / 56)));  // 10 labels at 640\n'),
    (b'/* ---------- render loop --------------------------------------------------- */\nfunction render() {\n  const rows = visibleRows();\n  renderKpis(rows);\n',
     b'/* ---------- render loop --------------------------------------------------- */\nfunction renderCharts(rows) {\n'),
    (b'  } else {\n    $("chart2").innerHTML = \'<text x="320" y="150" text-anchor="middle" class="axis-label">Ingen tidskolonne</text>\';\n',
     b'  } else {\n    const [W] = chartSize($("chart2"));\n    $("chart2").innerHTML = `<text x="${W / 2}" y="150" text-anchor="middle" class="axis-label">Ingen tidskolonne</text>`;\n'),
    (b'  }\n  renderTable(rows);\n',
     b'  }\n}\n\nfunction render() {\n  const rows = visibleRows();\n  renderKpis(rows);\n  renderCharts(rows);\n  renderTable(rows);\n'),
    (b'}\n\n(function footNote(){\n',
     b'}\n\n/* Redraw the charts, not the table, when the card changes width. */\nlet resizeFrame = 0;\naddEventListener("resize", () => {\n  cancelAnimationFrame(resizeFrame);\n  resizeFrame = requestAnimationFrame(() => renderCharts(visibleRows()));\n});\n\n(function footNote(){\n'),
    # Same date, the cube dashboard's 560/1120-wide charts drew 10 px text at 3 to 6 px on a
    # phone; they now draw in the panel's pixels and are named for screen readers.
    (b'const esc = s => String(s).replace(/[<>&"]/g, m => ({\'<\':\'&lt;\',\'>\':\'&gt;\',\'&\':\'&amp;\',\'"\':\'&quot;\'}[m]));\nfunction barChart(labels, values, unit){\n  const rowH = 24, W = 560, padL = 118, padR = 66, H = labels.length*rowH + 8;\n',
     b'const esc = s => String(s).replace(/[<>&"]/g, m => ({\'<\':\'&lt;\',\'>\':\'&gt;\',\'&\':\'&amp;\',\'"\':\'&quot;\'}[m]));\n/* Charts draw in their panel\'s own pixels, so 10 px text stays 10 px. A fixed\n   560/1120-wide viewBox scaled to a 330 px phone panel drew it at 3 to 6 px.\n   measureCharts() reads the real widths after a render; boot and resize redraw\n   once when they changed. */\nlet barW = 560, lineW = 1120;\nfunction measureCharts(){\n  const px = sel => { const el = document.querySelector(sel);\n    return el ? Math.round(el.getBoundingClientRect().width) : 0; };\n  const b = px("#charts svg") || barW, l = px("#trend svg") || lineW;\n  const changed = Math.abs(b - barW) > 1 || Math.abs(l - lineW) > 1;\n  barW = Math.max(280, b); lineW = Math.max(280, l);\n  return changed;\n}\nfunction barChart(labels, values, unit, name){\n  const rowH = 24, W = barW, padL = 118, padR = 66, H = labels.length*rowH + 8;\n'),
    (b'  const max = Math.max(...values, 1), bw = W - padL - padR;\n  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img">`;\n',
     b'  const max = Math.max(...values, 1), bw = W - padL - padR;\n  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img" aria-label="${esc(name)}">`;\n'),
    (b'}\nfunction lineChart(labels, values, unit){\n  const W = 1120, H = 230, padL = 62, padR = 14, padT = 12, padB = 34;\n',
     b'}\nfunction lineChart(labels, values, unit, name){\n  const W = lineW, H = 230, padL = 62, padR = 14, padT = 12, padB = 34;\n'),
    (b'  const y = v => H - padB - (v/max)*(H-padT-padB);\n  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img">`;\n',
     b'  const y = v => H - padB - (v/max)*(H-padT-padB);\n  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img" aria-label="${esc(name)}">`;\n'),
    (b'    + `fill="#fff" stroke="var(--gr)" stroke-width="1.8"><title>${esc(labels[i])}: ${fmt(v, unit)}</title></circle>`; });\n  const step = Math.ceil(n/12);\n',
     b'    + `fill="#fff" stroke="var(--gr)" stroke-width="1.8"><title>${esc(labels[i])}: ${fmt(v, unit)}</title></circle>`; });\n  const step = Math.ceil(n / Math.max(2, Math.floor((W-padL-padR)/87)));  // 12 labels at 1120\n'),
    (b'    document.getElementById("trend").innerHTML =\n      lineChart(ti.map(i => META.labels[TIME][i]), ti.map(i => base.out[i]), unit); }\n',
     b'    document.getElementById("trend").innerHTML =\n      lineChart(ti.map(i => META.labels[TIME][i]), ti.map(i => base.out[i]), unit,\n                "Utvikling per " + TIME); }\n'),
    (b'    const [, l, v] = ranked(d);\n    return `<div class="panel"><h2>Per ${esc(d)}</h2>${barChart(l, v, unit)}</div>`; }).join("");\n',
     b'    const [, l, v] = ranked(d);\n    return `<div class="panel"><h2>Per ${esc(d)}</h2>${barChart(l, v, unit, "Per " + d)}</div>`; }).join("");\n'),
    (b'    render();\n',
     b'    render();\n    if (measureCharts()) render();\n    let frame = 0;\n    addEventListener("resize", () => { cancelAnimationFrame(frame);\n      frame = requestAnimationFrame(() => { if (measureCharts()) render(); }); });\n'),
    # Same date, the process diagram (axe): the picture is a group, not an image, once its
    # steps are buttons; the flag badge sits beside its step; label lines are spaced; fills
    # behind ink text name the tint directly, since --bad-bg is now the white chip.
    (b'  --ink:        var(--palette-ink);\n  --muted:      #737373;\n',
     b'  --ink:        var(--palette-ink);\n  --muted:      #666666;\n'),
    (b'  --bad:   var(--status-negative);\n  --bad-bg:var(--status-negative-bg);\n',
     b'  --bad:   var(--status-negative);\n  --bad-bg:var(--palette-surface);\n'),
    (b'.num{background:var(--panel);color:var(--ink);border:1px solid var(--role,var(--line))}\n.badge{background:var(--bad-bg);color:var(--ink);border:2px solid var(--bad)}\n',
     b'.num{background:var(--panel);color:var(--ink);border:1px solid var(--role,var(--line))}\n/* Fills behind ink text keep the pale-red tint; red TEXT sits on white (--bad-bg). */\n.badge{background:var(--status-negative-bg);color:var(--ink);border:2px solid var(--bad)}\n'),
    (b'.card{overflow-wrap:anywhere}\n.card-flag{margin:.75rem 0 0;padding:.625rem .75rem;border-radius:.5rem;background:var(--bad-bg)}\n',
     b'.card{overflow-wrap:anywhere}\n.card-flag{margin:.75rem 0 0;padding:.625rem .75rem;border-radius:.5rem;background:var(--status-negative-bg)}\n'),
    (b'.pd .node-start .step-no circle,.pd .node-end .step-no circle{fill:var(--bg);fill-opacity:1}\n.pd .flagged .node-shape{fill:var(--bad-bg);stroke:var(--bad);stroke-width:2}\n.pd .flag-badge circle{fill:var(--bad-bg);stroke:var(--bad);stroke-width:2}\n',
     b'.pd .node-start .step-no circle,.pd .node-end .step-no circle{fill:var(--bg);fill-opacity:1}\n.pd .flagged .node-shape{fill:var(--status-negative-bg);stroke:var(--bad);stroke-width:2}\n.pd .flag-badge circle{fill:var(--status-negative-bg);stroke:var(--bad);stroke-width:2}\n'),
    (b'.pd .edge.hl .edge-arrow{fill:var(--brand)}\n.pd.focusing .node:not(.hl),.pd.focusing .edge:not(.hl){opacity:.22}\n.pd.lane-filter .node:not(.in-lane),.pd.lane-filter .edge:not(.in-lane){opacity:.18}\n',
     b'.pd .edge.hl .edge-arrow{fill:var(--brand)}\n.pd.focusing .node:not(.hl),.pd.focusing .edge:not(.hl),.pd.focusing .flag-badge:not(.hl){opacity:.22}\n.pd.lane-filter .node:not(.in-lane),.pd.lane-filter .edge:not(.in-lane),.pd.lane-filter .flag-badge:not(.in-lane){opacity:.18}\n'),
    (b'.pd.lane-filter .lane:not(.in-lane) .lane-band{fill-opacity:0}\n.pd .node,.pd .edge{transition:opacity .15s}\n',
     b'.pd.lane-filter .lane:not(.in-lane) .lane-band{fill-opacity:0}\n.pd .node,.pd .edge,.pd .flag-badge{transition:opacity .15s}\n'),
    (b'  .card{break-inside:avoid}\n  .pd.focusing .node,.pd.focusing .edge,.pd.lane-filter .node,.pd.lane-filter .edge{opacity:1}\n',
     b'  .card{break-inside:avoid}\n  .pd.focusing .node,.pd.focusing .edge,.pd.lane-filter .node,.pd.lane-filter .edge,\n  .pd.focusing .flag-badge,.pd.lane-filter .flag-badge{opacity:1}\n'),
    (b'<g class="nodes">\n<g class="node node-start c0" data-node="a" data-lane="0" transform="translate(52 130)"><title>1. &#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;measure&#125; &#123;dimension&#125; &#123;time&#125; &#123;name&#125; &#123;rows&#125; &#123;cells&#125; &#123;dims&#125; &#123;steps&#125; &#123;lanes&#125;</title><rect class="node-shape" width="224" height="130" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="26" cy="65" r="10"/><text x="26" y="69.2" text-anchor="middle" font-size="12" font-weight="700">1</text></g><text class="node-label" x="123" y="24.5" text-anchor="middle"><tspan x="123" dy="0">&#123;&#123;T:reset&#125;&#125; &#123;n&#125;</tspan><tspan x="123" dy="18">&#123;measure&#125;</tspan><tspan x="123" dy="18">&#123;dimension&#125; &#123;time&#125;</tspan><tspan x="123" dy="18">&#123;name&#125; &#123;rows&#125;</tspan><tspan x="123" dy="18">&#123;cells&#125; &#123;dims&#125;</tspan><tspan x="123" dy="18">&#123;steps&#125; &#123;lanes&#125;</tspan></text></g>\n<g class="node node-step c0 flagged" data-node="b" data-lane="0" transform="translate(52 316)"><title>2. Two (Forbedringspunkt 1: &#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;measure&#125; &#123;dimension&#125; &#123;time&#125; &#123;name&#125; &#123;rows&#125; &#123;cells&#125; &#123;dims&#125; &#123;steps&#125; &#123;lanes&#125;)</title><rect class="node-shape" width="224" height="130" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="65" r="10"/><text x="22" y="69.2" text-anchor="middle" font-size="12" font-weight="700">2</text></g><text class="node-label" x="123" y="69.5" text-anchor="middle"><tspan x="123" dy="0">Two</tspan></text><g class="flag-badge"><circle cx="224" cy="0" r="10"/><text x="224" y="4.2" text-anchor="middle" font-size="12" font-weight="700">1</text></g></g>\n<g class="node node-end c0" data-node="c" data-lane="0" transform="translate(52 502)"><title>3. Three</title><rect class="node-shape" width="224" height="130" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="26" cy="65" r="10"/><text x="26" y="69.2" text-anchor="middle" font-size="12" font-weight="700">3</text></g><text class="node-label" x="123" y="69.5" text-anchor="middle"><tspan x="123" dy="0">Three</tspan></text></g>\n',
     b'<g class="nodes">\n<g class="node node-start c0" data-node="a" data-lane="0" transform="translate(52 130)"><title>1. &#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;measure&#125; &#123;dimension&#125; &#123;time&#125; &#123;name&#125; &#123;rows&#125; &#123;cells&#125; &#123;dims&#125; &#123;steps&#125; &#123;lanes&#125;</title><rect class="node-shape" width="224" height="130" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="26" cy="65" r="10"/><text x="26" y="69.2" text-anchor="middle" font-size="12" font-weight="700">1 </text></g><text class="node-label" x="123" y="24.5" text-anchor="middle"><tspan x="123" dy="0">&#123;&#123;T:reset&#125;&#125; &#123;n&#125; </tspan><tspan x="123" dy="18">&#123;measure&#125; </tspan><tspan x="123" dy="18">&#123;dimension&#125; &#123;time&#125; </tspan><tspan x="123" dy="18">&#123;name&#125; &#123;rows&#125; </tspan><tspan x="123" dy="18">&#123;cells&#125; &#123;dims&#125; </tspan><tspan x="123" dy="18">&#123;steps&#125; &#123;lanes&#125;</tspan></text></g>\n<g class="node node-step c0 flagged" data-node="b" data-lane="0" transform="translate(52 316)"><title>2. Two (Forbedringspunkt 1: &#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;measure&#125; &#123;dimension&#125; &#123;time&#125; &#123;name&#125; &#123;rows&#125; &#123;cells&#125; &#123;dims&#125; &#123;steps&#125; &#123;lanes&#125;)</title><rect class="node-shape" width="224" height="130" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="65" r="10"/><text x="22" y="69.2" text-anchor="middle" font-size="12" font-weight="700">2 </text></g><text class="node-label" x="123" y="69.5" text-anchor="middle"><tspan x="123" dy="0">Two</tspan></text></g><g class="flag-badge" data-node="b" data-lane="0" aria-hidden="true" transform="translate(52 316)"><circle cx="224" cy="0" r="10"/><text x="224" y="4.2" text-anchor="middle" font-size="12" font-weight="700">1</text></g>\n<g class="node node-end c0" data-node="c" data-lane="0" transform="translate(52 502)"><title>3. Three</title><rect class="node-shape" width="224" height="130" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="26" cy="65" r="10"/><text x="26" y="69.2" text-anchor="middle" font-size="12" font-weight="700">3 </text></g><text class="node-label" x="123" y="69.5" text-anchor="middle"><tspan x="123" dy="0">Three</tspan></text></g>\n'),
    (b'  var nodes = Array.prototype.slice.call(svg.querySelectorAll("g.node"));\n',
     b'  var nodes = Array.prototype.slice.call(svg.querySelectorAll("g.node"));\n  var badges = Array.prototype.slice.call(svg.querySelectorAll("g.flag-badge"));\n  /* The steps become buttons below, so the picture is a group of them, not one image. */\n  svg.setAttribute("role", "group");\n'),
    (b'    svg.classList.toggle("focusing", !!id);\n    nodes.forEach(function (n) { n.classList.toggle("hl", n.getAttribute("data-node") === id); });\n',
     b'    svg.classList.toggle("focusing", !!id);\n    nodes.concat(badges).forEach(function (n) { n.classList.toggle("hl", n.getAttribute("data-node") === id); });\n'),
    (b'      svg.classList.toggle("lane-filter", lane !== "");\n      nodes.forEach(function (n) { n.classList.toggle("in-lane", n.getAttribute("data-lane") === lane); });\n',
     b'      svg.classList.toggle("lane-filter", lane !== "");\n      nodes.concat(badges).forEach(function (n) { n.classList.toggle("in-lane", n.getAttribute("data-lane") === lane); });\n'),
    # Export tree only: the dashboards here embed theme-light.css with its comments, so the
    # new --bad-bg comment is declared on its own (the context after a blank line occurs only
    # where comments survive); and the en/nb process fixtures' node lines get the spacing.
    (b'not text */\n\n  --ok:    var(--status-positive);\n  --ok-bg: var(--status-positive-bg-12);\n  --bad:   var(--status-negative);\n',
     b'not text */\n\n  --ok:    var(--status-positive);\n  --ok-bg: var(--status-positive-bg-12);\n  --bad:   var(--status-negative);\n  /* Fire Red on its own 8% tint is 4.22:1, under AA (axe 4.14, 2026-10-10). On white it\n     is 4.76:1, so the negative chip uses the surface, as theme-dark.css already does. */\n'),
    (b'<g class="nodes">\n<g class="node node-start c0" data-node="ask" data-lane="0" transform="translate(52 112)"><title>1. Needs numbers to share</title><rect class="node-shape" width="224" height="58" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="26" cy="29" r="10"/><text x="26" y="33.2" text-anchor="middle" font-size="12" font-weight="700">1</text></g><text class="node-label" x="123" y="24.5" text-anchor="middle"><tspan x="123" dy="0">Needs numbers to</tspan><tspan x="123" dy="18">share</tspan></text></g>\n<g class="node node-step c0" data-node="describe" data-lane="0" transform="translate(52 226)"><title>2. Describes the question</title><rect class="node-shape" width="224" height="58" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="29" r="10"/><text x="22" y="33.2" text-anchor="middle" font-size="12" font-weight="700">2</text></g><text class="node-label" x="123" y="24.5" text-anchor="middle"><tspan x="123" dy="0">Describes the</tspan><tspan x="123" dy="18">question</tspan></text></g>\n<g class="node node-step c1 flagged" data-node="build" data-lane="1" transform="translate(336 340)"><title>3. Builds the report (Forbedringspunkt 1: Often starts without an example)</title><rect class="node-shape" width="224" height="58" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="29" r="10"/><text x="22" y="33.2" text-anchor="middle" font-size="12" font-weight="700">3</text></g><text class="node-label" x="123" y="33.5" text-anchor="middle"><tspan x="123" dy="0">Builds the report</tspan></text><g class="flag-badge"><circle cx="224" cy="0" r="10"/><text x="224" y="4.2" text-anchor="middle" font-size="12" font-weight="700">1</text></g></g>\n<g class="node node-decision c1" data-node="ok" data-lane="1" transform="translate(336 454)"><title>4. Approved?</title><polygon class="node-shape" points="18,0 206,0 224,29 206,58 18,58 0,29" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="30" cy="29" r="10"/><text x="30" y="33.2" text-anchor="middle" font-size="12" font-weight="700">4</text></g><text class="node-label" x="123" y="33.5" text-anchor="middle"><tspan x="123" dy="0">Approved?</tspan></text></g>\n<g class="node node-end c1" data-node="done" data-lane="1" transform="translate(336 578)"><title>5. Report shared</title><rect class="node-shape" width="224" height="58" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="26" cy="29" r="10"/><text x="26" y="33.2" text-anchor="middle" font-size="12" font-weight="700">5</text></g><text class="node-label" x="123" y="33.5" text-anchor="middle"><tspan x="123" dy="0">Report shared</tspan></text></g>\n',
     b'<g class="nodes">\n<g class="node node-start c0" data-node="ask" data-lane="0" transform="translate(52 112)"><title>1. Needs numbers to share</title><rect class="node-shape" width="224" height="58" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="26" cy="29" r="10"/><text x="26" y="33.2" text-anchor="middle" font-size="12" font-weight="700">1 </text></g><text class="node-label" x="123" y="24.5" text-anchor="middle"><tspan x="123" dy="0">Needs numbers to </tspan><tspan x="123" dy="18">share</tspan></text></g>\n<g class="node node-step c0" data-node="describe" data-lane="0" transform="translate(52 226)"><title>2. Describes the question</title><rect class="node-shape" width="224" height="58" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="29" r="10"/><text x="22" y="33.2" text-anchor="middle" font-size="12" font-weight="700">2 </text></g><text class="node-label" x="123" y="24.5" text-anchor="middle"><tspan x="123" dy="0">Describes the </tspan><tspan x="123" dy="18">question</tspan></text></g>\n<g class="node node-step c1 flagged" data-node="build" data-lane="1" transform="translate(336 340)"><title>3. Builds the report (Forbedringspunkt 1: Often starts without an example)</title><rect class="node-shape" width="224" height="58" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="29" r="10"/><text x="22" y="33.2" text-anchor="middle" font-size="12" font-weight="700">3 </text></g><text class="node-label" x="123" y="33.5" text-anchor="middle"><tspan x="123" dy="0">Builds the report</tspan></text></g><g class="flag-badge" data-node="build" data-lane="1" aria-hidden="true" transform="translate(336 340)"><circle cx="224" cy="0" r="10"/><text x="224" y="4.2" text-anchor="middle" font-size="12" font-weight="700">1</text></g>\n<g class="node node-decision c1" data-node="ok" data-lane="1" transform="translate(336 454)"><title>4. Approved?</title><polygon class="node-shape" points="18,0 206,0 224,29 206,58 18,58 0,29" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="30" cy="29" r="10"/><text x="30" y="33.2" text-anchor="middle" font-size="12" font-weight="700">4 </text></g><text class="node-label" x="123" y="33.5" text-anchor="middle"><tspan x="123" dy="0">Approved?</tspan></text></g>\n<g class="node node-end c1" data-node="done" data-lane="1" transform="translate(336 578)"><title>5. Report shared</title><rect class="node-shape" width="224" height="58" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="26" cy="29" r="10"/><text x="26" y="33.2" text-anchor="middle" font-size="12" font-weight="700">5 </text></g><text class="node-label" x="123" y="33.5" text-anchor="middle"><tspan x="123" dy="0">Report shared</tspan></text></g>\n'),
    (b'<g class="nodes">\n<g class="node node-start c0" data-node="ask" data-lane="0" transform="translate(52 112)"><title>1. Trenger tall \xc3\xa5 dele</title><rect class="node-shape" width="224" height="76" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="26" cy="38" r="10"/><text x="26" y="42.2" text-anchor="middle" font-size="12" font-weight="700">1</text></g><text class="node-label" x="123" y="42.5" text-anchor="middle"><tspan x="123" dy="0">Trenger tall \xc3\xa5 dele</tspan></text></g>\n<g class="node node-step c0" data-node="describe" data-lane="0" transform="translate(52 244)"><title>2. Beskriver sp\xc3\xb8rsm\xc3\xa5let og hvem som skal se svaret</title><rect class="node-shape" width="224" height="76" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="38" r="10"/><text x="22" y="42.2" text-anchor="middle" font-size="12" font-weight="700">2</text></g><text class="node-label" x="123" y="24.5" text-anchor="middle"><tspan x="123" dy="0">Beskriver sp\xc3\xb8rsm\xc3\xa5let</tspan><tspan x="123" dy="18">og hvem som skal se</tspan><tspan x="123" dy="18">svaret</tspan></text></g>\n<g class="node node-step c1 flagged" data-node="model" data-lane="1" transform="translate(374 376)"><title>3. Modellerer dataene (Forbedringspunkt 1: Kolonnene m\xc3\xa5 ofte gjettes. Et eksempel p\xc3\xa5 svaret bestilleren vil ha sparer en hel runde.)</title><rect class="node-shape" width="224" height="76" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="38" r="10"/><text x="22" y="42.2" text-anchor="middle" font-size="12" font-weight="700">3</text></g><text class="node-label" x="123" y="42.5" text-anchor="middle"><tspan x="123" dy="0">Modellerer dataene</tspan></text><g class="flag-badge"><circle cx="224" cy="0" r="10"/><text x="224" y="4.2" text-anchor="middle" font-size="12" font-weight="700">1</text></g></g>\n<g class="node node-decision c2 flagged" data-node="approve" data-lane="2" transform="translate(703 508)"><title>4. Godkjent for denne m\xc3\xa5lgruppen? (Forbedringspunkt 2: Godkjenningen skjer p\xc3\xa5 e-post og blir borte. Den b\xc3\xb8r st\xc3\xa5 i provenance-blokken i filen.)</title><polygon class="node-shape" points="18,0 206,0 224,38 206,76 18,76 0,38" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="30" cy="38" r="10"/><text x="30" y="42.2" text-anchor="middle" font-size="12" font-weight="700">4</text></g><text class="node-label" x="123" y="33.5" text-anchor="middle"><tspan x="123" dy="0">Godkjent for denne</tspan><tspan x="123" dy="18">m\xc3\xa5lgruppen?</tspan></text><g class="flag-badge"><circle cx="206" cy="0" r="10"/><text x="206" y="4.2" text-anchor="middle" font-size="12" font-weight="700">2</text></g></g>\n<g class="node node-step c1" data-node="build" data-lane="1" transform="translate(374 650)"><title>5. Bygger \xc3\xa9n HTML-fil</title><rect class="node-shape" width="224" height="76" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="38" r="10"/><text x="22" y="42.2" text-anchor="middle" font-size="12" font-weight="700">5</text></g><text class="node-label" x="123" y="42.5" text-anchor="middle"><tspan x="123" dy="0">Bygger \xc3\xa9n HTML-fil</tspan></text></g>\n<g class="node node-decision c1" data-node="verified" data-lane="1" transform="translate(374 782)"><title>6. Best\xc3\xa5r tun-verify?</title><polygon class="node-shape" points="18,0 206,0 224,38 206,76 18,76 0,38" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="30" cy="38" r="10"/><text x="30" y="42.2" text-anchor="middle" font-size="12" font-weight="700">6</text></g><text class="node-label" x="123" y="42.5" text-anchor="middle"><tspan x="123" dy="0">Best\xc3\xa5r tun-verify?</tspan></text></g>\n<g class="node node-step c1" data-node="publish" data-lane="1" transform="translate(374 924)"><title>7. Publiserer i delt mappe</title><rect class="node-shape" width="224" height="76" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="38" r="10"/><text x="22" y="42.2" text-anchor="middle" font-size="12" font-weight="700">7</text></g><text class="node-label" x="123" y="33.5" text-anchor="middle"><tspan x="123" dy="0">Publiserer i delt</tspan><tspan x="123" dy="18">mappe</tspan></text></g>\n<g class="node node-step c0" data-node="use" data-lane="0" transform="translate(52 1056)"><title>8. \xc3\x85pner filen og bruker tallene</title><rect class="node-shape" width="224" height="76" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="38" r="10"/><text x="22" y="42.2" text-anchor="middle" font-size="12" font-weight="700">8</text></g><text class="node-label" x="123" y="33.5" text-anchor="middle"><tspan x="123" dy="0">\xc3\x85pner filen og bruker</tspan><tspan x="123" dy="18">tallene</tspan></text></g>\n<g class="node node-step c0" data-node="feedback" data-lane="0" transform="translate(52 1188)"><title>9. Gir tilbakemelding</title><rect class="node-shape" width="224" height="76" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="38" r="10"/><text x="22" y="42.2" text-anchor="middle" font-size="12" font-weight="700">9</text></g><text class="node-label" x="123" y="42.5" text-anchor="middle"><tspan x="123" dy="0">Gir tilbakemelding</tspan></text></g>\n<g class="node node-decision c0" data-node="change" data-lane="0" transform="translate(52 1320)"><title>10. M\xc3\xa5 noe endres?</title><polygon class="node-shape" points="18,0 206,0 224,38 206,76 18,76 0,38" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="30" cy="38" r="10"/><text x="30" y="42.2" text-anchor="middle" font-size="12" font-weight="700">10</text></g><text class="node-label" x="123" y="42.5" text-anchor="middle"><tspan x="123" dy="0">M\xc3\xa5 noe endres?</tspan></text></g>\n<g class="node node-end c0" data-node="done" data-lane="0" transform="translate(52 1462)"><title>11. Ferdig, til neste gang</title><rect class="node-shape" width="224" height="76" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="26" cy="38" r="10"/><text x="26" y="42.2" text-anchor="middle" font-size="12" font-weight="700">11</text></g><text class="node-label" x="123" y="33.5" text-anchor="middle"><tspan x="123" dy="0">Ferdig, til neste</tspan><tspan x="123" dy="18">gang</tspan></text></g>\n',
     b'<g class="nodes">\n<g class="node node-start c0" data-node="ask" data-lane="0" transform="translate(52 112)"><title>1. Trenger tall \xc3\xa5 dele</title><rect class="node-shape" width="224" height="76" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="26" cy="38" r="10"/><text x="26" y="42.2" text-anchor="middle" font-size="12" font-weight="700">1 </text></g><text class="node-label" x="123" y="42.5" text-anchor="middle"><tspan x="123" dy="0">Trenger tall \xc3\xa5 dele</tspan></text></g>\n<g class="node node-step c0" data-node="describe" data-lane="0" transform="translate(52 244)"><title>2. Beskriver sp\xc3\xb8rsm\xc3\xa5let og hvem som skal se svaret</title><rect class="node-shape" width="224" height="76" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="38" r="10"/><text x="22" y="42.2" text-anchor="middle" font-size="12" font-weight="700">2 </text></g><text class="node-label" x="123" y="24.5" text-anchor="middle"><tspan x="123" dy="0">Beskriver sp\xc3\xb8rsm\xc3\xa5let </tspan><tspan x="123" dy="18">og hvem som skal se </tspan><tspan x="123" dy="18">svaret</tspan></text></g>\n<g class="node node-step c1 flagged" data-node="model" data-lane="1" transform="translate(374 376)"><title>3. Modellerer dataene (Forbedringspunkt 1: Kolonnene m\xc3\xa5 ofte gjettes. Et eksempel p\xc3\xa5 svaret bestilleren vil ha sparer en hel runde.)</title><rect class="node-shape" width="224" height="76" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="38" r="10"/><text x="22" y="42.2" text-anchor="middle" font-size="12" font-weight="700">3 </text></g><text class="node-label" x="123" y="42.5" text-anchor="middle"><tspan x="123" dy="0">Modellerer dataene</tspan></text></g><g class="flag-badge" data-node="model" data-lane="1" aria-hidden="true" transform="translate(374 376)"><circle cx="224" cy="0" r="10"/><text x="224" y="4.2" text-anchor="middle" font-size="12" font-weight="700">1</text></g>\n<g class="node node-decision c2 flagged" data-node="approve" data-lane="2" transform="translate(703 508)"><title>4. Godkjent for denne m\xc3\xa5lgruppen? (Forbedringspunkt 2: Godkjenningen skjer p\xc3\xa5 e-post og blir borte. Den b\xc3\xb8r st\xc3\xa5 i provenance-blokken i filen.)</title><polygon class="node-shape" points="18,0 206,0 224,38 206,76 18,76 0,38" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="30" cy="38" r="10"/><text x="30" y="42.2" text-anchor="middle" font-size="12" font-weight="700">4 </text></g><text class="node-label" x="123" y="33.5" text-anchor="middle"><tspan x="123" dy="0">Godkjent for denne </tspan><tspan x="123" dy="18">m\xc3\xa5lgruppen?</tspan></text></g><g class="flag-badge" data-node="approve" data-lane="2" aria-hidden="true" transform="translate(703 508)"><circle cx="206" cy="0" r="10"/><text x="206" y="4.2" text-anchor="middle" font-size="12" font-weight="700">2</text></g>\n<g class="node node-step c1" data-node="build" data-lane="1" transform="translate(374 650)"><title>5. Bygger \xc3\xa9n HTML-fil</title><rect class="node-shape" width="224" height="76" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="38" r="10"/><text x="22" y="42.2" text-anchor="middle" font-size="12" font-weight="700">5 </text></g><text class="node-label" x="123" y="42.5" text-anchor="middle"><tspan x="123" dy="0">Bygger \xc3\xa9n HTML-fil</tspan></text></g>\n<g class="node node-decision c1" data-node="verified" data-lane="1" transform="translate(374 782)"><title>6. Best\xc3\xa5r tun-verify?</title><polygon class="node-shape" points="18,0 206,0 224,38 206,76 18,76 0,38" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="30" cy="38" r="10"/><text x="30" y="42.2" text-anchor="middle" font-size="12" font-weight="700">6 </text></g><text class="node-label" x="123" y="42.5" text-anchor="middle"><tspan x="123" dy="0">Best\xc3\xa5r tun-verify?</tspan></text></g>\n<g class="node node-step c1" data-node="publish" data-lane="1" transform="translate(374 924)"><title>7. Publiserer i delt mappe</title><rect class="node-shape" width="224" height="76" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="38" r="10"/><text x="22" y="42.2" text-anchor="middle" font-size="12" font-weight="700">7 </text></g><text class="node-label" x="123" y="33.5" text-anchor="middle"><tspan x="123" dy="0">Publiserer i delt </tspan><tspan x="123" dy="18">mappe</tspan></text></g>\n<g class="node node-step c0" data-node="use" data-lane="0" transform="translate(52 1056)"><title>8. \xc3\x85pner filen og bruker tallene</title><rect class="node-shape" width="224" height="76" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="38" r="10"/><text x="22" y="42.2" text-anchor="middle" font-size="12" font-weight="700">8 </text></g><text class="node-label" x="123" y="33.5" text-anchor="middle"><tspan x="123" dy="0">\xc3\x85pner filen og bruker </tspan><tspan x="123" dy="18">tallene</tspan></text></g>\n<g class="node node-step c0" data-node="feedback" data-lane="0" transform="translate(52 1188)"><title>9. Gir tilbakemelding</title><rect class="node-shape" width="224" height="76" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="38" r="10"/><text x="22" y="42.2" text-anchor="middle" font-size="12" font-weight="700">9 </text></g><text class="node-label" x="123" y="42.5" text-anchor="middle"><tspan x="123" dy="0">Gir tilbakemelding</tspan></text></g>\n<g class="node node-decision c0" data-node="change" data-lane="0" transform="translate(52 1320)"><title>10. M\xc3\xa5 noe endres?</title><polygon class="node-shape" points="18,0 206,0 224,38 206,76 18,76 0,38" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="30" cy="38" r="10"/><text x="30" y="42.2" text-anchor="middle" font-size="12" font-weight="700">10 </text></g><text class="node-label" x="123" y="42.5" text-anchor="middle"><tspan x="123" dy="0">M\xc3\xa5 noe endres?</tspan></text></g>\n<g class="node node-end c0" data-node="done" data-lane="0" transform="translate(52 1462)"><title>11. Ferdig, til neste gang</title><rect class="node-shape" width="224" height="76" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="26" cy="38" r="10"/><text x="26" y="42.2" text-anchor="middle" font-size="12" font-weight="700">11 </text></g><text class="node-label" x="123" y="33.5" text-anchor="middle"><tspan x="123" dy="0">Ferdig, til neste </tspan><tspan x="123" dy="18">gang</tspan></text></g>\n'),
    # Fourth (2026-10-12): an empty measure value is left out of the charts and the average
    # instead of counting as 0, the table decides a numeric column on any row instead of
    # rows[0], and the page's own CSV reader keeps an empty cell empty. One pair per hunk
    # of the template diff.
    (b'const sum = (rows, col) => rows.reduce((a, r) => a + (Number(r[col]) || 0), 0);\n',
     b'// A measure value as a number, or null when the cell is empty or not a number. Null is\n// left out of every aggregate: summing it as 0 moves the average and draws a bar or a\n// point that the data does not have.\nconst val = (v) => {\n  if (v === null || v === undefined || v === "") return null;\n  const n = Number(v);\n  return Number.isFinite(n) ? n : null;\n};\nconst valued = (rows, col) => rows.filter(r => val(r[col]) !== null);\nconst sum = (rows, col) => rows.reduce((a, r) => a + (val(r[col]) ?? 0), 0);\n'),
    (b'  for (const r of rows) m.set(r[key], (m.get(r[key]) || 0) + (Number(r[measure]) || 0));\n',
     b'  for (const r of valued(rows, measure)) m.set(r[key], (m.get(r[key]) || 0) + val(r[measure]));\n'),
    (b'  const avg = rows.length ? total / rows.length : 0;\n',
     b'  const n = valued(rows, META.measure).length;\n  const avg = n ? total / n : 0;\n'),
    (b'  const isNum = c => rows.length && typeof rows[0][c] === "number";\n',
     b'  // Numeric if any row has a number there: rows[0] may be empty.\n  const numCols = new Set(cols.filter(c => rows.some(r => typeof r[c] === "number")));\n  const isNum = c => numCols.has(c);\n'),
    (b'  // so an ID column that looks numeric survives as text)\n',
     b'  // so an ID column that looks numeric survives as text). Empty stays null, never 0.\n'),
    (b'      rows.forEach(r => r[col] = r[col] === "" ? 0 : parseNum(r[col]));\n',
     b'      rows.forEach(r => r[col] = r[col] === "" ? null : parseNum(r[col]));\n'),
    # Fifth (2026-10-12): a bar chart with a name longer than 16 characters lays its bars
    # out sideways instead of cutting the name and drawing it at an angle. The KPI cards
    # are not in this list: with neither --kpis nor --measure-kind the builder writes the
    # old cards block back, byte for byte, into the placeholder that replaced it.
    (b'    for (const k in a) n.setAttribute(k, a[k]); return n; };\n\n  // y gridlines + labels\n',
     b"    for (const k in a) n.setAttribute(k, a[k]); return n; };\n  // Under an upright bar a name is cut after 16 characters and drawn at an angle. When\n  // a name is longer than that, lay the bars out sideways: each name gets the card's width.\n  if (data.some(d => String(d.key).length > 16)) return sideBars(svg, W, H, data, max, el);\n\n  // y gridlines + labels\n"),
    (b'/* ---------- SVG line chart ------------------------------------------------- */\n',
     b'function sideBars(svg, W, H, data, max, el) {\n  const width = t => t.getComputedTextLength() || t.textContent.length * 6.5;\n  const labels = data.map(d => {\n    const t = el("text", { class: "axis-label", "text-anchor": "end" });\n    t.textContent = d.key; svg.appendChild(t); return t;\n  });\n  // The name column is as wide as the longest name, up to 45 % of the chart. A name\n  // that is wider still (on a phone) is cut, and keeps its full text as a tooltip.\n  const lw = Math.min(Math.round(W * 0.45), Math.max(...labels.map(width)));\n  labels.forEach((t, i) => {\n    const full = String(data[i].key);\n    if (width(t) <= lw) return;\n    for (let n = full.length - 1; n > 1 && width(t) > lw; n--) t.textContent = full.slice(0, n) + "\xe2\x80\xa6";\n    const title = el("title", {}); title.textContent = full; t.appendChild(title);\n  });\n\n  const m = { t: 8, r: 32, b: 28, l: lw + 16 };\n  const iw = W - m.l - m.r, ih = H - m.t - m.b, rowH = ih / data.length;\n  const bh = Math.min(rowH * 0.7, 28);\n  // Up to four steps on the value axis, fewer when the numbers would touch (a phone).\n  const probe = el("text", { class: "axis-label" }); probe.textContent = fmt(max);\n  svg.appendChild(probe);\n  const steps = Math.max(1, Math.min(4, Math.floor(iw / (width(probe) + 16))));\n  probe.remove();\n  for (let i = 0; i <= steps; i++) {\n    const x = m.l + iw * i / steps;\n    svg.appendChild(el("line", { class: "gridline", x1: x, x2: x, y1: m.t, y2: m.t + ih }));\n    const t = el("text", { class: "axis-label", x, y: m.t + ih + 18, "text-anchor": "middle" });\n    t.textContent = fmt(max * i / steps); svg.appendChild(t);\n  }\n  svg.appendChild(el("line", { class: "axis", x1: m.l, x2: m.l, y1: m.t, y2: m.t + ih }));\n\n  data.forEach((d, i) => {\n    const mid = m.t + i * rowH + rowH / 2;\n    const rect = el("rect", { class: "bar", x: m.l, y: mid - bh / 2, rx: 2, height: bh,\n      width: Math.max((d.value / max) * iw, 1) });\n    rect.addEventListener("mousemove", e => showTip(e, `${d.key}: ${fmt(d.value)}`));\n    rect.addEventListener("mouseleave", hideTip);\n    svg.appendChild(rect);\n    labels[i].setAttribute("x", m.l - 8); labels[i].setAttribute("y", mid + 4);\n  });\n}\n\n/* ---------- SVG line chart ------------------------------------------------- */\n'),
    # Sixth (2026-10-13): the charts also redraw when their card changes width without a
    # window resize event, as in an Atlassian Artifacts embed (docs/29). One pair per
    # template hunk: the dashboard, then the cube.
    (b'/* Redraw the charts, not the table, when the card changes width. */\nlet resizeFrame = 0;\naddEventListener("resize", () => {\n  cancelAnimationFrame(resizeFrame);\n  resizeFrame = requestAnimationFrame(() => renderCharts(visibleRows()));\n});\n',
     b'/* Redraw the charts, not the table, when a chart card changes width.\n   Watch the cards themselves, not only window "resize": a host can give the frame its\n   size without ever firing resize (measured in an Atlassian Artifacts embed inside a\n   Confluence page, docs/29). The charts would then keep the width they were drawn at\n   while the frame was still 0 x 0. Only a change of width redraws, so the height change a\n   redraw causes cannot loop. */\nlet resizeFrame = 0;\nconst queueChartRedraw = () => {\n  cancelAnimationFrame(resizeFrame);\n  resizeFrame = requestAnimationFrame(() => renderCharts(visibleRows()));\n};\naddEventListener("resize", queueChartRedraw);\nif (typeof ResizeObserver === "function") {\n  const seenW = new WeakMap();\n  const chartObserver = new ResizeObserver(entries => {\n    const widthChanged = entries.some(e => {\n      const w = Math.round(e.contentRect.width), was = seenW.get(e.target);\n      seenW.set(e.target, w);\n      return was !== undefined && w !== was;\n    });\n    if (widthChanged) queueChartRedraw();\n  });\n  ["chart1", "chart2"].forEach(id => chartObserver.observe($(id)));\n}\n'),
    (b'    addEventListener("resize", () => { cancelAnimationFrame(frame);\n      frame = requestAnimationFrame(() => { if (measureCharts()) render(); }); });\n',
     b'    const redraw = () => { cancelAnimationFrame(frame);\n      frame = requestAnimationFrame(() => { if (measureCharts()) render(); }); };\n    addEventListener("resize", redraw);\n    /* A host can size the frame without firing resize (measured in an Atlassian Artifacts\n       embed, docs/29), so also watch the chart containers. measureCharts() returns false\n       when no width changed, which stops the loop a redraw\'s own reflow would start. */\n    if (typeof ResizeObserver === "function") {\n      const ro = new ResizeObserver(redraw);\n      ["charts", "trend"].forEach(id => { const el = document.getElementById(id); if (el) ro.observe(el); });\n    }\n'),
    # Seventh (2026-10-13): the cube said lang="no" while every other template says "nb"
    # (docs/11). Both are valid BCP 47; one project should use one.
    (b'<html lang="no">', b'<html lang="nb">'),
]

BASELINE = {
    "fx-deck/fx-deck.html": "aa23237d87072b7f1897937665299e8e9df64d3e9537a68cb0b61f6255e9296a",
    "dash-bundled/dash-bundled.html": "54b23774e66b54375c106ce0916dbe00338d5c2e1c5eda1d9dbcf6ca191a2fe8",
    "dash-paired/paired/dash.html": "6ae89033549fa546d0e1178b7ec17b1b17477e976d9328d23679be332411e620",
    "dash-paired/paired/data.js": "57971987b2a191b18dc9d3980ccaad1419cb3a8d92145a9aef497bfaa72a678c",
    "dash-feedback/dash-feedback.html": "59b314f11d4bbeeaa85bc63ac691986a85dc85c46060548d101aef4437eb2926",
    "cube/cube.html": "b6d8a25b1741b2148227853b02bd55e0725328fb4bb3b43558258c5527c97bc9",
    "cube-feedback/cube-feedback.html": "149164c75093580f1d9cde8d211dd21d2ee67d84c9d219ae7bcf7e2fb7e70207",
    "process/process.html": "8991832b0e2c158e37ed365f8985df8be19a5f36338967e3b773ced2b3e12d04",
    "fx-dash/fx-dash.html": "48fdb94bfdb6ad75570dba34bb73f8821648bbdcb3afa7c5be19604d74bb0b9a",
    "fx-dash-paired/fxp/dash.html": "febc9ad24319d41cf1dbbb2426af15f8263b02a099cc21f7235a4eb38e953e92",
    "fx-dash-paired/fxp/data.js": "360bafa7d429d90f75a86aa7bc2f73f80db69634e8451dbf996c9001721f85bb",
    "fx-dash-notime/fx-dash-notime.html": "01622a697c8b0f1c3b48a2d32a5cf37efee647b41c34b41edc8021d7294bef0a",
    "fx-cube/fx-cube.html": "5c6a9390ad6fb8d55160ccaac9719c11b55dfe31af47d2cdb224fdfe8e49f7b2",
    "fx-process/fx-process.html": "07f1519b3f2922cc891bdbc2f6a4493b4db91ee77a6d82b3acb0e29ae8643875",
}

FORBIDDEN_IN_EN = ("'", '"', "\\", "`", "${")   # would break the string or comment it lands in
NORWEGIAN_LETTERS = re.compile("[æøåÆØÅ]")

passed = failed = 0


def chk(label: str, ok: bool, detail: str = "", n: int | None = None) -> bool:
    """One check. `n` is how many items it looked at; zero items is a failure."""
    global passed, failed
    if n is not None and n == 0:
        ok, detail = False, "checked 0 items"
    if ok:
        passed += 1
        print(f"  PASS {label}" + (f" ({n} checked)" if n is not None else ""))
    else:
        failed += 1
        print(f"  FAIL {label}" + (f": {detail}" if detail else ""))
    return ok


def build_case(name: str, out: pathlib.Path, lang: str | None, tools: pathlib.Path | None = None,
               extra_env: dict | None = None, check: bool = True):
    """Build one case into `out`. Returns ({relative file: bytes}, CompletedProcess)."""
    builder, source, args, files, _tables = CASES[name]
    out.mkdir(parents=True, exist_ok=True)
    data = out / "_in" / (source.name if source else "none")
    if source:
        data.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, data)
        os.utime(data, (1767323045, 1767323045))
    argv = [a.replace("{out}", str(out)).replace("{in}", str(data)) for a in args]
    if builder in (DASH, CUBE):
        argv = ["--data", str(data), *argv]
    if lang:
        argv += ["--lang", lang]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH="1767323045", **(extra_env or {}))
    r = subprocess.run([sys.executable, "-c", SHIM, str((tools or ROOT / "tools") / builder), *argv],
                       capture_output=True, text=True, cwd=ROOT, env=env)
    if r.returncode != 0:
        if check:
            raise SystemExit(f"{name} ({lang}): builder failed\n{r.stderr[-1500:]}")
        return {}, r
    return {f: (out / f).read_bytes() for f in files}, r


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


# ------------------------------------------------------------------------ table checks
def table_names() -> list[str]:
    return sorted(p.stem for p in i18n.DIR.glob("*.strings"))


def table_problems(directory: pathlib.Path) -> list[str]:
    """Key sets that differ between nb and en, in every table of a directory."""
    problems = []
    for p in sorted(directory.glob("*.strings")):
        tables = i18n.parse(p.read_text(encoding="utf-8"), p.name)
        for lang in i18n.LANGS:
            if lang not in tables:
                problems.append(f"{p.name}: no [{lang}] section")
        if all(lang in tables for lang in i18n.LANGS):
            for key in sorted(set(tables["nb"]) ^ set(tables["en"])):
                have = "nb" if key in tables["nb"] else "en"
                problems.append(f"{p.name}: {key} only in {have}")
    return problems


ALSO_ENGLISH = {"over"}    # an nb word that is an English word too ("{measure} over {time}")
IDENTIFIERS = re.compile(r'\b(?:id|for|aria-controls|aria-labelledby)="[^"]*"')


def en_problems(html: str, tables: list[str]) -> tuple[list[str], int]:
    """What is wrong with an en page: Norwegian letters, or an nb string. Also the number
    of nb fragments looked for, so the caller can refuse a check that looked for nothing.

    The reference is always the committed tables, never the ones a page was built from, so
    a table that was damaged cannot vouch for itself. Element ids (tab-steg, panel-roller)
    are identifiers that no one reads, and the verifiers and old links use them, so they
    stay as they were and are not scanned."""
    problems = []
    html = IDENTIFIERS.sub("", html)
    for m in NORWEGIAN_LETTERS.finditer(html):
        line = html.count("\n", 0, m.start()) + 1
        problems.append(f"letter {m.group()!r} on line {line}")
        break
    looked = 0
    for name in tables:
        t = i18n.load_all(name)
        for key, nb_value in t["nb"].items():
            en_value = t["en"][key]
            for frag in re.split(r"\{[a-z]+\}", nb_value):
                frag = frag.strip()
                if len(frag) < 3 or frag in en_value or frag in ALSO_ENGLISH:
                    continue          # too short to mean anything, or the same word in en
                looked += 1
                if re.search(r"(?<![\w])" + re.escape(frag) + r"(?![\w])", html):
                    problems.append(f"nb text from {name}.{key}: {frag!r}")
    return problems, looked


def declared_changes(blob: bytes) -> bytes:
    """What an old builder's output becomes once the declared nb changes are applied."""
    for before, after in DELIBERATE_NB_CHANGES:
        blob = blob.replace(before, after)
    return blob


def main() -> int:
    tools_dir = None
    if "--tools" in sys.argv:
        tools_dir = pathlib.Path(sys.argv[sys.argv.index("--tools") + 1])
    if "--dump" in sys.argv:
        dest = pathlib.Path(sys.argv[sys.argv.index("--dump") + 1])
        dest.mkdir(parents=True, exist_ok=True)
        for case in CASES:
            if tools_dir and CASES[case][0] == DECK:
                continue      # older tools had no deck builder
            built, _ = build_case(case, pathlib.Path(tempfile.mkdtemp()), None if tools_dir else "nb",
                                  tools_dir)
            for rel, blob in built.items():
                if tools_dir:
                    blob = declared_changes(blob)
                (dest / f"{case}--{rel.replace('/', '__')}").write_bytes(blob)
                print(f'    "{case}/{rel}": "{sha(blob)}",')
        return 0
    if "--dump-adv" in sys.argv:
        work = pathlib.Path(tempfile.mkdtemp(prefix="tun-i18n-adv-"))
        for name in register_probes(work):
            built, _ = build_case(name, work / "pin" / name, None if tools_dir else "nb", tools_dir)
            for rel, blob in built.items():
                if tools_dir:
                    blob = declared_changes(blob)
                print(f'    "{name}/{rel}": "{sha(blob)}",')
        return 0

    work = pathlib.Path(tempfile.mkdtemp(prefix="tun-i18n-"))
    try:
        return run(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


# sha256 of the nb build of each section 6 probe file, taken from the builders before any
# strings table existed (a9cca83) with the declared nb changes applied to their output
# (`--dump-adv --tools OLD_TOOLS`), and proved equal to the current builders' nb output.
# Pinned rather than rebuilt from git: a flattened export has no history to build from.
ADV_BASELINE = {
    "slot-dash/slot-dash.html": "582a36cdcb3449d65a4fbf863c68e61d7500ebedbc6339dc7dfa08757382ac15",
    "slot-cube/slot-cube.html": "f09ea5b27174dbd30aebd107554e5ddc0979479bd9dc23d72fdfafa0391874da",
    "tok-dash/tok-dash.html": "4b44b01eca03c1687981e82df36a8bbd48824dfd0800ff7bdbbd7d36da846e8c",
    "tok-cube/tok-cube.html": "97841300e28c35b35fb6b5e123f11c8de2e623cd39c2d9e6a4fbfd9f6781fc8d",
    "tok-process/tok-process.html": "ee57864c446946682980cc9be99ed9bb4025a741292cab188fe3305c7fbf1951",
}


def register_probes(work: pathlib.Path) -> dict:
    """Write the probe inputs under `work` and add the probes to CASES. Data that looks like
    a format slot or a template token: it must come out untouched, exactly as the builders
    before the tables wrote it (chained .replace() rescanned it). Returns name -> probe."""
    adv = work / "adv"
    adv.mkdir(exist_ok=True)
    # a measure column called {dimension}; the old builder printed "{dimension} per Product"
    slot_csv = adv / "slot.csv"
    slot_csv.write_text("Month,Product,{dimension}\n2026-01,Loans,10\n2026-02,Cards,20\n", encoding="utf-8")
    # a source file called source-{rows}.csv; the old cube builder kept the name as it was
    name_csv = adv / "source-{rows}.csv"
    name_csv.write_text("Month,Product,Amount\n2026-01,Loans,10\n2026-02,Cards,20\n", encoding="utf-8")
    # titles, column names, values and a requester that hold tokens and slots of every table
    evil = "{{T:reset}} {n} {measure} {dimension} {time} {name} {rows} {cells} {dims} {steps} {lanes}"
    tok_csv = adv / "tokens.csv"
    tok_csv.write_text(f'Month,Product,Amount\n2026-01,"{evil}",10\n2026-02,Cards,20\n', encoding="utf-8")
    spec = adv / "tokens.process.txt"
    short = "{{T:reset}} {n} {steps} {lanes}"       # a lane name is at most 40 characters
    spec.write_text(
        f"title: {evil}\nsource: {evil}\nrequested-by: {evil}\ndescription: {evil}\n\n"
        f"lane {short}\n  start a: {evil}\n    beskrivelse: {evil}\n  step b: Two\n"
        f"    improve: {evil}\n  end c: Three\n\nflow\n  a -> b -> c\n", encoding="utf-8")
    probes = {
        "slot-dash": (DASH, slot_csv, ["--title", "t", "--dimension", "Product", "--measure", "{dimension}",
                                       "--time", "Month", "--out", "{out}/slot-dash.html"],
                      ["slot-dash.html"], DASH_T,
                      {"nb": ["{dimension} per Product"], "en": ["{dimension} by Product"]}),
        "slot-cube": (CUBE, name_csv, ["--dims", "Product", "--time", "Month", "--measures", "Amount:sum",
                                       "--title", "t", "--feedback-to", "hei@example.org",
                                       "--out", "{out}/slot-cube.html"],
                      ["slot-cube.html"], CUBE_T + FB, ["source-{rows}.csv"]),
        "tok-dash": (DASH, tok_csv, ["--title", evil, "--dimension", "Product", "--measure", "Amount",
                                     "--time", "Month", "--requested-by", evil, "--source", evil,
                                     "--feedback-to", "hei@example.org", "--out", "{out}/tok-dash.html"],
                     ["tok-dash.html"], DASH_T + FB, [evil, "{{T:reset}}"]),
        "tok-cube": (CUBE, tok_csv, ["--dims", "Product", "--time", "Month", "--measures", "Amount:sum",
                                     "--title", evil, "--requested-by", evil,
                                     "--feedback-to", "hei@example.org", "--out", "{out}/tok-cube.html"],
                     ["tok-cube.html"], CUBE_T + FB, [evil]),
        "tok-process": (PROC, spec, ["{in}", "--out", "{out}/tok-process.html"], ["tok-process.html"],
                        ["process-diagram"], ["&#123;&#123;T:reset&#125;&#125;", "&#123;n&#125;"]),   # braces are escaped
    }
    for name, (builder, src, args, files, tables, _literals) in probes.items():
        CASES[name] = (builder, src, args, files, tables)
    return probes


def adversarial(work: pathlib.Path) -> None:
    """Data that looks like a format slot or a template token must come out untouched."""
    print("6. data that looks like a slot or a token")
    probes = register_probes(work)

    def lits_for(literals, lang):
        """A probe's expected strings: one list for both languages, or a list per language."""
        return literals[lang] if isinstance(literals, dict) else literals

    drifted, unpinned, seen = [], [], set()
    for name, (_b, _s, _a, _f, _t, literals) in probes.items():
        got_nb, _ = build_case(name, work / "adv-nb" / name, "nb")
        got_en, _ = build_case(name, work / "adv-en" / name, "en")
        for rel, blob in got_nb.items():
            key = f"{name}/{rel}"
            seen.add(key)
            if key not in ADV_BASELINE:
                unpinned.append(key)
            elif ADV_BASELINE[key] != sha(blob):
                drifted.append(key)
        if name.startswith("slot-"):      # the string the old builder wrote is still there, in both
            page = lambda built: "".join(b.decode("utf-8") for b in built.values())  # noqa: E731
            for lang, built in (("nb", got_nb), ("en", got_en)):
                for lit in lits_for(literals, lang):
                    if lit not in page(built):
                        drifted.append(f"{name} {lang}: {lit!r} was rewritten")
    chk("every probe file has a pinned hash", not unpinned, ", ".join(unpinned), n=len(seen))
    chk("every pinned hash belongs to a probe file (none is stale)",
        set(ADV_BASELINE) == seen, str(sorted(set(ADV_BASELINE) ^ seen)), n=len(ADV_BASELINE))
    chk("nb build equals the pinned old output byte for byte (slots and tokens as data)",
        not drifted, ", ".join(drifted), n=len(seen))
    for name, (_b, _s, _a, _f, _t, literals) in probes.items():
        page = "".join(b.decode("utf-8") for b in build_case(name, work / "adv-en" / name, "en")[0].values())
        en_lits = lits_for(literals, "en")
        missing = [lit for lit in en_lits if lit not in page]
        chk(f"{name}: en keeps {len(en_lits)} data string(s) as written", not missing, str(missing),
            n=len(en_lits))
    cube_page = build_case("slot-cube", work / "adv-en" / "slot-cube", "en")[0]["slot-cube.html"].decode("utf-8")
    chk("slot-cube: the file name was not filled in (no source-48.csv)", "source-48.csv" not in cube_page, n=1)
    for name in probes:
        del CASES[name]


def run(work: pathlib.Path) -> int:
    # 1 ---- tables
    print("1. tables")
    names = table_names()
    chk("there are strings tables", bool(names), n=len(names))
    problems = table_problems(i18n.DIR)
    nkeys = sum(len(i18n.load(n, "nb")) for n in names)
    chk("every key exists in both nb and en", not problems, "; ".join(problems), n=nkeys)

    used_bad, tokens = [], 0
    html_sources = sorted(TEMPLATES.glob("*.html"))
    for p in html_sources:
        keys = i18n.keys_used(p.read_text(encoding="utf-8"))
        table = i18n.path_for(p.stem)
        if not keys:
            continue
        if not table.exists():
            used_bad.append(f"{p.name}: has tokens, no table")
            continue
        have = set(i18n.load(p.stem, "nb"))
        tokens += len(keys)
        used_bad += [f"{p.name}: {{{{T:{k}}}}} not in the table" for k in sorted(keys - have)]
    chk("every {{T:key}} in a template exists in its table", not used_bad, "; ".join(used_bad), n=tokens)

    unused, total = [], 0
    code = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "tools").glob("*.py"))
    for n in names:
        tpl = TEMPLATES / f"{n}.html"
        text = (tpl.read_text(encoding="utf-8") if tpl.exists() else "") + code
        for key in i18n.load(n, "nb"):
            total += 1
            base = re.sub(r"_(one|other)$", "", key)     # n_steps_one is read as "n_steps"
            if f"{{{{T:{key}}}}}" not in text and f'"{key}"' not in text \
                    and f"'{key}'" not in text and f'"{base}"' not in text \
                    and f"'{base}'" not in text:
                unused.append(f"{n}.{key}")
    chk("every key is used by a template or a builder", not unused, ", ".join(unused), n=total)

    bad_chars = []
    for n in names:
        for key, v in i18n.load(n, "en").items():
            if any(c in v for c in FORBIDDEN_IN_EN):
                bad_chars.append(f"{n}.{key}")
    chk("no en value holds a quote, backslash, backtick or ${", not bad_chars, ", ".join(bad_chars), n=nkeys)

    # 2 ---- builds
    print("2. builds")
    nb, en = {}, {}
    for case in CASES:
        nb[case], _ = build_case(case, work / "nb" / case, "nb")
        en[case], _ = build_case(case, work / "en" / case, "en")
    chk("every builder builds with --lang nb", all(nb.values()), n=len(nb))
    chk("every builder builds with --lang en", all(en.values()), n=len(en))
    default, _ = build_case("dash-bundled", work / "default", None)
    chk("no --lang means nb", default == nb["dash-bundled"], n=len(default))

    # 3 ---- nb frozen
    print("3. nb output is what it was")
    drift, nfiles = [], 0
    for case, files in nb.items():
        for rel, blob in files.items():
            nfiles += 1
            want = BASELINE.get(f"{case}/{rel}")
            if want != sha(blob):
                drift.append(f"{case}/{rel}" + (" (no baseline)" if want is None else ""))
    chk("nb build equals the baseline sha256", not drift, ", ".join(drift), n=nfiles)

    # 4 ---- en clean
    print("4. en output has no Norwegian")
    bad, pages, looked_total = [], 0, 0
    for case, files in en.items():
        if not case.startswith("fx-"):
            continue
        tables = CASES[case][4]
        for rel, blob in files.items():
            pages += 1
            text = blob.decode("utf-8")
            problems, looked = en_problems(text, tables)
            looked_total += looked
            if rel.endswith(".html") and '<html lang="en">' not in text:
                problems.append("no <html lang=\"en\">")
            bad += [f"{case}/{rel}: {p}" for p in problems]
    chk("en pages: lang=en, no æøåÆØÅ, no nb strings", not bad, "; ".join(bad[:6]), n=pages)
    chk("... and the nb fragments were really looked for", looked_total > 0, n=looked_total)
    differ = sum(1 for c in en if c.startswith("fx-") for f in en[c] if en[c][f] != nb[c][f])
    chk("en differs from nb in every fx page", differ == sum(len(en[c]) for c in en if c.startswith("fx-"))
        - sum(1 for c in en if c.startswith("fx-") for f in en[c] if f.endswith("data.js")),
        f"{differ} differ", n=differ)

    # 5 ---- mutations
    print("5. a damaged table is noticed")
    broken = work / "broken"
    shutil.copytree(i18n.DIR, broken)
    victim = broken / "single-file-dashboard.strings"
    text = victim.read_text(encoding="utf-8")
    en_part = text.split("[en]", 1)[1]
    gone = en_part.replace("\nreset = Reset\n", "\n", 1)
    chk("mutation setup: the en key to delete is there", gone != en_part, n=1)
    victim.write_text(text.split("[en]", 1)[0] + "[en]" + gone, encoding="utf-8")
    seen = table_problems(broken)
    chk("a deleted en key is reported by the table check",
        len(seen) == 1 and "reset only in nb" in seen[0], "; ".join(seen), n=len(seen))
    _, r = build_case("fx-dash", work / "mut-build", "en", extra_env={"TUN_I18N_DIR": str(broken)},
                      check=False)
    chk("a deleted en key stops the en build", r.returncode != 0 and "reset" in r.stderr,
        f"exit {r.returncode}: {r.stderr[-200:]}", n=1)

    shutil.copyfile(i18n.DIR / "single-file-dashboard.strings", victim)
    leaked = victim.read_text(encoding="utf-8").replace("reset = Reset\n", "reset = Nullstill\n", 1)
    victim.write_text(leaked, encoding="utf-8")
    built, _ = build_case("fx-dash", work / "mut-nb", "en", extra_env={"TUN_I18N_DIR": str(broken)})
    problems, _ = en_problems(built["fx-dash.html"].decode("utf-8"), DASH_T + FB)
    chk("an nb string pasted into en is flagged", len(problems) == 1 and "reset" in problems[0],
        "; ".join(problems), n=len(problems))

    shutil.copyfile(i18n.DIR / "single-file-dashboard.strings", victim)
    leaked = victim.read_text(encoding="utf-8").replace("reset = Reset\n", "reset = Reset p\u00e5\n", 1)
    victim.write_text(leaked, encoding="utf-8")
    built, _ = build_case("fx-dash", work / "mut-letter", "en", extra_env={"TUN_I18N_DIR": str(broken)})
    problems, _ = en_problems(built["fx-dash.html"].decode("utf-8"), DASH_T + FB)
    chk("an \u00e5 pasted into en is flagged", len(problems) == 1 and "letter" in problems[0],
        "; ".join(problems), n=len(problems))

    shutil.copyfile(i18n.DIR / "single-file-dashboard.strings", victim)
    changed = victim.read_text(encoding="utf-8").replace("reset = Nullstill\n", "reset = Nullstill!\n", 1)
    victim.write_text(changed, encoding="utf-8")
    built, _ = build_case("fx-dash", work / "mut-frozen", "nb", extra_env={"TUN_I18N_DIR": str(broken)})
    chk("a changed nb string breaks the frozen hash",
        sha(built["fx-dash.html"]) != BASELINE["fx-dash/fx-dash.html"], n=len(built))

    adversarial(work)

    print("-" * 62)
    print(f"PASS: {passed}  FAIL: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
