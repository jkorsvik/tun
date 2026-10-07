# A Generic Artifact Model

> **Status: ADOPTED (generic split).** The split exists so that these principles can be
> extracted for reuse by tools outside this repo (see "External consumers" below). This
> document does not edit, rename or supersede anything in `00-vision.md`,
> `02-architecture.md` or `03-skill-tree.md`. It sits **beside** them, arguing for a layer
> underneath the dashboard specialisation those documents already cover well.
>
> What "adopted" resolves, concretely: the Layer 0/Layer 1 split below is the accepted
> model; `tools/verify_standalone_core.py` is no longer a proposal-only script (it is
> wired into `verify_dashboard.py`, see "Proposal: split the verify gate the same way"
> below — no longer just a proposal either); and the "where does this layer live" open
> thread is resolved as **this repo, consumed by others via vendoring** — see below. What
> is *not* resolved by this adoption: `artifact-audit`/`dashboard-audit` as named,
> separate skills are still unbuilt (the split exists inside the scripts, not yet as its
> own skill surface).

## Why generalise past dashboards at all

Everything measured in `01-tenant-constraints.md` is dashboard-agnostic — it is about
what a `file://` page can do, not about what a dashboard is. But today it is spent on
one specialisation. Outside this repo, several other standalone-HTML tools already
exist — a management-reporting overview, a process-diagram visualiser, a markdown-backed
executive summary, a change-queue pattern — and each one **re-derives the same tenant
physics independently**: brand tokens hand-copied again, a provenance block reinvented
in a slightly different shape, the "sidecar must be `.js`" trick rediscovered by trial
and error rather than read from this document.

That is the actual cost of keeping this repo dashboard-scoped: the highest-value asset
here — the measured tenant physics — only reaches one of several use cases that need it.
A thin, generic layer that any standalone-HTML artefact can stand on (reporting,
documentation, simulation tooling, process diagrams, and whatever comes next) lets the
next specialisation start from "here is what already works," not from re-measuring
`Content-Disposition` headers for the fourth time.

This is not a rewrite of what exists. Dashboards stay exactly what they are — the
**first, and so far only, proven specialisation** of the model below.

## Layer 0 stays exactly as measured

`01-tenant-constraints.md` needs no change to generalise — it already is generic. Worth
naming explicitly, because it clarifies where any future doc should look first:

- **Tenant policy** (SharePoint's choices, admin-gated, rows 1–5, 11–13): `.html` always
  downloads, anonymous sharing is blocked, framing is blocked. Could in principle change
  under a different tenant configuration.
- **Browser origin-`null` rule** (universal, not an organisation-specific choice, rows 8, 16, and the
  DuckDB-WASM section): once a file is opened locally, no browser — in any tenant —
  allows it to `fetch`/`XHR`/construct a `Worker` from a file path. This is the harder
  constraint, because no admin can lift it.

Everything below is about the second point: given that wall, what shapes can a
standalone artefact still take, regardless of what it contains?

## The proposed split

Today's vocabulary — `bundled` / `paired` / `cube` — mixes two different questions:
**how is the file delivered** (does it depend on a sibling file or not), and **how is
its payload shaped** (rows vs. a dense pre-aggregated table). Those are independent
axes, and conflating them is exactly what makes the vocabulary awkward to reuse for
something that has no rows at all — a documentation page, a simulation tool.

Splitting them:

```
Does the artefact depend on anything else present at open-time?

├── NO  → STANDALONE — one file, no dependency, ever.
│         Payload-shaping is an internal technique choice, not a category:
│           • content inlined directly (today's "bundled")
│           • a dense precomputed table inlined instead of raw rows,
│             when raw rows would be too large ("cube")
│         Both rebuild fully to change anything. Neither needs a sidecar.
│
└── YES → two mechanisms exist, not one — the browser gives two different
          doors past origin `null`, at different cost:
      │
      ├── DECLARATIVE SIDECAR, read-only ("linked")
      │     <script src="./sidecar.js"> — the ONLY way a file:// page can
      │     read a sibling file at all, of ANY payload shape, because it is
      │     loaded as code, not fetched as data (constraints doc rows 14–16).
      │     No permission prompt, any browser. Re-read fresh on every open,
      │     so the shell never needs to change — only the sidecar does.
      │     → today's "paired" / data.js.
      │
      └── LIVE FOLDER ACCESS, read+write ("connected")
            showDirectoryPicker (File System Access API) — a real permission
            grant, Chromium-only, but the ONLY mechanism where the page
            itself writes back into the shared folder while it is open.
            Materially different cost from "linked": a prompt, a narrower
            browser matrix, and (per constraints doc row 19) a
            mechanism that cannot be regression-tested
            headlessly at all.
            → the local change-queue pattern.
```

### Why this beats extending `bundled`/`paired`/`cube` directly

- **`cube` is not a peer of `bundled`/`paired` even today.** `02-architecture.md` says
  so directly: *"the cube is always BUNDLED... changing the numbers means re-running
  the builder."* Keeping it as a third co-equal mode overstates how independent it is.
  Demoting it to a technique **inside** standalone doesn't remove anything — it just
  stops implying a dashboard has three delivery choices when it has two, one of which
  has two techniques.
- **The change-queue pattern is not "paired with extra steps."** It uses a materially
  different browser API, with a different permission cost and a different (and much
  weaker) testability guarantee. Filing it under "paired" hides that cost from whoever
  is deciding whether to use it.
- **Vocabulary that survives content with no rows.** A documentation page or a
  simulation tool has no "dimension" or "measure," but it absolutely still needs to
  answer: does this depend on a sibling file, and if so, can it write back? That
  question is what the split above answers, without borrowing data words to do it.

### The prerequisite "connected" silently assumes

The local change-queue pattern folds cleanly into "connected" above, but it has one gap
that was never actually closed:
the pattern's failsafe (suggestions stay visible in the live view even if consolidation
into the source never runs) only produces a correct outcome if the shared folder's
membership was already scoped correctly **before** anyone could write into it. The first
non-negotiable rule in `AGENTS.md` — never write a row into a file whose audience shouldn't see it,
enforced by folder membership, not a filter — is a precondition for "connected" being
safe to use, not a separate, parallel concern next to it.

This was true the moment `showDirectoryPicker` was first considered and is not a new
constraint. It was just never written down as an explicit dependency, so a future reader
implementing this pattern could otherwise reasonably assume the queue mechanism itself
was the security boundary. It is not — the folder is, exactly as `AGENTS.md` rule 1
already states for `data.js` splitting. **Before wiring "connected" into any real skill,
confirm the target folder's membership is already correct for its full audience** — the
pattern adds no access control of its own.

### Mapping dashboards onto this model — nothing is lost

| Today's term | Under this model |
|---|---|
| `bundled`, rows inlined | STANDALONE, rows technique |
| `bundled`, cube inlined | STANDALONE, precomputed technique |
| `paired` | NOT STANDALONE → linked |
| local change-queue | NOT STANDALONE → connected |

Dashboards remain the reference specialisation. Nothing here asks `tun-new`,
`tun-data` or their vocabulary to change — the mapping above is meant as evidence
the split is sound, not as a migration to schedule.

### The names people use

The tree above uses `linked` for the read-only sidecar. The people explaining this outside
the repository settled on **paired** instead, in English and Norwegian alike, and it is the
word the skills and examples already use. Treat `linked` as this document's internal label
and **paired** as the name to put in front of a reader.

The one-line versions below were written for colleagues with no engineering background.
They have held up in presentations, so reuse them rather than paraphrase:

| Pattern | Norwegian | In one line | The cost, said plainly |
|---|---|---|---|
| **standalone** | selvstendig | One file. No dependency, ever. | To change anything, rebuild the whole file. |
| **paired** | parret | A shell, plus a sister file beside it. | The sister file must travel with the shell when it moves. |
| **connected** | koblet | The page gets read and write access to the folder while it is open. | A consent prompt every time, narrow browser support, hard to test. Never the default. |

The default rule follows from the costs: **standalone unless the data must change without a
rebuild, paired unless the page must write back, connected only when it must.**

### Outside the tree: the hosted route

One route does not fit the tree because it is not a file: a small web app on a real
`https://` origin that reads the reader's files through Microsoft Graph. It removes the
`file://` ceilings, and it costs an app registration, a host and an owner.
[The hosted route](23-hosted-route-it-brief.md) writes up what it needs and the questions
only IT can answer. Do not call it "connected": that word is taken, and the two differ on
every axis that matters.

## Proposal: split the verify gate the same way

`tools/verify_dashboard.py` mixes exactly this same two questions in one script: 4 of
its 7 checks are generic file-portability checks (self-contained, size budget, renders
without a console error, screenshot), and 3 are dashboard-template-specific DOM
assertions (`.kpi`, `.bar`/`.dot`, `#tbl tbody tr`, `.chip`).

Proof, not just a claim — run against `examples/04-generic-standalone-demo/standalone_html_demo1.html`
(a file with no dashboard vocabulary at all, see below):

```
tools/verify_standalone_core.py  →  PASS  (self-contained, size, console, screenshot)
tools/verify_dashboard.py        →  FAIL  (0 KPI cards, 0 chart marks, 0 table rows)
```

The second failure is **correct behaviour for a dashboard-shaped check run against a
non-dashboard file** — it is not a bug in `verify_dashboard.py`. It is exactly the
entanglement this proposal names: there is currently no way to ask "is this standalone
artefact safe to send?" without also asking "and is it a dashboard?"

`tools/verify_standalone_core.py` in this repo is the 4-check extraction, proving the
split is mechanically possible without touching `verify_dashboard.py`. If this proposal
is adopted, the natural shape is `tun-verify` calling the generic core plus its
own 3 checks, rather than the two living as separate, drifting copies.

## Proof of concept: a standalone artefact with zero dashboard vocabulary

`examples/04-generic-standalone-demo/` — generated by `build_standalone_demo.py`
(never hand-written), no `data.js`, no rows, no dimension or
measure. It exists solely to prove the STANDALONE leg renders, is brand-styled, carries a
provenance block, and uses topbar navigation between sections via JS toggle — all four
of which are today described only in dashboard terms in `docs/00-vision.md`, despite being visibly content-agnostic once built without data.

## Proposal: a generic `artifact-audit`, dashboard-audit as its consumer

Originally proposed narrower, as `dashboard-audit` — checking a dashboard `.html`
against the design principles in `docs/00-vision.md`. Revised per the same generalisation:

- **`artifact-audit`** (generic): checks the layer-1-level principles regardless of
  specialisation — single-file or declared-sidecar-only, brand tokens present, provenance
  block present, topbar nav present, no CDN reference, generated-not-handwritten marker.
- **`dashboard-audit`** (specialisation-specific, thin): calls `artifact-audit`, then
  adds dashboard-only checks — dimension/measure/filter vocabulary used consistently,
  mode (`bundled`/`paired`/`cube`) declared and matching what's on disk.

Not built yet. This is the proposal only — same reasoning as the verify-gate split
above: one generic layer, specialisations add their own on top rather than duplicating.

## External consumers — this repo is not the only home for these principles

Several standalone-HTML tools exist, or will exist, outside this repo — the
process-diagram visualiser is the first concrete one.
Most of them will **never become a full member of the OneDrive dashboard family**: they
are not built by `tun-new`, are not distributed via `tun-publish`, and their
audience/access model may not route through a SharePoint folder at all. That is fine and
expected — it does not mean they get a free pass on the principles.

The split this document argues for is exactly what makes that workable: Layer 0/1 (the
measured tenant physics, the portability rules, the provenance requirement) is generic
and travels; the dashboard-specific vocabulary (dimension/measure/filter,
`bundled`/`paired`/`cube`) does not, and an external tool has no reason to adopt it.

**Decision on "where does this layer live" (resolves the open question below):** it stays
in this repo, as the authoritative source. External repos do not get a submodule, a
package registry entry, or write access. With no CI runner available (see
`docs/06-way-of-working.md`), automated publishing would need a manual step regardless. Instead they **vendor**: copy
the specific generic-layer files, verbatim, into their own repo under a clearly marked
`vendor/tun/` folder, with a `VERSION.txt` naming the source commit
and date. An external consumer already uses this convention to vendor its own engine, so
this reuses a proven pattern rather than inventing a second one.

Drift between the vendored copy and this repo is an accepted, named cost, not a bug to
eliminate — the same trade this repo already makes for `skills/dev/` (see
`skills/README.md`, "Vendored, and what that costs"). A submodule or live dependency would
remove the drift but requires shared-git fluency this is deliberately not assuming any
consumer has.

**What exactly is safe to vendor today** is tracked in `docs/14-generic-layer-manifest.md`
— that file, not this one, is the thing an external repo's maintainer should read before
copying anything, and the thing to re-check when re-syncing.

**What this does not do:** it does not make this repo responsible for external repos'
correctness, does not add a test here that runs against another repo's checkout, and does
not mean every future standalone-HTML tool must vendor everything in the manifest — a
tool with no rows and no branding chrome may only need the provenance template, for
example. Vendor what applies; the manifest documents what exists, not what is mandatory.

## Explicitly left out of this document

- **Inline `Worker` from a `Blob` URL** (constraints doc row 20).
  It's a real, useful capability — client-side computation without a server, relevant
  to a future simulation-tooling specialisation — but it isn't a delivery-shape
  question like the three above, and folding it in here before there's a real
  consumer would be speculative. Tracked as an open thread, not a layer.

## What this does not do

- Does not rename, move, or edit `00-vision.md`, `02-architecture.md`,
  `03-skill-tree.md`.
- Does not change any existing dashboard skill's behaviour or output.
- Does not give any external repo write access, a submodule, or a package registry
  entry — see "External consumers" above for what it gets instead (vendoring).

## Open threads this proposal creates or inherits

- [x] Whether this doc's split is adopted at all: **adopted**.
- [x] Where the layer lives — **resolved: stays in this repo; external repos vendor**,
      see "External consumers" above and `docs/14-generic-layer-manifest.md`.
- [x] `tools/verify_standalone_core.py` — **wired into `tools/verify_dashboard.py`**,
      which now imports its checks instead of duplicating them; also extended with the
      provenance and unsubstituted-placeholder checks (previously miscounted as
      dashboard-specific — they are not, and an external consumer uses the same
      `{{PLACEHOLDER}}` convention, so this closes a real gap for the first external
      consumer).
- [ ] If adopted: renumber/relabel nothing yet, but decide whether `02-architecture.md`
      should eventually reflect "cube is a technique" rather than a third mode.
- [ ] `artifact-audit` / `dashboard-audit` as **named, separate skills** — still not
      built. The check-level split is done (previous bullet); a dedicated skill surface
      is a further step, not required for external vendoring to work.
- [ ] Constraints doc row 19 (File System Access, end-to-end) and the enterprise
      browser-policy question — both already logged in `01-tenant-constraints.md`
      under "Assumptions still to test," need a human in a headed browser, not a script.
- [ ] Inline Worker (row 20) — deliberately not modelled here; revisit once a
      compute-heavy specialisation (e.g. simulation tooling) actually needs it.
- [ ] **Open question, not decided:**
      `check_provenance()` in `tools/verify_standalone_core.py` only checks for the three
      literal strings "PROVENANCE", "Source data" and "Built" — it does not check whether
      any real traceability content is actually present. A benchmark of an external,
      unrelated file found one with a richer traceability pattern (source file, export
      timestamp, source-data SHA-256, field-level mapping, explicit PII-scrubbing note)
      that fails this check outright, despite arguably being more traceable than what the
      check requires. Worth asking: should `check_provenance()` be extended to recognise
      an equivalent richer pattern as a pass (not just our exact three words), or is a
      fixed, literal marker deliberately preferred for how cheap and unambiguous it is to
      check? Changing this changes what "passing" means for every dashboard already
      built. It needs a deliberate decision, not made here.
