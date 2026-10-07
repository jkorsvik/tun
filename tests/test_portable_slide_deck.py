#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Structural regression tests for the portable presentation and its template.

These checks need only the Python standard library. Browser behavior belongs in
tools/verify_slide_deck.py.
"""

from __future__ import annotations

import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional, Tuple

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import verify_standalone_core as core  # noqa: E402
DECKS = {
    "presentation": REPO / "examples" / "18-portable-slide-deck" / "sample-deck.html",
    "template": REPO / "templates" / "portable-slide-deck.html",
    "detail-overlay-variant": REPO / "examples" / "21-slide-deck-detail-overlay" / "detail-overlay-pattern.html",
}
SLIDES_START = '  <!-- Replace these sample slides. Keep class="slide" and data-sec. -->\n'
PLACEHOLDER = re.compile(r"\{\{[A-Z0-9_]+\}\}")


class DeckParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.slides: list[dict[str, Optional[str]]] = []
        self.references: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[Tuple[str, Optional[str]]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"] or "")
        classes = set((values.get("class") or "").split())
        if "slide" in classes:
            self.slides.append(values)
        for name in ("src", "href"):
            if values.get(name):
                self.references.append((name, values[name] or ""))


class PortableDeckTest(unittest.TestCase):
    def load(self, path: Path) -> tuple[str, DeckParser]:
        self.assertTrue(path.is_file(), path)
        text = path.read_text(encoding="utf-8")
        parser = DeckParser()
        parser.feed(text)
        parser.close()
        return text, parser

    def test_artifacts_are_single_self_contained_html_files(self) -> None:
        for name, path in DECKS.items():
            with self.subTest(name=name):
                text, parser = self.load(path)
                self.assertIn("<!DOCTYPE html>", text)
                self.assertNotRegex(text, r"https?://")
                self.assertNotRegex(text, r"@import\s")
                self.assertNotRegex(text, r"url\s*\(")
                for attr, value in parser.references:
                    self.assertFalse(
                        value.startswith(("//", "http://", "https://")),
                        f"external {attr}={value!r}",
                    )

    def test_every_slide_has_a_section_name(self) -> None:
        expected_counts = {"presentation": 3, "template": 3, "detail-overlay-variant": 4}
        for name, path in DECKS.items():
            with self.subTest(name=name):
                _, parser = self.load(path)
                self.assertEqual(len(parser.slides), expected_counts[name])
                self.assertTrue(all(slide.get("data-sec") for slide in parser.slides))

    def test_ids_are_unique(self) -> None:
        for name, path in DECKS.items():
            with self.subTest(name=name):
                _, parser = self.load(path)
                duplicates = sorted({value for value in parser.ids if parser.ids.count(value) > 1})
                self.assertEqual(duplicates, [])

    def test_required_controls_exist(self) -> None:
        required = {"rail", "railnav", "controls", "nprev", "counter", "nnext", "fullscreen", "progress", "toast", "js-warning"}
        for name, path in DECKS.items():
            with self.subTest(name=name):
                _, parser = self.load(path)
                self.assertTrue(required.issubset(parser.ids), required - set(parser.ids))

    def test_mobile_viewport_contract_is_present(self) -> None:
        required_fragments = (
            "viewport-fit=cover",
            "height:100dvh",
            "env(safe-area-inset-bottom)",
            "@media(hover:none),(pointer:coarse)",
            "@media(orientation:portrait)",
            "@media(orientation:landscape)",
            "min-width:48px",
        )
        for name, path in DECKS.items():
            with self.subTest(name=name):
                text, _ = self.load(path)
                for fragment in required_fragments:
                    self.assertIn(fragment, text)

    def test_all_navigation_modes_are_present(self) -> None:
        required_fragments = (
            "prevButton.onclick",
            "nextButton.onclick",
            "ArrowRight",
            "ArrowLeft",
            "PageDown",
            "PageUp",
            "touchstart",
            "touchend",
            "history.replaceState",
        )
        for name, path in DECKS.items():
            with self.subTest(name=name):
                text, _ = self.load(path)
                for fragment in required_fragments:
                    self.assertIn(fragment, text)

    def test_fullscreen_has_standard_webkit_and_failure_paths(self) -> None:
        required_fragments = (
            "requestFullscreen",
            "webkitRequestFullscreen",
            "exitFullscreen",
            "webkitExitFullscreen",
            "fullscreenchange",
            "webkitfullscreenchange",
            "notify(",
        )
        for name, path in DECKS.items():
            with self.subTest(name=name):
                text, _ = self.load(path)
                for fragment in required_fragments:
                    self.assertIn(fragment, text)

    def test_no_javascript_fallback_is_built_in(self) -> None:
        required_fragments = (
            'document.documentElement.className+=" js"',
            "html:not(.js) .slide:first-of-type",
            "html:not(.js) #rail",
            "html.js #js-warning",
            "Begrenset forhåndsvisning",
        )
        for name, path in DECKS.items():
            with self.subTest(name=name):
                text, _ = self.load(path)
                for fragment in required_fragments:
                    self.assertIn(fragment, text)

    def test_presentation_keeps_the_template_shell(self) -> None:
        # The sample exists to show the template in use, so everything outside the
        # replaced slides must be the template's own bytes. Placeholders are blanked on
        # both sides first: they are the only part a build is meant to change.
        template, _ = self.load(DECKS["template"])
        built, _ = self.load(DECKS["presentation"])
        self.assertEqual(template.count(SLIDES_START), 1)
        self.assertEqual(built.count(SLIDES_START), 1)
        t_head, t_rest = template.split(SLIDES_START)
        b_head, b_rest = built.split(SLIDES_START)
        t_tail = t_rest.split("</main>", 1)[1]
        b_tail = b_rest.split("</main>", 1)[1]
        self.assertEqual(b_tail, t_tail, "shell after </main> differs from the template")
        self.assertIn("{{TOKEN_CSS}}", t_head)
        # The head differs only where placeholders were filled: split the template head
        # on its placeholders and require every literal chunk, in order, in the build.
        position = 0
        for chunk in PLACEHOLDER.split(t_head):
            found = b_head.find(chunk, position)
            self.assertNotEqual(found, -1, f"template text missing from build: {chunk[:60]!r}")
            position = found + len(chunk)

    def test_presentation_is_fully_built_with_a_palette(self) -> None:
        text, _ = self.load(DECKS["presentation"])
        self.assertEqual(PLACEHOLDER.findall(text), [])
        sys.path.insert(0, str(REPO / "tools"))
        import tun_tokens
        self.assertEqual(tun_tokens.missing_slots(text), [])

    def test_sharepoint_preview_gates_accept_both_files(self) -> None:
        gates = (
            core.check_no_stray_script_text,
            core.check_no_target_driven_visibility,
            core.check_no_scroll_persistent_positioning,
        )
        for name, path in DECKS.items():
            text, _ = self.load(path)
            for gate in gates:
                with self.subTest(name=name, gate=gate.__name__):
                    ok, message = gate(text)
                    self.assertTrue(ok, message)

    def test_scripts_do_not_hide_controls_on_touch_devices(self) -> None:
        for name, path in DECKS.items():
            with self.subTest(name=name):
                text, _ = self.load(path)
                touch_blocks = re.findall(
                    r"@media\(hover:none\),\(pointer:coarse\)\{(.*?)\n\}",
                    text,
                    flags=re.DOTALL,
                )
                self.assertTrue(touch_blocks)
                self.assertFalse(any("#controls{display:none" in block for block in touch_blocks))


if __name__ == "__main__":
    unittest.main(verbosity=2)
