#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
check_export_clean.py — refuse an export that still carries identifying text.

Stdlib only. Run it over the tree you are about to hand to someone else:

    python3 tools/check_export_clean.py                 # this checkout's tracked files
    python3 tools/check_export_clean.py --root ../out   # any other tree (git or plain dir)

Why the terms are not in this file
----------------------------------
The thing being searched for is identifying by definition: names of people, the
organisation, internal hosts, internal programme names. A tracked list of those terms
would leak exactly what the gate exists to keep out. So the terms live in a local,
untracked file, one case-insensitive regex per line:

    $TUN_DENYLIST, or else ~/.config/tun/denylist.txt

    # comment
    label<TAB>regex

A missing or empty denylist is an error, never a pass. A gate that silently checks
nothing is worse than no gate.

What it reads
-------------
Every file in scope, as bytes, decoded leniently, so a term inside an image's metadata
or a minified vendor file is found too. File *paths* are checked as well: a directory
named after a person is as identifying as a sentence. Text drawn as pixels inside a
screenshot cannot be read here; regenerate screenshots from clean sources instead.

Findings are printed as label + file:line + a redacted match, so the log does not
become a second copy of what it found.

Exit codes: 0 clean, 1 findings, 2 the check could not run.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import gzip
import io
import zlib
import json
import os
import pathlib
import re
import subprocess
import sys

DEFAULT_DENYLIST = pathlib.Path.home() / ".config" / "tun" / "denylist.txt"

# Generic shapes that are never identifying to list here, checked on every run.
BUILTIN = [
    ("email", r"\b[A-Za-z0-9._%+-]+@(?!(?:example\.(?:com|org|net)|tun\.community)\b)[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b"),
    ("ci run id", r"\brun \d{6,}\b"),
]

# The gate itself names the shapes above; its own source is not an export risk.
SELF = "tools/check_export_clean.py"
#: Tools whose SUBJECT is the terms themselves: a scan that hunts identifying words has to
#: hold them to work, and rewriting them inside such a tool turns it into a scan for the
#: replacements. That is not a hole in the export, it is the shape of the tool.
SELF_TOOLS = (SELF, "tools/check_core_is_generic.py",
              "tests/test_core_boundary_gate.py",
              # The i18n table records "this old value became that new one". Its subject is the
              # terms, and in a single-commit export the section that reads the table does not
              # run at all, so nothing there is usage.
              "tests/test_i18n.py")


def load_denylist(path: pathlib.Path) -> list[tuple[str, re.Pattern]]:
    if not path.is_file():
        raise SystemExit(f"✗ denylist not found: {path}\n"
                         "  Set TUN_DENYLIST or create ~/.config/tun/denylist.txt. "
                         "Refusing to report clean without one.")
    rules = []
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        label, sep, rx = line.partition("\t")
        if not sep:
            label, rx = "term", line
        try:
            rules.append((label.strip(), re.compile(rx.strip(), re.IGNORECASE)))
        except re.error as e:
            raise SystemExit(f"✗ denylist line {n} is not a valid regex: {e}")
    if not rules:
        raise SystemExit(f"✗ denylist is empty: {path}. Refusing to report clean.")
    return rules


def list_files(root: pathlib.Path) -> list[str]:
    # A git hook exports GIT_DIR/GIT_INDEX_FILE, which override `git -C` entirely.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    if (root / ".git").exists():
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                             capture_output=True, env=env)
        if out.returncode != 0:
            raise SystemExit(f"✗ git ls-files failed in {root}: {out.stderr.decode().strip()}")
        return [p for p in out.stdout.decode().split("\0") if p]
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")
                  if p.is_file() and ".git" not in p.relative_to(root).parts)


#: A copyright notice names its holder on purpose: that is attribution, not a leak.
#: Only the "person" label is exempt, and only on the notice line itself, so the same
#: name anywhere else in the file is still caught, and an organisation named as holder
#: is still caught. Line count is preserved so reported line numbers stay right.
COPYRIGHT_LINE = re.compile(r"(?mi)^[^\n]*\b(?:Copyright \(C\)|SPDX-FileCopyrightText:)[ \t]*\d{4}\b[^\n]*$")
NOTICE_EXEMPT = ("person",)


PUBLIC_ORIGIN = re.compile(r'https://(?:github\.com/jkorsvik/tun(?:\.git)?|jkorsvik\.github\.io/tun)(?=[/#?"\'\s]|$)')


def strip_public_origin(text: str) -> str:
    """The already-public source and Pages origin, never an arbitrary handle."""
    return PUBLIC_ORIGIN.sub(lambda m: ' ' * len(m.group(0)), text)


def strip_copyright_lines(text: str) -> str:
    return COPYRIGHT_LINE.sub("", text)


#: A declared attribution region. Everything between these markers is deliberate
#: identification: who made this, who named it, who holds copyright. Such a region is the
#: opposite of the leak this gate hunts, so the identity categories skip it.
#:
#: Region-based rather than file-based on purpose. Exempting a whole README would let a
#: colleague's name drift into an unrelated paragraph and count as attribution; a region
#: says exactly which lines were reviewed as intentional, in the source, where the next
#: reader sees it.
ATTRIBUTION_START = "<!-- attribution:start -->"
ATTRIBUTION_END = "<!-- attribution:end -->"

#: Here only the person label is exempt inside the region: crediting the authors by name
#: is the point of the region, but an organisation named there is still caught.
ATTRIBUTION_EXEMPT = ("person",)


def strip_attribution(text: str) -> str:
    """Remove declared attribution regions, preserving line count so reported line numbers
    stay usable. An unterminated region is NOT stripped: a stray opening marker would
    otherwise silently exempt the rest of a file, which is a hole with a comment on it."""
    out, pos = [], 0
    while True:
        start = text.find(ATTRIBUTION_START, pos)
        if start == -1:
            out.append(text[pos:])
            return "".join(out)
        end = text.find(ATTRIBUTION_END, start)
        if end == -1:
            # Unterminated: keep the remainder so it is still scanned, and let the
            # dedicated test complain about the malformed marker.
            out.append(text[pos:])
            return "".join(out)
        end += len(ATTRIBUTION_END)
        out.append(text[pos:start])
        out.append("\n" * text.count("\n", start, end))
        pos = end


#: Attribution in JSON, where the comment markers above cannot live. Claude Code fixes the
#: path and the shape of these two manifests, and it requires a human name in each: the same
#: attribution the copyright notice makes. Exactly one value per file is exempt: the one at
#: this key path. A name in `description`, `keywords` or anywhere else in the same file still
#: counts, because the exemption subtracts the hits inside that one parsed value rather than
#: skipping the file. Only the person label is exempt: an organisation, host or colour inside
#: the name field is still a leak. A declared manifest that is not plain JSON (see
#: manifest_subjects) is a finding of its own, never a fallback. tools/check_core_is_generic.py
#: uses these same definitions.
JSON_ATTRIBUTION: dict[str, tuple[str, ...]] = {
    ".claude-plugin/marketplace.json": ("owner", "name"),
    ".claude-plugin/plugin.json": ("author", "name"),
}
JSON_ATTRIBUTION_EXEMPT = ("person",)
MANIFEST_SHAPE = "manifest-shape"      # the label of a finding about a manifest that is not plain JSON


def _strings(node) -> list[str]:
    """Every key and string value in a parsed JSON document, decoded."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [t for k, v in node.items() for t in [k, *_strings(v)]]
    if isinstance(node, list):
        return [t for v in node for t in _strings(v)]
    return []


class DuplicateKey(ValueError):
    """A JSON object repeated a key. json.loads would keep only the last value."""


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict:
    """object_pairs_hook: refuse a repeated key at any depth.

    json.loads keeps the last value of a repeated key, so the first one would ship in the
    file but never reach the scan. Strict validators accept such a file."""
    keys = [k for k, _v in pairs]
    dup = sorted({k for k in keys if keys.count(k) > 1})
    if dup:
        raise DuplicateKey(f"duplicate key(s): {', '.join(dup)}")
    return dict(pairs)


def _no_constants(name: str):
    """parse_constant hook: refuse NaN, Infinity and -Infinity. Python's json accepts them,
    JSON does not, and a strict validator will not read a file that holds one."""
    raise ValueError(f"not JSON: {name}")


class NotPlainJson(ValueError):
    """A declared manifest the gate cannot parse as plain, unambiguous JSON."""


def manifest_subjects(rel: str, text: str) -> tuple[str, str] | None:
    """For a declared JSON manifest, the two texts the person scan reads, else None.

    Returns (raw text with the attribution value removed, decoded strings with that one
    value blanked). A hit in either counts: the raw form catches a literal name, the
    decoded form catches one written as \\u escapes. Duplicate keys are refused at any
    depth, because json.loads keeps only the last value and the first would ship unseen.

    Raises NotPlainJson for anything that does not parse: invalid JSON, a repeated key, a
    leading BOM, trailing data, NaN or Infinity, nesting too deep. There is no fallback and
    no exemption, because a validator that tolerates the file is not evidence that a scan of
    it is complete. The gate reports it as a finding instead."""
    path = JSON_ATTRIBUTION.get(rel)
    if path is None:
        return None
    try:
        doc = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_no_constants)
        parent, value = doc, ""
        for key in path[:-1]:
            parent = parent.get(key) if isinstance(parent, dict) else None
        if isinstance(parent, dict) and isinstance(parent.get(path[-1]), str):
            value = parent[path[-1]]
            parent[path[-1]] = ""
        decoded = "\n".join(_strings(doc))
    except (ValueError, RecursionError) as exc:  # ValueError includes DuplicateKey
        raise NotPlainJson(rel) from exc
    raw = text
    if value:
        # Attribution must be written plainly: only canonical spellings are stripped, an escaped one is rejected (fails closed).
        for form in {json.dumps(value), json.dumps(value, ensure_ascii=False)}:
            raw = raw.replace(form, '""')
    return raw, decoded


def redact(s: str) -> str:
    s = s.strip()
    return s[:1] + "…" * min(len(s) - 1, 3) + f"({len(s)})" if s else "(empty)"


# Encoded carriers are not prose. Decode every one, scan textual contents and
# reject malformed base64/gzip. Mask only the encoded bytes in the parent, so
# entropy cannot masquerade as an identity. Nested pages receive the same scan.
PAYLOAD = re.compile(
    r'<[^>]+\bdata-live=["\'](?P<live>[^"\']*)["\']'
    r'|data:(?P<mime>image/[A-Za-z0-9+.-]+|text/[A-Za-z0-9+.-]+);base64,(?P<data>[A-Za-z0-9+/=]+)'
    r'|<script\b[^>]*\btype="application/gzip;base64"[^>]*>(?P<gzip>[^<]*)<', re.I)
MAX_PAYLOAD_BYTES = 50 * 1024 * 1024


class PayloadError(ValueError):
    """An encoded carrier cannot be checked completely."""


def payload_subjects(text: str, depth: int = 0, budget=None):
    """Return masked HTML and decoded children, bounded across the whole file."""
    if budget is None:
        budget = [MAX_PAYLOAD_BYTES]
    matches = list(PAYLOAD.finditer(text))
    if matches and depth >= 5:
        raise PayloadError('payload nesting exceeds five levels')
    children = []
    masked = text
    for index, match in reversed(list(enumerate(matches, 1))):
        kind = next(k for k in ('live', 'data', 'gzip') if match.group(k) is not None)
        chunk = match.group(kind)
        if chunk.startswith('{{') and chunk.endswith('}}'):
            continue  # Source templates are not built carriers.
        if kind == 'live' and not chunk.startswith('gzip:'):
            raise PayloadError(f'live payload {index} is not marked as gzip')
        compressed = kind in ('gzip', 'live')
        encoded = chunk[5:] if kind == 'live' else chunk
        encoded = re.sub(r'\s+', '', encoded)
        if len(encoded) > (budget[0] + 2) * 4 // 3 + 4:
            raise PayloadError(f'payload {index} exceeds the size budget')
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise PayloadError(f'payload {index} is not valid base64') from exc
        if compressed:
            try:
                with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
                    raw = stream.read(budget[0] + 1)
            except (OSError, EOFError, zlib.error) as exc:
                raise PayloadError(f'gzip payload {index} does not inflate') from exc
        budget[0] -= len(raw)
        if budget[0] < 0:
            raise PayloadError(f'payload {index} exceeds the inflated file budget')
        start, end = match.span(kind)
        masked = masked[:start] + re.sub(r'[^\n]', ' ', chunk) + masked[end:]
        # Only known raster formats are not prose. The numeric cube is binary,
        # but scanning its decoded bytes still exposes an embedded ASCII label.
        raster = (raw.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF87a', b'GIF89a', b'\0\0\1\0'))
                  or raw.startswith(b'RIFF') and raw[8:12] == b'WEBP')
        if kind == 'data' and raster:
            continue
        try:
            inner = raw.decode('utf-8') if kind != 'gzip' else raw.decode('utf-8', errors='replace')
        except UnicodeDecodeError as exc:
            raise PayloadError(f'text payload {index} is not UTF-8') from exc
        children.extend(payload_subjects(inner, depth + 1, budget))
    return [masked, *children]


def strip_binary_payloads(text: str) -> str:
    """Do not interpret image entropy in source-code literals as prose."""
    return re.sub(r';base64,[A-Za-z0-9+/=]{64,}', lambda m: ' ' * len(m.group(0)), text)


def scan(root: pathlib.Path, rules) -> tuple[int, list[tuple[str, str, int, str]]]:
    files = list_files(root)
    if not files:
        raise SystemExit(f"✗ no files in scope under {root}. Refusing to report clean.")
    hits = []
    for rel in files:
        for label, rx in rules:
            for m in rx.finditer(rel):
                hits.append((label, rel, 0, redact(m.group(0))))
        if rel in SELF_TOOLS:
            continue
        p = root / rel
        if not p.is_file():
            continue
        # "replace", not "ignore": an invalid byte must break a match, never glue two
        # fragments of binary data into one (a PNG once decoded to a fake email).
        text = p.read_bytes().decode("utf-8", errors="replace")
        try:
            subjects = payload_subjects(text) if rel.endswith(".html") else [strip_binary_payloads(text)]
        except PayloadError as exc:
            hits.append(('payload', rel, 1, str(exc)))
            continue
        for subject_index, text in enumerate(subjects):
            noticed = strip_copyright_lines(text)
            credited = strip_attribution(noticed)
            try:
                manifest = manifest_subjects(rel, text) if subject_index == 0 else None
            except NotPlainJson:
                manifest = None
                hits.append((MANIFEST_SHAPE, rel, 1, "not plain JSON"))
            prose = text
            for label, rx in rules:
                subject = prose
                if label in NOTICE_EXEMPT:
                    subject = strip_public_origin(noticed)
                if label in ATTRIBUTION_EXEMPT:
                    subject = strip_public_origin(credited)
                if manifest is not None and label in JSON_ATTRIBUTION_EXEMPT:
                    subject = manifest[0]
                found = list(rx.finditer(subject))
                for m in found:
                    line = subject.count("\n", 0, m.start()) + 1
                    hits.append((label, rel, line, redact(m.group(0)) + (" decoded payload" if subject_index else "")))
                if manifest is not None and label in JSON_ATTRIBUTION_EXEMPT:
                    # A name written as \u escapes is invisible to the raw text: count the
                    # decoded strings too, and report what the raw text did not already show.
                    for m in list(rx.finditer(manifest[1]))[len(found):]:
                        hits.append((label, rel, 1, redact(m.group(0)) + " decoded"))
    return len(files), hits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=None, help="tree to check (default: this repository)")
    ap.add_argument("--denylist", default=os.environ.get("TUN_DENYLIST") or str(DEFAULT_DENYLIST))
    args = ap.parse_args(argv)

    root = pathlib.Path(args.root).resolve() if args.root else pathlib.Path(__file__).resolve().parents[1]
    try:
        rules = load_denylist(pathlib.Path(args.denylist).expanduser())
        rules += [(label, re.compile(rx, re.IGNORECASE)) for label, rx in BUILTIN]
        n, hits = scan(root, rules)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2

    for label, rel, line, shown in hits:
        where = f"{rel} (path)" if line == 0 else f"{rel}:{line}"
        print(f"  ✗ {label:<10} {where}  {shown}")
    print("─" * 72)
    verdict = "✓ PASS" if not hits else f"✗ FAIL — {len(hits)} finding(s)"
    print(f"{verdict}: checked {n} file(s) against {len(rules)} pattern(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
