# The Skill Tree

The skill tree turns the architecture into something a **non-developer can drive by
talking**. Each skill is one verb in the sentence *"take this data, make a dashboard,
check it, put it somewhere people can see it."*

## Shape

```
                        ┌─────────────────┐
                        │  dashboard-help │   "what do I even ask for?"
                        │    (router)     │   → routes to the right skill
                        └────────┬────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
   ── BUILD ──              ── CHECK ──              ── SHIP ──
        │                        │                        │
┌───────▼────────┐      ┌────────▼────────┐      ┌────────▼────────┐
│ dashboard-new  │      │ dashboard-verify│      │dashboard-publish│
│ scaffold from  │─────►│ render, shoot,  │─────►│ upload to SP,   │
│ a data file    │      │ size budget     │      │ share, announce │
└───────┬────────┘      └─────────────────┘      └─────────────────┘
        │                        ▲
        │                        │
┌───────▼────────┐               │
│ dashboard-data │───────────────┘
│ add / refresh  │
│ a data source  │
└────────────────┘

   ── ESCALATE (Tier 2/3, needs approvals) ──
┌──────────────────┐  ┌───────────────────┐
│ dashboard-embed  │  │ dashboard-bigdata │
│ SPFx in-page     │  │ Parquet + DuckDB  │
└──────────────────┘  └───────────────────┘

   ── MIGRATE & MAINTAIN ──
┌──────────────────┐  ┌───────────────────┐
│ powerbi-escape     │  │ tenant-probe      │
│ port a PBI report│  │ re-verify the      │
│ (+ RLS gate)     │  │ constraints        │
└──────────────────┘  └───────────────────┘
```

## The skills

| Skill | One-liner | Who runs it | Status |
|---|---|---|---|
| **`dashboard-help`** | Router. Describes what you want in plain language, picks the skill, explains the tier and its cost. | anyone, first | ✅ built |
| **`dashboard-new`** | Scaffold a new single-file dashboard from an Excel/CSV/query. Picks charts, inlines data, applies the organisation's styling. Two modes: inline the **rows**, or inline a **dense cube** for millions of rows ([`07-portable-cube.md`](07-portable-cube.md)). | anyone | ✅ built |
| **`dashboard-data`** | Add a data source to an existing dashboard, or refresh its snapshot from source. | anyone | ✅ built |
| **`dashboard-verify`** | Open the file in a real headless browser, confirm it renders and JS runs, screenshot it, check the size budget. **Gate before publish.** | anyone (auto) | ✅ built |
| **`dashboard-publish`** | Upload to a SharePoint library or OneDrive folder, set/confirm permissions, produce a shareable link, draft the announcement. | anyone | ✅ built |
| **`powerbi-escape`** | Get a report out of Power BI. Answers the "but it needs RLS/refresh/alerts" objections instead of sending it back. | anyone | ✅ built |
| **`dashboard-embed`** | Tier 2. Build an SPFx web part to render in-page. Explains the admin approval chain up front. | with a developer | 🔶 planned — blocked on SPFx approvability |
| **`dashboard-bigdata`** | Tier 3. Convert a large dataset to Parquet, wire DuckDB-WASM over Range requests. | with a developer | 🔶 planned — needs `dashboard-embed` |
| **`tenant-probe`** | Re-run the tenant constraint probe and diff against the documented findings. | quarterly / on breakage | ✅ script built (`probe/tenant-probe.py`) |

## Design rules for these skills

These are the rules that keep the tree usable by whoever needs a dashboard, rather than
only by whoever built the tooling. They are not optional.

1. **`dashboard-verify` is a hard gate.** Nothing gets published without a real
   browser render and a screenshot. A dashboard that "should work" is worth nothing;
   the whole point of a portable artefact is that it opens on someone else's machine.
   *(Learned the hard way: a clean build log is not evidence — inspect the artefact.)*

2. **Every skill states its tier and its governance cost in its first reply.**
   "This is Tier 1 — no approvals needed, you can share it today" or
   "This is Tier 2 — it needs a SharePoint admin to approve a package first, which
   we have not yet done here." Never let someone discover the approval chain at
   the end.

3. **The who-sees-what question is in `dashboard-new`, `dashboard-help` and
   `powerbi-escape`, not buried in docs.** All three ask, early and in plain language:
   *"Does everyone see the same numbers, or should different people see different data?"*
   If different → **build one per audience**, split before writing, one folder each.
   Never refuse, and never put a filter in a shared file.

4. **No prerequisites on the Tier 1 path.** Nothing to install, no build step, no
   environment to activate. If a skill needs a tool, it installs or vendors it
   silently, or it does the work itself.

5. **Plain language in, artefact out.** Nobody should have to know what a
   `Content-Disposition` header is to get a dashboard. Explain what is specific to
   this stack when it matters; skip the general tutorial.

6. **Every skill leaves a trace.** Dashboards get a provenance comment in the HTML
   (source data, build time, who asked, which skill). A dashboard whose numbers
   nobody can trace back is a liability.

## Build order

The tree does not need to be built at once. Priority reflects what unblocks a
first real user fastest:

- **Phase 1 (unblocks a first user):** `dashboard-new` → `dashboard-verify` → `dashboard-publish`.
  With these three, Tier 1 works end to end and someone can ship a real dashboard.
- **Phase 2 (makes it stick):** `dashboard-help`, `dashboard-data`. Discovery and
  refresh — the difference between a demo and a habit.
- **Phase 3 (proves the replacement claim):** `powerbi-escape`. Needed before anyone
  will believe the Power BI framing.
- **Phase 4 (extends the ceiling):** `dashboard-embed`, `dashboard-bigdata`. Blocked
  on validating that an SPFx package gets through tenant admin review. Note the row-count ceiling was **already**
  lifted inside Tier 1 by cube mode (4 M rows in 0.81 MB, measured); what Phase 4 adds
  is in-page embedding and row-level detail over huge tables, not scale per se.
- **Continuous:** `tenant-probe`.

## Where the skills live

Skills in [`../skills/`](../skills/) are the source of truth. Install them with:

```bash
python3 setup.py
```

That links them into `~/.raiwork/skills/` (or copies them on Windows without Developer
Mode — it tells you which, and copies mean you re-run after editing a skill). RAIWork then
discovers them automatically, by name or matched from a plain-language request.
