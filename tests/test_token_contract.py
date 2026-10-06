#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_token_contract.py — prove tools/tun_tokens.py enforces what docs/22 promises.

Stdlib only.

    python3 tests/test_token_contract.py

Why this exists
---------------
`docs/22-plugin-contract.md` claimed three things that no code did:

  * a palette omitting a required slot "is rejected at build time"
  * plugins are discovered through `plugins/*/manifest.json`, sorted by id
  * "exactly one plugin may provide tokens; more than one is an error"

A contract that overstates its enforcement is worse than no contract: it is read as a
guarantee, and the failure it claims to prevent stays possible. The specific failure here
is quiet — an undefined custom property leaves an unresolved `var()`, which CSS renders as
nothing, so the artefact builds, passes every gate in this repo, and shows invisible or
wrong colours.

These assertions are the reason the claims are now true. The suite also pins the *count*
of required slots against the contract document, so the two cannot drift apart silently.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import tun_tokens as tok  # noqa: E402

passed = failed = 0


def chk(label, got, want):
    global passed, failed
    if got == want:
        print(f"  PASS {label}")
        passed += 1
    else:
        print(f"  FAIL {label}: got {got!r}, wanted {want!r}")
        failed += 1


def without_env(key: str = "TUN_PALETTE"):
    """Clear TUN_PALETTE for a block. A palette left selected by an earlier command would
    silently change what every assertion below is measuring."""
    return _Cleared(key)


class _Cleared:
    def __init__(self, key):
        self.key, self.old = key, None

    def __enter__(self):
        self.old = os.environ.pop(self.key, None)

    def __exit__(self, *_exc):
        if self.old is not None:
            os.environ[self.key] = self.old
        else:
            os.environ.pop(self.key, None)


print("the required slots are the measured seam, and the doc agrees")
chk("there are 8 required slots", len(tok.REQUIRED_SLOTS), 8)
chk("no duplicates", len(set(tok.REQUIRED_SLOTS)), len(tok.REQUIRED_SLOTS))
contract = (REPO / "docs" / "22-plugin-contract.md").read_text(encoding="utf-8")
for slot in tok.REQUIRED_SLOTS:
    chk(f"{slot} is documented in docs/22", slot in contract, True)
# Every slot core's theme files actually consume must be required. A theme referencing a
# slot nobody requires is the undefined-var() bug with extra steps.
theme_css = "".join((REPO / "tools" / "tokens" / n).read_text(encoding="utf-8")
                    for n in ("theme-light.css", "theme-dark.css"))
import re  # noqa: E402
referenced = {m for m in re.findall(r"var\((--palette-[a-z-]+)\)", theme_css)}
chk("every --palette-* the themes reference is a required slot",
    sorted(referenced - set(tok.REQUIRED_SLOTS)), [])

# Core must pass its own suite with plugins/ absent -- that is invariant 3, and a test
# that requires the plugin to exist would make the core-only tree fail for the wrong
# reason. Plugin-specific assertions are therefore conditional, and the condition is
# reported so a skip is never mistaken for a pass.
HAVE_PLUGINS = bool(tok.discover_plugins())
print(f"\nplugins installed: {HAVE_PLUGINS}"
      f"{'' if HAVE_PLUGINS else '  (plugin assertions skipped, core-only tree)'}")

print("\nthe shipped palette(s) satisfy the contract")
_palettes = ["tools/tokens/palette-neutral.css"]
if HAVE_PLUGINS:
    _palettes.append("plugins/eksempel/tokens/palette.css")
for rel_path in _palettes:
    path = REPO / rel_path
    if not path.is_file():
        chk(f"{rel_path} exists", False, True)
        continue
    chk(f"{rel_path} defines every required slot",
        tok.missing_slots(path.read_text(encoding="utf-8")), [])

print("\ncore pins neutral, so a rebuild cannot re-brand core")
# This is the assertion that protects the extraction. If an installed plugin won by
# default, rebuilding any core example would write brand values back into core files and
# the boundary ratchet would regress on the next commit.
with without_env():
    path, source = tok.palette_path()
    chk("default resolves to core's neutral palette", path, tok.NEUTRAL_PALETTE)
    chk("and says so", source, "core:neutral")
    if HAVE_PLUGINS:
        plugin_path, plugin_source = tok.palette_path(prefer_plugin=True)
        chk("prefer_plugin resolves to the plugin that provides tokens",
            plugin_path.is_file() and "plugins/" in str(plugin_path), True)
        chk("and names the plugin", plugin_source.startswith("plugin:"), True)
    else:
        # With no plugin installed, prefer_plugin must still yield a working palette
        # rather than raising: core has to build either way.
        chk("prefer_plugin falls back to neutral when no plugin is installed",
            tok.palette_path(prefer_plugin=True)[1], "core:neutral")

print("\na palette missing a slot is REJECTED, which is the contract's core claim")
chk("missing_slots finds a missing slot",
    tok.missing_slots(":root{--palette-ink:#000}") == list(tok.REQUIRED_SLOTS[1:]), True)
chk("a mention without a definition does not count",
    "--palette-surface" in tok.missing_slots("/* --palette-surface is nice */"), True)
try:
    tok.validate_palette(":root{--palette-ink:#000}", "test")
    chk("validate_palette raises on an incomplete palette", False, True)
except SystemExit as exc:
    chk("validate_palette raises on an incomplete palette", True, True)
    chk("the error names the slots that are missing",
        "--palette-surface" in str(exc), True)
    chk("the error explains why it matters (unresolved var renders as nothing)",
        "var()" in str(exc), True)
try:
    tok.validate_palette((REPO / "tools/tokens/palette-neutral.css").read_text("utf-8"),
                         "test")
    chk("validate_palette accepts a complete palette", True, True)
except SystemExit:
    chk("validate_palette accepts a complete palette", False, True)

print("\nTUN_PALETTE is validated, not trusted")
os.environ["TUN_PALETTE"] = "does/not/exist.css"
try:
    tok.palette_path()
    chk("a nonexistent TUN_PALETTE fails loudly", False, True)
except SystemExit as exc:
    chk("a nonexistent TUN_PALETTE fails loudly", True, True)
    # Falling back to neutral would produce a plausible artefact in the wrong colours,
    # which is the failure mode that is hardest to notice.
    chk("it does not silently fall back to neutral", "does/not/exist.css" in str(exc), True)
finally:
    os.environ.pop("TUN_PALETTE", None)

with tempfile.TemporaryDirectory() as td:
    bad = pathlib.Path(td) / "bad.css"
    bad.write_text(":root{--palette-ink:#000}", encoding="utf-8")
    os.environ["TUN_PALETTE"] = str(bad)
    try:
        tok.load_token_css()
        chk("an incomplete TUN_PALETTE palette fails the build", False, True)
    except SystemExit:
        chk("an incomplete TUN_PALETTE palette fails the build", True, True)
    finally:
        os.environ.pop("TUN_PALETTE", None)
    # A path outside the repository must not crash the reporting path.
    chk("an outside path is displayed, not crashed on", tok.rel(bad), str(bad))

print("\ndiscovery reads manifests, sorted, and refuses two token providers")
found = tok.discover_plugins()
chk("discovery is sorted by id", [p.get("id") for p in found],
    sorted(str(p.get("id")) for p in found))
if HAVE_PLUGINS:
    chk("the eksempel plugin is discovered", [p.get("id") for p in found], ["eksempel"])
    chk("the manifest is actually parsed, not just located",
        found[0].get("provides"), ["tokens", "assets"])
    chk("private is carried through", found[0].get("private"), True)
else:
    chk("no plugins discovered on a core-only tree", found, [])

real_plugins = tok.PLUGINS_DIR
with tempfile.TemporaryDirectory() as td:
    fake = pathlib.Path(td) / "plugins"
    # two providers -> must be an error, not last-wins
    for name in ("aaa", "zzz"):
        d = fake / name / "tokens"
        d.mkdir(parents=True)
        (d / "palette.css").write_text(
            ":root{" + "".join(f"{s}:#000;" for s in tok.REQUIRED_SLOTS) + "}",
            encoding="utf-8")
        (fake / name / "manifest.json").write_text(json.dumps(
            {"id": name, "provides": ["tokens"], "tokens": {"palette": "tokens/palette.css"}}
        ), encoding="utf-8")
    try:
        tok.PLUGINS_DIR = fake
        with without_env():
            try:
                tok.palette_path(prefer_plugin=True)
                chk("two token providers is an error", False, True)
            except SystemExit as exc:
                chk("two token providers is an error", True, True)
                chk("the error names both", "aaa" in str(exc) and "zzz" in str(exc), True)
            # A malformed manifest must be loud, not skipped: a skipped plugin is
            # installed to the user and absent to the build.
            (fake / "aaa" / "manifest.json").write_text("{not json", encoding="utf-8")
            try:
                tok.discover_plugins()
                chk("a malformed manifest is refused", False, True)
            except SystemExit:
                chk("a malformed manifest is refused", True, True)
    finally:
        tok.PLUGINS_DIR = real_plugins

print("\nload order matches the documented one")
with without_env():
    css, source = tok.load_token_css()
    chk("the palette comes first (theme files reference its slots)",
        css.index("--palette-ink:") < css.index("--ink:"), True)
    chk("status tokens precede the themes that reference them",
        css.index("--status-positive") < css.index("--ok:"), True)
    chk("the result is complete", tok.missing_slots(css), [])
    chk("core's default build is not branded", "--eksempel-" in css, False)

print("\n" + "-" * 66)
print(f"{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
