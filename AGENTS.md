# AGENTS.md

Repo instructions for RAIWork / Claude Code working in this repository.

## What this repo is

A capability for building **standalone interactive dashboards as single self-contained
HTML files**, distributed through SharePoint/OneDrive as documents rather than served as
a web app. Positioned as a lighter-weight alternative to Power BI for reporting that only
ever needed to be a shareable, explorable snapshot.

The direction is open-ended by design. This repo is plumbing that gets out of the
users' way: measured constraints, a working template, and skills that turn a sentence
into a shareable dashboard.

So: when a user wants to go somewhere the current design doesn't support, **the design is what
gives way.** Don't defend the architecture — check whether the constraint is real (measure
it) and then find the route. The only things that don't bend are the two safety rules below.

Users may not have a dev toolchain; many are on Windows. See rule 5.

## Non-negotiable rules

### 1. Never write a row into a file whose audience should not see it

The security boundary is the **folder**, not a filter expression. So when different people
need different data, the answer is **split the data and give each audience its own folder**
— same dashboard shell, one `data.js` each. Do not refuse the request, and do not put a
filter in a shared file: a browser filter hides nothing, the rows are still in the file.

The split must happen *before* the data is written. `tun-new`, `tun-help` and
`tun-powerbi-escape` all handle this. Keep that behaviour.

### 2. Never defeat `Content-Disposition: attachment`

SharePoint forces it on every file. It is an XSS control in a corporate document store. The
architecture routes around it (the download *is* the delivery mechanism). Any "clever"
workaround is defeating a security control — don't, and push back if asked.

### 3. `tun-verify` must pass before anything is published

A clean build is not evidence. The artefact must be opened in a real browser from a
`file://` URL — the same way a recipient will — and the screenshot must be looked at by a
human. Assertions cannot see overlapping labels or a number that's wrong by 1000×.

### 4. If a tenant constraint changes, update the doc in the same commit

`docs/01-tenant-constraints.md` is empirical. Every row was measured against a live
enterprise Microsoft 365 tenant. If `probe/tenant-probe.py` reports a divergence, update that doc **and** re-check
every architecture decision that depended on the old behaviour, in the same change.

### 5. Cross-platform, and no toolchain prerequisites

**Everything must run on Windows as well as macOS.** Many users are on Windows. That
means: no shell scripts, no `~/Library/...` paths, no `brew`, no assumption that symlinks
work. `setup.py` and `tools/` are cross-platform stdlib Python — keep them that way, and if
you add tooling, it goes in Python too.

Windows specifics that have bitten us: skills get **copied** rather than symlinked without
Developer Mode (so `setup.py` must be re-run after editing a `SKILL.md`), and the OneDrive
sync root is `%OneDriveCommercial%`, not the macOS CloudStorage path.

Nothing to install. No framework. No build step. No Node. No virtualenv to activate.
`tools/` is **stdlib-only Python** deliberately — keep it that way.

If a skill would require the user to install or configure something, either the skill
does it silently or the design is wrong.

Corollary for prose: explain the things that are specific to this stack — why SharePoint
forces a download, what "self-contained" buys us, why there is no compile step. Do not
explain general computing. Skills own the vocabulary of *this* domain; the user owns the
business question. Be concise and concrete rather than tutorial.

### 6. Never commit real customer/client data into this repository

Rule 1 governs what a *dashboard artefact* may put in front of an audience. This rule is
the same boundary applied to the repo itself: real data from any engagement — survey
responses, a named client's report or deck, anything that isn't synthetic example data —
must never enter a commit here, not even in a scratch subdirectory, not even briefly.

`work/<task>/` is where a session builds a real deliverable, and it is gitignored for
exactly this reason (see the comment in `.gitignore`). A `git add -A` in a shared checkout
can still sweep another task's scratch directory into a commit. Removing it afterwards
means rewriting history on every branch, and a forge can keep server-side snapshots (for
example a merged pull request's head ref) that cannot be deleted. It costs nothing to
avoid up front.

Concretely: before staging anything with `git add -A` or `git add .` in a checkout, check
`git status` for paths you don't recognize as this project's own — a shared checkout can
hold another task's scratch directory. When in doubt, stage explicit paths instead.

## Way of working

See [`docs/06-way-of-working.md`](docs/06-way-of-working.md). The load-bearing ones:

- **Verify, don't assume.** Measure the live system; don't cite a doc for a checkable fact.
- **Look at the artefact.** A clean build is not evidence. Open it, check a number.
- **Show before sending.** Anything going to a human is approved in full first.
- **Python → `uv`, JS → `bun`. Never `pip` or `npm`.** Public registries are the
  default source in `pyproject.toml` / `bunfig.toml`. The Tier 1 path needs neither tool,
  by design.
- **`hotshot`** for real tooling changes (implement → verify → review → PR). Not for prose
  edits to a `SKILL.md`.
- **`writing-for-agents`** whenever editing a `SKILL.md` or this file.

## Conventions

- **Skills are prose, not code.** `skills/*/SKILL.md` — frontmatter (`name`,
  `description`) plus plain-English instructions. Written to be edited by anyone on the
  team without a build step. Optimise for clarity over completeness.
- **Every skill states its tier and governance cost in its first reply.** Nobody should
  discover an admin approval chain at the end.
- **Provenance is mandatory.** Every generated dashboard carries a comment block naming
  source data, extract time, build time, requester, and row count. A number nobody can
  trace back is a liability.
- **Norwegian for user-facing output** (dashboard chrome, announcements) — match the
  user's language. English for docs and code.
  The builders take `--lang nb|en` (default `nb`); the strings live in `templates/i18n/`
  (docs/12 section 5).
- **Brand colours come from the active plugin**, never from core. The example brand
  (fictional Eksempel AS) lives in `plugins/eksempel/tokens/palette.css`; status
  colours live in `tools/tokens/status-semantic.css`. Do not invent a colour or recall
  one from memory — read it from those files.

  Two deliberate choices, both to protect portability:
  - **No external CSS package is imported.** Only the token *values* in use are
    inlined. Importing a full package would add a remote dependency and break the
    offline, self-contained guarantee.
  - **No webfont is embedded.** The `font-family` stack uses a brand typeface when it
    is installed locally, but never loads one from a font CDN. Embedding ~150 KB of
    base64 woff2 in every dashboard is the wrong trade, and redistributing a font
    inside arbitrary shared files is a licensing question.

  Spacing: `rem` in 0.5 increments, line-heights on the 8-pixel grid, no raw `px`.
- **Tier 1 size budget:** warn >20 MB, fail >50 MB. Enforced in `build_dashboard.py`. The
  fix for an over-budget dashboard is pre-aggregation, not raising the limit.

## Layout

```
docs/       00-vision, 01-tenant-constraints (empirical), 02-architecture,
            03-skill-tree, 04-onboarding, 05-toolchain,
            06-way-of-working, 07-portable-cube, 08-generic-artifact-model
            (adopted — Layer 0/1 split, external vendoring), 09-13 (usability,
            palettes, browser support, maintainability, paired-data contract),
            14-generic-layer-manifest (what's safe to vendor into another repo)
skills/     the six dashboard skills — this project's own
skills/dev/ hotshot, magnus-review, writing-for-agents — how the work gets done,
            deliberately stack-agnostic. See skills/README.md for the split.
            Both groups are copied into ~/.raiwork/skills by setup.py (--link to
            symlink instead, only when editing the skills themselves)
templates/  single-file-dashboard.html (rows), cube-dashboard.html (dense cube).
            Hand-rolled SVG charts, zero dependencies
tools/      build_dashboard.py, build_cube_dashboard.py, verify_dashboard.py — stdlib only
probe/      tenant-probe.py — reproducible tenant constraint check
examples/   working examples + sample data (03 regenerates its own source data)
```

## Verification gate

Before claiming any change works:

```bash
# rebuild the example and prove it still renders
python3 tools/build_dashboard.py \
  --data examples/01-hello-dashboard/salgsdata.csv \
  --title "Salg per region og produkt 2026" \
  --dimension Produkt --measure Belop --time Maaned \
  --filters Region,Produkt,Kanal \
  --source "Eksempeldata (syntetisk) — salgsdata.csv" \
  --requested-by "Prosjekteier" \
  --out examples/01-hello-dashboard/salg-dashboard.html

python3 tools/verify_dashboard.py examples/01-hello-dashboard/salg-dashboard.html
```

`--source` and `--requested-by` are part of the command, not optional garnish. Without
them the rebuild silently rewrites the committed example's provenance to `salgsdata.csv`
and `not stated`, and nothing warns you. Pass a role, not a person's name. One line of the block still moves on
every rebuild: `Extracted` comes from the data file's mtime, and git does not preserve
mtimes, so in a fresh clone or worktree it reads as the moment you checked out. That is
the artefact telling the truth about what it was built from, not a defect to chase.

Must print `✓ PASS`. Then **look at the screenshot**.

`verify_dashboard.py` and `verify_standalone_core.py` both need Playwright, and both
**fail** without it rather than skipping the browser half — a gate that reports success
having never opened the file is worse than one that reports nothing. Install it with
`uv sync --extra verify && uv run playwright install chromium`.

Then run the three suites. All are stdlib-only and none touch anything outside a temp
directory:

```bash
python3 tests/test_skill_links.py            # 44 assertions, throwaway HOME
python3 tests/test_row_24_26_checks.py       # 97 assertions + a mutation pass
python3 tests/test_verify_gate_browser.py    # 16 assertions + a mutation control
python3 tests/test_findings_index.py         # every findings-index row resolves, 3 mutation controls
python3 tests/test_process_diagram.py        # spec rules, layout faults injected, example up to date
python3 tests/test_tun_feedback.py           # feedback log helper + --feedback-to on both builders
```

`test_skill_links.py` covers `setup.py`, which decides whether to replace or preserve a
path in `~/.raiwork/skills`; getting that wrong deletes a skill the user wrote, or
silently moves authority for a global tool into this checkout. Both happened during
development.

`test_row_24_26_checks.py` covers the tenant-constraint gates for rows 24, 25 and 26 —
failures that cannot be reproduced locally, so a static check is the only mechanism that
can catch them. It scans the files git tracks, prints how many it resolved, and refuses
to report success on an empty list.

`test_verify_gate_browser.py` covers the one property above: no verdict of success
without a browser.

If you touched `templates/single-file-dashboard.html`, that is the only proof the change
is safe — the template is the whole product.

## Quirks worth carrying between sessions

- **Quick Look (iOS 13+/macOS) blocks JavaScript in HTML attachment previews** —
  Messages, Mail, and Files all use it when someone taps/opens an `.html` file sent as an
  attachment (not a link). Deliberate Apple security decision, not fixable from inside
  the file. `<noscript>` doesn't help (scripting is still "on" in the spec's eyes, Quick
  Look just won't run the specific script tags). Full writeup, root-caused, in
  `docs/11-responsiveness-and-browser-support.md` §3c — read it before touching
  the `#ingenkode`/canary pattern. **No client data or example content from a real case
  belongs in this repo** — the pattern and the generic lesson do, the specific dashboard
  never should (see the "Never write a row into a file whose audience should not see it"
  rule above; the same boundary applies to *this* repo's own working tree, not just to
  what a dashboard emits).
  - Detection needs no JS-in-JS bootstrapping: a canary
    `<script>document.documentElement.className+=" js"</script>` as the first line in
    `<body>`, plus plain CSS keyed off its *absence* (`html:not(.js) …`). The `.js` class
    landing on `<html>` **is** the proof something ran.
  - Don't stop at a "this is broken" banner — pre-render the highest-value static facts
    directly into the markup a JS render would otherwise populate from empty. The JS
    overwrites it harmlessly when it does run.
  - Watch for *nested* hidden state: unblocking a container's `opacity:0` isn't enough if
    its children have their own independent `opacity:0` rule, gated on the same missing
    class one level down — the container becomes visible but stays empty.
  - Regression-test with a real no-JS render, not a visual guess: a Playwright context
    with `java_script_enabled=False`, load the file, assert body text stays above a
    floor. Cheap and permanent; keep it as a script, not a one-off check.
  - The actual fix for distribution is still a shared link (OneDrive/SharePoint), not a
    raw attachment — zero recipient guiding needed vs. a multi-step "save then open in
    a browser" instruction per recipient.
- **Mutation harnesses run in the background.** A harness that edits a file in place and
  restores it afterwards must never run under a foreground tool timeout. One was killed
  between the two steps and left a mutated tree that looked like a real build. See
  `docs/12-maintainability-conventions.md` §4.
- **Pillow on macOS**: `Image.open()` is lazy — the file isn't decoded yet. Calling
  `.convert(...)` or `.save(...)` on that handle without an explicit `.load()` first can
  silently write a truncated ~32-byte file with no exception. Always `img.load()`
  immediately after `Image.open()` before any transform, unless it's one unbroken
  `Image.open(...).convert(...)` expression.
- **A repo checkout can end up disconnected from its own `.git`** — e.g. `core.bare`
  flipped to `true` on a directory that still holds real working files. Every `git`
  command in it then fails with "this operation must be run in a work tree", edits made
  there never reach any commit, and any real data dropped into it (survey exports,
  client files) sits on disk outside version control's visibility entirely, invisible to
  `git status` and easy to forget about. Confirm `git rev-parse --show-toplevel` succeeds
  in whatever directory you're about to write real data into, before you write it.

## Things that are deliberately not here

Don't add them without a conversation:

- a semantic layer or lineage graph. Provenance is written into each dashboard (source,
  extract time, requester) and is traceable by reading the file
- a JS framework or bundler — kills the zero-prerequisite property
- row-level anything — see rule 1
- a server — the artefact is a file; if a change needs a server, it's the wrong change

## 8. The public page at tun.community is not in this repo

Do not add a copy of it here. Its source lives in a separate repository, with its own
build and its own checks.

A copy here is worse than no copy. An edge proxy can rewrite HTML in transit: it can
inject a script into a page that promises none, and strip comment fences such as
`<!--email_off-->`. A copy taken by fetching the live page holds the *post-edge* bytes,
not the source. To check what the public actually gets, compare the delivered bytes with
the source, byte for byte.

What belongs in this repo is the licence the page describes: `LICENSE` and
`COPYING.ARTEFACT-EXCEPTION`. The page is a public surface, so review what it says about
that licence before a change goes live.
