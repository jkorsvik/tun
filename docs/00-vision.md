# Vision — Dashboards as Documents

**Reader:** user — you want an artefact out of your own data and do not intend to change the toolkit.

## The problem

Sharing an interactive dashboard inside Eksempel AS currently means a chain of prerequisites
before anyone can look at a chart:

- a **licence** for the author *and* every viewer (Pro or PPU, per user, per month)
- a **workspace**, which means a capacity, which means someone owns a budget line
- **publishing** — the `.pbix` on your disk is not the thing people see
- for anyone outside that chain — a contractor, a partner, a colleague in a
  department without licences, an auditor, someone reading on a plane — **no access at all**

The friction is not in building the dashboard. It is in *everything after* building
the dashboard. So people fall back to what always works: a screenshot in a
PowerPoint, or a pivot table in an emailed Excel file. Both are dead on arrival —
static, un-drillable, stale the moment they're sent.

## The reframe

> A dashboard should be **a document**, not a service.

Everyone at Eksempel AS already knows how to share a document. They know where the folder
is, who can see it, how to send a link, how it syncs to their laptop, and that it
still opens on a train with no wifi. That machinery — permissions, versioning,
audit, sensitivity labels, DLP, sync, search — already exists in SharePoint and
OneDrive and is already approved.

So: **ship the dashboard through it.**

A dashboard becomes a single self-contained `.html` file. Data, charts, styling and
interaction logic all inlined. Drop it in a SharePoint library. Anyone who can open
the folder can open the dashboard — fully interactive, filterable, drillable — with
**no licence, no workspace, no capacity, no admin request**.

SharePoint stops being a place we wish could host a web app, and becomes what it
actually is: **a permissioned CDN for documents**. See
[`01-tenant-constraints.md`](01-tenant-constraints.md) for the measured evidence that
this is the only model that works — and that it works well.

## What this replaces

Primarily **Power BI**, for the large class of reporting where Power BI is
over-engineered for the job:

- operational and KPI reporting off a periodic extract
- monthly / weekly / quarterly management reporting
- one-off analyses that need to stay explorable, not be flattened to slides
- anything currently distributed as "Excel with a pivot table" or "PNG in a deck"
- anything shared with people who do not and will not have a Power BI licence
- **anything that has to go outside Eksempel AS** — a partner, an auditor, a counterparty.
  Power BI simply cannot do this; a self-contained file can be attached to an email.
  See the external-sharing section in `01-tenant-constraints.md`, including the
  caveat that a file you have sent cannot be revoked.

Secondarily, it replaces the **screenshot-in-PowerPoint** habit, which is the real
incumbent and a much bigger share of the problem than anyone admits.

## The hard problems, and how we solve them

These are the things people assume a file cannot do. Each has a simple answer that
does not require a server, a licence, or a platform.

### Refresh — "the numbers will go stale"

**Paired mode.** The dashboard is a small shell; the data is a sibling `data.js` in the
same folder. Replace `data.js` and every copy of the dashboard shows the new numbers —
no rebuild, no republish, no server. OneDrive/SharePoint does the distribution.

Measured: a `<script src="./data.js">` loads from a `file://` page. (`fetch()` does not —
which is exactly why the data is a `.js` assigning a global rather than a `.json`.)

So refresh is: regenerate one small file, drop it in the folder. That can be a person, a
scheduled job, or a sentence to RAIWork.

### Different people seeing different data

**One data file per audience, each in a folder with its own permissions.**

The same dashboard shell, a different `data.js` beside it. Access is enforced by
SharePoint at the folder level — the thing SharePoint is actually good at, already
audited, already reviewed.

This is *better* than a row filter in one important way: you can see exactly who can
read what by looking at folder permissions, instead of reasoning about a filter
expression evaluated at query time.

> ⚠️ The rule that still stands: **never put rows in a file that its audience should not
> see.** The security boundary is the folder, so the data must be split *before* it is
> written, not filtered after. If you catch yourself wanting one file with a filter in
> it, split the file instead.

### Live-ish data

Paired mode already gives "as fresh as the last sync". For large data, the dense cube
(`docs/07-portable-cube.md`) puts 4 M source rows into a 0.81 MB file, exact, with no
engine in the page. That covers most cases.

Parquet, SQLite and DuckDB still have a place, but for most backends and use cases they
are more than the job needs. Their place is:

- **On the build side.** The job that writes `data.js` or the cube can read Parquet or
  query SQLite or DuckDB. The page never sees the engine. This is already how the cube is
  checked: against DuckDB on the raw Parquet.
- **Behind a hosted origin, for heavy cases.** Real SQL in the browser over a file too big
  to inline needs DuckDB-WASM. SharePoint does answer HTTP Range requests (`206 Partial
  Content`, measured), but the engine cannot start from a `file://` page: `fetch`, `Worker`
  and dynamic `import()` are all blocked there. So this needs a hosted page (Tier 2), and
  that needs an approval.

Reach for them when the cube cannot answer the question (row-level detail over a huge
table, ad hoc queries), not by default.

### Alerts, subscriptions, "certified datasets", paginated print

Mostly ceremony that exists because the platform needs it. Where a real need survives
contact with the question *"what decision does this support?"*, it is a small piece of
plumbing — a scheduled job that regenerates a `data.js` and sends a message — not a
reason to adopt a BI platform.

Print works: the template has a print stylesheet.

## What "good" looks like

A colleague in any department can say to RAIWork:

> *"Take this Excel file and make me a dashboard showing volume by month and by
> product, let people filter by region, and put it in the team's SharePoint folder."*

…and get back a single file that works, looks like Eksempel AS, and is shareable
immediately — without learning a BI tool, without filing a ticket, and without
knowing what a `Content-Disposition` header is.

That is the target. The [skill tree](03-skill-tree.md) is how we get there: each
skill is one step of that sentence, made repeatable and hard to get wrong.

## Choosing the format

**Text commits to a moment. Interaction commits to a stream.** A dashboard makes no claims
in prose, so new data does not make it false. A report states things about specific
numbers: when the data changes, the text becomes false and still looks just as sure.
Slides are worse, because they travel without their context, so the drift is noticed
later. So: data that keeps changing gets a dashboard. A report or a deck is for a fixed
moment, and should say which moment.

## Design principles

1. **The artefact is a file.** If a change makes the output need a server, it is
   the wrong change.
2. **Portable by default, live by exception.** Inlined data is the default because
   it always works. Live data (Tier 3) is opt-in and costs governance.
3. **Never defeat a security control.** `Content-Disposition: attachment` is an XSS
   control in a tenant's document store. Route around it; do not break it.
4. **Zero admin dependency on the happy path.** If the common case needs a tenant
   admin, we have built the wrong thing. Tier 1 needs nobody's approval.
5. **Honest about RLS.** See above. This is the one that gets someone fired.
6. **No toolchain prerequisites.** If the workflow assumes a build step, a
   `node_modules`, or an environment to activate, it has failed. One copy-pasteable
   command is the budget.
7. **Measure the tenant, don't trust the docs.** Every constraint in this repo was
   probed. Microsoft's documentation was materially incomplete on the two facts
   that mattered most (Range requests, and what actually happens to `.html`).

Worked examples of the same method, by pattern: [what was built](27-what-was-built.md).
