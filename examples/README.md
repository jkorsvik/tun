# Examples — one row per artefact, what it proves, and how to rebuild it

Every directory here is a working artefact with the command that made it. Nothing
in this folder is a mock-up: if a file is here, it was built by a builder in
`tools/` and opened in a browser.

The numbering is chronological, not a curriculum. Read the "proves" column, pick
the claim you need to believe, and rebuild that one.

| # | Proves | Rebuild |
|---|---|---|
| [01](01-hello-dashboard/) | The default dashboard end to end: one CSV, four filters, two charts, a sortable table, provenance a reader can audit | `tools/build_dashboard.py` — command in [AGENTS.md](../AGENTS.md) |
| [02](02-paired-dashboard/) | Paired mode: `dash.html` plus a sibling `data.js`, so a synced folder updates the numbers without rebuilding the page | `tools/build_dashboard.py --mode paired` |
| [03](03-cube-dashboard/) | Four million rows in a 0.81 MB file, exact, answered in under a millisecond by pre-aggregating into a cube | `examples/03-cube-dashboard/generate_data.py`, then `build_cube_dashboard.py` |
| [04](04-generic-standalone-demo/) | The generic half of the model works with no dashboard vocabulary at all: no rows, no dimension, no measure | `examples/04-generic-standalone-demo/build_standalone_demo.py` |
| [05](05-theme-toggle-demo/) | Three navigation decisions from `docs/09` on a throwaway artefact, before they touch a template | `examples/05-theme-toggle-demo/build_theme_toggle_demo.py` |
| [06](06-chart-palette-demo/) | The eight chart types and every colour family in `docs/10`, side by side with a palette switcher | `examples/06-chart-palette-demo/build_chart_palette_demo.py` |
| [07](07-topbar-pattern-demo/) | A neutral top bar with a menu and an info panel, keyboard-operable, for issue #15 | `examples/07-topbar-pattern-demo/build_topbar_demo.py` |
| [10](10-consolidated-standalone-demo/) | The JavaScript-resilience pattern: what a file still says when scripting is blocked | `examples/10-consolidated-standalone-demo/` (see its README) |
| [13](13-js-free-standalone-poc/) | A standalone page with no script at all, for issue #30 | see its README |
| [14](14-chart-emulation-nojs-poc/) | Which of twelve chart types survives without JavaScript, and which does not | see its README |
| [15](15-chart-library-comparison-poc/) | Chart.js against hand-rolled SVG against a Matplotlib image, on the same data | see its README |
| [16](16-embedding-mode-comparison-poc/) | The embedding modes compared, for issue #39 | see its README |
| [17](17-multi-regime-day-board/) | An operational day board for an organisation running three régimes with three owners | `examples/17-multi-regime-day-board/build_day_board.py` |
| [18](18-portable-slide-deck/) | A slide deck as one portable file, its first real use of the deck template | `tools/build_slide_deck.py` |
| [19](19-tun-pitch/) | The project's own pitch, told with the thing it is about | see its README |
| [20](20-tun-for-kommunikasjon/) | The idea explained for a communications reader, in their vocabulary | see the file itself |
| [21](21-slide-deck-detail-overlay/) | A detail overlay, `vmin` typography and an extended keyboard map on the deck | see its README |
| [22](22-xlsx-from-file/) | A real `.xlsx` read from `file://` with no library, in the browser | see its README |
| [23](23-process-diagram/) | A process diagram that draws this repository's own workflow: lanes, branches, improvement notes | `tools/build_process_diagram.py examples/23-process-diagram/fem-roller.process.txt` |
| [24](24-editable-document/) | Text you can change in the browser and download again, still one file | see its README |
| [25](25-living-idea-picture/) | The idea as a moving, explorable picture with no script | see its README |
| [26](26-kpi-board/) | The four flags no other example used: a KPI strip, `--measure-kind rate`, English chrome, and the feedback link — plus the guard that refuses a misleading mean | `examples/26-kpi-board/generate_data.py`, then the commands in [its README](26-kpi-board/README.md) |
| [27](27-survey-board/) | Survey answers as a file that withholds small cells: k-anonymity built into the builder, name and free-text columns refused, a stacked distribution per question, and a test that proves the names never reach the page | `examples/27-survey-board/generate_data.py`, then the commands in [its README](27-survey-board/README.md) |
| [28](28-one-dataset-three-artefacts/) | The same 285 rows built three ways — every row, four numbers, and a pre-aggregated cube — so the choice between them stops being a guess, and the totals agree across all three | `examples/28-one-dataset-three-artefacts/` ships its CSV; the three commands are in [its README](28-one-dataset-three-artefacts/README.md) |
| [29](29-audience-split/) | The audience split as two files: one extract per audience, the same build command twice, and a test that reads both pages back to prove the narrow one carries none of the other teams' rows | `examples/29-audience-split/generate_data.py`, then the commands in [its README](29-audience-split/README.md) |
| [30](30-json-to-dashboard/) | The file an API hands you is nested JSON; the flattener that turns it into a flat table is fifteen lines, and it says out loud which assumptions it makes | `examples/30-json-to-dashboard/` ships the JSON, the flattener and the CSV; the commands are in [its README](30-json-to-dashboard/README.md) |
| [31](31-survey-crosstab/) | A cross-tab is where a per-cell floor stops working, so it gets an all-or-nothing rule: printed when every combination reaches the floor, dropped with its reason when one does not, and it needs one row per respondent to pair the answers at all | `examples/31-survey-crosstab/generate_data.py`, then the commands in [its README](31-survey-crosstab/README.md) |
| [32](32-rows-register/) | Sometimes the question is not a chart but the list: a register that searches, sorts and pages its rows in a self-contained file, with the first page written into the markup for a reader whose browser will not run the script | `examples/32-rows-register/generate_data.py`, then the commands in [its README](32-rows-register/README.md) |
| [33](33-comparison/) | The most common reporting question is a subtraction: two extracts of one measure, matched on a key, with the change beside each key and "new" or "gone" named rather than dropped. Colour stays neutral until the builder is told which direction is good news | `examples/33-comparison/generate_data.py`, then the commands in [its README](33-comparison/README.md) |
| [34](34-folder-index/) | A folder of built files has no order, so the reader picks one and hopes. The index is the front page: one card per file, read out of that file's own provenance block, with a file that cannot account for itself listed rather than described. No script, relative links, and the folder's own name instead of its path | `examples/34-folder-index/build_example.py`, then the commands in [its README](34-folder-index/README.md) |
| [35](35-timeline/) | "When does this happen, and what overlaps" is a picture, not two date columns. One bar per row on one axis, the same rows written out in a table underneath, and a refusal for every row that cannot be drawn honestly | `examples/35-timeline/generate_data.py`, then the commands in [its README](35-timeline/README.md) |
| [36](36-review-roundtrip/) | Every other artefact is one-way. A reader who disagrees with a number has a screenshot and a sentence that names neither the row nor the build. Here the file asks: press a button, click the row, write, copy one text block. It carries the build identity, the column order, the row's own cells and the figure the reader saw, so `read_review.py` finds the row again and reports what the file says beside it | `examples/36-review-roundtrip/build_example.py`, then the commands in [its README](36-review-roundtrip/README.md) |
| [37](37-printable-onepager/) | The artefact you hand over: one A4 sheet, printed or sent as a PDF, where nobody can filter it. Four numbers, the bars behind them, and the sentences that say what moved, because the reader cannot sort by the biggest change to find out. Its characteristic failure is not a broken layout: the page quietly becomes two, and nothing on screen shows it, so `verify_print.py` measures the printed page | `examples/37-printable-onepager/generate_data.py`, then the commands in [its README](37-printable-onepager/README.md) |
| [38](38-distribution/) | Every other artefact answers a question about a total, and a total hides the shape. One panel per group on the same intervals, every bar carrying its own count, the median drawn where it sits, and a recount in the suite that has to agree with the printed total. The mean is never shown without the median beside it | `examples/38-distribution/generate_data.py`, then the commands in [its README](38-distribution/README.md) |
| [39](39-scorecard/) | The monthly management report: many measures, one period, each with its history, its target and the distance between them. Status appears only when the direction and the bands were declared, a missing month breaks the line instead of sloping through it, and the gap is always latest minus target | `examples/39-scorecard/generate_data.py`, then the commands in [its README](39-scorecard/README.md) |
| [40](40-waterfall/) | A change is not answered by two totals and a subtraction: it is answered by the parts that moved it. A bridge where the steps float between the levels they move the total across, the largest are drawn and the rest are one exact sum, and the column adds up on the page. The axis does not start at zero, and the page says where it starts | `examples/40-waterfall/generate_data.py`, then the commands in [its README](40-waterfall/README.md) |
| [41](41-composition/) | A total hides what it is made of, and a share hides the level it is a share of. One column per period split into the categories that make it up, the period total above the column, shares rounded so they add to exactly 100,0, and a sentence for every category whose share and level move in opposite directions | `examples/41-composition/generate_data.py`, then the commands in [its README](41-composition/README.md) |
| [42](42-funnel/) | A funnel is a cohort passing stages, not four counts in a column. The stages are declared, the nesting is checked (a record at a later stage without the earlier one is a defect in the extract, refused by name), only the width carries the count, both conversion rates are printed, the drop between two stages is a number, and the worst step is named from the counts | `examples/42-funnel/generate_data.py`, then the commands in [its README](42-funnel/README.md) |
| [43](43-heatmap/) | Where the mass is, and where there is none. One number per row-and-column pair, shaded on a scale whose ranges are printed and whose rounded edges decide the bands, with every value printed in its own cell and the ink chosen per cell by measured contrast. An empty cell is hatched, never drawn as zero | `examples/43-heatmap/generate_data.py`, then the commands in [its README](43-heatmap/README.md) |
| [44](44-cohort/) | Of the people who started, how many are still here. One row per cohort, one column per period since that cohort started: the axis is derived from each person's earliest date, so a reversed extract gives the same grid. Every share is divided by its own cohort, a cell that cannot exist yet is hatched rather than drawn as zero, a cell counts people and not rows, and a cohort too small to speak about is named instead of drawn | `examples/44-cohort/lag_data.py`, then the commands in [its README](44-cohort/README.md) |
| [45](45-smallmultiples/) | Which of these groups behaves differently. One small panel per group, every panel on ONE scale that the page prints, because a per-panel axis makes a group moving between 4 and 8 look exactly like one moving between 400 and 800, with every number still true. A missing period is a break, never a bridge or a zero; the panel order is declared and printed; a truncated floor is allowed only with a warning that names it | `examples/45-smallmultiples/lag_data.py`, then the commands in [its README](45-smallmultiples/README.md) |
| [46](46-rank-change/) | Who moved, and how far. Two ranked columns with a line per entity, and the four ways that chart lies banked as checks: rank is not value, a newcomer is not a mover, a tie is a shared rank, and a line between two columns has no inherent direction (the first draft drew every climber as a fall) | `examples/46-rank-change/lag_data.py`, then the commands in [its README](46-rank-change/README.md) |
| [47](47-scatter/) | Two numbers that move together, and the one unit that sits apart. One point per unit on two measures, every point named, the axis span printed, and a fit line only when it is asked for and only with its coefficient and its count | `examples/47-scatter/generate_data.py`, then `tools/build_scatter.py` |
| [48](48-boxplot/) | The spread of twenty groups on one axis, which is where a histogram stops working. Quartiles by one declared convention, Tukey whiskers with the tail drawn as dots, n printed at every box, and all five numbers in a table | `examples/48-boxplot/generate_data.py`, then `tools/build_boxplot.py` |
| [49](49-gantt/) | Whether the plan was kept. A plan bar and an actual bar per task on one scale, the slip as a signed number of days, and an unfinished task as a WORD rather than a zero-length bar | `examples/49-gantt/generate_data.py`, then `tools/build_gantt.py` |
| [50](50-calendar/) | When in the week and when in the year. One cell per day aligned to weekday rows, a Monday start the browser gate measures, missing days hatched rather than pale, and a declared clamp when one peak would flatten the year | `examples/50-calendar/generate_data.py`, then `tools/build_calendar.py` |
| [51](51-bullet/) | Which of a long list is behind its own target. One row per unit with the target as a mark and the gap as a signed number, a direction the builder refuses to guess, and an axis that starts at zero when the data does | `examples/51-bullet/generate_data.py`, then `tools/build_bullet.py` |
| [52](52-pareto/) | Which few categories carry the total. Bars sorted largest first, a cumulative line on its own labelled axis, a folded tail that keeps its sum, and shares rounded so the column adds to exactly 100,0 | `examples/52-pareto/generate_data.py`, then `tools/build_pareto.py` |
| [53](53-sankey/) | Where a quantity went between stages, and that it adds up: every middle node takes in exactly what it passes on (checked to the last unit), one scale for the whole picture, ribbons that tile their node with no gap, and a cycle refused rather than drawn | `examples/53-sankey/generate_data.py`, then `tools/build_sankey.py` |
| [54](54-showcase/) | Every example in the repository on one page: a real photograph of each built artefact taken by a browser at build time, with the command from its own README, so a stale picture or a broken rebuild is visible at a glance | `tools/build_showcase.py --out examples/54-showcase/oversikt.html` |

## Checking one

Every artefact is opened in a real browser before it is trusted, because a clean
build log is not evidence. Two tools do that:

```bash
# renders, charts drawn, filters re-render, reset works, screenshot, console clean
uv run --extra verify python tools/verify_dashboard.py examples/01-hello-dashboard/salg-dashboard.html

# six viewports: no overflow, no touch target under 44x44 px, no text under 14 px
uv run --extra verify python tools/verify_viewports.py examples/01-hello-dashboard/salg-dashboard.html
```

`tools/verify_viewports.py` runs on every artefact here. It found two real
defects when it was written: dashboards with 37 px controls and 11 px axis
labels, and a feedback link that was 17 px tall. Both are fixed in the templates.

## Adding one

1. A directory numbered one higher than the highest here.
2. The source data, generated by a seeded script next to it — never real data
   (`docs/06`, and the rule at the top of `AGENTS.md`).
3. A `README.md` that states the claim in one sentence, shows the rebuild command,
   and shows the verify command — `verify_viewports` and `verify_a11y` at least, and
   whatever measures the thing this artefact claims (`verify_print` for a printed sheet).
   `tests/test_gate_coverage.py` fails on a shipped artefact no documented command names,
   so this step is also what makes the example measured at all: CI is the only place the
   floors and the a11y rules run, and on the internal forge CI skips.
4. A row in the table above. An example nobody can find is not an example.
5. `python3 tools/check_all.py` before the commit, plus
   `uv run --extra verify python tools/verify_documented.py --engines chromium` for anything
   that renders: a green `check_all` says nothing about a text floor or a touch target.
   What it will catch, and what to do about it, in `docs/12`:
   * a new template's boilerplate is organisation-specific debt, so bank it in the same
     commit (`python3 tools/check_core_is_generic.py --baseline > tools/core_generic_baseline.json`,
     after diffing that the file only grew by your own lines);
   * a new data file is either gitignored or added to `ALLOWED_DATA` in
     `tools/check_no_real_data.py`, and it must be tracked;
   * a new doc needs a `**Reader:**` line and a row in `docs/index.md` under that reader,
     and a real markdown link from outside `docs/` or it is unreachable;
   * a new i18n key must be used somewhere, in both languages.

Prose in English, artefact chrome in the language of its reader (`--lang nb|en`).
