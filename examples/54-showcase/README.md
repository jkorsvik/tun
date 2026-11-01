# 54. Tún Explorer: every possibility, one consolidated view

A self-contained Explorer for the whole toolkit. Six guided paths connect a reader's goal to a
large live stage, the example's own build recipe, a full-screen view, a byte-exact HTML download
and a shareable example link. The full visual card collection remains below for browsing.

The page carries every built example and a real browser photograph of each. The live stage opens
example 55, the raw-WebGL task space, so the first view is itself an artefact rather than a video
or a marketing illustration. No library, framework, server or runtime request is added.

## Build it

```bash
python3 tools/build_showcase.py \
  --examples examples \
  --title "Tún Explorer" \
  --source "the built examples in this repository" \
  --requested-by "Prosjekteier" \
  --out examples/54-showcase/oversikt.html
```

Requires Playwright, and fails without it rather than shipping a page of empty frames:

```bash
uv sync --extra verify && uv run playwright install chromium
```

## What is on the page

- Six guided paths: all possibilities, data, stories, processes, scale and browser capability.
- A persistent live stage with previous/next navigation, full-screen view and build recipe.
- Byte-exact HTML downloads from the embedded artefact bytes, plus deep links by path and example.
- Every example as a searchable visual card, with builders, skills, test suites and docs read from
  the tree at build time.

It is a document, not a dashboard, so it is verified as one: `verify_standalone_core.py`,
`verify_viewports.py` at the 14 px floor, `verify_a11y.py`, and `tests/test_explorer.py` for the
stage, paths, deep links and downloads. `verify_dashboard.py` refuses it on purpose, because it
looks for KPI cards and chart marks that this Explorer has no reason to have.
