# Toolchain — Skills, MCP Servers and CLI Tools

**Reader:** contributor — you are changing the toolkit, and need the constraint or the convention behind it.

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

That opens a browser for normal Eksempel AS sign-in (Entra + MFA). Delegated permissions only —
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

### Explicitly NOT needed

Don't let these confuse you when you see them in `raiwork mcp list`:

| Server | Why it's irrelevant here |
|---|---|
| `servicenow` | incidents and change requests — unrelated |
| `aws-mcp` | AWS infrastructure — unrelated |
| `github-eksempelc` | GitHub Copilot API — unrelated |
| `plattformen-data` | plattformen payment data — a possible *data source* one day, not part of the workflow |
| `developer-portal` | Eksempel AS API catalogue — unrelated |

Leave them disabled. Fewer connected servers = less to go wrong and a leaner context.

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
appears, it goes through `bun`. **Never `npm`.** `bunfig.toml` already points at Eksempel AS
Nexus.

### `playwright` + chromium — REQUIRED (in practice)

This is what opens the finished dashboard in a real browser, from a real `file://` URL,
and proves it works before anyone sends it out. Technically optional — `verify` degrades
to static checks and says so — but the render checks are the valuable ones, and
publishing without them defeats the point.

```bash
uv sync --extra verify && uv run playwright install chromium
```

`uv` handles it. **Never `pip`.** Sources are declared in `pyproject.toml`: PyPI as the
default, plus **Eksempel AS Nexus** as an extra internal source (verified reachable from a
Eksempel AS laptop — faster, and the route that works when public PyPI is blocked).

### Windows vs macOS

All the tooling here is **cross-platform Python** — `setup.py`, `tools/build_dashboard.py`
and `tools/verify_dashboard.py` run the same on Windows, macOS and Linux. There are no
shell scripts.

Two Windows-specific things to know:

- **Skills get copied, not symlinked.** Developer Mode is not needed and not used.
  `setup.py` copies and tells you. The consequence: **re-run `py -3 setup.py` after editing
  a `SKILL.md`**, or the change won't reach the assistant.
- **The OneDrive sync folder is somewhere else** — `%OneDriveCommercial%` or
  `C:\Users\<user>\Eksempel AS Bank ASA\...`, not the macOS `~/Library/CloudStorage/...` path.
  `setup.py` finds and prints it.

### `git` — REQUIRED

To clone this repo and to contribute skill improvements back.

### `gh` (GitHub CLI) — OPTIONAL

Only for opening PRs against `example.com`. Not needed to use the dashboards.

```bash
GH_HOST=example.com gh auth login
```

### Deliberately NOT required

No Node, no framework, no bundler, no Docker. And **never `pip` or `npm`** — `uv` and
`bun` only, both pointed at Eksempel AS Nexus as an extra source.

If you ever find yourself needing to install something to *use* a dashboard skill, that
is a bug in the skill — report it.

---

## Skills

### This repo's skills — REQUIRED

Installed by `python3 setup.py` (`py -3 setup.py` on Windows), which copies them into
`~/.raiwork/skills/`:

| Skill | Job |
|---|---|
| `tun-help` | router — "what can you do with dashboards?" |
| `tun-new` | build one from a data file |
| `tun-data` | refresh or repoint the data |
| `tun-verify` | prove it renders (the gate) |
| `tun-publish` | put it in SharePoint, confirm access, draft the message |
| `tun-powerbi-escape` | port a Power BI report, or refuse with reasons |

Because they are copies, editing `skills/*/SKILL.md` in this repo does **not** reach the
installed skill until you re-run `setup.py`. That is the intended trade: a symlink would make
editing a skill silently edit this checkout, on whatever branch is checked out, underneath a
running session. `setup.py --check` reports a copy that has fallen behind, and
`setup.py --link` symlinks instead, for when you are editing the skills themselves.

### Marketplace skills worth having

| Skill | Why | Priority | Where from |
|---|---|---|---|
| **`xlsx`** | Real data arrives as Excel. Reads, cleans and converts spreadsheets properly — including merged cells and the formula-vs-value trap that breaks naive conversion. | **strongly recommended** | `eksempel-office-pack` plugin |
| `eksempel-brand` | the design system design system — the authoritative source for the Eksempel AS palette used in the template. Reach for this before inventing a colour. | recommended | marketplace |
| `outlook-cli` | Sends the announcement `tun-publish` drafts, from your real mailbox. | optional | marketplace |
| `pptx` | For when someone insists on a screenshot in a deck. Sometimes the honest answer. | optional | `eksempel-office-pack` plugin |
| `research` | Investigating a tenant or tooling question against primary sources. | optional | marketplace |

Install from RAIWork's marketplace UI. Note `xlsx` and `pptx` arrive together as part of
the **eksempel-office-pack** plugin rather than as standalone skills — installing that one
plugin covers both.

`python3 setup.py` reports which of these it can find and where.


### Power tools and general-purpose skills

| Skill | Use it when |
|---|---|
| **`hotshot`** | Making a real change to the tooling (template, `tools/`, `setup.py`). Runs implement → verify → review → simplify → commit → push → PR in one go. |
| **`writing-for-agents`** | Editing any `SKILL.md` or `AGENTS.md` — the highest-value skill for this repo. |
| `ask-matt` | You don't know which skill fits. |
| `grilling` | Stress-testing a decision before committing to it. |
| `domain-modeling` | Keeping our vocabulary consistent across docs and skills. |
| `diagnosing-bugs` | A dashboard broke and the cause isn't obvious. |
| `prototype` | Answering a design question with a throwaway build. |

See [`06-way-of-working.md`](06-way-of-working.md) for when each earns its keep.

Don't reach for `hotshot` to edit prose in a `SKILL.md` — that's a one-line instruction
change, not a pipeline.

---

## Permissions and access

What en kollega needs from other people — deliberately close to nothing, which is the
point of Tier 1:

| Access | Needed for | Who grants it |
|---|---|---|
| Normal Eksempel AS M365 sign-in | everything | already have it |
| Write access to one SharePoint library | publishing dashboards | whoever owns the team site |
| Read access to `example.com/tun` | cloning this repo | vedlikeholderen |

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
  not real Eksempel AS data.

---

## Checking your machine

```bash
python3 setup.py
```

Reports what's present, what's missing, and the exact command to fix each gap. Safe to
re-run.
