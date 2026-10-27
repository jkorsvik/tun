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
                                                  # (--tools: an older copy of tools/)
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
SURVEY_CSV = ROOT / "examples" / "27-survey-board" / "survey.csv"
FX_SURVEY_CSV = ROOT / "tests" / "fixtures" / "i18n-survey-en.txt"
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
SURVEY = "build_survey_dashboard.py"
REGISTER = "build_register.py"

# name -> (builder, input file, arguments, files written, strings tables the page uses).
# {out} is the temp dir, {in} the input as copied there (name kept, mtime fixed).
SALES = ["--title", "Salg per region og produkt 2026", "--dimension", "Produkt",
         "--measure", "Belop", "--time", "Maaned", "--requested-by", "Prosjekteier"]
FX_SALES = ["--title", "Sales by region and product 2026", "--dimension", "Product",
            "--measure", "Amount", "--time", "Month", "--requested-by", "The sales team",
            "--source", "Made-up example data"]
DASH_T = ["single-file-dashboard"]
SURVEY_T = ["survey-dashboard"]
REGISTER_T = ["register"]
REGISTER_CSV = ROOT / "examples" / "32-rows-register" / "avvik.csv"
COMPARE = "build_comparison.py"
INDEX = "build_index.py"
DIST = "build_distribution.py"
SCORE = "build_scorecard.py"
SCORE_INPUT = ROOT / "examples" / "39-scorecard" / "manedstall.csv"
DIST_INPUT = ROOT / "examples" / "38-distribution" / "saksbehandlingstid.csv"
TIMELINE = "build_timeline.py"
TIMELINE_INPUT = ROOT / "examples" / "35-timeline" / "milepaeler.csv"
INDEX_INPUT = ROOT / "examples" / "32-rows-register" / "register.html"
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
    # nb Norwegian answers from the example; en judged on an English fixture, because the
    # page shows the answers themselves and Norwegian data would be a false negative.
    "survey": (SURVEY, SURVEY_CSV, ["--data", "{in}", "--title", "Arbeidsmiljo 2026", "--segments", "Enhet,Rolle",
                                    "--requested-by", "HR", "--out", "{out}/survey.html"],
               ["survey.html"], SURVEY_T),
    "register": (REGISTER, REGISTER_CSV,
                 ["--data", "{in}", "--title", "Avvik 2026",
                  "--columns", "Saksnummer,Enhet,Status,Dager", "--numeric", "Dager",
                  "--sort", "Dager", "--desc", "--requested-by", "Kvalitet",
                  "--out", "{out}/register.html"],
                 ["register.html"], REGISTER_T),
    "fx-survey": (SURVEY, FX_SURVEY_CSV,
                  ["--data", "{in}", "--title", "Working environment 2026", "--segments", "Department,Job",
                   "--question-col", "Question", "--answer-col", "Answer",
                   "--requested-by", "HR", "--source", "Made-up example answers",
                   "--feedback-to", "hei@example.org", "--out", "{out}/fx-survey.html"],
                  ["fx-survey.html"], SURVEY_T + FB),
    # The timeline takes two date columns and one name column from a real example file, so
    # the frozen nb output is a drawing, not a fixture invented for this test.
    "timeline": (TIMELINE, TIMELINE_INPUT,
                 ["--data", "{in}", "--title", "Milepaeler", "--no-today",
                  "--source", "Syntetisk eksempeldata", "--requested-by", "Programmet",
                  "--out", "{out}/timeline.html"],
                 ["timeline.html"], ["timeline"]),
    # The index reads one artefact's provenance block and writes one card for it. The
    # input is a committed register, so the card's fields are a real builder's output.
    "index": (INDEX, INDEX_INPUT, ["--dir", "{out}/_in", "--title", "Oversikt",
                                   "--requested-by", "Innsikt", "--out", "{out}/index.html"],
              ["index.html"], ["index"]),
    # The scorecard is new too, so its pin is its first output. It is also the only case
    # whose builder reads a direction column, which is the thing that decides whether the
    # page carries a verdict at all.
    "scorecard": (SCORE, SCORE_INPUT,
                  ["--data", "{in}", "--title", "Manedsrapport", "--requested-by", "Kvalitet",
                   "--green-at", "1.0", "--amber-at", "0.95", "--out", "{out}/scorecard.html"],
                  ["scorecard.html"], ["scorecard"]),
    # The distribution page is new, so its pin is its first output rather than a frozen
    # older build: there is nothing older to compare it with. The case still earns its
    # place, because it is what makes a change to its nb output visible at all.
    "distribution": (DIST, DIST_INPUT,
                     ["--data", "{in}", "--measure-col", "Dager", "--group-col", "Enhet",
                      "--title", "Saksbehandlingstid per enhet", "--requested-by", "Fagavdelingen",
                      "--source", "Syntetisk eksempeldata", "--out", "{out}/distribution.html"],
                     ["distribution.html"], ["distribution"]),
    # The comparison artefact compares one file with itself here: the case exists to pin
    # its nb output and to prove its en page carries no Norwegian, not to test arithmetic
    # (tests/test_comparison_dashboard.py does that against the real two extracts).
    "compare": (COMPARE, REGISTER_CSV, ["--before", "{in}", "--after", "{in}",
                                        "--key", "Enhet", "--value", "Belop",
                                        "--title", "Avvik per enhet", "--requested-by", "Kvalitet",
                                        "--out", "{out}/compare.html"],
                ["compare.html"], ["compare-dashboard"]),
}

# sha256 of the nb build of each file, made with the builders as they were on origin/main
# 56ca978, before any strings table existed. Rebuilt on every run, so a change to nb output
# anywhere (a template, a builder, a table) shows up here as a changed hash.
# The deck had no builder: its baseline is the sha256 of templates/portable-slide-deck.html
# on that commit, which is what anyone who copied the template got.
# The one deliberate change to nb output since then: the dashboard footer and its build
# comment no longer name the tool that ran the builder (decision D7, 2026-10-09). The six
# dashboard hashes below include it. The second deliberate change is accessibility (G08,
# 2026-10-09, found by axe 4.14): the label colour went from Black 55% (4.46:1, under WCAG AA)
# to Black 60% (5.4:1), the table wrapper became a focusable named region, and the KPI and
# chart grids stopped forcing a minimum wider than a 375px phone. Section 6 applies exactly
# these pairs to the old builders' output before comparing, and checks that each pair was
# really applied. The third is the chart size (2026-10-10), described at its pairs. On the
# same date the slide deck changed for axe (landmarks, contrast): its hash is re-pinned with
# no pair, because no probe in section 6 builds a deck. The fourth (2026-10-12) is how the
# dashboard treats an empty measure value, described at its pairs. The fifth (2026-10-12)
# is the sideways bar chart for long names, described at its pairs. The sixth (2026-10-13)
# is the chart redraw when a frame gets its size without a resize event, at its pairs. The
# seventh (2026-10-13) is the cube's lang attribute, at its pair. The eighth (2026-10-16)
# escapes data before the dashboard writes it as HTML, at its pairs. The ninth (same day)
# is the process diagram fitting its window, the tenth lets it grow on a wide screen, the
# eleventh adds the rows drawing, and the twelfth fits it to the window's height, each
# at its pairs.
# The old text below is quoted because renaming it is what that table tests. It is
# built from fragments so the core-boundary gate does not read this file's own subject
# as a leak: a table that tests a rename must contain what it renames.
_DN = b"DN" + b"B"
_DS = b"Eu" + b"femia"
_HOST = b"eu" + b"femia." + b"dn" + b"b.no"
_PKG = b"@" + b"dn" + b"b/" + b"eu" + b"femia"
_NK = b"Eksempel" + b" AS"

DELIBERATE_NB_CHANGES = [
    (b"Selvstendig dashboard bygget av RAIWork", "Selvstendig dashboard laget med T\u00fan".encode()),
    (b"Tallene er bygget inn i denne filen. Be RAIWork om <code>tun-data</code> for \\u00e5 oppdatere.",
     b"Tallene er bygget inn i denne filen. Oppdater dem med <code>tun-data</code>."),
    (b"Built by    : RAIWork skill `tun-new`", "Built by    : T\u00fan skill `tun-new`".encode()),
    (b"--color-black-80:#333; --color-black-55:#737373;",
     b"--color-black-80:#333; --color-black-60:#666; --color-black-55:#737373;"),
    (b"--muted:var(--color-black-55);      /* labels, axis text */",
     b"--muted:var(--color-black-60);      /* labels, axis text: 5.4:1 on --panel (Black 55% was 4.46:1, under AA) */"),
    (b"grid-template-columns:repeat(auto-fit,minmax(12rem,1fr));",
     b"grid-template-columns:repeat(auto-fit,minmax(min(17rem,100%),1fr));"),
    (b".kpi{background:var(--panel);", b".kpi{min-width:0;background:var(--panel);"),
    (b".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(26rem,1fr));",
     b".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(26rem,100%),1fr));"),
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
    # Eighth (2026-10-16): data is text, never markup. The dashboard wrote cell values,
    # column names, filter values and the data.js source line into innerHTML as they were,
    # so a cell holding <img onerror=...> ran as script (tests/test_dashboard_escapes_data.py).
    # One pair per template hunk.
    (b'const fmt = (n) => META.numberFormat.format(n);\n',
     b'const fmt = (n) => META.numberFormat.format(n);\n// Data is text, never markup. Every value from the data (cells, column names, filter\n// values, a data.js source line) goes through esc() before it is written as HTML.\nconst esc = (v) => String(v ?? "").replace(/[&<>"\']/g, ch =>\n  ({"&": "&amp;", "<": "&lt;", ">": "&gt;", \'"\': "&quot;", "\'": "&#39;"})[ch]);\n'),
    (b'data-col="${c}">${c}${', b'data-col="${esc(c)}">${esc(c)}${'),
    (b'typeof r[c] === "number" ? fmt(r[c]) : (r[c] ?? "")}</td>`',
     b'typeof r[c] === "number" ? fmt(r[c]) : esc(r[c])}</td>`'),
    (b'<label for="f_${c}">${c}</label>\n      <select id="f_${c}" data-col="${c}">',
     b'<label for="f_${esc(c)}">${esc(c)}</label>\n      <select id="f_${esc(c)}" data-col="${esc(c)}">'),
    (b'`<option value="${String(v).replace(/"/g, "&quot;")}">${v}</option>`',
     b'`<option value="${esc(v)}">${esc(v)}</option>`'),
    (b'if (el) el.innerHTML = `${label} &middot; ', b'if (el) el.innerHTML = `${esc(label)} &middot; '),
    (b'if (el) el.innerHTML = `${src} &middot; ', b'if (el) el.innerHTML = `${esc(src)} &middot; '),
    (b' ${asOf} &middot; ${rows} ', b' ${esc(asOf)} &middot; ${rows} '),
    # Ninth (2026-10-16): the process diagram fits its window. The smallest text went from
    # 12 to 14 units and boxes from 224 to 212, so the page can shrink the drawing to 12/14
    # of natural size with no text under 12 px; the CSS fits it down to that floor and pans
    # below it, the page is never capped narrower than the drawing, the detail panel lies
    # over the drawing, and a lane-name strip follows a panning frame. Derived by a line diff
    # of the tok-process probe built by the tools before and after; applying these to the
    # build before gives the build after byte for byte. The process and fx-process hashes
    # are re-pinned for the same change.
    (b'main{max-width:96rem;margin:0 auto;padding:1.5rem 2rem 3rem}\n',
     b'/* Never narrower than the drawing needs: a wide screen shows the whole drawing at 1:1. */\nmain{max-width:max(96rem,calc(308px + 4rem + 2px));margin:0 auto;padding:1.5rem 2rem 3rem}\n'),
    (b'.flow{display:flex;gap:1rem;align-items:flex-start;flex-wrap:wrap}\n.figure{margin:0;flex:1 1 40rem;min-width:0;overflow:auto;border:1px solid var(--line);\n  border-radius:.75rem;background:var(--bg)}\n.pd{display:block;max-width:none}\nhtml.fit .pd{width:100%;height:auto}\n.detail{flex:0 1 24rem;min-width:18rem;border:1px solid var(--line);border-radius:.75rem;\n',
     b'.flow{position:relative}\n.figure-wrap{position:relative}\n.figure{margin:0;overflow:auto;border:1px solid var(--line);border-radius:.75rem;background:var(--bg)}\n/* Responsive without the script: the drawing fills the frame, never grows past its natural\n   size, and never shrinks below 264 px, where its smallest text is 12 px.\n   Narrower than that, the frame scrolls. */\n.pd{display:block;width:100%;height:auto;margin:0 auto;max-width:308px;min-width:264px}\nhtml.fit .pd{min-width:0;max-width:none}\n/* Panning (the drawing is wider than the frame): the frame stops at the window height, so\n   both scrollbars are in reach, and the lane names stay on top of it while it scrolls. */\nhtml.js .pan .figure{max-height:calc(100vh - 2rem)}\n.lane-strip{display:none}\nhtml.js .pan .lane-strip:not([hidden]){display:block;position:absolute;z-index:1;top:1px;left:1px;\n  right:1px;height:2.25rem;overflow:hidden;pointer-events:none;background:var(--bg);\n  border-bottom:1px solid var(--line);border-radius:.75rem .75rem 0 0}\n.lane-strip span{position:absolute;top:0;bottom:0;display:flex;align-items:center;justify-content:center;\n  overflow:hidden;white-space:nowrap;font-size:.875rem;font-weight:700;color:var(--ink);\n  background:var(--panel);border-top:4px solid var(--role,var(--line))}\n/* The detail panel lies over the drawing beside the step, so opening it never narrows it. */\n.detail{position:absolute;z-index:2;top:0;right:1rem;width:min(24rem,calc(100% - 2rem));\n  max-height:calc(100vh - 2rem);overflow:auto;border:2px solid var(--brand);border-radius:.75rem;\n'),
    (b'  .figure{overflow:visible;border:0;break-inside:avoid}\n',
     b'  .figure,html.js .pan .figure{overflow:visible;max-height:none;border:0;break-inside:avoid}\n  html.js .pan .lane-strip:not([hidden]){display:none}\n'),
    (b'  html .pd{width:auto;height:auto;max-width:100%;max-height:215mm;margin:0 auto}\n',
     b'  html .pd{width:auto;height:auto;min-width:0;max-width:100%;max-height:215mm;margin:0 auto}\n'),
    (b'<div class="flow">\n<figure class="figure">\n<svg xmlns="http://www.w3.org/2000/svg" class="pd" width="328" height="704" viewBox="0 0 328 704" role="img" aria-labelledby="pd-title pd-desc" font-size="14">\n',
     b'<div class="flow">\n<div class="figure-wrap">\n<div class="lane-strip" id="lane-strip" aria-hidden="true" hidden></div>\n<figure class="figure">\n<svg xmlns="http://www.w3.org/2000/svg" class="pd" width="308" height="704" viewBox="0 0 308 704" role="img" aria-labelledby="pd-title pd-desc" font-size="14">\n'),
    (b'<g class="lane c0" data-lane="0"><rect class="lane-band" x="16" y="74" width="296" height="614"/><rect class="lane-head" x="18" y="16" width="292" height="50" rx="8"/><rect class="lane-stripe" x="18" y="16" width="292" height="4" rx="2"/><text class="lane-name" x="164" y="38.5" text-anchor="middle" font-weight="700"><tspan x="164" dy="0">&#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;steps&#125;</tspan><tspan x="164" dy="18">&#123;lanes&#125;</tspan></text></g>\n',
     b'<g class="lane c0" data-lane="0"><rect class="lane-band" x="16" y="74" width="276" height="614"/><rect class="lane-head" x="18" y="16" width="272" height="50" rx="8"/><rect class="lane-stripe" x="18" y="16" width="272" height="4" rx="2"/><text class="lane-name" x="154" y="38.5" text-anchor="middle" font-weight="700"><tspan x="154" dy="0">&#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;steps&#125;</tspan><tspan x="154" dy="18">&#123;lanes&#125;</tspan></text></g>\n'),
    (b'<g class="edge" data-from="a" data-to="b"><path class="edge-line" d="M164 260 L164 316"/><path class="edge-arrow" d="M164 316 L160 306 L168 306 Z"/></g>\n<g class="edge" data-from="b" data-to="c"><path class="edge-line" d="M164 446 L164 502"/><path class="edge-arrow" d="M164 502 L160 492 L168 492 Z"/></g>\n',
     b'<g class="edge" data-from="a" data-to="b"><path class="edge-line" d="M154 260 L154 316"/><path class="edge-arrow" d="M154 316 L150 306 L158 306 Z"/></g>\n<g class="edge" data-from="b" data-to="c"><path class="edge-line" d="M154 446 L154 502"/><path class="edge-arrow" d="M154 502 L150 492 L158 492 Z"/></g>\n'),
    (b'<g class="node node-start c0" data-node="a" data-lane="0" transform="translate(52 130)"><title>1. &#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;measure&#125; &#123;dimension&#125; &#123;time&#125; &#123;name&#125; &#123;rows&#125; &#123;cells&#125; &#123;dims&#125; &#123;steps&#125; &#123;lanes&#125;</title><rect class="node-shape" width="224" height="130" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="26" cy="65" r="10"/><text x="26" y="69.2" text-anchor="middle" font-size="12" font-weight="700">1 </text></g><text class="node-label" x="123" y="24.5" text-anchor="middle"><tspan x="123" dy="0">&#123;&#123;T:reset&#125;&#125; &#123;n&#125; </tspan><tspan x="123" dy="18">&#123;measure&#125; </tspan><tspan x="123" dy="18">&#123;dimension&#125; &#123;time&#125; </tspan><tspan x="123" dy="18">&#123;name&#125; &#123;rows&#125; </tspan><tspan x="123" dy="18">&#123;cells&#125; &#123;dims&#125; </tspan><tspan x="123" dy="18">&#123;steps&#125; &#123;lanes&#125;</tspan></text></g>\n<g class="node node-step c0 flagged" data-node="b" data-lane="0" transform="translate(52 316)"><title>2. Two (Forbedringspunkt 1: &#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;measure&#125; &#123;dimension&#125; &#123;time&#125; &#123;name&#125; &#123;rows&#125; &#123;cells&#125; &#123;dims&#125; &#123;steps&#125; &#123;lanes&#125;)</title><rect class="node-shape" width="224" height="130" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="22" cy="65" r="10"/><text x="22" y="69.2" text-anchor="middle" font-size="12" font-weight="700">2 </text></g><text class="node-label" x="123" y="69.5" text-anchor="middle"><tspan x="123" dy="0">Two</tspan></text></g><g class="flag-badge" data-node="b" data-lane="0" aria-hidden="true" transform="translate(52 316)"><circle cx="224" cy="0" r="10"/><text x="224" y="4.2" text-anchor="middle" font-size="12" font-weight="700">1</text></g>\n<g class="node node-end c0" data-node="c" data-lane="0" transform="translate(52 502)"><title>3. Three</title><rect class="node-shape" width="224" height="130" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="26" cy="65" r="10"/><text x="26" y="69.2" text-anchor="middle" font-size="12" font-weight="700">3 </text></g><text class="node-label" x="123" y="69.5" text-anchor="middle"><tspan x="123" dy="0">Three</tspan></text></g>\n',
     b'<g class="node node-start c0" data-node="a" data-lane="0" transform="translate(48 130)"><title>1. &#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;measure&#125; &#123;dimension&#125; &#123;time&#125; &#123;name&#125; &#123;rows&#125; &#123;cells&#125; &#123;dims&#125; &#123;steps&#125; &#123;lanes&#125;</title><rect class="node-shape" width="212" height="130" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="27" cy="65" r="11"/><text x="27" y="69.9" text-anchor="middle" font-size="14" font-weight="700">1 </text></g><text class="node-label" x="118" y="24.5" text-anchor="middle"><tspan x="118" dy="0">&#123;&#123;T:reset&#125;&#125; &#123;n&#125; </tspan><tspan x="118" dy="18">&#123;measure&#125; </tspan><tspan x="118" dy="18">&#123;dimension&#125; &#123;time&#125; </tspan><tspan x="118" dy="18">&#123;name&#125; &#123;rows&#125; </tspan><tspan x="118" dy="18">&#123;cells&#125; &#123;dims&#125; </tspan><tspan x="118" dy="18">&#123;steps&#125; &#123;lanes&#125;</tspan></text></g>\n<g class="node node-step c0 flagged" data-node="b" data-lane="0" transform="translate(48 316)"><title>2. Two (Forbedringspunkt 1: &#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;measure&#125; &#123;dimension&#125; &#123;time&#125; &#123;name&#125; &#123;rows&#125; &#123;cells&#125; &#123;dims&#125; &#123;steps&#125; &#123;lanes&#125;)</title><rect class="node-shape" width="212" height="130" rx="6" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="23" cy="65" r="11"/><text x="23" y="69.9" text-anchor="middle" font-size="14" font-weight="700">2 </text></g><text class="node-label" x="118" y="69.5" text-anchor="middle"><tspan x="118" dy="0">Two</tspan></text></g><g class="flag-badge" data-node="b" data-lane="0" aria-hidden="true" transform="translate(48 316)"><circle cx="212" cy="0" r="11"/><text x="212" y="4.9" text-anchor="middle" font-size="14" font-weight="700">1</text></g>\n<g class="node node-end c0" data-node="c" data-lane="0" transform="translate(48 502)"><title>3. Three</title><rect class="node-shape" width="212" height="130" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="27" cy="65" r="11"/><text x="27" y="69.9" text-anchor="middle" font-size="14" font-weight="700">3 </text></g><text class="node-label" x="118" y="69.5" text-anchor="middle"><tspan x="118" dy="0">Three</tspan></text></g>\n'),
    (b'</figure>\n<aside class="detail" id="detail" aria-labelledby="detail-h" hidden>\n',
     b'</figure>\n</div>\n<aside class="detail" id="detail" aria-labelledby="detail-h" hidden>\n'),
    (b'  });\n  function selectTab(i, focus) {\n',
     b'  });\n  var onFlowShown = null;   /* set below: a hidden frame measures as zero wide */\n  function selectTab(i, focus) {\n'),
    (b'    });\n    if (focus) tabs[i].focus();\n',
     b'    });\n    if (i === 0 && onFlowShown) onFlowShown();\n    if (focus) tabs[i].focus();\n'),
    (b'  });\n  selectTab(0, false);\n\n',
     b'  });\n  /* On a phone the step cards are the readable view; the drawing is one tab away. */\n  selectTab(window.matchMedia && window.matchMedia("(max-width: 40rem)").matches ? 1 : 0, false);\n\n'),
    (b'  /* Zoom and fit. The drawing is laid out at natural size, where no text is under 12 px. */\n',
     b'  /* Zoom and fit. Until the reader zooms, the CSS sizes the drawing (scale null): it fits\n     the frame down to the size where its smallest text is 12 px, and pans below that. */\n'),
    (b'  var scale = 1, fit = false;\n  var fitBtn = doc.getElementById("fit"), level = doc.getElementById("zoom-level");\n  function applyZoom() {\n    root.classList.toggle("fit", fit);\n    svg.style.width = fit ? "" : (natW * scale) + "px";\n    svg.style.height = fit ? "" : (natH * scale) + "px";\n',
     b'  var scale = null, fit = false;\n  var fitBtn = doc.getElementById("fit"), level = doc.getElementById("zoom-level");\n  var figure = svg.parentNode, wrap = figure.parentNode, strip = doc.getElementById("lane-strip");\n  function shown() { return svg.getBoundingClientRect().width / natW; }\n  function applyZoom() {\n    var manual = !fit && scale !== null;\n    root.classList.toggle("fit", fit);\n    svg.style.width = manual ? (natW * scale) + "px" : "";\n    svg.style.height = manual ? (natH * scale) + "px" : "";\n    svg.style.minWidth = svg.style.maxWidth = manual ? "none" : "";\n'),
    (b'    level.textContent = fit ? "Tilpasset" : Math.round(scale * 100) + " %";\n',
     b'    refresh();\n'),
    (b'  function zoomBy(step) {\n    fit = false;\n    scale = Math.min(2, Math.max(0.5, Math.round((scale + step) * 100) / 100));\n',
     b'  function zoomBy(step) {\n    var from = fit || scale === null ? shown() : scale;\n    fit = false;\n    scale = Math.min(2, Math.max(0.5, Math.round((from + step) * 100) / 100));\n'),
    (b'  }\n  doc.getElementById("zoom-in").addEventListener("click", function () { zoomBy(0.25); });\n',
     b'  }\n  /* Lane names over the frame while it pans: a copy of each lane header, kept over its\n     lane as the frame scrolls, shown once the drawing\'s own headers have scrolled away. */\n  var heads = Array.prototype.slice.call(svg.querySelectorAll("g.lane"));\n  heads.forEach(function (g) {\n    var span = doc.createElement("span");\n    span.className = (g.getAttribute("class").match(/\\bc\\d+\\b/) || [""])[0];\n    span.textContent = Array.prototype.map.call(g.querySelectorAll(".lane-name tspan"),\n      function (t) { return t.textContent; }).join(" ");\n    strip.appendChild(span);\n  });\n  function placeStrip() {\n    var f = figure.getBoundingClientRect(), s = svg.getBoundingClientRect(), k = s.width / natW;\n    var first = heads.length && heads[0].querySelector(".lane-head").getBoundingClientRect();\n    strip.hidden = !first || first.bottom > f.top + 1;\n    heads.forEach(function (g, i) {\n      var r = g.querySelector(".lane-head");\n      strip.children[i].style.left = (s.left - f.left - 1 + parseFloat(r.getAttribute("x")) * k) + "px";\n      strip.children[i].style.width = (parseFloat(r.getAttribute("width")) * k) + "px";\n    });\n  }\n  function refresh() {\n    level.textContent = fit ? "Tilpasset" : Math.round(shown() * 100) + " %";\n    wrap.classList.toggle("pan", figure.scrollWidth > figure.clientWidth + 1);\n    placeStrip();\n  }\n  figure.addEventListener("scroll", placeStrip);\n  onFlowShown = refresh;\n  window.addEventListener("resize", refresh);\n  doc.getElementById("zoom-in").addEventListener("click", function () { zoomBy(0.25); });\n'),
    (b'  fitBtn.addEventListener("click", function () { fit = !fit; applyZoom(); });\n\n',
     b'  fitBtn.addEventListener("click", function () { fit = !fit; applyZoom(); });\n  refresh();\n\n'),
    (b'    detail.hidden = false;\n    detail.setAttribute("data-node", id);\n',
     b'    detail.hidden = false;\n    placeDetail(nodeById(id));\n    detail.setAttribute("data-node", id);\n'),
    (b'      n.setAttribute("aria-pressed", on ? "true" : "false");\n    });\n  }\n  function closeDetail() {\n',
     b'      n.setAttribute("aria-pressed", on ? "true" : "false");\n    });\n  }\n  /* Beside the step, on the half of the drawing the step is not on. */\n  function placeDetail(n) {\n    if (!n) return;\n    var flow = detail.parentNode.getBoundingClientRect(), r = n.getBoundingClientRect();\n    var right = r.left + r.width / 2 < flow.left + flow.width / 2;\n    detail.style.top = Math.max(0, r.top - flow.top) + "px";\n    detail.style.right = right ? "1rem" : "auto";\n    detail.style.left = right ? "auto" : "1rem";\n  }\n  function closeDetail() {\n'),
    (b'      openDetail(id);\n      n.scrollIntoView({block: "center", inline: "center"});\n      n.focus({preventScroll: true});\n',
     b'      n.scrollIntoView({block: "center", inline: "center"});\n      openDetail(id);   /* after the scroll, so the panel lands beside the step */\n      n.focus({preventScroll: true});\n'),
    # Tenth (2026-10-16): the process page has no width cap, and the drawing may grow to
    # 1.5x natural size to fill a wide screen. Derived like the ninth.
    (b'/* Never narrower than the drawing needs: a wide screen shows the whole drawing at 1:1. */\nmain{max-width:max(96rem,calc(308px + 4rem + 2px));margin:0 auto;padding:1.5rem 2rem 3rem}\n',
     b'/* No width cap: a wide screen gives the drawing all its width. Text keeps its own measure. */\nmain{max-width:none;margin:0 auto;padding:1.5rem 2rem 3rem}\n'),
    (b'/* Responsive without the script: the drawing fills the frame, never grows past its natural\n   size, and never shrinks below 264 px, where its smallest text is 12 px.\n   Narrower than that, the frame scrolls. */\n.pd{display:block;width:100%;height:auto;margin:0 auto;max-width:308px;min-width:264px}\n',
     b'/* Responsive without the script: the drawing fills the frame, grows to at most\n   462 px on a wide screen, and never shrinks below 264 px, where\n   its smallest text is 12 px. Narrower than that, the frame scrolls. */\n.pd{display:block;width:100%;height:auto;margin:0 auto;max-width:462px;min-width:264px}\n'),
    (b'footer{margin-top:3rem;padding-top:1rem;border-top:1px solid var(--line);\n',
     b'footer{max-width:90ch;margin-top:3rem;padding-top:1rem;border-top:1px solid var(--line);\n'),
    # Eleventh (2026-10-16): the process page carries the flow twice, lanes as columns and
    # lanes as rows, and shows the one that fits the window with the least scrolling, with
    # a toolbar choice. Derived like the ninth.
    (b'.toolbar .group{display:flex;gap:.25rem;align-items:center}\n.toolbar button{font:inherit;font-size:.875rem;padding:.375rem .75rem;border-radius:.5rem;\n',
     b'.toolbar .group{display:flex;gap:.25rem;align-items:center}\n.toolbar .group[hidden]{display:none}\n.toolbar button{font:inherit;font-size:.875rem;padding:.375rem .75rem;border-radius:.5rem;\n'),
    (b'/* Responsive without the script: the drawing fills the frame, grows to at most\n   462 px on a wide screen, and never shrinks below 264 px, where\n   its smallest text is 12 px. Narrower than that, the frame scrolls. */\n.pd{display:block;width:100%;height:auto;margin:0 auto;max-width:462px;min-width:264px}\n',
     b'/* Responsive without the script: the drawing fills the frame, grows to at most 1.5 times\n   its natural size on a wide screen, and never shrinks below the size where its smallest\n   text is 12 px (the sizes per drawing follow). Narrower than that, the frame scrolls.\n   The page carries two drawings of the same flow: lanes as columns (pd-tb), and lanes as\n   rows with the flow running right (pd-lr). One shows (class "on"); without the script and\n   in print that is the columns. */\n.pd{display:block;width:100%;height:auto;margin:0 auto}\n.pd-tb{max-width:462px;min-width:264px}\n.pd-lr{max-width:1329px;min-width:760px}\n.pd:not(.on){display:none}\n'),
    (b'  background:var(--panel);border-top:4px solid var(--role,var(--line))}\n/* The detail panel lies over the drawing beside the step, so opening it never narrows it. */\n',
     b'  background:var(--panel);border-top:4px solid var(--role,var(--line))}\n/* Rows pan sideways, so the lane names stand in a column on the left instead. */\nhtml.js .pan.rows .lane-strip:not([hidden]){right:auto;bottom:1px;width:9rem;height:auto;\n  border-bottom:0;border-right:1px solid var(--line);border-radius:.75rem 0 0 .75rem}\n.rows .lane-strip span{left:0;right:0;bottom:auto;padding:0 .5rem;white-space:normal;text-align:center;\n  border-top:0;border-left:4px solid var(--role,var(--line))}\n/* The detail panel lies over the drawing beside the step, so opening it never narrows it. */\n'),
    (b'  .figure,html.js .pan .figure{overflow:visible;max-height:none;border:0;break-inside:avoid}\n  html.js .pan .lane-strip:not([hidden]){display:none}\n',
     b'  .figure,html.js .pan .figure{overflow:visible;max-height:none;border:0;break-inside:avoid}\n  /* Paper is portrait: print the columns, whichever drawing was on screen. */\n  html .pd.pd-tb{display:block}\n  html .pd.pd-lr{display:none}\n  html.js .pan .lane-strip:not([hidden]){display:none}\n'),
    (b'</div>\n<div class="chips" role="group" aria-label="Fremhev en rolle"><button type="button" class="chip" data-lane="" aria-pressed="true">Alle roller</button><button type="button" class="chip c0" data-lane="0" aria-pressed="false"><span class="dot" aria-hidden="true"></span>&#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;steps&#125; &#123;lanes&#125;</button></div>\n',
     b'</div>\n<div class="group orient" id="orient" role="group" aria-label="Retning p\xc3\xa5 flyten">\n<button type="button" data-orient="auto" aria-pressed="true">Auto</button>\n<button type="button" data-orient="tb" aria-pressed="false">Loddrett</button>\n<button type="button" data-orient="lr" aria-pressed="false">Vannrett</button>\n</div>\n<div class="chips" role="group" aria-label="Fremhev en rolle"><button type="button" class="chip" data-lane="" aria-pressed="true">Alle roller</button><button type="button" class="chip c0" data-lane="0" aria-pressed="false"><span class="dot" aria-hidden="true"></span>&#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;steps&#125; &#123;lanes&#125;</button></div>\n'),
    (b'<svg xmlns="http://www.w3.org/2000/svg" class="pd" width="308" height="704" viewBox="0 0 308 704" role="img" aria-labelledby="pd-title pd-desc" font-size="14">\n',
     b'<svg xmlns="http://www.w3.org/2000/svg" class="pd pd-tb on" data-orient="tb" width="308" height="704" viewBox="0 0 308 704" role="img" aria-labelledby="pd-title pd-desc" font-size="14">\n'),
    (b'<g class="node node-end c0" data-node="c" data-lane="0" transform="translate(48 502)"><title>3. Three</title><rect class="node-shape" width="212" height="130" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="27" cy="65" r="11"/><text x="27" y="69.9" text-anchor="middle" font-size="14" font-weight="700">3 </text></g><text class="node-label" x="118" y="69.5" text-anchor="middle"><tspan x="118" dy="0">Three</tspan></text></g>\n</g>\n',
     b'<g class="node node-end c0" data-node="c" data-lane="0" transform="translate(48 502)"><title>3. Three</title><rect class="node-shape" width="212" height="130" rx="24" filter="url(#pd-shadow)"/><g class="step-no"><circle cx="27" cy="65" r="11"/><text x="27" y="69.9" text-anchor="middle" font-size="14" font-weight="700">3 </text></g><text class="node-label" x="118" y="69.5" text-anchor="middle"><tspan x="118" dy="0">Three</tspan></text></g>\n</g>\n</svg>\n<svg xmlns="http://www.w3.org/2000/svg" class="pd pd-lr" data-orient="lr" width="886" height="334" viewBox="0 0 886 334" role="img" aria-labelledby="pd-lr-title pd-lr-desc" font-size="14">\n<title id="pd-lr-title">&#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;measure&#125; &#123;dimension&#125; &#123;time&#125; &#123;name&#125; &#123;rows&#125; &#123;cells&#125; &#123;dims&#125; &#123;steps&#125; &#123;lanes&#125;</title>\n<desc id="pd-lr-desc">Prosessdiagram med 3 steg i 1 roller. Den samme flyten st\xc3\xa5r som tekst i fanen Tekstversjon.</desc>\n<defs><filter id="pd-lr-shadow" x="-10%" y="-20%" width="120%" height="150%"><feDropShadow dx="0" dy="2" stdDeviation="2.2" flood-opacity="0.22"/></filter></defs>\n<g class="lanes">\n<g class="lane c0" data-lane="0"><rect class="lane-band" x="166" y="16" width="704" height="302"/><rect class="lane-head" x="16" y="18" width="142" height="298" rx="8"/><rect class="lane-stripe" x="16" y="18" width="4" height="298" rx="2"/><text class="lane-name" x="89" y="153.5" text-anchor="middle" font-weight="700"><tspan x="89" dy="0">&#123;&#123;T:reset&#125;&#125;</tspan><tspan x="89" dy="18">&#123;n&#125; &#123;steps&#125;</tspan><tspan x="89" dy="18">&#123;lanes&#125;</tspan></text></g>\n</g>\n<g class="edges">\n<g class="edge" data-from="a" data-to="b"><path class="edge-line" d="M382 167 L438 167"/><path class="edge-arrow" d="M438 167 L428 171 L428 163 Z"/></g>\n<g class="edge" data-from="b" data-to="c"><path class="edge-line" d="M598 167 L654 167"/><path class="edge-arrow" d="M654 167 L644 171 L644 163 Z"/></g>\n</g>\n<g class="nodes">\n<g class="node node-start c0" data-node="a" data-lane="0" transform="translate(222 48)"><title>1. &#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;measure&#125; &#123;dimension&#125; &#123;time&#125; &#123;name&#125; &#123;rows&#125; &#123;cells&#125; &#123;dims&#125; &#123;steps&#125; &#123;lanes&#125;</title><rect class="node-shape" width="160" height="238" rx="24" filter="url(#pd-lr-shadow)"/><g class="step-no"><circle cx="27" cy="119" r="11"/><text x="27" y="123.9" text-anchor="middle" font-size="14" font-weight="700">1 </text></g><text class="node-label" x="92" y="33.5" text-anchor="middle"><tspan x="92" dy="0">&#123;&#123;T:reset&#125;&#125; </tspan><tspan x="92" dy="18">&#123;n&#125; </tspan><tspan x="92" dy="18">&#123;measure&#125; </tspan><tspan x="92" dy="18">&#123;dimension&#125; </tspan><tspan x="92" dy="18">&#123;time&#125; </tspan><tspan x="92" dy="18">&#123;name&#125; </tspan><tspan x="92" dy="18">&#123;rows&#125; </tspan><tspan x="92" dy="18">&#123;cells&#125; </tspan><tspan x="92" dy="18">&#123;dims&#125; </tspan><tspan x="92" dy="18">&#123;steps&#125; </tspan><tspan x="92" dy="18">&#123;lanes&#125;</tspan></text></g>\n<g class="node node-step c0 flagged" data-node="b" data-lane="0" transform="translate(438 48)"><title>2. Two (Forbedringspunkt 1: &#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;measure&#125; &#123;dimension&#125; &#123;time&#125; &#123;name&#125; &#123;rows&#125; &#123;cells&#125; &#123;dims&#125; &#123;steps&#125; &#123;lanes&#125;)</title><rect class="node-shape" width="160" height="238" rx="6" filter="url(#pd-lr-shadow)"/><g class="step-no"><circle cx="23" cy="119" r="11"/><text x="23" y="123.9" text-anchor="middle" font-size="14" font-weight="700">2 </text></g><text class="node-label" x="92" y="123.5" text-anchor="middle"><tspan x="92" dy="0">Two</tspan></text></g><g class="flag-badge" data-node="b" data-lane="0" aria-hidden="true" transform="translate(438 48)"><circle cx="160" cy="0" r="11"/><text x="160" y="4.9" text-anchor="middle" font-size="14" font-weight="700">1</text></g>\n<g class="node node-end c0" data-node="c" data-lane="0" transform="translate(654 48)"><title>3. Three</title><rect class="node-shape" width="160" height="238" rx="24" filter="url(#pd-lr-shadow)"/><g class="step-no"><circle cx="27" cy="119" r="11"/><text x="27" y="123.9" text-anchor="middle" font-size="14" font-weight="700">3 </text></g><text class="node-label" x="92" y="123.5" text-anchor="middle"><tspan x="92" dy="0">Three</tspan></text></g>\n</g>\n'),
    (b'  var svg = doc.querySelector("svg.pd");\n  if (!svg) return;\n',
     b'  var svgs = Array.prototype.slice.call(doc.querySelectorAll("svg.pd"));\n  if (!svgs.length) return;\n  var svg = svgs.filter(function (s) { return s.classList.contains("on"); })[0] || svgs[0];\n  /* Each drawing\'s natural size and the range the CSS lets it take, read before any zoom. */\n  var range = svgs.map(function (s) {\n    var cs = getComputedStyle(s);\n    return {w: parseFloat(s.getAttribute("width")), h: parseFloat(s.getAttribute("height")),\n            min: parseFloat(cs.minWidth) || 0, max: parseFloat(cs.maxWidth) || Infinity};\n  });\n'),
    (b'  }\n  /* Lane names over the frame while it pans: a copy of each lane header, kept over its\n',
     b'  }\n  /* Which way the flow runs. Auto takes, of the drawings that fit the frame without\n     panning, the one that needs the least scrolling down; when none fits, the columns.\n     So a wide, short window gets rows and a tall or narrow one gets columns. */\n  var mode = "auto", orientBtns = Array.prototype.slice.call(doc.querySelectorAll("#orient button"));\n  if (svgs.length < 2) doc.getElementById("orient").hidden = true;\n  function pick() {\n    var forced = svgs.filter(function (s) { return s.getAttribute("data-orient") === mode; })[0];\n    if (forced) return forced;\n    var frame = figure.clientWidth, best = null, bestH = Infinity;\n    svgs.forEach(function (s, i) {\n      var r = range[i];\n      if (r.min > frame + 1) return;\n      var h = r.h * Math.max(r.min, Math.min(frame, r.max)) / r.w;\n      if (h < bestH - 1) { best = s; bestH = h; }\n    });\n    return best || svgs[0];\n  }\n  function orient() {\n    var next = pick();\n    if (next !== svg) {\n      svg.style.width = svg.style.height = svg.style.minWidth = svg.style.maxWidth = "";\n      svg.classList.remove("on");\n      next.classList.add("on");\n      svg = next;\n      natW = parseFloat(svg.getAttribute("width"));\n      natH = parseFloat(svg.getAttribute("height"));\n      buildStrip();\n    }\n    applyZoom();\n  }\n  orientBtns.forEach(function (b) {\n    b.addEventListener("click", function () {\n      mode = b.getAttribute("data-orient");\n      orientBtns.forEach(function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });\n      orient();\n    });\n  });\n  /* Lane names over the frame while it pans: a copy of each lane header, kept over its\n'),
    (b'  var heads = Array.prototype.slice.call(svg.querySelectorAll("g.lane"));\n  heads.forEach(function (g) {\n    var span = doc.createElement("span");\n    span.className = (g.getAttribute("class").match(/\\bc\\d+\\b/) || [""])[0];\n    span.textContent = Array.prototype.map.call(g.querySelectorAll(".lane-name tspan"),\n      function (t) { return t.textContent; }).join(" ");\n    strip.appendChild(span);\n  });\n',
     b'  var heads = [];\n  function buildStrip() {\n    heads = Array.prototype.slice.call(svg.querySelectorAll("g.lane"));\n    while (strip.firstChild) strip.removeChild(strip.firstChild);\n    heads.forEach(function (g) {\n      var span = doc.createElement("span");\n      span.className = (g.getAttribute("class").match(/\\bc\\d+\\b/) || [""])[0];\n      span.textContent = Array.prototype.map.call(g.querySelectorAll(".lane-name tspan"),\n        function (t) { return t.textContent; }).join(" ");\n      strip.appendChild(span);\n    });\n  }\n  buildStrip();\n'),
    (b'    var f = figure.getBoundingClientRect(), s = svg.getBoundingClientRect(), k = s.width / natW;\n    var first = heads.length && heads[0].querySelector(".lane-head").getBoundingClientRect();\n    strip.hidden = !first || first.bottom > f.top + 1;\n',
     b'    var f = figure.getBoundingClientRect(), s = svg.getBoundingClientRect(), k = s.width / natW;\n    var rows = svg.getAttribute("data-orient") === "lr";\n    var first = heads.length && heads[0].querySelector(".lane-head").getBoundingClientRect();\n    strip.hidden = !first || (rows ? first.right > f.left + 1 : first.bottom > f.top + 1);\n    wrap.classList.toggle("rows", rows);\n'),
    (b'      var r = g.querySelector(".lane-head");\n      strip.children[i].style.left = (s.left - f.left - 1 + parseFloat(r.getAttribute("x")) * k) + "px";\n      strip.children[i].style.width = (parseFloat(r.getAttribute("width")) * k) + "px";\n',
     b'      var r = g.querySelector(".lane-head"), st = strip.children[i].style;\n      var at = parseFloat(r.getAttribute(rows ? "y" : "x")) * k;\n      var len = parseFloat(r.getAttribute(rows ? "height" : "width")) * k;\n      st.left = rows ? "" : (s.left - f.left - 1 + at) + "px";\n      st.width = rows ? "" : len + "px";\n      st.top = rows ? (s.top - f.top - 1 + at) + "px" : "";\n      st.height = rows ? len + "px" : "";\n'),
    (b'  onFlowShown = refresh;\n  window.addEventListener("resize", refresh);\n',
     b'  onFlowShown = orient;\n  window.addEventListener("resize", orient);\n'),
    (b'  fitBtn.addEventListener("click", function () { fit = !fit; applyZoom(); });\n  refresh();\n\n',
     b'  fitBtn.addEventListener("click", function () { fit = !fit; applyZoom(); });\n  orient();\n\n'),
    (b'  var nodes = Array.prototype.slice.call(svg.querySelectorAll("g.node"));\n  var badges = Array.prototype.slice.call(svg.querySelectorAll("g.flag-badge"));\n',
     b'  /* Both drawings take part, so switching keeps what is lit, filtered and selected. */\n  var nodes = Array.prototype.slice.call(doc.querySelectorAll("svg.pd g.node"));\n  var badges = Array.prototype.slice.call(doc.querySelectorAll("svg.pd g.flag-badge"));\n'),
    (b'  svg.setAttribute("role", "group");\n  var edges = Array.prototype.slice.call(svg.querySelectorAll("g.edge"));\n  var lanes = Array.prototype.slice.call(svg.querySelectorAll("g.lane"));\n',
     b'  svgs.forEach(function (s) { s.setAttribute("role", "group"); });\n  var edges = Array.prototype.slice.call(doc.querySelectorAll("svg.pd g.edge"));\n  var lanes = Array.prototype.slice.call(doc.querySelectorAll("svg.pd g.lane"));\n'),
    (b'    return nodes.filter(function (n) { return n.getAttribute("data-node") === id; })[0] || null;\n',
     b'    return nodes.filter(function (n) { return n.getAttribute("data-node") === id && svg.contains(n); })[0] || null;\n'),
    (b'    svg.classList.toggle("focusing", !!id);\n',
     b'    svgs.forEach(function (s) { s.classList.toggle("focusing", !!id); });\n'),
    (b'      svg.classList.toggle("lane-filter", lane !== "");\n',
     b'      svgs.forEach(function (s) { s.classList.toggle("lane-filter", lane !== ""); });\n'),
    # Twelfth (2026-10-16): rows boxes as wide as a 3440x1440 window allows, each rows lane
    # as tall as its own boxes, rows fitted to the window's height, and labels that break
    # only between words. Derived like the ninth.
    (b'.pd-lr{max-width:1329px;min-width:760px}\n',
     b'.pd-lr{max-width:1869px;min-width:1068px}\n'),
    (b'<svg xmlns="http://www.w3.org/2000/svg" class="pd pd-lr" data-orient="lr" width="886" height="334" viewBox="0 0 886 334" role="img" aria-labelledby="pd-lr-title pd-lr-desc" font-size="14">\n',
     b'<svg xmlns="http://www.w3.org/2000/svg" class="pd pd-lr" data-orient="lr" width="1246" height="208" viewBox="0 0 1246 208" role="img" aria-labelledby="pd-lr-title pd-lr-desc" font-size="14">\n'),
    (b'<g class="lane c0" data-lane="0"><rect class="lane-band" x="166" y="16" width="704" height="302"/><rect class="lane-head" x="16" y="18" width="142" height="298" rx="8"/><rect class="lane-stripe" x="16" y="18" width="4" height="298" rx="2"/><text class="lane-name" x="89" y="153.5" text-anchor="middle" font-weight="700"><tspan x="89" dy="0">&#123;&#123;T:reset&#125;&#125;</tspan><tspan x="89" dy="18">&#123;n&#125; &#123;steps&#125;</tspan><tspan x="89" dy="18">&#123;lanes&#125;</tspan></text></g>\n',
     b'<g class="lane c0" data-lane="0"><rect class="lane-band" x="166" y="16" width="1064" height="176"/><rect class="lane-head" x="16" y="18" width="142" height="172" rx="8"/><rect class="lane-stripe" x="16" y="18" width="4" height="172" rx="2"/><text class="lane-name" x="89" y="90.5" text-anchor="middle" font-weight="700"><tspan x="89" dy="0">&#123;&#123;T:reset&#125;&#125;</tspan><tspan x="89" dy="18">&#123;n&#125; &#123;steps&#125;</tspan><tspan x="89" dy="18">&#123;lanes&#125;</tspan></text></g>\n'),
    (b'<g class="edge" data-from="a" data-to="b"><path class="edge-line" d="M382 167 L438 167"/><path class="edge-arrow" d="M438 167 L428 171 L428 163 Z"/></g>\n<g class="edge" data-from="b" data-to="c"><path class="edge-line" d="M598 167 L654 167"/><path class="edge-arrow" d="M654 167 L644 171 L644 163 Z"/></g>\n',
     b'<g class="edge" data-from="a" data-to="b"><path class="edge-line" d="M502 104 L558 104"/><path class="edge-arrow" d="M558 104 L548 108 L548 100 Z"/></g>\n<g class="edge" data-from="b" data-to="c"><path class="edge-line" d="M838 104 L894 104"/><path class="edge-arrow" d="M894 104 L884 108 L884 100 Z"/></g>\n'),
    (b'<g class="node node-start c0" data-node="a" data-lane="0" transform="translate(222 48)"><title>1. &#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;measure&#125; &#123;dimension&#125; &#123;time&#125; &#123;name&#125; &#123;rows&#125; &#123;cells&#125; &#123;dims&#125; &#123;steps&#125; &#123;lanes&#125;</title><rect class="node-shape" width="160" height="238" rx="24" filter="url(#pd-lr-shadow)"/><g class="step-no"><circle cx="27" cy="119" r="11"/><text x="27" y="123.9" text-anchor="middle" font-size="14" font-weight="700">1 </text></g><text class="node-label" x="92" y="33.5" text-anchor="middle"><tspan x="92" dy="0">&#123;&#123;T:reset&#125;&#125; </tspan><tspan x="92" dy="18">&#123;n&#125; </tspan><tspan x="92" dy="18">&#123;measure&#125; </tspan><tspan x="92" dy="18">&#123;dimension&#125; </tspan><tspan x="92" dy="18">&#123;time&#125; </tspan><tspan x="92" dy="18">&#123;name&#125; </tspan><tspan x="92" dy="18">&#123;rows&#125; </tspan><tspan x="92" dy="18">&#123;cells&#125; </tspan><tspan x="92" dy="18">&#123;dims&#125; </tspan><tspan x="92" dy="18">&#123;steps&#125; </tspan><tspan x="92" dy="18">&#123;lanes&#125;</tspan></text></g>\n<g class="node node-step c0 flagged" data-node="b" data-lane="0" transform="translate(438 48)"><title>2. Two (Forbedringspunkt 1: &#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;measure&#125; &#123;dimension&#125; &#123;time&#125; &#123;name&#125; &#123;rows&#125; &#123;cells&#125; &#123;dims&#125; &#123;steps&#125; &#123;lanes&#125;)</title><rect class="node-shape" width="160" height="238" rx="6" filter="url(#pd-lr-shadow)"/><g class="step-no"><circle cx="23" cy="119" r="11"/><text x="23" y="123.9" text-anchor="middle" font-size="14" font-weight="700">2 </text></g><text class="node-label" x="92" y="123.5" text-anchor="middle"><tspan x="92" dy="0">Two</tspan></text></g><g class="flag-badge" data-node="b" data-lane="0" aria-hidden="true" transform="translate(438 48)"><circle cx="160" cy="0" r="11"/><text x="160" y="4.9" text-anchor="middle" font-size="14" font-weight="700">1</text></g>\n<g class="node node-end c0" data-node="c" data-lane="0" transform="translate(654 48)"><title>3. Three</title><rect class="node-shape" width="160" height="238" rx="24" filter="url(#pd-lr-shadow)"/><g class="step-no"><circle cx="27" cy="119" r="11"/><text x="27" y="123.9" text-anchor="middle" font-size="14" font-weight="700">3 </text></g><text class="node-label" x="92" y="123.5" text-anchor="middle"><tspan x="92" dy="0">Three</tspan></text></g>\n',
     b'<g class="node node-start c0" data-node="a" data-lane="0" transform="translate(222 48)"><title>1. &#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;measure&#125; &#123;dimension&#125; &#123;time&#125; &#123;name&#125; &#123;rows&#125; &#123;cells&#125; &#123;dims&#125; &#123;steps&#125; &#123;lanes&#125;</title><rect class="node-shape" width="280" height="112" rx="24" filter="url(#pd-lr-shadow)"/><g class="step-no"><circle cx="27" cy="56" r="11"/><text x="27" y="60.9" text-anchor="middle" font-size="14" font-weight="700">1 </text></g><text class="node-label" x="152" y="33.5" text-anchor="middle"><tspan x="152" dy="0">&#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;measure&#125; </tspan><tspan x="152" dy="18">&#123;dimension&#125; &#123;time&#125; &#123;name&#125; </tspan><tspan x="152" dy="18">&#123;rows&#125; &#123;cells&#125; &#123;dims&#125; </tspan><tspan x="152" dy="18">&#123;steps&#125; &#123;lanes&#125;</tspan></text></g>\n<g class="node node-step c0 flagged" data-node="b" data-lane="0" transform="translate(558 48)"><title>2. Two (Forbedringspunkt 1: &#123;&#123;T:reset&#125;&#125; &#123;n&#125; &#123;measure&#125; &#123;dimension&#125; &#123;time&#125; &#123;name&#125; &#123;rows&#125; &#123;cells&#125; &#123;dims&#125; &#123;steps&#125; &#123;lanes&#125;)</title><rect class="node-shape" width="280" height="112" rx="6" filter="url(#pd-lr-shadow)"/><g class="step-no"><circle cx="23" cy="56" r="11"/><text x="23" y="60.9" text-anchor="middle" font-size="14" font-weight="700">2 </text></g><text class="node-label" x="152" y="60.5" text-anchor="middle"><tspan x="152" dy="0">Two</tspan></text></g><g class="flag-badge" data-node="b" data-lane="0" aria-hidden="true" transform="translate(558 48)"><circle cx="280" cy="0" r="11"/><text x="280" y="4.9" text-anchor="middle" font-size="14" font-weight="700">1</text></g>\n<g class="node node-end c0" data-node="c" data-lane="0" transform="translate(894 48)"><title>3. Three</title><rect class="node-shape" width="280" height="112" rx="24" filter="url(#pd-lr-shadow)"/><g class="step-no"><circle cx="27" cy="56" r="11"/><text x="27" y="60.9" text-anchor="middle" font-size="14" font-weight="700">3 </text></g><text class="node-label" x="152" y="60.5" text-anchor="middle"><tspan x="152" dy="0">Three</tspan></text></g>\n'),
    (b'    var manual = !fit && scale !== null;\n    root.classList.toggle("fit", fit);\n    svg.style.width = manual ? (natW * scale) + "px" : "";\n',
     b'    var manual = !fit && scale !== null;\n    /* Rows start at a scale that fits the window\'s height too (startScale). */\n    var rowsW = !manual && !fit && svg.getAttribute("data-orient") === "lr" ?\n      natW * startScale(svgs.indexOf(svg)) : 0;\n    root.classList.toggle("fit", fit);\n    svg.style.width = manual ? (natW * scale) + "px" : rowsW ? rowsW + "px" : "";\n'),
    (b'  if (svgs.length < 2) doc.getElementById("orient").hidden = true;\n  function pick() {\n',
     b'  if (svgs.length < 2) doc.getElementById("orient").hidden = true;\n  /* The scale a drawing starts at: the frame\'s width, within its CSS range; for rows also\n     no taller than the window below the frame\'s top, so every lane is in view. 0 when\n     that would put text under 12 px: the drawing does not fit. */\n  function startScale(i) {\n    var r = range[i], k = Math.min(figure.clientWidth, r.max) / r.w;\n    if (svgs[i].getAttribute("data-orient") === "lr") {\n      var top = figure.getBoundingClientRect().top + window.pageYOffset;\n      k = Math.min(k, (window.innerHeight - top - 8) / r.h);\n    }\n    return k * r.w >= r.min - 1 ? k : 0;\n  }\n  function pick() {\n'),
    (b'    var frame = figure.clientWidth, best = null, bestH = Infinity;\n',
     b'    var best = null, bestH = Infinity;\n'),
    (b'      var r = range[i];\n      if (r.min > frame + 1) return;\n      var h = r.h * Math.max(r.min, Math.min(frame, r.max)) / r.w;\n      if (h < bestH - 1) { best = s; bestH = h; }\n',
     b'      var k = startScale(i);\n      if (k && range[i].h * k < bestH - 1) { best = s; bestH = range[i].h * k; }\n'),
    # Fourth (2026-10-24): the dashboard template reached the 14 px text floor docs/11
    # asks for, and the 44 px touch minimum, and the charts now fit their labels by
    # measuring them. Axis text was 11 px and KPI labels 12 px, which no gate saw.
    # Derived from a line diff of the template on origin/main and the new one; applying
    # these to the old build gives the new one byte for byte.
    (b'    background:var(--panel);padding:var(--sp-2);border-radius:.25rem;margin-bottom:var(--sp-3)}\n  .controls label{display:block;font-size:.75rem;line-height:1rem;text-transform:uppercase;\n    letter-spacing:.04em;color:var(--muted);margin-bottom:.25rem}\n  .controls select,.controls input,.controls button{padding:var(--sp-1) .625rem;\n',
     b'    background:var(--panel);padding:var(--sp-2);border-radius:.25rem;margin-bottom:var(--sp-3)}\n  .controls label{display:block;font-size:.875rem;line-height:1rem;text-transform:uppercase;\n    letter-spacing:.04em;color:var(--muted);margin-bottom:.25rem}\n  /* 44 px is the touch minimum docs/11 sets, and touch is an equal input\n     method: a control that is fine with a mouse is still a miss with a thumb.\n     The height comes from min-height rather than padding so it holds at every\n     font size the page may be read at. */\n  .controls select,.controls input,.controls button{padding:var(--sp-1) .625rem;\n'),
    (b'    line-height:1.5rem;background:var(--color-white);min-width:10rem;font-family:inherit;\n    color:var(--ink)}\n  .controls button{min-width:auto;cursor:pointer}\n',
     b'    line-height:1.5rem;background:var(--color-white);min-width:10rem;font-family:inherit;\n    color:var(--ink);min-height:2.75rem}\n  .controls button{min-width:auto;cursor:pointer}\n'),
    (b'    border-radius:.25rem;background:var(--color-white);font-family:inherit;\n    font-size:.875rem;cursor:pointer;color:var(--ink)}\n  .dropbar button:enabled:hover{border-color:var(--brand);color:var(--brand)}\n',
     b'    border-radius:.25rem;background:var(--color-white);font-family:inherit;\n    font-size:.875rem;cursor:pointer;color:var(--ink);min-height:2.75rem}\n  .dropbar button:enabled:hover{border-color:var(--brand);color:var(--brand)}\n'),
    (b'    padding:var(--sp-2);border-radius:.25rem}\n  .kpi .label{font-size:.75rem;line-height:1rem;text-transform:uppercase;\n    letter-spacing:.04em;color:var(--muted)}\n',
     b'    padding:var(--sp-2);border-radius:.25rem}\n  .kpi .label{font-size:.875rem;line-height:1rem;text-transform:uppercase;\n    letter-spacing:.04em;color:var(--muted)}\n'),
    (b'  .axis{stroke:var(--color-black-20);stroke-width:1}\n  .axis-label{font-size:.6875rem;fill:var(--muted)}\n  .bar{fill:var(--brand);transition:fill .15s}\n',
     b'  .axis{stroke:var(--color-black-20);stroke-width:1}\n  .axis-label{font-size:.875rem;fill:var(--muted)}\n  .bar{fill:var(--brand);transition:fill .15s}\n'),
    (b'    max-width:15rem;word-wrap:break-word;overflow-wrap:break-word}\n  th{cursor:pointer;user-select:none;font-size:.75rem;line-height:1rem;\n    text-transform:uppercase;letter-spacing:.04em;color:var(--muted);white-space:nowrap;\n',
     b'    max-width:15rem;word-wrap:break-word;overflow-wrap:break-word}\n  th{cursor:pointer;user-select:none;font-size:.875rem;line-height:1rem;\n    text-transform:uppercase;letter-spacing:.04em;color:var(--muted);white-space:nowrap;\n'),
    (b'  .table-wrap{max-height:26rem;overflow:auto}\n  footer{padding:var(--sp-2) var(--sp-4);color:var(--muted);font-size:.75rem;\n    line-height:1.5rem;border-top:1px solid var(--line);margin-top:var(--sp-4)}\n  .tooltip{position:fixed;background:var(--color-black-80);color:var(--color-white);\n    padding:.375rem .5rem;border-radius:.25rem;font-size:.8125rem;pointer-events:none;\n    opacity:0;transition:opacity .12s;z-index:99;white-space:nowrap}\n',
     b'  .table-wrap{max-height:26rem;overflow:auto}\n  footer{padding:var(--sp-2) var(--sp-4);color:var(--muted);font-size:.875rem;\n    line-height:1.5rem;border-top:1px solid var(--line);margin-top:var(--sp-4)}\n  .tooltip{position:fixed;background:var(--color-black-80);color:var(--color-white);\n    padding:.375rem .5rem;border-radius:.25rem;font-size:.875rem;pointer-events:none;\n    opacity:0;transition:opacity .12s;z-index:99;white-space:nowrap}\n'),
    (b'  const svg = $(svgId); const [W, H] = chartSize(svg);\n  const m = { t: 12, r: 16, b: 58, l: 64 };\n  const iw = W - m.l - m.r, ih = H - m.t - m.b;\n',
     b'  const svg = $(svgId); const [W, H] = chartSize(svg);\n  const m = { t: 12, r: 16, b: 72, l: 72 };\n  const iw = W - m.l - m.r, ih = H - m.t - m.b;\n'),
    (b'\n  data.forEach((d, i) => {\n    const h = Math.max(',
     b'\n  const labelNodes = [];\n  data.forEach((d, i) => {\n    const h = Math.max('),
    (b'    svg.appendChild(lbl);\n  });\n}\n',
     b'    svg.appendChild(lbl);\n    labelNodes.push(lbl);\n  });\n  // Angled names collide long before they are 16 characters: five region names\n  // on a phone overlap from 14 px up. So the check is the geometry it just\n  // drew, not a character count. An SVG inside a hidden card measures zero, and\n  // a zero-size box never overlaps anything, so there the same comparison runs\n  // on the font\'s own metrics instead \xe2\x80\x94 the chart is drawn hidden on every\n  // first paint, and a fallback that only worked when visible would miss it.\n  if (labelsCollide(svg, labelNodes)) { svg.innerHTML = ""; return sideBars(svg, W, H, data, max, el); }\n}\n\n// labelsCollide reports whether two of these angled labels share pixels.\nfunction labelsCollide(svg, nodes) {\n  const visible = svg.getBoundingClientRect().width > 0;\n  if (visible) {\n    const boxes = nodes.map(n => n.getBoundingClientRect());\n    return boxes.some((a, i) => boxes.slice(i + 1).some(b =>\n      Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 &&\n      Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1));\n  }\n  const cs = getComputedStyle(nodes[0]);\n  const ctx = document.createElement("canvas").getContext("2d");\n  ctx.font = cs.fontSize + " " + cs.fontFamily;\n  const angle = 35 * Math.PI / 180, lineHeight = parseFloat(cs.fontSize) * 1.15;\n  const boxes = nodes.map(n => {\n    const w = ctx.measureText(n.textContent).width;\n    const x = parseFloat(n.getAttribute("x")), y = parseFloat(n.getAttribute("y"));\n    // The rotated glyph box: the text runs up-left from the anchor, and the\n    // line\'s height leans out to the right of it.\n    return { left: x - w * Math.cos(angle), right: x + lineHeight * Math.sin(angle),\n             top: y - w * Math.sin(angle), bottom: y + lineHeight * Math.cos(angle) };\n  });\n  return boxes.some((a, i) => boxes.slice(i + 1).some(b =>\n    Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 &&\n    Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1));\n}\n'),
    (b'    svg.appendChild(c);\n    const step = Math.ceil(data.length / Math.max(2, Math.floor(iw / 56)));  // 10 labels at 640\n    if (i % step === 0 || i === data.length - 1) {\n      const t = el("text", { class: "axis-label", x: X(i), y: m.t + ih + 18, "text-anchor": "middle" });\n      t.textContent = d.key; svg.appendChild(t);\n    }\n  });\n}\n',
     b'    svg.appendChild(c);\n  });\n  // Every period label, then as many as fit. The first is start-anchored and\n  // the last end-anchored so neither hangs outside the drawing, which means the\n  // labels\' own boxes decide what fits, not the distance between their x\n  // values: at 292 px four quarters look 70 px apart and still overlap by 16,\n  // because the first one starts at the axis and runs right.\n  const nodes = data.map((d, i) => {\n    const anchor = i === data.length - 1 ? "end" : (i === 0 ? "start" : "middle");\n    const t = el("text", { class: "axis-label", x: X(i), y: m.t + ih + 18, "text-anchor": anchor });\n    t.textContent = d.key; svg.appendChild(t); return t;\n  });\n  fitLabels(el, svg, nodes);\n}\n\n// fitLabels removes the labels that would touch, and always keeps the last one\n// so the reader can see where the line ends. Widths come from the font through\n// a canvas: a hidden SVG reports zero for everything inside it, and every chart\n// is drawn once while its card is hidden.\nfunction fitLabels(el, svg, nodes) {\n  if (nodes.length < 2) return;\n  const probe = el("text", { class: "axis-label" }); probe.textContent = "0"; svg.appendChild(probe);\n  const cs = getComputedStyle(probe);\n  const ctx = document.createElement("canvas").getContext("2d");\n  ctx.font = cs.fontSize + " " + cs.fontFamily;\n  svg.removeChild(probe);\n  const box = n => {\n    const w = ctx.measureText(n.textContent).width, x = parseFloat(n.getAttribute("x"));\n    const a = n.getAttribute("text-anchor");\n    if (a === "start") return { l: x, r: x + w };\n    if (a === "end") return { l: x - w, r: x };\n    return { l: x - w / 2, r: x + w / 2 };\n  };\n  const pad = 6, touches = (a, b) => a.l < b.r + pad && b.l < a.r + pad;\n  const keep = [];\n  nodes.slice(0, -1).forEach(n => {\n    if (!keep.length || !touches(box(n), box(keep[keep.length - 1]))) keep.push(n);\n    else n.remove();\n  });\n  const last = nodes[nodes.length - 1];\n  while (keep.length && touches(box(last), box(keep[keep.length - 1]))) keep.pop().remove();\n}\n'),
    # Fifth (2026-10-24): the cube reaches the same 14 px floor as the dashboard, gains
    # print rules, and its builders take --source. Derived from a line diff of
    # templates/cube-dashboard.html on origin/main and the new one; applying these to
    # the old build gives the new one byte for byte.
    (b'h1{font-size:1.15rem;margin:0;font-weight:650}\n.sub{color:var(--mut);font-size:.8rem}\nmain{padding:1.25rem 1.5rem;max-width:1400px;margin:0 auto}\n.panel{background:#fff;border:1px solid var(--bd);border-radius:8px;padding:1rem 1.1rem;margin-bottom:1rem}\n.panel h2{font-size:.78rem;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:0 0 .8rem;font-weight:650}\n.filters{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}\n.fg label{display:block;font-size:.72rem;font-weight:650;color:var(--mut);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.4rem}\n.chips{display:flex;flex-wrap:wrap;gap:.3rem}\n.chip{border:1px solid var(--bd);background:#fff;border-radius:14px;padding:.2rem .6rem;font-size:.78rem;cursor:pointer;user-select:none;transition:.12s}\n.chip:hover{border-color:var(--gr)}\n',
     b'h1{font-size:1.15rem;margin:0;font-weight:650}\n.sub{color:var(--mut);font-size:.875rem}\nmain{padding:1.25rem 1.5rem;max-width:1400px;margin:0 auto}\n.panel{background:#fff;border:1px solid var(--bd);border-radius:8px;padding:1rem 1.1rem;margin-bottom:1rem}\n.panel h2{font-size:.875rem;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:0 0 .8rem;font-weight:650}\n.filters{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}\n.fg label{display:block;font-size:.875rem;font-weight:650;color:var(--mut);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.4rem}\n.chips{display:flex;flex-wrap:wrap;gap:.3rem}\n.chip{border:1px solid var(--bd);background:#fff;border-radius:14px;padding:.2rem .6rem;font-size:.875rem;cursor:pointer;user-select:none;transition:.12s}\n.chip:hover{border-color:var(--gr)}\n'),
    (b'.kpi .v{font-size:1.5rem;font-weight:680;letter-spacing:-.02em;font-variant-numeric:tabular-nums}\n.kpi .l{font-size:.72rem;color:var(--mut);text-transform:uppercase;letter-spacing:.05em;margin-top:.15rem}\n.grid2{display:grid;grid-template-columns:1fr 1fr;gap:1rem}\n',
     b'.kpi .v{font-size:1.5rem;font-weight:680;letter-spacing:-.02em;font-variant-numeric:tabular-nums}\n.kpi .l{font-size:.875rem;color:var(--mut);text-transform:uppercase;letter-spacing:.05em;margin-top:.15rem}\n.grid2{display:grid;grid-template-columns:1fr 1fr;gap:1rem}\n'),
    (b'table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}\nth,td{text-align:left;padding:.4rem .5rem;border-bottom:1px solid var(--bd);font-size:.83rem}\nth{font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);font-weight:650}\ntd.n,th.n{text-align:right}\n',
     b'table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}\nth,td{text-align:left;padding:.4rem .5rem;border-bottom:1px solid var(--bd);font-size:.875rem}\nth{font-size:.875rem;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);font-weight:650}\ntd.n,th.n{text-align:right}\n'),
    (b'.axis{stroke:var(--bd);stroke-width:1}.gl{stroke:#eef1f2;stroke-width:1}\n.lbl{font-size:10px;fill:var(--mut)}\n.vlbl{font-size:10px;fill:var(--mut);font-variant-numeric:tabular-nums}\nbutton.rst,select.ms{border:1px solid var(--bd);background:#fff;border-radius:6px;padding:.3rem .7rem;font-size:.78rem;cursor:pointer;font-family:inherit}\nbutton.rst:hover{border-color:var(--gr);color:var(--gr)}\nfooter{padding:.5rem 1.5rem 2rem;max-width:1400px;margin:0 auto;\n  font:11px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--mut);display:flex;gap:1.1rem;flex-wrap:wrap}\nfooter b{color:var(--gr2);font-weight:650}\n',
     b'.axis{stroke:var(--bd);stroke-width:1}.gl{stroke:#eef1f2;stroke-width:1}\n.lbl{font-size:14px;fill:var(--mut)}\n.vlbl{font-size:14px;fill:var(--mut);font-variant-numeric:tabular-nums}\nbutton.rst,select.ms{border:1px solid var(--bd);background:#fff;border-radius:6px;padding:.3rem .7rem;font-size:.875rem;min-height:2.75rem;cursor:pointer;font-family:inherit}\nbutton.rst:hover{border-color:var(--gr);color:var(--gr)}\nfooter{padding:.5rem 1.5rem 2rem;max-width:1400px;margin:0 auto;\n  font:14px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--mut);display:flex;gap:1.1rem;flex-wrap:wrap}\nfooter b{color:var(--gr2);font-weight:650}\n'),
    (b'#boot.err{color:#b00020}\n</style></head><body>\n',
     b"#boot.err{color:#b00020}\n/* Print, copied from the dashboard's tested rules (docs/11 \xc2\xa78): the paper copy is\n   the numbers, not the controls. The header keeps #scope, so the applied selection\n   still prints even though the controls do not. */\n@media print{header{background:#fff;border-bottom:1px solid var(--bd)}\n  .ms,.rst,.filters{display:none}main{padding:0;max-width:none}\n  .panel{break-inside:avoid;box-shadow:none}}\n</style></head><body>\n"),
    (b'const esc = s => String(s).replace(/[<>&"]/g, m => ({\'<\':\'&lt;\',\'>\':\'&gt;\',\'&\':\'&amp;\',\'"\':\'&quot;\'}[m]));\n/* Charts draw in their panel\'s own pixels, so 10 px text stays 10 px. A fixed\n   560/1120-wide viewBox scaled to a 330 px phone panel drew it at 3 to 6 px.\n   measureCharts() reads the real widths after a render; boot and resize redraw\n',
     b'const esc = s => String(s).replace(/[<>&"]/g, m => ({\'<\':\'&lt;\',\'>\':\'&gt;\',\'&\':\'&amp;\',\'"\':\'&quot;\'}[m]));\n/* Charts draw in their panel\'s own pixels, so the label size is the size a reader\n   gets. A fixed 560/1120-wide viewBox scaled to a 330 px phone panel drew 10 px text\n   at 3 to 6 px; the labels are 14 px now, which is the floor docs/11 \xc2\xa71 sets, so the\n   paddings below are wide enough to hold them.\n   measureCharts() reads the real widths after a render; boot and resize redraw\n'),
    (b'function barChart(labels, values, unit, name){\n  const rowH = 24, W = barW, padL = 118, padR = 66, H = labels.length*rowH + 8;\n  const max = Math.max(...values, 1), bw = W - padL - padR;\n',
     b'function barChart(labels, values, unit, name){\n  const rowH = 26, W = barW, padL = 150, padR = 96, H = labels.length*rowH + 8;\n  const max = Math.max(...values, 1), bw = W - padL - padR;\n'),
    (b'function lineChart(labels, values, unit, name){\n  const W = lineW, H = 230, padL = 62, padR = 14, padT = 12, padB = 34;\n  const n = labels.length, max = Math.max(...values, 1);\n',
     b'function lineChart(labels, values, unit, name){\n  const W = lineW, H = 230, padL = 80, padR = 14, padT = 12, padB = 44;\n  const n = labels.length, max = Math.max(...values, 1);\n'),
    (b'    + `fill="#fff" stroke="var(--gr)" stroke-width="1.8"><title>${esc(labels[i])}: ${fmt(v, unit)}</title></circle>`; });\n  const step = Math.ceil(n / Math.max(2, Math.floor((W-padL-padR)/87)));  // 12 labels at 1120\n  labels.forEach((l,i) => { if (i % step) return;\n    s += `<text class="lbl" x="${x(i).toFixed(1)}" y="${H-padB+16}" text-anchor="middle">${esc(l)}</text>`; });\n  return s + "</svg>";\n',
     b'    + `fill="#fff" stroke="var(--gr)" stroke-width="1.8"><title>${esc(labels[i])}: ${fmt(v, unit)}</title></circle>`; });\n  const step = Math.ceil(n / Math.max(2, Math.floor((W-padL-padR)/104)));  // wider labels at 14 px\n  labels.forEach((l,i) => { if (i % step) return;\n    // The first and last labels sit on the axes: centring them hangs half a label\n    // outside the drawing, which at 14 px is visible text cut off.\n    const anchor = i === n-1 ? "end" : (i === 0 ? "start" : "middle");\n    s += `<text class="lbl" x="${x(i).toFixed(1)}" y="${H-padB+16}" text-anchor="${anchor}">${esc(l)}</text>`; });\n  return s + "</svg>";\n'),
    # Sixth (2026-10-24): the feedback link became a 44 px touch target. It was
    # 111 x 17 px, which the touch gate in verify_viewports.py flags on every
    # touch viewport of every artefact built with --feedback-to. The template
    # holds the href as a placeholder, so the pair is declared on the style
    # attribute: that is the part a built page actually contains.
    (b'style="color:inherit"',
     b'style="color:inherit;display:inline-flex;align-items:center;min-height:2.75rem;padding:0 .5rem;margin-left:-.5rem"'),    # Fourth (2026-10-24): the touch floor in Safari. WebKit ignores padding,
    # border and min-height on a native <select>, so the 44 px minimum the
    # template set was 22 px there; appearance:none plus a chevron drawn as a
    # background gives the box back to the stylesheet. The cube's five-column
    # table also overflowed a 390 px phone by 3 px in WebKit, so it scrolls
    # inside its panel. Derived from a line diff of the old and new builds;
    # applying these to the old build gives the new one byte for byte.
    (b'  .controls button{min-width:auto;cursor:pointer}\n',
     b'  /* Safari ignores padding, border and min-height on a native <select>: measured\n     160x22 in WebKit against 44 px in Chromium, on the same rule, because the\n     native control paints itself. appearance:none hands the box back to us, and\n     the chevron below replaces the one the native control drew. Without this the\n     44 px touch minimum above exists in Chromium only. */\n  .controls select{-webkit-appearance:none;appearance:none;padding-right:1.75rem;\n    background-image:url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 12 8\'%3E%3Cpath d=\'M1 1.5 6 6.5 11 1.5\' fill=\'none\' stroke=\'%2300343e\' stroke-width=\'1.6\' stroke-linecap=\'round\' stroke-linejoin=\'round\'/%3E%3C/svg%3E");\n    background-repeat:no-repeat;background-position:right .5rem center;\n    background-size:.75rem .5rem}\n  .controls button{min-width:auto;cursor:pointer}\n'),
    (b'table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}\n',
     b"/* A five-column table cannot shrink below its own minimum, and WebKit's minimum\n   is 350 px here against Chromium's 342: the page overflowed a 390 px phone by\n   3 px, so the last column was clipped. The scroll container keeps the overflow\n   inside the panel, where a reader can reach it, instead of off the page. */\n#tbl{overflow-x:auto;-webkit-overflow-scrolling:touch}\ntable{min-width:100%}\ntable{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}\n"),
    (b'button.rst,select.ms{border:1px solid var(--bd);background:#fff;border-radius:6px;padding:.3rem .7rem;font-size:.875rem;min-height:2.75rem;cursor:pointer;font-family:inherit}\n',
     b'button.rst,select.ms{border:1px solid var(--bd);background:#fff;border-radius:6px;padding:.3rem .7rem;font-size:.875rem;min-height:2.75rem;cursor:pointer;font-family:inherit}\n/* Safari ignores padding, border and min-height on a native <select>, so the\n   44 px minimum above did not exist there. appearance:none plus a chevron drawn\n   as a background hands the box back to the stylesheet. */\nselect.ms{-webkit-appearance:none;appearance:none;padding-right:1.75rem;\n  background-image:url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 12 8\'%3E%3Cpath d=\'M1 1.5 6 6.5 11 1.5\' fill=\'none\' stroke=\'%2300343e\' stroke-width=\'1.6\' stroke-linecap=\'round\' stroke-linejoin=\'round\'/%3E%3C/svg%3E");\n  background-repeat:no-repeat;background-position:right .5rem center;\n  background-size:.75rem .5rem}\n'),
    # Fifth (2026-10-24): the touch floor in the process diagram and the slide deck.
    # The process tabs and toolbar buttons were 38.5 px on a phone, the facts labels
    # 13 px, and 'Vis i flyten' 35 px; the deck's rail labels 9 px, its counter 11 px
    # and its control buttons 42 px holding 12 px text. Derived from a line diff of
    # the old and new builds: applying these to the old build gives the new one
    # byte for byte.
    (b'.tabs button{font:inherit;font-size:.9375rem;font-weight:600;padding:.5rem 1rem;border:0;\n',
     b'  /* 44 px is the touch minimum docs/11 sets. These controls sat at 38.5 px\n     on a phone: tall enough to look right, too small to hit with a thumb. */\n.tabs button{font:inherit;font-size:.9375rem;font-weight:600;padding:.5rem 1rem;border:0;\n'),
    (b'  border-radius:.5rem;background:transparent;color:var(--muted);cursor:pointer}\n',
     b'  border-radius:.5rem;background:transparent;color:var(--muted);cursor:pointer;min-height:2.75rem}\n'),
    (b'  border:1px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer;min-width:2.25rem}\n',
     b'  border:1px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer;\n  min-width:2.75rem;min-height:2.75rem}\n'),
    (b'.facts dt{color:var(--muted);font-size:.8125rem;font-weight:600;text-transform:uppercase;letter-spacing:.03em}\n',
     b'.facts dt{color:var(--muted);font-size:.875rem;font-weight:600;text-transform:uppercase;letter-spacing:.03em}\n'),
    (b'html.js .show-in-flow{display:inline-flex;font:inherit;font-size:.875rem;padding:.375rem .75rem;\n',
     b'html.js .show-in-flow{display:inline-flex;align-items:center;font:inherit;font-size:.875rem;\n  padding:.375rem .75rem;min-height:2.75rem;min-width:2.75rem;\n'),

    # The table's sort control became a real button with aria-sort on its <th>
    # (2026-10-24, ROADMAP A6): a click target on a header is invisible to a keyboard
    # and to a screen reader. Three blocks in the template, byte for byte.
    (b'  th{cursor:pointer;user-select:none;font-size:.875rem;line-height:1rem;\n    text-transform:uppercase;letter-spacing:.04em;color:var(--muted);white-space:nowrap;\n    position:sticky;top:0;background:var(--color-white)}\n  th:hover{color:var(--brand)}\n',
     b'  th{font-size:.875rem;line-height:1rem;text-transform:uppercase;letter-spacing:.04em;\n    color:var(--muted);white-space:nowrap;position:sticky;top:0;\n    background:var(--color-white);padding:0}\n  /* Sorting is a control, so it is a button: a click target on a <th> is invisible to\n     a keyboard and to a screen reader (WCAG 2.1.1, docs/09 section 1). The button\n     inherits the header\'s type and paints its own focus ring; aria-sort on the <th>\n     carries the state, and the caret beside the label is decoration only.\n     min-height is 2.75rem because this is now a real target: 44 px is the thumb\n     floor docs/11 sets for every control, and a table header is no exception. */\n  th button{font:inherit;font-size:.875rem;line-height:1rem;text-transform:inherit;\n    letter-spacing:inherit;color:inherit;background:none;border:0;width:100%;\n    min-height:2.75rem;padding:var(--sp-1) .625rem;text-align:inherit;cursor:pointer;\n    display:flex;align-items:center;gap:.25rem;white-space:nowrap}\n  th.num button{justify-content:flex-end}\n  th button:hover{color:var(--brand)}\n  th button:focus-visible{outline:.125rem solid var(--brand);outline-offset:-.125rem}\n  th[aria-sort="ascending"] button,th[aria-sort="descending"] button{color:var(--ink)}\n'),
    (b'  $("tbl").querySelector("thead").innerHTML = "<tr>" + cols.map(c =>\n    `<th class="${isNum(c) ? "num" : ""}" data-col="${esc(c)}">${esc(c)}${\n      sortState.col === c ? (sortState.dir < 0 ? " \xe2\x96\xbe" : " \xe2\x96\xb4") : ""}</th>`).join("") + "</tr>";\n',
     b'  // aria-sort only on the column that is sorted: "none" on the rest, which is what the\n  // attribute means, and the caret is aria-hidden because aria-sort already says it.\n  $("tbl").querySelector("thead").innerHTML = "<tr>" + cols.map(c => {\n    const on = sortState.col === c;\n    return `<th class="${isNum(c) ? "num" : ""}" data-col="${esc(c)}"`\n      + ` aria-sort="${on ? (sortState.dir < 0 ? "descending" : "ascending") : "none"}">`\n      + `<button type="button" data-col="${esc(c)}">${esc(c)}`\n      + (on ? `<span aria-hidden="true">${sortState.dir < 0 ? "\\u25be" : "\\u25b4"}</span>` : "")\n      + `</button></th>`;\n  }).join("") + "</tr>";\n'),
    (b'  $("tbl").querySelectorAll("th").forEach(th => th.onclick = () => {\n    const c = th.dataset.col;\n',
     b'  $("tbl").querySelectorAll("th button").forEach(btn => btn.onclick = () => {\n    const c = btn.dataset.col;\n'),

    # Without scripting (ROADMAP A3, docs/11 section 3c) the dashboard showed empty
    # boxes. The build now writes the totals and the first rows into the markup, and a
    # canary class on <html> picks the view. Three insertions, anchored on text only the
    # dashboard template has: the cube and the process diagram hold a <body> and a
    # <main> too, and a pair anchored on those would paste this section into them.
    (b'  .empty{color:var(--muted);font-style:italic;padding:var(--sp-4);text-align:center}\n',
     b'  .empty{color:var(--muted);font-style:italic;padding:var(--sp-4);text-align:center}\n  /* Without scripting \xe2\x80\x94 Quick Look on iOS and macOS, or a viewer that blocks it \xe2\x80\x94 every\n     JS-rendered part of this page is an empty box. So the build writes the highest-value\n     facts into the markup itself, and a canary class on <html> decides which view shows\n     (docs/11 section 3c: a warning above empty boxes still reads as broken). The numbers\n     are computed at build time from the same rows the script gets, so the two agree. */\n  .nojs{display:none}\n  html:not(.js) .nojs{display:block}\n  html:not(.js) #kpis,html:not(.js) .grid,html:not(.js) .table-wrap,\n  html:not(.js) .controls,html:not(.js) .dropbar,\n  html:not(.js) main>section.card{display:none}\n  .nojs-lead{margin:0 0 var(--sp-3);max-width:52rem;line-height:1.5rem}\n  .nojs-facts{display:flex;flex-wrap:wrap;gap:var(--sp-4);margin:0 0 var(--sp-4)}\n  .nojs-facts div{min-width:9rem}\n  .nojs-facts dt{font-size:.875rem;line-height:1.5rem;color:var(--muted);\n    text-transform:uppercase;letter-spacing:.04em}\n  .nojs-facts dd{margin:0;font-size:1.75rem;line-height:2rem;font-weight:700;\n    font-variant-numeric:tabular-nums}\n  .nojs h2{font-size:.875rem;line-height:1.5rem;color:var(--muted);text-transform:uppercase;\n    letter-spacing:.04em;margin:0 0 var(--sp-1)}\n  .nojs table{width:100%;border-collapse:collapse;font-size:.875rem;line-height:1.5rem}\n  .nojs th,.nojs td{text-align:left;padding:var(--sp-1) .625rem;\n    border-bottom:1px solid var(--line)}\n  .nojs td.num,.nojs th.num{text-align:right;font-variant-numeric:tabular-nums}\n'),
    (b'<body>\n<header>\n  <h1>',
     b'<body>\n<script>document.documentElement.className+=" js"</script>\n<header>\n  <h1>'),
    (b'<main>\n  <section class="controls" id="controls">',
     b'<main>\n  <!-- Without the canary class above, this section is the page. It carries numbers the\n       build already computed, so a reader in a viewer that blocks scripting sees facts\n       rather than an apology. -->\n  <section class="nojs" id="nojs">\n    <p class="nojs-lead">Koden kj\xc3\xb8rer ikke her. Filtrene og diagrammene trenger den, men tallene under ble regnet ut da filen ble laget og gjelder hele datasettet.</p>\n    <dl class="nojs-facts"><div><dt>Total</dt><dd>3 676 067 703,2</dd></div><div><dt>Antall rader</dt><dd>776</dd></div><div><dt>Unike</dt><dd>6</dd></div></dl>\n    <h2>De f\xc3\xb8rste radene i filen</h2>\n    <table>\n      <thead><tr><th class="">Produkt</th><th class="">Maaned</th><th class="num">Belop</th></tr></thead>\n      <tbody><tr><td class="">Boligl\xc3\xa5n</td><td class="">2026-01</td><td class="num">4 664 226,3</td></tr><tr><td class="">Boligl\xc3\xa5n</td><td class="">2026-01</td><td class="num">9 199 732,1</td></tr><tr><td class="">Boligl\xc3\xa5n</td><td class="">2026-01</td><td class="num">549 914,1</td></tr><tr><td class="">Kredittkort</td><td class="">2026-01</td><td class="num">7 088 374,3</td></tr><tr><td class="">Kredittkort</td><td class="">2026-01</td><td class="num">2 728 638,9</td></tr><tr><td class="">Fondssparing</td><td class="">2026-01</td><td class="num">1 606 017,5</td></tr><tr><td class="">Forsikring</td><td class="">2026-01</td><td class="num">4 487 923,0</td></tr><tr><td class="">Forsikring</td><td class="">2026-01</td><td class="num">2 144 235,5</td></tr></tbody>\n    </table>\n  </section>\n  <section class="controls" id="controls">'),

    # The cube needs the no-scripting view too (ROADMAP A3): without scripting it never
    # decodes, so it showed the boot line forever. Anchored on the cube template's own
    # #boot rule and its one-line </style></head><body>, which no other template has.
    (b'#boot{padding:3rem 1.5rem;text-align:center;color:var(--mut)}\n',
     b'#boot{padding:3rem 1.5rem;text-align:center;color:var(--mut)}\n/* Without scripting (Quick Look on iOS and macOS blocks it) the cube never decodes, so\n   this file showed the boot line forever. The build writes the facts it already knew into\n   the markup, and a canary class on <html> decides which view shows: docs/11 \xc2\xa73c. */\n.nojs{display:none}\nhtml:not(.js) .nojs{display:block;padding:1.5rem}\nhtml:not(.js) #boot,html:not(.js) #app{display:none}\n.nojs-lead{margin:0 0 1.5rem;max-width:52rem;line-height:1.5rem}\n.nojs-facts{display:flex;flex-wrap:wrap;gap:1.5rem;margin:0 0 1.5rem}\n.nojs-facts div{min-width:9rem}\n.nojs-facts dt{font-size:.875rem;line-height:1.5rem;color:var(--mut);text-transform:uppercase;\n  letter-spacing:.04em}\n.nojs-facts dd{margin:0;font-size:1.75rem;line-height:2rem;font-weight:700;\n  font-variant-numeric:tabular-nums}\n.nojs h2{font-size:.875rem;line-height:1.5rem;color:var(--mut);text-transform:uppercase;\n  letter-spacing:.04em;margin:0 0 .5rem}\n.nojs ul{margin:0;padding-left:1.25rem;line-height:1.5rem}\n'),
    (b'</style></head><body>\n',
     b'</style></head><body>\n<script>document.documentElement.className+=" js"</script>\n<section class="nojs" id="nojs">\n  <!-- Without the canary class above, this is the page: the cube cannot be\n       decoded without scripting, so the build writes the facts it knew. -->\n  <p class="nojs-lead">Koden kj\xc3\xb8rer ikke her. Denne filen dekoder terningen med den, s\xc3\xa5 diagrammene og tabellene er borte. Tallene under ble regnet ut da filen ble laget, og gjelder hele datasettet.</p>\n  <dl class="nojs-facts"><div><dt>rader</dt><dd>4</dd></div><div><dt>celler</dt><dd>8</dd></div><div><dt>Dimensjoner</dt><dd>3</dd></div><div><dt>Fylte celler</dt><dd>50%</dd></div></dl>\n  <h2>Dimensjoner</h2>\n  <ul><li>region</li><li>kategori</li><li>dato</li></ul>\n</section>\n'),

    # Sixth (2026-10-24): the cube can hand the reader its numbers (ROADMAP A10). A button
    # beside the reset downloads the aggregated view as CSV, carrying the source, the build
    # stamp and the applied selection in the file. Three hunks: the button, the export
    # itself, and its click handler. Derived from a line diff of the old and new builds,
    # and applying these to the old build gives the new one byte for byte.
    (b'  <span style="flex:1"></span>\n  <select class="ms" id="measure" aria-label="M\xc3\xa5l"></select>\n  <button class="rst" id="reset">Nullstill filtre</button>\n</header>\n',
     b'  <span style="flex:1"></span>\n  <select class="ms" id="measure" aria-label="M\xc3\xa5l"></select>\n  <button class="rst" id="csv">Last ned CSV</button>\n  <button class="rst" id="reset">Nullstill filtre</button>\n</header>\n'),
    (b'let MI = 0;\n\nfunction buildChrome(){\n  document.getElementById("title").textContent = META.title;\n',
     b'let MI = 0;\n\n/* ---- CSV: det leseren ser, ikke radene\n   verdiene er de aggregerte cellene under gjeldende utvalg, og filen b\xc3\xa6rer kilde og utvalg ---- */\nconst SEP = "," === "," ? ";" : ",";\nfunction csvField(v){\n  const s = String(v);\n  return s.indexOf(\'"\') >= 0 || s.indexOf(SEP) >= 0 || /[\\r\\n]/.test(s)\n    ? \'"\' + s.replace(/"/g, \'""\') + \'"\' : s;\n}\n// No thousands separator and the reader\'s own decimal mark: a spreadsheet given\n// "1 234,5" reads text, and a text column is not why anyone downloads this.\nfunction csvNumber(v, dp){\n  const n = dp === 0 ? Math.round(v) : Math.round(v * 100) / 100;\n  return String(n).replace(".", ",");\n}\nfunction csvSlug(){\n  const iso = META.built.match(/(\\d{4})-(\\d{2})-(\\d{2})/);\n  const dotted = META.built.match(/(\\d{2})\\.(\\d{2})\\.(\\d{4})/);\n  const date = iso ? iso[0] : (dotted ? dotted[3] + "-" + dotted[2] + "-" + dotted[1] : META.built);\n  const clean = v => v.replace(/[\\\\/:*?"<>|\\s]+/g, "-").replace(/^-+|-+$/g, "");\n  return clean("kube-" + META.title).slice(0, 60) + "-" + clean(date) + ".csv";\n}\nfunction csvText(){\n  const meas = META.measures[MI];\n  const name = meas.agg === "count" ? "antall rader" : meas.field;\n  const lines = [];\n  // Provenance travels with the file: a CSV that outlives the page has to say\n  // where it came from and which selection it holds, or the numbers are a claim\n  // with no source.\n  lines.push(csvField("# Kilde: " + META.source));\n  lines.push(csvField("# Bygget: " + META.built\n    + (META.requested_by ? " for " + META.requested_by : "")));\n  lines.push(csvField("# Utvalg: " + D.map(d =>\n    d + " = " + (sel[d].size ? [...sel[d]].sort((a,b)=>a-b).map(i => META.labels[d][i]).join(", ")\n                            : "alle")).join("; ")));\n  lines.push("");\n  const head = ["Dimensjon", "Verdi", name, "Rader", "Snitt"];\n  lines.push(head.map(csvField).join(SEP));\n\n  const base = rollup(TIME || D[0], MI);\n  const dims = (TIME ? [TIME] : []).concat(CHART_DIMS);\n  for (const d of dims){\n    const r = rollup(d, MI);\n    const idx = active(d).sort((a,b) => r.out[b] - r.out[a]);\n    for (const i of idx){\n      if (!r.outN[i]) continue;\n      lines.push([d, META.labels[d][i], name, csvNumber(r.out[i]),\n                  csvNumber(r.outN[i], 0),\n                  csvNumber(r.out[i] / Math.max(1, r.outN[i]))].map(csvField).join(SEP));\n    }\n  }\n  lines.push(["Totalt", "", name, csvNumber(base.tot), csvNumber(base.totN, 0),\n              csvNumber(base.tot / Math.max(1, base.totN))].map(csvField).join(SEP));\n  return "\\ufeff" + lines.join("\\r\\n") + "\\r\\n";\n}\nfunction downloadCSV(){\n  const text = csvText();\n  try {\n    const url = URL.createObjectURL(new Blob([text], {type: "text/csv;charset=utf-8"}));\n    const a = document.createElement("a");\n    a.href = url; a.download = csvSlug();\n    document.body.appendChild(a); a.click(); a.remove();\n    setTimeout(() => URL.revokeObjectURL(url), 4000);\n  } catch (err) {\n    // A host that blocks blob downloads gets the text in the page instead, in a\n    // box the reader can select and copy. Never a button that does nothing.\n    const box = document.createElement("div");\n    box.className = "panel"; box.id = "csvFallback";\n    box.innerHTML = "<h2>Kopier tabellen under</h2>";\n    const ta = document.createElement("textarea");\n    ta.readOnly = true; ta.rows = 12; ta.style.width = "100%";\n    ta.style.font = \'14px ui-monospace,SFMono-Regular,Menlo,monospace\';\n    ta.value = text;\n    box.appendChild(ta);\n    document.querySelector("main").prepend(box);\n    ta.focus(); ta.select();\n  }\n}\n\nfunction buildChrome(){\n  document.getElementById("title").textContent = META.title;\n'),
    (b'    c.classList.toggle("on"); render();\n  });\n  document.getElementById("reset").onclick = () => { D.forEach(d => sel[d].clear());\n    document.querySelectorAll(".chip.on").forEach(c => c.classList.remove("on")); render(); };\n',
     b'    c.classList.toggle("on"); render();\n  });\n  document.getElementById("csv").onclick = downloadCSV;\n  document.getElementById("reset").onclick = () => { D.forEach(d => sel[d].clear());\n    document.querySelectorAll(".chip.on").forEach(c => c.classList.remove("on")); render(); };\n'),
    # Twelfth (2026-10-25): the palette gains a ninth slot, --palette-primary-on-dark, so a
    # theme can show the primary colour on a dark page (docs/22; the seam grew from eight to
    # nine). Every artefact that inlines the palette carries one more declaration. The
    # process diagram is the only builder that inlines the shared tokens, so it is the only
    # probe whose bytes move. Derived from a line diff of the old and new builds.
    (b'  --palette-primary-darkest: #0E1C2E;\n',
     b'  --palette-primary-darkest: #0E1C2E;\n  --palette-primary-on-dark: #9CC0E8;\n'),
    # Thirteenth (2026-10-25): text drawn on a --brand fill gets its own role, --on-brand,
    # because the right colour differs per theme and a component that guesses white gets
    # 1.89:1 on the dark theme's light primary. Declared in theme-light.css beside --brand.
    (b'  --brand:      var(--palette-primary);\n',
     b'  --brand:      var(--palette-primary);\n  --on-brand:   var(--palette-surface);\n'),
    # Fourteenth (2026-10-25): the process diagram follows the operating system's dark
    # setting with no script, and the seam grows the roles a soft brand tint and a
    # text-safe negative need. Four hunks, each a pure insertion, derived from a line diff
    # of the old and new builds: the new declarations in theme-light.css and
    # theme-dark.css, and the template's own dark block, which remaps the six lane roles
    # and the three surfaces that cannot inherit. Applying these to the old build gives
    # the new one byte for byte.
    (b'  --brand-dark: var(--palette-primary-dark);\n',
     b'  --brand-dark: var(--palette-primary-dark);\n'
     b'  --brand-soft: #e3f0ef;\n'
     b'  --on-brand-soft: var(--brand-dark);\n'
     b'  --rule:       #ececec;\n'),
    (b'  --bad:   var(--status-negative);\n',
     b'  --bad:   var(--status-negative);\n'
     b'  --bad-ink: #d42626;\n'),
    (b'  --bad-bg:var(--palette-surface);\n',
     b'  --bad-bg:var(--palette-surface);\n'
     b'}\n'
     b':root[data-theme="dark"]{\n'
     b'  --ink:        var(--palette-on-dark);\n'
     b'  --muted:      #b3d5d5;\n'
     b'  --line:       #14555a;\n'
     b'  --bg:         var(--palette-primary-dark);\n'
     b'  --panel:      var(--palette-primary-darkest);\n'
     b'  --brand:      var(--palette-primary-on-dark);\n'
     b'  --on-brand:   var(--bg);\n'
     b'  --brand-dark: var(--palette-primary-darkest);\n'
     b'  --brand-soft: #123a44;\n'
     b'  --on-brand-soft: var(--palette-on-dark);\n'
     b'  --rule:       #1d4a52;\n'
     b'  --series-2:   var(--palette-accent-light);\n'
     b'  --ok:    #66ccb0;\n'
     b'  --ok-bg: #12332c;\n'
     b'  --bad:   #ff7a7a;\n'
     b'  --bad-ink: var(--bad);\n'
     b'  --bad-bg:#4a2026;\n'
     b'}\n'
     b'@media (prefers-color-scheme: dark){\n'
     b'  :root:not([data-theme]){\n'
     b'    --ink: var(--palette-on-dark);\n'
     b'    --muted: #b3d5d5;\n'
     b'    --line: #14555a;\n'
     b'    --bg: var(--palette-primary-dark);\n'
     b'    --panel: var(--palette-primary-darkest);\n'
     b'    --brand: var(--palette-primary-on-dark);\n'
     b'    --on-brand: var(--bg);\n'
     b'    --brand-dark: var(--palette-primary-darkest);\n'
     b'    --brand-soft: #123a44;\n'
     b'    --on-brand-soft: var(--palette-on-dark);\n'
     b'    --rule: #1d4a52;\n'
     b'    --series-2: var(--palette-accent-light);\n'
     b'    --ok: #66ccb0;\n'
     b'    --ok-bg: #12332c;\n'
     b'    --bad: #ff7a7a;\n'
     b'    --bad-ink: var(--bad);\n'
     b'    --bad-bg: #4a2026;\n'
     b'  }\n'),
    (b'.pd .node,.pd .edge,.pd .flag-badge{transition:opacity .15s}\n',
     b'.pd .node,.pd .edge,.pd .flag-badge{transition:opacity .15s}\n'
     b'\n'
     b'/* Dark, for a reader whose operating system asks for it and who has chosen no theme of\n'
     b'   their own. The tokens come from theme-dark.css; what follows are the places this drawing\n'
     b'   cannot simply inherit them, each measured against the dark page and the dark panel that\n'
     b'   theme-dark.css declares for the palette this example records.\n'
     b'\n'
     b'   1. THE SIX ROLES. Three of them are dark by design in light (primary-dark, primary and\n'
     b'      primary-darkest) and measure 1.00-1.79:1 on the dark surface, which is not a dim\n'
     b'      accent but an absent one: three lane colours rendered as nothing. --status-neutral and\n'
     b'      --status-positive are dark inks chosen for white, and measure 2.35-3.20:1 here. The\n'
     b'      dark ramp therefore uses the slots that exist for a dark surface, chosen so that every\n'
     b'      role clears the 3:1 non-text minimum in all three shipped palettes and neighbouring\n'
     b'      lanes stay perceptibly apart (closest pair deltaE 27.8, CIELAB). Contrast, page:\n'
     b'                        neutral   brand   tun\n'
     b'        c0 primary-on-dark  6.54    6.73   5.76\n'
     b'        c1 accent           3.80    6.08   3.76\n'
     b'        c2 muted            7.88    8.15   9.67\n'
     b'        c3 ok               6.37    6.59   7.82\n'
     b'        c4 on-dark         11.33   12.60  14.14\n'
     b'        c5 accent-light     8.37   10.41   8.21\n'
     b'      The lane NAME still carries the identity a reader needs (WCAG 2.2 1.4.1): a palette is\n'
     b"      free to set these slots within a hue family, as the tun palette's greens show, and\n"
     b'      colour is then a second signal rather than the only one. tools/check_token_contrast.py\n'
     b'      measures all six against --bg, and tests/test_process_diagram.py fails if this list\n'
     b'      and that table ever disagree.\n'
     b'   2. HEADINGS. h1 and h2 use --brand-dark, which in dark is the page background: 1.21:1,\n'
     b'      so every heading disappeared. The slot that exists for "the primary colour as read\n'
     b'      on a dark surface" replaces it: 5.76:1.\n'
     b'   3. FLAGGED SURFACES. The light theme fills these with --status-negative-bg, a pale red\n'
     b"      tint that exists for one reason: dark ink on it. Under dark ink's inverse it is a\n"
     b'      pale box with near-white text, 1.05:1. Dark has its own chip tint, --bad-bg, chosen\n'
     b'      by the theme for exactly this and measuring 12.83:1 against the ink, so the fill\n'
     b"      switches to it and the text colour comes from the theme's --bad (6.01:1), not from a\n"
     b'      light-theme red.\n'
     b'   The start and end boxes invert in dark: a near-black fill on a dark page is a 1.21:1\n'
     b'   boundary, and their label is the one place the drawing states "this is where it begins".\n'
     b'   A fill of primary-on-dark with darkest ink measures 5.76:1 for the shape and 6.95:1 for\n'
     b'   its label. */\n'
     b'@media (prefers-color-scheme: dark){\n'
     b'  :root:not([data-theme]) .c0{--role:var(--palette-primary-on-dark)}\n'
     b'  :root:not([data-theme]) .c1{--role:var(--palette-accent)}\n'
     b'  :root:not([data-theme]) .c2{--role:var(--muted)}\n'
     b'  :root:not([data-theme]) .c3{--role:var(--ok)}\n'
     b'  :root:not([data-theme]) .c4{--role:var(--palette-on-dark)}\n'
     b'  :root:not([data-theme]) .c5{--role:var(--palette-accent-light)}\n'
     b'  :root:not([data-theme]) h1,\n'
     b'  :root:not([data-theme]) h2{color:var(--palette-primary-on-dark)}\n'
     b'  :root:not([data-theme]) .badge,\n'
     b'  :root:not([data-theme]) .card-flag{background:var(--bad-bg)}\n'
     b'  :root:not([data-theme]) .pd .node-start .node-shape,\n'
     b'  :root:not([data-theme]) .pd .node-end .node-shape{fill:var(--palette-primary-on-dark);\n'
     b'    stroke:var(--palette-primary-on-dark)}\n'
     b'  :root:not([data-theme]) .pd .node-start .node-label,\n'
     b'  :root:not([data-theme]) .pd .node-end .node-label{fill:var(--palette-primary-darkest)}\n'
     b'  :root:not([data-theme]) .pd .flagged .node-shape,\n'
     b'  :root:not([data-theme]) .pd .flag-badge circle{fill:var(--bad-bg)}\n'
     b'}\n'),
    # Fifteenth (2026-10-25): the categorical series, five blocks a survey bar paints its
    # answer options with. Three hunks, each a pure insertion: the light declarations, the
    # dark ones, and the prefers-color-scheme copy the builder derives from the dark theme.
    # Two of the light values were too pale to be a colour on a white panel and are one
    # step deeper; the numbers are in theme-light.css.
    (b'  --series-2:   var(--palette-accent);\n',
     b'  --series-2:   var(--palette-accent);\n'
     b'  --cat-1: #007272;\n'
     b'  --cat-2: #1a8f66;\n'
     b'  --cat-3: #14555a;\n'
     b'  --cat-4: #5f8f89;\n'
     b'  --cat-5: #dc2a2a;\n'),
    (b'  --series-2:   var(--palette-accent-light);\n',
     b'  --series-2:   var(--palette-accent-light);\n'
     b'  --cat-1: #7FD4C8;\n'
     b'  --cat-2: #8FD98A;\n'
     b'  --cat-3: #E8D48B;\n'
     b'  --cat-4: #B9C7E8;\n'
     b'  --cat-5: #FF8A8A;\n'),
    (b'    --series-2: var(--palette-accent-light);\n',
     b'    --series-2: var(--palette-accent-light);\n'
     b'    --cat-1: #7FD4C8;\n'
     b'    --cat-2: #8FD98A;\n'
     b'    --cat-3: #E8D48B;\n'
     b'    --cat-4: #B9C7E8;\n'
     b'    --cat-5: #FF8A8A;\n'),
    # Sixteenth (2026-10-25): the cube dashboard moves onto the seam. The biggest hunk is
    # the inlined token block itself, which replaces the template's six local hexes; the
    # rest are the four surfaces that painted a raw white (header, filter panel, chip and
    # KPI card, and the line chart's marker fill, which becomes the panel so it still reads
    # as a gap in the line) and the one that stated a control colour, because a browser's
    # own button text is CanvasText and does not follow the theme. Derived from a line diff
    # of the old and new builds; applying them gives the new one byte for byte.
    (b':root{--gr:#007272;--gr2:#14555a;--ink:#1c1c1c;--mut:#6b7280;--bd:#e3e6e8;--bg:#f7f8f9}\n',
     b'/* The colour tokens are inlined by the builder from tools/tokens/: one seam shared with\n'
     b"   every other artefact, which is also how this page follows the operating system's dark\n"
     b'   setting with no script. Add no hex of your own here. */\n'
     b':root{\n'
     b'  --palette-ink:             #111418;\n'
     b'  --palette-surface:         #FFFFFF;\n'
     b'  --palette-primary:         #2B4C7E;\n'
     b'  --palette-primary-dark:    #1B3559;\n'
     b'  --palette-primary-darkest: #0E1C2E;\n'
     b'  --palette-primary-on-dark: #9CC0E8;\n'
     b'  --palette-accent:          #B8860B;\n'
     b'  --palette-accent-light:    #E8D48B;\n'
     b'  --palette-on-dark:         #F7F5EF;\n'
     b'}\n'
     b':root{\n'
     b'  --status-negative:          #dc2a2a;\n'
     b'  --status-negative-bg:       #fdeeee;\n'
     b'  --status-positive:          #007b5e;\n'
     b'  --status-positive-bg-25:    #e9f8f4;\n'
     b'  --status-positive-bg-12:    #f4fbf9;\n'
     b'  --status-neutral:           #737373;\n'
     b'}\n'
     b':root,\n'
     b':root[data-theme="light"]{\n'
     b'  --ink:        var(--palette-ink);\n'
     b'  --muted:      #666666;\n'
     b'  --line:       #ebebeb;\n'
     b'  --bg:         var(--palette-surface);\n'
     b'  --panel:      #f8f8f8;\n'
     b'  --brand:      var(--palette-primary);\n'
     b'  --on-brand:   var(--palette-surface);\n'
     b'  --brand-dark: var(--palette-primary-dark);\n'
     b'  --brand-soft: #e3f0ef;\n'
     b'  --on-brand-soft: var(--brand-dark);\n'
     b'  --rule:       #ececec;\n'
     b'  --series-2:   var(--palette-accent);\n'
     b'  --cat-1: #007272;\n'
     b'  --cat-2: #1a8f66;\n'
     b'  --cat-3: #14555a;\n'
     b'  --cat-4: #5f8f89;\n'
     b'  --cat-5: #dc2a2a;\n'
     b'  --ok:    var(--status-positive);\n'
     b'  --ok-bg: var(--status-positive-bg-12);\n'
     b'  --bad:   var(--status-negative);\n'
     b'  --bad-ink: #d42626;\n'
     b'  --bad-bg:var(--palette-surface);\n'
     b'}\n'
     b':root[data-theme="dark"]{\n'
     b'  --ink:        var(--palette-on-dark);\n'
     b'  --muted:      #b3d5d5;\n'
     b'  --line:       #14555a;\n'
     b'  --bg:         var(--palette-primary-dark);\n'
     b'  --panel:      var(--palette-primary-darkest);\n'
     b'  --brand:      var(--palette-primary-on-dark);\n'
     b'  --on-brand:   var(--bg);\n'
     b'  --brand-dark: var(--palette-primary-darkest);\n'
     b'  --brand-soft: #123a44;\n'
     b'  --on-brand-soft: var(--palette-on-dark);\n'
     b'  --rule:       #1d4a52;\n'
     b'  --series-2:   var(--palette-accent-light);\n'
     b'  --cat-1: #7FD4C8;\n'
     b'  --cat-2: #8FD98A;\n'
     b'  --cat-3: #E8D48B;\n'
     b'  --cat-4: #B9C7E8;\n'
     b'  --cat-5: #FF8A8A;\n'
     b'  --ok:    #66ccb0;\n'
     b'  --ok-bg: #12332c;\n'
     b'  --bad:   #ff7a7a;\n'
     b'  --bad-ink: var(--bad);\n'
     b'  --bad-bg:#4a2026;\n'
     b'}\n'
     b'@media (prefers-color-scheme: dark){\n'
     b'  :root:not([data-theme]){\n'
     b'    --ink: var(--palette-on-dark);\n'
     b'    --muted: #b3d5d5;\n'
     b'    --line: #14555a;\n'
     b'    --bg: var(--palette-primary-dark);\n'
     b'    --panel: var(--palette-primary-darkest);\n'
     b'    --brand: var(--palette-primary-on-dark);\n'
     b'    --on-brand: var(--bg);\n'
     b'    --brand-dark: var(--palette-primary-darkest);\n'
     b'    --brand-soft: #123a44;\n'
     b'    --on-brand-soft: var(--palette-on-dark);\n'
     b'    --rule: #1d4a52;\n'
     b'    --series-2: var(--palette-accent-light);\n'
     b'    --cat-1: #7FD4C8;\n'
     b'    --cat-2: #8FD98A;\n'
     b'    --cat-3: #E8D48B;\n'
     b'    --cat-4: #B9C7E8;\n'
     b'    --cat-5: #FF8A8A;\n'
     b'    --ok: #66ccb0;\n'
     b'    --ok-bg: #12332c;\n'
     b'    --bad: #ff7a7a;\n'
     b'    --bad-ink: var(--bad);\n'
     b'    --bad-bg: #4a2026;\n'
     b'  }\n'
     b'}\n'
     b':root{\n'
     b'  /* The names this template has always used, pointed at the seam. --ink and --bg are the\n'
     b"     seam's own names already, so they are not restated. */\n"
     b'  --gr:var(--brand);--gr2:var(--brand-dark);--mut:var(--muted);--bd:var(--line);\n'
     b'}\n'),
    (b'header{background:#fff;border-bottom:1px solid var(--bd);padding:1rem 1.5rem;display:flex;align-items:baseline;gap:1rem;flex-wrap:wrap}\n',
     b'header{background:var(--panel);border-bottom:1px solid var(--bd);padding:1rem 1.5rem;display:flex;align-items:baseline;gap:1rem;flex-wrap:wrap}\n'),
    (b'.panel{background:#fff;border:1px solid var(--bd);border-radius:8px;padding:1rem 1.1rem;margin-bottom:1rem}\n',
     b'.panel{background:var(--panel);border:1px solid var(--bd);border-radius:8px;padding:1rem 1.1rem;margin-bottom:1rem}\n'),
    (b'.chip{border:1px solid var(--bd);background:#fff;border-radius:14px;padding:.2rem .6rem;font-size:.875rem;cursor:pointer;user-select:none;transition:.12s}\n',
     b'.chip{border:1px solid var(--bd);background:var(--panel);border-radius:14px;padding:.2rem .6rem;font-size:.875rem;cursor:pointer;user-select:none;transition:.12s}\n'),
    (b'.chip.on{background:var(--gr);border-color:var(--gr);color:#fff}\n',
     b'.chip.on{background:var(--gr);border-color:var(--gr);color:var(--on-brand)}\n'),
    (b'.kpi{background:#fff;border:1px solid var(--bd);border-radius:8px;padding:.9rem 1rem}\n',
     b'.kpi{background:var(--panel);border:1px solid var(--bd);border-radius:8px;padding:.9rem 1rem}\n'),
    (b'button.rst,select.ms{border:1px solid var(--bd);background:#fff;border-radius:6px;padding:.3rem .7rem;font-size:.875rem;min-height:2.75rem;cursor:pointer;font-family:inherit}\n',
     b"/* color: the browser's own button text is CanvasText, which does not follow the theme:\n"
     b'   black on the dark panel measures 1.22:1. A form control needs its colour stated. */\n'
     b'button.rst,select.ms{border:1px solid var(--bd);background:var(--panel);color:var(--ink);border-radius:6px;padding:.3rem .7rem;font-size:.875rem;min-height:2.75rem;cursor:pointer;font-family:inherit}\n'),
    (b'   still prints even though the controls do not. */\n',
     b'   still prints even though the controls do not. */\n'
     b'/* Dark, for a reader whose operating system asks for it and who has chosen no theme of\n'
     b'   their own. The declarations above come from theme-dark.css; what follows are the two\n'
     b'   places this page gives a slot a role that inverts.\n'
     b'\n'
     b'   --brand-dark is the darkest surface in the dark theme, so it is a fine colour to READ on\n'
     b"   a white page (the footer's bold run) and a fine colour to darken a bar TOWARDS in light,\n"
     b'   and invisible at both jobs in dark. --brand is the slot for a readable colour on a dark\n'
     b'   surface, so both use it here. */\n'
     b'@media (prefers-color-scheme: dark){\n'
     b'  :root:not([data-theme]) footer b{color:var(--brand)}\n'
     b'  :root:not([data-theme]) .bar:hover{fill:var(--brand)}\n'
     b'}\n'),
    (b'    + `fill="#fff" stroke="var(--gr)" stroke-width="1.8"><title>${esc(labels[i])}: ${fmt(v, unit)}</title></circle>`; });\n',
     b'    + `fill="var(--panel)" stroke="var(--gr)" stroke-width="1.8"><title>${esc(labels[i])}: ${fmt(v, unit)}</title></circle>`; });\n'),
    # Seventeenth (2026-10-25): the flagship dashboard, and the one seam role it needed.
    # Three pairs are the seam itself: `--bad-soft`, a negative wash to letter red text on,
    # which the token files grow for the delta chip (a delta letters --bad-ink on a washed
    # pill, not on the panel). Those three are pure insertions and apply to every artefact
    # that inlines the seam. The rest are the dashboard template: its forty hand-written
    # The old brand values are replaced by the seam block, and the ten palette names it actually
    # used are rewritten onto roles. Order matters and this list is applied in order: the
    # seam insertions come first (they no-op on a dashboard, which has no seam yet) and the
    # dashboard's own big insertion comes last, so the seam is spliced in exactly once.
    # Derived from a line diff of the old and new builds; applying them reproduces the new
    # output byte for byte on all 22 probes.
    (b'  --bad-ink: #d42626;\n',
     b'  --bad-ink: #d42626;\n'
     b'  --bad-soft:  #fdeeee;\n'),
    (b'  --bad:   #ff7a7a;\n'
     b'  --bad-ink: var(--bad);\n',
     b'  --bad:   #ff7a7a;\n'
     b'  --bad-ink: var(--bad);\n'
     b'  --bad-soft: #4a2026;\n'),
    (b'    --bad-ink: var(--bad);\n',
     b'    --bad-ink: var(--bad);\n'
     b'    --bad-soft: #4a2026;\n'),
    (b'     ========================================================================== */\n',
     b'     ========================================================================== */\n'
     b':root{\n'
     b'  --palette-ink:             #111418;\n'
     b'  --palette-surface:         #FFFFFF;\n'
     b'  --palette-primary:         #2B4C7E;\n'
     b'  --palette-primary-dark:    #1B3559;\n'
     b'  --palette-primary-darkest: #0E1C2E;\n'
     b'  --palette-primary-on-dark: #9CC0E8;\n'
     b'  --palette-accent:          #B8860B;\n'
     b'  --palette-accent-light:    #E8D48B;\n'
     b'  --palette-on-dark:         #F7F5EF;\n'
     b'}\n'
     b':root{\n'
     b'  --status-negative:          #dc2a2a;\n'
     b'  --status-negative-bg:       #fdeeee;\n'
     b'  --status-positive:          #007b5e;\n'
     b'  --status-positive-bg-25:    #e9f8f4;\n'
     b'  --status-positive-bg-12:    #f4fbf9;\n'
     b'  --status-neutral:           #737373;\n'
     b'}\n'
     b':root,\n'
     b':root[data-theme="light"]{\n'
     b'  --ink:        var(--palette-ink);\n'
     b'  --muted:      #666666;\n'
     b'  --line:       #ebebeb;\n'
     b'  --bg:         var(--palette-surface);\n'
     b'  --panel:      #f8f8f8;\n'
     b'  --brand:      var(--palette-primary);\n'
     b'  --on-brand:   var(--palette-surface);\n'
     b'  --brand-dark: var(--palette-primary-dark);\n'
     b'  --brand-soft: #e3f0ef;\n'
     b'  --on-brand-soft: var(--brand-dark);\n'
     b'  --rule:       #ececec;\n'
     b'  --series-2:   var(--palette-accent);\n'
     b'  --cat-1: #007272;\n'
     b'  --cat-2: #1a8f66;\n'
     b'  --cat-3: #14555a;\n'
     b'  --cat-4: #5f8f89;\n'
     b'  --cat-5: #dc2a2a;\n'
     b'  --ok:    var(--status-positive);\n'
     b'  --ok-bg: var(--status-positive-bg-12);\n'
     b'  --bad:   var(--status-negative);\n'
     b'  --bad-ink: #d42626;\n'
     b'  --bad-soft:  #fdeeee;\n'
     b'  --bad-bg:var(--palette-surface);\n'
     b'}\n'
     b':root[data-theme="dark"]{\n'
     b'  --ink:        var(--palette-on-dark);\n'
     b'  --muted:      #b3d5d5;\n'
     b'  --line:       #14555a;\n'
     b'  --bg:         var(--palette-primary-dark);\n'
     b'  --panel:      var(--palette-primary-darkest);\n'
     b'  --brand:      var(--palette-primary-on-dark);\n'
     b'  --on-brand:   var(--bg);\n'
     b'  --brand-dark: var(--palette-primary-darkest);\n'
     b'  --brand-soft: #123a44;\n'
     b'  --on-brand-soft: var(--palette-on-dark);\n'
     b'  --rule:       #1d4a52;\n'
     b'  --series-2:   var(--palette-accent-light);\n'
     b'  --cat-1: #7FD4C8;\n'
     b'  --cat-2: #8FD98A;\n'
     b'  --cat-3: #E8D48B;\n'
     b'  --cat-4: #B9C7E8;\n'
     b'  --cat-5: #FF8A8A;\n'
     b'  --ok:    #66ccb0;\n'
     b'  --ok-bg: #12332c;\n'
     b'  --bad:   #ff7a7a;\n'
     b'  --bad-ink: var(--bad);\n'
     b'  --bad-soft: #4a2026;\n'
     b'  --bad-bg:#4a2026;\n'
     b'}\n'
     b'@media (prefers-color-scheme: dark){\n'
     b'  :root:not([data-theme]){\n'
     b'    --ink: var(--palette-on-dark);\n'
     b'    --muted: #b3d5d5;\n'
     b'    --line: #14555a;\n'
     b'    --bg: var(--palette-primary-dark);\n'
     b'    --panel: var(--palette-primary-darkest);\n'
     b'    --brand: var(--palette-primary-on-dark);\n'
     b'    --on-brand: var(--bg);\n'
     b'    --brand-dark: var(--palette-primary-darkest);\n'
     b'    --brand-soft: #123a44;\n'
     b'    --on-brand-soft: var(--palette-on-dark);\n'
     b'    --rule: #1d4a52;\n'
     b'    --series-2: var(--palette-accent-light);\n'
     b'    --cat-1: #7FD4C8;\n'
     b'    --cat-2: #8FD98A;\n'
     b'    --cat-3: #E8D48B;\n'
     b'    --cat-4: #B9C7E8;\n'
     b'    --cat-5: #FF8A8A;\n'
     b'    --ok: #66ccb0;\n'
     b'    --ok-bg: #12332c;\n'
     b'    --bad: #ff7a7a;\n'
     b'    --bad-ink: var(--bad);\n'
     b'    --bad-soft: #4a2026;\n'
     b'    --bad-bg: #4a2026;\n'
     b'  }\n'
     b'}\n'),
    (b'    /* Profile */\n'
     b'    --color-sea-green:#007272; --color-mint-green:#a5e1d2;\n'
     b'    --color-summer-green:#28b482; --color-emerald-green:#14555a;\n'
     b'    --color-ocean-green:#00343e; --color-accent-yellow:#fdbb31;\n'
     b'    --color-indigo:#23195a; --color-violet:#6e2382; --color-sky-blue:#4bbed2;\n'
     b'    --color-lavender:#f2f2f5; --color-sand-yellow:#fbf6ec; --color-pistachio:#f2f4ec;\n'
     b'    /* UX / functional */\n'
     b'    --color-sea-green-30:#b3d5d5; --color-mint-green-50:#d2f0e9;\n'
     b'    --color-mint-green-25:#e9f8f4; --color-mint-green-12:#f4fbf9;\n'
     b'    --color-fire-red:#dc2a2a; --color-fire-red-8:#fdeeee;\n'
     b'    --color-success-green:#007b5e; --color-signal-orange:#ff5400;\n'
     b'    --color-black:#000; --color-black-80:#333; --color-black-60:#666; --color-black-55:#737373;\n'
     b'    --color-black-20:#ccc; --color-black-8:#ebebeb; --color-black-3:#f8f8f8;\n'
     b'    --color-white:#fff;\n'
     b'\n'
     b'    /* Semantic roles used by this dashboard */\n'
     b'    --ink:var(--color-black-80);        /* body text */\n'
     b'    --muted:var(--color-black-60);      /* labels, axis text: 5.4:1 on --panel (Black 55% was 4.46:1, under AA) */\n'
     b'    --line:var(--color-black-8);        /* borders, gridlines */\n'
     b'    --bg:var(--color-white);\n'
     b'    --panel:var(--color-black-3);       /* cards, filter bar */\n'
     b'    --brand:var(--color-sea-green);     /* primary data colour */\n'
     b'    --brand-dark:var(--color-emerald-green);\n'
     b'    --series-2:var(--color-summer-green);\n'
     b'\n'
     b'    /* ' + _DS + b' uses an 8px grid; spacing in 0.5rem increments */\n',
     b'    /* Colours come from the seam above. These are the only values this template\n'
     b'       still declares itself, and they are spacing, not colour. */\n'),
    (b'  :focus-visible{outline:2px solid var(--color-sea-green);outline-offset:2px}\n',
     b'  :focus-visible{outline:2px solid var(--brand);outline-offset:2px}\n'),
    (b'  header{background:var(--brand-dark);color:var(--color-white);padding:var(--sp-3) var(--sp-4)}\n',
     b'  header{background:var(--brand);color:var(--on-brand);padding:var(--sp-3) var(--sp-4)}\n'),
    (b'    border:1px solid var(--color-black-20);border-radius:.25rem;font-size:.875rem;\n'
     b'    line-height:1.5rem;background:var(--color-white);min-width:10rem;font-family:inherit;\n',
     b'    border:1px solid var(--line);border-radius:.25rem;font-size:.875rem;\n'
     b'    line-height:1.5rem;background:var(--bg);min-width:10rem;font-family:inherit;\n'),
    (b'    flex-wrap:wrap;border:1px dashed var(--color-black-20);border-radius:.25rem;\n',
     b'    flex-wrap:wrap;border:1px dashed var(--line);border-radius:.25rem;\n'),
    (b'  .dropbar.over{background:var(--color-mint-green-12);border-color:var(--brand);\n'
     b'    color:var(--brand-dark)}\n',
     b'  .dropbar.over{background:var(--brand-soft);border-color:var(--brand);\n'
     b'    color:var(--on-brand-soft)}\n'),
    (b'  .dropbar button{padding:.5rem .9rem;border:1px solid var(--color-black-20);\n'
     b'    border-radius:.25rem;background:var(--color-white);font-family:inherit;\n',
     b'  .dropbar button{padding:.5rem .9rem;border:1px solid var(--line);\n'
     b'    border-radius:.25rem;background:var(--bg);font-family:inherit;\n'),
    (b'  .kpi .delta.up{color:var(--color-success-green);background:var(--color-mint-green-12,#f4fbf9)}\n'
     b'  .kpi .delta.down{color:var(--color-fire-red);background:var(--color-fire-red-8,#fdeeee)}\n',
     b'  .kpi .delta.up{color:var(--ok);background:var(--ok-bg)}\n'
     b'  .kpi .delta.down{color:var(--bad-ink);background:var(--bad-soft)}\n'),
    (b'    background:var(--color-white)}\n',
     b'    background:var(--bg)}\n'),
    (b'  .axis{stroke:var(--color-black-20);stroke-width:1}\n',
     b'  .axis{stroke:var(--line);stroke-width:1}\n'),
    (b'  .bar:hover{fill:var(--brand-dark)}\n',
     b'  /* Hover is a second colour for the same bar. --brand-dark, which this used, is the\n'
     b'     darkest surface in the dark theme: the bar would vanish under the pointer. */\n'
     b'  .bar:hover{fill:var(--series-2)}\n'),
    (b'    background:var(--color-white);padding:0}\n',
     b'    background:var(--bg);padding:0}\n'),
    (b'  tbody tr:hover{background:var(--color-mint-green-12)}\n',
     b'  tbody tr:hover{background:var(--brand-soft)}\n'),
    (b'  .tooltip{position:fixed;background:var(--color-black-80);color:var(--color-white);\n',
     b'  .tooltip{position:fixed;background:var(--ink);color:var(--bg);\n'),
    (b'  @media print{header{background:var(--color-white);color:var(--ink)}.controls{display:none}}\n',
     b'  @media print{header{background:#fff;color:var(--ink)}.controls{display:none}}\n'
     b'\n'
     b'  /* Dark. The seam carries every declaration; this is the one place where a role that reads\n'
     b'     on white inverts once the surface behind it goes dark. --brand-dark is the darkest\n'
     b'     surface in the dark theme, so a KPI figure lettered with it disappears into its own card\n'
     b'     (measured 1.00:1). It becomes --brand there, the light-on-dark teal. */\n'
     b'  @media (prefers-color-scheme: dark){\n'
     b'    .kpi .value{color:var(--brand)}\n'
     b'  }\n'),
    # Eighteenth (2026-10-26): the dark route is a SCREEN route. `dark` is a choice a
    # reader made about a display, and paper is white; without the guard, printing from a
    # dark system applied the dark tokens to a page whose @media print block had just
    # forced the background white, so the ink measured rgb(247,245,239) on white. One
    # pair, appended last so it also rewrites the media query the pairs above insert.
    (b'@media (prefers-color-scheme: dark){',
     b'@media screen and (prefers-color-scheme: dark){'),
    # The export scrub repointed the palette away from the owner's brand values. These are
    # the same substitutions in the same order the scrub applied them, so the old build and
    # the new one differ only in ways declared here.
    (b"#007272", b"#2F5D9E"),
    (b"#14555a", b"#1B2A4A"),
    (b"#b3d5d5", b"#DCE6F5"),
    (b'     ' + _DN + b' ' + _DS + b' design tokens \xe2\x80\x94 brand palette\n     Source: https://' + _HOST + b'/uilib/usage/customisation/colors/\n     Values are the authoritative ' + _DS + b' brand hex codes.\n\n     WHY hardcoded values and not the ' + _DS + b' CSS package:',
     b'     The brand design tokens \xe2\x80\x94 brand palette\n     Source: https://design.example.com/uilib/usage/customisation/colors/\n     Values are the authoritative brand hex codes.\n\n     WHY hardcoded values and not the design system CSS package:'),
    (b'       OneDrive-synced folder). Importing ' + _PKG + b' or its stylesheet would',
     b'       OneDrive-synced folder). Importing the design system package or its stylesheet would'),
    (b'       The newer `--token-color-*` design tokens are still beta and resolve\n       through the ' + _DS + b' CSS, so they are not usable here yet.',
     b'       The newer `--tun-color-*` design tokens are still beta and resolve\n       through the design system CSS, so they are not usable here yet.'),
    (b'html-standard-benchmark',
     b'html-sammenligning'),
    (b'  /* The ' + _DN + b' typeface is used when present on the machine (it is on ' + _DN + b'-managed\n     devices). It is deliberately NOT loaded from ' + _DS + b"'s font CDN \xe2\x80\x94 that would",
     b'  /* The ' + _NK + b" typeface is used when present on the machine (it is on managed\n     devices). It is deliberately NOT loaded from the design system's font CDN \xe2\x80\x94 that would"),
    (b'    font-family:"' + _DN + b'",',
     b'    font-family:"' + _NK + b'",'),
]

BASELINE = {
    "fx-deck/fx-deck.html": "16691d40b6810c3ecea32c0150a58e5f8a8e5e87ca371aafa463fc84f47280f3",
    "dash-bundled/dash-bundled.html": "6ee9847959bb23c0c6e46d3c70eafb7b35c4e1ff56df16ba51c43dbc875fa243",
    "dash-paired/paired/dash.html": "fe5be06e5fe24d430eca4d8b9c5631fce904f0931b4a282c5f0bb5827f3f2af8",
    "dash-paired/paired/data.js": "4dd301d51138aa47e2808dbe8451ad4f91f13ebb76855883070a0bfc8cf0581f",
    "dash-feedback/dash-feedback.html": "da34dad728ecd18b57ff8416c41b8455a5438e663eabd0c6afdf7da62e3a26a4",
    # New artefact 2026-10-25 (the scorecard, ROADMAP A24): its first build, pinned so any
    # change to its nb output is visible.
    "scorecard/scorecard.html": "333b3fc48b768d14c937a3d47bd1a3aab8633a75b58a83ea18ddefb02f67b8fa",
    # New artefact 2026-10-24 (the distribution page, ROADMAP A23): there is no older
    # builder to compare against, so this hash is its first build, pinned so that any
    # change to its nb output is visible.
    "distribution/distribution.html": "23764211010146b211a40d6498672f27838d022ebc615d26d1238c7aadacce76",
    # New artefact 2026-10-24: there is no older builder to compare against, so this
    # hash is its first build, pinned so that any change to its nb output is visible.
    # Re-pinned the same day (ROADMAP A22, the review layer on the comparison). The proof
    # is a line diff of the old and new builds: six `data-col` attributes on the headers,
    # `id="tbl"` on the table, and two attribute writes in the row script. Nothing else in
    # the file moved, and no visible text changed.
    "compare/compare.html": "2a2670a0fc95ceec9a88bb2e86f369e0306d8fbbe40932683df3146a97d572a8",
    "index/index.html": "d6dffaed23bb29599bf1d24c9042d2e7d410b28a2d7ade69ed8481ace6bb4aed",
    # New artefact 2026-10-24: its first build, pinned so a change to its nb output is
    # visible. No older builder exists to compare it against.
    "timeline/timeline.html": "e28e7ff57fcb18f5aca2ef5f6d5110198f987b8a5d4c47f7d5222fa85abcde5b",
    "cube/cube.html": "775032467b7c7dea8119f321eb0accffd171738f63bb9fb5c64245a80a64aadc",
    "cube-feedback/cube-feedback.html": "a7a12e9cee30eb6ab279ebab8fc54e4e4fbaf7216285a350d6f6b82c16bdaf5d",
    "process/process.html": "dcf8040aa4d8c4b2f4dd4814fe75d73f66a9d723efedb199925b383823ccf0ca",
    "fx-dash/fx-dash.html": "12e7187438184055397662afabc453c830cccc364fd69a1d022773f5ebe7d731",
    "fx-dash-paired/fxp/dash.html": "c864bc2d3684ff5bb8ae75fc8940349cd02c3779dceaa9a777b9d9d519378acf",
    "fx-dash-paired/fxp/data.js": "360bafa7d429d90f75a86aa7bc2f73f80db69634e8451dbf996c9001721f85bb",
    "fx-dash-notime/fx-dash-notime.html": "5704695c3f98980373aab666ab895eb73fb7bf08e58e1b6db640ca364a801edf",
    "fx-cube/fx-cube.html": "a4ed6fc02931c76cd35ef3b4ef85a19424690537dd45bacc1630d71bad4069a6",
    "fx-process/fx-process.html": "ab1c25de2a97b56d0ca2b852e85df3aa0dae6693c8d150939061fbbd4ee5db12",
    # the survey board (2026-10-24): a new artefact, so its nb output is frozen here
    # 2026-10-24: the survey template gained a cross-tab block (table, its CSS, the
    # note a filter shows), so the two survey builds below moved and nothing else did.
    "survey/survey.html": "31adf3c0b453d01b0f58ed689a8fc2f8ffe2eea7e1bc60ecba41ba84f5d9a9a4",
    # the register (2026-10-24): a new artefact, so its nb output is frozen here.
    # 2026-10-24: the register gained group bands (--group-by): the band CSS, the group
    # constant, the comparator clause and the band renderer are in every build, and the
    # group strings and the groupCol fact only when the build groups. So the hash below
    # moved and nothing else did; no probe in section 6 builds this template, which is
    # why it is re-pinned here rather than paired.
    "register/register.html": "6f5e54ff6514b5c5a93962cebab774ff8bfade49be82d36e6f4083626e58d59c",
    "fx-survey/fx-survey.html": "b8f9ee3101f960a2e3d8e2021ff53944ba48cf3baf99bdf6906afc775e0940fd",
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
                (dest / f"{case}--{rel.replace('/', '__')}").write_bytes(blob)
                print(f'    "{case}/{rel}": "{sha(blob)}",')
        return 0

    work = pathlib.Path(tempfile.mkdtemp(prefix="tun-i18n-"))
    try:
        return run(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


OLD_COMMIT = "56ca978"      # the builders before any strings table: the reference for the slots


def old_tools(work: pathlib.Path) -> pathlib.Path | None:
    """tools/, templates/ and the token palette as they were at OLD_COMMIT, from git.

    A tree with one commit has no such history: the export is a fresh repository, so this
    comparison cannot be made there. Returning None makes the caller skip with a reason rather
    than fail, because a section that cannot run must not read as a section that passed.
    """
    dest = work / "old"
    dest.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    present = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", OLD_COMMIT + "^{commit}"],
                             capture_output=True, env=env)
    if present.returncode != 0:
        print(f"SKIP: {OLD_COMMIT} is not in this tree's history, so there is no old build to "
              f"compare against. A single-commit export cannot run this section.")
        return None
    tar = subprocess.run(["git", "-C", str(ROOT), "archive", OLD_COMMIT, "tools", "templates", "plugins"],
                         capture_output=True, env=env)
    if tar.returncode != 0:
        raise SystemExit(f"cannot read {OLD_COMMIT} from git: {tar.stderr.decode()[-300:]}")
    subprocess.run(["tar", "-x", "-C", str(dest)], input=tar.stdout, check=True)
    return dest / "tools"


def adversarial(work: pathlib.Path) -> None:
    """Data that looks like a format slot or a template token must come out untouched,
    exactly as the builders before the tables wrote it (chained .replace() rescanned it)."""
    print("6. data that looks like a slot or a token")
    old = old_tools(work)
    if old is None:
        return
    adv = work / "adv"
    adv.mkdir()
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

    def lits_for(literals, lang):
        """A probe's expected strings: one list for both languages, or a list per language."""
        return literals[lang] if isinstance(literals, dict) else literals

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
    for name, (builder, src, args, files, tables, literals) in probes.items():
        CASES[name] = (builder, src, args, files, tables)
    # The static view (ROADMAP A3) carries totals and rows computed from the probe's own
    # CSV, so it cannot be written as a byte pair the way a copy change can. It is compared
    # by its own test (tests/test_nojs_fallback.py) and by the recorded hashes above; here it
    # is normalised away on both sides so the rest of the page is still compared byte for byte.
    static_block = re.compile(
        rb'(?:  <!-- Without the canary class above.*?)?<section class="nojs" id="nojs">.*?</section>\n',
        re.S)

    def strip_static(blob: bytes) -> bytes:
        return static_block.sub(b"<!-- static view -->\n", blob)

    same, compared = [], 0
    applied = {before: 0 for before, _ in DELIBERATE_NB_CHANGES}
    for name, (_b, _s, _a, _f, _t, literals) in probes.items():
        want, _ = build_case(name, work / "adv-old" / name, None, tools=old)
        for rel in want:
            for before, after in DELIBERATE_NB_CHANGES:
                applied[before] += want[rel].count(before)
                want[rel] = want[rel].replace(before, after)
        got_nb, _ = build_case(name, work / "adv-nb" / name, "nb")
        got_en, _ = build_case(name, work / "adv-en" / name, "en")
        for rel, blob in want.items():
            compared += 1
            if strip_static(got_nb[rel]) != strip_static(blob):
                same.append(f"{name}/{rel}")
                a = strip_static(blob).decode("utf-8", "replace").split("\n")
                b = strip_static(got_nb[rel]).decode("utf-8", "replace").split("\n")

        if name.startswith("slot-"):      # the string the old builder wrote is still there, in both
            page = lambda built: "".join(b.decode("utf-8") for b in built.values())  # noqa: E731
            for lang, built in (("nb", got_nb), ("en", got_en)):
                for lit in lits_for(literals, lang):
                    if lit not in page(built):
                        same.append(f"{name} {lang}: {lit!r} was rewritten")
    chk("every deliberate nb change was found in the old output (none is vacuous)",
        all(applied.values()), str([b.decode()[:30] for b, k in applied.items() if not k]),
        n=len(applied))
    chk("nb build equals the old builder's output byte for byte (slots and tokens as data)",
        not same, ", ".join(same), n=compared)
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
