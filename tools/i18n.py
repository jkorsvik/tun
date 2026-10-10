#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
i18n.py: the strings tables behind `--lang en|nb`.

Stdlib only, like the rest of tools/. Each template has one table in
`templates/i18n/<template>.strings`. A table holds a `[nb]` and an `[en]` section with the
same keys. The template carries `{{T:key}}` where a person reads a word, and a builder
swaps those for the chosen language before it fills in any data, so data is never
scanned for tokens.

File format, one entry per line:

    # a comment, only at the start of a line
    [nb]
    key = value        <- the value is everything after the first "= ", spaces included

There is no escaping and no trimming past that one space. A value is pasted into the
template exactly as written, which is how `nb` output stays byte for byte what it was
before the tables existed. That includes the three JavaScript escapes (`\\u00e5`) that
the old dashboard carried: they are kept as text on purpose.

A value goes into HTML, into a JavaScript string or into a comment, so an `en` value
never contains a quote, a backslash or a backtick. tests/test_i18n.py checks that.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re

LANGS = ("nb", "en")
DEFAULT_LANG = "nb"
# TUN_I18N_DIR is a test hook: tests/test_i18n.py points it at a damaged copy of the tables
# to prove that a missing key stops a build.
DIR = pathlib.Path(os.environ.get("TUN_I18N_DIR")
                   or pathlib.Path(__file__).resolve().parents[1] / "templates" / "i18n")
TOKEN = re.compile(r"\{\{T:([a-z0-9_]+)\}\}")


def parse(text: str, name: str = "strings") -> dict[str, dict[str, str]]:
    """Parse a strings file into {lang: {key: value}}. Raises ValueError with the line."""
    tables: dict[str, dict[str, str]] = {}
    section = None
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith("[") and line.rstrip().endswith("]"):
            section = line.strip()[1:-1]
            if section not in LANGS:
                raise ValueError(f"{name}:{n}: unknown language [{section}]")
            if section in tables:
                raise ValueError(f"{name}:{n}: [{section}] appears twice")
            tables[section] = {}
            continue
        if section is None:
            raise ValueError(f"{name}:{n}: entry before any [lang] section")
        key, sep, value = line.partition(" = ")
        if not sep and line.endswith(" ="):
            key, value = line[:-2], ""
        elif not sep:
            raise ValueError(f"{name}:{n}: expected 'key = value'")
        if not re.fullmatch(r"[a-z0-9_]+", key):
            raise ValueError(f"{name}:{n}: bad key {key!r}")
        if key in tables[section]:
            raise ValueError(f"{name}:{n}: {key} defined twice in [{section}]")
        tables[section][key] = value
    return tables


def path_for(name: str) -> pathlib.Path:
    return DIR / f"{name}.strings"


def load_all(name: str) -> dict[str, dict[str, str]]:
    """Both languages of one table, checked to hold the same keys."""
    p = path_for(name)
    tables = parse(p.read_text(encoding="utf-8"), p.name)
    for lang in LANGS:
        if lang not in tables:
            raise ValueError(f"{p.name}: no [{lang}] section")
    only = set(tables["nb"]) ^ set(tables["en"])
    if only:
        raise ValueError(f"{p.name}: keys missing in one language: {sorted(only)}")
    return tables


def load(name: str, lang: str) -> dict[str, str]:
    if lang not in LANGS:
        raise ValueError(f"unknown language {lang!r}")
    return load_all(name)[lang]


def apply(text: str, table: dict[str, str]) -> str:
    """Swap every {{T:key}} for its value. An unknown key is an error, never a blank."""
    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key not in table:
            raise KeyError(f"template uses {{{{T:{key}}}}} but the strings table has no such key")
        return table[key]
    return TOKEN.sub(sub, text)


def keys_used(text: str) -> set[str]:
    return set(TOKEN.findall(text))


SLOT = re.compile(r"\{([a-z]+)\}")


def fill(text: str, **values) -> str:
    """Fill {slot}s of a table value in ONE pass. A value that holds a slot of its own
    (a column called "{dimension}", a file called "source-{rows}.csv") is pasted as it
    is and never filled again, which chained .replace() calls would do. A slot with no
    value is left as written."""
    return SLOT.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), text)


def plural(table: dict[str, str], base: str, n: int) -> str:
    """table[base_one] for exactly one, table[base_other] otherwise, with {n} filled in."""
    return fill(table[f"{base}_{'one' if n == 1 else 'other'}"], n=n)


def group_int(n: int, lang: str) -> str:
    """1234567 as '1 234 567' (nb, a plain space as before) or '1,234,567' (en)."""
    s = f"{n:,}"
    return s.replace(",", " ") if lang == "nb" else s


def add_lang_argument(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--lang", choices=LANGS, default=DEFAULT_LANG,
                    help="language of the page chrome: labels, buttons, number format "
                         "(default nb). Your data is never translated.")
