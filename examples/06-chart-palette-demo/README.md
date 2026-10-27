# 06. Every chart type and every colour family, side by side

The eight chart types [`docs/10`](../../docs/10-chart-colour-palettes.md) allows, drawn four
times each: one per palette family (categorical, sequential, diverging) with a switcher, so
a colour decision is made by looking at real bars and lines instead of at a swatch grid. The
palettes are Okabe–Ito, ColorBrewer Set2 and a table view for readers who need the numbers.

Chart.js is **vendored, not fetched**: `vendor/chart.umd.min.js` (4.4.0, MIT) is inlined at
build time, so the artefact has no remote dependency and works from `file://` on a laptop
with no network. That is the only chart library in this repository, and the reason it is
here rather than in `templates/` is that everything else is hand-rolled SVG.

## Rebuild it

```bash
python3 examples/06-chart-palette-demo/build_chart_palette_demo.py
```

No arguments. It reads `vendor/chart.umd.min.js`, prints the vendored size so a silent
upgrade is visible, and writes `chart-palette-demo.html` beside itself (about 250 KB). To
change the library, replace that one file and rebuild: the version is written into the
artefact's provenance block.

## Verify it

```bash
uv run --extra verify python tools/verify_standalone_core.py examples/06-chart-palette-demo/chart-palette-demo.html
uv run --extra verify python tools/verify_viewports.py examples/06-chart-palette-demo/chart-palette-demo.html
uv run --extra verify python tools/verify_a11y.py examples/06-chart-palette-demo/chart-palette-demo.html
```

2026-10-24: five declarations here were under the 14 px floor (the swatch name, the hex, the
note, the table, and the chart caption) and three controls were under 44 px. A palette demo
is copied more often than it is read, so its smallest type is the type a copy inherits. All
of them measure at the floor now.
