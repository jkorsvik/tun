#!/usr/bin/env python3
"""
build_chart_emulation_poc.py — generates chart-emulation-nojs-poc.html

Diagnostic companion to examples/06-chart-palette-demo/ and issue #30
(Javascript-løs standalone HTML). Renders the SAME nine Chart.js chart
types from that demo's "Kategorisk" tab — bar, pie, doughnut, polar area,
line, area, radar, scatter, bubble — using the SAME synthetic dataset and
ONE palette (Okabe–Ito, the colour-vision-deficiency-safe qualitative
one), but with ZERO <script> tags anywhere in the output. Not "JS with a
fallback" like examples/13-js-free-standalone-poc/ — there is no JS
version to fall back FROM here. Every pixel is decided by this Python
script at build time and baked into static CSS (conic-gradient, div
widths) or static inline SVG (path/polygon/circle coordinates).

WHY THIS EXISTS: issue #30's POC drew one hard line — "no honest
CSS-only substitute exists for a scatter+trendline chart" — and declared
it uncrossable. That conclusion is correct for a chart whose DATA is only
known at runtime (user input, a live filter, a fetch). It stops being
true the moment the data is already known when the file is generated:
Python can do the same coordinate math a browser's JS would have done,
and bake the answer into a static SVG path. This file exists to find out,
chart type by chart type, whether that theoretical point holds up when
actually built and looked at — not to re-litigate #13's scatter finding,
which is about a different (runtime-unknown-data) case.

STATUS: exploratory/diagnostic, like examples/06 and examples/13. Grades
each of the nine chart types by eye (see README.md's table) so a later
build-instruction can let a user opt in/out of "emulate this chart type
without JS" per chart, instead of guessing. Does not touch examples/06
or examples/13.

    python3 build_chart_emulation_poc.py

No dependencies beyond the standard library.
"""
from __future__ import annotations

import datetime
import math
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
REPO_ROOT = HERE.parent.parent
OUT = HERE / "chart-emulation-nojs-poc.html"

BUILT = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")



# Light theme only — this POC is about chart-type feasibility, not
# re-proving the theme toggle (that's #05/#13's job).
sys.path.insert(0, str(REPO_ROOT / "tools"))
import tun_tokens  # noqa: E402

# Tokens come from tools/tun_tokens.py: it resolves which palette is active, validates
# that it defines all eight slots core's theme files consume, and inlines them in the
# documented load order. Core pins the neutral palette deliberately -- see that module's
# palette_path() for why an installed plugin does not win by default.
TOKEN_CSS, TOKEN_SOURCE = tun_tokens.load_token_css(("status-semantic.css", "theme-light.css"))

# ---------------------------------------------------------------------------
# Data — copied verbatim from examples/06-chart-palette-demo/build_chart_palette_demo.py
# (categorical tab dataset + Okabe–Ito palette) so the two demos are a fair,
# like-for-like comparison. Not re-derived, not tuned to flatter either side.
# ---------------------------------------------------------------------------
PALETTE = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00"]
LABELS = ["Nord", "Sør", "Øst", "Vest", "Midt", "Innlandet"]
VALUES = [42, 78, 55, 90, 33, 61]
SERIES_LABELS = ["Q1", "Q2", "Q3", "Q4", "Q5"]
SERIES = {
    "Nord": [10, 14, 18, 22, 19],
    "Sør": [30, 28, 35, 40, 44],
    "Øst": [15, 20, 17, 25, 30],
    "Vest": [50, 48, 55, 60, 58],
    "Midt": [8, 12, 10, 15, 20],
    "Innlandet": [25, 22, 28, 26, 31],
}
SCATTER = {
    "Nord": [[10, 10], [12, 13], [9, 8], [11, 12], [13, 9]],
    "Sør": [[30, 15], [32, 18], [28, 13], [31, 16], [29, 19]],
    "Øst": [[20, 30], [22, 33], [18, 28], [21, 31], [19, 34]],
    "Vest": [[40, 35], [42, 38], [38, 33], [41, 36], [39, 39]],
    "Midt": [[15, 45], [17, 48], [13, 43], [16, 46], [14, 49]],
    "Innlandet": [[35, 5], [37, 8], [33, 3], [36, 6], [34, 9]],
}


def color_for(i: int) -> str:
    return PALETTE[i % len(PALETTE)]


# ---------------------------------------------------------------------------
# Small geometry helpers — all build-time, all pure Python, output is
# already-final numbers baked into strings. Nothing here runs in the browser.
# ---------------------------------------------------------------------------
def polar_point(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    rad = math.radians(deg)
    return (cx + r * math.cos(rad), cy + r * math.sin(rad))


def fmt(n: float) -> str:
    return f"{n:.2f}".rstrip("0").rstrip(".") if "." in f"{n:.2f}" else f"{n:.2f}"


def legend_html(labels: list[str], colors_by_index=color_for) -> str:
    chips = "".join(
        f'<span class="legend-chip"><span class="legend-swatch" style="background:{colors_by_index(i)}"></span>{lab}</span>'
        for i, lab in enumerate(labels)
    )
    return f'<div class="legend">{chips}</div>'


# ---------------------------------------------------------------------------
# 1. Bar — pure CSS, no SVG needed at all. Same technique as
# examples/13-js-free-standalone-poc/'s always-present CSS bar chart.
# ---------------------------------------------------------------------------
def build_bar() -> str:
    maxv = max(VALUES)
    rows = []
    for i, (lab, val) in enumerate(zip(LABELS, VALUES)):
        pct = val / maxv * 100
        rows.append(
            f'<div class="bar-row"><span class="bar-label">{lab}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{fmt(pct)}%;background:{color_for(i)}"></div>'
            f'<span class="bar-value">{val}</span></div></div>'
        )
    return f'<div class="bar-chart">{"".join(rows)}</div>'


# ---------------------------------------------------------------------------
# 1b. Vertical bar (søyle) — same data as Bar, rotated. Pure CSS flexbox,
# bottom-aligned columns instead of left-aligned rows.
# ---------------------------------------------------------------------------
def build_bar_vertical() -> str:
    maxv = max(VALUES)
    cols = []
    for i, (lab, val) in enumerate(zip(LABELS, VALUES)):
        pct = val / maxv * 100
        cols.append(
            f'<div class="vbar-col"><span class="vbar-value">{val}</span>'
            f'<div class="vbar-fill" style="height:{fmt(pct)}%;background:{color_for(i)}"></div>'
            f'<span class="vbar-label">{lab}</span></div>'
        )
    return f'<div class="vbar-chart">{"".join(cols)}</div>'


# ---------------------------------------------------------------------------
# 1c/1d. Grouped (multi-series) bar — horizontal and vertical. Both reuse
# SERIES (region -> [Q1..Q5]), transposed so each GROUP is a quarter and
# each BAR within the group is a region — matching how Line/Area/Radar
# already treat region as "the series" elsewhere on this page, so the
# colour legend stays consistent across every chart card. Horizontal and
# vertical use the SAME grouping logic: the Q-label sits at the group's
# own axis position (left for horizontal, below for vertical — mirroring
# each other), and bars within one group are packed tightly, with more
# visual air between groups than between bars inside a group.
# ---------------------------------------------------------------------------
def grouped_values() -> tuple[list[str], list[list[int]], float]:
    groups = SERIES_LABELS  # Q1..Q5
    per_group = [[SERIES[region][j] for region in LABELS] for j in range(len(groups))]
    vmax = max(v for grp in per_group for v in grp)
    return groups, per_group, vmax


def build_bar_horizontal_multi() -> str:
    groups, per_group, vmax = grouped_values()
    blocks = []
    for gi, (glabel, vals) in enumerate(zip(groups, per_group)):
        rows = []
        for i, val in enumerate(vals):
            pct = val / vmax * 100
            rows.append(
                f'<div class="hbar-row"><div class="hbar-fill" style="width:{fmt(pct)}%;background:{color_for(i)}"></div>'
                f'<span class="hbar-val">{val}</span></div>'
            )
        blocks.append(
            f'<div class="hbar-group"><span class="hbar-group-label">{glabel}</span>'
            f'<div class="hbar-group-bars">{"".join(rows)}</div></div>'
        )
    return f'<div class="hbar-multi">{"".join(blocks)}</div>' + legend_html(LABELS)


def build_bar_vertical_multi() -> str:
    groups, per_group, vmax = grouped_values()
    blocks = []
    for gi, (glabel, vals) in enumerate(zip(groups, per_group)):
        bars = []
        for i, val in enumerate(vals):
            pct = val / vmax * 100
            bars.append(f'<div class="vbar-group-bar" style="height:{fmt(pct)}%;background:{color_for(i)}"></div>')
        blocks.append(
            f'<div class="vbar-group"><div class="vbar-group-bars">{"".join(bars)}</div>'
            f'<span class="vbar-group-label">{glabel}</span></div>'
        )
    return f'<div class="vbar-multi">{"".join(blocks)}</div>' + legend_html(LABELS)


# ---------------------------------------------------------------------------
# 2. Pie — pure CSS conic-gradient. Percentages computed once, here, not
# guessed: this IS the same maths Chart.js would do, just run in Python
# instead of in the browser.
# ---------------------------------------------------------------------------
def build_pie() -> str:
    total = sum(VALUES)
    stops = []
    acc = 0.0
    for i, val in enumerate(VALUES):
        start = acc / total * 100
        acc += val
        end = acc / total * 100
        stops.append(f"{color_for(i)} {fmt(start)}% {fmt(end)}%")
    gradient = ", ".join(stops)
    return (
        f'<div class="pie-wrap"><div class="pie-circle" style="background:conic-gradient({gradient})"></div></div>'
        + legend_html(LABELS)
    )


# ---------------------------------------------------------------------------
# 3. Doughnut — same conic-gradient, with a plain circle of the card's own
# background colour punched in the middle. Only works cleanly on a flat
# background (fine here; would need `mask` instead over an image/gradient
# background).
# ---------------------------------------------------------------------------
def build_doughnut() -> str:
    total = sum(VALUES)
    stops = []
    acc = 0.0
    for i, val in enumerate(VALUES):
        start = acc / total * 100
        acc += val
        end = acc / total * 100
        stops.append(f"{color_for(i)} {fmt(start)}% {fmt(end)}%")
    gradient = ", ".join(stops)
    return (
        '<div class="pie-wrap"><div class="pie-circle" style="background:conic-gradient('
        + gradient
        + ')"><div class="doughnut-hole"></div></div></div>'
        + legend_html(LABELS)
    )


# ---------------------------------------------------------------------------
# 4. Polar area — static SVG. Radius scales linearly with value (matches
# Chart.js's default radial scale behaviour); angle is fixed per category
# (360/6 = 60°). Native SVG arc command, no polygon approximation needed —
# an arc is exactly representable, not just approximated, when the radius
# and angles are known numbers, which they are, at build time.
# ---------------------------------------------------------------------------
def build_polar() -> str:
    cx, cy, rmax = 110, 110, 88
    n = len(VALUES)
    maxv = max(VALUES)
    step = 360 / n
    parts = []
    # background reference rings
    for frac in (0.33, 0.66, 1.0):
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{fmt(rmax*frac)}" class="grid-ring"/>')
    for i, val in enumerate(VALUES):
        r = val / maxv * rmax
        a0 = -90 + i * step
        a1 = a0 + step
        x0, y0 = polar_point(cx, cy, r, a0)
        x1, y1 = polar_point(cx, cy, r, a1)
        lx, ly = polar_point(cx, cy, rmax + 14, a0 + step / 2)
        parts.append(
            f'<path d="M{fmt(cx)},{fmt(cy)} L{fmt(x0)},{fmt(y0)} A{fmt(r)},{fmt(r)} 0 0,1 {fmt(x1)},{fmt(y1)} Z" '
            f'fill="{color_for(i)}" fill-opacity="0.8" stroke="{color_for(i)}" stroke-width="1"/>'
        )
        parts.append(f'<text x="{fmt(lx)}" y="{fmt(ly)}" class="axis-label" text-anchor="middle">{LABELS[i]}</text>')
    svg = (
        f'<svg viewBox="0 0 220 220" class="chart-svg" role="img" aria-label="Polar area">{"".join(parts)}</svg>'
    )
    return svg


# ---------------------------------------------------------------------------
# 5. Line — static SVG polylines, one per region, 5 points each (Q1..Q5).
# ---------------------------------------------------------------------------
def series_scale():
    all_vals = [v for series in SERIES.values() for v in series]
    return min(all_vals), max(all_vals)


def build_line() -> str:
    vmin, vmax = series_scale()
    w, h, pad = 300, 190, 28
    n = len(SERIES_LABELS)

    def xy(idx: int, val: int) -> tuple[float, float]:
        x = pad + idx / (n - 1) * (w - 2 * pad)
        y = h - pad - (val - vmin) / (vmax - vmin) * (h - 2 * pad)
        return x, y

    parts = [f'<line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" class="axis-line"/>']
    for i, lab in enumerate(SERIES_LABELS):
        x, _ = xy(i, vmin)
        parts.append(f'<text x="{fmt(x)}" y="{h-8}" class="axis-label" text-anchor="middle">{lab}</text>')
    for i, (region, vals) in enumerate(SERIES.items()):
        pts = " ".join(f"{fmt(x)},{fmt(y)}" for x, y in (xy(j, v) for j, v in enumerate(vals)))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color_for(i)}" stroke-width="2"/>')
        for j, v in enumerate(vals):
            x, y = xy(j, v)
            parts.append(f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="3" fill="{color_for(i)}"/>')
    svg = f'<svg viewBox="0 0 {w} {h}" class="chart-svg" role="img" aria-label="Line">{"".join(parts)}</svg>'
    return svg + legend_html(LABELS)


# ---------------------------------------------------------------------------
# 6. Area — same coordinates as the line chart, closed into a filled
# polygon per series. Six overlapping translucent fills is the SAME
# visual-clutter problem Chart.js's own area chart has with six series —
# not something the no-JS technique introduces on its own.
# ---------------------------------------------------------------------------
def build_area() -> str:
    vmin, vmax = series_scale()
    w, h, pad = 300, 190, 28
    n = len(SERIES_LABELS)

    def xy(idx: int, val: int) -> tuple[float, float]:
        x = pad + idx / (n - 1) * (w - 2 * pad)
        y = h - pad - (val - vmin) / (vmax - vmin) * (h - 2 * pad)
        return x, y

    baseline = h - pad
    parts = [f'<line x1="{pad}" y1="{baseline}" x2="{w-pad}" y2="{baseline}" class="axis-line"/>']
    for i, (region, vals) in enumerate(SERIES.items()):
        top_pts = [xy(j, v) for j, v in enumerate(vals)]
        poly = [f"{fmt(top_pts[0][0])},{fmt(baseline)}"]
        poly += [f"{fmt(x)},{fmt(y)}" for x, y in top_pts]
        poly.append(f"{fmt(top_pts[-1][0])},{fmt(baseline)}")
        parts.append(
            f'<polygon points="{" ".join(poly)}" fill="{color_for(i)}" fill-opacity="0.28" '
            f'stroke="{color_for(i)}" stroke-width="1.5"/>'
        )
    svg = f'<svg viewBox="0 0 {w} {h}" class="chart-svg" role="img" aria-label="Area">{"".join(parts)}</svg>'
    return svg + legend_html(LABELS)


# ---------------------------------------------------------------------------
# 7. Radar — static SVG. Five axes (Q1..Q5) at 72° apart, six overlaid
# polygons. The most code of the nine, but every number is still just
# trigonometry on already-known data, computed once here.
# ---------------------------------------------------------------------------
def build_radar() -> str:
    cx, cy, rmax = 110, 105, 78
    axes = SERIES_LABELS
    naxes = len(axes)
    step = 360 / naxes
    _, vmax = series_scale()

    def axis_point(idx: int, r: float) -> tuple[float, float]:
        return polar_point(cx, cy, r, -90 + idx * step)

    parts = []
    for frac in (0.33, 0.66, 1.0):
        ring = " ".join(f"{fmt(x)},{fmt(y)}" for x, y in (axis_point(j, rmax * frac) for j in range(naxes)))
        parts.append(f'<polygon points="{ring}" class="grid-ring" fill="none"/>')
    for j in range(naxes):
        x, y = axis_point(j, rmax)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{fmt(x)}" y2="{fmt(y)}" class="axis-line"/>')
        lx, ly = axis_point(j, rmax + 14)
        parts.append(f'<text x="{fmt(lx)}" y="{fmt(ly)}" class="axis-label" text-anchor="middle">{axes[j]}</text>')
    for i, (region, vals) in enumerate(SERIES.items()):
        pts = " ".join(f"{fmt(x)},{fmt(y)}" for x, y in (axis_point(j, v / vmax * rmax) for j, v in enumerate(vals)))
        parts.append(
            f'<polygon points="{pts}" fill="{color_for(i)}" fill-opacity="0.18" '
            f'stroke="{color_for(i)}" stroke-width="2"/>'
        )
        for j, v in enumerate(vals):
            x, y = axis_point(j, v / vmax * rmax)
            parts.append(f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="2.5" fill="{color_for(i)}"/>')
    svg = f'<svg viewBox="0 0 220 220" class="chart-svg" role="img" aria-label="Radar">{"".join(parts)}</svg>'
    return svg + legend_html(LABELS)


# ---------------------------------------------------------------------------
# 8. Scatter — static SVG. Six point SHAPES (not just six colours) mirror
# Chart.js's pointStyle-per-dataset in the source demo, since colour alone
# is not always enough to tell series apart (docs/10's rule D).
# ---------------------------------------------------------------------------
def marker(shape: str, x: float, y: float, color: str, size: float = 6) -> str:
    if shape == "circle":
        return f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="{size}" fill="{color}"/>'
    if shape == "rect":
        s = size * 1.7
        return f'<rect x="{fmt(x-s/2)}" y="{fmt(y-s/2)}" width="{fmt(s)}" height="{fmt(s)}" fill="{color}"/>'
    if shape == "rectRot":
        s = size * 1.3
        return (
            f'<rect x="{fmt(x-s/2)}" y="{fmt(y-s/2)}" width="{fmt(s)}" height="{fmt(s)}" '
            f'fill="{color}" transform="rotate(45 {fmt(x)} {fmt(y)})"/>'
        )
    if shape == "triangle":
        pts = [(x, y - size), (x - size, y + size * 0.8), (x + size, y + size * 0.8)]
        return f'<polygon points="{" ".join(f"{fmt(px)},{fmt(py)}" for px, py in pts)}" fill="{color}"/>'
    if shape == "star":
        pts = []
        for k in range(10):
            r = size if k % 2 == 0 else size * 0.45
            deg = -90 + k * 36
            pts.append(polar_point(x, y, r, deg))
        return f'<polygon points="{" ".join(f"{fmt(px)},{fmt(py)}" for px, py in pts)}" fill="{color}"/>'
    if shape == "cross":
        s, t = size, size * 0.32
        return (
            f'<path d="M{fmt(x-t)},{fmt(y-s)} h{fmt(2*t)} v{fmt(s-t)} h{fmt(s-t)} v{fmt(2*t)} '
            f'h{fmt(-(s-t))} v{fmt(s-t)} h{fmt(-2*t)} v{fmt(-(s-t))} h{fmt(-(s-t))} v{fmt(-2*t)} '
            f'h{fmt(s-t)} Z" fill="{color}"/>'
        )
    return f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="{size}" fill="{color}"/>'


POINT_SHAPES = ["circle", "triangle", "rect", "rectRot", "star", "cross"]


def build_scatter() -> str:
    all_pts = [p for pts in SCATTER.values() for p in pts]
    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    w, h, pad = 300, 190, 24

    def xy(px: float, py: float) -> tuple[float, float]:
        x = pad + (px - xmin) / (xmax - xmin) * (w - 2 * pad)
        y = h - pad - (py - ymin) / (ymax - ymin) * (h - 2 * pad)
        return x, y

    parts = [
        f'<line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" class="axis-line"/>',
        f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{h-pad}" class="axis-line"/>',
    ]
    for i, (region, pts) in enumerate(SCATTER.items()):
        shape = POINT_SHAPES[i % len(POINT_SHAPES)]
        for px, py in pts:
            x, y = xy(px, py)
            parts.append(marker(shape, x, y, color_for(i)))
    svg = f'<svg viewBox="0 0 {w} {h}" class="chart-svg" role="img" aria-label="Scatter">{"".join(parts)}</svg>'
    return svg + legend_html(LABELS)


# ---------------------------------------------------------------------------
# 9. Bubble — static SVG circles, radius mapped from value like the source
# demo (r = value / 6), scaled by a fixed pixels-per-unit factor so the
# circles are legible at this viewBox size.
# ---------------------------------------------------------------------------
def build_bubble() -> str:
    bubbles = [((i + 1) * 10, VALUES[i] / 2, VALUES[i] / 6) for i in range(len(LABELS))]
    xs = [b[0] for b in bubbles]
    ys = [b[1] for b in bubbles]
    xmin, xmax = min(xs) - 8, max(xs) + 8
    ymin, ymax = min(ys) - 8, max(ys) + 8
    w, h, pad = 300, 190, 24

    def xy(px: float, py: float) -> tuple[float, float]:
        x = pad + (px - xmin) / (xmax - xmin) * (w - 2 * pad)
        y = h - pad - (py - ymin) / (ymax - ymin) * (h - 2 * pad)
        return x, y

    parts = [
        f'<line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" class="axis-line"/>',
        f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{h-pad}" class="axis-line"/>',
    ]
    for i, (bx, by, r) in enumerate(bubbles):
        x, y = xy(bx, by)
        parts.append(f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="{fmt(r*2.6)}" fill="{color_for(i)}" fill-opacity="0.75" stroke="{color_for(i)}"/>')
    svg = f'<svg viewBox="0 0 {w} {h}" class="chart-svg" role="img" aria-label="Bubble">{"".join(parts)}</svg>'
    return svg + legend_html(LABELS)


# ---------------------------------------------------------------------------
# Grading — this is the point of the whole file. "grade" is one of:
#   ok       — solid static substitute, cheap to build generically, ship by default
#   caution  — works, but costlier to build generically and/or visually busier
#              than the JS version; make it opt-in, not default
# Nothing here is graded "impossible" — see the module docstring for why.
# Full reasoning per chart lives in README.md's table; this is just the
# short line rendered directly under each chart in the page itself.
# ---------------------------------------------------------------------------
CHARTS = [
    ("Bar (horisontal)", build_bar, "ok", "Ren CSS (div-bredde). Samme teknikk som examples/13. Billigst av de tolv."),
    ("Bar (vertikal)", build_bar_vertical, "ok", "Ren CSS (div-høyde). Samme teknikk som horisontal Bar, bare bunn-justerte kolonner i stedet for rader."),
    ("Bar (horisontal, flere serier)", build_bar_horizontal_multi, "ok", "Ren CSS, gruppert: én rad-gruppe per Q, seks tynne stolper (én per region) i hver gruppe. Fortsatt ingen SVG nødvendig."),
    ("Bar (vertikal, flere serier)", build_bar_vertical_multi, "ok", "Ren CSS, gruppert: én kolonne-gruppe per Q, seks smale stolper side ved side i hver gruppe."),
    ("Pie", build_pie, "ok", "Ren CSS (conic-gradient). Prosentregning gjort her i Python, ikke i nettleseren."),
    ("Doughnut", build_doughnut, "ok", "Ren CSS, som Pie + ett hull. Krever flat bakgrunnsfarge i midten."),
    ("Polar area", build_polar, "ok", "Statisk SVG (bue-kommando). I praksis like rent resultat som Pie, bare med variabel radius i tillegg til vinkel."),
    ("Line", build_line, "ok", "Statisk SVG (polyline). Rett frem å generere for et vilkårlig antall serier/punkter."),
    ("Area", build_area, "caution", "Statisk SVG (polygon). Seks overlappende flater blir visuelt rotete — samme problem som Chart.js-varianten har."),
    ("Radar", build_radar, "caution", "Statisk SVG, mest kode av de tolv (akser + rutenett + polygoner). Fungerer, men dyrest å bygge generisk."),
    ("Scatter", build_scatter, "ok", "Statisk SVG. Løser #13s 'ingen erstatning finnes'-konklusjon for NÅR dataene er kjent ved bygging — se docstring."),
    ("Bubble", build_bubble, "ok", "Statisk SVG, samme teknikk som Scatter, radius i tillegg til posisjon."),
]

BADGE_LABEL = {"ok": "Anbefales som standard", "caution": "Mulig, gjør det valgfritt"}

# ---------------------------------------------------------------------------
# HTML template — plain string with __PLACEHOLDER__ tokens, not an f-string,
# same reasoning as examples/06's build script (embedded CSS is full of
# literal { } that an f-string would need doubled).
# ---------------------------------------------------------------------------
TEMPLATE = """<!DOCTYPE html>
<html lang="nb">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chart-emulering uten JavaScript &mdash; POC</title>
<!--
  Chart-emulering uten JavaScript
  PROVENANCE
    Source data : none — same synthetic regional counts as examples/06-chart-palette-demo/
    Built       : __BUILT__
    Companion to: issue #30, examples/06-chart-palette-demo/, examples/13-js-free-standalone-poc/
    Built by    : RAIWork
    Repo        : tun
    Generator   : examples/14-chart-emulation-nojs-poc/build_chart_emulation_poc.py
  STATUS: exploratory/diagnostic POC. ZERO script elements in this file — see
  the generator's module docstring for why that's possible for all nine
  chart types when data is known at build time, and what that changes
  about examples/13's "no honest substitute" scatter finding.
  Tier 1, STANDALONE: fully self-contained, no server, no CDN, no JS.
-->
<style>
__TOKEN_CSS__

  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:"Eksempel AS",-apple-system,BlinkMacSystemFont,Arial,system-ui,sans-serif;
    font-size:1rem;line-height:1.5}
  header{background:var(--brand-dark);color:var(--palette-on-dark);padding:1.25rem 2rem}
  header h1{margin:0;font-size:1.4rem;font-weight:500}
  header .meta{opacity:.85;font-size:.85rem;line-height:1.5;margin-top:.5rem;max-width:52rem}
  header code{background:rgba(255,255,255,.12);padding:.05rem .3rem;border-radius:.2rem}
  main{padding:1.5rem 2rem;max-width:78rem;margin:0 auto}
  .chart-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1.25rem;align-items:start}
  .chart-card{background:var(--panel);border:1px solid var(--line);border-radius:.375rem;padding:1rem}
  .chart-card h2{margin:0 0 .6rem;font-size:.95rem;font-weight:600;color:var(--ink)}
  .chart-svg{width:100%;height:auto;display:block;margin:0 auto}
  .axis-line{stroke:var(--line);stroke-width:1}
  .axis-label{fill:var(--muted);font-size:9px}
  .grid-ring{stroke:var(--line);fill:none;stroke-width:1}
  .legend{display:flex;flex-wrap:wrap;gap:.4rem .8rem;margin-top:.6rem;font-size:.78rem;color:var(--muted)}
  .legend-chip{display:inline-flex;align-items:center;gap:.3rem}
  .legend-swatch{width:.7rem;height:.7rem;border-radius:.15rem;display:inline-block;flex-shrink:0}
  .bar-chart{display:flex;flex-direction:column;gap:.4rem}
  .bar-row{display:flex;align-items:center;gap:.6rem;font-size:.82rem}
  .bar-label{width:5rem;flex:0 0 auto}
  .bar-track{flex:1;display:flex;align-items:center;gap:.5rem;min-width:0}
  .bar-fill{height:1.1rem;border-radius:.2rem;flex:0 0 auto}
  .bar-value{font-variant-numeric:tabular-nums;white-space:nowrap;flex:0 0 auto}
  .vbar-chart{display:flex;align-items:flex-end;gap:.9rem;height:180px;padding:0 .25rem}
  .vbar-col{display:flex;flex-direction:column;align-items:center;justify-content:flex-end;flex:1;height:100%;min-width:0}
  .vbar-fill{width:65%;border-radius:.25rem .25rem 0 0;min-height:2px}
  .vbar-value{font-size:.72rem;margin-bottom:.25rem;font-variant-numeric:tabular-nums}
  .vbar-label{font-size:.75rem;color:var(--muted);margin-top:.35rem;text-align:center;white-space:normal;line-height:1.2}
  .vbar-multi{display:flex;align-items:flex-end;gap:1.1rem;height:180px;padding:0 .25rem}
  .vbar-group{display:flex;flex-direction:column;align-items:center;flex:1;height:100%;min-width:0}
  .vbar-group-bars{display:flex;align-items:flex-end;gap:2px;height:100%;width:100%;justify-content:center}
  .vbar-group-bar{width:8px;border-radius:.15rem .15rem 0 0;min-height:2px}
  .vbar-group-label{font-size:.75rem;color:var(--muted);margin-top:.35rem}
  .hbar-multi{display:flex;flex-direction:column;gap:1rem}
  .hbar-group{display:flex;align-items:center;gap:.6rem}
  .hbar-group-label{font-size:.78rem;font-weight:600;color:var(--ink);flex:0 0 1.6rem}
  .hbar-group-bars{display:flex;flex-direction:column;gap:1px;flex:1;min-width:0}
  .hbar-row{display:flex;align-items:center;gap:.4rem;height:.85rem}
  .hbar-fill{height:100%;border-radius:.15rem;flex:0 0 auto;min-width:2px}
  .hbar-val{font-size:.68rem;color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums;flex:0 0 auto}
  .pie-wrap{display:flex;justify-content:center;padding:.5rem 0}
  .pie-circle{width:170px;height:170px;border-radius:50%;position:relative}
  .doughnut-hole{position:absolute;inset:32px;border-radius:50%;background:var(--panel)}
  .verdict{display:inline-block;margin-top:.7rem;padding:.25rem .55rem;border-radius:.2rem;
    font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.02em}
  .verdict-ok{background:#e3f5ea;color:#0a6b39;border:1px solid #0a6b39}
  .verdict-caution{background:#fff3e0;color:#8a5300;border:1px solid #8a5300}
  .verdict-note{font-size:.8rem;color:var(--muted);margin:.4rem 0 0}
  .about{margin-top:2rem;padding-top:1.5rem;border-top:1px solid var(--line);max-width:56rem}
  .about code{background:var(--panel);padding:.1rem .3rem;border-radius:.2rem}
  .note{background:var(--panel);border:1px dashed var(--line);border-radius:.25rem;padding:1rem;
    font-size:.875rem;color:var(--muted);margin-top:1.5rem}
</style>
</head>
<body>
<header>
  <h1>Chart-emulering uten JavaScript &mdash; tolv diagramtyper, &eacute;n palett</h1>
  <div class="meta">Samme datasett og samme Okabe&ndash;Ito-palett som
    <code>examples/06-chart-palette-demo/</code>s &laquo;Kategorisk&raquo;-fane (ni av de tolv
    typene under) &mdash; utvidet med tre stolpevarianter examples/06 ikke har (vertikal,
    og gruppert flere-serier i begge retninger). Denne filen har <strong>null</strong>
    <code>&lt;script&gt;</code>-tagger. Alt er CSS (<code>conic-gradient</code>, div-bredde/h&oslash;yde)
    eller statisk, forh&aring;ndsberegnet SVG. &Eacute;n palett er nok til &aring; vurdere
    teknikken &mdash; se README.md for full begrunnelse per diagramtype.</div>
</header>
<main>
  <div class="chart-grid">
__CHART_CARDS__
  </div>

  <div class="about">
    <h2>Hva dette beviser &mdash; og ikke</h2>
    <p>Beviser: alle tolv diagramtypene her &mdash; ni Chart.js-typer fra <code>examples/06</code>
      pluss tre stolpevarianter (vertikal, og flere serier i begge retninger) &mdash; lar seg
      gjengi uten JavaScript n&aring;r dataene er kjent p&aring; byggetidspunktet &mdash;
      forskjellen mellom dem ligger i hvor mye kode en generisk generator trenger og hvor
      visuelt tett resultatet blir, ikke i en hard mulig/umulig-grense.</p>
    <p>Beviser <strong>ikke</strong>: at dette b&oslash;r v&aelig;re standardoppf&oslash;rsel for
      alle rapporter. Interaktivitet (hover-tooltip med eksakt verdi, zoom, skjul/vis serie ved
      klikk p&aring; forklaring) mangler helt her, p&aring; alle tolv &mdash; det er samme
      begrensning for alle diagramtypene, ikke noe som skiller dem fra hverandre. Og dataene m&aring;
      v&aelig;re kjent f&oslash;r filen genereres; en side som skal vise data brukeren selv
      laster opp eller filtrerer interaktivt trenger fortsatt JavaScript, uansett diagramtype.</p>
    <div class="note">
      Byggetidspunkt: __BUILT__ &middot; generert av <code>build_chart_emulation_poc.py</code>,
      aldri h&aring;ndskrevet.
    </div>
  </div>
</main>
</body>
</html>
"""

CARD_TEMPLATE = """    <div class="chart-card">
      <h2>{title}</h2>
      {body}
      <div><span class="verdict verdict-{grade}">{badge}</span></div>
      <p class="verdict-note">{note}</p>
    </div>
"""

cards = []
for title, builder, grade, note in CHARTS:
    cards.append(CARD_TEMPLATE.format(title=title, body=builder(), grade=grade, badge=BADGE_LABEL[grade], note=note))

html = (
    TEMPLATE.replace("__TOKEN_CSS__", TOKEN_CSS)
    .replace("__CHART_CARDS__", "".join(cards))
    .replace("__BUILT__", BUILT)
)

OUT.write_text(html, encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
print("next: python3 ../../tools/verify_standalone_core.py " + str(OUT))


