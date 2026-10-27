# Findings index

Where each finding from the September 2026 harvest now lives. The harvest found 337
findings in 18 working reports. Most were already documented. This table lists the ones
that were missing or incomplete and have now been written in. The IDs come from the
internal coverage review. `tests/test_findings_index.py` checks that every row points to
a file that exists and still contains its anchor text. So if a section is deleted or
reworded, the test fails and someone has to decide where the finding went.

Internal-only findings (real-case details, server state) are not listed here.

| IDs | Finding | Home | Anchor |
|---|---|---|---|
| F513 F100 F674 F106 | Two devices editing one synced file: no merge (vendor behaviour, not measured) | [`01-tenant-constraints.md`](01-tenant-constraints.md) | `Two devices editing one synced file offline` |
| F514 F102 | A lock file cannot work from file:// | [`01-tenant-constraints.md`](01-tenant-constraints.md) | `A lock file cannot work.` |
| F101 | SharePoint list: If-Match returns 412 (from Graph docs) | [`01-tenant-constraints.md`](01-tenant-constraints.md) | `412 Precondition Failed` |
| F302 | SVG script runs from disk, SharePoint still forces download | [`01-tenant-constraints.md`](01-tenant-constraints.md) | `an SVG with an inline script *does* run its script` |
| F625 | iPhone Safari: Fullscreen API for video only | [`01-tenant-constraints.md`](01-tenant-constraints.md) | `` Fullscreen API for `<video>` only `` |
| F421 | Row 25 enforcing function and date | [`01-tenant-constraints.md`](01-tenant-constraints.md) | `` check_no_stray_script_text() `` |
| F118 | Outlook iOS preview blocks JS, static layer survives | [`11-responsiveness-and-browser-support.md`](11-responsiveness-and-browser-support.md) | `iOS app, native preview, measured 2026-09-28` |
| F376 F383 | Words in HTML, not inside an SVG, for phones | [`11-responsiveness-and-browser-support.md`](11-responsiveness-and-browser-support.md) | `Do not draw text into an SVG diagram` |
| F633 | overflow:hidden on body alone does not stop scrolling | [`11-responsiveness-and-browser-support.md`](11-responsiveness-and-browser-support.md) | `html, body { height: 100%; overflow: hidden; }` |
| F330 | Paired swap probe: 114 rows stay until reload, then 140 | [`13-paired-data-contract.md`](13-paired-data-contract.md) | `Reload: version 2,` |
| F503 | Four levels of who refreshes the data | [`13-paired-data-contract.md`](13-paired-data-contract.md) | `Four levels of who refreshes the data.` |
| F332 F680 | Parquet, SQLite, DuckDB: build side and heavy cases, not default | [`00-vision.md`](00-vision.md) | `Parquet, SQLite and DuckDB still have a place` |
| F505 | Text commits to a moment, interaction to a stream | [`00-vision.md`](00-vision.md) | `Text commits to a moment. Interaction commits to a stream.` |
| F424 | Core verifier checks listed in the manifest | [`14-generic-layer-manifest.md`](14-generic-layer-manifest.md) | `` no `:target`-driven visibility (row 24) `` |
| F647 F419 | Rebuild gives the same bytes | [`12-maintainability-conventions.md`](12-maintainability-conventions.md) | `A rebuild gives the same bytes.` |
| F502 | Derived numbers are locked by hash | [`12-maintainability-conventions.md`](12-maintainability-conventions.md) | `A number that can be derived is derived, then locked.` |
| F105 | A gate must prove it ran | [`12-maintainability-conventions.md`](12-maintainability-conventions.md) | `A gate must prove it ran.` |
| F406 | Static scan blind spot for script-loaded sidecars | [`12-maintainability-conventions.md`](12-maintainability-conventions.md) | `A static scan has a blind spot.` |
| F670 | zsh glob with no match stops the build | [`12-maintainability-conventions.md`](12-maintainability-conventions.md) | `Shell globs can stop a build.` |
| F144 F230 | Mutation harness never under a foreground timeout | [`12-maintainability-conventions.md`](12-maintainability-conventions.md) | `Never run an in-place mutation harness under a foreground timeout.` |
| F516 F626 | Keyboard shortcut standard, evaluated, not adopted | [`09-usability-and-navigation-principles.md`](09-usability-and-navigation-principles.md) | `Keyboard shortcuts: evaluated, not adopted` |
| F533 F537 F539 | Skills ship as a plugin that replaces the installer | [`21-plugin-architecture.md`](21-plugin-architecture.md) | `Decided: Tún's own skills ship as a plugin` |
| F348 | The old repository name | [`18-naming.md`](18-naming.md) | `tun` |
| F227 | uv missing from a non-login shell | [`05-toolchain.md`](05-toolchain.md) | `may be missing from a non-login shell` |
| F519 F125 | Block pushes from a clone with real data | [`24-git-hygiene.md`](24-git-hygiene.md) | `Block pushes from a clone that holds real data` |
| F506 | git add -A in a shared checkout | [`24-git-hygiene.md`](24-git-hygiene.md) | `is a claim about files you do not own` |
| F607 | Repair after an accidental sweep | [`24-git-hygiene.md`](24-git-hygiene.md) | `Repair after an accidental sweep` |
| F507 F508 F247 | History rewrite and how to check it | [`24-git-hygiene.md`](24-git-hygiene.md) | `byte-for-byte identical outside the stripped paths` |
| F509 | Forge-held pull refs | [`24-git-hygiene.md`](24-git-hygiene.md) | `The forge keeps refs you cannot delete` |
| F521 F360 | Ruleset without a pull_request rule | [`24-git-hygiene.md`](24-git-hygiene.md) | `does not block direct writes` |
| F216 | Archive a branch with real data | [`24-git-hygiene.md`](24-git-hygiene.md) | `Archive a branch with real data before deleting it` |
| F217 | Check identity after a rename | [`24-git-hygiene.md`](24-git-hygiene.md) | `Check identity after a rename or a long pause` |
| F143 | Ask the owner, do not infer | [`25-working-with-real-sources.md`](25-working-with-real-sources.md) | `Ask the owner. Do not infer.` |
| F121 | Build the step the workflow depends on first | [`25-working-with-real-sources.md`](25-working-with-real-sources.md) | `Build the step the real workflow depends on first.` |
| F129 | Copy the structure, never the rows | [`25-working-with-real-sources.md`](25-working-with-real-sources.md) | `Copy the structure, never the rows.` |
| F130 | The artefact carries the routine | [`25-working-with-real-sources.md`](25-working-with-real-sources.md) | `Let the artefact carry the routine.` |
| F663 | Form-tool CSV: BOM, dialect, stable ID | [`25-working-with-real-sources.md`](25-working-with-real-sources.md) | `Form-tool CSV exports are fragile.` |
| F664 | Excel cached values can be stale | [`25-working-with-real-sources.md`](25-working-with-real-sources.md) | `Excel cached values can be stale.` |
| F665 | Manual corrections in a side file | [`25-working-with-real-sources.md`](25-working-with-real-sources.md) | `Keep manual corrections in a side file.` |
| F662 | Primary answers beat secondary sources | [`25-working-with-real-sources.md`](25-working-with-real-sources.md) | `Primary answers beat secondary sources.` |
| F656 F512 | Quotes must be substrings of the fetched page | [`25-working-with-real-sources.md`](25-working-with-real-sources.md) | `exact substring of that text` |
| F658 | Check page numbers against the builder | [`25-working-with-real-sources.md`](25-working-with-real-sources.md) | `Proving the numbers on the page` |
