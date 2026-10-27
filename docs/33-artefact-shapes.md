# 33. Twenty-six builders: which shape answers which question

**Reader:** user — you have data and a sentence about what you want to know, and you need to pick the right file to build.

The hardest part of this toolkit is not the build. It is the first thirty seconds, when a
question that sounds ordinary ("how are we doing?") has to become a shape. Pick the wrong one
and every later step inherits the mistake: the page is built, verified, shared, and answers a
question nobody asked.

So this page is a chooser, not a reference. One row per shape, with the question it answers in
the words people actually use, and the one thing it refuses to do. Every row links to its
builder and to a working example. If your question is not in this table, it is one of the
[five this format does not answer](#what-no-shape-answers).

## The shapes

| If the question is | The shape | Builder | Example |
|---|---|---|---|
| "I have a spreadsheet and want charts people can filter" | A bundled dashboard: filters, KPI figures, charts, a table | `tools/build_dashboard.py` | [01](../examples/01-hello-dashboard/) |
| "There are millions of rows, I only need the totals" | A dense cube: one cell per filter combination, exact sums | `tools/build_cube_dashboard.py` | [03](../examples/03-cube-dashboard/) |
| "Why did the number change" | A waterfall: what each contributor added or took away, from one level to the next | `tools/build_waterfall.py` | [40](../examples/40-waterfall/) |
| "Which keys moved, and by how much" | A comparison: every key, both periods, the difference stated | `tools/build_comparison.py` | [33](../examples/33-comparison/) |
| "When does this happen, and what overlaps" | A timeline: one axis, one bar per task, the dates written out underneath | `tools/build_timeline.py` | [35](../examples/35-timeline/) |
| "How long do these cases take, and what is typical" | A distribution: the spread, the buckets, the tail, never an average alone | `tools/build_distribution.py` | [38](../examples/38-distribution/) |
| "How many get through, and where do they stop" | A funnel: one cohort passing declared stages, both conversion rates printed | `tools/build_funnel.py` | [42](../examples/42-funnel/) |
| "Where is it busy, and where is it thin" | A heatmap: one cell per row-and-column pair, value printed in the cell | `tools/build_heatmap.py` | [43](../examples/43-heatmap/) |
| "What is this total made of" | A composition: one column per period, split into its parts, columns summing to 100 | `tools/build_composition.py` | [41](../examples/41-composition/) |
| "Who comes back, and when do they drop off" | A cohort grid: one row per cohort, one column per period since it started | `tools/build_cohort.py` | [44](../examples/44-cohort/) |
| "Where did the volume go between stages" | A Sankey: flows between nodes in stages, every middle node balanced, one shared scale | `tools/build_sankey.py` | [53](../examples/53-sankey/) |
| "Which few explain most of it" | A Pareto: categories sorted by size, with the cumulative share and the folded tail | `tools/build_pareto.py` | [52](../examples/52-pareto/) |
| "Which of these is behind its target" | A bullet: one row per unit, its value against its own target, the gap as a signed number | `tools/build_bullet.py` | [51](../examples/51-bullet/) |
| "When in the week, and when in the year" | A calendar: one cell per day, aligned to weekday rows, missing days hatched | `tools/build_calendar.py` | [50](../examples/50-calendar/) |
| "Was the plan kept, and by how much did it slip" | A Gantt: a plan bar and an actual bar per task, the difference as a signed number of days | `tools/build_gantt.py` | [49](../examples/49-gantt/) |
| "Which of these is wide, which has a tail" | A box plot: one box per group on one axis, n printed, the tail drawn as dots | `tools/build_boxplot.py` | [48](../examples/48-boxplot/) |
| "Do these two move together, and which unit is the odd one out" | A scatter: one point per unit on two measures, named, with the axes' span printed | `tools/build_scatter.py` | [47](../examples/47-scatter/) |
| "Which of these units behaves differently" | Small multiples: one small panel per group, all on one printed scale | `tools/build_smallmultiples.py` | [45](../examples/45-smallmultiples/) |
| "Who moved up or down, and by how much" | A rank change: two ranked columns, a line only for what is in both periods, values printed at both ends | `tools/build_rank_change.py` | [46](../examples/46-rank-change/) |
| "The monthly report, with targets and status" | A scorecard: each measure, its history, its target, the gap | `tools/build_scorecard.py` | [39](../examples/39-scorecard/) |
| "Give me the list itself" | A register: one row per case, sortable, filterable, nothing aggregated | `tools/build_register.py` | [32](../examples/32-rows-register/) |
| "The audience answered a survey" | A survey board: one block per question, counts and shares, a cross-tab when the answer differs by unit | `tools/build_survey_dashboard.py` | [27](../examples/27-survey-board/) |
| "Who does what, in which order, and where it breaks" | A process diagram: declared lanes and steps, with the faults marked | `tools/build_process_diagram.py` | [23](../examples/23-process-diagram/) |
| "It has to be one sheet I can hand over" | A printable one-pager: four figures, the chart, the sentences, on one A4 | `tools/build_onepager.py` | [37](../examples/37-printable-onepager/) |
| "A folder of these needs a front page" | A folder index: what each file answers, read from its own provenance block | `tools/build_index.py` | [34](../examples/34-folder-index/) |
| "I have to present it, not explore it" | A slide deck: keyboard navigation, a section rail, same offline guarantee | `tools/build_slide_deck.py` | [18](../examples/18-portable-slide-deck/) |
| "The reader disagrees and wants to say which row" | A review layer on an existing artefact, handed back as one text block | [31](31-review-roundtrip.md) | [36](../examples/36-review-roundtrip/) |

## When two shapes compete

The questions overlap, and the choice is usually decided by what the reader will do next.

- **Distribution, box plot or small multiple.** One group's shape: a distribution. Many groups'
  spread on one axis: a box plot. Many groups' *paths* over time: a small multiple.
- **Distribution, heatmap or small multiple.** One number per group: a distribution. One number
  per group *and* period, and the question is where the mass sits: a heatmap. The same, and the
  question is which group's *path* differs: a small multiple.
- **Comparison or waterfall.** A comparison answers "which keys moved". A waterfall answers
  what the moves *add up to*, which is a different sentence and a different picture. When both
  are wanted, build the waterfall and keep the comparison table underneath it.
- **Funnel or Sankey.** A funnel is one cohort passing declared stages in a line. A Sankey is a
  network: several starts, several ends, and flows meeting. If there is one path through it, the
  funnel is the clearer page.
- **Composition or Pareto.** A composition asks what a total is made of, and every part is
  drawn. A Pareto asks which parts matter, so it sorts them and folds the tail. If the reader
  needs every category named, it is a composition.
- **Scorecard or bullet.** A scorecard judges a few measures over time against declared
  targets. A bullet judges a long list of units in one period. Both refuse to draw status
  without a declared direction.
- **Heatmap or calendar.** A heatmap compares two categories. A calendar compares days, and its
  columns are weeks: use it when the question is about the weekday or the season, not about
  departments.
- **Timeline or Gantt.** A timeline shows when things happen. A Gantt shows whether the plan
  was kept: it needs a planned *and* an actual date for the same task. With only one set of
  dates there is nothing to compare, and the timeline is the page.
- **Funnel or cohort.** A funnel counts one cohort passing *stages*. A cohort counts a different
  set of people each *period*. If the axis is time since someone started, it is a cohort.
- **Scatter or small multiple.** Both compare units. A small multiple asks "does this group's
  path differ from the others"; a scatter asks "do these two measures move together". If the
  question needs a period on one axis, it is not a scatter.
- **Scorecard or dashboard.** A dashboard is explored; a scorecard is read once a month against
  declared targets. A scorecard with no direction and no bands is a dashboard pretending to be
  a verdict, and `build_scorecard.py` refuses to draw status without both.

## What no shape answers

These are real questions and the honest answer is another tool, not a worse file:

- **row-level security.** The security boundary here is the folder. If two audiences must see
  different rows, build two files and put them in two folders. A filter in a shared file hides
  nothing: the rows are in the file.
- **a live feed.** The file is a snapshot with a provenance block saying when it was taken. A
  number that must be current needs a service, and that is a different project.
- **row-level drill from a cube.** The cube keeps totals. If a reader must reach individual
  rows, pair the cube with a register, or stay on the rows path.
- **an editable input.** The review layer (31) carries a reader's disagreement back as text, by
  hand or by script. It is not a form that writes to a database.
- **a chart nobody must verify.** Every shape here prints its numbers, because a picture that
  cannot be checked against a table is a claim, not a report.

## What is not here yet

This page lists what exists. The other half of the map, the shapes somebody has asked for and
nobody has built, is [34](34-artefact-ideas.md): each candidate with the trap that makes it
harder than it looks, whether the data is in reach, and the five things a new shape has to pay
for before it is worth building.

## Checking you picked right

Before you build, answer these three in one sentence each. If you cannot, the shape is not yet
decided:

1. What does the reader do with this file the day after they open it?
2. What is the one number they must be able to quote, and where is it printed?
3. What would make this page wrong, and which gate catches it?

Each example's README names its own gate. `tests/test_skill_routes.py` keeps every shape on
this page reachable from a skill, so a new kind cannot be added without a route and a row here.
