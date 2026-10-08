#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
build_cube_dashboard.py — build a single-file dashboard backed by a dense OLAP cube.

Where `build_dashboard.py` inlines *rows*, this inlines a *pre-aggregated cube*: one
cell per combination of the dimensions the dashboard can actually filter on. Row count
stops mattering; only dimension cardinality does. 4 000 000 source rows collapse to
115 200 cells and 0.67 MB of base64 inside the .html.

The cube is stored as dense typed arrays in canonical dimension order, so no keys are
written at all — a cell's position *is* its coordinate. That array is gzipped and
base64-inlined, and the browser inflates it with the native `DecompressionStream`
(no library, and verified to work from a `file://` page).

    python3 tools/build_cube_dashboard.py \
        --data transaksjoner.csv \
        --dims region,kategori,kanal,aldersgruppe \
        --time dato --time-grain month \
        --measures belop:sum,antall:sum \
        --title "Transaksjonsoversikt" \
        --requested-by "Analyseteamet" \
        --out dashboards/transaksjoner.html

Stdlib only, on purpose — same contract as the rest of tools/. Input: .csv, .tsv,
.json (array of objects). For .xlsx or Parquet, convert first; the `tun-data`
skill does that.

Read docs/07-portable-cube.md before changing the encoding — the browser side in
templates/cube-dashboard.html has to agree with it byte for byte.
"""
from __future__ import annotations

import argparse
import array
import base64
import csv
import datetime as dt
import json
import pathlib
import struct
import sys
import zlib

TEMPLATE = pathlib.Path(__file__).resolve().parents[1] / "templates" / "cube-dashboard.html"

# Colours come from tools/tun_tokens.py, never from the template. The cube template
# defines its own neutral greys and uses only the palette slots, so no theme file is
# inlined (core_files=()).
TOOLS_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
import feedback_link  # noqa: E402
import tun_tokens  # noqa: E402

# Bounds the browser's decoded footprint: cells x measures x 4 bytes.
MAX_CELLS_DEFAULT = 2_000_000
SIZE_WARN_MB = 20  # keep in step with docs/02-architecture.md

TIME_GRAINS = ("month", "quarter", "year", "day", "week")
INT32_MAX = 2_147_483_647

# What the provenance block says when nobody named a requester. Never fall back to the
# OS user name: it put the builder's login into every committed artefact (#45).
# A role is what the block wants; pass one with --requested-by.
NOT_STATED = "not stated"


def die(msg: str) -> "None":
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(2)


# --------------------------------------------------------------------------- input
def load_rows(path: pathlib.Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            die(f"{path.name}: expected a JSON array of objects")
        return rows
    if suffix in (".csv", ".tsv", ".txt"):
        delim = "\t" if suffix == ".tsv" else ","
        with path.open(newline="", encoding="utf-8-sig") as fh:
            sample = fh.read(64 * 1024)
            fh.seek(0)
            if suffix != ".tsv":
                try:
                    delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
                except csv.Error:
                    delim = ","
            return list(csv.DictReader(fh, delimiter=delim))
    die(f"{path.name}: unsupported input. Use .csv, .tsv or .json "
        f"(convert .xlsx/.parquet first — see the tun-data skill)")


def to_number(raw) -> float:
    """Tolerant numeric parse: handles '1 234,56', '1,234.56', '', None."""
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip().replace("\u00a0", "").replace(" ", "")
    if not s:
        return 0.0
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rindex(".") > s.rindex(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


_BUCKET_MEMO: "dict[tuple, str]" = {}


def bucket_time(raw, grain: str) -> str:
    """Normalise a date-ish value to a sortable bucket label.

    Memoised: a date column has at most a few thousand distinct values but is read
    once per row, and strptime dominates the build otherwise.
    """
    key = (raw, grain)
    hit = _BUCKET_MEMO.get(key)
    if hit is not None:
        return hit
    out = _bucket_time_uncached(raw, grain)
    _BUCKET_MEMO[key] = out
    return out


def _bucket_time_uncached(raw, grain: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return "(ukjent)"
    d = None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            d = dt.datetime.strptime(s[:len(fmt) + 2].rstrip("Z"), fmt)
            break
        except ValueError:
            continue
    if d is None:
        # already a bucket label such as "2024-05" or a plain year
        return s[:10]
    if grain == "year":
        return f"{d.year}"
    if grain == "quarter":
        return f"{d.year}-Q{(d.month - 1) // 3 + 1}"
    if grain == "week":
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    if grain == "day":
        return d.strftime("%Y-%m-%d")
    return d.strftime("%Y-%m")


# ---------------------------------------------------------------------------- cube
class Measure:
    def __init__(self, spec: str):
        parts = spec.split(":")
        self.field = parts[0].strip()
        self.agg = (parts[1].strip().lower() if len(parts) > 1 else "sum")
        self.unit = (parts[2].strip() if len(parts) > 2 else "")
        if self.agg not in ("sum", "count"):
            die(f"measure {spec!r}: only sum and count are additive over a cube "
                f"(avg is derived in the browser as sum/count)")
        if not self.field:
            die(f"measure {spec!r}: missing field name")
        self.scale = 1
        self.dtype = "i"  # int32; may be promoted to float64


def build_cube(rows, dim_fields, time_field, grain, measures, max_cells):
    # 1. discover every dimension domain in a single pass over the data
    labels: "dict[str, list]" = {}
    dims: list[str] = list(dim_fields) + ([time_field] if time_field else [])
    seen: "dict[str, set]" = {d: set() for d in dims}
    for r in rows:
        for f in dim_fields:
            seen[f].add(str(r.get(f, "") or "(tom)"))
        if time_field:
            seen[time_field].add(bucket_time(r.get(time_field), grain))
    for d in dims:
        labels[d] = sorted(seen[d])
    if not dims:
        die("need at least one --dims entry or a --time field")

    shape = [len(labels[d]) for d in dims]
    n_cells = 1
    for s in shape:
        n_cells *= s
    if n_cells > max_cells:
        worst = max(zip(shape, dims))
        die(f"cube would be {n_cells:,} cells (limit {max_cells:,}). "
            f"Largest dimension is {worst[1]!r} with {worst[0]} values. "
            f"Drop a dimension, or coarsen it (e.g. --time-grain quarter).")

    strides = [1] * len(shape)
    for i in range(len(shape) - 2, -1, -1):
        strides[i] = strides[i + 1] * shape[i + 1]
    index = {d: {v: i for i, v in enumerate(labels[d])} for d in dims}

    # 2. accumulate into dense float64 buffers, then narrow
    acc = [[0.0] * n_cells for _ in measures]
    cnt = array.array("I", bytes(4 * n_cells))
    skipped = 0
    for r in rows:
        pos = 0
        try:
            for k, d in enumerate(dims):
                v = bucket_time(r.get(d), grain) if d == time_field else str(r.get(d, "") or "(tom)")
                pos += index[d][v] * strides[k]
        except KeyError:
            skipped += 1
            continue
        cnt[pos] += 1
        for m, meas in enumerate(measures):
            if meas.agg == "count":
                acc[m][pos] += 1
            else:
                acc[m][pos] += to_number(r.get(meas.field))

    # 3. choose a compact exact encoding per measure
    payload = bytearray()
    for m, meas in enumerate(measures):
        vals = acc[m]
        peak = max((abs(v) for v in vals), default=0.0)
        chosen = None
        for scale in (1, 10, 100):
            scaled = [v * scale for v in vals]
            if peak * scale > INT32_MAX:
                break
            if all(abs(v - round(v)) < 1e-6 for v in scaled):
                chosen = (scale, array.array("i", (int(round(v)) for v in scaled)))
                break
        if chosen is None:
            meas.dtype, meas.scale = "d", 1
            payload += array.array("d", vals).tobytes()
        else:
            meas.scale, buf = chosen
            meas.dtype = "i"
            payload += buf.tobytes()
    payload += cnt.tobytes()

    density = sum(1 for c in cnt if c) / n_cells if n_cells else 0
    return {
        "dims": dims, "shape": shape, "labels": labels, "n": n_cells,
        "measures": [{"field": m.field, "agg": m.agg, "unit": m.unit,
                      "scale": m.scale, "dtype": m.dtype} for m in measures],
        "time_dim": time_field or None,
        "source_rows": len(rows) - skipped,
        "skipped_rows": skipped,
        "density": round(density, 4),
        "raw_bytes": len(payload),
    }, bytes(payload)


# A gzip member header with nothing in it that depends on the machine: no file name,
# mtime 0, XFL 2 (maximum compression), OS 255 (unknown). gzip.compress() does not give
# that across Python builds: before 3.14 it stamps the current time unless told otherwise,
# and with mtime=0 it hands the header to zlib, which writes its own OS code (0x13 on
# macOS) where 3.14 writes 0xff. Same data, different bytes, so a rebuild showed up as a
# diff. The deflate body still comes from the local zlib; equal zlib versions give equal
# bodies, a different zlib may not. templates/cube-dashboard.html only reads the body.
GZIP_HEADER = bytes((0x1F, 0x8B, 8, 0, 0, 0, 0, 0, 2, 0xFF))


def deterministic_gzip(data: bytes) -> bytes:
    """One gzip member: the fixed header above, raw deflate at level 9, CRC32 and size."""
    deflate = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
    body = deflate.compress(data) + deflate.flush()
    return GZIP_HEADER + body + struct.pack("<II", zlib.crc32(data), len(data) & 0xFFFFFFFF)


# ---------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--title", default="Dashboard")
    ap.add_argument("--dims", default="", help="comma-separated filterable dimension columns")
    ap.add_argument("--time", default="", help="date column, becomes the trend axis")
    ap.add_argument("--time-grain", default="month", choices=TIME_GRAINS)
    ap.add_argument("--measures", default="", help="field:agg[:unit], comma-separated. agg = sum|count")
    ap.add_argument("--max-cells", type=int, default=MAX_CELLS_DEFAULT)
    ap.add_argument("--requested-by", default="",
                    help="a role, e.g. \"Salgsavdelingen\". Not a person's name.")
    ap.add_argument("--feedback-to", default="", metavar="ADDRESS_OR_ISSUE_URL",
                    help=feedback_link.FLAG_HELP)
    args = ap.parse_args()

    if not args.data.exists():
        die(f"{args.data} not found")
    if not TEMPLATE.exists():
        die(f"template missing: {TEMPLATE}")

    rows = load_rows(args.data)
    if not rows:
        die(f"{args.data.name} has no rows")

    dim_fields = [d.strip() for d in args.dims.split(",") if d.strip()]
    measures = [Measure(s) for s in args.measures.split(",") if s.strip()] or [Measure("rader:count")]

    have = set(rows[0].keys())
    for f in dim_fields + ([args.time] if args.time else []):
        if f not in have:
            die(f"column {f!r} not in {args.data.name}. Available: {', '.join(sorted(have))}")
    for m in measures:
        if m.agg == "sum" and m.field not in have:
            die(f"measure column {m.field!r} not in {args.data.name}")

    meta, payload = build_cube(rows, dim_fields, args.time or None,
                              args.time_grain, measures, args.max_cells)
    gz = deterministic_gzip(payload)
    b64 = base64.b64encode(gz).decode("ascii")

    meta.update(title=args.title, built=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                # The raw value: "" when nobody was named, so the footer can leave it out.
                # Only the provenance comment spells that out as NOT_STATED.
                requested_by=args.requested_by, source=args.data.name)

    source = (f"{args.data.name} — {meta['source_rows']:,} rows aggregated to "
              f"{meta['n']:,} cube cells over {', '.join(meta['dims'])}")
    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title,
                                           built=meta["built"], source=source)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    token_css, token_source = tun_tokens.load_token_css(core_files=())

    html = (TEMPLATE.read_text(encoding="utf-8")
            .replace("{{TOKEN_CSS}}", token_css)
            .replace("{{META}}", json.dumps(meta, ensure_ascii=False))
            .replace("{{DATA}}", b64)
            .replace("{{TITLE}}", args.title)
            .replace("{{SOURCE_DESCRIPTION}}", source)
            .replace("{{BUILD_TIMESTAMP}}", meta["built"])
            .replace("{{REQUESTED_BY}}", args.requested_by or NOT_STATED)
            # last, so no later replacement rewrites text inside the block
            .replace("{{FEEDBACK_BLOCK}}", feedback))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")

    mb = args.out.stat().st_size / 1e6
    print(f"source rows   : {meta['source_rows']:,}"
          + (f"  ({meta['skipped_rows']:,} skipped)" if meta["skipped_rows"] else ""))
    print(f"cube cells    : {meta['n']:,}  ({meta['density'] * 100:.0f}% populated)")
    print(f"cube raw      : {meta['raw_bytes'] / 1e6:.2f} MB")
    print(f"gzip          : {len(gz) / 1e6:.2f} MB")
    print(f"base64 inlined: {len(b64) / 1e6:.2f} MB")
    print(f"{args.out.name:14}: {mb:.2f} MB")
    print(f"palette       : {token_source}")
    if meta["source_rows"]:
        ratio = meta["source_rows"] / max(1, meta["n"])
        if ratio >= 2:
            print(f"reduction     : {ratio:.0f}x fewer cells than source rows")
        else:
            print(f"reduction     : none — {meta['n']:,} cells for {meta['source_rows']:,} rows")
            print(f"\nwarning: the cube is not smaller than the data ({meta['density'] * 100:.0f}% of cells "
                  f"populated). A dense cube pays off when many rows share a cell. Either drop a "
                  f"dimension / coarsen --time-grain, or inline the rows directly with "
                  f"tools/build_dashboard.py.", file=sys.stderr)
    if mb > SIZE_WARN_MB:
        print(f"\nwarning: {mb:.1f} MB exceeds the {SIZE_WARN_MB} MB Tier 1 budget. "
              f"Coarsen a dimension — see docs/02-architecture.md", file=sys.stderr)
    print(f"\nverify it renders before sharing:\n  python3 tools/verify_dashboard.py {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
