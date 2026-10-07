# Architecture — Three Delivery Tiers

Each tier is a complete, shippable way to deliver a dashboard. They differ in
**capability** and in **governance cost**. Start at Tier 1 always; escalate only
when a requirement forces it.

```
                          governance cost  ──────────────────────────►
   ┌──────────────────────────────────────────────────────────────────────┐
   │ TIER 1 — PORTABLE          │ TIER 2 — EMBEDDED   │ TIER 3 — LIVE     │
   │ single-file .html          │ SPFx web part       │ Parquet + DuckDB  │
   │ rows OR a dense cube       │ in a SP page        │ over Range reqs   │
   │ inlined                    │                     │ (hosted BY tier 2)│
   │ approvals: NONE            │ approvals: SP admin │ approvals: Tier 2 │
   │ data size:  rows ≤ ~50 MB  │ + app catalog       │ + data placement  │
   │   cube: millions of rows   │ offline: no         │ data: ≤ ~1 GB     │
   │   in < 1 MB                │ live data: yes      │ live data: yes    │
   │ offline:    YES            │  (same-origin)      │ row detail: yes   │
   │ live data:  no             │                     │                   │
   │ ✅ THE DEFAULT             │ for in-page KPI     │ for real analytics│
   └──────────────────────────────────────────────────────────────────────┘
```

> Tier 3 is **not** reachable from a portable file — DuckDB-WASM cannot boot against
> origin `null`. Measured; see [`01-tenant-constraints.md`](01-tenant-constraints.md).
> For aggregates over millions of rows without any approval, use the Tier 1
> [dense cube](07-portable-cube.md) instead.

---

## Tier 1 — Portable (the default)

**A single `.html` file with everything inlined, stored in SharePoint/OneDrive.**

```
  build time                          view time
  ──────────                          ─────────
  Excel/CSV/Snowflake                 SharePoint library
        │                                    │
        │ RAIWork skill                      │ user clicks / opens
        │ inlines data + charts              │ from synced folder
        ▼                                    ▼
  dashboard.html  ───── upload ─────►  dashboard.html ──► browser (file://)
  (self-contained)                                        renders, interactive
```

- **Auth model:** SharePoint file permissions. Nothing else. If you can open the
  folder, you can open the dashboard.
- **Why it works:** verified in [`01-tenant-constraints.md`](01-tenant-constraints.md)
  row 7 — a local `.html` renders fully and stays interactive.
- **Why the download is fine:** row 1. It was never going to render in-place, and it
  does not need to.
- **Ceiling:** data must be small enough to inline. Two ways to do that — see below.
- **Cannot do:** live refresh, RLS.

**This tier requires no approval from anyone and should cover most work.**

### Two shapes of Tier 1

|  | inline the **rows** | inline a **cube** |
|---|---|---|
| tool | `tools/build_dashboard.py` | `tools/build_cube_dashboard.py` |
| what ships | every source row | one cell per filter combination |
| ceiling set by | **row count** | **dimension cardinality** |
| row-level drill | yes | no |
| new questions after build | any the rows support | only the compiled-in dimensions |
| measures | anything | additive only (`sum`, `count`, and `avg` as their ratio) |

### Size budget — inlined rows

| Inlined rows | Approx. file size | Verdict |
|---|---|---|
| < 10 000 | < 2 MB | ideal |
| 10 000 – 100 000 | 2 – 20 MB | fine; prefer a cube |
| 100 000 – 500 000 | 20 – 50 MB | works, sluggish to open; use a cube |
| > 500 000 | > 50 MB | **stop** — use a cube |

### Size budget — inlined cube

Row count is irrelevant here; the cell count is the product of the dimension
cardinalities.

| Cube cells | Approx. file size | Verdict |
|---|---|---|
| < 200 000 | < 1 MB | ideal — **measured: 4 M rows in 0.81 MB** |
| 200 000 – 1 M | 1 – 5 MB | fine |
| 1 M – 2 M | 5 – 10 MB | works; check decode time on a real laptop |
| > 2 M | — | builder refuses; coarsen a dimension |

**Measured** (`examples/03-cube-dashboard`): 4 000 000 rows over 5 dimensions →
115 200 cells → 0.81 MB `.html`, 40 ms to decode, filter clicks at a median of
0.10 ms, exact against DuckDB on the raw data.

Pre-aggregating to the grain the dashboard actually shows almost always drops a
"too big" dashboard back into the ideal band. Do that before reaching for Tier 2 or 3 —
and note that **the cube is what makes Tier 1 viable for large data**, because Tier 3
cannot run from a portable file at all. Details in
[`07-portable-cube.md`](07-portable-cube.md).

---

## Tier 2 — Embedded (native, in-page)

**An SPFx web part rendering the dashboard inside a modern SharePoint page.**

Use when the dashboard must appear *in place* — on a team site homepage, in a
Teams tab, next to other content — rather than being opened as a file.

- **Auth model:** the viewer's existing SharePoint session. SPFx gives
  `SPHttpClient` / `MSGraphClientV3` with tokens handled for you.
- **Live data:** yes — same-origin `fetch()` against `/_api/...` works without MSAL
  (no app registration needed for reads; `X-RequestDigest` only for writes).
- **Governance cost:** **high and unavoidable.** Requires a built `.sppkg`, upload
  to the tenant app catalog, and a **SharePoint admin approval** — per package, and
  again for each API permission. This cannot be shipped without a developer and an admin.
- **Status:** ⚠️ **unvalidated in the measured tenant.** Whether an SPFx package gets through admin review there,
  and the lead time, is an open question and gates this tier entirely. See the open
  assumptions in the constraints doc.

> Do not promise Tier 2 to a stakeholder until someone has landed one `.sppkg` in
> the tenant's app catalog end-to-end. Until then it is a design, not a capability.

---

## Tier 3 — Live / large data

**Parquet files in SharePoint, queried in-browser by DuckDB-WASM over HTTP Range
requests.**

```
  SharePoint library                     browser
  ─────────────────                      ───────
  facts.parquet  (500 MB)  ◄──── Range: bytes=… ──── DuckDB-WASM
       │                          206 Partial            │
       └── only needed columns ────────────────────►     │ SQL
           and row-groups transferred                    ▼
                                                    charts, drilldown
```

- **Why it works:** row 6 of the constraints doc — SharePoint returns
  `206 Partial Content` with a correct `content-range`. Columnar partial reads are
  genuinely possible. **Measured:** `count(*)` over a 24 MB / 4 M-row Parquet pulls
  0.03 MB (0.1 %); a region roll-up pulls 7 %.
- **Capability:** real SQL over a dataset far too large to inline, **including
  row-level detail** — the one thing a cube cannot give you.
- **Requires a real HTTP origin, so Tier 2 must host it.** Not a preference: a
  `file://` page cannot construct a `Worker`, `fetch` the `.wasm`, or dynamic-`import`
  the module — all three fail against origin `null`. And the runtime cannot be inlined
  to route around it (33 MB `.wasm` + 755 KB worker + `apache-arrow` and three
  transitive deps). Measured; see the constraints doc.
- **Ceiling:** browser WASM memory. Comfortable to a few hundred MB of scanned data;
  degrades beyond that.

> ⚠ **Two silent traps.** Both return correct answers while transferring the whole
> file, so they cannot be caught by looking at the dashboard:
> 1. `LOAD httpfs` must run on the connection, or every query pulls 100 % of the file.
> 2. `registerFileURL(..., HTTP, directIO)` never range-reads, with `directIO` either
>    `true` or `false`. Only `read_parquet('https://…')` does.
>
> Assert on the network — count `206` responses and sum the bytes.

**Tier 3 is a capability multiplier on Tier 2, not a standalone tier.** It inherits
Tier 2's approval requirements. If all you need is aggregates, the
[portable cube](07-portable-cube.md) gets you there at Tier 1 with no approval.

---

## Updating the data — three routes, none needs a build step

| Route | Who | How |
|---|---|---|
| **drag in → click → drag out** | anyone | drag a CSV onto the dashboard, click "Lagre datafil", drop the `data.js` in the folder |
| **edit `data.js`** | anyone with Notepad | the file can hold raw CSV between backticks (`window.DASHBOARD_CSV`); paste and save |
| **regenerate** | RAIWork / a job | `tun-data` — for queries, joins, aggregation, Excel conversion |

All three end the same way: a `data.js` sitting next to the dashboard. SharePoint/OneDrive
distributes it. No server, no rebuild of the dashboard, no republish.

Why the data file is `.js` and not `.csv`: measured — from a `file://` page a
`<script src>` loads, but `fetch()`, `XMLHttpRequest`, `<iframe>` and `<object>` are all
blocked from reading a sibling file. So the payload has to be JavaScript. It can still be
*written* as plain CSV inside a template literal, which is what makes route B possible.

## Choosing a mode

```
Will it go OUTSIDE the organisation, or must it survive with no folder at all?
   └─ YES → BUNDLED. One file, data inlined. Attach it to an email.
   └─ NO  ↓

Do the numbers need to keep updating?
   └─ YES → PAIRED. dash.html + data.js in a synced folder.
            Replace data.js to update everyone. No rebuild.
   └─ NO  → BUNDLED is simpler. Use it.

Do different audiences need different data?
   └─ One data.js per audience, each in its own permissioned folder.
     Same shell. The folder is the security boundary.

Is the data too big to ship as rows (hundreds of thousands and up)?
   └─ Are aggregates enough — no row-level drill needed?
        └─ YES → CUBE. build_cube_dashboard.py. One file, still Tier 1,
                 still no approval. 4 M rows measured at 0.81 MB.
        └─ NO  → Parquet + DuckDB-WASM over Range requests. Needs a real
                 origin, so it rides on Tier 2 and its admin approval.
```

Note the cube is always **BUNDLED**: it is self-contained by construction, so the
PAIRED `data.js` update route does not apply. Changing the numbers means re-running the
builder and replacing the file.

## Toolchain

For Tier 1 the recommendation is a **plain single-file HTML template** with an
embedded chart library, generated by the RAIWork skills — not a framework. Reasons:

- zero build step, so it can be regenerated by asking, with nothing installed
- zero CDN dependency, so it works offline and in a locked-down browser
- no `node_modules`, so nothing to install, scan, or patch

Heavier toolchains (Quarto for authored analytical documents; Marimo/WASM for
notebook-style exploration) are worth adopting **later, per use case**, and both
can emit a self-contained HTML file that fits Tier 1. They are deliberately out of
scope for v1 so the first version has no prerequisites.

> Decision to record as an ADR once validated: *plain templated HTML for v1;
> revisit Quarto once there is a real authored-report use case.*
