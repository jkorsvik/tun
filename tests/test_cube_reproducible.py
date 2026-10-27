#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""test_cube_reproducible.py — the same data gives the same cube bytes on any Python build.

The cube is gzipped before it is inlined. gzip.compress() lets the interpreter pick two
header fields: the mtime (the current time before Python 3.14, unless told otherwise) and
the OS byte (0x13 from zlib on 3.11/3.12 on macOS, 0xff on 3.14). So one data set gave
different bytes depending on who rebuilt it, and every rebuild of example 03 was a diff.

The test cannot install a second Python, so it brings the other build to this one: a shim
replaces gzip.compress with one that behaves like an older build (current mtime, OS byte
0x13). The builder runs once plainly and once under the shim. If its output depends on
gzip.compress at all, the two cubes differ and this fails.

Stdlib only, runs the real builder as a subprocess into a temp dir.

    python3 tests/test_cube_reproducible.py
"""
from __future__ import annotations

import base64
import gzip
import pathlib
import re
import subprocess
import sys
import tempfile
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_cube_dashboard.py"
CSV = ROOT / "examples" / "01-hello-dashboard" / "salgsdata.csv"
WANT_HEADER = bytes.fromhex("1f8b08000000000002ff")

# Runs the builder with gzip.compress swapped for an "older Python build" that stamps
# the time and writes zlib's OS code. Passed with -c, so no file lands in the repo.
SHIM = r"""
import gzip, runpy, sys, time
_real = gzip.compress
def older_build(data, compresslevel=9, *, mtime=None):
    out = bytearray(_real(data, compresslevel, mtime=int(time.time()) if mtime is None else mtime))
    out[4:8] = (1234567890).to_bytes(4, "little")  # a fixed, nonzero mtime
    out[9] = 0x13
    return bytes(out)
gzip.compress = older_build
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""

passed = failed = 0


def chk(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS {label}")
    else:
        failed += 1
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def build(out: pathlib.Path, shim: bool) -> bytes:
    args = [str(BUILDER), "--data", str(CSV), "--title", "t", "--dims", "Region,Produkt",
            "--time", "Maaned", "--measures", "Belop:sum,Antall:sum",
            "--requested-by", "Analyseteamet", "--out", str(out)]
    cmd = [sys.executable, "-c", SHIM, *args] if shim else [sys.executable, *args]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit(f"builder failed ({'shim' if shim else 'plain'}):\n{r.stderr}")
    html = out.read_text(encoding="utf-8")
    m = re.search(r'<script id="cube" type="application/gzip;base64">([^<]*)</script>', html)
    if not m:
        raise SystemExit("no cube script element in the built file")
    return base64.b64decode(m.group(1))


def main() -> int:
    print("cube reproducibility: same data, same bytes, on any Python build")
    print("─" * 62)
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        plain = build(tmp / "plain.html", shim=False)
        again = build(tmp / "again.html", shim=False)
        other = build(tmp / "other.html", shim=True)

    chk("header is fixed (no name, mtime 0, XFL 2, OS 255)", plain[:10] == WANT_HEADER,
        plain[:10].hex())
    chk("two plain builds give identical cube bytes", plain == again)
    chk("an older Python build gives identical cube bytes", plain == other,
        f"header {plain[:10].hex()} vs {other[:10].hex()}")

    # The shim must really change gzip.compress output, or the check above is vacuous.
    probe_real = gzip.compress(b"probe", 9, mtime=0)
    ns: dict = {}
    exec(SHIM.split("gzip.compress = older_build")[0], ns)  # defines older_build only
    probe_shim = ns["older_build"](b"probe", 9, mtime=0)
    chk("the shim really alters gzip.compress output (control)", probe_real != probe_shim)

    body = gzip.decompress(plain)
    chk("it is still valid gzip and inflates", len(body) > 0)
    chk("trailer CRC32 and size match the payload",
        plain[-8:] == zlib.crc32(body).to_bytes(4, "little") + len(body).to_bytes(4, "little"))
    print("─" * 62)
    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
