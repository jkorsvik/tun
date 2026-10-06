#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
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

    python3 examples/18-portable-slide-deck/build_sample_deck.py

Stdlib only. Colours come from tools/tun_tokens.py, like every other builder.
"""
from __future__ import annotations

import datetime
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
TEMPLATE = REPO_ROOT / "templates" / "portable-slide-deck.html"
OUT = HERE / "sample-deck.html"

sys.path.insert(0, str(REPO_ROOT / "tools"))
import tun_tokens  # noqa: E402

#: The template marks where its sample slides start. Everything after this marker up to
#: </main> is replaced; everything else is kept byte for byte.
SLIDES_START = '  <!-- Replace these sample slides. Keep class="slide" and data-sec. -->\n'
SLIDES_END = "</main>"

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
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(SLIDES_START) != 1 or template.count(SLIDES_END) != 1:
        sys.exit(f"error: {TEMPLATE.name} no longer has exactly one slide marker and one "
                 f"</main>; update this builder with the template")

    token_css, token_source = tun_tokens.load_token_css(core_files=())
    head, rest = template.split(SLIDES_START)
    _, tail = rest.split(SLIDES_END)
    # The marker stays in the output, so a reader of the built file sees where the
    # template ends and the deck's own content begins.
    html = head + SLIDES_START + SLIDES + SLIDES_END + tail

    subs = {
        "TOKEN_CSS": token_css,
        "ARTIFACT_TITLE": TITLE,
        "SOURCE_DESCRIPTION": "none — synthetic sample content",
        "BUILD_TIMESTAMP": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "REQUESTED_BY": "n/a (sample deck)",
        "BUILT_BY": "examples/18-portable-slide-deck/build_sample_deck.py",
    }
    for key, value in subs.items():
        html = html.replace("{{" + key + "}}", value)
    leftover = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", html)))
    if leftover:
        sys.exit(f"error: template placeholders not substituted: {leftover}")

    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, palette: {token_source})")
    print("next: uv run --extra verify python tools/verify_slide_deck.py " + str(OUT)
          + " --out /tmp/sample-deck-check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
