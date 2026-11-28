#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Every showcase card must have a real link, not only a JavaScript payload.

The gallery publishes the same bytes at two paths: the site root (`_site/index.html`) and
`examples/54-showcase/oversikt.html`. A relative href would work at one and break at the
other, so `build_showcase.py --base-url` writes an absolute Pages URL for each card.
This gate reads the committed document and proves:

  * every card still carries its gzip `data-live` payload (the offline path);
  * every card carries an `href` to the page it embeds;
  * stripping the published base URL leaves a file that exists under `examples/`;
  * deleting one card's href makes the gate fail, so the check can actually see a loss.

Stdlib only: no browser and no Playwright, so it runs in every checkout.

    python3 tests/test_showcase_links.py
"""
from __future__ import annotations

import html.parser
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
import build_showcase  # noqa: E402

SHOWCASE = ROOT / "examples" / "54-showcase" / "oversikt.html"
EXAMPLES = ROOT / "examples"
BASE = "https://jkorsvik.github.io/tun/"
CHECKS = FAILED = 0


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS, FAILED
    CHECKS += 1
    print(f"  {'✓' if ok else '✗'} {what}" + ("" if ok else f" — {detail}"))
    if not ok:
        FAILED += 1


class CardParser(html.parser.HTMLParser):
    """Collect each card's live payload, slug and the hrefs inside that card."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[dict] = []
        self._card: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "li" and "card" in (values.get("class") or "").split():
            self._card = {
                "live": values.get("data-live") or "",
                "number": values.get("data-num") or "",
                "slug": values.get("data-slug") or "",
                "hrefs": [],
            }
            self.cards.append(self._card)
        elif tag == "a" and self._card is not None and values.get("href"):
            self._card["hrefs"].append(values["href"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "li":
            self._card = None


def selected_pages() -> dict[str, dict]:
    """The examples the builder would put on a card: one README and one built page each."""
    own_dir = SHOWCASE.parent.resolve()
    found = (build_showcase.read_example(path) for path in sorted(EXAMPLES.iterdir())
             if path.is_dir())
    return {example["slug"]: example for example in found
            if example and example["dir"].resolve() != own_dir and example["page"]}


def audit(text: str, expected: dict[str, dict]) -> tuple[list[str], list[dict]]:
    """Every problem with the card links, and the cards that were read."""
    parser = CardParser()
    parser.feed(text)
    parser.close()
    problems: list[str] = []
    if len(parser.cards) != len(expected):
        problems.append(f"found {len(parser.cards)} cards, expected {len(expected)} examples "
                        "with a built page")
    prefix = BASE.rstrip("/") + "/"
    for card in parser.cards:
        number = card["number"] or "?"
        slug = card["slug"]
        if not card["live"].startswith(build_showcase.LIVE_PREFIX):
            problems.append(f"example {number}: card has no gzip data-live payload")
        if not card["hrefs"]:
            problems.append(f"example {number}: card has no static href")
        want = expected.get(slug)
        if want is None:
            problems.append(f"example {number}: card names an unknown example {slug!r}")
            continue
        wanted = build_showcase.static_url(BASE, slug, want["page"])
        if wanted not in card["hrefs"]:
            problems.append(f"example {number}: card does not link to its selected page "
                            f"({wanted})")
        for href in card["hrefs"]:
            if not href.startswith(prefix):
                problems.append(f"example {number}: href is outside the published base "
                                f"({href})")
                continue
            target = (ROOT / href[len(prefix):]).resolve()
            try:
                target.relative_to(EXAMPLES.resolve())
            except ValueError:
                problems.append(f"example {number}: href escapes examples/ ({href})")
                continue
            if not target.is_file():
                problems.append(f"example {number}: href points at a missing file ({href})")
    return problems, parser.cards


def main() -> int:
    print("showcase links: every card has a static URL and a live payload")
    if not SHOWCASE.is_file():
        print(f"FAIL: no showcase at {SHOWCASE}")
        return 1
    text = SHOWCASE.read_text(encoding="utf-8")
    expected = selected_pages()
    chk(bool(expected), f"resolved {len(expected)} example(s) with a built page")
    problems, cards = audit(text, expected)
    chk(not problems, f"every one of {len(cards)} card(s) has a live payload and a real href",
        "; ".join(problems[:4]))
    if problems:
        for problem in problems[:12]:
            print(f"      {problem}")

    # The gate must see a loss. Remove the first card's Pages href and require the audit to
    # name it; otherwise a parser that stopped matching cards would report success.
    mutated = re.sub(r'href="https://jkorsvik\.github\.io/tun/examples/[^"]*"', "", text,
                     count=1)
    chk(mutated != text, "the mutation removed one static href")
    changed, changed_cards = audit(mutated, expected)
    chk(any("has no static href" in problem for problem in changed),
        "a card without an href fails the gate", "; ".join(changed[:4]))
    chk(len(changed_cards) == len(cards), "the mutation kept every card readable")

    # The base option is part of the contract: no trailing slash still appends to the root.
    page = pathlib.Path("examples/01-hello-dashboard/salg-dashboard.html")
    chk(build_showcase.static_url(BASE.rstrip("/"), "01-hello-dashboard", page)
        == BASE + "examples/01-hello-dashboard/salg-dashboard.html",
        "a base URL without its trailing slash still builds the examples path")

    print(f"{CHECKS - FAILED}/{CHECKS} checks passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
