# Generic-layer manifest — what an external repo may vendor

**Read this before copying anything from this repo into another one.** It exists because
`docs/08-generic-artifact-model.md` decided *that* external tools should vendor the
generic layer rather than restate it in prose; this file is the concrete list of *what*
that layer currently is, so a re-sync is a diff against a known list, not a guess.

This manifest only ever lists files that are genuinely generic — safe for a standalone
HTML artefact that has no dashboard vocabulary at all (no dimension/measure/filter, no
`bundled`/`paired`/`cube`). If a file only makes sense for dashboards, it does not belong
here, no matter how reusable it looks at first glance.

## The list

| File | What it is | Generic because |
|---|---|---|
| `tools/verify_standalone_core.py` | Verification: self-contained, size budget, unsubstituted `{{PLACEHOLDER}}` tokens, provenance block present, no literal `<script` text outside real script tags (docs/01 row 25), no `:target`-driven visibility (row 24), no scroll-persistent `sticky`/`fixed` positioning (row 26), console-clean render, screenshot | None of these checks reference dashboard DOM (`.kpi`, `.bar`, `#tbl`, `.chip`) — they check the *file*, not a template |
| `plugins/eksempel/tokens/palette.css` | Eksempel AS brand colour tokens (Blue, Navy, etc.), invented for the fictional example brand | Colour values, not layout or component markup — usable by any Eksempel-AS-branded artefact |
| `tools/tokens/status-semantic.css` | Positive/negative/neutral status colours, WCAG-checked against white | Same reasoning — a status colour is not dashboard-specific, any artefact showing a delta or health state needs one |
| `tools/tokens/theme-light.css` | Maps generic chrome roles (`--bg`, `--panel`, `--ink`, `--muted`, `--line`, `--brand`) onto the tokens above | The role names are generic UI chrome, not dashboard vocabulary |
| `templates/_generic-provenance-block.html` | The provenance HTML-comment template, extracted from `templates/single-file-dashboard.html`, with the one dashboard-only line (`Rows inlined`) replaced by a free-form `{{ARTIFACT_SPECIFIC_LINE}}` a specialisation fills in | Every generated standalone artefact needs traceability, not just dashboards — see `AGENTS.md` rule "Provenance is mandatory" |

## Explicitly NOT on this list (dashboard-specific, do not vendor)

- `tools/verify_dashboard.py` — imports the generic core above but adds KPI/chart/table/
  interactivity DOM assertions that only make sense for `single-file-dashboard.html` /
  `cube-dashboard.html`.
- `templates/single-file-dashboard.html`, `templates/cube-dashboard.html` — real templates
  with dimension/measure/filter vocabulary baked in.
- `templates/portable-slide-deck.html` and `tools/verify_slide_deck.py` — a reusable
  presentation specialisation, not the Layer 1 core shared by every artefact type.
- `tools/tokens/theme-dark.css` — marked experimental in its own header, not wired into
  any production template here yet; wait for it to graduate before another repo builds on
  a moving target.
- Anything under `skills/dashboard-*` — those are this project's own RAIWork skills.

## Vendoring convention

An external repo that wants some of the files above:

1. Create `vendor/tun/` in the external repo, mirroring this
   repo's relative paths (`vendor/tun/tools/tokens/...`, etc.).
2. Copy the files **verbatim** — do not hand-edit a vendored file. If it needs to behave
   differently, that is a sign it should not have been vendored as-is; open a conversation
   about generalising it here instead.
3. Add a `VERSION.txt` inside `vendor/tun/` recording:
   ```
   <commit-sha> (<your-forge>/<owner>/tun, <date>)
   ```
   This repo has no tags yet, so pin to a commit SHA,
   not a version number, until that changes.
4. Re-sync manually when needed — there is no automation, deliberately (see `docs/08`,
   "External consumers": a submodule or live dependency would remove the drift but
   assumes shared-git fluency this convention does not require).
5. When re-syncing, diff against this manifest first — a file added here since the last
   sync is a deliberate signal that it graduated to "safe to reuse," not noise to ignore.

## Change log

- Manifest created at adoption of `docs/08-generic-artifact-model.md`.
