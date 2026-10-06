---
name: dashboard-new
description: Build a new standalone interactive dashboard from a data file (Excel, CSV, JSON, or a query result). Produces a single self-contained HTML file that can be shared through SharePoint or OneDrive with no Power BI licence, no workspace, and no admin approval. Use when someone wants a dashboard, a report, charts from a spreadsheet, or to share data interactively.
license: AGPL-3.0-or-later
---

# Build a standalone dashboard

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

- `.xlsx` / `.xlsm` → convert to CSV first (see `dashboard-data`), then read
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

## Step 3b — Pick a mode

Two options. Ask which fits, in one sentence:

> "Do the numbers need to keep updating, or is this a fixed picture?"

| Mode | What you get | Use when |
|---|---|---|
| **`paired`** *(default for recurring)* | `dash.html` + `data.js` side by side. Replace `data.js` and **everyone sees new numbers** — no rebuild, no republish. | anything recurring; anything where "is this current?" will be asked |
| **`bundled`** | one self-contained file, data inside | it must leave the organisation (email attachment), or must survive with no folder around it |

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
  --requested-by "<who asked>" \
  --mode paired \
  --out dashboards/<slug>/dash.html
```

In paired mode `data.js` is written next to `--out`, so give each dashboard its own
folder. **The two files must stay together.**

The `--source` and `--requested-by` values become a provenance block in the file.
**Always fill them in properly.** A dashboard whose numbers cannot be traced back to
a source is a liability, and someone will ask in three months.

Never rebuild a committed example or a shipped dashboard without those two flags. A
rebuild that omits them silently replaces a descriptive source and a real requester with
a filename and whoever happens to be logged in, with no warning — the provenance block
degrades and the file still looks fine.

If the build fails on size (>50 MB), do not fight it — **pre-aggregate**. Group the
data to the grain the dashboard actually displays and rebuild. That almost always
fixes it, and it makes the dashboard faster too.

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

For a *presentation* rather than a dashboard, see the synthetic sample deck in
`examples/18-portable-slide-deck/` and `templates/portable-slide-deck.html`,
or a dedicated slide-deck skill if your environment has one. Give it the same provenance
discipline.

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
2. **How to share it** — "ask me to publish it" (`dashboard-publish`), or just drop it
   in a SharePoint folder themselves.
3. **That it is a snapshot** — the numbers are frozen at build time. To refresh, ask
   for `dashboard-data`.

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
