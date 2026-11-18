# Claude Code: build the reference file

[Shared fixture, commands and checks](common-contract.md)

**Reader:** user — you have Claude Code in a terminal and want a Tún file from the shared
fixture, with a verification step you can trust.

**Owner:** Tún maintainers. **Supported version:** Claude Code with Agent Skills support —
`claude --version` reports 2.1.327 on the machine this was written on, which shows the CLI is
installed, not that it is a proven minimum. Two documented version floors matter for edge
cases: `/add-dir` skill loading needs 2.1.257+, and claude.ai skill syncing needs 2.1.273+.

**Tier and cost:** Tier 1 dashboard, no licence, no admin approval. Skills are copied; the
build needs no package installation.

## What this environment can and cannot do

| Capability | Here | Note |
|---|---|---|
| Browse the public docs | **no browser by default** | it can fetch a URL, but it does not browse for you unless a browser tool is enabled |
| Read repository instructions | yes | `CLAUDE.md`, `AGENTS.md`, `.claude/rules/`, and skills |
| Create files | yes | it edits the working tree directly, showing each change for approval |
| Run commands | yes | each command is approved, or covered by your allowlist |
| Open a real browser and verify | **yes, if Playwright is installed** | it can run the Chromium check; it cannot judge the rendered page |

The render judgement stays with you. That is the rule this whole project is built on: a
clean build is not evidence.

## 1. Get the toolkit

Clone or download **Code → Download ZIP** as shown in [Get the toolkit](../../INSTALL.md#get-the-toolkit), then start
Claude Code **in the folder that contains `setup.py`**. Project skills load from where you
start and from every parent directory up to the repository root, so starting in the toolkit
root is correct.

```bash
cd path/to/tun
claude
```

## 2. Copy the Tún skills (one command)

There are two routes. Pick one; installing both makes every skill appear twice.

**Recommended — personal, available in every project.** From a shell, not inside Claude
Code:

```bash
python3 setup.py --install --tool claude --check
```

Windows PowerShell: `py -3 setup.py --install --tool claude --check`.

`--check` writes nothing and lists each skill as match or missing. Drop `--check` to copy
into `~/.claude/skills`. `--install` copies only the Tún `tun-*` skills and never replaces
an existing path; it prints the path of any copy it left alone, so nothing of yours is
deleted.

**Project-local — only in this checkout.** Claude Code reads `.claude/skills/` in the
repository, which is the folder to use when the skills should travel with the project:

```bash
mkdir -p .claude/skills && cp -R skills/tun-* .claude/skills/
```

Do not put this in a commit unless the project wants every contributor to have it.

### Load-bearing caveat

`~/.claude/skills` is read by Claude Code's **personal** tier. When both a personal and a
project skill share a name, **personal wins** — a stale copy in your home folder silently
shadows a corrected one in the repository. If a skill behaves oddly after a pull, run the
`--check` above; it is exactly the drift it reports.

Skills are copied, not symlinked, on purpose: a symlink makes `~/.claude/skills/<name>` the
same file as a tracked file, so editing a skill edits the checkout on whatever branch is
open. `setup.py --link` exists for authors, and is the wrong choice here.

## 3. Confirm the skills loaded

Inside Claude Code:

```
/skills
```

You should see `tun-new`, `tun-verify`, `tun-help` and the rest. Then check it really
applies — a listing only proves discovery:

```
/tun-help
```

If a skill is missing: confirm the folder name matches the `name:` frontmatter, and if you
created the skills folder during the session, run `/reload-skills`. Edits under
`~/.claude/skills` and the project `.claude/skills` are picked up live; a brand-new top-level
folder is not.

## 4. Build the reference file

Paste this as one message:

> Use the `tun-new` skill from this toolkit. Build the shared recipe fixture
> `docs/ai-recipes/fixtures/excuses.csv` — four synthetic rows, Category/Count/Month, total
> 10 — into `work/ai-recipes/tun-recipe.html` by running
> `python3 tools/ai_recipe.py build`. Do not hand-write the HTML and do not substitute a
> generic chart library; that command calls Tún's own builder and is the only thing whose
> output counts.
>
> Then run `python3 tools/ai_recipe.py check` and paste the output verbatim. Then run
> `python3 tools/ai_recipe.py browser` and tell me plainly whether it passed, was blocked
> for a missing Playwright or Chromium, or failed — do not describe a blocked check as a
> pass. Touch no file outside `work/`.

## 5. Verify before you trust the file

**Layer 1 — built.** `Built …` means one file exists. Nothing about correctness.

**Layer 2 — canonical.** `check` rebuilds in a temp folder and compares the HTML content, then
confirms the provenance and Origin Notice:

```
Static PASS: 4 rows, total 10, exact canonical content and Origin Notice. Browser not checked by this step.
```

**Layer 3 — browser.** Provision once, then check:

```bash
uv sync --extra verify && uv run playwright install chromium
uv run --extra verify python tools/ai_recipe.py browser
```

```
Browser PASS: Chromium file:// offline, filter and reset work, zero external requests and errors. Inspect …/tun-recipe.verify.png before sharing.
```

What that proves: the file opens from `file://` with no network, the Category filter takes
the total from 10 to 5, Reset returns it to 10, and there are zero page errors and zero
external requests. What it does not prove: that it looks good. Open the PNG, and open the
file in your own browser. Check four rows — Traffic 5, Weather 1, Calendar 4 — total 10, no
overlapping labels.

If `browser` prints `Browser check blocked`, Playwright or Chromium is missing. That is
**Not run**. Say so.

## What the file promises

A **Tier 1 portable dashboard**: one self-contained HTML file, data inlined, no server, no
CDN, offline-capable, opens from a synced SharePoint or OneDrive folder. The provenance
block records source, extract time, build time, requester, builder and row count, and carries
the **Origin Notice** `Made with   : Tún — tun.community`. The licence lets you convey the
document under your own terms **provided that notice is preserved** — do not strip it.

## Data boundaries

The fixture is synthetic: four rows, no people. For real data, the boundary is the folder,
not a filter: **everyone who can open the file reads every row.** Different audiences get
different files in different folders, split before the build.

## Handoff

Hand over the file or a link to it. Direct download and open is the reliable route; a
SharePoint or OneDrive **attachment** preview blocks JavaScript and shows a still frame.
Do not wrap the result in a server or a hosted app.

## Recovery

| Symptom | Cause | Fix |
|---|---|---|
| `/skills` does not list `tun-new` | not copied, wrong tier, or name/folder mismatch | re-run `--install --tool claude --check`; verify frontmatter `name:` equals the folder |
| A skill seems old | a personal copy shadows the project one | `--check` reports the drift; follow the backup steps in [Install and use Tún](../../INSTALL.md#copy-tun-skills-to-your-assistant) |
| New skills folder ignored | created after the session started | `/reload-skills` |
| Claude writes its own HTML | the skill was not selected | restate "run the command"; a hand-written file fails `check` byte comparison |
| `check` fails | different builder or edited fixture | rebuild; never patch the HTML |
| `browser` blocked | no Playwright/Chromium | run the two `uv` lines; until then it is Not run |

## Evidence for this page

- **Last product test: Not run.** Written from Anthropic's official Claude Code documentation
  and from reading this repository's `setup.py` and `tools/ai_recipe.py`. I did not drive
  Claude Code through this recipe.
- Documentation inspection is not a product test. `claude --version` reports 2.1.327 here,
  which shows the CLI is installed — not that a skill-loaded build works.
- Tún commands run 2026-11-18 on macOS 27.0.1, Python 3.14.6, the recipe draft based on `bf92fd7`:
  `python3 tools/ai_recipe.py build` → `Built …`; `check` → `Static PASS: 4 rows, total 10,
  exact canonical content and Origin Notice`; `browser` → `Browser check blocked: provision
  Playwright and Chromium`. `python3 setup.py --install --tool claude --check` ran read-only
  and listed every Tún skill as not installed, which is the documented `--check` behaviour.
- Vendor page read 2026-11-18: Claude Code *Skills*
  (<https://docs.claude.com/en/docs/claude-code/skills>) for the tiers, personal-over-project
  precedence, `/skills`, `/reload-skills` and the symlink rule.
