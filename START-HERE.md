# Start here

Tún turns a CSV, spreadsheet or query result into a dashboard, report, process diagram or
slide deck in one HTML file. Share the file through SharePoint, OneDrive, Teams, Confluence
or email. Your reader opens it in a browser. No server, workspace or Power BI licence is
needed to read it.

[See the live Explorer](https://jkorsvik.github.io/tun/) · [tun.community](https://tun.community)

## Choose your route

### 1. No AI: build an example

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

### 2. Claude Code, Codex, Gemini CLI, Copilot, VS Code or OpenCode

Clone the repository, then install the open Agent Skills for your tool:

| Tool | Run in the repository |
|---|---|
| Claude Code | `python3 setup.py --tool claude` |
| Codex, Gemini CLI, GitHub Copilot, VS Code, OpenCode | `python3 setup.py --tool agents` |
| RAIWork | `python3 setup.py` |

Then open your assistant in the repository and ask:

> Make a dashboard from `examples/01-hello-dashboard/salgsdata.csv`. Show amounts by
> product and the trend over months, with region as a filter.

The skills tell the assistant to use the tested builders and verification tools. The skills
are editable Markdown recipes in [`skills/`](skills/).

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

## Keep going

- [Onboarding in detail](docs/04-onboarding.md), including Windows differences and publishing
- [Examples](examples/README.md), one working file per artefact kind
- [Which shape answers which question](docs/33-artefact-shapes.md)
- [Contribute](CONTRIBUTING.md): report a real task, improve a skill or add an example
- [Source and licence](README.md): AGPL for the toolkit, with an exception for generated documents
