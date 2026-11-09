#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Render identity from file://, with and without script, in both colour schemes.

TUN_BRAND_ENGINES=chromium,firefox,webkit selects the release matrix. Default
matches the other browser suites. No engine failure is skipped.
"""
from __future__ import annotations

import os
import pathlib
import sys
import unittest

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGES = (
    '01-hello-dashboard/salg-dashboard.html',
    '28-one-dataset-three-artefacts/kube.html',
    '23-process-diagram/tun-workflow.html',
    '37-printable-onepager/ett-ark.html',
    '18-portable-slide-deck/maalebandet.html',
    '21-slide-deck-detail-overlay/detail-overlay-pattern.html',
    '55-functional-app/snapshot.html',
)


class BrandingBrowser(unittest.TestCase):
    def test_identity_survives_render_and_degradation(self):
        seen = 0
        with sync_playwright() as pw:
            for engine in os.environ.get('TUN_BRAND_ENGINES', 'chromium').split(','):
                browser = getattr(pw, engine).launch()
                try:
                    for script in (True, False):
                        for scheme in ('light', 'dark'):
                            context = browser.new_context(java_script_enabled=script, color_scheme=scheme,
                                                          viewport={'width': 390, 'height': 844}, has_touch=True)
                            try:
                                for rel in PAGES:
                                    with self.subTest(engine=engine, script=script, scheme=scheme, page=rel):
                                        page = context.new_page()
                                        remote = []
                                        page.on('request', lambda request: remote.append(request.url)
                                                if request.url.startswith(('http:', 'https:')) else None)
                                        page.goto((ROOT / 'examples' / rel).as_uri())
                                        link = page.locator('.tun-credit a')
                                        self.assertEqual(link.count(), 1)
                                        self.assertTrue(link.is_visible())
                                        link.scroll_into_view_if_needed()
                                        self.assertEqual(link.get_attribute('href'), 'https://tun.community')
                                        icon = page.locator('link[rel="icon"]')
                                        self.assertEqual(icon.count(), 1)
                                        self.assertTrue(icon.get_attribute('href').startswith('data:image/svg+xml,'))
                                        self.assertFalse(remote, remote)
                                        if not script and rel.startswith(('18-', '21-')):
                                            # is_visible() cannot detect equal foreground/background.
                                            ink = link.evaluate('(el) => getComputedStyle(el).color')
                                            stage = page.locator('.slide').first.evaluate(
                                                '(el) => getComputedStyle(el).backgroundColor')
                                            self.assertNotEqual(ink, stage, 'credit must contrast in no-JS decks')

                                        box = link.bounding_box()
                                        self.assertGreater(box['width'], 0)
                                        self.assertGreater(box['height'], 0)
                                        self.assertGreaterEqual(box['x'], 0)
                                        # The printable A4 sheet pans on a phone by design.
                                        if not rel.startswith('37-'):
                                            self.assertLessEqual(box['x'] + box['width'], 391)
                                        if script:
                                            loaded = page.evaluate('''() => new Promise(resolve => {
                                              const img = new Image();
                                              img.onload = () => resolve(img.naturalWidth > 0);
                                              img.onerror = () => resolve(false);
                                              img.src = document.querySelector('link[rel="icon"]').href;
                                            })''')
                                            self.assertTrue(loaded, 'the favicon bytes must decode as an image')
                                        page.close()
                                        seen += 1
                            finally:
                                context.close()
                finally:
                    browser.close()
        self.assertGreaterEqual(seen, 28)
        print(f'Branding render matrix: {seen} page/scheme/script/engine combinations')


if __name__ == '__main__':
    unittest.main()
