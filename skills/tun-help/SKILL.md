---
name: tun-help
description: Introduce Tún, show its verbs, and figure out which skill or artefact shape fits a situation and what it costs in approvals and effort. Use when someone is new to Tún, asks what Tún can do or which verbs exist, wants to share data interactively without knowing where to start, asks whether this can replace a Power BI report, or asks what is possible in SharePoint, OneDrive, Confluence or Atlassian Artifacts.
---

# Which dashboard path fits?

**Tier and cost, for the first reply:** none of its own. It names the skill that fits, and
that skill's first reply states the cost before any work starts.

Route the user. Ask as few questions as possible, match the user's language (Norwegian or
English), and answer in plain words. Never make someone read the architecture doc to get
started.

## When someone is new ("what is Tún / introduce me / what verbs do I have?")

Give a short, warm introduction in their language:

1. **The idea in two sentences:** Tún turns a CSV, spreadsheet or query extract into **one
   self-contained HTML file** with interactive charts, filters, sortable tables and
   provenance. Drop it in SharePoint, OneDrive or Teams (or attach it to an email) — anyone
   who can open the folder opens it in their browser, offline too, with no Power BI licence,
   no workspace and nothing to install.
2. **The verbs you can invoke from any folder** (as `/tun-...` or in plain words):
   - **`tun-new`** — *build* a dashboard, scorecard, register, survey board, timeline, slide deck or any of the 27 shapes from a file
   - **`tun-data`** — *refresh* the numbers in an existing artefact (or show the no-tooling drag-and-drop refresh)
   - **`tun-verify`** — *prove* a file in a real browser and inspect its screenshot before sharing
   - **`tun-publish`** — *share* via SharePoint, OneDrive or Atlassian Artifacts and draft the message
   - **`tun-process`** — *map* how work flows across people or teams as a swimlane HTML file
   - **`tun-review`** — *collect & read back* row-level comments from recipients with no server
   - **`tun-host`** — *decide* between a portable file, a static web host, or a real backend
   - **`tun-powerbi-escape`** — *move* a report stuck behind licences into a portable file
   - **`tun-for-communicators`** — *translate* technical terms into plain communications language
   - **`tun-feedback`** — *log* what worked or broke locally, or prepare a GitHub issue
3. **The one rule to know up front:** the **folder** is the access control, not a browser
   filter. Everyone who can open the file can read every row inside it; when audiences differ,
   Tún splits the data first and builds one file per folder.
4. **Offer an immediate next step:** *"Point me at a CSV or Excel file, or ask me to build a
   quick demo from the built-in example data (`examples/01-hello-dashboard/salgsdata.csv`)."*

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
| "I have an Excel file and want charts people can filter" | **`tun-new`** | nothing — ship today |
| "make me a dashboard from this data" | **`tun-new`** | nothing |
| "where do I put it so the team can open it" | **`tun-publish`** | nothing |
| "put this interactive app on a static web host" | **`tun-host`** | Tier 1 file stays unchanged; host ownership, audience and approval must be confirmed; Platform cost is unverified |
| "it needs shared writes, sign-in, saved state or scheduled jobs" | **`tun-host`** | a separate backend application with security, data and run ownership; no server enters the toolkit core |
| "it should open as a link in Confluence or Jira, not as a download" | **`tun-publish`** (Atlassian Artifacts) | nothing to install; internal, non-sensitive material only, no paired mode, and a newly published file is readable by the whole organisation through its link until a person sets it private in the Artifacts UI |
| "is this one broken / can I send it" | **`tun-verify`** | nothing |
| "the numbers are old, update it" | **`tun-data`** | nothing |
| "we have a Power BI report, can you move it" | **`tun-powerbi-escape`** | nothing (unless it uses RLS) |
| "it has to show on our team site page, not as a file" | **`dashboard-embed`** | ⚠️ needs a SharePoint admin — and is **not yet proven at Eksempel AS** |
| "why did the number change / break it down for me" | **`tun-new`** (waterfall) | nothing — a bridge that adds up, printed on the page |
| "how many get through / where do the cases stop" | **`tun-new`** (funnel) | nothing |
| "where is it busy / where do the errors concentrate" | **`tun-new`** (heatmap) | nothing — one cell per pair, with the value printed in it |
| "what is this total made of / who takes the biggest share" | **`tun-new`** (composition) | nothing |
| "how long do these cases take / what is typical" | **`tun-new`** (distribution) | nothing |
| "the monthly report with targets and status" | **`tun-new`** (scorecard) | nothing, once the direction and the bands are declared |
| "do people stay / who comes back / where do they drop off" | **`tun-new`** (cohort grid) | nothing — one row per cohort, and a period that has not happened yet is hatched, not zero |
| "which unit is the odd one out / do they all behave the same" | **`tun-new`** (small multiple) | nothing — one panel per group, all on one printed scale |
| "the dataset is millions of rows, I just need the totals" | **`tun-new`** (cube mode) | nothing — 4 M rows fit in 0.81 MB |
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
- **Download, not preview, is the normal path** on SharePoint and OneDrive. Expect the
  browser to save the file rather than render it, and say so before you send the link.
  Atlassian Artifacts is the exception: it shows the file in the browser
  (`docs/29-atlassian-artifacts.md`).

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
