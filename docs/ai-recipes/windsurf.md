# Build a Tún artefact in Windsurf / Devin Desktop

**Reader:** user — you want an artefact out of a local data file, in the Windsurf-family editor.

One local file in, one self-contained HTML file out. The repository's own command does the
work, so this recipe is the same script a maintainer runs.

> **Read this first — the product was renamed.** As of 2026-11-18, `docs.windsurf.com`
> serves `docs.devin.ai/desktop/getting-started`, and the IDE that shipped as Windsurf now
> ships as **Devin Desktop**. The vendor's own words: "the package is now called
> `devin-desktop`. `windsurf` remains as a transitional package that pulls in
> `devin-desktop`, so existing installs keep updating." Rule files that still live under
> `.windsurf/` keep working — they are imported by default — but new files should go in
> `.devin/`. The recipe below gives both, and says which one wins when both exist.

## Capability line

| Capability | Devin Desktop | Notes |
|---|---|---|
| Read the repo and the fixture | yes | Rules, skills and plugins share one harness with Devin CLI |
| Repository instructions | `AGENTS.md` (root), or `.devin/rules/*.md` | Legacy `.windsurf/rules/*.md`, `.windsurf/global_rules.md` and `.windsurfrules` are imported by default |
| Create the output file | yes | Writes are governed by allow / ask / deny permission rules |
| Run the build and the check | yes | "The agent can run terminal commands on its own. Your permission rules and the session mode decide which commands run without asking" |
| Open the result in a browser | partial — **Previews**, not a verification tool | Previews proxy your local dev server into the IDE or your browser for element/error capture. It is not a headless test. Use the repo's `browser` command for that. |

`Cascade` is the legacy agent: the vendor states Devin Desktop "no longer starts new Cascade
conversations". Use **Devin Local**. Workflows are Cascade-only; do not build this on them.

## Setup

1. Clone and enter the repository:

   ```bash
   git clone https://github.com/jkorsvik/tun.git
   cd tun
   ```

2. The simplest instruction file is `AGENTS.md` in the project root. It needs no
   frontmatter, and it is always on:

   ```markdown
   # Tún project rules

   - Build artefacts only with `python3 tools/ai_recipe.py build`.
   - Verify with `python3 tools/ai_recipe.py check` before opening a browser.
   - On Windows use `py -3` instead of `python3`.
   - Write output only under `work/`.
   - Keep the Origin Notice provenance block in every generated artefact.
   ```

   `AGENTS.local.md` works too, for personal rules you keep out of version control, and
   `AGENT.md` is also read. In a subdirectory, an `AGENTS.md` gives directory-specific
   guidance.

3. If you want a trigger-scoped rule instead, `.devin/rules/tun-recipe.md`:

   ```markdown
   ---
   trigger: always_on
   ---

   - Build with `python3 tools/ai_recipe.py build`, verify with `check`.
   - Windows: `py -3 tools/ai_recipe.py …`.
   - Output only under `work/`. Keep the Origin Notice.
   ```

   `trigger` accepts `always_on`, `glob`, `model_decision` and `manual`.

   **If you already have `.windsurf/rules/`**, leave it in place: "Rule files in both
   `.devin/rules/` and `.windsurf/rules/` load; when both `global_rules.md` files exist,
   only `.devin/global_rules.md` loads." A stale `.windsurf/` rule that contradicts the new
   one is a real failure mode here — if the agent disobeys, look there.

4. No package install. Python 3.9 or newer; the builders are standard library only.

## The prompt

Paste this into Devin Local, unchanged:

```text
Work in this repository (the Tún toolkit checkout). Do not use the network.

Read docs/ai-recipes/common-contract.md and docs/ai-recipes/fixtures/excuses.csv first.

1. The fixture has columns Category,Count,Month: Traffic 3, Weather 1, Traffic 2,
   Calendar 4. Count totals 10. It is synthetic example data, safe to read.
2. Build the artefact with the repository's own command:
       python3 tools/ai_recipe.py build
   (Windows: py -3 tools/ai_recipe.py build)
3. Verify it:
       python3 tools/ai_recipe.py check
4. If Playwright and Chromium are already provisioned, run:
       python3 tools/ai_recipe.py browser
   and confirm the Traffic filter shows 10, then 5, then 10 again on Reset, with no
   console errors and no network requests.
5. Report: the output path, the row count, the traffic total before and after the filter,
   and whether the Origin Notice block is present. Change nothing outside work/.
```

## What you should get

Exactly one file: `work/ai-recipes/tun-recipe.html`. All markup, CSS, data and interaction
inlined; no remote resource. The command takes no required arguments — that default path is
the contract. `build` has no positional argument; `check` and `browser` accept one optional
HTML path.

## Validate

```bash
python3 tools/ai_recipe.py check
python3 tools/ai_recipe.py browser      # needs provisioned Playwright + Chromium
```

`check` asserts the canonical structure and content: four rows, total 10, the Origin Notice,
and the builder-output and fixture digests. `browser` loads the file over
`file://` with remote requests blocked, drives the filter, and takes a screenshot.

If a colleague sends you a copy to inspect:

```bash
python3 tools/ai_recipe.py check ~/Downloads/tun-recipe.html
```

Do not substitute Previews for `browser`. A preview shows you the page; it does not assert
the numbers.

## Licence and the Origin Notice

The toolkit is AGPL-3.0-or-later; **the artefact is your own work**, under terms of your
choosing, by the Tún Artefact Exception v1.1 — provided "the Origin Notice is preserved in
the Generated Artefact". That is the provenance comment block naming Tún and where to find
it. It need not be visible to a reader, and any visible "made with Tún" text is a removable
default. Do not claim the file came from something other than Tún.

## Safe file handoff

With the synthetic fixture, `work/ai-recipes/tun-recipe.html` is safe to send to anyone.

With real data the boundary is the **folder, not a filter**: a browser filter hides nothing,
the rows are in the file. Build one artefact per audience, each in its own folder, so the
destination's permissions govern access. Split the data before it is written.

## Limitations and recovery

- **Product identity drift.** The rename is recent enough that screenshots, menus and
  third-party guides on the web still say Windsurf. The file locations are the thing to
  trust; they are the ones above.
- **Two rule trees.** `.devin/` wins for `global_rules.md`, but `.windsurf/rules/` still
  loads. Conflicting rules are a plausible cause of odd behaviour.
- **Previews are not verification.** They need a local dev server and they do not assert
  anything. For a file on disk, `browser` is the real check.
- **Browser verification unavailable** when Playwright + Chromium are not provisioned; that
  step is blocked, not fixable from inside the recipe. Use `check` and look at the file.
- **Windows.** Use `py -3` for every `python3`.
- **Permission prompts.** The agent may ask before a command runs; approve the two Tún
  commands and nothing wider.

## Status

**Last product run:** Not run. The commands are the repository's documented ones; the
capability claims are from the vendor's published documentation, read 2026-11-18. No
end-to-end run in Devin Desktop (or Windsurf) has been recorded against this recipe.

**Owner:** Tún maintainers.

**Sources** (vendor documentation, read 2026-11-18):
<https://docs.devin.ai/desktop/devin-local/customizations> ·
<https://docs.devin.ai/desktop/devin-local/permissions> ·
<https://docs.devin.ai/desktop/terminal> ·
<https://docs.devin.ai/desktop/previews> ·
<https://docs.devin.ai/desktop/cascade> ·
<https://docs.windsurf.com/> (redirects to Devin Docs)
