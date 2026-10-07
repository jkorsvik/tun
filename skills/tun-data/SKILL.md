---
name: tun-data
description: Refresh the data in an existing standalone dashboard, or add a new data source to it. Converts Excel to a usable format, re-extracts from the source, and rebuilds the file in place so existing share links keep working. Use when dashboard numbers are stale, someone asks to update or refresh a dashboard, or wants to point it at different data.
license: AGPL-3.0-or-later
---

# Refresh or repoint a dashboard's data

**Check first whether the user even needs you.** A paired dashboard can be updated with no
tooling at all, and if that fits, say so instead of doing it for them — it makes them
self-sufficient, which is worth more than one refresh.

## The no-tooling routes (offer these first)

**A — drag in, click, drag out.** No text editing, no terminal.

1. Open the dashboard and **drag a CSV onto it** — it re-renders immediately with the new
   numbers, and the header says *"ikke lagret ennå"* so nobody mistakes it for published.
2. Click **"Lagre datafil (data.js)"** — the dashboard writes the data file for you.
3. Drop that `data.js` into the SharePoint folder next to the dashboard.

Everyone with the folder synced sees the new numbers next time they open it. Norwegian
number formats (`1 500 000,50`) are parsed correctly, and a column only becomes numeric if
every value in it parses — so an ID column survives as text.

**B — edit `data.js` in Notepad.** For a small hand-maintained table. The file can carry
raw CSV between backticks:

```js
window.DASHBOARD_CSV = `Maaned,Region,Belop
2026-01,Oslo,1500000
2026-02,Bergen,2500000`;
window.DASHBOARD_META = {generated:"2026-03-01", source:"manuelt vedlikeholdt", rows:2};
```

Paste the new CSV between the backticks, save. That's the whole update.

## When you should do it (route C)

Take over when the refresh involves real work: re-running a query, joining sources,
aggregating to a coarser grain, or converting from Excel. Then continue below.

## Step 1 — Find out what it was built from

Read the provenance block at the top of the dashboard HTML:

```bash
head -30 <dashboard.html>
```

It records the source description, extract timestamp, build timestamp, requester, and
the row count. That tells you what to re-extract and what the numbers should roughly
look like afterwards.

If the provenance block is missing, the dashboard predates the convention or was
hand-edited. Reconstruct what you can, ask the user, and **make sure the rebuild has a
proper one.**

## Step 2 — Get fresh data in the same shape

The rebuild only works if the new extract has the **same column names**. If columns
were renamed or dropped upstream, the build will fail its own checks — that is the
intended behaviour, not a bug to work around. Tell the user what changed.

**Excel (`.xlsx`)** — convert to CSV. Prefer stdlib-free options in this order:

```bash
# 1. if the file is simple, ask the user to "Save As CSV" — zero tooling, zero risk
# 2. otherwise, a converter (only if already available):
python3 -c "
import openpyxl, csv, sys
wb = openpyxl.load_workbook(sys.argv[1], data_only=True)   # data_only: values, not formulas
ws = wb[sys.argv[3]] if len(sys.argv) > 3 else wb.active
with open(sys.argv[2], 'w', newline='', encoding='utf-8') as f:
    csv.writer(f).writerows(ws.values)
" input.xlsx output.csv [SheetName]
```

⚠️ `data_only=True` matters — without it you get formula strings instead of values and
every numeric column silently becomes text. If openpyxl is not installed, do not
install a toolchain on the user's behalf for a one-off; ask them to Save As CSV.

**A query (Snowflake etc.)** — re-run it and write the result to CSV. Record the query
text in `--source` so the next refresh is reproducible.

**Sanity-check the extract before rebuilding.** Row count in the same ballpark as last
time? If it dropped by 90%, something upstream broke — say so instead of shipping a
dashboard that quietly shows a tenth of the business.

## Step 3 — Rebuild in place

Same output path, same column arguments as the original build:

```bash
python3 tools/build_dashboard.py \
  --data <fresh.csv> \
  --title "<same title>" \
  --dimension <same> --measure <same> --time <same> \
  --filters <same> \
  --source "<source description>" \
  --requested-by "<original requester>" \
  --out <same/path/dashboard.html>
```

Overwriting the same path is deliberate: the share link keeps working and SharePoint
keeps the old version in its version history.

## Step 4 — Verify, then compare

```bash
python3 tools/verify_dashboard.py <dashboard.html>
```

Then do the thing that catches real errors: **compare the new headline number to the
old one** and say it out loud.

> "Total Belop went from 648 924 441 to 701 233 908 — up 8%, and there are 40 more rows.
> That looks like a normal month."

If a number moved implausibly, investigate before publishing. This comparison is the
main defence against a broken extract sailing through every automated check.

## Step 5 — Republish

Copy over the published copy (`tun-publish`), same path. Then tell the user what
the new "as of" date is, because that is the only thing that visibly changed.

## Adding a new data source

To combine sources, join them into one flat table **before** building — the template
takes a single array of rows. Do the join in Python or SQL, keep the joined extract, and
describe both sources in `--source`.

If the two sources have different grains, aggregate to the coarser one first. Silently
fanning out rows through a join is the fastest way to produce a dashboard that
double-counts.

## Automating a recurring refresh

If a dashboard needs refreshing on a schedule, that is a small pipeline: extract →
build → verify → copy to the synced folder. Only automate it once the manual path has
run cleanly a few times, and make sure a failure is **loud** — a silently stale
dashboard is worse than an obviously broken one, because people keep trusting it.
