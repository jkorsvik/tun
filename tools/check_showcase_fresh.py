#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Every showcase card must carry the current page for its own example.

The gallery embeds each selected page as gzip base64. A server-backed example can ship a
`snapshot.html`; build_showcase selects that instead of the client that needs its API.
This gate reads the same selection and requires one card per example, one payload per
selected page, and decoded bytes equal to that page after sibling inlining. A missing card,
a missing payload, a wrong-page payload and a stale payload all fail.

    python3 tools/check_showcase_fresh.py
    python3 tools/check_showcase_fresh.py --showcase <path> --examples <dir>
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from build_showcase import decode_live, inline_siblings, read_example  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
CARD = re.compile(
    r'<li class="card" id="example-([^"]+)"(?: data-live="([^"]+)")? data-num="([^"]+)"')


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
    rows = CARD.findall(page)
    if not rows:
        print("FAIL: the showcase has no readable cards, so this check proves nothing")
        return 1
    cards = {number: (payload, actual) for number, payload, actual in rows}

    folder = pathlib.Path(args.examples)
    own_dir = showcase.resolve().parent
    examples = [e for e in (read_example(p) for p in sorted(folder.iterdir()) if p.is_dir())
                if e and e["dir"].resolve() != own_dir]
    if not examples:
        print("FAIL: no examples resolved, so this check proves nothing")
        return 1

    stale: list[str] = []
    if len(rows) != len(cards):
        stale.append("two or more cards use the same example id")
    known = {e["slug"].split("-")[0] for e in examples}
    for number in sorted(set(cards) - known):
        stale.append(f"example {number}: card has no source example")

    embedded = 0
    selected = 0
    for example in examples:
        number = example["slug"].split("-")[0]
        entry = cards.get(number)
        if entry is None:
            stale.append(f"example {number}: no card")
            continue
        payload, actual = entry
        if actual != number:
            stale.append(f"example {number}: card label says {actual}")
        if example["page"] is None:
            if payload:
                stale.append(f"example {number}: has a payload but no selected page")
            continue
        selected += 1
        if not payload:
            stale.append(f"example {number}: selected page has no embedded payload")
            continue
        embedded += 1
        try:
            decoded = decode_live(payload)
        except Exception:
            stale.append(f"example {number}: not valid base64 gzip content")
            continue
        if decoded != inline_siblings(example["page"]):
            stale.append(f"example {number}: payload differs from {example['page'].name}")

    print(f"cards: {len(cards)}; examples: {len(examples)}")
    print(f"embedded payloads: {embedded}; selected pages: {selected}")
    if stale:
        for row in stale[:12]:
            print(f"  ✗ {row}")
        print(f"FAIL: {len(stale)} card/payload problem(s). Build the showcase last, after "
              "every page it embeds is final.")
        return 1
    print(f"PASS: every example has one card, and every selected page is embedded byte for byte "
          f"({embedded})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
