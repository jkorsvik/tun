#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
build_slide_deck.py: write the starter slide deck in Norwegian or English.

Stdlib only, like the rest of tools/. The starter is templates/portable-slide-deck.html:
the controls, the fullscreen button, the warning for a limited preview and three sample
slides. This script swaps the {{T:key}} words for one language and writes one file.

    python3 tools/build_slide_deck.py --out deck.html              # nb, the default
    python3 tools/build_slide_deck.py --out deck.html --lang en

Then replace the three sample slides, keep class="slide" and data-sec on each, and fill in
the provenance comment at the top of the file. Your slide text is yours: only the chrome
and the samples change with --lang.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_size
import i18n  # noqa: E402

TEMPLATE = pathlib.Path(__file__).resolve().parents[1] / "templates" / "portable-slide-deck.html"
STRINGS = "portable-slide-deck"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=pathlib.Path, help="the .html file to write")
    i18n.add_lang_argument(ap)
    args = ap.parse_args(argv)

    html = i18n.apply(TEMPLATE.read_text(encoding="utf-8"), i18n.load(STRINGS, args.lang))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"built {args.out}  ({args.out.stat().st_size / 1024:.1f} KB, {args.lang})")
    # No builder ships an artefact past the Tier 1 ceiling (tools/build_size.py).
    build_size.enforce(args.out)
    print("  next: replace the three sample slides and fill in the provenance comment, then\n"
          f"        uv run --extra verify python tools/verify_slide_deck.py {args.out} --out <dir>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
