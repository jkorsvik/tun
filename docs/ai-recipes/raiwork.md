# Build a Tún artefact in RAIWork

**Reader:** user — you work in RAIWork and want an artefact out of a local data file.

Two routes, and they are not the same thing:

1. **Skills** — Tún 0.1.9 from the public marketplace. The assistant gets the vocabulary and
   the workflow, and asks before it builds.
2. **The repository's own commands** — `tools/ai_recipe.py`. This is the baseline, and it is
   what every other recipe in this directory uses.

The skill bundle does **not** ship `tools/ai_recipe.py`. It carries the engine, templates,
tokens and docs; the root CLI in this repository is a separate thing. So: use the repo
command for the build, and use the skills to make the assistant behave sensibly around it.

## Capability line

| Capability | RAIWork | Notes |
|---|---|---|
| Read the repo and the fixture | yes | Local file access in the session's working directory |
| Repository instructions | `AGENTS.md`, `CLAUDE.md` / `.claude/CLAUDE.md`, `.claude/rules/**/*.md` | Read from the repo root down to the working directory |
| Create the output file | yes | Writes under `work/` are ordinary file writes |
| Run the build and the check | yes | Bash tool, with the same approval gate as any command |
| Open the result in a browser | yes, via the repository's `browser` command | It needs provisioned Playwright + Chromium. RAIWork's own browser tools act in your real browser and are not a substitute for the assertion. |
| Install Tún skills | yes | Marketplace → search “Tún” → Install, or the CLI |

## Setup

### If Tún is already installed, skip this

Check first rather than installing over a working setup:

```bash
raicode manage marketplace list
```

`plugin  tun  0.1.9  …` in the output means you are done. If it is there at another version,
decide whether you need 0.1.9 before changing anything; this recipe is written against it.

### Installing 0.1.9

**In the app:** Marketplace → search **Tún** → **Install**. The listing is *Tún: dashboards
as one HTML file*, version 0.1.9, public.

**From the CLI:**

```bash
raicode manage marketplace install plugin/tun@0.1.9 --accept=skills
```

The CLI installs the plugin skeleton only unless you name the component groups:
`--accept=skills` installs the bundled skills, `--accept=scripts` the scripts. MCP server
consent is **not** supported from the CLI — if the plugin declares MCP servers, the install
still succeeds and the MCP entries are skipped with a note pointing at the GUI. Tún 0.1.9
does not need MCP for this recipe, so nothing is missing.

**Check where the selected skill resolves.** This is the failure mode worth the extra
minute. The plugin's own README warns: "Earlier repository-installed skills in
`~/.raiwork/skills/` can override plugin skills." Two copies of `tun-new` can exist —
`~/.raiwork/marketplace/plugins/tun/skills/tun-new/` and `~/.raiwork/skills/tun-new/` — and
the older one may win. Compare them:

```bash
head -8 ~/.raiwork/marketplace/plugins/tun/skills/tun-new/SKILL.md
head -8 ~/.raiwork/skills/tun-new/SKILL.md 2>/dev/null
```

The 0.1.9 copy carries `license: AGPL-3.0-or-later` and `metadata: version: 0.1.9` in its
frontmatter. A copy without those is the older user-level one shadowing the plugin. Do not
delete a user skill you or a colleague wrote — inspect it first, and if it was locally
modified, that is a deliberate migration decision, not cleanup this recipe should make.

**No dependency install, no publishing, no MCP.** The package has "no upload helper, remote
issue sender, feedback target or automatic dependency installer". Browser verification uses
an already provisioned Playwright package and matching browser binaries; if they are absent
the step is **BLOCKED** rather than downloading anything.

### Give the assistant the rule

In the repository, `AGENTS.md` already carries project instructions. For this task
specifically, add the two lines that matter to your session prompt rather than editing a
shared file:

```text
Build with `python3 tools/ai_recipe.py build`, verify with `check`, then `browser` if
Playwright is provisioned. On Windows `py -3`. Output only under work/. Keep the Origin
Notice. Do not use the network.
```

## The prompt

Paste this into a RAIWork session whose working directory is the Tún checkout, unchanged:

```text
Work in this repository (the Tún toolkit checkout). Do not use the network.

Ask your skills first: if a Tún skill is available, say which one you are using and why.
Then read docs/ai-recipes/common-contract.md and docs/ai-recipes/fixtures/excuses.csv.

1. The fixture has columns Category,Count,Month: Traffic 3, Weather 1, Traffic 2,
   Calendar 4. Count totals 10. It is synthetic example data, safe to read.
2. Build with the repository's own command — not a script you write yourself:
       python3 tools/ai_recipe.py build
   (Windows: py -3 tools/ai_recipe.py build)
3. Verify:
       python3 tools/ai_recipe.py check
4. If Playwright and Chromium are already provisioned, run:
       python3 tools/ai_recipe.py browser
   and confirm the Traffic filter shows 10, then 5, then 10 again on Reset, with no
   console errors and no network requests.
5. Report: the output path, the row count, the overall total and the Traffic subtotal,
   and whether the Origin Notice block is present. Change nothing outside work/. Do not
   publish, upload or send anything.
```

The `Ask your skills first` line is doing real work. The skills are prose, so the assistant
may route through `tun-new` — which asks about audiences before it builds, correctly — or it
may go straight to the command. Either is acceptable; what is not acceptable is inventing a
builder because a skill's scripts are elsewhere.

## What you should get

Exactly one file: `work/ai-recipes/tun-recipe.html`. All markup, CSS, data and interaction
inlined; no remote resource. `build` takes no arguments and writes there by default; `check`
and `browser` accept one optional HTML path.

## Validate

```bash
python3 tools/ai_recipe.py check
python3 tools/ai_recipe.py browser      # needs provisioned Playwright + Chromium
```

`check` asserts four rows, total 10, the Origin Notice, and exact agreement with this toolkit and fixture. `browser` loads the file over `file://` with remote requests blocked, drives
the filter, and writes a screenshot. RAIWork's `browser_*` tools can open the file too, but
they show you the page; the command is the assertion.

For a copy someone sent you:

```bash
python3 tools/ai_recipe.py check ~/Downloads/tun-recipe.html
```

## Licence and the Origin Notice

The toolkit and the plugin are AGPL-3.0-or-later. **The artefact is your own work**, under
terms of your choosing, by the Tún Artefact Exception v1.1 — provided "the Origin Notice is
preserved in the Generated Artefact". That is the provenance comment block naming Tún and
where to find it. It need not be visible to a reader, any visible "made with Tún" text is a
removable default, and the condition lapses for a delivery format that cannot carry it. You
may not claim the file came from something other than Tún.

## Safe file handoff

`work/ai-recipes/tun-recipe.html` built from the synthetic fixture is safe to send to anyone.

For real data the boundary is the **folder, not a filter**: a browser filter hides nothing,
the rows are in the file. Split the data before it is written; one artefact per audience,
each in its own folder, and let destination permissions decide access.

## Limitations and recovery

- **A shadowed skill.** Symptoms: the assistant uses an older workflow, misses a step this
  repository added, or cannot find the shared engine. Cause: `~/.raiwork/skills/tun-*`
  winning over the plugin copy. Check the frontmatter as above.
- **The repo command is not in the plugin.** If you installed only the plugin and have no
  checkout, `tools/ai_recipe.py` is not there to run. Clone this repository for the command;
  the skills are not a substitute for it.
- **Browser verification blocked.** Playwright and Chromium must already be provisioned. The
  package does not install them and neither does this recipe.
- **MCP skipped on CLI install.** Expected. Tún 0.1.9 needs no MCP entry for this task; if a
  future version does, install through the GUI.
- **No publishing.** `tun-publish` and `tun-host` prepare local handoffs. There is no
  uploader, remote issue sender or feedback target in the package, and this recipe does not
  add one.
- **Windows.** Use `py -3` for every `python3`.
- **If `build` fails**, read the error. The builders refuse a table they cannot parse and
  name the column at fault; a retry fails identically.

## Status

**Last product run:** Not run. The install path, the shadowing behaviour and the package
boundary were read from the installed 0.1.9 manifest, its README and the RAIWork CLI's own
help text on 2026-11-18. No end-to-end run through this prompt has been recorded.

**Owner:** Tún maintainers.

**Sources** (product documentation and the installed package, read 2026-11-18):
`raicode manage marketplace --help`, `raicode manage marketplace install --help` and
`raicode manage marketplace list`;
the public listing *Tún: dashboards as one HTML file* as reported by
`raicode manage marketplace info plugin/tun` (version 0.1.9, public);
`plugin/manifest.json` in this repository, and the installed plugin's `README.md` at
`~/.raiwork/marketplace/plugins/tun/README.md`.
