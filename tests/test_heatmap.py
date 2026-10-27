#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The heatmap: one number per row-and-column cell, shaded on a stated scale.

A heatmap is the easiest artefact in this repo to draw wrongly, because every mistake is
invisible in a screenshot: a shade nobody can convert back into a number, a legend whose
ranges do not match the shades actually used, an empty cell drawn as zero, a ramp that is not
ordered, white text on a pale cell. This suite checks the properties that make the page mean
what it says:

  1. every figure in a cell is this suite's own aggregation of the extract, computed here.
     Colouring by one number and printing another is the failure a reader cannot see
  2. the legend explains the drawing: each cell's shade is the band the PRINTED ranges put its
     value in. The ranges are rounded to what the page prints, so this is the check that would
     catch a legend saying "13-28" while a cell holding 28 sits one band lighter
  3. an empty cell is hatched and says so. A cell that genuinely holds 0 is shaded, because
     "no cases" and "no cases recorded" are two different findings
  4. the ramp is one hue with strictly decreasing lightness, so the shade carries direction
  5. every cell's own figure has a contrast of at least 4.5:1 against its own fill, measured
     here from the colours on the page. verify_a11y passes white-on-pale-grey SVG text, so
     nothing else in the gate would notice
  6. the row totals, the column totals and the grand total are sums this suite takes itself
  7. --clamp states a top, the darkest shade means "at least" it, and the page counts how
     many cells sit above
  8. refusals name what to fix: a negative value, a column name too long for a cell, too many
     columns or rows, a non-numeric measure, an order that drops a value, a clamp under the
     lowest value
  9. no script, and the English build carries none of the page's Norwegian words
 10. the committed example is the builder's own output, byte for byte
 11. five mutations, each tripping exactly the check it should

Stdlib for the arithmetic.

    python3 tests/test_heatmap.py
"""
from __future__ import annotations

import csv
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_heatmap.py"
EXAMPLE = ROOT / "examples" / "43-heatmap"
DATA = EXAMPLE / "henvendelser.csv"
PIN = "1792836000"          # a fixed clock: one input, one file, on any day

sys.path.insert(0, str(ROOT / "tools"))
import build_heatmap as B  # noqa: E402  the constants the geometry is checked against

FAILURES: list[str] = []
CHECKS = 0


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    mark = "\u2713" if ok else "\u2717"
    print(f"  {mark} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


# ------------------------------------------------------------------------------- helpers
def run(data: pathlib.Path, out: pathlib.Path, *extra: str,
        tools: pathlib.Path | None = None, lang: str = "nb") -> subprocess.CompletedProcess:
    builder = (tools / "build_heatmap.py") if tools else BUILDER
    args = [sys.executable, str(builder), "--data", str(data),
            "--row", "Enhet", "--col", "Uke", "--measure", "Antall",
            "--title", "Henvendelser per enhet og uke",
            "--source", "Syntetisk eksempeldata (henvendelser.csv)",
            "--requested-by", "Kundeservice", "--lang", lang, "--out", str(out), *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env)


def scratch(root: pathlib.Path, *pairs: tuple[str, str]) -> pathlib.Path:
    """A copy of tools/ and templates/ a mutation can break without touching the repo."""
    tools = root / "tools"
    tools.mkdir(parents=True)
    for name in ("build_heatmap.py", "build_size.py", "build_stamp.py", "feedback_link.py",
                 "i18n.py", "tun_core.py", "tun_tokens.py"):
        shutil.copy2(ROOT / "tools" / name, tools / name)
    # tun_tokens resolves the token files from its own location, so the scratch tree needs them:
    # the template carries {{TOKEN_CSS}} and the builder cannot produce a page without the seam.
    shutil.copytree(ROOT / "tools" / "tokens", tools / "tokens")
    shutil.copytree(ROOT / "templates", root / "templates")
    target = tools / "build_heatmap.py"
    text = target.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            raise SystemExit(f"the mutation does not apply: {old[:70]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")
    return tools


def num(text: str) -> float:
    t = re.sub(r"[\s\u00a0\u2009\u2265]", "", text).replace("\u2212", "-")
    return float(t.replace(",", "."))


def own_cells(path: pathlib.Path, agg: str = "sum") -> tuple[dict, set, set]:
    """This suite's own aggregation of the extract, straight from the CSV."""
    total: dict[tuple[str, str], float] = {}
    counted: dict[tuple[str, str], int] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            work = row["Enhet"].strip()
            week = row["Uke"].strip()
            if not work or not week:
                continue
            total[(work, week)] = total.get((work, week), 0.0) + float(row["Antall"])
            counted[(work, week)] = counted.get((work, week), 0) + 1
    if agg == "mean":
        return ({k: v / counted[k] for k, v in total.items()},
                {w for w, _ in total}, {c for _, c in total})
    if agg == "count":
        return {k: float(v) for k, v in counted.items()}, {w for w, _ in total}, \
               {c for _, c in total}
    return total, {w for w, _ in total}, {c for _, c in total}


def rownames_of(html: str) -> list[str]:
    return [re.sub(r"<[^>]+>", "", m) for m in
            re.findall(r'<text class="hm-rname"[^>]*>(.*?)</text>', html, re.S)]


def colnames_of(html: str) -> list[str]:
    return [re.sub(r"<[^>]+>", "", m) for m in
            re.findall(r'<text class="hm-chead"[^>]*>(.*?)</text>', html, re.S)]


def ramp_of(html: str) -> dict[int, dict]:
    """The printed ramp, read from the page's own CSS: each band's fill and its ink.

    The bands are classes rather than inline attributes, because the same page has to answer
    the media query with a different ramp, and an inline fill cannot be re-pointed by CSS.
    The dark block repeats the same selectors, so the FIRST rule for a band wins: the light
    block is written before it, and a later duplicate must not overwrite it.
    """
    bands: dict[int, dict] = {}
    for n, fill, ink in re.findall(
            r"\.hm-b(\d+)\{fill:(#[0-9a-f]{6})\}\s*\.hm-b\1 \.hm-val\{fill:(#[0-9a-f]{6})\}",
            html):
        bands.setdefault(int(n), {"fill": fill, "ink": ink})
    if not bands:  # a single-band page writes one rule and no ink pair
        for n, fill in re.findall(r"\.hm-b(\d+)\{fill:(#[0-9a-f]{6})\}", html):
            bands.setdefault(int(n), {"fill": fill, "ink": None})
    return bands


def cells_of(html: str) -> list[dict]:
    """Every drawn cell: its shade, the ink, the printed figure and where it sits."""
    out = []
    ramp = ramp_of(html)
    for block in re.findall(r'<g class="hm-cell([^"]*)">(?:<title>.*?</title>)?(.*?)</g>',
                            html, re.S):
        classes, body = block
        rect = re.search(r'<rect class="hm-box" x="([\d.]+)" y="([\d.]+)" '
                         r'width="([\d.]+)" height="([\d.]+)"', body)
        text = re.search(r'<text class="hm-val"[^>]*>(.*?)</text>', body, re.S)
        if not rect or not text:
            continue
        band = re.search(r"hm-b(\d+)", classes)
        hatch = "hm-none" in classes
        resolved = ramp.get(int(band.group(1))) if band else None
        out.append({"x": float(rect.group(1)), "y": float(rect.group(2)),
                    "w": float(rect.group(3)),
                    "fill": resolved["fill"] if resolved else ("url(#hm-none)" if hatch else None),
                    "ink": resolved["ink"] if resolved else None,
                    "text": re.sub(r"<[^>]+>", "", text.group(1)).strip(),
                    "hatch": hatch})
    return out


def grid_of(html: str) -> tuple[list[str], list[str], dict]:
    """Cells keyed by (row name, column name), from the page's own geometry."""
    rows, cols = rownames_of(html), colnames_of(html)
    cells = cells_of(html)
    if not cells:
        return rows, cols, {}
    x0, y0 = cells[0]["x"], cells[0]["y"]
    pitch = cells[1]["x"] - cells[0]["x"] if len(cells) > 1 else cells[0]["w"] + 2
    row_h = B.ROW_H
    grid = {}
    for cell in cells:
        j = round((cell["x"] - x0) / pitch)
        i = round((cell["y"] - y0) / row_h)
        if 0 <= i < len(rows) and 0 <= j < len(cols):
            grid[(rows[i], cols[j])] = cell
    return rows, cols, grid


def legend_of(html: str) -> list[dict]:
    """The printed bands in the order they are drawn: their range text and their colour."""
    block = html[html.index('class="legend"'):]
    block = block[:block.index("</ul>")]
    ramp = ramp_of(html)
    bands = []
    for item in re.findall(r"<li>(.*?)</li>", block, re.S):
        inline = re.search(r'background:(#[0-9a-f]{6})', item)
        swatch = re.search(r'class="sw hm-b(\d+)"', item)
        fill = (inline.group(1) if inline else
                ramp[int(swatch.group(1))]["fill"] if swatch and int(swatch.group(1)) in ramp
                else None)
        text = re.sub(r"<[^>]+>", "", item).strip()
        bands.append({"fill": fill, "text": text})
    return bands


def luminance(colour: str) -> float:
    value = colour.lstrip("#")
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def table_of(html: str) -> tuple[list[list[str]], list[str]]:
    start = html.index('aria-labelledby="tbl-h"')
    block = html[start:html.index("</table>", start)]
    body = block[block.index("<tbody>"):block.index("</tbody>")]
    foot = block[block.index("<tfoot>"):block.index("</tfoot>")]
    def rows_in(piece: str) -> list[list[str]]:
        out = []
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", piece, re.S):
            out.append([re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
                        for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)])
        return out
    return rows_in(body), rows_in(foot)


def band_for(value: float, bands: list[dict]) -> dict | None:
    """The band the PRINTED ranges put this value in: the reader's own reading of the legend."""
    shaded = [b for b in bands if b["fill"]]
    for i, band in enumerate(shaded):
        if band["text"].startswith("\u2265") or band["text"].startswith("≥"):
            if value >= num(band["text"]):
                return band
            continue
        if "\u2013" not in band["text"]:
            continue
        low, high = band["text"].split("\u2013")
        if num(low) <= value < num(high):
            return band
    return shaded[-1] if shaded else None


def distinct_bands(html: str) -> list[dict]:
    """The legend bands with a colour, in order, which the ramp checks walk."""
    return [band for band in legend_of(html) if band["fill"]]


# --------------------------------------------------------------------------------- main
def main() -> int:
    if not DATA.is_file():
        raise SystemExit(f"{DATA} is missing; run examples/43-heatmap/generate_data.py")
    values, rows_in_data, cols_in_data = own_cells(DATA)

    with tempfile.TemporaryDirectory() as raw:
        work = pathlib.Path(raw)

        print("1. the example builds, and every cell carries this suite's own number")
        out = work / "hm.html"
        done = run(DATA, out)
        chk(done.returncode == 0, "the builder exits 0", (done.stderr or "")[-500:])
        page = out.read_text(encoding="utf-8")
        rows, cols, grid = grid_of(page)
        chk(sorted(rows) == sorted(rows_in_data), "every row in the extract is drawn",
            f"{rows} vs {sorted(rows_in_data)}")
        chk(sorted(cols) == sorted(cols_in_data), "every column in the extract is drawn",
            f"{cols} vs {sorted(cols_in_data)}")
        bad = []
        for key, want in values.items():
            cell = grid.get(key)
            if cell is None or cell["hatch"]:
                bad.append(f"{key} missing")
                continue
            if abs(num(cell["text"]) - round(want)) > 0.01:
                bad.append(f"{key}: {cell['text']} vs {want}")
        chk(not bad, "each printed figure is this suite's own sum", "; ".join(bad[:3]))
        chk(f"cells         : {len(values)} of {len(rows) * len(cols)}" in done.stdout,
            "the build prints how many cells have a value", done.stdout)

        print("\n2. the legend explains the drawing")
        bands = legend_of(page)
        chk(len(distinct_bands(page)) == B.BINS, "the legend prints one swatch per band",
            str(len(distinct_bands(page))))
        chk(any("Ingen data" in b["text"] or "No data" in b["text"] for b in bands),
            "and one for a cell with no data")
        bad = []
        for key, want in values.items():
            cell = grid.get(key)
            band = band_for(round(want), bands)
            if cell is None or band is None:
                continue
            if cell["fill"].lower() != band["fill"].lower():
                bad.append(f"{key}={want}: drawn {cell['fill']} but the legend puts it in "
                           f"{band['text']} {band['fill']}")
        chk(not bad, "each cell's shade is the band its own value falls in", "; ".join(bad[:2]))
        ranges = [b["text"] for b in distinct_bands(page)]
        edges = [num(r.split("\u2013")[0]) for r in ranges]
        tops = [num(r.split("\u2013")[1]) for r in ranges[:-1]]
        joined = tops == edges[1:]
        chk(joined, "the printed ranges join, with no gap and no overlap", str(ranges))
        chk(ranges[-1].startswith("\u2265"),
            "the top band is open ended, so the largest value has a band", ranges[-1])

        print("\n3. an empty cell is hatched, and a real zero is not")
        absent = {(r, c) for r in rows_in_data for c in cols_in_data} - set(values)
        hatched = {k for k, cell in grid.items() if cell["hatch"]}
        chk(hatched == absent, "exactly the cells with no rows are hatched",
            f"{sorted(hatched)} vs {sorted(absent)}")
        chk(all(grid[k]["text"] == "\u2013" for k in absent if k in grid),
            "and they carry the dash rather than a figure")
        zero_csv = work / "zero.csv"
        with zero_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Enhet", "Uke", "Antall"])
            writer.writerows([["Oslo", "2026-W01", 5], ["Oslo", "2026-W02", 0],
                              ["Agder", "2026-W01", 0], ["Agder", "2026-W02", 7]])
        zero_out = work / "zero.html"
        done = run(zero_csv, zero_out)
        chk(done.returncode == 0, "a file holding a real zero builds", (done.stderr or "")[-300:])
        _zr, _zc, zgrid = grid_of(zero_out.read_text(encoding="utf-8"))
        zero_cells = [c for c in zgrid.values() if not c["hatch"] and c["text"] == "0"]
        chk(len(zero_cells) == 2, "the two zeros are shaded, not hatched",
            str([(k, v['text'], v['hatch']) for k, v in zgrid.items()]))

        print("\n4. the ramp is one hue, strictly ordered, and every figure is legible")
        stops = [b["fill"] for b in distinct_bands(page)]
        lums = [luminance(stop) for stop in stops]
        chk(all(a > b for a, b in zip(lums, lums[1:])),
            "each shade is darker than the one before", str([round(l, 3) for l in lums]))
        def hue(hexcode: str) -> float:
            r, g, b = (int(hexcode.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
            mx, mn = max(r, g, b), min(r, g, b)
            if mx == mn:
                return 0.0
            d = mx - mn
            if mx == r:
                h = ((g - b) / d) % 6
            elif mx == g:
                h = (b - r) / d + 2
            else:
                h = (r - g) / d + 4
            return h * 60

        # The old check was `g == b`, which is true of a teal and of nothing else: it passed
        # because the ramp's base happened to have two equal channels, not because the ramp
        # held one hue. Measure the hue instead, so the claim survives a change of brand.
        hues = [hue(stop) for stop in stops]
        spread = max(hues) - min(hues)
        chk(spread <= 6,
            "and every shade keeps one hue: the hue spread stays within six degrees",
            f"{[round(h) for h in hues]}, spread {spread:.1f}")
        bad = [f"{k}: {c['ink']} on {c['fill']} = {contrast(c['ink'], c['fill']):.2f}"
               for k, c in grid.items()
               if not c["hatch"] and contrast(c["ink"], c["fill"]) < 4.5]
        chk(not bad, "every printed figure reaches 4.5:1 against its own fill",
            "; ".join(bad[:3]))

        print("\n5. the totals are sums this suite takes itself")
        body, foot = table_of(page)
        chk(len(body) == len(rows), "the table has one row per row", str(len(body)))
        bad = []
        for row in body:
            name = row[0]
            figures = [num(cell) for cell in row[1:-1] if cell.strip() not in ("\u2013", "")]
            want = sum(v for (r, _c), v in values.items() if r == name)
            if abs(num(row[-1]) - round(want)) > 0.01:
                bad.append(f"{name}: {row[-1]} vs {want}")
            if figures and abs(sum(figures) - num(row[-1])) > 0.01:
                bad.append(f"{name}: cells {figures} do not add to {row[-1]}")
        chk(not bad, "each row total is that row's cells added up", "; ".join(bad[:2]))
        foot_row = foot[0] if foot else []
        bad = []
        for j, name in enumerate(cols):
            want = sum(v for (_r, c), v in values.items() if c == name)
            if abs(num(foot_row[j + 1]) - round(want)) > 0.01:
                bad.append(f"{name}: {foot_row[j + 1]} vs {want}")
        chk(not bad, "each column total is that column's cells added up", "; ".join(bad[:2]))
        chk(abs(num(foot_row[-1]) - round(sum(values.values()))) <= 0.5,
            "and the grand total is every cell", f"{foot_row[-1]} vs {sum(values.values())}")

        print("\n6. a stated top: the darkest shade means at least that much")
        top = 60.0
        capped = work / "cap.html"
        done = run(DATA, capped, "--clamp", str(top))
        chk(done.returncode == 0, "the clamped build runs", (done.stderr or "")[-300:])
        cap_page = capped.read_text(encoding="utf-8")
        _cr, _cc, cgrid = grid_of(cap_page)
        over = [v for v in values.values() if v > top]
        dark = distinct_bands(cap_page)[-1]
        band_low = num(dark["text"])
        in_dark = {k for k, c in cgrid.items()
                   if c["fill"].lower() == dark["fill"].lower() and not c["hatch"]}
        want_dark = {k for k, v in values.items() if v >= band_low}
        chk(in_dark == want_dark, "the darkest shade is the top band and nothing else",
            f"{sorted(in_dark)} vs {sorted(want_dark)}")
        chk(all(values[k] > top for k in in_dark if values[k] > top) and over,
            "and it starts below the stated top, so the top is not a floor on the drawing",
            f"{len(over)} cell(s) above {top}, band starts at {band_low}")
        chk(dark["text"].startswith("\u2265"), "the top band prints 'at least'", dark["text"])
        chk(f"{len(over)}" in cap_page and "over toppen" in cap_page,
            "and the page counts how many cells sit above it")

        print("\n7. averaging and counting are labelled as themselves")
        for agg, expect in (("mean", "Gjennomsnitt"), ("count", "Antall rader")):
            agg_out = work / f"{agg}.html"
            done = run(DATA, agg_out, "--agg", agg)
            chk(done.returncode == 0, f"the --agg {agg} build runs", (done.stderr or "")[-300:])
            agg_page = agg_out.read_text(encoding="utf-8")
            _ar, _ac, agrid = grid_of(agg_page)
            wanted, _w, _c = own_cells(DATA, agg)
            bad = [f"{k}: {agrid[k]['text']} vs {wanted[k]}"
                   for k in wanted if k in agrid
                   and abs(num(agrid[k]["text"]) - wanted[k]) > 0.01]
            chk(not bad, f"each --agg {agg} figure is this suite's own", "; ".join(bad[:2]))
            chk(expect in agg_page, f"and the total column says {expect!r}, not 'Sum'")
        chk("ikke det samme som gjennomsnittet" in (work / "mean.html").read_text(
            encoding="utf-8"), "the average build says its total is not the overall average")

        print("\n8. refusals name what to fix")
        def refuses(text: str, what: str, data: pathlib.Path = DATA,
                    extra: tuple[str, ...] = (), measure: bool = True) -> None:
            args = [sys.executable, str(BUILDER), "--data", str(data), "--row", "Enhet",
                    "--col", "Uke", "--title", "t",
                    "--out", str(work / f"r{abs(hash(what)) % 9999}.html"), *extra]
            if measure:
                args += ["--measure", "Antall"]
            done = subprocess.run(args, capture_output=True, text=True, cwd=ROOT,
                                  env=dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN))
            chk(done.returncode != 0 and text in done.stderr, what,
                (done.stderr or done.stdout)[-240:])

        negative = work / "negative.csv"
        with negative.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Enhet", "Uke", "Antall"])
            writer.writerows([["Oslo", "2026-W01", 5], ["Oslo", "2026-W02", -3],
                              ["Agder", "2026-W01", 7]])
        refuses("holds a negative value", "a negative value, named", data=negative)
        refuses("is not above the lowest value", "a clamp below the lowest value",
                extra=("--clamp", "5"))
        refuses("Pass the numeric column", "no measure", measure=False)

        letters = work / "letters.csv"
        with letters.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Enhet", "Uke", "Antall"])
            writer.writerows([["Oslo", "2026-W01", "mange"], ["Agder", "2026-W01", 7]])
        refuses("must hold numbers", "a measure that is not a number", data=letters)

        wide = work / "wide.csv"
        with wide.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Enhet", "Uke", "Antall"])
            writer.writerows([["Oslo", f"2026-W{i:02d}", i] for i in range(1, B.MAX_COLS + 2)])
        refuses("at most", "more columns than the page can label", data=wide)

        tall = work / "tall.csv"
        with tall.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Enhet", "Uke", "Antall"])
            writer.writerows([[f"Enhet {i}", "2026-W01", i] for i in range(1, B.MAX_ROWS + 2)])
        refuses("at most", "more rows than the page can draw", data=tall)

        long_col = work / "long-col.csv"
        with long_col.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Enhet", "Uke", "Antall"])
            writer.writerows([["Oslo", "veke " + "x" * 40, 5]]
                             + [["Oslo", f"2026-W{i:02d}", 5 + 10 * i] for i in range(2, 9)])
        refuses("Shorten the column names", "a column name wider than a cell", data=long_col)

        refuses("does not name 5 value", "an order that leaves a value out",
                extra=("--row-order", "Oslo"))
        refuses("is not a value in", "an order that invents a value",
                extra=("--row-order", "Oslo,Agder,Bergen"))

        print("\n9. no script, and the English build carries none of the page's words")
        chk("<script" not in page.lower(), "the page holds no script element")
        chk(not re.search(r'(src|href)="(https?:)?//', page), "and fetches nothing")
        en_out = work / "en.html"
        done = run(DATA, en_out, lang="en")
        en = en_out.read_text(encoding="utf-8")
        chk(done.returncode == 0, "the English build runs", (done.stderr or "")[-300:])
        chk('<html lang="en">' in en, "the page declares its language")
        for word in ("Rader", "Skalaen", "Selvstendig", "Bygget", "Ingen data", "høyeste"):
            chk(word not in en, f"and not the Norwegian {word!r}")

        print("\n10. the committed example is the builder's own output")
        fresh = work / "fresh.html"
        run(DATA, fresh)
        chk(fresh.read_bytes() == (EXAMPLE / "varmekart.html").read_bytes(),
            "a pinned rebuild equals the committed file byte for byte")

        print("\n11. the mutations")
        # 1. the ink assumed dark, so the darkest cells swallow their own figure.
        one = work / "m1"
        one.mkdir()
        tools = scratch(one, ('    return hexa(INK) if contrast(fill, INK) >= contrast(fill, WHITE) '
                              'else "#ffffff"', '    return hexa(INK)'))
        out1 = work / "m1.html"
        done = run(DATA, out1, tools=tools)
        chk(done.returncode == 0, "the dark-ink mutation still builds", (done.stderr or "")[-260:])
        _r1, _c1, g1 = grid_of(out1.read_text(encoding="utf-8"))
        low = [f"{k}: {contrast(c['ink'], c['fill']):.2f}" for k, c in g1.items()
               if not c["hatch"] and contrast(c["ink"], c["fill"]) < 4.5]
        chk(bool(low), "dark ink on a dark fill is caught by the contrast check", "; ".join(low[:2]))

        # 2. an empty cell drawn in the palest shade instead of hatched: zero by another name.
        two = work / "m2"
        two.mkdir()
        tools = scratch(two, ('                css, fill, text, label = " hm-none", \' '
                              'fill="url(#hm-none)"\', t["dash"], \\',
                              '                css, fill, text, label = " hm-b0", "", '
                              't["dash"], \\'))
        out2 = work / "m2.html"
        done = run(DATA, out2, tools=tools)
        chk(done.returncode == 0, "the unhatched mutation still builds", (done.stderr or "")[-260:])
        _r2, _c2, g2 = grid_of(out2.read_text(encoding="utf-8"))
        chk(not any(c["hatch"] for c in g2.values()),
            "a missing cell drawn as a shade is caught: nothing is hatched any more")

        # 3. the legend prints rounded edges but the drawing uses the unrounded ones.
        three = work / "m3"
        three.mkdir()
        tools = scratch(three, ("    edges = [_round(low + i * width, decimals) for i in "
                                "range(BINS + 1)]",
                                "    edges = [low + i * width for i in range(BINS + 1)]"))
        # The example data holds no value that sits between a rounded edge and the exact one,
        # so the mutation would be invisible on it: the fixture has to straddle the edge.
        edge_csv = work / "edge.csv"
        with edge_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Enhet", "Uke", "Antall"])
            writer.writerows([["Oslo", "2026-W01", 13], ["Oslo", "2026-W02", 28],
                              ["Agder", "2026-W01", 90], ["Agder", "2026-W02", 51]])
        clean = work / "edge-clean.html"
        done = run(edge_csv, clean)
        chk(done.returncode == 0, "the straddling fixture builds unchanged",
            (done.stderr or "")[-260:])
        out3 = work / "m3.html"
        done = run(edge_csv, out3, tools=tools)
        chk(done.returncode == 0, "the unrounded-edge mutation still builds",
            (done.stderr or "")[-260:])
        m3 = out3.read_text(encoding="utf-8")
        _r3, _c3, g3 = grid_of(m3)
        bands3 = legend_of(m3)
        off = [f"{k}={v}" for k, v in
               {("Oslo", "2026-W01"): 13, ("Oslo", "2026-W02"): 28,
                ("Agder", "2026-W01"): 90, ("Agder", "2026-W02"): 51}.items()
               if k in g3 and not g3[k]["hatch"]
               and g3[k]["fill"].lower() != (band_for(v, bands3) or {}).get("fill", "").lower()]
        chk(bool(off), "a shade that disagrees with the printed range is caught", str(off[:2]))
        clean_page = clean.read_text(encoding="utf-8")
        _r4, _c4, gclean = grid_of(clean_page)
        clean_bands = legend_of(clean_page)
        fixture = {("Oslo", "2026-W01"): 13, ("Oslo", "2026-W02"): 28,
                   ("Agder", "2026-W01"): 90, ("Agder", "2026-W02"): 51}
        wrong = [f"{k}={v}: {gclean[k]['fill']} vs {band_for(v, clean_bands)['fill']}"
                 for k, v in fixture.items()
                 if k in gclean and gclean[k]["fill"].lower()
                 != (band_for(v, clean_bands) or {}).get("fill", "").lower()]
        chk(not wrong, "the unmutated build puts all four values in their printed band",
            "; ".join(wrong))

        # 4. the row total taken from the first cell instead of the sum of them.
        four = work / "m4"
        four.mkdir()
        tools = scratch(four, ('        rows.append({"name": name, "values": values, '
                              '"total": sum(values.values())})',
                              '        rows.append({"name": name, "values": values, '
                              '"total": (list(values.values()) or [0])[0]})'))
        out4 = work / "m4.html"
        done = run(DATA, out4, tools=tools)
        chk(done.returncode == 0, "the wrong-total mutation still builds", (done.stderr or "")[-260:])
        body4, _f4 = table_of(out4.read_text(encoding="utf-8"))
        name = body4[0][0]
        want = sum(v for (r, _c), v in values.items() if r == name)
        chk(abs(num(body4[0][-1]) - round(want)) > 0.01,
            "a row total that is not the row's sum is caught", f"{body4[0][-1]} vs {want}")

        # 5. the ramp reversed, so a darker cell means less.
        five = work / "m5"
        five.mkdir()
        tools = scratch(five, ('             "fill": RAMP[i], "dark": RAMP_DARK[i], '
                               '"ink": ink_for(RAMP[i]),',
                               '             "fill": RAMP[BINS - 1 - i], '
                               '"dark": RAMP_DARK[BINS - 1 - i], '
                               '"ink": ink_for(RAMP[BINS - 1 - i]),'))
        out5 = work / "m5.html"
        done = run(DATA, out5, tools=tools)
        chk(done.returncode == 0, "the reversed-ramp mutation still builds",
            (done.stderr or "")[-260:])
        lums5 = [luminance(b["fill"]) for b in distinct_bands(out5.read_text(encoding="utf-8"))]
        chk(not all(a > b for a, b in zip(lums5, lums5[1:])),
            "a ramp whose darkest shade carries the smallest value is caught",
            str([round(l, 3) for l in lums5]))

    print()
    if FAILURES:
        print(f"{CHECKS - len(FAILURES)} passed, {len(FAILURES)} failed")
        for f in FAILURES:
            print(f"  \u2717 {f}")
        return 1
    print(f"{CHECKS} passed, 0 failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
