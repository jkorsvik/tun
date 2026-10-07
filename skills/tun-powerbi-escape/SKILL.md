---
name: tun-powerbi-escape
description: Get a report out of Power BI and turn it into a standalone interactive dashboard that anyone can open — no licence, no workspace, no capacity. Use when someone wants to move, replace, retire or escape a Power BI report, is frustrated with licence or sharing friction, or asks whether a report could just be a file.
license: AGPL-3.0-or-later
---

# Get a report out of Power BI

The job is to **move it out**, not to assess whether it's allowed to leave. Assume it can.
Most of what looks like a hard dependency turns out to be ceremony the platform required,
not something the report's readers actually need.

Start by finding out what people **actually use**, because it's always less than the
report contains.

## Step 1 — Find the real report inside the report

Don't try to parse the `.pbix` — treat it as opaque. Ask instead:

- *"Which two or three numbers do people actually look at?"*
- *"Which filters get used?"*
- *"What decision does this support?"*
- *"Which pages does anyone open?"*

Then say what you'll build, and **name what you're dropping**:

> "I'll rebuild the main view: total volume as a KPI, volume by product as bars, monthly
> trend as a line, filters for region and channel. The four detail pages nobody mentioned
> I'm leaving out — tell me if any of them matter."

A port should come out **smaller** than the original. Power BI reports accumulate pages
nobody opens; this is a good moment to shed them.

## Step 2 — Handle the "but it needs…" objections

These come up every time. None of them require going back:

| "It needs…" | What you actually do |
|---|---|
| **different rows per person** | one data file per audience, each in its own permissioned folder. Split the data *before* writing it. SharePoint enforces access — visibly, auditably. |
| **to stay up to date** | `--mode paired`. Replace `data.js` and everyone sees new numbers. No rebuild, no republish. |
| **scheduled refresh** | a job that regenerates one small `data.js` and drops it in the folder. That's a few lines, not a platform. |
| **live/DirectQuery** | ask what decision needs sub-daily data. Usually the answer is "none". If it genuinely does, paired mode + a frequent job gets close; Parquet + DuckDB-WASM handles big data. |
| **alerts** | a job that checks the number and sends a message. Unrelated to how the dashboard is drawn. |
| **certified dataset / lineage** | provenance is written into every dashboard: source, extract time, who asked. Traceable by reading the file. |
| **complex DAX** | reimplement in the extract SQL or in Python. This is the real work — scope it honestly, it's where the hours go. |
| **paginated print** | the template has a print stylesheet. Try it before assuming. |

If someone insists on a genuine platform feature after that conversation, fine — say so
plainly and move on to the next report. Don't argue, and don't pretend the file does
something it doesn't.

## Step 3 — Get the data out

You need the underlying data, not the visuals:

- **best:** go to the original source — the warehouse table or query the report is built
  on. Keeps the dashboard reproducible and refreshable.
- **acceptable:** export the underlying data from a visual. There is a row cap, so
  **check the export isn't truncated** — a silently cut-off export that looks complete is
  a real risk.
- **last resort:** transcribe from screenshots. One-off only, and label it as such in the
  provenance.

Then **reconcile**: pick three numbers from the original and confirm your extract
reproduces them exactly. Write the comparison down. This is the only proof the port is
faithful, and it's the first thing anyone will test.

## Step 4 — Build, verify, publish

Hand off to `tun-new` (default to `--mode paired`), then `tun-verify`, then
`tun-publish`.

## Step 5 — Show the difference

Put them side by side: the original screenshot, the new dashboard, the reconciled numbers.

> "Same three headline numbers. This one is a file — opens for anyone who can open the
> folder, no licence, works offline, and I can send it to someone outside the organisation. Updating is
> dropping in a new data file."

Then let them retire the original when they're ready. **Don't delete anything.** Run both
in parallel until they're satisfied; it's their call, and a forced migration breeds
resistance.

## Notes

- **Track what moved**, and what the port cost in effort. That list is the argument for
  the next one.
- Licence saving is a consequence, not the pitch. Lead with *"shareable to anyone,
  instantly, including outside the organisation"* — that's what people actually feel.
- If the data is large, don't pre-aggregate it into uselessness. Aggregate to the grain
  the dashboard shows, and keep the option of Parquet + DuckDB-WASM for real exploration.
