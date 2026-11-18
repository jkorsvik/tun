# OpenAI Codex CLI: build the reference file

[Shared fixture, commands and checks](common-contract.md)

**Reader:** user — you have Codex CLI in a terminal and want a Tún file from the shared
fixture, without giving the agent more access than the job needs.

**Owner:** Tún maintainers. **Supported version:** Codex CLI with Agent Skills support —
the feature is current in this CLI, and `codex --version` reports `codex-cli 0.148.0` on the
machine this was written on. That is the observed version, not a proven minimum. On Linux
and WSL2 the sandbox needs `bubblewrap` installed first; on macOS it uses Seatbelt out of the
box, and on Windows PowerShell the native Windows sandbox.

**Tier and cost:** Tier 1 dashboard, no licence, no admin approval. Building needs no
network, so it fits inside the default sandbox.

## What this environment can and cannot do

| Capability | Here | Note |
|---|---|---|
| Browse the public docs | **no** | the default sandbox has no network; it reads what is on disk |
| Read repository instructions | yes | `AGENTS.md` at the root and in parent folders, plus skills |
| Create files | yes | inside the workspace sandbox boundary; `.git`, `.agents`, `.codex` stay read-only |
| Run commands | yes | inside the sandbox; anything beyond it triggers the approval flow |
| Open a real browser | **no** | headless only; the render judgement is yours |

The network being off by default is a **feature** here, not an obstacle: the build inlines
the data and fetches nothing. Do not reach for `:danger-full-access` to "make it work" — if
this recipe needs the open network, something is wrong with the recipe.

## 1. Get the toolkit

Clone or download **Code → Download ZIP** as shown in [Get the toolkit](../../INSTALL.md#get-the-toolkit) and open the
folder that contains `setup.py`:

```bash
cd path/to/tun
codex
```

Codex is a reader of the open Agent Skills format and loads **repo** skills from
`.agents/skills` and **personal** skills from `~/.agents/skills`. Codex also keeps its own
home at `~/.codex/` for config and `AGENTS.md`; skills are not read from there.

## 2. Copy the Tún skills (one command)

From a shell, not inside Codex:

```bash
python3 setup.py --install --tool agents --check
```

Windows PowerShell: `py -3 setup.py --install --tool agents --check`.

`--check` writes nothing and lists each skill as match or missing. Drop `--check` to copy the
Tún `tun-*` skills into `~/.agents/skills` — the folder Codex reads for personal skills.
`--install` never replaces an existing path; it reports any copy it left alone instead of
deleting something of yours.

**Project-local alternative.** If the skills should live with the checkout rather than in
your home folder, copy them into the repository:

```bash
mkdir -p .agents/skills && cp -R skills/tun-* .agents/skills/
```

Then commit it only if the project wants every contributor to have it. Choose one route:
skills in both places appear twice and it is not obvious which the model picked.

## 3. Confirm the skills loaded

Inside Codex:

```
/skills
```

The list shows each skill's name and path. That proves discovery. To prove the workflow
applies, invoke it explicitly: type `$` and pick `tun-new`, or run `/skills` and choose it.

Codex budgets its initial skills list to about 2% of the context window and shortens
descriptions first when there are many skills. A long list therefore does not guarantee every
skill is described in full; `skills.max_context_tokens` raises the budget (up to 10,000
tokens) if the Tún skills get crowded out.

## 4. Build the reference file

Paste this as one message:

> Use the `tun-new` skill in this repository. Build the shared recipe fixture
> `docs/ai-recipes/fixtures/excuses.csv` — four synthetic rows, Category/Count/Month, total
> 10 — into `work/ai-recipes/tun-recipe.html` by running
> `python3 tools/ai_recipe.py build` (on Windows, `py -3 tools/ai_recipe.py build`). Do not
> hand-write the HTML and do not substitute a generic chart library; that command calls Tún's
> own builder.
>
> Then run `python3 tools/ai_recipe.py check` and paste the output verbatim. Then run
> `python3 tools/ai_recipe.py browser` and say plainly whether it passed, was blocked for a
> missing Playwright or Chromium, or failed — a blocked check is not a pass. Change no file
> outside `work/`. You do not need network access for any of this; stay inside the sandbox.

If Codex asks for approval to run a `python3` command, approve it — that is the sandbox
boundary doing its job, not a sign of trouble. Do not answer by switching to full access.

## 5. Verify before you trust the file

**Layer 1 — built.** `Built …` means one file exists.

**Layer 2 — canonical.** `check` rebuilds in a temp folder and compares the HTML content, then
confirms the provenance block and the Origin Notice:

```
Static PASS: 4 rows, total 10, exact canonical content and Origin Notice. Browser not checked by this step.
```

**Layer 3 — browser.** Run this **outside** the sandbox, because the browser check launches a
real Chromium:

```bash
uv sync --extra verify && uv run playwright install chromium
uv run --extra verify python tools/ai_recipe.py browser
```

```
Browser PASS: Chromium file:// offline, filter and reset work, zero external requests and errors. Inspect …/tun-recipe.verify.png before sharing.
```

The browser check proves the file opens offline from `file://`, filtering to Traffic takes
the total from 10 to 5, Reset returns it to 10, and there are zero page errors and zero
external requests. It does not prove the page looks right. Open the PNG and the HTML
yourself: rows Traffic 5, Weather 1, Calendar 4, total 10, no overlapping labels.

If it prints `Browser check blocked`, Playwright or Chromium is missing: **Not run**.

## What the file promises

A **Tier 1 portable dashboard**: one self-contained HTML file, data inlined, no server, no
CDN, works offline and from a synced SharePoint or OneDrive folder. The provenance block
records source, extract and build times, requester, builder and row count, and ends with the
**Origin Notice** `Made with   : Tún — tun.community`. Documents built with Tún may be
conveyed under your own terms **provided that notice is preserved**.

## Data boundaries

The fixture is synthetic: four rows, no people. For real data the folder is the boundary:
everyone who can open the file reads every row, so separate audiences get separate files
built from separate extracts, never one file with a filter.

## Handoff

Hand over the file or a link to it. Direct download and open works; a SharePoint or OneDrive
**attachment** preview blocks JavaScript and shows a still frame. Do not convert the result
into a hosted app.

## Recovery

| Symptom | Cause | Fix |
|---|---|---|
| `tun-new` absent from `/skills` | not copied, or copied to a folder Codex does not read | re-run `--install --tool agents --check`; Codex reads `~/.agents/skills` and `.agents/skills`, not `~/.codex/skills` |
| Skill list looks truncated | many installed skills, 2% context budget | raise `skills.max_context_tokens`; invoke with `$` explicitly |
| Command refused | sandbox boundary | approve it; do not switch to `:danger-full-access` |
| `bubblewrap` warning on Linux | sandbox prerequisite | install `bubblewrap` from your package manager |
| Codex writes its own HTML | the skill was not selected | restate "run the command"; hand-written output fails the byte comparison |
| `check` fails | different builder or edited fixture | rebuild; never patch the HTML by hand |
| `browser` blocked | no Playwright/Chromium, or run inside the sandbox | provision outside, then run outside; otherwise it is Not run |

## Evidence for this page

- **Last product test: Not run.** Written from OpenAI's official Codex documentation and
  from reading this repository's `setup.py` and `tools/ai_recipe.py`. I did not drive Codex
  through this recipe.
- Documentation inspection is not a product test. `codex --version` reports `codex-cli
  0.148.0` here, which shows the CLI is installed — nothing more.
- Tún commands run 2026-11-18 on macOS 27.0.1, Python 3.14.6, the recipe draft based on `bf92fd7`:
  `build` → `Built …`; `check` → `Static PASS: 4 rows, total 10, exact canonical content and
  Origin Notice`; `browser` → `Browser check blocked: provision Playwright and Chromium`.
- Vendor pages read 2026-11-18: *Customization overview*
  (<https://learn.chatgpt.com/docs/customization/overview.md>) for `~/.agents/skills` and
  repo `.agents/skills`; *Build skills* (<https://learn.chatgpt.com/docs/build-skills.md>)
  for `/skills`, `$`, and `skills.max_context_tokens`; *Sandbox*
  (<https://learn.chatgpt.com/docs/sandboxing.md>) for the default boundary, Seatbelt on
  macOS, `bubblewrap` on Linux and the Windows sandbox; *Permissions*
  (<https://learn.chatgpt.com/docs/permissions.md>) for `:read-only` and
  `:danger-full-access`.
