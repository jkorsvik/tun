#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Identity defaults and overrides are shared by every builder. Stdlib only."""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
import xml.etree.ElementTree as ET
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import tun_brand as brand


class Branding(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = pathlib.Path(self.temp.name)
        self.icon = self.folder / 'custom icon.svg'
        self.icon.write_text(brand.DEFAULT_SVG.replace('>u<', '>x<'), encoding='utf-8')

    def test_default_is_the_square_mark_without_a_plugin(self):
        def shape(node):
            return node.tag, node.attrib, (node.text or '').strip(), [shape(c) for c in node]
        mark = (ROOT / 'plugins/tun/assets/mark.svg').read_text(encoding='utf-8')
        self.assertEqual(shape(ET.fromstring(mark)), shape(ET.fromstring(brand.DEFAULT_SVG)))
        link = brand.favicon_link()
        self.assertIn('image/svg+xml', link)
        self.assertIn(urllib.parse.quote(brand.DEFAULT_SVG, safe=''), link)
        # The default code never reads plugins/, including after vendoring.
        with patch.object(brand, 'plugin_favicon', return_value=None):
            self.assertEqual(brand.favicon_link(), link)

    def test_cli_wins_over_env_and_env_over_plugin(self):
        os.environ['TUN_FAVICON'] = 'missing-file.svg'
        self.assertIn('data:,', brand.favicon_link('none'))
        with self.assertRaisesRegex(ValueError, 'cannot read favicon'):
            brand.favicon_link()
        os.environ['TUN_FAVICON'] = str(self.icon)
        self.assertIn('%3Ex%3C', brand.favicon_link())
        with patch.object(brand, 'plugin_favicon', side_effect=AssertionError('not selected')):
            self.assertIn('%3Ex%3C', brand.favicon_link())
        os.environ['TUN_FAVICON'] = ''
        with self.assertRaises(ValueError):
            brand.favicon_link()  # empty is an explicit invalid choice, not fallback

    def test_data_uri_and_local_files(self):
        raw = self.icon.read_bytes()
        uri = 'data:image/svg+xml;base64,' + base64.b64encode(raw).decode('ascii')
        self.assertEqual(brand.favicon_link(uri), brand.favicon_link(self.icon))
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLttAAAAABJRU5ErkJggg==')
        uri = 'data:image/png;base64,' + base64.b64encode(png).decode('ascii')
        self.assertIn(uri, brand.favicon_link(uri))
        for bad in ['data:image/svg+xml;base64,!@', 'data:image/png,hello',
                    'data:text/html,' + urllib.parse.quote(brand.DEFAULT_SVG),
                    'data:image/svg+xml', 'https://example.com/icon.svg']:
            with self.subTest(bad=bad[:40]), self.assertRaises(ValueError):
                brand.favicon_link(bad)
        with self.assertRaises(ValueError):
            brand.image_type(b'x' * (brand.MAX_ICON_BYTES + 1))

    def test_only_the_selected_palette_plugin_supplies_the_asset(self):
        plugin = self.folder / 'plugin'
        (plugin / 'tokens').mkdir(parents=True)
        (plugin / 'assets').mkdir()
        palette = plugin / 'tokens/palette.css'
        palette.touch()
        asset = plugin / 'assets/icon.svg'
        asset.write_bytes(self.icon.read_bytes())
        data = {'provides': ['tokens', 'assets'], 'tokens': {'palette': 'tokens/palette.css'},
                'assets': {'favicon': 'assets/icon.svg'}}
        manifest = plugin / 'manifest.json'
        manifest.write_text(json.dumps(data), encoding="utf-8")
        os.environ['TUN_PALETTE'] = str(palette)
        self.assertEqual(brand.favicon_link(), brand.favicon_link(asset))
        del os.environ['TUN_PALETTE']
        self.assertEqual(brand.favicon_link(palette=palette), brand.favicon_link(asset))
        self.assertNotEqual(brand.favicon_link(), brand.favicon_link(asset))
        data['assets']['favicon'] = '../custom icon.svg'
        manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, 'inside its plugin'):
            brand.favicon_link(palette=palette)
        data['assets']['favicon'] = 'assets/missing.svg'
        manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, 'cannot read favicon'):
            brand.favicon_link(palette=palette)

    def test_active_svg_is_refused_and_local_gradients_work(self):
        start = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"'
        for body in [' onload="alert(1)"></svg>', '><script/></svg>',
                     '><foreignObject/></svg>', '><image href="https://example.com/x"/></svg>',
                     '><use href="file:///private/x"/></svg>',
                     '><path style="fill:url( https://example.com/x)"/></svg>',
                     ' xml:base="https://example.com/"><use href="#x"/></svg>',
                     '><animate attributeName="href" to="https://example.com/x"/></svg>']:
            with self.subTest(body=body), self.assertRaises(ValueError):
                brand.validate_svg((start + body).encode())
        brand.validate_svg((start + '><path fill="url(\'#paint\')"/></svg>').encode())

    def test_review_regressions_fail_closed(self):
        raw = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1">'
               '<?x <!--?><text><![CDATA[-->?><script>alert(1)</script>'
               '<text><![CDATA[]]></text></svg>')
        with self.assertRaises(ValueError):
            brand.favicon_link('data:image/svg+xml,' + urllib.parse.quote(raw))
        with self.assertRaises(ValueError):
            brand.validate_svg(brand.DEFAULT_SVG.encode('utf-16'))
        raw = brand.DEFAULT_SVG.replace('class="logo"',
              'style="background-image:image-set(https://example.com/a 1x)"')
        with self.assertRaises(ValueError):
            brand.validate_svg(raw.encode())
        # Unrelated parent manifests do not turn an ordinary CSS file into a plugin.
        palette = self.folder / 'ordinary.css'
        palette.touch()
        (self.folder / 'manifest.json').write_text('["pwa"]', encoding="utf-8")
        self.assertIsNone(brand.plugin_favicon(palette))
        with patch.object(brand.tun_tokens, 'REPO', self.folder):
            self.assertIsNone(brand.plugin_favicon('ordinary.css'))
        plugin = self.folder / 'owner'
        plugin.mkdir()
        (plugin / 'palette.css').touch()
        (plugin / 'icon.svg').write_bytes(self.icon.read_bytes())
        (plugin / 'manifest.json').write_text(json.dumps({
            'tokens': {'palette': 'palette.css'}, 'assets': {'favicon': 'icon.svg'}}), encoding='utf-8')
        with patch.object(brand.tun_tokens, 'REPO', self.folder):
            self.assertEqual(brand.plugin_favicon('owner/palette.css'), (plugin / 'icon.svg').resolve())

    def test_apply_is_removable_and_does_not_change_origin(self):
        template = '<!-- Made with: Tún - tun.community -->{{TUN_FAVICON}}<style>{{TUN_CREDIT_CSS}}</style><footer>{{TUN_CREDIT}}</footer>'
        page = brand.apply(template)
        self.assertEqual(page.count('href="https://tun.community"'), 1)
        hidden = brand.apply(template, no_hint=True, favicon='none')
        self.assertNotIn('https://tun.community', hidden)
        self.assertIn('<!-- Made with: Tún - tun.community -->', hidden)
        self.assertIn('href="data:,"', hidden)
        ap = argparse.ArgumentParser()
        brand.add_arguments(ap)
        self.assertEqual(brand.prepare(template, ap.parse_args(['--no-tun-hint', '--favicon', 'none'])), hidden)

    def test_every_template_and_cli_has_the_seam(self):
        templates = [p for p in (ROOT / 'templates').glob('*.html') if not p.name.startswith('_')]
        self.assertGreaterEqual(len(templates), 27)
        builders = [p for p in (ROOT / 'tools').glob('build_*.py') if 'TEMPLATE =' in p.read_text(encoding='utf-8')]
        self.assertEqual(len(builders), len(templates))
        print(f'Branding coverage: {len(templates)} templates, {len(builders)} builder CLIs')
        for path in templates:
            with self.subTest(template=path.name):
                text = path.read_text(encoding='utf-8')
                for slot in ('TUN_FAVICON', 'TUN_CREDIT', 'TUN_CREDIT_CSS'):
                    self.assertEqual(text.count('{{' + slot + '}}'), 1)
                self.assertIn('{{TUN_FAVICON}}', text.split('</head>')[0])
        for path in builders:
            with self.subTest(builder=path.name):
                run = subprocess.run([sys.executable, str(path), '--help'], capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertIn('--favicon', run.stdout)
                self.assertIn('--no-tun-hint', run.stdout)

    def test_day_board_allows_only_inline_icon_links(self):
        import contextlib
        import importlib.util
        import io
        source = ROOT / 'examples/17-multi-regime-day-board/verify_day_board.py'
        spec = importlib.util.spec_from_file_location('brand_day_gate', source)
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        original = gate.HTML.read_text(encoding='utf-8')
        for extra, expected in (
                ('', []),
                ('<link rel="stylesheet" href="https://example.invalid/x.css">',
                 ['no fetched <link — data-URI icons are inline']),
                ('<link rel="icon" href="https://example.invalid/icon.svg">',
                 ['no fetched <link — data-URI icons are inline'])):
            probe = self.folder / 'board.html'
            probe.write_text(original.replace('</head>', extra + '</head>'), encoding='utf-8')
            failures = []
            with patch.object(gate, 'HTML', probe), contextlib.redirect_stdout(io.StringIO()):
                gate.run_brand(failures)
            self.assertEqual(failures, expected)

    def test_dashboard_cli_override_no_hint_and_hostile_data(self):
        data = self.folder / 'data.csv'
        data.write_text('Kind,Amount\n{TUN_CREDIT},1\nOther,2\n', encoding="utf-8")
        out = self.folder / 'dashboard.html'
        cmd = [sys.executable, str(ROOT / 'tools/build_dashboard.py'), '--data', str(data),
               '--title', '{TUN_FAVICON}', '--dimension', 'Kind', '--measure', 'Amount',
               '--out', str(out), '--favicon', str(self.icon), '--no-tun-hint']
        run = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        text = out.read_text(encoding='utf-8')
        self.assertIn('%3Ex%3C', text)
        self.assertNotIn('href="https://tun.community"', text)
        self.assertIn('{TUN_FAVICON}', text)
        self.assertIn('{TUN_CREDIT}', text)
        self.assertIn('Made with', text)
        # Double braces remain the existing builder refusal, not a branding slot
        # rescan. The brand helper itself is never given user data.
        data.write_text('Kind,Amount\n{{TUN_CREDIT}},1\nOther,2\n', encoding='utf-8')
        run = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('template placeholders not substituted', run.stderr)
        self.assertIn('{{TUN_CREDIT}}', run.stderr)



if __name__ == '__main__':
    unittest.main()
