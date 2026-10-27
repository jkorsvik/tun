# 02. Paired: a dashboard and its data, in two files

`dash.html` is a dashboard with no data inside it. The rows live in `data.js` beside it, and
the page loads that file. Replace `data.js` in a synced folder and everyone who has the pair
sees the new numbers without anyone rebuilding the page.

That is the whole trade. The bundled shape (`../01-hello-dashboard/`) survives being mailed
as one attachment; this one does not, because an artefact without its data file is a
dashboard with no numbers in it. Choose paired when the numbers change more often than the
layout, and when the folder is shared rather than the file. The contract, including what a
recipient sees when the pair is broken, is [`docs/13`](../../docs/13-paired-data-contract.md).

## Rebuild it

```bash
python3 tools/build_dashboard.py \
  --data examples/01-hello-dashboard/salgsdata.csv \
  --title "Salg per region og produkt 2026" \
  --dimension Produkt --measure Belop --time Maaned \
  --filters Region,Produkt,Kanal \
  --source "Eksempeldata (syntetisk) — salgsdata.csv" \
  --requested-by "Prosjekteier" \
  --mode paired \
  --out examples/02-paired-dashboard/dash.html
```

`--mode paired` writes `data.js` beside `--out` and points the page at it. Keep the two files
together: the builder prints that warning, and it is the one thing a reader can get wrong.

## Verify it

```bash
uv run --extra verify python tools/verify_standalone_core.py examples/02-paired-dashboard/dash.html
uv run --extra verify python tools/verify_viewports.py examples/02-paired-dashboard/dash.html
uv run --extra verify python tools/verify_a11y.py examples/02-paired-dashboard/dash.html
```

`verify_standalone_core` passes because "standalone" here means the *page* has no remote
dependency, not that it holds its own data. Its screenshot is the proof the data file was
found: a page that could not load `data.js` renders empty.

Data is synthetic (`../01-hello-dashboard/salgsdata.csv`), so nothing here is a real figure.
