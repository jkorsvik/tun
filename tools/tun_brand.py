#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Offline identity defaults for all Tún builders. Standard library only.

Apply to the template BEFORE inserting user data. The visible hint is removable;
the separate Origin Notice is not. Favicon order: CLI, environment, the plugin
owning the selected palette, then Tún. Merely installing a plugin changes nothing.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import html
import json
import os
import pathlib
import re
import urllib.parse
import xml.etree.ElementTree as ET

import tun_tokens

# Same square mark as plugins/tun/assets/mark.svg. The contract test compares the
# parsed trees. Kept here so a vendored core needs no plugin or extra asset file.
DEFAULT_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" class="logo" viewBox="0 0 160 160" role="img" aria-label="Tún">
    <rect x="6" y="6" width="148" height="148" rx="26" fill="none" stroke="#0d2b21" stroke-width="7"/>
    <text x="80" y="112" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif"
          font-size="86" font-weight="500" fill="#0d2b21" letter-spacing="1">u</text>
    <path d="M69 48 l11 12 22 -25" fill="none" stroke="#3f8f3f" stroke-width="9"
          stroke-linecap="round" stroke-linejoin="round"/>
  </svg>'''
MAX_ICON_BYTES = 256 * 1024
HINT = '<span class="tun-credit"> <a href="https://tun.community" rel="noreferrer">Tún · tun.community</a></span>'
CSS = ('.tun-credit{font-size:inherit;font-weight:400;white-space:normal}'
       '.tun-credit a{color:inherit;text-decoration:underline;text-underline-offset:.15em}'
       '.tun-credit a:hover{color:inherit;text-decoration-thickness:.125em}'
       '.tun-credit a:focus-visible{outline:.125rem solid currentColor;outline-offset:.25rem}')


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--favicon', metavar='FILE_OR_DATA_URI',
                        help='inline a local SVG, PNG, ICO, GIF, JPEG or WebP icon; '
                             'none disables the icon (default: TUN_FAVICON, selected '
                             'palette plugin assets.favicon, then the Tún square mark)')
    parser.add_argument('--no-tun-hint', action='store_true',
                        help='omit the visible Tún link; keep the Origin Notice')


def plugin_favicon(palette: str | pathlib.Path | None) -> pathlib.Path | None:
    if not palette:
        return None
    palette = pathlib.Path(palette).expanduser()
    if not palette.is_absolute():
        palette = tun_tokens.REPO / palette
    palette = palette.resolve()
    # Only the selected palette's owner, not every installed plugin. This also
    # works for a private plugin outside the checkout.
    for folder in palette.parents:
        manifest = folder / 'manifest.json'
        if not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue  # An unrelated ancestor's manifest is not a selected plugin.
        if not isinstance(data, dict) or not isinstance(data.get('tokens'), dict):
            continue
        mapped = data['tokens'].get('palette')
        if not isinstance(mapped, str) or (folder / mapped).resolve() != palette:
            continue
        assets = data.get('assets', {})
        if not isinstance(assets, dict):
            raise ValueError('selected plugin assets must be a map')
        asset = assets.get('favicon')
        if asset is None:
            return None
        if not isinstance(asset, str) or not asset:
            raise ValueError('assets.favicon must name a local file')
        target = (folder / asset).resolve()
        if not target.is_relative_to(folder.resolve()):
            raise ValueError('assets.favicon must stay inside its plugin')
        return target
    return None


def validate_svg(raw: bytes) -> None:
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('favicon SVG must use UTF-8') from exc
    without_declaration = re.sub(r'^\s*<\?xml\s[^?]*\?>', '', text)
    if '<?' in without_declaration or '<![CDATA[' in text:
        raise ValueError('favicon SVG must not contain processing instructions or CDATA')
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('favicon SVG must not declare entities or a doctype')
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError(f'favicon is not valid SVG: {exc}') from exc
    ns = '{http://www.w3.org/2000/svg}'
    if root.tag != ns + 'svg' or not root.get('viewBox'):
        raise ValueError('favicon SVG needs the SVG namespace and a viewBox')
    # A passive image, never a document which runs code or fetches a resource.
    allowed = {'svg', 'g', 'defs', 'title', 'desc', 'path', 'rect', 'circle',
               'ellipse', 'line', 'polyline', 'polygon', 'text', 'tspan', 'use',
               'linearGradient', 'radialGradient', 'stop', 'clipPath', 'mask'}
    allowed_tags = {ns + name for name in allowed}
    for node in root.iter():
        if node.tag not in allowed_tags:
            raise ValueError('favicon SVG contains an unsupported active or embedded element')
        for name, value in node.attrib.items():
            name = name.rsplit('}', 1)[-1].lower()
            if name.startswith('on') or name in ('base', 'src', 'style'):
                raise ValueError('favicon SVG contains an active attribute')
            if name == 'href' and not value.startswith('#'):
                raise ValueError('favicon SVG must not fetch resources')
            urls = re.findall(r'url\s*\(([^)]*)\)', value, re.I)
            if any(not url.strip().strip('\'"').startswith('#') for url in urls) or '@' in value or '\\' in value:
                raise ValueError('favicon SVG must not fetch resources or import CSS')


def image_type(raw: bytes) -> str:
    if len(raw) > MAX_ICON_BYTES or not raw:
        raise ValueError('favicon must contain 1 to 262144 bytes')
    for magic, mime in ((b'\x89PNG\r\n\x1a\n', 'image/png'), (b'\x00\x00\x01\x00', 'image/x-icon'),
                        (b'GIF87a', 'image/gif'), (b'GIF89a', 'image/gif'),
                        (b'\xff\xd8\xff', 'image/jpeg')):
        if raw.startswith(magic):
            return mime
    if raw.startswith(b'RIFF') and raw[8:12] == b'WEBP':
        return 'image/webp'
    validate_svg(raw)
    return 'image/svg+xml'


def favicon_link(value: str | pathlib.Path | None = None,
                 palette: str | pathlib.Path | None = None) -> str:
    chosen = value if value is not None else os.environ.get('TUN_FAVICON')
    if chosen is None:
        chosen = plugin_favicon(os.environ.get('TUN_PALETTE') or palette)
    if chosen is None:
        raw = DEFAULT_SVG.encode('utf-8')
    elif str(chosen) == 'none':
        # Suppress the browser's implicit /favicon.ico request too.
        return '<link rel="icon" href="data:,">'
    elif str(chosen).startswith('data:'):
        header, sep, payload = str(chosen).partition(',')
        if not sep or len(payload) > MAX_ICON_BYTES * 4:
            raise ValueError('favicon data URI is missing its payload or is too large')
        try:
            raw = (base64.b64decode(payload, validate=True) if header.endswith(';base64')
                   else urllib.parse.unquote_to_bytes(payload))
        except (ValueError, binascii.Error) as exc:
            raise ValueError('favicon data URI has invalid encoding') from exc
        mime = image_type(raw)
        declared = header[5:].split(';', 1)[0].lower()
        if declared != mime and not (mime == 'image/x-icon' and declared == 'image/vnd.microsoft.icon'):
            raise ValueError('favicon data URI media type does not match its image')
    else:
        try:
            with pathlib.Path(chosen).expanduser().open('rb') as handle:
                raw = handle.read(MAX_ICON_BYTES + 1)
        except OSError as exc:
            raise ValueError(f'cannot read favicon: {exc.strerror}') from exc
    mime = image_type(raw)
    if mime == 'image/svg+xml':
        raw = re.sub(rb'<!--.*?-->', b'', raw, flags=re.S).strip()
        validate_svg(raw)  # Validate the exact bytes that will be emitted.
    uri = ('data:image/svg+xml,' + urllib.parse.quote(raw.decode('utf-8'), safe='')
           if mime == 'image/svg+xml' else
           f'data:{mime};base64,' + base64.b64encode(raw).decode('ascii'))
    return f'<link rel="icon" type="{mime}" href="{html.escape(uri, quote=True)}">'


def apply(template: str, args: argparse.Namespace | None = None, *,
          favicon: str | pathlib.Path | None = None, no_hint: bool = False,
          palette: str | pathlib.Path | None = None) -> str:
    """Fill identity slots once, before data substitution. No user text is scanned."""
    if args is not None:
        favicon, no_hint = args.favicon, args.no_tun_hint
    values = {'TUN_FAVICON': favicon_link(favicon, palette),
              'TUN_CREDIT': '' if no_hint else HINT,
              'TUN_CREDIT_CSS': '' if no_hint else CSS}
    return re.sub(r'\{\{(TUN_FAVICON|TUN_CREDIT|TUN_CREDIT_CSS)\}\}',
                  lambda match: values[match.group(1)], template)


def prepare(template: str, args: argparse.Namespace) -> str:
    """Builder adapter: fail before writing anything, without a Python traceback."""
    try:
        return apply(template, args)
    except ValueError as exc:
        raise SystemExit(f'error: favicon: {exc}') from exc
