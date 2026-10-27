# 54. Every example, on one page

The answer to "what does this repository actually contain". One self-contained document with
a card per example: a photograph of the built artefact, the question it answers, and the
command from its own README.

The pictures are taken by a real browser from a `file://` URL at build time. That is the whole
point: a card cannot show a page that no longer builds, and a rebuild that breaks an example
shows up as a wrong or empty picture rather than as a passing test.

## Build it

```bash
python3 tools/build_showcase.py \
  --examples examples \
  --title "Tún: alle eksempel" \
  --source "the built examples in this repository" \
  --requested-by "Prosjekteier" \
  --out examples/54-showcase/oversikt.html
```

Requires Playwright, and fails without it rather than shipping a page of empty frames:

```bash
uv sync --extra verify && uv run playwright install chromium
```

## What is on the page

- A card per example, searchable by title, purpose, kind or folder number.
- Three counts across the top: examples, builders, and how many carry a documented command.
- Four columns at the bottom for everything that is not a picture: builders, skills, test
  suites and documents, read from the tree at build time and never typed by hand.

It is a document, not a dashboard, so it is verified as one: `verify_standalone_core.py`,
`verify_viewports.py` at the 14 px floor, and `verify_a11y.py`. `verify_dashboard.py` refuses
it on purpose, because it looks for KPI cards and chart marks that a document has no reason
to have.
