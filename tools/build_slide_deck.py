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
slides. This script is the one place that fills that template: it swaps the {{T:key}} words
for one language, inlines the palette (tools/tun_tokens.py: core's neutral palette unless a
brand plugin supplies one) and fills the title and the provenance block.

    python3 tools/build_slide_deck.py --out deck.html              # nb, the default
    python3 tools/build_slide_deck.py --out deck.html --lang en

Then replace the three sample slides, keep class="slide" and data-sec on each, and fill in
the provenance comment at the top of the file. Your slide text is yours: only the chrome
and the samples change with --lang. examples/18-portable-slide-deck/build_sample_deck.py
calls build() below with slides of its own.
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import i18n  # noqa: E402
import tun_tokens  # noqa: E402

TEMPLATE = pathlib.Path(__file__).resolve().parents[1] / "templates" / "portable-slide-deck.html"
STRINGS = "portable-slide-deck"
NOT_STATED = "not stated"

#: The template marks where its sample slides start. Everything after this marker up to
#: </main> is the deck's content; everything else is the shell, kept byte for byte.
SLIDES_START = '  <!-- Replace these sample slides. Keep class="slide" and data-sec. -->\n'
SLIDES_END = "</main>"
PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def build(lang: str, title: str | None = None, slides: str | None = None,
          source: str = "none (starter deck)", requested_by: str = NOT_STATED,
          built_by: str = "tools/build_slide_deck.py") -> tuple[str, str]:
    """The deck as text, and where its palette came from. `slides` replaces the three
    sample slides; it is pasted last, so text in it is never scanned for placeholders."""
    t = i18n.load(STRINGS, lang)
    template = i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
    if template.count(SLIDES_START) != 1 or template.count(SLIDES_END) != 1:
        sys.exit(f"error: {TEMPLATE.name} no longer has exactly one slide marker and one "
                 f"</main>; update this builder with the template")
    token_css, token_source = tun_tokens.load_token_css(core_files=())
    subs = {
        "TOKEN_CSS": token_css,
        "ARTIFACT_TITLE": title or t["title"],
        "SOURCE_DESCRIPTION": source,
        "BUILD_TIMESTAMP": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "REQUESTED_BY": requested_by,
        "BUILT_BY": built_by,
    }
    head, rest = template.split(SLIDES_START)
    sample, tail = rest.split(SLIDES_END)
    # One pass, so a value that holds a placeholder (a title, say) is pasted as written.
    fill = lambda text: PLACEHOLDER.sub(lambda m: subs.get(m.group(1), m.group(0)), text)  # noqa: E731
    head, tail = fill(head), fill(tail)
    leftover = sorted(set(PLACEHOLDER.findall(head + tail)) - set(subs))
    if leftover:
        sys.exit(f"error: template placeholders not substituted: {leftover}")
    # The marker stays in the output, so a reader of the built file sees where the
    # template ends and the deck's own content begins.
    return head + SLIDES_START + (slides if slides is not None else fill(sample)) + SLIDES_END + tail, \
        token_source


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=pathlib.Path, help="the .html file to write")
    ap.add_argument("--title", help="the deck's title (default: the strings table's title)")
    ap.add_argument("--source", default="none (starter deck)",
                    help="what the provenance block says the source data is")
    ap.add_argument("--requested-by", default=NOT_STATED, help="who asked for the deck")
    i18n.add_lang_argument(ap)
    args = ap.parse_args(argv)

    html, token_source = build(args.lang, args.title, source=args.source,
                               requested_by=args.requested_by)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"built {args.out}  ({args.out.stat().st_size / 1024:.1f} KB, {args.lang}, "
          f"palette: {token_source})")
    print("  next: replace the three sample slides and fill in the provenance comment, then\n"
          f"        uv run --extra verify python tools/verify_slide_deck.py {args.out} --out <dir>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
