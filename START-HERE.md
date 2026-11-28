# Start here

Tún turns a CSV, spreadsheet or query result into an interactive dashboard, report, process
diagram or slide deck in **one self-contained HTML file**. Drop the file in SharePoint,
OneDrive, Teams, Confluence or an email. Anyone who can open the folder opens it in their
browser — offline too — with no server, no workspace and no Power BI licence.

[See the live Explorer (51 runnable examples)](https://jkorsvik.github.io/tun/) · [tun.community](https://tun.community) · [AI bootstrap (`llms.txt`)](llms.txt)

## Fastest start: tell your AI assistant

Paste this single sentence into Claude Code, GitHub Copilot, VS Code, Cursor, Codex,
Gemini CLI, Windsurf, OpenCode or RAIWork:

```text
Set up Tún from https://github.com/jkorsvik/tun for this tool, check that it works, and introduce me to the Tún verbs.
```

*(Referencing `https://jkorsvik.github.io/tun/` works too — the Explorer carries the same
setup instructions and links to `llms.txt`.)*

## Choose your route

### 1. Coding assistant (Claude Code, Copilot, VS Code, Cursor, Codex, Gemini CLI, Windsurf, OpenCode, RAIWork)

Clone the repository, then install the open [Agent Skills](https://agentskills.io/specification)
for your tool (on Windows, use `py -3` instead of `python3`):

| Tool | Run in the repository |
|---|---|
| Detect installed tools automatically | `python3 setup.py --tool auto` |
| Claude Code | `python3 setup.py --tool claude` |
| Codex, Gemini CLI, GitHub Copilot, VS Code, OpenCode, Goose, Amp | `python3 setup.py --tool agents` |
| Cursor (personal + Cloud Agents sync) | `python3 setup.py --tool cursor` |
| Windsurf | `python3 setup.py --tool windsurf` |
| RAIWork | `python3 setup.py` |

Once installed, the skills work from **any folder** on your machine. Open your assistant
where your data lives and ask in plain words — or use a verb directly:

> Make a dashboard from `examples/01-hello-dashboard/salgsdata.csv`. Show amounts by
> product and the trend over months, with region as a filter.

### The verbs you get

Invoke them as `/tun-...` or just describe what you want in Norwegian or English:

| Verb | When to reach for it |
|---|---|
| **`tun-help`** | *"What can Tún do?"* — introduces Tún, picks the right shape, and states any approval cost up front |
| **`tun-new`** | *"Make a dashboard / scorecard / register / timeline / slide deck from this file"* (27 shapes) |
| **`tun-data`** | *"Update the numbers"* — refreshes an artefact or shows zero-tooling CSV drag-and-drop |
| **`tun-verify`** | *"Is this ready to send?"* — opens the file in a real browser and shows a screenshot |
| **`tun-publish`** | *"Share this with the team"* — puts it in SharePoint, OneDrive or Atlassian Artifacts and drafts the message |
| **`tun-process`** | *"Map how this process works"* — draws a swimlane diagram in one HTML file |
| **`tun-review`** | *"Let readers flag wrong rows"* — adds `--annotate` and reads pasted comment blocks back |
| **`tun-host`** | *"Does this need a web host or backend?"* — keeps portable files, static hosts and apps separate |
| **`tun-powerbi-escape`** | *"Move this report out of Power BI"* — turns it into a licence-free file |
| **`tun-for-communicators`** | *"Explain this without technical jargon"* — translates technical terms and messages |
| **`tun-feedback`** | *"Log an idea or something that broke"* — saves locally or prepares a GitHub issue |

### 2. No AI: build an example with Python

You need Git and Python 3.9 or newer. On Windows, use `py -3` instead of `python3`.

```bash
git clone https://github.com/jkorsvik/tun.git
cd tun
python3 tools/build_dashboard.py \
  --data examples/01-hello-dashboard/salgsdata.csv \
  --title "Salg per region og produkt 2026" \
  --dimension Produkt --measure Belop --time Maaned \
  --filters Region,Produkt,Kanal \
  --source "Eksempeldata (syntetisk) - salgsdata.csv" \
  --requested-by "Prosjekteier" \
  --out work/demo.html
```

Open `work/demo.html` in your browser. On Windows, `start work\demo.html` does the same.

The builders use only the Python standard library. There is no package installation or
server to start.

### 3. ChatGPT, Grok or another chat bot

Upload a CSV containing data you may share, and paste this prompt:

```text
Turn the attached CSV into one self-contained HTML dashboard.
Include a short explanation, filters, a chart and the rows behind the numbers.
Put all CSS, JavaScript and data in the file. Use no remote resources.
Include the source, data extraction time and build time.
Use semantic HTML and clear labels.
Give me the complete HTML file and tell me to open it in a browser.
```

This is a simple first try. The bot writes its own code, not the tested Tún builders.
Use route 1 or 2 for the full toolkit and verification.

## Check before you share

Open the file and compare one number with the source. For a browser check with a
screenshot, install [uv](https://docs.astral.sh/uv/), then run:

```bash
uv sync --extra verify && uv run playwright install chromium
uv run python tools/verify_dashboard.py work/demo.html
```

Look at the screenshot. A successful build alone does not prove that the page is readable
or that its numbers are right.

Share only data your whole audience may see. A browser filter is not access control.
Split the data and give each audience its own file and folder when permissions differ.

## For AI agents sent here by a user

1. Clone `https://github.com/jkorsvik/tun.git` if not already inside a checkout (for example `~/tun` or `%USERPROFILE%\tun`).
2. Run `python3 setup.py --tool <your-harness>` (`py -3` on Windows; use `claude`, `cursor`, `windsurf`, `agents` for Codex/Gemini CLI/Copilot/VS Code/OpenCode/Goose/Amp, or `auto`).
3. Confirm the smoke test succeeded; when the user asks you to build an artefact from their own folder, resolve `<repo>/tools/...` from `.installed-by-tun` and write outputs into the user's folder (never commit or write real data inside the Tún repo).
4. Reply in the user's language with a short welcome: what Tún produces, the main `tun-*` verbs above, the folder-permission rule, and an offer to build their first file now.

## Keep going

- [Onboarding in detail](docs/04-onboarding.md), including Windows differences and publishing
- [Examples](examples/README.md), one working file per artefact kind
- [Which shape answers which question](docs/33-artefact-shapes.md)
- [Contribute](CONTRIBUTING.md): report a real task, improve a skill or add an example
- [Source and licence](README.md): AGPL for the toolkit, with an exception for generated documents
