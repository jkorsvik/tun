#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
simplify_fylker.py — one-time preprocessing script, not part of the page build.

SOURCE: fylker-S.geojson from https://github.com/robhop/fylker-og-kommuner
(CC BY 4.0, itself derived from Kartverket's official administrative boundaries).
Not committed to this repo — only this script's OUTPUT (fylker-6.geojson, ~140 KB) is.
To regenerate from scratch:
    curl -sSL -o fylker-S.geojson \
      https://raw.githubusercontent.com/robhop/fylker-og-kommuner/main/Fylker-S.geojson
    python3 simplify_fylker.py

Filters that source down to the six fylker this POC's synthetic regions are mapped to,
and thins each ring's point count with a simple minimum-distance filter. This is a small
illustrative map inlined in a self-contained HTML file, not a survey-grade cartographic
product — coastline precision finer than the map is ever drawn at is wasted bytes.

No dependencies beyond the standard library.
"""
import json
import math
import pathlib

HERE = pathlib.Path(__file__).parent
SRC = HERE / "fylker-S.geojson"
OUT = HERE / "fylker-6.geojson"

# fylkesnavn (as it appears in the source file) -> this POC's synthetic region label
TARGET = {
    "Nordland - Nordlánnda": "Nord",
    "Agder": "Sør",
    "Østfold": "Øst",
    "Vestland": "Vest",
    "Trøndelag - Trööndelage": "Midt",
    "Innlandet": "Innlandet",
}

MIN_DIST_DEG = 0.1  # ~2km at this latitude; tune for size vs. recognisability


def thin_ring(ring: list[list[float]]) -> list[list[float]]:
    if len(ring) <= 4:
        return ring
    kept = [ring[0]]
    for pt in ring[1:-1]:
        last = kept[-1]
        if math.hypot(pt[0] - last[0], pt[1] - last[1]) >= MIN_DIST_DEG:
            kept.append(pt)
    kept.append(ring[-1])
    return kept if len(kept) >= 4 else ring


def thin_geometry(geom: dict) -> dict:
    if geom["type"] == "Polygon":
        geom["coordinates"] = [thin_ring(ring) for ring in geom["coordinates"]]
    elif geom["type"] == "MultiPolygon":
        geom["coordinates"] = [
            [thin_ring(ring) for ring in poly] for poly in geom["coordinates"]
        ]
    return geom


def count_points(geom: dict) -> int:
    if geom["type"] == "Polygon":
        return sum(len(r) for r in geom["coordinates"])
    return sum(len(r) for poly in geom["coordinates"] for r in poly)


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    out_features = []
    before_total = 0
    after_total = 0
    for feat in data["features"]:
        name = feat["properties"]["fylkesnavn"]
        if name not in TARGET:
            continue
        before_total += count_points(feat["geometry"])
        feat["geometry"] = thin_geometry(feat["geometry"])
        after_total += count_points(feat["geometry"])
        feat["properties"] = {"fylkesnavn": name, "region_label": TARGET[name]}
        out_features.append(feat)

    if len(out_features) != len(TARGET):
        missing = set(TARGET) - {f["properties"]["fylkesnavn"] for f in out_features}
        raise SystemExit(f"missing fylker in source file: {missing}")

    out = {"type": "FeatureCollection", "features": out_features}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"points: {before_total} -> {after_total} ({after_total/before_total:.0%})")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
