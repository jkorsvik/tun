#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
build_dashboard.py — fill the single-file dashboard template with real data.

Used by the RAIWork skill `dashboard-new`. Stdlib only: no pip install, no
node_modules, nothing for a non-developer to set up.

    python3 tools/build_dashboard.py \
        --data sales.csv \
        --title "Salg per region" \
        --dimension Region --measure Belop --time Maaned \
        --filters Region,Produkt \
        --out dashboards/salg.html

Input formats: .csv, .tsv, .json (array of objects). For .xlsx, convert first
(`dashboard-data` handles that) — we deliberately avoid an Excel dependency here
so the Tier 1 path stays prerequisite-free.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import getpass
import json
import pathlib
import re
import sys

TEMPLATE = pathlib.Path(__file__).resolve().parents[1] / "templates" / "single-file-dashboard.html"

# Colours come from tools/tun_tokens.py, never from the template: it resolves the active
# palette (core's neutral one unless TUN_PALETTE says otherwise), validates every slot,
# and returns the CSS to inline. Named as a constant so a test can point a copy of this
# script at the real tools/ directory.
TOOLS_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
import tun_tokens  # noqa: E402

TOKEN_FILES = ("status-semantic.css", "theme-light.css")

# Anything above this is a Tier 1 violation — see docs/02-architecture.md
SIZE_WARN_MB = 20
SIZE_FAIL_MB = 50


def load_rows(path: pathlib.Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            sys.exit("error: JSON input must be an array of objects")
        return rows
    if suffix in (".csv", ".tsv", ".txt"):
        delim = "\t" if suffix == ".tsv" else ","
        with path.open(newline="", encoding="utf-8-sig") as fh:
            sample = fh.read(8192)
            fh.seek(0)
            if suffix != ".tsv":
                try:
                    delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
                except csv.Error:
                    delim = ","
            return list(csv.DictReader(fh, delimiter=delim))
    sys.exit(f"error: unsupported input {suffix!r}. Convert to csv/tsv/json first.")


def coerce_numbers(rows: list[dict]) -> list[dict]:
    """Turn numeric-looking strings into real numbers so charts and sorting work.

    Handles Norwegian formatting: '1 234,56' and '1.234,56' both become 1234.56.
    A column is only converted if EVERY non-empty value in it parses — otherwise
    we would silently corrupt an ID column that happens to look numeric.
    """
    if not rows:
        return rows
    cols = list(rows[0].keys())
    numeric_cols = []
    for col in cols:
        values = [r.get(col) for r in rows]
        non_empty = [v for v in values if v not in (None, "")]
        if not non_empty or not all(isinstance(v, str) for v in non_empty):
            continue
        if all(_parse_num(v) is not None for v in non_empty):
            numeric_cols.append(col)
    for row in rows:
        for col in numeric_cols:
            if row.get(col) not in (None, ""):
                row[col] = _parse_num(row[col])
            elif col in row:
                row[col] = 0
    return rows


def _parse_num(value):
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        return None
    s = value.strip().replace("\u00a0", "").replace(" ", "")
    if not s:
        return None
    # Norwegian: comma is the decimal separator, dot/space the thousands sep
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    s = s.rstrip("%")
    try:
        f = float(s)
    except ValueError:
        return None
    return int(f) if f.is_integer() and abs(f) < 2**53 else f


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, type=pathlib.Path)
    ap.add_argument("--title", required=True)
    ap.add_argument("--dimension", required=True, help="categorical column for the bar chart")
    ap.add_argument("--measure", required=True, help="numeric column to sum")
    ap.add_argument("--time", default="", help="ordered column for the line chart")
    ap.add_argument("--filters", default="", help="comma-separated filter columns")
    ap.add_argument("--source", default="", help="human description of where data came from")
    ap.add_argument("--requested-by", default="")
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--mode", choices=("bundled", "paired"), default="bundled",
                    help="bundled = one self-contained file (max portability, email it). "
                         "paired = dashboard + sibling data.js that OneDrive syncs, so the "
                         "data updates for everyone without rebuilding the dashboard.")
    args = ap.parse_args()

    rows = coerce_numbers(load_rows(args.data))
    if not rows:
        sys.exit("error: input contained zero rows")

    cols = list(rows[0].keys())
    for name, col in (("--dimension", args.dimension), ("--measure", args.measure)):
        if col not in cols:
            sys.exit(f"error: {name} {col!r} not found. Available: {', '.join(cols)}")
    if args.time and args.time not in cols:
        sys.exit(f"error: --time {args.time!r} not found. Available: {', '.join(cols)}")

    if not isinstance(rows[0].get(args.measure), (int, float)):
        sys.exit(f"error: --measure {args.measure!r} is not numeric — charts would be empty. "
                 f"Check the column, or pick a numeric one from: "
                 f"{', '.join(c for c in cols if isinstance(rows[0].get(c), (int, float))) or '(none found)'}")

    filters = [c.strip() for c in args.filters.split(",") if c.strip()]
    missing = [c for c in filters if c not in cols]
    if missing:
        sys.exit(f"error: filter column(s) not found: {', '.join(missing)}")

    now = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    extracted = dt.datetime.fromtimestamp(args.data.stat().st_mtime).astimezone() \
                  .strftime("%Y-%m-%d %H:%M %Z")

    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    meta_js = json.dumps({
        "generated": extracted,
        "source": args.source or args.data.name,
        "rows": len(rows),
    }, ensure_ascii=False)

    if args.mode == "paired":
        data_path = args.out.parent / "data.js"
        data_block = '<script src="./data.js"></script>'
    else:
        data_path = None
        data_block = ("<script>\n"
                      f"window.DASHBOARD_DATA={payload};\n"
                      f"window.DASHBOARD_META={meta_js};\n"
                      "</script>")

    token_css, token_source = tun_tokens.load_token_css(TOKEN_FILES)

    subs = {
        "TOKEN_CSS": token_css,
        "DATA_BLOCK": data_block,
        "DATA_MODE": args.mode,
        "DASHBOARD_TITLE": args.title,
        "SOURCE_DESCRIPTION": args.source or args.data.name,
        "EXTRACT_TIMESTAMP": extracted,
        "BUILD_TIMESTAMP": now,
        "REQUESTED_BY": args.requested_by or getpass.getuser(),
        "ROW_COUNT": f"{len(rows):,}".replace(",", " "),
        "DIMENSION_COL": args.dimension,
        "TIME_COL": args.time,
        "MEASURE_COL": args.measure,
        "FILTER_COLS_JSON": json.dumps(filters or [args.dimension], ensure_ascii=False),
        "CHART1_TITLE": f"{args.measure} per {args.dimension}",
        "CHART2_TITLE": f"{args.measure} over {args.time}" if args.time else "Utvikling",
    }

    html = TEMPLATE.read_text(encoding="utf-8")
    for key, value in subs.items():
        html = html.replace("{{" + key + "}}", str(value))

    leftover = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", html)))
    if leftover:
        sys.exit(f"error: template placeholders not substituted: {leftover}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")

    if data_path is not None:
        data_path.write_text(
            "// Data for " + args.out.name + " — replace this file to update the dashboard.\n"
            "// Generated " + now + " from " + (args.source or args.data.name) + "\n"
            f"window.DASHBOARD_DATA={payload};\n"
            f"window.DASHBOARD_META={meta_js};\n",
            encoding="utf-8")

    size_mb = args.out.stat().st_size / 1_048_576
    print(f"built {args.out}  ({size_mb:.2f} MB, {len(rows):,} rows)".replace(",", " "))
    print(f"  palette: {token_source}")
    if data_path is not None:
        d_mb = data_path.stat().st_size / 1_048_576
        print(f"  + {data_path.name}  ({d_mb:.2f} MB)  <- keep these two together")
        print("  paired mode: replace data.js to update the numbers everywhere, "
              "no rebuild needed")
        size_mb += d_mb
    if size_mb > SIZE_FAIL_MB:
        print(f"  ✗ FAIL {size_mb:.1f} MB exceeds the {SIZE_FAIL_MB} MB Tier 1 ceiling.\n"
              f"    Pre-aggregate the data, or move to Tier 3 (docs/02-architecture.md).",
              file=sys.stderr)
        sys.exit(2)
    if size_mb > SIZE_WARN_MB:
        print(f"  ⚠ {size_mb:.1f} MB is above the {SIZE_WARN_MB} MB comfort budget — "
              f"consider pre-aggregating.", file=sys.stderr)
    print("  next: python3 tools/verify_dashboard.py " + str(args.out))


if __name__ == "__main__":
    main()
