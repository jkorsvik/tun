# Toolchain — Skills, MCP Servers and CLI Tools

Everything RAIWork needs to work smoothly on this repo, and **why** each item is here.
Run `python3 setup.py` to check your machine against this list.

Nothing on the required list is exotic. The Tier 1 path deliberately has no build
toolchain — see rule 5 in [`../AGENTS.md`](../AGENTS.md).

---

## TL;DR — the minimum that works

| | What | Why |
|---|---|---|
| **1 MCP server** | `ms365` | this *is* the SharePoint/OneDrive backend — upload, permissions, share links |
| **2 CLI tools** | `python3`, `playwright` + chromium | build the dashboard; prove it renders |
| **6 skills** | this repo's `skills/` | the workflow itself |
| **1 skill** | `xlsx` (marketplace) | because real data arrives as Excel |

Everything else below is optional and clearly marked.

---

## MCP servers

MCP servers are what let RAIWork touch real systems. Check what you have:

```bash
raiwork mcp list
```

You want to see `authenticated` (or `refresh ready`) next to the ones marked
**required** below.

### `ms365` — REQUIRED

**The whole SharePoint/OneDrive half of this project runs through here.** Without it,
RAIWork can build a dashboard but cannot publish one.

Used for:
- `list-drives`, `search-sharepoint-sites` — find the right library
- `upload-file-content` — publish the dashboard
- `list-drive-item-permissions` — **confirm who can actually see it** before sharing
- `create-drive-item-share-link` — produce the link
- `list-users`, `list-relevant-people` — resolve colleagues by name
- `get-drive-item` — read a `downloadUrl`, which is how the tenant probe works

It ships **inside RAIWork** — it is an in-process server, so there is no URL to
configure. It just needs authenticating:

```bash
raiwork mcp auth ms365
```

That opens a browser for your normal Microsoft 365 sign-in. Delegated permissions only —
you get exactly the SharePoint access you already have, nothing more. No app
registration, no admin consent, no ticket.

> If it says `needs auth`, run the command above. If it says nothing at all, add it from
> RAIWork's settings UI — HTTP/in-process servers are added there, not from the CLI
> (`raiwork mcp add` is for stdio servers and will register a URL as a command by
> mistake).

### `atlassian` — OPTIONAL

For pulling report requirements out of Jira, or writing findings to Confluence. Not
needed to build or publish a dashboard.

```bash
raiwork mcp auth atlassian
```

Any other server in `raiwork mcp list` is not part of this workflow. Leave it disabled:
fewer connected servers means less to go wrong and a leaner context.

---

## CLI tools

### `python3` — REQUIRED

Runs `tools/build_dashboard.py` and `tools/verify_dashboard.py`. **Stdlib only** — the
build needs nothing installed. macOS ships with a usable Python 3.

```bash
python3 --version        # 3.9+ is fine
```

### `uv` — REQUIRED (for anything that needs installing)

The only Python package manager we use. **Never `pip`.**

```bash
winget install astral-sh.uv     # Windows
brew install uv                 # macOS
```

**`uv` may be missing from a non-login shell.** The installer puts it in `~/.local/bin`, and
only a login shell's profile adds that to `PATH`. Agents and scripts often run a non-login
shell, so `uv` "is not installed" there. Use `zsh -lc '...'` (or `bash -lc`), or call
`~/.local/bin/uv` by full path. Do not install it a second time.

### `bun` — only if JS ever appears

There is no JavaScript dependency in this repo and that is deliberate. If one ever
appears, it goes through `bun`. **Never `npm`.**

### `playwright` + chromium — REQUIRED (in practice)

This is what opens the finished dashboard in a real browser, from a real `file://` URL,
and proves it works before anyone sends it out. Technically optional — `verify` degrades
to static checks and says so — but the render checks are the valuable ones, and
publishing without them defeats the point.

```bash
uv sync --extra verify && uv run playwright install chromium
```

`uv` handles it. **Never `pip`.** Sources are declared in `pyproject.toml`: PyPI is the
default and only source.

### Windows vs macOS

All the tooling here is **cross-platform Python** — `setup.py`, `tools/build_dashboard.py`
and `tools/verify_dashboard.py` run the same on Windows, macOS and Linux. There are no
shell scripts.

Two Windows-specific things to know:

- **Skills get copied, not symlinked**, unless Developer Mode is on. `setup.py` handles this
  automatically and tells you. The consequence: **re-run `python3 setup.py` after editing
  a `SKILL.md`**, or the change won't reach RAIWork.
- **The OneDrive sync folder is somewhere else** — `%OneDriveCommercial%` or
  `C:\Users\<user>\Eksempel AS\...`, not the macOS `~/Library/CloudStorage/...` path.
  `setup.py` finds and prints it.

### `git` — REQUIRED

To clone this repo and to contribute skill improvements back.

### `gh` (GitHub CLI) — OPTIONAL

Only for opening PRs against your forge. Not needed to use the dashboards.

```bash
GH_HOST=<your-forge> gh auth login
```

### Deliberately NOT required

No Node, no framework, no bundler, no Docker. And **never `pip` or `npm`** — `uv` and
`bun` only, both using public registries by default.

If you ever find yourself needing to install something to *use* a dashboard skill, that
is a bug in the skill — report it.

---

## Skills

### This repo's skills — REQUIRED

Installed by `python3 setup.py`, which symlinks them into `~/.raiwork/skills/`:

| Skill | Job |
|---|---|
| `tun-help` | router — "what can you do with dashboards?" |
| `tun-new` | build one from a data file |
| `tun-data` | refresh or repoint the data |
| `tun-verify` | prove it renders (the gate) |
| `tun-publish` | put it in SharePoint, confirm access, draft the message |
| `tun-powerbi-escape` | port a Power BI report, or refuse with reasons |

Because they're symlinks, editing `skills/*/SKILL.md` in this repo takes effect
immediately — no reinstall.

### Marketplace skills worth having

| Skill | Why | Priority | Where from |
|---|---|---|---|
| **`xlsx`** | Real data arrives as Excel. Reads, cleans and converts spreadsheets properly — including merged cells and the formula-vs-value trap that breaks naive conversion. | **strongly recommended** | marketplace |
| your brand skill | your organisation's brand skill, if any. Otherwise the active plugin's `tokens/palette.css`. Reach for one of these before inventing a colour. | recommended | marketplace |
| `outlook-cli` | Sends the announcement `tun-publish` drafts, from your real mailbox. | optional | marketplace |
| `pptx` | For when someone insists on a screenshot in a deck. Sometimes the honest answer. | optional | marketplace |
| `research` | Investigating a tenant or tooling question against primary sources. | optional | marketplace |

Install from RAIWork's marketplace UI. Some marketplaces ship `xlsx` and `pptx` together
as one plugin rather than as standalone skills.

`python3 setup.py` reports which of these it can find and where.


### Power tools and general-purpose skills

| Skill | Use it when |
|---|---|
| **`hotshot`** | Making a real change to the tooling (template, `tools/`, `setup.py`). Runs implement → verify → review → simplify → commit → push → PR in one go. |
| **`writing-for-agents`** | Editing any `SKILL.md` or `AGENTS.md` — the highest-value skill for this repo. |
| other general-purpose skills | Routing to the right skill, stress-testing a decision, keeping vocabulary consistent, root-causing a broken dashboard, prototyping. Use whatever your setup offers; none is vendored here. |

See [`06-way-of-working.md`](06-way-of-working.md) for when each earns its keep.

Don't reach for `hotshot` to edit prose in a `SKILL.md` — that's a one-line instruction
change, not a pipeline.

---

## Permissions and access

What a user needs from other people: deliberately close to nothing, which is the
point of Tier 1:

| Access | Needed for | Who grants it |
|---|---|---|
| Normal organisation M365 sign-in | everything | already have it |
| Write access to one SharePoint library | publishing dashboards | whoever owns the team site |
| Read access to `<your-forge>/<owner>/tun` | cloning this repo | the maintainer |

**No Power BI licence. No workspace. No Fabric capacity. No app registration. No admin
consent. No tenant change.** If a step ever seems to need one of those, you have drifted
off the Tier 1 path — stop and re-read [`02-architecture.md`](02-architecture.md).

The one thing worth thinking about: which SharePoint library a dashboard goes in **is**
its security model. That's a judgement call about audience, not an IT request.

---

## Working setup for RAIWork

- **Working folder:** set it to this repo. RAIWork then reads
  [`../AGENTS.md`](../AGENTS.md) automatically and picks up the house rules — including
  the row-level-security refusal.
- **Session per dashboard** is a good habit. Long-running, and you can come back to it.
- **Keep source data out of git.** `.gitignore` blocks `*.xlsx` outside `examples/`.
  Examples must be synthetic — `examples/01-hello-dashboard/salgsdata.csv` is generated,
  not real data.

---

## Checking your machine

```bash
python3 setup.py
```

Reports what's present, what's missing, and the exact command to fix each gap. Safe to
re-run.
