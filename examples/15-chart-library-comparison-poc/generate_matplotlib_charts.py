#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
generate_matplotlib_charts.py — writes static SVG files into mpl-svg/.

Build-time only. Requires matplotlib (uv sync --extra charts) — the page build
script (build_comparison_poc.py) does NOT import matplotlib; it only reads the
.svg text files this script already wrote, the same "vendor the heavy thing once"
principle examples/06 applies to Chart.js. The shipped HTML never runs Python.

Three outputs, same data/palette as the Chart.js and hand-rolled versions on the
page (shared_data.py):
  1. bar-vertical.svg — same six regions/values as the other two renderers.
  2. donut.svg — same data, drawn as a ring (Wedge with width < radius).
  3. norway-map.svg — choropleth over six real fylker (data/fylker-6.geojson),
     each standing in for one synthetic region — see README.md for the mapping
     and its honesty caveat.

    uv sync --extra charts
    python3 generate_matplotlib_charts.py
"""
from __future__ import annotations

import json
import pathlib
import sys

import matplotlib

matplotlib.use("svg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.patches import Wedge

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from shared_data import LABELS, PALETTE, REGION_TO_FYLKE, VALUES, color_for

HERE = pathlib.Path(__file__).parent
OUT_DIR = HERE / "mpl-svg"
OUT_DIR.mkdir(exist_ok=True)
GEOJSON = HERE / "data" / "fylker-6.geojson"

# Text as real <text> elements, not vector paths — keeps the SVG small and the
# text selectable/copyable. Trade-off documented in README.md: this DOES mean
# the glyph shapes depend on the viewer having a similar font installed, unlike
# svg.fonttype="path" (matplotlib's default), which would be font-independent
# but bakes every letter into a path and bloats the file. Chosen deliberately
# for this POC, not left at the default by accident.
plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["font.family"] = "Arial, sans-serif"


def save_svg(fig, name: str) -> None:
    path = OUT_DIR / name
    fig.savefig(path, format="svg", bbox_inches="tight", transparent=True)
    plt.close(fig)
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def build_bar_vertical() -> None:
    fig, ax = plt.subplots(figsize=(4.4, 3.0), dpi=100)
    colors = [color_for(i) for i in range(len(LABELS))]
    bars = ax.bar(LABELS, VALUES, color=colors, width=0.62)
    for rect, val in zip(bars, VALUES):
        ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + 1.5,
                 str(val), ha="center", va="bottom", fontsize=9)
    ax.set_ylim(0, max(VALUES) * 1.18)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#cccccc")
    ax.tick_params(colors="#444444", labelsize=9)
    ax.set_yticks([])
    fig.tight_layout()
    save_svg(fig, "bar-vertical.svg")


def build_donut() -> None:
    fig, ax = plt.subplots(figsize=(3.6, 3.6), dpi=100)
    total = sum(VALUES)
    start = 90.0  # 12 o'clock
    colors = [color_for(i) for i in range(len(LABELS))]
    for i, val in enumerate(VALUES):
        theta2 = start
        theta1 = start - val / total * 360
        ax.add_patch(Wedge((0, 0), 1.0, theta1, theta2, width=0.42,
                            facecolor=colors[i], edgecolor="white", linewidth=1.5))
        start = theta1
    ax.set_xlim(-1.15, 1.15)
    ax.set_ylim(-1.15, 1.15)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    save_svg(fig, "donut.svg")


def load_geojson() -> dict:
    return json.loads(GEOJSON.read_text(encoding="utf-8"))


def polygons_for(geom: dict) -> list[list[list[float]]]:
    """Exterior ring only per polygon part — see data/simplify_fylker.py's note
    on lakes/holes being an accepted simplification for this illustrative map."""
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    return [poly[0] for poly in geom["coordinates"]]


def build_norway_map() -> None:
    data = load_geojson()
    by_fylke = {f["properties"]["fylkesnavn"]: f for f in data["features"]}

    fig, ax = plt.subplots(figsize=(3.6, 5.4), dpi=100)
    for i, (region, val) in enumerate(zip(LABELS, VALUES)):
        fylke_name = REGION_TO_FYLKE[region]
        feat = by_fylke[fylke_name]
        color = color_for(i)
        for ring in polygons_for(feat["geometry"]):
            ax.add_patch(MplPolygon(ring, closed=True, facecolor=color,
                                     edgecolor="white", linewidth=0.6))
        # Label at the biggest ring's simple centroid, not an average across every
        # point of every part — Nordland/Vestland/Trøndelag all include many small
        # islands, and including those would drag a naive whole-shape average
        # towards the sea instead of the mainland.
        rings = polygons_for(feat["geometry"])
        biggest = max(rings, key=len)
        cx = sum(p[0] for p in biggest) / len(biggest)
        cy = sum(p[1] for p in biggest) / len(biggest)
        ax.text(cx, cy, str(val), ha="center", va="center", fontsize=9,
                fontweight="bold", color="#111111",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", alpha=0.75, linewidth=0))

    ax.set_xlim(3.5, 19.5)
    ax.set_ylim(57.3, 70.0)
    ax.set_aspect(1.9)  # crude equirectangular-ish correction at this latitude
    ax.axis("off")
    fig.tight_layout()
    save_svg(fig, "norway-map.svg")


if __name__ == "__main__":
    build_bar_vertical()
    build_donut()
    build_norway_map()
