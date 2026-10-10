# Roadmap

**The direction belongs to the people who use this.** What follows is not a fixed plan.
It is the state of the plumbing, plus the questions currently blocking things, so that
users can decide what matters.

If their priorities differ from this list, **this list is wrong.** Rewrite it.

---

## Phase 1 — Tier 1 works end to end ✅ DONE

- [x] Verify empirically what SharePoint/OneDrive do with HTML (`docs/01-tenant-constraints.md`)
- [x] Single-file dashboard template, no framework, no CDN, brand palette
- [x] `build_dashboard.py` — stdlib only, Norwegian number parsing, size budget enforcement
- [x] `verify_dashboard.py` — real browser render, interactivity check, screenshot
- [x] Skills: `tun-help`, `tun-new`, `tun-data`, `tun-verify`,
      `tun-publish`, `tun-powerbi-escape`
- [x] `tenant-probe.py` — reproducible constraint check
- [x] Onboarding for a first user
- [x] Working example, verified

## Phase 2 — First real user, first real dashboard 🔜 NEXT

The point of this phase is to find out what the docs got wrong.

- [ ] **A first real user installs RAIWork and ships one real dashboard** end to end, from their own
      data, into a real SharePoint folder, shared with real colleagues
- [ ] Fix whatever that reveals — expect the onboarding and `tun-new`'s questions
      to need adjusting after contact with a real user
- [ ] A use-case list: the real reports in your area that could move, **and the ones
      that can't, with the reason.** The refusal list is the more valuable half
- [ ] Capture the first honest reaction from a viewer who is not us. Specifically: does
      the download step confuse them, and does the wording in `tun-publish` fix it?

**Success criterion:** a colleague who has never heard of this opens a dashboard, uses a
filter, and gets an answer — without asking how.

## Phase 3 — Prove the Power BI claim

- [ ] Port one real Power BI report with `tun-powerbi-escape`, including number-for-number
      reconciliation against the original
- [ ] Run both in parallel; let the owner decide whether to retire the original
- [ ] Write up what the port cost in effort and what it lost — honestly
- [ ] Decide whether the "replaces Power BI" framing survives contact with reality, or
      needs narrowing to a specific report class

## Phase 4 — Break the download ceiling (Tier 2)

Blocked on a governance question, not an engineering one.

- [x] ~~Test the **Teams tab** / iframe hypothesis~~ — **answered, negative.**
      `Content-Disposition: attachment` is unconditional (HTML, `.aspx`, `.svg` all
      tested) and in an iframe that disposition renders nothing while triggering a
      download. No iframe can render a file from a document library, so this is not a
      CSP or Teams problem — the route does not exist. Constraints doc rows 12–13.
- [ ] **Decide whether in-page embedding is worth an admin chain at all.** The only
      routes left are SPFx (code in the page bundle) or an Embed web part in HTML-snippet
      mode (markup in the page). Both need an admin, and Baseline Security Mode is closing
      the second. What it buys is "appears on a page without clicking a file" — a
      convenience, not a capability. Paired mode already gives dynamism; a file already
      reaches further, including outside the organisation.
- [ ] If either lands: `dashboard-embed` skill + a minimal SPFx host web part
- [ ] Confirm same-origin `fetch('/_api/...')` works from an SPFx-hosted page without an
      app registration (expected, unverified)

## Phase 5 — Break the size ceiling (Tier 3)

Depends on Phase 4 for a real HTTP origin to run from.

- [ ] Prove DuckDB-WASM reading Parquet from SharePoint over Range requests.
      The enabling constraint is **already confirmed** (`206 Partial Content`) — what's
      unproven is the end-to-end path with auth
- [ ] Establish the practical data ceiling by measurement, not by citing blog posts
- [ ] `dashboard-bigdata` skill

Most large-data needs are already met by the dense cube in Tier 1. Parquet, SQLite and
DuckDB earn their place first on the build side, in the job that writes the file. Phase 5
is for the cases the cube cannot answer: row-level detail over a huge table, ad hoc queries.

## Later, deliberately not now

- General builders for decks and reports beyond the current templates
- A plugin registry, and backend adapters for publishing targets
- Shipping all of Tún's skills as one plugin that replaces `setup.py` (decided in
  `docs/21-plugin-architecture.md`, not built)

## Continuous

- [ ] Re-run `probe/tenant-probe.py` quarterly, and whenever something breaks.
      Microsoft's Baseline Security Mode is actively tightening; assume the constraints
      doc decays
- [ ] Keep the skills' governance statements honest — if Tier 2 stays unproven, they must
      keep saying so
- **Enforce what is measured before measuring more.** A new tenant probe adds rows to
  `docs/01`. If earlier rows are still not enforced by a gate, the new rows repeat the same
  drift. Rows 24 and 26 were gated before row 27 was probed for this reason.
- **Ownership is settled (2026-10-11).** The code and docs are public through the
  sanitised export, and v0.1.0 is released. No marketplace release yet. The public face is
  tun.community.

## Harvested, not yet scheduled

Ideas from the working notes and presentations around this project, recorded so they are
not lost. None is committed to. Each needs an issue before work starts.

- [ ] **A default "make HTML" skill for RAIWork and Copilot**, built on the three patterns
      (standalone, paired, connected; `docs/08`). The stated goal is for it to be as
      ordinary to have installed as the Microsoft 365 skill.
- [x] **Feedback from inside the artefact.** Let a reader report a fault or a wish from the
      file itself, with a snapshot of machine, surface and console attached, so an issue
      arrives with its evidence instead of a description of it.
- [ ] **A glossary for non-developers**, one place for the explanations `docs/06` rule 7 asks
      for.
- [ ] **An analyser for HTML pages built outside this toolkit**, measuring them against the
      same gates. First run on one page only; too early to conclude anything.
- [ ] **Substrates beyond OneDrive and SharePoint**: a plain filesystem with hyperlinks, and
      Google Drive, next to the backends `docs/index.md` already lists as direction.
- [x] **A process-diagram skill that draws its own workflow.** One exists outside this
      repository, applied to itself: request, modelling, approval, rendering, with nodes
      flagged where the step should improve. Its purpose is teaching: help a beginner turn a
      script into a skill, and move from a local skill to a marketplace one.
- [x] **Spec-valid skill frontmatter** for every Agent Skills harness, with a gate
      (`docs/28`). Four of twelve skills were invalid YAML under the reference validator.
- [x] **Install into every harness:** `setup.py --tool agents|claude`. Tested: Gemini CLI
      and Claude Code load every skill (`docs/28`).
- [ ] **The rest of the `docs/28` harvest:** `compatibility` lines, `SOURCE_DATE_EPOCH` in
      every builder, a measured `<meta>` CSP, measured `<details name>` / `popover` /
      `:has()` rows, axe-core in the verifiers, a CSV download, text linked to the picture.

---

## Open questions

Written down so they don't get quietly forgotten. Answering any of these is worth more
than new features.

| Question | Blocks | Who can answer |
|---|---|---|
| Can an SPFx package get through tenant admin review? What's the lead time? | all of Tier 2, and Tier 3 with it | your SharePoint / M365 admins |
| Does a Teams tab work as a dashboard host? | a possible no-SPFx route to in-page embedding | anyone who can add a tab and try it |
| How do sensitivity labels / DLP behave on an `.html` file carrying business data? | whether Tier 1 is safe for labelled data | whoever owns information protection in your tenant |
| Do Range requests survive a *sharing link*, not just a Graph `downloadUrl`? | Tier 3 architecture | measurable — extend `tenant-probe.py` |
| Practical file-size ceiling before Outlook/SharePoint/browsers complain? | the Tier 1 size budget, currently a reasoned estimate | measurable |
| Which reports should move first? | Phase 2 and 3 scope | the users |
| The five questions in [the hosted route](docs/23-hosted-route-it-brief.md): who approves a single-page app registration with delegated `Files.Read`, and which host is approved for small internal tools? | the hosted route, which is Tier 2 option A and a real origin for Tier 3 | IT architecture and security |
| Is the multi-block model (`docs/13` §10) worth its formality, or should people match data sources to HTML themselves? | the multi-block design | the people who will build with it |
| Does a self-refreshing paired page, one that re-reads its sidecars without a reload, survive each surface? One informal session (2026-09-09) found: works through a Windows filesystem shortcut, fails in the OneDrive web app, macOS untested, and sharing the folder directly was not enough without a OneDrive shortcut. | self-refreshing paired pages | measurable; becomes a `docs/01` row only once reproduced with a written method |

## Explicit non-goals

Recorded so they don't creep back in:

- **A filter that pretends to be a security control.** Access is enforced by the folder a
  file sits in. Different audiences get different data files, split before writing. A
  browser-side filter is decoration, never a boundary.
- **Defeating `Content-Disposition: attachment`.** It is an XSS control in a corporate
  document store. We route around it; we do not break it.
- **A build toolchain on the Tier 1 path.** Nothing to install, no framework, no Node. The
  moment using a dashboard requires a build step, the product has failed its main user.
- **Becoming a BI platform.** No semantic layer, no lineage graph, no scheduler. If a
  need genuinely requires those, the answer is Power BI and we should say so quickly.
