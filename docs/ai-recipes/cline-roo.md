# Build a Tún artefact in Cline or Roo Code

**Reader:** user — you want an artefact out of a local data file, in a VS Code-family agent.

Cline and Roo Code can work with project files and run terminal commands when you permit them. Use the local Chromium check for browser verification.

## Capability line

| Capability | Cline | Roo Code | Notes |
|---|---|---|---|
| Read the repo and the fixture | yes | yes | both read files with approval |
| Repository instructions | `.clinerules/` or `.cline/rules/` or `AGENTS.md` | `.roo/rules/` or `.roorules` or `AGENTS.md` | Cline: "Workspace rules go in `.clinerules/` or `.cline/rules/`"; Roo: "Preferred Method: Directory (`.roo/rules/`)" |
| Create the output file | yes | yes | writes need approval |
| Run the build and the check | yes | yes | Cline: "run terminal commands"; Roo: `execute_command` "runs CLI commands on the user's system" |
| Open the result in a browser | Documented | Not confirmed | Use the local Chromium check for either tool |

Both require your explicit approval for actions. That is the point of the design, not an
obstacle — approve the two Tún commands and nothing wider.

## Setup

1. Clone and enter the repository:

   ```bash
   git clone https://github.com/jkorsvik/tun.git
   cd tun
   ```

2. Add the rules. `AGENTS.md` at the project root works in **both** tools with no
   frontmatter — the cheapest route, and it travels with the repo:

   ```markdown
   # Tún project rules

   - Build artefacts only with `python3 tools/ai_recipe.py build`.
   - Verify with `python3 tools/ai_recipe.py check` before opening a browser.
   - On Windows use `py -3` instead of `python3`.
   - Write output only under `work/`.
   - Keep the Origin Notice provenance block in every generated artefact.
   ```

   Tool-specific alternative, if you already use the native directory:

   | Tool | Path | Note |
   |---|---|---|
   | Cline | `.clinerules/tun-recipe.md` | `.cline/rules/` is the same thing; both are searched |
   | Roo Code | `.roo/rules/01-tun-recipe.md` | read recursively, in alphabetical order by filename |

   Cline precedence: "Workspace rules take precedence when they conflict with global
   rules." Roo precedence: global rules first, then workspace — "workspace rules take
   precedence when they conflict". Roo also reads `AGENTS.md` by default; it loads after
   mode-specific rules and before generic rules, and can be turned off with
   `"roo-cline.useAgentRules": false`.

3. No package install. Python 3.12 or later for this guide; the builders are standard library only.

## The prompt

Paste this into the agent, unchanged:

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
inlined; no remote resource. `build` takes no arguments and writes there by default; `check`
and `browser` accept one optional HTML path.

## Validate

```bash
python3 tools/ai_recipe.py check
python3 tools/ai_recipe.py browser      # needs provisioned Playwright + Chromium
```

`check` asserts four rows, total 10, the Origin Notice, and the recorded builder revision
and data identity. `browser` loads it over `file://` with remote requests blocked, drives
the filter, and writes a screenshot.

To inspect a copy rather than your own build:

```bash
python3 tools/ai_recipe.py check ~/Downloads/tun-recipe.html
```

## Licence and the Origin Notice

The toolkit is AGPL-3.0-or-later; **the artefact is your own work**, under terms of your
choosing, by the Tún Artefact Exception v1.1 — provided "the Origin Notice is preserved in
the Generated Artefact". That is the provenance comment block naming Tún and where to find
it. It need not be visible to a reader; any visible "made with Tún" text is a removable
default. Do not claim the file came from something other than Tún.

## Safe file handoff

`work/ai-recipes/tun-recipe.html` built from the synthetic fixture is safe to send to
anyone.

For real data the boundary is the **folder, not a filter**: a browser filter hides nothing,
the rows are still in the file. Split the data before it is written and give each audience
its own artefact in its own folder.

## Limitations and recovery

- **A tool's browser feature is not the repo's browser check.** An IDE preview shows you a page, but proves neither offline use nor the filter results. `tools/ai_recipe.py browser` is what asserts
  the numbers. Use the repository command for the verdict.
- **Browser verification unavailable** when Playwright + Chromium are not provisioned. The
  step is blocked, not self-fixing. Use `check` and open the file yourself.
- **Cline's single-file `.clinerules`.** The current documentation describes the
  `.clinerules/` and `.cline/rules/` directories; the legacy single `.clinerules` file is
  not in the docs any more. Use the directory.
- **Roo's rule load order** is easy to misread: global rules load first, so a global rule
  that contradicts the workspace one needs the workspace one to actually win. It does — but
  only for genuine conflicts, so check a surprising behaviour there.
- **Windows.** Use `py -3` for every `python3`.
- **If `build` fails**, read the error. The builders refuse a table they cannot parse and
  name the column at fault; retrying the same command will fail the same way.

## Status

**Last product run:** Not run. Commands are the repository's documented ones; capability
claims are from each vendor's published documentation, read 2026-11-18. No end-to-end run
recorded in either Cline or Roo Code.

**Owner:** Tún maintainers.

**Sources** (vendor documentation, read 2026-11-18):
<https://docs.cline.bot/features/cline-rules> ·
<https://docs.cline.bot/cline-overview> ·
<https://docs.roocode.com/features/custom-instructions> ·
<https://docs.roocode.com/advanced-usage/available-tools/execute-command>
