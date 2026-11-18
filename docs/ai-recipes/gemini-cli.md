# Gemini CLI: build the reference file

[Shared fixture, commands and checks](common-contract.md)

**Reader:** user — you have Gemini CLI in a terminal and want a Tún file from the shared
fixture, with an approval step you are aware of.

**Owner:** Tún maintainers. **Supported version:** Gemini CLI with Agent Skills support —
`gemini --version` reports `0.46.0` on the machine this was written on. That is the observed
version, not a proven minimum. The `activate_skill` tool and the `~/.agents/skills` alias are
documented current features.

**Tier and cost:** Tier 1 dashboard, no licence, no admin approval. Skills are copied; the
build needs no package installation.

## What this environment can and cannot do

| Capability | Here | Note |
|---|---|---|
| Browse the public docs | **no** | it reads what is on disk and what you paste |
| Read repository instructions | yes | `GEMINI.md` for durable context, plus skills |
| Create files | yes | within the workspace; skill folders are added to allowed paths on activation |
| Run commands | yes | shell commands prompt for approval unless allowed |
| Open a real browser | **no** | headless only; the render judgement is yours |

One behaviour is specific to this CLI and worth expecting: skills do not auto-load silently.
When Gemini picks one it calls an `activate_skill` tool, and **you** see a confirmation
prompt naming the skill, its purpose and the directory it will gain read access to. Approving
grants the skill's folder to the agent's allowed paths.

## 1. Get the toolkit

Clone or download **Code → Download ZIP** as shown in [Get the toolkit](../../INSTALL.md#get-the-toolkit) and open the
folder that contains `setup.py`:

```bash
cd path/to/tun
gemini
```

Gemini CLI discovers skills in this order, lowest to highest precedence: built-in, extension,
**user** (`~/.gemini/skills/` or the `~/.agents/skills/` alias), then **workspace**
(`.gemini/skills/` or `.agents/skills/`). Within a tier the `.agents/skills/` alias wins over
the `.gemini/skills/` directory.

## 2. Copy the Tún skills (one command)

From a shell, not inside Gemini CLI:

```bash
python3 setup.py --install --tool agents --check
```

Windows PowerShell: `py -3 setup.py --install --tool agents --check`.

`--check` writes nothing and lists each skill as match or missing. Drop `--check` to copy the
Tún `tun-*` skills into `~/.agents/skills` — the documented user alias Gemini CLI reads.
`--install` never replaces an existing path; it reports any copy it left alone.

**Project-local alternative**, if the skills should travel with the checkout:

```bash
mkdir -p .agents/skills && cp -R skills/tun-* .agents/skills/
```

Workspace skills take precedence over user skills of the same name, so a corrected project
copy beats a stale home copy — the opposite of the shadowing trap in some other tools. Commit
it only if the team wants it. Pick one route; both makes every skill appear twice.

## 3. Confirm the skills loaded

Inside Gemini CLI:

```
/skills list
```

(It is a subcommand — a bare `/skills` only shows the help.) You should see `tun-new`,
`tun-verify`, `tun-help` and the rest with their descriptions. Add `all` to include built-in
skills, or `nodesc` to drop descriptions. That proves discovery — the names and descriptions
are injected into the system prompt at session start. It does not prove activation: the first
time Gemini uses one it calls `activate_skill` and asks for consent (see above), and only
after you approve does the `SKILL.md` body load.

If a skill is missing, check that its folder name matches the `name:` frontmatter and that it
sits in one of the four discovery locations above; `/skills reload` refreshes the list.

The same list is available outside a session:

```bash
gemini skills list --all
```

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
> outside `work/`.

Approve the skill activation prompt when it appears, and approve the `python3` commands.

## 5. Verify before you trust the file

**Layer 1 — built.** `Built …` means one file exists.

**Layer 2 — canonical.** `check` rebuilds in a temp folder and compares the HTML content, then
confirms the provenance block and Origin Notice:

```
Static PASS: 4 rows, total 10, exact canonical content and Origin Notice. Browser not checked by this step.
```

**Layer 3 — browser.**

```bash
uv sync --extra verify && uv run playwright install chromium
uv run python tools/ai_recipe.py browser
```

```
Browser PASS: Chromium file:// offline, filter and reset work, zero external requests and errors. Inspect …/tun-recipe.verify.png before sharing.
```

That proves the file opens offline from `file://`, filtering to Traffic takes the total from
10 to 5, Reset returns it to 10, and there are zero page errors and zero external requests.
It does not prove the page looks right. Open the PNG and the HTML yourself and check: four
rows — Traffic 5, Weather 1, Calendar 4 — total 10, no overlapping labels.

If it prints `Browser check blocked`, Playwright or Chromium is missing: **Not run**. Say so
rather than counting it as a pass.

## What the file promises

A **Tier 1 portable dashboard**: one self-contained HTML file, data inlined, no server, no
CDN, offline-capable, opens from a synced SharePoint or OneDrive folder. The provenance block
records source, extract and build times, requester, builder and row count, and ends with the
**Origin Notice** `Made with   : Tún — tun.community`. Documents built with Tún may be
conveyed under your own terms **provided that notice is preserved**.

## Data boundaries

The fixture is synthetic: four rows, no people. With real data, the folder is the boundary and
there is no row-level security: everyone who can open the file reads every row. Different
audiences get different files, split before the build.

## Handoff

Hand over the file or a link to it. Direct download and open works; a SharePoint or OneDrive
**attachment** preview blocks JavaScript and shows a still frame. Do not turn the result into
a hosted app.

## Recovery

| Symptom | Cause | Fix |
|---|---|---|
| `tun-new` absent from `/skills` | not copied, or wrong folder | re-run `--install --tool agents --check`; needs `~/.agents/skills`, `~/.gemini/skills`, `.agents/skills` or `.gemini/skills` |
| Consent prompt keeps appearing | new session per use | expected: consent is per activation unless you approve persistently |
| Skill loaded but ignored | description mismatch or a competing copy | the higher-precedence copy wins; check both locations |
| Gemini writes its own HTML | the skill was not activated | restate "run the command"; hand-written output fails the byte comparison |
| `check` fails | different builder or edited fixture | rebuild; never patch the HTML by hand |
| `browser` blocked | no Playwright/Chromium | run the two `uv` lines; until then it is Not run |

## Evidence for this page

- **Last product test: Not run.** Written from Google's official Gemini CLI documentation and
  from reading this repository's `setup.py` and `tools/ai_recipe.py`. I did not drive Gemini
  CLI through this recipe.
- Documentation inspection is not a product test. `gemini --version` reports `0.46.0` here,
  which shows the CLI is installed — nothing more.
- Tún commands run 2026-11-18 on macOS 27.0.1, Python 3.14.6, the recipe draft based on `bf92fd7`:
  `build` → `Built …`; `check` → `Static PASS: 4 rows, total 10, exact canonical content and
  Origin Notice`; `browser` → `Browser check blocked: provision Playwright and Chromium`.
- Vendor page read 2026-11-18: Gemini CLI *Agent Skills*
  (<https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/skills.md>) for the
  discovery tiers, the `.agents/skills` alias and the `activate_skill` consent flow.
