# Build a Tún artefact in a JetBrains IDE

**Reader:** user — you want an artefact out of a local data file, in IntelliJ IDEA, PyCharm,
WebStorm, GoLand or another JetBrains IDE.

One local file in, one self-contained HTML file out. The Python tooling has nothing to do
with your project's language: the Tún checkout is a folder you open and a command you run.

## Capability line

| Capability | JetBrains AI Assistant | Notes |
|---|---|---|
| Read the repo and the fixture | yes | Context-aware chat over the open project |
| Repository instructions | `AGENTS.md` at the repo root for agents; `.aiassistant/rules/*.md` for chat | The vendor separates the two; see setup |
| Create the output file | yes, via the agent's edits | Review the diff before accepting |
| Run the build and the check | **not confirmed in the vendor docs** | Coding agents "can handle multi-step development tasks", but the documentation I read does not state that they execute terminal commands in the IDE terminal. Use the IDE terminal or the Run button to be certain. |
| Open the result in a browser | no dedicated browser tool documented | Open `work/ai-recipes/tun-recipe.html` in your browser, or use the repo's `browser` command from the terminal |

So this recipe leans on the IDE terminal for the two commands that matter. That is not a
workaround, it is the interface: the commands are short and the output is a file.

## Setup

1. Clone the repository with **Git → Clone** in the IDE, or in the terminal:

   ```bash
   git clone https://github.com/jkorsvik/tun.git
   ```

   Open the resulting `tun` folder as a project. The IDE may offer to configure a Python
   interpreter. Use Python 3.12 or later for this guide. The builders use the standard library only. No
   package installation.

2. **For coding agents**, add `AGENTS.md` at the repo root. The vendor's agent-instructions
   page states agents read instruction files from the project — "Most agents rely on an
   `AGENTS.md` file for reusable guidance, though some use their own format" — and lists the
   sections a useful file has. Keep it short:

   ```markdown
   # Tún project rules

   ## Common tasks
   - Build: `python3 tools/ai_recipe.py build`
   - Verify: `python3 tools/ai_recipe.py check`
   - Browser check: `python3 tools/ai_recipe.py browser` (needs Playwright + Chromium)

   ## Development rules
   - On Windows use `py -3` instead of `python3`.
   - Write output only under `work/`.
   - Keep the Origin Notice provenance block in every generated artefact.
   - Do not use the network for this task.
   ```

3. **For AI Assistant chat**, optionally add `.aiassistant/rules/tun-recipe.md`. Do it from
   **Settings | Tools | AI Assistant | Rules → New Project Rules File**, which creates the
   `.aiassistant/rules` folder for you, or create the folder and file by hand. In the file's
   editor, set **Rule type**:

   | Rule type | Effect |
   |---|---|
   | `Always` | applied to every chat session (the default) |
   | `Manually` | only on `@rule:` or `#rule:` |
   | `By model decision` | applied when the model judges it relevant; needs an Instruction |
   | `By file patterns` | applied when a referenced file matches the Pattern |
   | `Off` | inactive |

   The distinction matters: **project rules apply "only in AI Assistant chat mode"**, while
   instruction files are what the selected coding agent reads. Setting only one of the two
   leaves the other path unguided.

4. Activation: the vendor lists a JetBrains AI subscription, your own API keys, an
   authorized provider account for integrated agents, or external coding agents. The
   documentation does not state which plan each feature needs — check your licence before
   assuming the agent is available.

## The prompt

Paste this into AI Assistant chat (or the agent), unchanged:

```text
Work in this repository (the Tún toolkit checkout). Do not use the network.

Read docs/ai-recipes/common-contract.md and docs/ai-recipes/fixtures/excuses.csv first.

1. The fixture has columns Category,Count,Month: Traffic 3, Weather 1, Traffic 2,
   Calendar 4. Count totals 10. It is synthetic example data, safe to read.
2. Build the artefact with the repository's own command, in the IDE terminal:
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
and `browser` accept one optional HTML path. Then open it: right-click the file in the
Project view → **Open In → Browser**, or drag it into Chrome.

## Validate

In the IDE terminal:

```bash
python3 tools/ai_recipe.py check
python3 tools/ai_recipe.py browser      # needs provisioned Playwright + Chromium
```

`check` asserts four rows, total 10, the Origin Notice, and the builder-output and fixture digests. `browser` loads the file over `file://` with remote requests blocked, drives
the filter, and writes a screenshot you should look at.

For a downloaded copy:

```bash
python3 tools/ai_recipe.py check ~/Downloads/tun-recipe.html
```

The IDE's own preview panes show you the page; they do not assert the numbers. Use the
command for the verdict.

## Licence and the Origin Notice

The toolkit is AGPL-3.0-or-later; **the artefact is your own work**, under terms of your
choosing, by the Tún Artefact Exception v1.1 — provided "the Origin Notice is preserved in
the Generated Artefact". That is the provenance comment block naming Tún and where to find
it. It need not be visible to a reader, and any visible "made with Tún" text is a removable
default. Do not claim the file came from something other than Tún.

## Safe file handoff

`work/ai-recipes/tun-recipe.html` built from the synthetic fixture is safe to send to anyone.

For real data the boundary is the **folder, not a filter**: a browser filter hides nothing,
the rows are in the file. Build one artefact per audience, each in its own folder.

## Limitations and recovery

- **Terminal execution by the agent is unconfirmed.** The vendor documents coding agents
  that work across files; it does not state that they run IDE terminal commands. If the
  agent cannot run the command, run it yourself in the terminal. Either way the artefact is
  identical.
- **Two instruction paths, and they are not the same file.** `.aiassistant/rules` is chat
  behaviour; `AGENTS.md` is what an agent reads. Configure the one that matches the feature
  you are using.
- **Rule type defaults to `Always`.** A rule you meant to keep manual will follow every
  chat. Check the Rule type in the file's editor if a rule feels intrusive.
- **Browser verification unavailable** when Playwright + Chromium are not provisioned.
  Blocked, not self-fixing; fall back to `check` plus a manual look.
- **ReSharper and Android Studio differ.** The vendor's AI Assistant documentation covers
  JetBrains IDEs only and says "Usage in Android Studio and ReSharper is not covered here."
  Do not assume identical rule paths there.
- **Windows.** Use `py -3` for every `python3`.
- **If `build` fails**, read the error rather than retrying; the builders refuse a table they
  cannot parse and name the column at fault.

## Status

**Last product run:** Not run. Commands are the repository's documented ones; capability
claims are from the vendor's published documentation, read 2026-11-18. No end-to-end run
recorded in a JetBrains IDE against this recipe.

**Owner:** Tún maintainers.

**Sources** (vendor documentation, read 2026-11-18):
<https://www.jetbrains.com/help/ai-assistant/> ·
<https://www.jetbrains.com/help/ai-assistant/configure-project-rules.html> ·
<https://www.jetbrains.com/help/ai-assistant/configure-agent-behavior.html>
