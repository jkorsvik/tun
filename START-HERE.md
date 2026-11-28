# Start here

Tún turns a CSV, spreadsheet or query result into a dashboard, report, process diagram or
slide deck in one HTML file. Share the file through SharePoint, OneDrive, Teams, Confluence
or email. Your reader opens it in a browser. No server, workspace or Power BI licence is
needed to read it.

[See the live Explorer](https://jkorsvik.github.io/tun/) · [tun.community](https://tun.community)

## Choose your route

### 1. No AI: build an example

[Get the toolkit by ZIP or Git](INSTALL.md#get-the-toolkit). Use Python 3.12 or later for this guide. The build commands below run from the extracted or cloned folder. On Windows, use PowerShell and `py -3`.

macOS or Linux:

```bash
python3 tools/build_dashboard.py \
  --data examples/01-hello-dashboard/salgsdata.csv \
  --title "Salg per region og produkt 2026" \
  --dimension Produkt --measure Belop --time Maaned \
  --filters Region,Produkt,Kanal \
  --source "Eksempeldata (syntetisk) - salgsdata.csv" \
  --requested-by "Prosjekteier" \
  --out work/demo.html
```

Open `work/demo.html` in your browser. On Windows, paste the following single line into PowerShell instead of the macOS/Linux command above:

```powershell
py -3 tools/build_dashboard.py --data examples/01-hello-dashboard/salgsdata.csv --title "Salg per region og produkt 2026" --dimension Produkt --measure Belop --time Maaned --filters Region,Produkt,Kanal --source "Eksempeldata (syntetisk) - salgsdata.csv" --requested-by "Prosjekteier" --out work/demo.html
```

Then run `Invoke-Item work/demo.html` to open the file.

The builders use only the Python standard library. There is no package installation or
server to start.

### 2. Claude Code, Codex, Gemini CLI, Copilot, VS Code or OpenCode

[Install Tún for your tool](INSTALL.md), then open [the AI recipes](docs/ai-recipes/README.md). Use Marketplace for RAIWork. For local coding assistants, open the toolkit folder and follow the recipe for your tool. The recipes all start with synthetic data and give the commands to build and check one HTML file.

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
