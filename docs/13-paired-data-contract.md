# Paired-mode data contract — what `dash.html` and `data.js` actually exchange today

**Status: as-built, not a proposal.** Documents what `dashboard-new --mode paired` and
`dashboard-data` actually produce and read, correcting the original contract proposal,
which specified a fuller contract before any of it was implemented. Where the proposal and
the real code differ,
the real code wins; this document is not a redesign, it's a correction.

The multi-block idea in the original proposal (several independently-typed data units
per dashboard) never got built and is being pursued separately. This document only covers the single-table contract that exists today.

---

## 1. The interface — actual global names, not the proposed ones

- `window.DASHBOARD_DATA` — a JSON array of row objects, **or**
- `window.DASHBOARD_CSV` — raw CSV text, deliberately hand-editable in Notepad (see
  `skills/dashboard-data/SKILL.md` route B). If present, this takes priority over
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

- **Which columns are filters** is decided once, at build time, via `dashboard-new`'s
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

Covered by `AGENTS.md` rule 1 and enforced in `skills/dashboard-new/SKILL.md` step 1
(split the data before writing, one folder per audience) — not something specific to the
paired-mode contract, applies identically to bundled mode.

---

## What this leaves open

- [ ] No validation on the initial `data.js` load path (§2) — only the drag-in-CSV path
      checks columns. A generator bug here would currently fail silently.
- [ ] No cache-buster (§7) — swapping `data.js` may not be seen immediately if the
      browser has cached the old one.
- [ ] `data.js` is not self-describing (§4) — fine for today's generic row/dimension/
      measure model, worth re-checking if a future block type needs pre-shaped data.
