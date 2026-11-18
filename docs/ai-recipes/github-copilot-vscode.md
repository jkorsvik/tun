# GitHub Copilot in VS Code: build the reference file

[Shared fixture, commands and checks](common-contract.md)

**Reader:** user — you want one Tún file out of the shared fixture, and you have Copilot
in VS Code. No repository changes, no account beyond the Copilot subscription you already
have.

**Owner:** Tún maintainers. **Supported version:** VS Code with GitHub Copilot Chat, running
the **Copilot harness**. Microsoft's docs do not pin a minimum VS Code version for Agent
Skills on the page I read, so this recipe does not claim one: check **Help → About** and
whether **Chat: Open Customizations** offers a `Skills` tab — if it does, the feature is
present. The deprecated **Local** harness has different skill folders and is removed in
February 2027 (see step 2).

**Tier and cost:** Tier 1 dashboard, no licence and no admin approval. Copying Tún skills
costs one command; building and checking costs nothing.

## What this environment can and cannot do

| Capability | Here | Note |
|---|---|---|
| Browse the public docs | yes | Copilot Chat can read `tun.community` and the repository |
| Read repository instructions | yes | `.github/copilot-instructions.md`, `AGENTS.md`; skills by folder |
| Create files in the workspace | yes | in agent mode, with your approval per tool call |
| Run terminal commands | yes | agent mode asks before each command; you approve |
| Open a real browser and verify | **partly** | it can run a headless Chromium check through Playwright **if Playwright and Chromium are already installed**. It cannot see the rendered page the way you can |

The last row is the one people get wrong. A passing headless check is not the same as a
person looking at the file. Both are needed; see [Verify](#5-verify-before-you-trust-the-file).

## 1. Get the toolkit

Download **Code → Download ZIP** as shown in [Get the toolkit](../../INSTALL.md#get-the-toolkit) and extract it, or
clone it. Open the folder that contains `setup.py` in VS Code. The toolkit is imported
already: no Node, no server, no pip.

## 2. Make the skills visible in VS Code

In the toolkit folder, copy the `skills/tun-*` folders into `.github/skills/` using your file manager. Create the destination if needed. Skip any folder that already exists instead of merging or replacing it. Each copied skill must have its own `SKILL.md`.

The current Copilot harness reads `.github/skills/`. Its personal location is `~/.copilot/skills/`, not `~/.agents/skills/`. Use one location, not both. If you cannot copy skills, open Agent mode and run the reference commands in the integrated terminal instead.

## 3. Confirm the skills loaded

Start a fresh chat, choose the **Copilot** harness, and type:

```
/skills
```

You should see `tun-new`, `tun-verify`, `tun-help` and the rest. Alternatively type `/` and
look for `tun-new`. If a skill is missing, its `name` frontmatter does not match its folder
name, or it is in a folder this harness does not read (previous section).

A skill appearing in the menu proves it was **discovered**. It does not prove Copilot will
choose it, and it is not evidence that the skill runs correctly.

## 4. Build the reference file

Paste this as one message, in **agent mode** (the mode that may edit files and run
commands; ask mode cannot write):

> In this repository, use the `tun-new` skill. Build the shared recipe fixture at
> `docs/ai-recipes/fixtures/excuses.csv` (four rows, synthetic: Category, Count, Month;
> total 10) into `work/ai-recipes/tun-recipe.html` by running
> `python3 tools/ai_recipe.py build` (`py -3 tools/ai_recipe.py build` on Windows).
> Do not hand-write the HTML and do not substitute a generic chart library; the command
> calls Tún's own builder. Then run `python3 tools/ai_recipe.py check` and paste its
> output verbatim. Then run `python3 tools/ai_recipe.py browser` and tell me honestly
> whether it passed, was blocked for a missing Playwright or Chromium, or failed.
> Do not change any file outside `work/`.

Approve the terminal commands. The build writes exactly one file.

## 5. Verify before you trust the file

Three layers, and they prove different things. Do not let one stand in for another.

**Layer 1 — did it build?** The build command printing `Built …` means a file exists. It
says nothing about whether the numbers are right.

**Layer 2 — is it the canonical file?** `check` re-builds the reference in a temporary
folder and compares the HTML content, then confirms the Origin Notice. Success looks like:

```
Static PASS: 4 rows, total 10, exact canonical content and Origin Notice. Browser not checked by this step.
```

**Layer 3 — does it work in a browser?**

```bash
uv sync --extra verify && uv run playwright install chromium
uv run python tools/ai_recipe.py browser
```

Expected:

```
Browser PASS: Chromium file:// offline, filter and reset work, zero external requests and errors. Inspect …/tun-recipe.verify.png before sharing.
```

If Playwright is missing, `browser` fails with `Browser check blocked` rather than
pretending to pass. That is a **Not run**, not a pass. Report it as Not run.

**Still yours to do:** open the PNG it wrote, and open `work/ai-recipes/tun-recipe.html` in
your own browser. Confirm the four rows read Traffic 5, Weather 1, Calendar 4; the total
reads 10; the Category filter to Traffic gives 5; Reset returns 10; nothing overlaps and
the colours are the Tún palette. No automated check replaces this.

## What the file promises

The file is a **Tier 1 portable dashboard**: one HTML file, all data inlined, no server, no
CDN, works offline and from a SharePoint or OneDrive folder. Recipients need nothing
installed.

The provenance block at the top records source data, extract time, build time, requester,
the Tún builder, and the row count, and ends with the **Origin Notice** line
`Made with   : Tún — tun.community`. The licence asks you to preserve it: documents built
with Tún may be conveyed under terms of your choice **provided the Origin Notice is
preserved**. Do not delete it to make a file look in-house.

## Data boundaries

The fixture is synthetic: four rows, no people. If you swap in real data remember the rule
that does not bend: **everyone who can open the file can read every row in it.** There is no
row-level security. If different audiences need different rows, build one file per audience
and let folder permissions do the splitting — never a filter in a shared file.

## Handoff

The file is the deliverable. Put it in the folder whose existing permissions match its
audience, and share the **link**, not the attachment: a SharePoint or OneDrive attachment
preview runs in a sandbox that refuses JavaScript, so the recipient sees a still frame or a
blank page while you see a working dashboard. The download-and-open route is the fallback,
not the default.

Do not turn it into a hosted app. If the answer needs a server, it is the wrong answer.

## Recovery

| Symptom | Cause | Fix |
|---|---|---|
| `tun-new` not in `/skills` | wrong harness folder, or name/folder mismatch | use the path in step 2; check that `name:` matches the folder |
| Copilot writes its own HTML | it ignored the skill and free-styled | re-state "run the command, do not hand-write the HTML"; a file that is not identical in content to the canonical build makes `check` fail |
| `check` says "Not the canonical file" | different builder version or fixture edited | rebuild with the command; do not patch the HTML by hand |
| `browser` says blocked | Playwright or Chromium not installed | run the two `uv` lines; report Not run until they pass |
| Everything passes but the page looks wrong | assertions cannot see layout | open the PNG and the file yourself; this is the check that catches it |

## Evidence for this page

- **Last product test: Not run.** This recipe was written from official vendor
  documentation and from reading the Tún launcher's source. I did not install and drive
  Copilot in VS Code, so I have no first-hand result for it.
- Documentation inspection is not a product test. The commands, paths and flags here were
  checked against the code in this repository (`setup.py --install`, `tools/ai_recipe.py`);
  the behaviour of Copilot itself is quoted from Microsoft's and GitHub's docs, not observed.
- Vendor pages read 2026-11-18: VS Code Agent Skills
  (<https://code.visualstudio.com/docs/agent-customization/agent-skills>) for the harness
  and folder tables; GitHub, *Adding agent skills for Copilot*
  (<https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills>)
  for the cloud agent's folders.
- The Tún commands in this page were run on macOS 27.0.1 with Python 3.14.6 against
  recipe draft based on `bf92fd7`, 2026-11-18: `build` and `check` passed; `browser` returned
  `Browser check blocked` because Playwright is not installed here, which is why browser
  verification is documented as **Not run**.
