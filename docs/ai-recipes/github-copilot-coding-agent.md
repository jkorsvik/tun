# GitHub Copilot coding agent: issue to reviewable pull request

[Shared fixture, commands and checks](common-contract.md)

**Reader:** user — you want a Tún file produced by the Copilot coding agent and handed back
as a pull request you review and merge yourself, never a push to your branch.

**Owner:** Tún maintainers. **Supported edition:** Copilot coding agent on GitHub, with a
Copilot plan that includes the agent and a repository that grants Copilot write access.
Sessions on GitHub Actions are capped at **59 minutes** and cannot be extended.

**Tier and cost:** Tier 1 dashboard. The agent consumes Copilot premium requests and Actions
minutes. No Tún licence, no admin approval for Tier 1.

## The one thing to decide first: gitignored output cannot be in a PR

`tools/ai_recipe.py build` writes `work/ai-recipes/tun-recipe.html` by default, and **`work/`
is gitignored** in this repository (`.gitignore` line 66). A gitignored file never appears in
`git diff`, never enters a commit, and therefore **never appears in the pull request**. An
agent told to "build the fixture" will produce a file nobody can see.

So the prompt below builds to a **tracked** path instead. The positional argument is
accepted by `check` and `browser`; `build` always writes the default path, so the agent
copies the file afterwards:

```bash
python3 tools/ai_recipe.py build
mkdir -p examples/ai-recipe
cp work/ai-recipes/tun-recipe.html examples/ai-recipe/tun-recipe.html
```

On Windows PowerShell: `py -3 tools/ai_recipe.py build` then
`New-Item -ItemType Directory -Force examples/ai-recipe` and
`Copy-Item work/ai-recipes/tun-recipe.html examples/ai-recipe/tun-recipe.html`.

Only do this when the file is synthetic, as the shared fixture is. **Never commit real
customer data to this repository** — that is a hard rule in `AGENTS.md`, .

## What this environment can and cannot do

| Capability | Here | Note |
|---|---|---|
| Browse the repository and issues | yes | its GitHub MCP access is scoped to the one repository where it works |
| Read repository instructions | yes | `AGENTS.md`, `.github/copilot-instructions.md`, and skills under `.github/skills/` |
| Create and edit files | yes | on its own branch only |
| Run commands, tests, linters | yes | on a GitHub Actions runner or cloud sandbox, in the background |
| Open a real browser | **no** | the agent runs headless on a runner; a Playwright check runs there, but the rendered page is something **you** look at |
| Push to your branch | **no** | it works on one branch and opens **one** pull request per task |
| Merge that pull request | **no** | merging is yours. Agent Merge only keeps *fixing* blockers you select |

## 1. Prepare the repository once

Use an authorised repository that already contains the toolkit and the shared fixture. The agent sees only files available in the repository. If you want it to load `tun-new` as a skill, prepare `.github/skills/tun-new/` from the matching toolkit skill and add it through your normal reviewed change process. No home-directory installer is needed. If you cannot add the skill, tell the agent to read `skills/tun-new/SKILL.md` before running the reference command.

## 2. Open the issue with the whole task in it

The agent works from the issue body and sees nothing of your session. Paste this, with the
repository's own paths:

> **Task: build the Tún reference dashboard and prove it matches.**
>
> Use `tun-new` if it is loaded. Otherwise read `skills/tun-new/SKILL.md`.
>
> 1. Build the synthetic fixture `docs/ai-recipes/fixtures/excuses.csv` (four rows,
>    Category/Count/Month, total 10) by running `python3 tools/ai_recipe.py build`. Do not
>    hand-write the HTML and do not substitute a chart library — the command calls Tún's
>    own builder.
> 2. Copy `work/ai-recipes/tun-recipe.html` to `examples/ai-recipe/tun-recipe.html`, because
>    `work/` is gitignored. This is synthetic data only. Do not add any other file.
> 3. Run `python3 tools/ai_recipe.py check examples/ai-recipe/tun-recipe.html` and paste
>    the output into the pull request description verbatim.
> 4. Run `python3 tools/ai_recipe.py browser examples/ai-recipe/tun-recipe.html`. If
>    Playwright or Chromium is missing, write **"browser check: not run"** and say exactly
>    what was missing. Do not claim it passed.
> 5. Open one pull request against `main`. Do not merge it, do not force-push, and do not
>    change any file outside `examples/ai-recipe/`.
>
> In the pull request description state: the four rows and the total of 10, that the Origin
> Notice line `Made with   : Tún — tun.community` is present, which checks passed, which
> were not run, and that a human must still open the file in a browser.

**Minimal permissions.** Use an existing Copilot entitlement and approve only the repository access needed to create a draft PR. Keep protection, rulesets and secrets unchanged. If the organisation does not allow assignment, run the same commands in a local checkout and submit the result through the usual review process.

Then assign the issue to Copilot. It creates a branch, opens a **draft** pull request, and
works in the background while you do something else.

## 3. Review the diff, not the summary

An agent's written summary costs it nothing to produce. Open the **Files changed** tab and
check the diff yourself:

- **New files only.** Exactly `examples/ai-recipe/tun-recipe.html`. Any change to `tools/`,
  `templates/` or `setup.py` is out of scope — reject it.
- **One file, self-contained.** No `src/`, no `node_modules`, no `package.json`. The whole
  point is one HTML file with the data inlined.
- **Provenance present.** Search the file for `PROVENANCE` and
  `Made with   : Tún — tun.community`. Both must be there.
- **The numbers.** Open the file and look: Traffic 5, Weather 1, Calendar 4, total 10.
  Filtering to Traffic gives 5; Reset returns 10.
- **No secrets, no private paths.** No tokens, no `~/…` paths from someone's laptop.

If CI exists on this repository it runs on the pull request; a green check there is
evidence the workflow passed, **not** that the file renders correctly. The Tún verifier's
own rule is that a clean build is not evidence.

## 4. What the agent proves, and what you still prove

The agent can prove: the canonical build is reproducible (`check` compares the HTML content
against a fresh build), the provenance and Origin Notice are present, and four rows total
10. That is structural.

You still prove: that the page looks right. Download the pull request's file, open it in
your browser, and look at it. If you want the automated browser layer, run it on your own
machine after checkout:

```bash
uv sync --extra verify && uv run playwright install chromium
uv run --extra verify python tools/ai_recipe.py browser examples/ai-recipe/tun-recipe.html
```

## Data boundaries

The shared fixture is synthetic: four rows, no people, no customer. That is the only reason
its output may be committed. If you point the agent at anything else, the answer is a build
whose output stays **out** of Git and reaches the audience through a folder whose
permissions already match — one file per audience, never a filter in a shared file.

## Handoff

Merge when the diff is what you asked for and you have looked at the file. The merged
`examples/ai-recipe/tun-recipe.html` is then a repository artefact others can download
directly — direct download and open is the supported route. A SharePoint or OneDrive
**attachment** preview is not: it runs without JavaScript and shows a still frame. Share a
link to the file, or hand over the file itself.

## Recovery

| Symptom | Cause | Fix |
|---|---|---|
| Pull request has no HTML file | it built into gitignored `work/` | re-issue with the explicit `cp` step; `git check-ignore -v work/ai-recipes/tun-recipe.html` confirms the cause |
| Agent edits `tools/` or `templates/` | out-of-scope wandering | close the pull request; restate "change no file outside `examples/ai-recipe/`" |
| No pull request appears | ruleset or branch protection blocking it, or Copilot lacks write access | check repository rules and Copilot's access; do not silently grant a bypass |
| Session stopped mid-task | the 59-minute Actions cap | split the task; the cap cannot be extended |
| `check` fails in CI but passed locally | different builder version or the fixture was edited | re-run the build; never patch the HTML by hand |
| "browser check: not run" in the description | Playwright/Chromium absent on the runner | that is the honest answer; run the browser layer locally |

## Evidence for this page

- **Last product test: Not run.** Written from official GitHub documentation and from
  reading the Tún launcher and `.gitignore`. I did not assign an issue to Copilot, so I have
  no first-hand pull request to point at.
- Documentation inspection is not a product test. The gitignored-output consequence was
  verified locally: `git check-ignore -v work/ai-recipes/tun-recipe.html` reports
  `.gitignore:66:work/`. `build` and `check` were run against the recipe draft based on `bf92fd7` on macOS
  27.0.1, Python 3.14.6, 2026-11-18; `browser` was blocked for missing Playwright.
- Vendor pages read 2026-11-18: GitHub *About Copilot coding agent*
  (<https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent>) for
  the one-branch/one-pull-request rule, write-access requirement, ruleset blocking and the
  59-minute cap; *Adding agent skills for Copilot*
  (<https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills>)
  for `.github/skills/`; Copilot CLI *delegate tasks* for the draft-pull-request flow.
- These docs describe the agent's documented behaviour. Where GitHub's own text did not
  state a thing — for instance an explicit "the agent cannot merge" sentence — this page
  says what the documents *do* support and does not invent the rest.
