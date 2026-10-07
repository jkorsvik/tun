# Paired-mode data contract — what `dash.html` and `data.js` actually exchange today

**Status: as-built, not a proposal.** Documents what `tun-new --mode paired` and
`tun-data` actually produce and read, correcting the original contract proposal,
which specified a fuller contract before any of it was implemented. Where the proposal and
the real code differ,
the real code wins; this document is not a redesign, it's a correction.

The multi-block idea in the original proposal (several independently-typed data units
per dashboard) never got built and is being pursued separately. This document only covers the single-table contract that exists today.

---

## 1. The interface — actual global names, not the proposed ones

- `window.DASHBOARD_DATA` — a JSON array of row objects, **or**
- `window.DASHBOARD_CSV` — raw CSV text, deliberately hand-editable in Notepad (see
  `skills/tun-data/SKILL.md` route B). If present, this takes priority over
  `DASHBOARD_DATA`.
- `window.DASHBOARD_META` — `{generated, source, rows}`. No other fields.
- Fixed filename `data.js`, same folder as `dash.html`, loaded via
  `<script src="./data.js"></script>` — never fetched. This isn't a style choice, it's
  the measured tenant constraint (`docs/01-tenant-constraints.md` rows 14–16: a sibling
  file can only be read as loaded code, not as fetched data, from `file://`).
- Load order: plain `<script>` tag order in the HTML — `data.js` is written before the
  reading code in the document, so it has already run by the time `DASHBOARD_DATA` is
  read. The proposal suggested a `data:ready` event as a fallback if load order ever
  couldn't be guaranteed; never needed, because it always can be.

## 2. No schema version field — the proposal's ask was only half built

`SCHEMA_VERSION` does not exist anywhere in the codebase. What does exist is narrower and
only covers one of the two paths data can enter the page:

- **Dragging a new CSV onto an open dashboard** (`loadRows()` in
  `templates/single-file-dashboard.html`) checks that the dimension and measure columns
  are present and **alerts visibly** if they're missing, naming exactly which columns and
  what was found instead. This matches the proposal's actual goal ("fail visibly instead of
  drawing a chart with the wrong numbers").
- **The initial page load** (reading `window.DASHBOARD_DATA` when `data.js` loads at
  open-time) has **no equivalent check**. A `data.js` written by a future, buggy
  generator with the wrong columns would fail silently or render an empty chart, not
  alert. This is a real, currently-open gap, not a design decision.

## 3. Freshness is read out of the data — built, matches the proposal exactly

`DASHBOARD_META.generated`, `.source` and `.rows` are read live and displayed; nothing in
`dash.html` hardcodes a date. Confirmed in `examples/02-paired-dashboard/` (swapping `data.js` changed the
displayed date without touching the shell).

## 4. Chart-ready shape — the opposite of what the proposal asked for, and that's fine

The proposal asked for `data.js` to either match Chart.js's shape directly or hand `dash.html` a
thin, fixed intermediate format, with "no domain interpretation in the shell." What's
actually built does the reverse: `data.js` carries raw rows (JSON or CSV), and
`dash.html` does the dimension/measure/filter interpretation itself, entirely at render
time. This works today because the interpretation is generic (group-by-column,
sum-a-measure) rather than domain-specific — but it does mean `data.js` is not a
self-describing contract the way the proposal envisioned. Worth revisiting only if a future block
type needs data pre-shaped in a way generic grouping can't produce.

## 5. Filters are half data-driven, half fixed at build time

- **Which columns are filters** is decided once, at build time, via `tun-new`'s
  `--filters Region,Produkt,Kanal` argument, and baked into `dash.html` as
  `META.filters`. Swapping `data.js` cannot add or remove a filter dimension.
- **Which values appear in each filter** genuinely is read live from whatever rows are
  currently loaded (`Array.from(new Set(rows.map(...))).sort()`), so a new `data.js` with
  a new region shows that region without a rebuild.

This is a narrower claim than the proposal ("filter dimensions are listed by data.js
itself") — the dimensions are fixed at build time, only their values are live.

## 6. "No data" state — built, matches the proposal

`templates/single-file-dashboard.html` shows a literal "Ingen data" state (both for an
empty chart and for a dashboard built with zero rows). No silent stale/empty chart.

## 7. No cache-buster — not implemented

`<script src="./data.js"></script>` — no `?v=<timestamp>` query parameter anywhere in
`examples/02-paired-dashboard/` or the templates. Browser caching of `data.js` after a
swap is therefore an open risk the proposal correctly anticipated but nothing has closed.

## 8. Size guidance — built, but as one shared budget, not a paired-specific one

`tools/build_dashboard.py` enforces the Tier 1 budget (warn >20 MB, fail >50 MB,
`docs/02-architecture.md`) uniformly — there is no separate, smaller recommended
ceiling for paired mode specifically, the way the proposal suggested there should be
before pointing to cube mode.

## 9. Multiple audiences, same contract, different folders — built as a rule, not paired-specific

Covered by `AGENTS.md` rule 1 and enforced in `skills/tun-new/SKILL.md` step 1
(split the data before writing, one folder per audience) — not something specific to the
paired-mode contract, applies identically to bundled mode.

## 10. Beyond one table: what the multi-block prototype chose per format

**Status: a prototype outside this repository, not part of the contract above.** Recorded
because it is the first worked answer to the multi-block question in the introduction, and
because its format choices are worth keeping whether or not the prototype survives.

One dashboard, one folder, four panels. Each panel owns its own source and its own view, so
one broken file breaks one panel, not the page:

| Format | Used for | Why that format |
|---|---|---|
| JSON | key figures with a trend, status summaries, anything shaped like "field: value" | structured single values |
| CSV | tables and time series | rows and columns that chart and sort naturally |
| NDJSON | event logs that grow a line at a time | one JSON object per line, so a single corrupt line costs that line, not the file |
| Markdown | commentary and analysis | formatted prose, headings and lists, written by a person |

**The constraint this collides with, and must not hide.** From a `file://` page, a plain
sibling file cannot be read at all ([tenant constraints](01-tenant-constraints.md) row 16).
Only a `.js` sidecar loads, because it is loaded as code (row 14). So none of these four
formats works as a **paired** sidecar as they stand. The prototype reaches them in the two
ways that do work:

- the reader drops or picks the file by hand, read with `FileReader` (row 17), or
- the reader grants the folder with `showDirectoryPicker`, which is **connected**, with every
  cost [the generic artifact model](08-generic-artifact-model.md) lists (row 19).

A paired multi-block design would have to wrap each block in its own `.js` sidecar, or
generate one sidecar that carries all four. That choice is open.

---

## 11. Refresh: what a swap does, and who does it

**Measured with a synthetic probe.** A probe built its own shell and `data.js` in a
temporary folder, then measured instead of assuming. Initial load: version 1, 114 rows.
Replace only `data.js`, page still open: still version 1, 114 rows. Reload: version 2,
140 rows. Today's shells read `data.js` once, at load, so a swap is picked up at the next
load. (Row 15 in `docs/01-tenant-constraints.md` is the same fact, measured from OneDrive.)

**A page can reload its sidecar without a reload, if it is built to.** Measured 2026-09-08
with Playwright, from `file://`, in a proof of concept that was never merged: a `<script>`
element created and appended *after* the page has loaded still loads and runs a sibling
file. The browser treats it as code being loaded, the same loophole as row 14. `fetch` to
the same file stays blocked (row 16).

```js
var s = document.createElement("script");
s.src = "./data.js?t=" + Date.now();   // the cache-buster is not optional
s.onload = function () { /* read the new globals, redraw */ };
document.body.appendChild(s);
```

A button and a 3-second timer were both tested: 4 swaps in 12.8 seconds landed on
schedule, the URL never changed, the timer stopped when switched off, and the console
stayed clean. Without the changing query string the browser may serve its cached copy and
show stale data in silence (see §7). Not used in any template or skill yet. Per surface,
only one informal session exists (2026-09-09): it worked through a Windows filesystem
shortcut and failed in the OneDrive web app. That is an open question in `ROADMAP.md`, not a
measurement.

**Four levels of who refreshes the data.** Each level removes one manual step:

| Level | Who or what refreshes | What the data owner does |
|---|---|---|
| 0 | A person drags a CSV into the open page (row 17) | Exports a CSV |
| 1 | A person runs one command | Exports, then runs the command |
| 2 | A job watches an input folder and writes `data.js` to an output folder | Saves the Excel file in the input folder. No new tool, no account, no portal |
| 3 | A job reads the source on a schedule | Nothing |

Level 2 is the usual sweet spot: the owner keeps working in Excel and never learns a new
tool. Level 3 needs read access to the source system, which is an approval question, not a
technical one.

**One writer only.** Paired mode assumes one person or one job writes `data.js`. With
several editors at once, see *More than one editor* in `docs/01-tenant-constraints.md`.

**Check the page against the builder.** When the page re-aggregates in the browser, prove
it agrees with the build script. The method is in `docs/25-working-with-real-sources.md`.

## 12. Proposal: several data blocks on one page (not built)

A second, separate prototype (§10) chose a file format per panel. This one tested the
data contract itself.

**Status: proposal, not adopted.** The contract above is one table per page. A page with
several independent blocks (a story sentence, KPI cards, a chart) needs more. A proof of
concept from 2026-09-08 tested three parts. It was never merged. Its code is on the
internal branch `issue-26-multiblock-poc` (`examples/11-multiblock-poc/`).

1. **A generic body: tidy rows.** One flat array of observations, each row naming its own
   dimensions (`{"maaned": "jan", "aar": 2025, "verdi": 100}`), the convention behind
   Vega-Lite, D3 and Observable Plot. The page decides how to group and order. The same
   output came out as with a bespoke shape. Limit: a block of pure text has no row form, so
   a real catalogue needs at least two body conventions.
2. **A self-describing envelope.** The payload names its own contract:
   `{"apiVersion": "v1", "kind": "...", "meta": {...}, "rows": [...]}`, like Kubernetes
   `apiVersion` + `kind`. Fed the wrong `kind`, the page showed a worded error instead of a
   blank page or a guess.
3. **Derived values are declared, not inferred.** "Grew" or "fell" was computed by the
   page and silently assumed a prior year existed. In a first year there is nothing to
   compare with: that is not "no growth", it is "does not apply". The producer decides and
   ships it:
   `"derived": {"yoy": {"available": false, "reason": "..."}, "mom": {"available": true, "pct": 6.5}}`.
   The page only branches on `available` and never re-derives it from missing rows. With a
   synthetic first-year payload, the sentence, both cards and the chart degraded to a
   stated reason, a dash and a single line. Nothing crashed.

What a block catalogue would have to store per block type, then: the body convention, the
envelope `kind` and version, and which derived fields are optional with what to show when
they are absent. The live reload in §11 is the fourth part of the same proof of concept.

## What this leaves open

- [ ] No validation on the initial `data.js` load path (§2) — only the drag-in-CSV path
      checks columns. A generator bug here would currently fail silently.
- [ ] No cache-buster (§7) — swapping `data.js` may not be seen immediately if the
      browser has cached the old one.
- [ ] `data.js` is not self-describing (§4) — fine for today's generic row/dimension/
      measure model, worth re-checking if a future block type needs pre-shaped data.
