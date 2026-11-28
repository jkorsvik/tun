---
name: tun-new
description: Build a new standalone interactive dashboard from a data file (Excel, CSV, JSON, or a query result). Produces a single self-contained HTML file that can be shared through SharePoint or OneDrive with no Power BI licence, no workspace, and no admin approval. Use when someone wants a dashboard, a report, charts from a spreadsheet, or to share data interactively.
---

# Build a standalone dashboard

**Tier and cost, for the first reply:** Tier 1, no approvals and no licence; the file goes
where the reader's existing folder permissions already reach.

You are producing a **Tier 1 portable dashboard**: one self-contained `.html` file,
data inlined, no server, no CDN. See `docs/02-architecture.md`.

**Toolkit path:** Commands below (`python3 tools/...`) are relative to the Tún checkout.
When working in another folder, read `repo:` from `.installed-by-tun` next to this
`SKILL.md` (or `TUN_HOME`), run `<repo>/tools/...`, and write outputs in the user's
current folder — never inside the Tún repository.

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

Every new artefact uses the Tún square favicon and a quiet footer link to
`https://tun.community`. The builders add both without a flag. Keep them unless
the user asks for an override. `--favicon <local-file|data-uri|none>` replaces or
disables the icon; `--no-tun-hint` removes the visible link, not the Origin Notice.

For custom HTML, use `tools/tun_brand.py`: put `{{TUN_FAVICON}}` in `<head>`,
`{{TUN_CREDIT_CSS}}` inside the style block, and `{{TUN_CREDIT}}` in the footer's
metadata line. Run `tun_brand.apply(template)` before inserting user content.
For slides, keep the credit visible beside the slide controls. Inline the icon;
no external icon request, tracking, script, or overlay is needed.

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

### When a specialised shape answers the question better

Before defaulting to `build_dashboard.py`, check whether the user's question matches a
dedicated shape below. **Read [`shapes.md`](shapes.md) in this folder** before running any
of these builders — it holds the exact flags, refusals and caveats to state up front
(full chooser: [`../../docs/33-artefact-shapes.md`](../../docs/33-artefact-shapes.md)).

| When the question is… | Shape | Builder |
|---|---|---|
| "Give me the rows / a searchable list" | Register | `tools/build_register.py` |
| "What moved between two extracts?" | Comparison | `tools/build_comparison.py` |
| "Why did the total change?" (bridge) | Waterfall | `tools/build_waterfall.py` |
| "How many get through each stage?" | Funnel | `tools/build_funnel.py` |
| "Where do cases or errors concentrate?" | Heatmap | `tools/build_heatmap.py` |
| "What is this total made of over time?" | Composition | `tools/build_composition.py` |
| "How long do cases take / what is typical?" | Distribution | `tools/build_distribution.py` |
| "Compare spread & tails across many units" | Box plot | `tools/build_boxplot.py` |
| "The monthly report with targets & status" | Scorecard | `tools/build_scorecard.py` |
| "Which of these 20 units is off target?" | Bullet | `tools/build_bullet.py` |
| "Which few categories explain 80 %?" | Pareto | `tools/build_pareto.py` |
| "Do people come back / stay?" | Cohort grid | `tools/build_cohort.py` |
| "Who moved up or down in rank?" | Rank change | `tools/build_rank_change.py` |
| "Which unit behaves differently over time?" | Small multiples | `tools/build_smallmultiples.py` |
| "Do these two measures move together?" | Scatter | `tools/build_scatter.py` |
| "Where did the volume flow across stages?" | Sankey | `tools/build_sankey.py` |
| "How does this sequence fit in 3D space?" | Task space | `tools/build_task_space.py` |
| "When in the week or year does it peak?" | Calendar | `tools/build_calendar.py` |
| "Was the plan kept vs actual dates?" | Gantt | `tools/build_gantt.py` |
| "When does this happen, and what overlaps?" | Timeline | `tools/build_timeline.py` |
| "What did respondents answer?" | Survey board | `tools/build_survey_dashboard.py` |
| "One A4 sheet to hand over on paper / PDF" | One-pager | `tools/build_onepager.py` |
| "A front page for a folder of artefacts" | Folder index | `tools/build_index.py` |
| "Present in a meeting, not explore" | Slide deck | `tools/build_slide_deck.py` |
| "Millions of rows, aggregates only" | Cube | `tools/build_cube_dashboard.py` |
| "Show every built example in one page" | Explorer | `tools/build_showcase.py` |
| "Who does what in which order?" | Swimlane process | see `tun-process` (`tools/build_process_diagram.py`) |

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

For a *presentation* rather than a dashboard, use `tools/build_slide_deck.py` (in
[`shapes.md`](shapes.md)) and give it the same provenance discipline.

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
- For large data, **stay on this tier** and build a cube ([`shapes.md`](shapes.md)). Only escalate to
  `dashboard-bigdata` when the user needs row-level detail over a huge table — that
  path needs `dashboard-embed` first, because DuckDB-WASM cannot run from a portable
  file at all (measured; `docs/01-tenant-constraints.md`).
