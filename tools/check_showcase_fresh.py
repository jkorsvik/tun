#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The showcase embeds every example, so every embedded copy must BE that example.

examples/54-showcase/oversikt.html carries each page twice: a thumbnail (a JPEG, which
needs a browser to make) and `data-live`, the page's own bytes inlined as base64 so the
dialog can run it without a network. The second copy is a snapshot, and snapshots go
stale: after the licence-header pass ran over the published tree, all 49 embedded copies
were older than the pages they came from, and two of them still carried a word that had
been fixed in the source. Nothing noticed, because both the byte scan and the staleness
gate look at files, and this stale text is inside a base64 string.

So: decode every data-live and require it to equal inline_siblings(the current page),
byte for byte. Static, no browser, no server.

    python3 tools/check_showcase_fresh.py
    python3 tools/check_showcase_fresh.py --showcase <path> --examples <dir>
"""
from __future__ import annotations

import argparse
import base64
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from build_showcase import inline_siblings  # noqa: E402  the one definition of "embedded"

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIVE = re.compile(r'data-live="([A-Za-z0-9+/=]+)"')
NUM = re.compile(r' data-num="([^"]*)"')


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--showcase", default=str(ROOT / "examples" / "54-showcase" / "oversikt.html"))
    ap.add_argument("--examples", default=str(ROOT / "examples"))
    args = ap.parse_args(argv)

    showcase = pathlib.Path(args.showcase)
    if not showcase.is_file():
        print(f"FAIL: no showcase at {showcase}")
        return 1
    page = showcase.read_text(encoding="utf-8")
    payloads = LIVE.findall(page)
    if not payloads:
        print("FAIL: the showcase carries no data-live payloads, so this check proves nothing")
        return 1

    expected: dict[bytes, pathlib.Path] = {}
    for source in sorted(pathlib.Path(args.examples).glob("*/*.html")):
        try:
            expected[inline_siblings(source)] = source
        except OSError:
            continue

    stale: list[str] = []
    for index, payload in enumerate(payloads, start=1):
        try:
            decoded = base64.b64decode(payload, validate=True)
        except Exception:
            stale.append(f"payload {index}: not base64")
            continue
        if decoded not in expected:
            stale.append(f"payload {index}: equals no current page")

    print(f"embedded payloads: {len(payloads)}")
    print(f"current pages: {len(expected)}")
    if stale:
        for row in stale[:10]:
            print(f"  ✗ {row}")
        print(f"FAIL: {len(stale)} embedded copy/copies are stale. The showcase must be built "
              f"last, after every page it embeds is final.")
        return 1
    print(f"PASS: every embedded copy equals a current page byte for byte ({len(payloads)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
