# Build a Tún artefact in Visual Studio (not VS Code)

**Reader:** user — you have Visual Studio 2022 or Visual Studio 2026 open and want an
artefact out of a local data file.

**This is not VS Code.** Visual Studio and Visual Studio Code are different products with
different Copilot integrations, different instruction file support and different version
requirements. If you are in VS Code — or in one of its derivatives such as Cursor, Windsurf
or Cline — this is the wrong page. The difference that bites here: **Visual Studio
documents `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md` and a
user-level `copilot-instructions.md`; it does not document `AGENTS.md` at all.**

Also worth separating: **IntelliCode is not Copilot.** It is the IntelliSense model that
star-sorts completions and offers whole-line inline predictions. It is completions only —
no chat, no agent, no file edits — and it is free for all Visual Studio users. Everything in
this recipe needs **GitHub Copilot in Visual Studio**, which requires a subscription (there
is a free trial).

## Capability line

| Capability | Visual Studio + Copilot agent mode | Notes |
|---|---|---|
| Read the repo and the fixture | yes | Agent mode can manipulate "local files that are part of the solution" and files in the open solution directory |
| Repository instructions | `.github/copilot-instructions.md`, or `.github/instructions/*.instructions.md` | **Off by default** — you must enable the loading of `.github` instructions in Options |
| Create the output file | yes | Streamed edits; review through **Total changes** and keep or discard |
| Run the build and the check | yes, with confirmation | "Copilot requests confirmation before running a terminal command or using a tool that isn't built in" |
| Open the result in a browser | no browser tool documented | Open the file yourself; use the repo's `browser` command for the assertion |

**Versions.** Agent mode requires **Visual Studio 2022 version 17.14 or later**. The 18.x
versions named in the documentation (18.6 multi-file diff view, 18.11 new chat experience)
are Visual Studio 2026. On 17.14 without agent mode enabled, you still have Copilot Edits.

**Editions.** The documentation states no Community / Professional / Enterprise requirement,
but it does state an admin control: "Administrators control agent mode in Visual Studio by
using the **Editor preview features** flag on the GitHub Copilot dashboard." On a managed
machine, agent mode can be off for you regardless of your subscription.

## Setup

1. Open the **Tún folder as the solution directory**. Two ways:

   - **File → Open → Folder…** and pick the clone. Agent mode's file access is scoped to "the
     open solution directory or its subdirectories"; a folder open gives it the whole tree.
   - Or open a `.sln` that sits inside the clone.

   ```bash
   git clone https://github.com/jkorsvik/tun.git
   ```

   If you cloned elsewhere, open that folder. Cloning is the only terminal step; after that
   Copilot can run the commands.

2. Enable repository instructions. **Tools → Options → All Settings → GitHub → Copilot →
   Copilot Chat** → tick **"Enable custom instructions to be loaded from
   .github/copilot-instructions.md files and added to requests"**. Skip this and your
   instruction file is inert — the single most common reason "the rules did nothing".

3. Add `.github/copilot-instructions.md` in the repository root:

   ```markdown
   # Tún project rules

   - Build artefacts only with `python3 tools/ai_recipe.py build`.
   - Verify with `python3 tools/ai_recipe.py check` before opening a browser.
   - On Windows use `py -3` instead of `python3` (this is a Windows-first repository).
   - Write output only under `work/`.
   - Keep the Origin Notice provenance block in every generated artefact.
   - Do not use the network for this task.
   ```

   For guidance that should apply only to some files, use
   `.github/instructions/tun-recipes.instructions.md` with an `applyTo` frontmatter property
   instead — "Targeted instruction files use the `.instructions.md` extension". The pattern
   is relative to the workspace root.

4. Confirm agent mode is on: the **Enable Agent mode in the chat pane** option must be
   selected. Open Copilot Chat and switch to Agent.

5. **No .NET, MSBuild or C++ dependency.** The Tún tooling is Python and does not care what
   your solution contains. You do not need the C++ workload: `find_symbol` and the C++
   hierarchy tools are extras, not prerequisites for running a Python command.

## The prompt

Paste this into Copilot Chat in **Agent** mode, unchanged:

```text
Work in this repository (the Tún toolkit checkout). Do not use the network.

Read docs/ai-recipes/common-contract.md and docs/ai-recipes/fixtures/excuses.csv first.

1. The fixture has columns Category,Count,Month: Traffic 3, Weather 1, Traffic 2,
   Calendar 4. Count totals 10. It is synthetic example data, safe to read.
2. Build the artefact with the repository's own command, in the terminal:
       py -3 tools/ai_recipe.py build
   (On macOS or Linux: python3 tools/ai_recipe.py build)
3. Verify it:
       py -3 tools/ai_recipe.py check
4. If Playwright and Chromium are already provisioned, run:
       py -3 tools/ai_recipe.py browser
   and confirm the Traffic filter shows 10, then 5, then 10 again on Reset, with no
   console errors and no network requests.
5. Report: the output path, the row count, the traffic total before and after the filter,
   and whether the Origin Notice block is present. Change nothing outside work/.
```

Approve the two terminal commands when it asks. Review the diff under **Total changes**
before keeping it.

## What you should get

Exactly one file: `work/ai-recipes/tun-recipe.html`. All markup, CSS, data and interaction
inlined; no remote resource. `build` takes no arguments and writes there by default; `check`
and `browser` accept one optional HTML path.

Open it from Solution Explorer or Explorer. Your default browser is fine.

## Validate

In the Visual Studio terminal (**View → Terminal**):

```bat
py -3 tools\ai_recipe.py check
py -3 tools\ai_recipe.py browser
```

`check` asserts four rows, total 10, the Origin Notice, and the builder-output and fixture digests. `browser` loads the file over `file://` with remote requests blocked, drives
the filter, and writes a screenshot you should look at.

For a downloaded copy:

```bat
py -3 tools\ai_recipe.py check %USERPROFILE%\Downloads\tun-recipe.html
```

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

- **Instructions silently inert.** The `.github` instructions loader is off by default. If
  Copilot ignores `.github/copilot-instructions.md`, the Options checkbox in step 2 is the
  cause.
- **No `AGENTS.md`.** Unlike VS Code, Cursor, Cline and Roo, Visual Studio does not document
  `AGENTS.md` support. Do not create one here and assume it is read.
- **Agent mode unavailable.** Either the version is below 17.14, the **Enable Agent mode in
  the chat pane** option is off, or an administrator has disabled the Editor preview
  features flag. Without agent mode you can still run the command yourself — it is one line
  — and use Copilot Edits for any edits.
- **Terminal permissions.** Agent mode has "the same permissions as the running Visual
  Studio process". Review proposed commands; do not blanket-allow.
- **No stepwise undo.** "the Visual Studio Copilot agent doesn't support stepwise undo or
  redo" — use **Restore** to a checkpoint, so commit or back up before a large task.
- **Browser verification unavailable** when Playwright + Chromium are not provisioned.
  Blocked, not self-fixing; fall back to `check`.
- **Windows paths.** Use `py -3` and backslashes in `cmd`, or `/` in PowerShell. There is no
  `python3` on a default Windows install.

## Status

**Last product run:** Not run. Commands are the repository's documented ones; capability and
version claims are from Microsoft's published documentation, read 2026-11-18. No end-to-end
run recorded in Visual Studio against this recipe.

**Owner:** Tún maintainers.

**Sources** (vendor documentation, read 2026-11-18):
<https://learn.microsoft.com/en-us/visualstudio/ide/copilot-agent-mode> ·
<https://learn.microsoft.com/en-us/visualstudio/ide/copilot-chat-context> ·
<https://learn.microsoft.com/en-us/visualstudio/intellicode/overview>
