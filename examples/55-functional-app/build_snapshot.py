#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build the committed, synthetic standalone snapshot used by the gallery."""
from __future__ import annotations

import argparse
import os
import pathlib
import tempfile

from app import Store, export_snapshot

HERE = pathlib.Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path, default=HERE / "snapshot.html")
    args = parser.parse_args(argv)
    os.environ.setdefault("SOURCE_DATE_EPOCH", "1792836000")
    with tempfile.TemporaryDirectory(prefix="tun-functional-app-") as raw:
        store = Store(pathlib.Path(raw) / "decisions.db")
        store.initialize()
        store.seed()
        out = export_snapshot(store, args.out, "Tún example builder")
    print(f"Wrote {out} from three synthetic decisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
