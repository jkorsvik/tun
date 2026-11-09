# Start here

Build one dashboard, open it, and share the file. You need Python 3.9 or newer. You do not
need an AI tool, Node, a server, or a Power BI licence.

## 1. Build the example

From the repository folder, run:

```bash
python3 tools/build_dashboard.py --data examples/01-hello-dashboard/salgsdata.csv --title "Salg per region og produkt 2026" --dimension Produkt --measure Belop --time Maaned --filters Region,Produkt,Kanal --source "Synthetic example data" --requested-by "Project owner" --out start-here.html
```

On Windows, use `py -3` instead of `python3`.

The command writes `start-here.html`. This is synthetic example data, not customer data.

## 2. Open the file

Open `start-here.html` in your browser. Try the filters and the table. The file contains its
data and code, so it also works without a network connection.

Do not judge the result from the build log alone. Look at the page and check one number.

## 3. Use your own data

Replace the CSV path and the field names in the same command:

- `--data`: your CSV file
- `--dimension`: the field to group by
- `--measure`: the numeric field to sum
- `--time`: the date or month field
- `--filters`: the fields a reader can filter on

Keep `--source` and `--requested-by`. They tell the reader where the numbers came from.

**One safety rule:** everyone who receives the file can read all the data inside it. If
different audiences need different rows, make one file per audience and put each file in its
own folder. A browser filter is not access control.

## 4. Share it

Put the HTML file in a SharePoint or OneDrive folder and share the folder link. SharePoint
may show its own preview. For the reliable route, download the file and open it in a browser.
The preview has measured limits: downloads, printing and some navigation do not work there.

For a real report, verify the file before you share it:

```bash
uv run --extra verify python tools/verify_dashboard.py start-here.html
```

The first verification needs `uv sync --extra verify` and
`uv run playwright install chromium`. The build itself needs neither.

## Prefer to ask an AI tool?

Install the skills once for your tool:

| Tool | Command |
|---|---|
| RAIWork | `python3 setup.py --tool raiwork` |
| Claude Code | `python3 setup.py --tool claude` |
| Other agents | `python3 setup.py --tool agents` |

Then ask:

> Make a dashboard from this spreadsheet. Use product as the dimension, amount as the measure,
> and region and channel as filters. Norwegian. Verify it before I share it.

## What next?

- [Full onboarding](docs/04-onboarding.md): Windows details, installation and publishing
- [Choose an artefact shape](docs/33-artefact-shapes.md): charts, reports, decks and diagrams
- [Open the example gallery](examples/54-showcase/oversikt.html): the self-contained gallery file
- [Read the idea and the limits](https://tun.community): why the artefact is a file
