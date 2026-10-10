#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
build_sample_deck.py — builds sample-deck.html from templates/portable-slide-deck.html.

A synthetic three-slide sample. It shows the one thing a deck author does with the
template: keep the shell (controls, rail, mobile rules, no-JavaScript fallback) and
replace the sample slides. Everything outside <main> comes from the template unchanged;
tests/test_portable_slide_deck.py asserts that.

The template is filled by tools/build_slide_deck.py (strings, palette, provenance), so
this file holds only what is the deck's own: its title and its slides.

    python3 examples/18-portable-slide-deck/build_sample_deck.py [--lang nb|en] [--out FILE]

--lang changes the page chrome (buttons, labels). The slide text below is the deck's own
and is never translated. --out defaults to sample-deck.html next to this file. Stdlib only.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
OUT = HERE / "sample-deck.html"

sys.path.insert(0, str(REPO_ROOT / "tools"))
import build_slide_deck  # noqa: E402
import i18n  # noqa: E402

TITLE = "Del et dashboard som én fil"

SLIDES = """  <section class="slide dark" data-sec="Start">
    <div class="eyebrow">Syntetisk eksempel</div>
    <h1>Del et dashboard som én fil.</h1>
    <p style="margin-top:3vh">Ingen server, ingen lisens og ingen innlogging for den som åpner den.</p>
  </section>

  <section class="slide" data-sec="Tre steg">
    <div class="eyebrow">Slik gjør du det</div>
    <h2>Bygg, sjekk, del</h2>
    <div class="grid">
      <div class="card"><strong>1</strong><span>Bygg filen fra dataene med ett skript</span></div>
      <div class="card"><strong>2</strong><span>Kjør verifikasjonen og se på skjermbildet</span></div>
      <div class="card"><strong>3</strong><span>Legg filen i en delt mappe og send lenken</span></div>
    </div>
  </section>

  <section class="slide dark" data-sec="Husk">
    <div class="eyebrow">Én regel</div>
    <h2>Alle som kan åpne filen, ser alle tallene.</h2>
    <p>Trenger ulike lesere ulike rader, hører rapporten hjemme i et verktøy med radnivåsikkerhet.</p>
  </section>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=pathlib.Path, default=OUT, help="the .html file to write")
    i18n.add_lang_argument(ap)
    args = ap.parse_args()
    html, token_source = build_slide_deck.build(
        args.lang, title=TITLE, slides=SLIDES,
        source="none — synthetic sample content",
        requested_by="n/a (sample deck)",
        built_by="examples/18-portable-slide-deck/build_sample_deck.py")
    args.out.write_text(html, encoding="utf-8")
    print(f"wrote {args.out} ({args.out.stat().st_size} bytes, palette: {token_source})")
    print("next: uv run --extra verify python tools/verify_slide_deck.py " + str(args.out)
          + " --out /tmp/sample-deck-check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
