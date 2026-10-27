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

import i18n  # noqa: E402
import verify_standalone_core as core  # noqa: E402
DECKS = {
    "presentation": REPO / "examples" / "18-portable-slide-deck" / "maalebandet.html",
    "template": REPO / "templates" / "portable-slide-deck.html",
    "detail-overlay-variant": REPO / "examples" / "21-slide-deck-detail-overlay" / "detail-overlay-pattern.html",
}


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
        # The template holds {{T:key}} words; what a person gets is the nb build of it,
        # which tools/build_slide_deck.py writes. tests/test_i18n.py covers both languages.
        text = i18n.apply(text, i18n.load("portable-slide-deck", "nb"))
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
        expected_counts = {"presentation": 15, "template": 3, "detail-overlay-variant": 4}
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

    def test_presentation_counters_have_static_final_values(self) -> None:
        text, _ = self.load(DECKS["presentation"])
        counters = re.findall(r'<div class="num"(?P<attrs>[^>]*)>(?P<text>[^<]+)</div>', text)
        self.assertGreater(len(counters), 0)
        for attrs, value in counters:
            target = re.search(r'data-to="([0-9]+)"', attrs)
            if not target:
                continue
            divisor = re.search(r'data-div="([0-9]+)"', attrs)
            suffix = re.search(r'data-suffix="([^"]*)"', attrs)
            raw = int(target.group(1))
            if divisor:
                div = int(divisor.group(1))
                expected = f"{raw / div:.{len(str(div)) - 1}f}".replace(".", ",")
            else:
                expected = str(raw)
            expected += suffix.group(1) if suffix else ""
            self.assertEqual(value, expected)

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
