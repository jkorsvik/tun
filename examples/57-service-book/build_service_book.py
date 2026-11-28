#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
build_service_book.py — write the standalone service book from its state file.

Stdlib only.

    python3 examples/57-service-book/build_service_book.py

The built file is one self-contained HTML document: no external reference, no
script beyond its own, and the whole state embedded in a JSON block so the file
reopens with its edits. `SOURCE_DATE_EPOCH` pins the build stamp.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = HERE / "service-book.tpl"
STATE = HERE / "service-book.json"
OUT = HERE / "service-book.html"


def build_stamp() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch and epoch.strip().isdigit():
        moment = dt.datetime.fromtimestamp(int(epoch), tz=dt.timezone.utc)
    else:
        moment = dt.datetime.now(dt.timezone.utc)
    return moment.strftime("%Y-%m-%d %H:%M UTC")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the service-book example.")
    parser.add_argument("--state", type=pathlib.Path, default=STATE)
    parser.add_argument("--template", type=pathlib.Path, default=TEMPLATE)
    parser.add_argument("--out", type=pathlib.Path, default=OUT)
    parser.add_argument("--source", default="synthetic example data (service-book.json)",
                        help="where the rows came from; written into the provenance block")
    parser.add_argument("--requested-by", default="Tún example",
                        help="a role, not a person's name; written into the provenance block")
    args = parser.parse_args()

    if not args.state.exists():
        raise SystemExit("state file not found: %s" % args.state)

    state = json.loads(args.state.read_text(encoding="utf-8"))
    template = args.template.read_text(encoding="utf-8")

    # Escape `<`/`>` so a hostile string in the state cannot close the script element.
    payload = json.dumps(state, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")

    built = build_stamp()
    html = (template
            .replace("__TITLE__", _escape(state.get("title", "Servicebok")))
            .replace("__STATE__", payload)
            .replace("__ROWS__", str(len(state.get("watches", []))))
            .replace("__PEOPLE__", str(len(state.get("people", []))))
            .replace("__POSTS__", str(_posts(state)))
            .replace("__SOURCE__", _escape(args.source))
            .replace("__REQUESTED__", _escape(args.requested_by))
            .replace("__BUILT__", built))

    for token in ("__TITLE__", "__STATE__", "__ROWS__", "__PEOPLE__", "__POSTS__", "__BUILT__",
                  "__SOURCE__", "__REQUESTED__"):
        if token in html:
            raise SystemExit("placeholder %s was not replaced" % token)

    args.out.write_text(html, encoding="utf-8")
    print("wrote %s (%d bytes, %d watches, %d roles, %d posts)"
          % (args.out.relative_to(HERE.parent.parent) if args.out.is_relative_to(HERE.parent.parent) else args.out,
             args.out.stat().st_size, len(state.get("watches", [])),
             len(state.get("people", [])), _posts(state)))
    return 0


def _posts(state: dict) -> int:
    """How many fixed posts the state holds, wherever the key that holds them is named.

    Reading one hard-coded key made the count silently report 0 after a rename, which
    is the same class of defect as a badge that stops counting.
    """
    for key in ("beskjed",):
        block = state.get(key)
        if isinstance(block, dict) and isinstance(block.get("posts"), list):
            return len(block["posts"])
    return 0


def _escape(value: str) -> str:
    return (str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


if __name__ == "__main__":
    raise SystemExit(main())
