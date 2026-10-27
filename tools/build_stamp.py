#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""build_stamp.py — the one place a builder reads the clock.

Every artefact stamps two times into itself: when it was built, and when the data behind it
was extracted. A reader uses both to judge whether the numbers are current, so neither may
be invented: they come from the clock and from the data file's mtime, never from a constant.

But a rebuild that changed nothing should produce the same bytes. Otherwise every rebuild of
a committed example is a diff, and nobody can tell a real change from a clock tick.

`SOURCE_DATE_EPOCH` is the reproducible-builds convention for exactly that: when it is set,
the build stamps that instant instead of the current one, in UTC, for both stamps — the
extraction time too, since a fresh clone has fresh mtimes. Unset (the normal case) behaves
exactly as before. Nothing about a normal build changes.

    SOURCE_DATE_EPOCH=1700000000 python3 tools/build_dashboard.py ... --out /tmp/a.html

Stdlib only.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import sys

VAR = "SOURCE_DATE_EPOCH"


def epoch() -> int | None:
    """The pinned instant, or None when the build should use the current time."""
    raw = os.environ.get(VAR, "").strip()
    if not raw:
        return None
    if not raw.isdigit():
        sys.exit(f"error: {VAR} must be a whole number of seconds since 1970, not {raw!r}.\n"
                 f"       Unset it to build with the current time.")
    return int(raw)


def _pinned() -> dt.datetime | None:
    e = epoch()
    return None if e is None else dt.datetime.fromtimestamp(e, tz=dt.timezone.utc)


def local(fmt: str = "%Y-%m-%d %H:%M %Z") -> str:
    """Build time with a zone name. Pinned builds are UTC, so their zone reads UTC."""
    p = _pinned()
    if p is not None:
        return p.strftime(fmt)
    return dt.datetime.now().astimezone().strftime(fmt)


def naive(fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Build time with no zone, for the templates that print a bare wall clock."""
    p = _pinned()
    return p.strftime(fmt) if p is not None else dt.datetime.now().strftime(fmt)


def from_mtime(path, fmt: str = "%Y-%m-%d %H:%M %Z", aware: bool = True) -> str:
    """Extraction time: the data file's mtime, or the pinned instant when one is set.

    git does not preserve mtimes, so a fresh clone reads as the moment of checkout. That is
    the artefact telling the truth about what it was built from; pin it when you need the
    bytes to be reproducible instead.
    """
    p = _pinned()
    if p is not None:
        return p.strftime(fmt)
    when = dt.datetime.fromtimestamp(pathlib.Path(path).stat().st_mtime)
    if aware:
        when = when.astimezone()
    return when.strftime(fmt)
