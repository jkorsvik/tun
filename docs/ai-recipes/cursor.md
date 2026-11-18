# Build a Tún artefact in Cursor

**Reader:** user — you want an artefact out of a local data file, in the editor you already use.

One local file in, one self-contained HTML file out. No server, no account, no build step.
The repository's own command does the work, so the recipe is not a description of a
procedure you have to retype: it is the same script a maintainer runs.

## Capability line

| Capability | Cursor | Notes |
|---|---|---|
| Read the repo and the fixture | yes | "Search for files by name, read directory structures, and find exact keywords or patterns within files." |
| Repository instructions | `.cursor/rules/*.mdc`, or `AGENTS.md` | `.md` files in `.cursor/rules` are ignored — the extension must be `.mdc` |
| Create the output file | yes | "Suggest edits to files and apply them automatically." |
| Run the build and the check | yes | "Execute terminal commands and monitor output." |
| Open the result in a browser | yes | "Control a browser to take screenshots, test applications, and verify visual changes." |

The recipe below uses only the first, third and fourth. Browser verification is the
repository's `browser` command, which needs a provisioned Playwright + Chromium; if that is
missing, run the `check` step and look at the file yourself in Chrome.

## Setup

1. Clone and enter the repository (Cursor's terminal, or your own):

   ```bash
   git clone https://github.com/jkorsvik/tun.git
   cd tun
   ```

2. Add the project rule. Create `.cursor/rules/tun-recipe.mdc` with this frontmatter and
   body — `alwaysApply: true` is what makes it apply without you `@`-mentioning it:

   ```markdown
   ---
   description: "Build Tún artefacts with the repository's own commands"
   alwaysApply: true
   ---

   - Build artefacts only with `python3 tools/ai_recipe.py build`.
   - Verify with `python3 tools/ai_recipe.py check` before opening anything in a browser.
   - On Windows use `py -3` instead of `python3`.
   - Emit files only under `work/`.
   - Never remove the Origin Notice provenance block from a generated artefact.
   ```

   If you prefer a plain file, `AGENTS.md` in the project root works too, with no
   frontmatter. Cursor reads `AGENTS.md` in the root and in subdirectories, and combines
   nested files with "more specific instructions taking precedence".

3. No package install. The builders are standard library Python only. Python 3.12 or later for this guide.

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
inlined; no remote resource; opens from a folder or an attachment. The command takes no
required arguments — that default path is the contract.

Sanity-check it yourself before trusting it: open the file, and confirm four rows and a
total of 10. A clean build is not evidence that the page renders.

## Validate

```bash
python3 tools/ai_recipe.py check
python3 tools/ai_recipe.py browser      # needs provisioned Playwright + Chromium
```

`check` compares the output against the canonical structure and content: four rows, total
10, the Origin Notice present, and the builder-output and fixture digests.
`browser` opens the file from a `file://` URL with remote requests blocked and exercises
the filter; it writes a screenshot.

To validate a copy someone sent you rather than your own build, pass the path — it is the
only optional argument, and only `check` and `browser` accept it:

```bash
python3 tools/ai_recipe.py check ~/Downloads/tun-recipe.html
```

## Licence and the Origin Notice

The toolkit is AGPL-3.0-or-later. The **artefact you produce is your own work**, under
terms of your choosing, because of the Tún Artefact Exception v1.1 — provided you keep the
Origin Notice, the machine-readable provenance block naming Tún and where to find it:

> "the Origin Notice is preserved in the Generated Artefact."

It does not have to be visible to a reader, and any visible "made with Tún" line is a
removable default, not a condition. What you may not do is claim the file was produced by
something other than Tún. So: keep the comment block, rebrand the page freely.

## Safe file handoff

The fixture is synthetic, so `work/ai-recipes/tun-recipe.html` is safe to send to anyone.

For real data the boundary is the **folder, not a filter**. A browser filter hides nothing —
the rows are in the file. When different people need different numbers, build one artefact
per audience and put each in its own folder, so the destination's permissions decide who
opens which. Split the data before it is written.

## Limitations and recovery

- **Browser verification unavailable.** `browser` needs a Playwright package and matching
  browser binaries already provisioned. It does not install them. Without them, use
  `check` and open the file by hand.
- **`.md` in `.cursor/rules` silently does nothing.** The file must be `.mdc`. If your rule
  seems ignored, that is the first thing to check.
- **A wrong or missing rule file is not fatal.** The prompt above carries the instructions
  itself, so the build still works; the rule only saves you repeating them next time.
- **Windows.** Use `py -3` everywhere `python3` appears. No other difference.
- **If `build` fails**, read the error rather than retrying: the builders refuse a table they
  cannot parse, and the message names the column.

## Status

**Last product run:** Not run. The commands in this recipe are the repository's documented
ones; the capability claims are from Cursor's published documentation, read 2026-11-18.
Nobody has driven this recipe end to end in Cursor and recorded the result yet.

**Owner:** Tún maintainers.

**Sources** (vendor documentation, read 2026-11-18):
<https://cursor.com/docs/context/rules> ·
<https://cursor.com/docs/agent/tools>
