# Roadmap

**The direction belongs to the people who use this.** What follows is the state of the
plumbing, the work that is ready to do, and the questions that block the rest. If their
priorities differ from this list, **this list is wrong.** Rewrite it.

Rewritten 2026-10-16 from a measured audit of the repository, its issues and tun.community.
Every item names its evidence, so it can be checked instead of trusted.

---

## Where it stands

Shipped and in use:

- Six artefact kinds from stdlib-only builders: bundled and paired dashboards, the dense
  cube, process diagrams, portable slide decks (`tools/build_*.py`), with `--lang nb|en`.
- Nine `tun-*` skills, installable into RAIWork, Claude Code and every Agent Skills tool
  (`python3 setup.py --tool raiwork|agents|claude`).
- Verification in a real browser, in Chromium, Firefox and WebKit (`--engines`), run on every
  public pull request.
- Hosts measured against the live tenant: SharePoint, OneDrive, Teams, e-mail, USB, cloud
  folders and Atlassian Artifacts (`docs/01`, `docs/26`, `docs/29`).
- Public since 2026-10-11 (AGPL-3.0 with the artefact exception), a Marketplace plugin
  `tun`, and the page at tun.community.

Measured on 2026-10-16:

| What | Value |
|---|---|
| Build of the example dashboard | 0.18 s, 122 KB |
| Largest committed artefact (cube, 4 M rows) | 0.82 MB |
| Pre-commit hook | 28 s, of which `test_core_boundary_gate.py` is 18 s |
| All 26 test suites, one after another | 53 s |
| Flaky suites | `test_chart_width_after_hidden_load.py`, 1 failure in 8 runs |

Not yet done: **nobody outside the project has shipped a real dashboard with it.** That is
the one gap that decides what the rest of this list is worth.

---

## Now: v0.2, the polish release

Known defects in what a user builds today. Each one is documented, still true in the code,
and small. One pull request per risk; then one Marketplace release carries them.

### A. The artefacts

| # | Item | Evidence | Effort |
|---|---|---|---|
| **A0** | **The dashboard escapes data before it writes HTML.** A CSV cell `<img src=x onerror=…>` runs as script in every reader's browser (proved 2026-10-16). Cell values, column names and filter options go into `innerHTML` raw. The cube escapes and is not affected. Free-text survey answers are a real use case. **Fixed 2026-10-16 in 0.1.4**, with a test that injects markup through every path. Rebuild dashboards made with an older version | `templates/single-file-dashboard.html:426`, `:436`, `:451-452` | S |
| A0b | The builders escape their own values: `--title` goes raw into HTML, and the dimension, time and measure column names go raw into JS strings, so a `"` in a column name stops the page | `templates/single-file-dashboard.html:6`, `:227-229` | S |
| A1 | Touch targets in the dashboard reach 44 × 44 px (three `<select>` are 37 px, reset is 42 px) | `docs/11` §1 | S |
| A2 | `verify_viewports.py` becomes a gate: run it from `verify_documented.py`, so CI fails on a small target | not referenced by any gate today | S |
| A3 | The no-JavaScript fallback (canary class plus pre-rendered facts) moves into the dashboard and cube templates | `docs/11` §1 and §3c; proven in examples 07 and 10, absent from both templates | M |
| A4 | The cube gets `@media print`, copied from the dashboard's tested rules | `docs/11` §8; no print rule in `templates/cube-dashboard.html` | S |
| A5 | The cube builder takes `--source`, like the dashboard builder, so its provenance can name the data | `tools/build_cube_dashboard.py` argparse | S |
| A6 | Sortable table headers work from the keyboard (`<button>` in `<th>`, `aria-sort`) | `docs/09` §1, `docs/11` §6 (WCAG 2.1.1) | M |
| A7 | One size budget for every builder (warn > 20 MB, fail > 50 MB), not only the two dashboard builders | process and deck builders have none | S |
| A8 | Builder flags agree: both dashboard builders accept `--dimensions` and `--measures`; the old names keep working | `--dimension` vs `--dims`, `--measure` vs `--measures` | S |
| A9 | Shared builder code (CSV reading, provenance, size budget) in one stdlib module | duplicated in `build_dashboard.py` and `build_cube_dashboard.py` | M |
| A10 | The rest of the `docs/28` harvest: axe-core inside the verifiers, `SOURCE_DATE_EPOCH` in every builder, a CSV download in the cube | `docs/28`, harvest list | M |

### B. The first five minutes

| # | Item | Evidence | Effort |
|---|---|---|---|
| B1 | Every user skill states its tier and governance cost in its first reply: `tun-data`, `tun-publish`, `tun-powerbi-escape`, `tun-verify`, `tun-help`, `tun-for-communicators` | AGENTS.md conventions; only `tun-new`, `tun-process` and `tun-feedback` do | S |
| B2 | A generic onboarding with a written Windows path, not "ask a teammate" | `docs/04-onboarding.md` Step 1 | M |
| B3 | Docs split by reader: user, contributor, and record. Records are marked as such; licensing (16, 17) and naming (18, 19) each become one doc | 33 docs, one flat folder | M |
| B4 | A glossary for non-developers, one place for the explanations `docs/06` rule 7 asks for | harvest list | S |
| B5 | tun.community shows real artefacts built by the engine, one link each, beside the hand-made demos | design review 2026-10-13 | M |
| B6 | One word for one thing: artefact, provenance block, self-contained | used interchangeably across skills and docs | S |

### C. The development loop

| # | Item | Evidence | Effort |
|---|---|---|---|
| C1 | Pre-commit under 10 s: run the independent checks in parallel, and run the boundary tests only when their inputs are staged | 28 s today; one suite is 18 s | S |
| C2 | Fix the flaky chart-width test | 1 failure in 8 runs | S |
| C3 | One command that runs every suite in parallel and prints one verdict | 26 suites, 53 s in sequence | S |
| C4 | The release as one checklist script: merge, tag, Marketplace plugin | several manual steps, each with its own guard | M |

**Done when:** every row above is merged, `tun` 0.2.0 is on the Marketplace, and the public
CI is green on all three engines.

---

## Next: real use

The point of this phase is to find out what the docs got wrong. Nothing here can be done
by writing code first.

- [ ] **The first real user builds one real dashboard** from their own data, into a real SharePoint folder,
      shared with real colleagues. Someone watches and writes down every point they get
      stuck.
- [ ] Fix what that shows. Expect the onboarding and `tun-new`'s questions to change.
- [ ] `docs/use-cases.md`: the real reports that could move, **and the ones that cannot,
      with the reason.** The refusal list is the more valuable half.
- [ ] The first honest reaction from a reader who is not us: does the download step confuse
      them, and does the wording in `tun-publish` fix it?
- [ ] Port one real Power BI report with `tun-powerbi-escape`, reconciled number for number
      against the original. Write down what the port cost and what it lost, and decide
      whether "replaces Power BI" survives or narrows to one class of report.

**Success criterion:** a colleague who has never heard of this opens a dashboard, uses a
filter, and gets an answer, without asking how.

---

## Later, after real use

Chosen from what real use shows, not before. Each needs an issue before work starts.

- A "make HTML" skill on the three patterns (standalone, paired, connected; `docs/08`), as
  ordinary to have installed as the Microsoft 365 skill.
- An analyser that measures HTML built outside Tún against the same gates.
- More hosts: a plain filesystem with links, and Google Drive.
- Multi-block dashboards from one catalogue and a shared purpose taxonomy, once someone
  needs more than one view in one file.
- A pitch deck on the slide deck builder.
- Data labels that translate, not only page strings (`docs/12` §1).
- Paired mode: validate the first `data.js` on load, and a cache-buster on swap (`docs/13`
  §2 and §7).

## Blocked: questions, not code

Tier 2 (a dashboard inside a page) and Tier 3 (data beyond the cube) wait on people, not on
engineering. Ask; do not build ahead of the answer.

| Question | Blocks | Who can answer |
|---|---|---|
| Can an SPFx package be approved in the tenant, and how long does it take? | all of Tier 2, and Tier 3 with it | SharePoint / M365 platform team |
| How do sensitivity labels and DLP treat an `.html` file with business data? | whether Tier 1 is safe for labelled data | Information Protection |
| The five questions in [the hosted route](docs/23-hosted-route-it-brief.md) | Tier 2 option A, and a real origin for Tier 3 | IT architecture and security |
| Do Range requests survive a sharing link, not only a Graph `downloadUrl`? | Tier 3 | measurable: extend `probe/tenant-probe.py` |
| What file size makes Outlook, SharePoint or a browser complain? | the size budget, today a reasoned estimate | measurable |
| Which reports move first? | real use | the first real user |
| Does a self-refreshing paired page survive each surface? One informal session (2026-09-09) said: yes through a Windows shortcut, no in the OneDrive web app | self-refreshing paired pages | measurable, once a written method exists |

Already answered: an iframe or Teams tab cannot render a file from a document library.
`Content-Disposition: attachment` is unconditional (`docs/01` rows 12 and 13).

## Continuous

- Re-run `probe/tenant-probe.py` every quarter, and whenever something breaks. Baseline
  Security Mode is tightening; assume `docs/01` decays.
- Gate what is measured before measuring more. Rows 24 and 26 were gated before row 27 was
  probed for this reason.
- Keep the skills' governance statements honest. If Tier 2 stays unproven, they keep saying
  so.

## Explicit non-goals

Recorded so they do not creep back in:

- **A filter that pretends to be a security control.** The folder a file sits in is the
  boundary. Different audiences get different data files, split before writing.
- **Defeating `Content-Disposition: attachment`.** It is an XSS control in a corporate
  document store. We route around it; we do not break it.
- **A build toolchain on the Tier 1 path.** Nothing to install, no framework, no Node.
- **Becoming a BI platform.** No semantic layer, no lineage graph, no scheduler. If a need
  really requires those, the answer is Power BI, and we say so quickly.
