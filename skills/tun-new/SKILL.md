---
name: tun-new
description: Build a new standalone interactive dashboard from a data file (Excel, CSV, JSON, or a query result). Produces a single self-contained HTML file that can be shared through SharePoint or OneDrive with no Power BI licence, no workspace, and no admin approval. Use when someone wants a dashboard, a report, charts from a spreadsheet, or to share data interactively.
---

# Build a standalone dashboard

**Tier and cost, for the first reply:** Tier 1, no approvals and no licence; the file goes
where the reader's existing folder permissions already reach.

You are producing a **Tier 1 portable dashboard**: one self-contained `.html` file,
data inlined, no server, no CDN. See `docs/02-architecture.md`.

Tell the user this up front, in one line:

> "This will be a single file you can drop in SharePoint or OneDrive — anyone who can
> open the folder can open the dashboard. No Power BI licence, no approvals needed."

## Step 1 — Who sees what (do this FIRST, never skip)

Ask, in plain language:

> **"Does everyone who opens this see the same numbers, or should different people see
> different data?"**
> *(For example: should a regional manager only see their own region?)*

- **Same for everyone** → continue to step 2.
- **Different per audience** → **build one per audience.** Don't refuse, and don't put a
  filter in a shared file. Say:
  > "Then I'll build one per audience — same dashboard, different data file, each in its
  > own folder so SharePoint controls who gets which. Which groups, and who's in each?"

  Then split the data *before* writing it (one `--data` extract per group), build with
  `--mode paired`, and give each group its own folder. The folder permission **is** the
  security boundary, and it is visible and auditable in a way a filter expression isn't.

  > ⚠️ The rule that does not bend: **never write a row into a file whose audience
  > shouldn't see it.** Split the data, don't filter it at display time — a filter in the
  > browser is decoration, the data is still in the file.

Also check: does the data contain personal data (names, account numbers, national ID)? If
so, flag it — the file is as readable as the folder it sits in, and it will land on
laptops. Confirm the audience before continuing.

## Step 2 — Understand the data

Read the source file. Do not guess at its shape.

- `.xlsx` / `.xlsm` → convert to CSV first (see `tun-data`), then read
- `.csv` / `.tsv` / `.json` → read directly
- a database/Snowflake query → run it, save the result as CSV

Then report back what you found, concretely:

> "The file has 776 rows and these columns: Maaned, Region, Produkt, Kanal, Antall,
> Belop. Antall and Belop look numeric; the rest are categories."

## Step 3 — Decide the shape of the dashboard

You need four things. Infer sensible defaults from the data and **propose** them
rather than interrogating the user field by field:

| Need | What it drives | How to infer |
|---|---|---|
| **measure** | the number being summed, KPIs, both charts | the numeric column that looks like a value/amount/count |
| **dimension** | the bar chart, "what breaks it down" | the categorical column with a useful cardinality (3–20 distinct) |
| **time** | the line chart (optional) | a column of dates, months, or years |
| **filters** | the dropdowns | 1–4 categorical columns with low cardinality |

Propose it as a sentence and let them correct it:

> "I'll show total **Belop** broken down by **Produkt**, trended over **Maaned**, with
> filters for **Region**, **Produkt** and **Kanal**. Sound right?"

Avoid a high-cardinality dimension (an ID column) — the bar chart becomes noise.
Avoid making the measure a column that is really an identifier.

**Is the measure an amount or a rate?** An amount (kroner, a count) adds up, and its
mean per row means something. A rate is a value per person or per unit (kroner per
person): add `--measure-kind rate`, and the KPI cards become the sum, the mean per
`--time` value and the number of `--dimension` values, with no mean per row. A rate
that does not add up across rows (a share, an interest rate) is the wrong fit for this
builder, because the charts sum the measure. `--kpis total,distinct` picks the cards and
their order directly (`--help` lists them). Either flag gives the cards labels a reader
understands; with neither, the four cards are the ones this builder always made.

## Step 3b — Pick a mode

Two options. Ask which fits, in one sentence:

> "Do the numbers need to keep updating, or is this a fixed picture?"

| Mode | What you get | Use when |
|---|---|---|
| **`paired`** *(default for recurring)* | `dash.html` + `data.js` side by side. Replace `data.js` and **everyone sees new numbers** — no rebuild, no republish. | anything recurring; anything where "is this current?" will be asked |
| **`bundled`** | one self-contained file, data inside | it must leave Eksempel AS (email attachment), or must survive with no folder around it |

Paired mode is the more useful default: the dashboard shell stays ~20 KB, the data is a
separate file that OneDrive syncs, and updating is "drop in a new data.js".

## Step 4 — Build

```bash
python3 tools/build_dashboard.py \
  --data <source.csv> \
  --title "<a title in the user's own words>" \
  --dimension <col> --measure <col> --time <col> \
  --filters <col,col,col> \
  --source "<where this data came from, in words>" \
  --requested-by "<the role or team that asked>" \
  --mode paired \
  --out dashboards/<slug>/dash.html
```

On Windows, `python3` is `py -3`: `python3` is not a command there unless the Microsoft Store alias is installed. The rest of the line is the same.

In paired mode `data.js` is written next to `--out`, so give each dashboard its own
folder. **The two files must stay together.**

The `--source` and `--requested-by` values become a provenance block in the file.
**Always fill them in properly.** A dashboard whose numbers cannot be traced back to
a source is a liability, and someone will ask in three months.

Never rebuild a committed example or a shipped dashboard without those two flags. A
rebuild that omits them silently replaces a descriptive source and a real requester with
a filename and `not stated`, with no warning — the provenance block
degrades and the file still looks fine.

If the build fails on size (>50 MB), do not fight it — **pre-aggregate**. Group the
data to the grain the dashboard actually displays and rebuild. That almost always
fixes it, and it makes the dashboard faster too.

### When the user wants the list, not a chart: build a register

"Give me the rows", "a list I can search", "the open cases with a filter" — that is not a
dashboard with fewer charts, it is a different artefact. `tools/build_register.py` writes a
self-contained file whose whole job is the list: a search field, sortable columns, pages,
and the first page written into the markup so it survives a browser that will not run the
script.

```bash
python3 tools/build_register.py \
    --data <source>.csv \
    --title "<title>" \
    --columns Sak,Tittel,Enhet,Mottatt,Status,Dager \
    --numeric Dager --sort Dager --desc \
    --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

Two things to say to the user before you build one:

- **every row you pass is in the file**, and anyone with the file can search all of it. If
  two audiences must see different rows, build two files from two extracts — do not filter
  one. `--columns` drops the rest before anything is written, which is how a column such as
  a name or an internal note stays out.
- a register can group, and a group can carry its own numbers: `--group-by Enhet` puts a
  band above each group stating how many rows it holds and what its numeric columns
  sum to. The count and the sums follow what is on screen, so a search narrows them
  and a group split across two pages keeps one total. What it still will not do is a
  chart: if they want the shape of the numbers, that is `build_dashboard.py`.

Measured: 1 200 rows → a 120 KB file, search on a keystroke, `verify_viewports` clean, and
under 40 rem each row becomes a labelled card so a phone never scrolls a table sideways.

### When the question is "what moved": build a comparison

"Show me what changed since last month", "these two extracts", "where did it go up and
where did it go down" — that is neither a dashboard nor a register. It is one subtraction
per key, and it should be a column, not a chart with two dates stapled on.
`tools/build_comparison.py` matches two extracts on a key and writes one file per key:
before, after, the change, the percentage, and what is new or gone.

```bash
python3 tools/build_comparison.py \
    --before <earlier>.csv --after <later>.csv \
    --key Region --value Omsetning \
    --title "<title>" --before-label September --after-label Oktober \
    --source "<where the two extracts came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

Three things to say to the user before you build one:

- **a key that appears more than once is summed**, because an extract is usually one row
  per transaction. If their numbers are already one row per key, that is the same answer.
- **a key in only one extract is shown as "ny" or "borte"**, never dropped. A unit that
  stopped reporting and a unit with zero are the same number and not the same fact. If they
  expected the key to be there, that is a question for whoever produced the extract.
- **colour stays neutral unless they say which direction is good news.** More revenue and
  more overtime are the same arithmetic. `--meaning up` or `--meaning down` turns on the
  approved status colours; without it the sign and the words carry the movement.

That last point is worth saying out loud: a page that paints every increase green has made
a judgement on the reader's behalf, and sometimes it is the wrong one.

### When the question is "why did it change": build a waterfall

"What explains the drop from last month", "break it down by unit", "does it add up" — a
comparison says which keys moved; this says what the moves amount to. `tools/build_waterfall.py`
reads one extract with both periods in it and writes a bridge: the opening figure, one bar per
contributor floating between the levels it moves the total across, and the closing figure.

```bash
python3 tools/build_waterfall.py \
    --data <extract>.csv \
    --measure Omsetning --dim Produkt --period-col Måned \
    --from September --to Oktober \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

Four things to say to the user before you build one:

- **the page adds up, and that is the point.** Opening plus every step equals closing, printed
  in one line. If their spreadsheet's bridge does not close, the difference is a real finding.
- **the drawing shows the largest steps and sums the rest into one bar**, named with how many
  it holds. Every contributor is still in the table, so nothing is hidden.
- **the axis does not start at zero**, because steps that are small against the level would
  disappear. The page says where the axis starts; if they need the full scale, say so and we
  will not pretend the picture has it.
- **a contributor that only exists in one period is a step**, named *ny* or *borte*. A product
  launched in October explains part of the change, and burying it in an "other" column hides
  the thing the reader is looking for.

### When the question is "how many get through": build a funnel

"How many applications reach a decision", "where do the cases stop", "what is our conversion" —
one bar per stage, its width the number of records that reached it, with both conversion rates
and the number lost between two stages. `tools/build_funnel.py` builds it from an extract with
one row per record per stage it reached.

```bash
python3 tools/build_funnel.py \
    --data <extract>.csv --id <record number> --stage <status column> \
    --stages "Mottatt,Vurdert,Innstilt,Utbetalt" \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- **the stages are declared by you, in order.** Ask the user for them; never infer the order
  from the data.
- **the nesting is checked.** If a case appears at a later stage without the earlier one, the
  build refuses and names the pair. That is usually a real defect in the extract, and it is
  worth saying out loud to the user rather than drawing around.
- **two percentages, not one**: of the first stage and of the stage before. Say which is which
  when you hand it over, because the difference is the whole question.
- the width carries the count and nothing else does. Do not "make it a funnel" by scaling both
  dimensions: a fall of half the records then looks like a loss of three quarters.

### When the question is "where is the mass": build a heatmap

"Which unit is busiest which week", "where do the errors concentrate", "where is it thin" —
one cell per row-and-column pair, shaded by its value, with the value printed inside the cell.
`tools/build_heatmap.py` builds it from an extract with one row per pair, or several rows per
pair that it adds up.

```bash
python3 tools/build_heatmap.py \
    --data <extract>.csv --row <row column> --col <column column> --measure <number column> \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- **the scale is on the page, with numbers.** Every shade prints the range it stands for, so a
  reader can convert a colour back into a figure. Never hand over a heatmap whose legend is
  only colours.
- **an empty cell is not a zero.** No cases and no cases recorded are different findings. The
  builder hatches the empty cells and says how many there are; tell the user, because an absent
  cell is usually the thing worth asking about.
- **`--clamp <top>` when one cell dwarfs the rest.** Without it a single outlier flattens every
  other cell into the palest shade. Above the top the darkest shade means "at least", and the
  page counts how many cells sit above it.
- **more than twelve columns or sixty rows is a table, not a picture.** The builder refuses.
  Group the columns or split the page; do not shrink the drawing.
- **say which order the rows are in.** Sorted by total unless you pass `--row-order`. A time
  column always wants `--col-order`, or the weeks arrive alphabetical instead of in sequence.

### When the question is "what is this made of": build a composition

"What are the hours going to", "how is the case mix changing", "which unit takes the biggest
share" — one column per period, split into the categories that make it up.
`tools/build_composition.py` builds it from one extract, and it prints the period's total above
each column, because a share hides the level it is a share of.

```bash
python3 tools/build_composition.py \
    --data <extract>.csv \
    --measure Timer --cat Oppgave --period-col Kvartal \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- **the shares add up to exactly 100,0**, rounded by largest remainder, and every level is
  printed beside its share in the table. Say this: the picture is the mix, the table is the
  account.
- **a share can rise while the figure falls.** The page names every category where that
  happens, in words, from the numbers. Lead with it if there is one: it is usually the finding.
- four categories are drawn and the rest become one band named with its count; `--top` can
  lower that, never raise it, because the approved palette has four slots and a column of ten
  bands cannot be read.
- a negative figure is refused. If the data has negatives in it, the question is a change, not
  a mix: build a waterfall instead.

### When one measure hides its shape: build a distribution

"How long do these cases take", "how big are the invoices", "who is the typical case" — a
total and a mean answer none of it: three cases at 1, 1 and 40 have the same sum as eleven at
4, and a mean of 14 describes neither. `tools/build_distribution.py` writes the bucket counts
per group, with the median, the 90th percentile and the largest value beside the picture.

```bash
python3 tools/build_distribution.py \
    --data <extract>.csv --measure-col Dager --group-col Enhet \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- the intervals are a presentation choice and the page prints them, so two builds can be
  compared only when they share edges.
- the mean is never shown alone: a mean far above the median is the sentence they need.
- `--min-group 5` names a group too small to have a shape instead of drawing it.

### When it is the monthly report: build a scorecard

A short list of measures, each with this period's figure, the last, the same month last year,
a target and a status. `tools/build_scorecard.py` builds it, and it needs two things declared
before any colour or status word appears: which direction is good, and the bands.

```bash
python3 tools/build_scorecard.py \
    --data <monthly>.csv \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --green-at 1.00 --amber-at 0.95 \
    --out dashboards/<slug>.html
```

- **no direction, no verdict**: an increase is good for revenue and bad for complaints. Give
  `--lower-is-better`, or a `Retning` column in the file.
- **no bands, no status word.** "Near target" is a policy; ask which bands they use.
- there is no amber in the approved palette, so the middle band uses the neutral token and the
  word carries the meaning. Do not invent a third colour.

### When the question is "who comes back": build a cohort grid

"Do people stay", "when do they drop off", "is the January group better than the March one" —
one row per cohort, one column per period since that cohort started, shaded by the share still
active. `tools/build_cohort.py` builds it from an extract of one row per person per activity,
and the cohort is each person's earliest date, never the file's row order.

```bash
python3 tools/build_cohort.py \
    --data <extract>.csv --id <person column> --date <date column> [--period month|week] \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- **the denominator is that row's own cohort.** Divided by the whole file every cell is small
  and the picture says nothing. The size is printed under the cohort name, and column +0 is
  that size by definition, not a finding.
- **a cell that cannot exist yet is hatched, never zero.** "Not yet" and "nobody came back" are
  opposite findings. If the reader asks about the empty triangle, that is the answer: the
  period has not happened.
- **a cell counts people, not rows.** Three visits in a month is one person.
- **`--min-cohort <n>`** names a cohort too small to speak about, with its size, instead of
  drawing a square that wears the same colour as a finding.
- **the bands are fixed percentages**, so two pages can be read against each other. Print the
  legend, because a share is a second reading of a number already in the cell.

### When the question is "who moved up or down": build a rank change

"Who is top now" is a sorted list. "Who moved" is a different question, and a table answers it
badly. `tools/build_rank_change.py` draws two ranked columns with a line per entity, so the
movement is one glance instead of two columns compared by eye.

```bash
python3 tools/build_rank_change.py \
    --data <extract>.csv --entity <what is ranked> --period <period column> \
    --measure <number column> --from <earlier period> --to <later period> \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- **rank is not value.** A product can climb four places on a rounding difference and fall one
  place while growing. The value is printed at both ends; never hand over a rank chart that
  prints only the ranks.
- **a line means "this entity is in both periods".** A newcomer or a leaver gets a stub and a
  word. If the reader asks where somebody came from, that is the answer: they were not there.
- **a shared rank is shared:** 1, 1, 3, with a line on the page saying so. Do not let anyone
  "fix" the gap in the numbers.
- **say which way "up" is.** A solid line climbs and a dashed one falls, and the page does not
  know which direction anybody wanted. If the reader needs good or bad, that is
  `build_scorecard.py`, which requires a declared direction and two bands.
- **more than eighteen entities is a list again.** The builder refuses; filter the extract to
  the part being asked about.

### When the question is "which of these behaves differently": build a small multiple

"Which unit is the odd one out", "do all four follow the same path", "who is moving and who is
flat" — one small panel per group, all of them on **one** scale. `tools/build_smallmultiples.py`
builds it from an extract of one row per group per period.

```bash
python3 tools/build_smallmultiples.py \
    --data <extract>.csv --group <group column> --period <period column> --measure <number column> \
    [--periods A,B,C] [--order name|latest|change] [--truncate] \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- **the scale is shared and printed.** This is the whole artefact. A panel with its own axis
  makes a group moving between 4 and 8 look exactly like one moving between 400 and 800, with
  every number still true and nothing on the page looking wrong. Never "improve" it by letting
  each panel fit itself.
- **zero is the floor** unless you pass `--truncate`, and then the page carries a warning that
  names the floor. A truncated axis is a legitimate choice and an illegitimate surprise.
- **a missing period is a break, never a bridge and never a zero.** Tell the user how many
  gaps the page counted.
- **`--periods` when the labels do not sort as text.** Without it the labels are sorted
  alphabetically, which is right for `2026-W03` and wrong for `uke 1 … uke 10`.
- **`--order latest|change`** when the reader's question is "who is highest now" or "who has
  moved". The page says which rule it used, and the two give different first panels.
- **more than sixteen groups is not a small multiple**, it is a table. The builder refuses.

### When the question is "which of these is wide, which is late": build a box plot

"Compare the spread across twenty units", "who has the tail", "which group is slow on a bad day
and not just on average" — one box per group on one axis. `tools/build_boxplot.py` builds it from
one row per observation.

```bash
python3 tools/build_boxplot.py \
    --data <extract>.csv --value <number column> --group <group column> \
    [--order median|name] \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- **the quartiles are a convention, and the page states which one.** Say the same thing when you
  hand it over: a reader who recomputes in another tool may get a different number on a small
  sample, and neither tool is wrong.
- **n stands beside every group.** A box over four observations looks exactly like a box over
  four hundred, so quote the count with any claim about a group.
- **the whisker is Tukey's 1.5 IQR, and the dots beyond it are the tail.** If the reader's
  question is about the worst cases, those dots are the answer, and their count prints.
- **a box hides the shape.** Two groups with the same quartiles can be one peak or two. If the
  shape is the question, that is `build_distribution.py`, not this.
- **more than 24 groups is a wall.** The builder refuses; group the smallest together.

### When the question is "do these two move together": build a scatter

"Does longer waiting mean lower satisfaction", "are the big units also the slow ones", "who is
the odd one out on these two numbers" — one point per unit in a plane of two measures.
`tools/build_scatter.py` builds it from an extract of one row per unit.

```bash
python3 tools/build_scatter.py \
    --data <extract>.csv --label <unit column> --x-col <first measure> --y-col <second measure> \
    [--group <category column>] [--trend] [--labels auto|on|off] \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- **this page cannot say one causes the other, and it must not look as if it does.** The picture
  shows that two measures move together *in this sample*. If the reader needs a cause, that is a
  different piece of work.
- **names, not just dots.** A cloud with no names can be looked at and not acted on: the reason
  to draw it is usually the one unit that sits apart. Keep `--labels auto`, and if the page says
  the names are in the table, say the same thing when you hand it over.
- **`--trend` only when the reader asked whether they move together**, and read the coefficient
  out loud with its `n`. A line through a cloud with no coefficient is an assertion.
- **paste the summary sentence into the reply.** It states the span of both axes and who sits
  highest and lowest, and a reader who only reads the sentence still gets the answer.
- **more than 120 units is a blob, not a scatter.** Aggregate to one row per group first, or use
  the heatmap, which is built for density.

### When the question is "where did the volume go": build a Sankey

"Which channels end up escalated", "what happens to the cases we pass on" — volume traced through
stages, where every middle node passes on what arrived. `tools/build_sankey.py` builds it from one
row per flow.

```bash
python3 tools/build_sankey.py \
    --data <extract>.csv --from <where it leaves> --to <where it arrives> --value <quantity> \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- **it must balance, and the builder refuses when it does not.** A middle node with more in than
  out is a picture where volume vanishes; quote the balance check when you hand the page over,
  because it is the reason to believe the drawing.
- **one scale for the whole picture.** A stage carrying less volume is visibly shorter; say that
  when you explain it.
- **a cycle is refused**, not drawn. If volume can return to an earlier stage there are no
  stages, and the honest page is a heatmap of the pairs.
- **the flows must be counted, not averaged.** A rate per channel has nothing to add up.
- **give it three stages or more.** Two nodes and one arrow is a number with a picture round it.

### When the question is "which few explain most of it": build a Pareto

"Where do eighty percent of the cases come from", "which of these forty reasons can we actually
fix" — categories sorted by size with the cumulative share, so the handful that carries the total
is a shape. `tools/build_pareto.py` builds it from one row per category.

```bash
python3 tools/build_pareto.py \
    --data <extract>.csv --label <category column> --value <additive number column> \
    [--top 12] [--threshold 80] \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- **quote the count, not the picture.** "Seven of twenty-two reach eighty percent" is the
  sentence; the bars are the evidence.
- **the sort is the claim**, so the page states it. Never sort by the source's order.
- **the values must be additive.** A rate or an average is not a Pareto: summing them is
  meaningless. Count first, then build.
- **the folded tail keeps its arithmetic.** Past `--top` categories the rest become one bar with
  its count in the name; the total does not move, and the cumulative line still ends at 100 %.
- **negatives are refused.** A credit makes the cumulative line run backwards; that is the
  waterfall's question, not this one.

### When the question is "which of these is behind its target": build a bullet

Forty units, each with a number and its own target, and the question is which of them is off
plan. `tools/build_bullet.py` draws one row per unit on one axis, with the target as a mark and
the gap as a signed number.

```bash
python3 tools/build_bullet.py \
    --data <extract>.csv --label <unit column> --value <number column> \
    --target <target column> --direction up|down [--target-note "<where the target comes from>"] \
    [--order gap|name] \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- **`--direction` is required.** A rise is good for coverage and bad for waiting time, and a
  page that does not know which way is better cannot say who is behind.
- **quote the count and the worst, not the picture.** "Seven of fourteen behind, worst 13,2"
  is the answer; the rows are the evidence.
- **pass `--target-note`.** A target is a decision, and naming where it came from lets a reader
  argue with the target instead of with the chart.
- **the gap is signed and in the measure's own unit.** Say the number with its sign when you
  hand the page over.
- **more than 30 rows is a wall.** Show the ones that are off target, or split the list.

### When the question is "when in the week, or when in the year": build a calendar

"Are Mondays always bad", "is August quiet", "which days were unusual" — one cell per day,
aligned to weekday rows, so a rhythm is a shape and not a table. `tools/build_calendar.py` builds
it from one row per day.

```bash
python3 tools/build_calendar.py \
    --data <extract>.csv --date <YYYY-MM-DD column> --value <number column> \
    [--from YYYY-MM-DD --to YYYY-MM-DD] [--clamp N] \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- **the week start is the claim.** Monday, stated on the page. A calendar whose week starts on
  the wrong day invents a pattern out of its own layout.
- **a day with no data is hatched, never pale.** Pale reads as "a little", which is a
  measurement nobody took. Tell the user how many days are missing; the page counts them.
- **`--clamp` when one peak flattens the year.** Without it a single busy day collapses every
  other day into one shade and the weekday rhythm disappears. The top band then prints a
  minimum, and the exact values stay in the two tables.
- **one row per day.** Several rows on one date is refused: sum or average them first, and say
  which you did.
- **more than 400 days is a year, not a page.** Pass `--from`/`--to`, or build one page per year.

### When the question is "was the plan kept": build a Gantt

"Are we on schedule", "which tasks slipped and by how much", "what is still open" — one bar for
what was planned and one for what happened, per task, on the same date axis.
`tools/build_gantt.py` builds it from an extract with four date columns.

```bash
python3 tools/build_gantt.py \
    --data <extract>.csv --task <name column> --start <planned start> --end <planned finish> \
    [--actual-start <column> --actual-end <column>] [--today YYYY-MM-DD] \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- **the slip is a signed number and never a colour.** Quote it as a number when you hand the page
  over ("five tasks finished after the plan, worst 14 days"). A red bar is a mood.
- **a task with no finish is not a bar.** It is "not started" or "running", and those are two
  different words on purpose; a zero-day bar would read as finished on time.
- **`--actual-start` and `--actual-end` go together.** With neither, this is the timeline (35).
- **dates are read only as YYYY-MM-DD.** If the extract has dd.mm, convert it before building
  rather than letting anyone guess which half is the month.
- **more than 28 tasks is a wall.** Keep the milestones and use the timeline for the rest.

### When the question is "when does this happen, and what overlaps": build a timeline

"Who is busy when", "do these two phases collide", "how long from start to end" — one time axis,
one bar per row, with the dates still written out in the table underneath so a reader can check
the picture instead of trusting it. `tools/build_timeline.py` builds it from an extract with a
start and an end column.

```bash
python3 tools/build_timeline.py \
    --data <extract>.csv --task-col <task column> --start-col <start date> --end-col <end date> \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- **`--today` draws the now-line**, and `--no-today` removes it. Without a now-line a reader
  cannot tell a plan from a record.
- **`--group-col` when the rows belong to lanes**, `--owner-col` and `--status-col` when who and
  where-it-stands are part of the question.
- **an end date that is not in the data is not a zero-length bar.** Say what the empty end means
  before you build; the builder will not invent a duration.

### When the audience answers a survey: build a survey board

One question per block, the answer distribution drawn, the counts printed, and a cross-tab when
the reader's real question is "does the answer differ by unit".
`tools/build_survey_dashboard.py` reads answers in long format, one row per answer given.

```bash
python3 tools/build_survey_dashboard.py \
    --data <answers>.csv --question-col <question column> --answer-col <answer column> \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- **`--segments <col>` for the cross-tab**, `--min-cell <n>` so a cell with four respondents is
  named rather than drawn as a percentage. A percentage of four people is noise wearing a
  number.
- **free text is not a distribution.** Keep the open answers out of the chart, or paste them
  beside it; do not let the builder bucket them into a bar.
- **`--wide`** when the extract is one row per respondent with a column per question.

### When it has to be handed over on paper: build a one-pager

The other artefacts are explored. This one is handed over: four figures, the chart behind them,
and the sentences that say what moved, on one A4 sheet, for paper or PDF.
`tools/build_onepager.py` builds it from the same extract a dashboard would use.

```bash
python3 tools/build_onepager.py \
    --data <extract>.csv --dimension <category column> --measure <number column> \
    --title "<title>" --source "<where the rows came from>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

- **there is no filter, no hover and no scroll**, because the reader is holding it. Every number
  the reader needs must be on the sheet.
- **`--period` and `--top`** pick the slice. Print the slice on the sheet, or the numbers are
  unattributable a week later.
- **check it in print preview** (`tools/verify_print.py`) before handing it over: a page that
  spills onto a second sheet has failed at the one thing it was built for.

### When the folder needs a front page: build a folder index

A folder of built artefacts has no order and no introduction. Whoever is handed it picks a file
name and hopes. `tools/build_index.py` writes the missing front page: what each file answers,
where its numbers came from, when it was built and for whom, each fact lifted out of the built
file's own provenance block.

```bash
python3 tools/build_index.py --dir dashboards/ --title "<folder title>" \
    --requested-by "<the role or team that asked>" --out dashboards/index.html
```

- **rebuild it after every rebuild.** The index reads the artefacts' provenance, so a stale index
  describes a file that no longer exists in that form.
- **`--include <glob>`** when the folder holds files that are not for this audience. The index is
  a publication surface: anything it lists is discoverable from it.

### When it has to be presented, not explored: build a slide deck

A dashboard in a meeting is a bad slide: someone else drives the screen. `tools/build_slide_deck.py`
writes the starter deck from `templates/portable-slide-deck.html`: keyboard navigation, a section
rail, and the same offline guarantee.

```bash
python3 tools/build_slide_deck.py --lang nb --out dashboards/<slug>-slides.html
```

- **it is a starter, not a finished deck.** You write the slides into the file; the builder only
  settles the controls, the language and the preview warning.
- **hash-based navigation is blocked in the SharePoint preview** (issue #47). Send the deck as a
  link or a download, not as a preview.

### When there are too many rows to inline: build a cube instead

If the source has more rows than fit comfortably (roughly >100 000), and the user only
needs **aggregates** — no "show me the underlying records" drill — switch builders
rather than tiers. `tools/build_cube_dashboard.py` inlines one pre-aggregated cell per
filter combination instead of the rows:

```bash
python3 tools/build_cube_dashboard.py \
    --data <source>.csv \
    --dims region,kategori,kanal,aldersgruppe \
    --time dato --time-grain month \
    --measures "belop:sum:kr,antall:sum" \
    --title "<title>" \
    --requested-by "<the role or team that asked>" \
    --out dashboards/<slug>.html
```

Measured: 4 000 000 rows → a 0.81 MB file, filter clicks at 0.10 ms, exact to the øre.
Still Tier 1, still zero approvals. See `docs/07-portable-cube.md`.

**Ask before choosing it**, because it costs the user something real:

- ✅ pick the cube when the questions are known and the answers are sums/counts
- ❌ do **not** pick it if the viewer may want row-level detail — the rows are gone
- ❌ do **not** promise a filter that was not compiled in; a new dimension = a rebuild
- ❌ `avg` is fine (derived as sum/count) but **distinct counts and medians are refused**,
  because they do not compose over cells. Do not work around that.

The builder warns when the cube is not actually smaller than the source data. If it
warns, inline the rows instead — the cube is the wrong shape for that dataset.

## Step 4b — Visual direction, in five decisions

The floor for "looks like a template" is far higher in a hand-built HTML file than in
Power BI, and clearing it is most of why a dashboard reads as credible. Five decisions,
made once, do nearly all the work.

**1. Palette: one dominant, one accent, one neutral**, plus an ink and a paper colour.
The accent must appear rarely enough that its appearance means something — the key
number, the active filter, the current state. An accent used everywhere is decoration;
used three times it is a signal.

**2. Avoid the current generated-look defaults.** Three palettes appear right now
regardless of subject, and people recognise them: cream near `#F4F1EA` with a
high-contrast serif and a terracotta accent; near-black with one acid-green accent;
broadsheet hairline rules in dense columns. All three are legitimate designs and all
three read as a default rather than a choice. Derive the palette from the subject, or
from the organisation's brand, and push contrast further than brand web examples do.

**3. Type: nothing below ~16px rendered.** If you are tempted to shrink type to make
content fit, cut content instead. The file must work offline, so use a system stack or
embed the font as base64 — a web-font link breaks on guest wifi and in a locked-down
tenant, which is exactly where these files get opened.

**4. Space beats density.** The clearest difference between a good standalone file and a
Power BI page is that the good one is not full. Content that does not fit belongs behind
a click, in a detail row, or cut.

**5. Motion only where it carries meaning.** A number arriving, a row highlighting under
discussion, a reveal following the order you explain things in. Nothing moves because
moving is available. Honour `prefers-reduced-motion`, and keep reveals under ~600ms.

For a *presentation* rather than a dashboard, do not build this by hand: the
`eksempel-html-slides` skill already produces a single self-contained deck with keyboard
navigation and a section rail. Use it, and give it the same provenance discipline.

## Step 5 — Verify (mandatory)

```bash
python3 tools/verify_dashboard.py dashboards/<slug>.html
```

This must **PASS** before you show the user anything. Then **look at the screenshot
it produces** — do not just trust the exit code. A dashboard can pass every
assertion and still have overlapping labels or an unreadable chart.

Show the screenshot to the user inline: `![dashboard](path/to/x.verify.png)`

If it fails, fix and re-run. Never hand over an unverified file.

## Step 6 — Hand over

Tell them three things:

1. **Where the file is** and that it is one file, nothing else needed.
2. **How to share it** — "ask me to publish it" (`tun-publish`), or just drop it
   in a SharePoint folder themselves.
3. **That it is a snapshot** — the numbers are frozen at build time. To refresh, ask
   for `tun-data`.

Offer, don't assume: *"Want me to put it in a SharePoint folder for you?"*

## Notes

- The template is `templates/single-file-dashboard.html` — plain HTML with hand-rolled
  SVG charts. No framework, no build step, no dependency to install. Keep it that way;
  a prerequisite is a failure on the Tier 1 path.
- Norwegian number formats (`1 234,56` and `1.234,56`) are parsed by the builder. A
  column is only converted to numeric if *every* value parses, so ID columns survive.
- Labels and chrome in the template are Norwegian. Match the user's language.
- For large data, **stay on this tier** and build a cube (above). Only escalate to
  `dashboard-bigdata` when the user needs row-level detail over a huge table — that
  path needs `dashboard-embed` first, because DuckDB-WASM cannot run from a portable
  file at all (measured; `docs/01-tenant-constraints.md`).
