#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""What every builder does before it draws anything: read a table, read a number, stop.

Five builders grew their own copy of this and the copies drifted, which is how a number
became wrong by a thousand on one of them (see `to_number` below). One home, stdlib only,
so the next artefact kind inherits the behaviour instead of re-deciding it.

Nothing here knows about a dashboard, a template, or a browser. It reads files and turns
text into values, and it stops the build with one message in one shape.
"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import sys
from typing import Any, NoReturn

# What the provenance block says when nobody named a requester. Never fall back to the OS
# user name: it put the builder's login into every committed artefact (#45). A role is what
# the block wants; a caller passes one with --requested-by.
NOT_STATED = "not stated"

# One sample size for the delimiter sniffer, on every builder. Two builders used to read
# 8 KiB and 64 KiB here, so the same file could be sniffed two ways depending on which
# builder opened it: a wide header block is not exotic in an export from a case system.
SAMPLE_BYTES = 64 * 1024

DELIMITERS = ",;\t|"
TEXT_SUFFIXES = (".csv", ".tsv", ".txt")


def die(message: str, code: int = 2) -> NoReturn:
    """Stop the build, with one line the person who ran it can act on.

    Exit 2 for every refusal: a caller that only checks "did it work" must not mistake a
    refused build for a crash, and the suite asserts the code rather than the wording.
    """
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


# --------------------------------------------------------------------------- tables
def read_rows(path: pathlib.Path) -> list[dict]:
    """A table as a list of dicts: csv/tsv/txt with a sniffed delimiter, or a JSON array.

    `utf-8-sig` because Excel's "CSV UTF-8" writes a BOM, and a BOM stuck to the first
    column name makes `--dimension Region` name a column that is not there. The error that
    follows is incomprehensible to the person who saved the file.
    """
    path = pathlib.Path(path)
    suffix = path.suffix.lower()
    if not path.exists():
        # A traceback is not an error message. The person who ran the build needs the file
        # name and the reason, and the suite asserts the exit code and the one-line shape.
        die(f"{path}: no such file")
    if suffix == ".json":
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(rows, list):
            die(f"{path.name}: expected a JSON array of objects")
        return rows
    if suffix in TEXT_SUFFIXES:
        delimiter = "\t" if suffix == ".tsv" else ","
        with path.open(newline="", encoding="utf-8-sig") as fh:
            sample = fh.read(SAMPLE_BYTES)
            fh.seek(0)
            if suffix != ".tsv":
                try:
                    delimiter = csv.Sniffer().sniff(sample, delimiters=DELIMITERS).delimiter
                except csv.Error:
                    delimiter = ","          # one column, or too little text to tell
            return list(csv.DictReader(fh, delimiter=delimiter))
    die(f"{path.name}: unsupported input. Use .csv, .tsv or .json "
        f"(convert .xlsx/.parquet first, see the tun-data skill)")


def columns(rows: list[dict]) -> list[str]:
    return list(rows[0].keys()) if rows else []


# -------------------------------------------------------------------------- numbers
def to_number(value: Any) -> float | int | None:
    """The number a cell holds, or None when it holds something else.

    Two locales write the same amount differently: `1 234,56` and `1,234.56` are both one
    thousand two hundred and thirty four and a half. When a value carries both separators
    the **last** one is the decimal separator, and that is the only reading that is not a
    guess. The dashboard builder used to assume Norwegian unconditionally, which turned an
    en-US `1,234.56` into `1.23456`: a silent factor of a thousand, on the one kind of
    error a screenshot cannot show you.

    A single separator stays a decimal separator, because that is what both builders have
    always done and `1.234` genuinely cannot be resolved without knowing the source locale.
    `to_number("1.234")` is therefore 1.234, and a Norwegian thousands separator in a
    three-digit column has to be declared by the caller if it matters.
    """
    if isinstance(value, bool):
        return None                      # True is not 1 in a table that came from a file
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip().replace("\u00a0", "").replace(" ", "")
    if not text:
        return None
    text = text.rstrip("%")
    has_comma, has_dot = "," in text, "." in text
    if has_comma and has_dot:
        decimal = "," if text.rindex(",") > text.rindex(".") else "."
        thousands = "." if decimal == "," else ","
        text = text.replace(thousands, "").replace(decimal, ".")
    elif has_comma:
        text = text.replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() and abs(number) < 2**53 else number


def number_or_zero(value: Any) -> float:
    """The same parse, with an unreadable cell counting as nothing.

    For a measure in a cube, where a missing amount must not remove the row from its cell.
    """
    number = to_number(value)
    return 0.0 if number is None else float(number)


def coerce_numbers(rows: list[dict]) -> list[dict]:
    """Turn numeric-looking strings into real numbers, per column, all or nothing.

    A column is converted only if EVERY non-empty value parses: otherwise an id column that
    happens to look numeric would be corrupted. An empty value in a converted column becomes
    None, never 0, because a 0 would move an average.
    """
    if not rows:
        return rows
    converted = []
    for col in columns(rows):
        values = [r.get(col) for r in rows if r.get(col) not in (None, "")]
        if values and all(isinstance(v, str) for v in values) \
                and all(to_number(v) is not None for v in values):
            converted.append(col)
    for row in rows:
        for col in converted:
            if col in row:
                row[col] = None if row[col] in (None, "") else to_number(row[col])
    return rows


def is_numeric_column(rows: list[dict], col: str) -> bool:
    """True when the column has at least one value and every non-empty value is a number.

    Decided on the non-empty values: a query result often has NULL in the first row.
    """
    values = [r.get(col) for r in rows if r.get(col) not in (None, "")]
    return bool(values) and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                for v in values)


def as_script_json(value) -> str:
    """JSON that is safe inside a <script> element.

    A value holding the text `</script>` ends the script element when it is written raw,
    and the rest of the value becomes markup. That is how a CSV cell turns into script in
    this repository's history, so the payload is escaped at the three characters that can
    do it: `<` and `>` (which also covers `</script>`, `<!--` and `<script`) and `&`. The
    page reads the values back unchanged, because `\u003c` is the same string in JSON.

    Lives here rather than in one builder: two builders inline data, and a second copy of
    this rule is a second place for it to be subtly weaker.
    """
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
                .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def strip_licence_header(text: str) -> str:
    """Drop a licence comment at the head of an inlined partial.

    A partial under templates/_ carries a licence notice like every other source file,
    because the licence touches the source. The artefact built from it carries its own
    notice too, and the partial is inlined into the middle of that artefact, so copying
    the header in gives a page two notices with one of them between the footer and the
    feedback link. Exactly one notice per artefact: strip at inline time, not at source.
    """
    stripped = text.lstrip("\ufeff \t\r\n")
    if stripped.startswith("<!--"):
        end = stripped.find("-->")
        if end != -1 and re.search(r"SPDX-License-Identifier|Copyright \(C\)|Artefact Exception",
                                  stripped[:end]):
            return stripped[end + 3:].lstrip("\r\n")
    return text
