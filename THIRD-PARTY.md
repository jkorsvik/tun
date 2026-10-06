# Third-party components

Tún's own code is AGPL-3.0-or-later (see `LICENSE` and `README.md`). These files keep
their own licences, and their notices stay intact wherever they are copied.

| Component | Where | Licence | Notice |
|---|---|---|---|
| Chart.js v4.4.0 | `examples/06-chart-palette-demo/vendor/chart.umd.min.js`, `examples/15-chart-library-comparison-poc/vendor/chart.umd.min.js`, and inlined into the two built HTML files of those examples | MIT | Kept verbatim at the top of the file: "Chart.js v4.4.0 ... (c) 2023 Chart.js Contributors ... Released under the MIT License". <https://www.chartjs.org> |
| Norwegian county boundaries | `examples/15-chart-library-comparison-poc/data/fylker-6.geojson` (filtered and simplified) | CC BY 4.0 | From [robhop/fylker-og-kommuner](https://github.com/robhop/fylker-og-kommuner), derived from Kartverket's official administrative boundaries. Processing: `data/simplify_fylker.py`. |
