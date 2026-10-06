---
name: dashboard-help
description: Figure out which dashboard skill fits a situation, and what it will cost in approvals and effort. Use when someone wants to share data interactively but does not know where to start, asks whether this can replace a Power BI report, or asks what is possible with dashboards in SharePoint or OneDrive.
license: AGPL-3.0-or-later
---

# Which dashboard path fits?

Route the user. Ask as few questions as possible and answer in plain language. Never
make someone read the architecture doc to get started.

## The one question that comes first

> **"Does everyone who opens this see the same numbers, or should different people see
> different data?"**

- **same for everyone** → straightforward, continue.
- **different per audience** → **one dashboard per audience.** Same shell, a different
  data file each, each in its own folder so SharePoint decides who gets which. Not a
  blocker — just say how many groups.

  The one rule: split the data *before* writing it. Never put rows in a file whose
  audience shouldn't see them; a filter in the browser hides nothing.

## Then route on how it needs to be seen

| They say something like… | Route to | Cost |
|---|---|---|
| "I have an Excel file and want charts people can filter" | **`dashboard-new`** | nothing — ship today |
| "make me a dashboard from this data" | **`dashboard-new`** | nothing |
| "where do I put it so the team can open it" | **`dashboard-publish`** | nothing |
| "is this one broken / can I send it" | **`dashboard-verify`** | nothing |
| "the numbers are old, update it" | **`dashboard-data`** | nothing |
| "we have a Power BI report, can you move it" | **`powerbi-escape`** | nothing (unless it uses RLS) |
| "it has to show on our team site page, not as a file" | **`dashboard-embed`** | ⚠️ needs a SharePoint admin — and is **not yet proven at the organisation** |
| "the dataset is millions of rows, I just need the totals" | **`dashboard-new`** (cube mode) | nothing — 4 M rows fit in 0.81 MB |
| "millions of rows **and** I must see individual records" | **`dashboard-bigdata`** | ⚠️ needs `dashboard-embed` first |

## What to say about the default path

Lead with the payoff, not the mechanism:

> "I can turn that into a single interactive file — filters, charts, sortable table.
> You drop it in a SharePoint folder and anyone who can open the folder can open the
> dashboard. No Power BI licence, no workspace, no approvals. It works offline too.
>
> The trade-off: the numbers are a snapshot from when we build it. Refreshing means
> rebuilding, which I can do any time you ask."

## Set the download expectation early

This surprises everyone, so get ahead of it:

> "One quirk: SharePoint always *downloads* HTML files rather than showing them in the
> page — that's a security rule we can't change and shouldn't try to. So clicking the
> link downloads the file and it opens in the browser. It's also why it keeps working
> offline afterwards."

## Say the limits before they hit them

State these plainly when the file is proposed, not after someone has tried and been
surprised. Each one is cheap to hear up front and expensive to discover late.

- **The numbers are as of the day it was built.** If a figure will be stale by the
  meeting, put the date next to it, in the file.
- **Not co-editable.** A colleague cannot work in it with you the way they can in a
  spreadsheet or a PowerPoint. One person rebuilds it.
- **No live data and no calls out.** Offline and self-contained means exactly that;
  there is no API, no refresh button that can work.
- **Everything in the file is readable by anyone who can open it.** If different people
  must see different rows, this is the wrong tool — that is a Power BI job.
- **Download, not preview, is the normal path.** Expect the browser to save the file
  rather than render it, and say so before you send the link.

## If they are comparing against Power BI

Be even-handed. Power BI is the right tool for a real set of things:

**This project wins on:** sharing to anyone (no licence), zero setup, offline, portable,
version-controlled like a document, minutes not weeks.

**Power BI wins on:** row-level security, scheduled refresh, live connections to a
warehouse, alerts and subscriptions, certified datasets and lineage, paginated print
reports.

The honest framing: *this is not a Power BI replacement for everything — it's for the
large amount of reporting that only ever needed to be a shareable, explorable snapshot,
and is currently either stuck behind licences or flattened into a screenshot.*

## Notes

- Full reasoning: `docs/00-vision.md`. Tiers and their costs: `docs/02-architecture.md`.
  Measured tenant behaviour: `docs/01-tenant-constraints.md`.
- If asked "why can't we just host the HTML in SharePoint" — the answer is measured, not
  theoretical: every file comes back `Content-Disposition: attachment`, and `.aspx` gets
  its MIME type downgraded. Both were tested. Constraints doc, rows 1 and 2.
