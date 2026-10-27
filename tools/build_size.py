#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""build_size.py — one size budget for every builder.

The dashboard builder has enforced a two-stage budget for a while: warn above
20 MB, fail above 50 MB (docs/02-architecture.md). The cube, process and slide
builders had none, so an artefact that had quietly grown past the Tier 1 ceiling
was reported as built. A budget that only one builder applies is not a budget.

20 MB and 50 MB are about what a document store and a mail gateway will take,
not about what this toolkit finds convenient, so they live here once and every
builder calls the same function. Stdlib only, no imports from the builders: this
module must stay safe to vendor (docs/14).

    from build_size import enforce
    enforce(path)                     # exit 2 above 50 MB, warn above 20 MB
    enforce(path, extra_mb=0.4)       # a paired data.js counts toward the total
"""
from __future__ import annotations

import pathlib
import sys

# Keep in step with docs/02-architecture.md.
SIZE_WARN_MB = 20
SIZE_FAIL_MB = 50


def megabytes(path: pathlib.Path) -> float:
    """The file's size in MiB, or 0.0 when it is not there yet."""
    try:
        return path.stat().st_size / 1_048_576
    except OSError:
        return 0.0


def enforce(path: pathlib.Path, *, extra_mb: float = 0.0) -> float:
    """Apply the budget to one built artefact. Returns the size it counted.

    Prints to stderr and exits 2 above the ceiling, because a builder that
    returns success for an artefact nobody can distribute is lying to whoever
    runs it in a script.
    """
    total = megabytes(path) + extra_mb
    if total > SIZE_FAIL_MB:
        print(
            f"  ✗ FAIL {total:.1f} MB exceeds the {SIZE_FAIL_MB} MB Tier 1 ceiling.\n"
            f"    Pre-aggregate the data, or move to Tier 3 (docs/02-architecture.md).",
            file=sys.stderr,
        )
        sys.exit(2)
    if total > SIZE_WARN_MB:
        print(
            f"  ⚠ {total:.1f} MB is above the {SIZE_WARN_MB} MB comfort budget — "
            f"consider pre-aggregating.",
            file=sys.stderr,
        )
    return total
