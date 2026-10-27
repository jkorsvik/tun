"""
shared_data.py — the single source of truth for data + palette in this POC.

Imported by both generate_matplotlib_charts.py (build-time SVG generation) and
build_comparison_poc.py (the page assembler, which also embeds this as JSON for
Chart.js). Same six numbers, same six hex colours, in all three renderers on the
page — otherwise "side by side" would not be a fair comparison.
"""
from __future__ import annotations

# Okabe–Ito qualitative palette, same six colours already used in
# examples/06-chart-palette-demo/ and examples/14-chart-emulation-nojs-poc/.
PALETTE = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00"]
LABELS = ["Nord", "Sør", "Øst", "Vest", "Midt", "Innlandet"]
VALUES = [42, 78, 55, 90, 33, 61]

# Region label -> real fylke used for the choropleth map (see data/simplify_fylker.py
# for how the boundary file was produced, and README.md for why these six were picked).
REGION_TO_FYLKE = {
    "Nord": "Nordland - Nordlánnda",
    "Sør": "Agder",
    "Øst": "Østfold",
    "Vest": "Vestland",
    "Midt": "Trøndelag - Trööndelage",
    "Innlandet": "Innlandet",
}


def color_for(i: int) -> str:
    return PALETTE[i % len(PALETTE)]
