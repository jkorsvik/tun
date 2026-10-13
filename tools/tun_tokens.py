#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
tun_tokens.py — resolve, validate and load the token CSS a build inlines.

Stdlib only. Importable by any builder; also runnable as a check:

    python3 tools/tun_tokens.py            # report the active palette and validate it
    python3 tools/tun_tokens.py --list     # list discovered plugins

Why this module exists
----------------------
Four separate problems in `docs/22-plugin-contract.md` turned out to be one missing shape.

1. `read_tokens()` was copy-pasted into five builders, each with its own idea of where a
   palette lives. Three of them (`examples/06`, `14`, `15`) still named the brand palette
   by its pre-extraction filename and broke the moment it moved into the plugin. Nothing
   noticed, because no gate builds the examples.
2. The contract promised that "a palette that omits a slot is rejected at build time".
   Nothing validated anything. A missing slot leaves an unresolved `var()`, which CSS
   renders as *nothing* — an invisible or wrong colour in a shipped artefact that passes
   every gate in the repo.
3. The contract promised discovery through `plugins/*/manifest.json`, sorted by id, with
   "more than one token provider is an error". No code read a manifest at all, so the
   plugin manifest was decoration.
4. `TUN_PALETTE` was an environment variable with no validation, which is the least
   discoverable interface available.

A builder now asks one question — "what CSS do I inline?" — and this answers it.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
PLUGINS_DIR = REPO / "plugins"
CORE_TOKENS = REPO / "tools" / "tokens"

#: The palette core ships so a build works with plugins/ absent. Invariant 3.
NEUTRAL_PALETTE = CORE_TOKENS / "palette-neutral.css"

#: The seam, measured rather than chosen: these are the palette values that core's theme
#: files actually consume. Eight, not the nineteen a brand happens to define. Keep this
#: list and docs/22-plugin-contract.md in step; tests/test_token_contract.py asserts it.
REQUIRED_SLOTS = (
    "--palette-ink",
    "--palette-surface",
    "--palette-primary",
    "--palette-primary-dark",
    "--palette-primary-darkest",
    "--palette-accent",
    "--palette-accent-light",
    "--palette-on-dark",
)

#: Load order matters: later files reference earlier ones. The palette is prepended by
#: load_token_css(), because which palette is active is the part that varies.
CORE_TOKEN_ORDER = ("status-semantic.css", "theme-light.css", "theme-dark.css")


class TokenError(SystemExit):
    """Raised as a build failure. A builder should not continue with a broken palette:
    the output would look finished and render wrongly."""

    def __init__(self, message: str) -> None:
        super().__init__(f"token error: {message}")


def discover_plugins() -> list[dict]:
    """Return every plugin manifest, sorted by id.

    Sorted rather than filesystem order so two machines resolve the same palette; an
    ordering that depends on directory iteration is a difference that only shows up as a
    colour change in someone else's build.
    """
    if not PLUGINS_DIR.is_dir():
        return []
    found: list[dict] = []
    for manifest in sorted(PLUGINS_DIR.glob("*/manifest.json")):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            # Loud, not skipped. A malformed manifest silently ignored is a plugin that
            # is installed as far as the user is concerned and absent as far as the build
            # is concerned.
            raise TokenError(f"{rel(manifest)} is not readable JSON: {exc}")
        data["_dir"] = manifest.parent
        data["_manifest"] = manifest
        found.append(data)
    return sorted(found, key=lambda d: str(d.get("id", d["_dir"].name)))


def rel(path: pathlib.Path) -> str:
    """Display a path relative to the repo when it is inside it, absolute when it is not.
    `Path.relative_to` raises for an outside path, and a crash while reporting a bad
    palette replaces a clear message with a traceback."""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def palette_path(prefer_plugin: bool = False,
                 palette: str | None = None) -> tuple[pathlib.Path, str]:
    """Resolve the active palette. Returns (path, why) so a build can state its source.

    Precedence, and the reason for it:
      1. TUN_PALETTE — an explicit override, for testing a palette without installing a
         plugin. Validated like any other, so a typo fails loudly instead of silently
         falling back to neutral and producing a plausible wrong-coloured artefact.
      2. the single plugin that provides `tokens`, but ONLY when prefer_plugin is set.
      3. core's neutral palette.

    Why a plugin does not win by default, which looks backwards for a plugin system:
    this repository *contains* the brand plugin, so an installed-wins default would make
    every core example rebuild branded. Brand hex values would flow straight back into
    core files, and the core boundary ratchet (tools/check_core_is_generic.py) would
    regress on the next rebuild — the build would undo the extraction. Core artefacts
    therefore pin neutral on purpose, and anything that wants the brand asks for it. The
    plugin's own examples pass prefer_plugin=True or set TUN_PALETTE.

    `palette` is the same selection made by the artefact itself (a builder reading it from
    its own spec), so a rebuild cannot lose it. It ranks just below TUN_PALETTE: the person
    running the build can still override what the file asks for.
    """
    env = os.environ.get("TUN_PALETTE")
    override = env or palette
    if override:
        label = f"TUN_PALETTE={override}" if env else f"spec:{override}"
        path = pathlib.Path(override)
        if not path.is_absolute():
            path = REPO / override
        if not path.is_file():
            raise TokenError(
                f"{label!r} does not exist (looked at {rel(path)}).\n"
                f"  Unset it to use core's neutral palette, or give a path relative to "
                f"the repository root.")
        return path, label

    providers = ([p for p in discover_plugins() if "tokens" in (p.get("provides") or [])]
                 if prefer_plugin else [])
    if len(providers) > 1:
        names = ", ".join(str(p.get("id", p["_dir"].name)) for p in providers)
        raise TokenError(
            f"{len(providers)} plugins provide tokens ({names}); exactly one may.\n"
            f"  Last-wins would make the palette of a built artefact impossible to "
            f"determine by reading it, so this is refused rather than resolved.")
    if providers:
        plugin = providers[0]
        palette_rel = (plugin.get("tokens") or {}).get("palette")
        if not palette_rel:
            raise TokenError(
                f"plugin {plugin.get('id')!r} declares provides:[tokens] but its manifest "
                f"has no tokens.palette path ({rel(plugin['_manifest'])})")
        path = plugin["_dir"] / palette_rel
        if not path.is_file():
            raise TokenError(
                f"plugin {plugin.get('id')!r} points tokens.palette at {palette_rel}, which does "
                f"not exist under {rel(plugin['_dir'])}")
        return path, f"plugin:{plugin.get('id')}"

    if not NEUTRAL_PALETTE.is_file():
        raise TokenError(
            f"core's neutral palette is missing ({rel(NEUTRAL_PALETTE)}). "
            f"Core must build with plugins/ absent, so this file is not optional.")
    return NEUTRAL_PALETTE, "core:neutral"


def provenance_label(source: str) -> str:
    """The palette source as an artefact may record it: `source` without the user's path.

    `palette_path()` labels an override with the path exactly as given, which is what a
    person checking which file was used wants on their own screen. An artefact is shared,
    though, and a brand plugin sets TUN_PALETTE to an absolute path under the user's home
    directory (a relative one resolves against the repo). Copied into a provenance block,
    that path puts the OS user name in every file the user hands out.

    So a path inside the repo is shown relative to it, which says nothing about the
    person, and a path outside it keeps only its file name and parent directory
    (`TUN_PALETTE=…/tun-eksempel/palette.css`), which is usually the plugin. The parent is
    dropped when it is part of the home path itself, because for a palette saved
    directly in home the parent directory is the user name.
    """
    for prefix in ("TUN_PALETTE=", "spec:"):
        if not source.startswith(prefix):
            continue
        given = pathlib.Path(source[len(prefix):])
        # Lexical, not resolve(): the label describes what was given, and a symlink in
        # the repo path must not turn an in-repo palette into an outside one.
        full = pathlib.Path(os.path.normpath(given if given.is_absolute() else REPO / given))
        try:
            return prefix + full.relative_to(REPO).as_posix()
        except ValueError:
            pass
        try:
            home_parts = set(pathlib.Path.home().parts)
        except RuntimeError:  # no home directory can be determined
            home_parts = set()
        parent = full.parent.name
        shown = f"{parent}/{full.name}" if parent and parent not in home_parts else full.name
        return f"{prefix}…/{shown}"
    return source


def missing_slots(css: str) -> list[str]:
    """Which required slots this CSS fails to define.

    Checks for a definition (`--slot:`), not a mere mention, so a palette that only
    *references* a slot in a comment does not count as defining it.
    """
    return [s for s in REQUIRED_SLOTS if f"{s}:" not in css]


def validate_palette(css: str, source: str) -> None:
    missing = missing_slots(css)
    if missing:
        raise TokenError(
            f"palette from {source} does not define {len(missing)} required slot(s):\n"
            + "".join(f"    {s}\n" for s in missing)
            + "  Core's theme files reference these. An undefined custom property leaves\n"
              "  an unresolved var(), which CSS renders as nothing: the artefact builds,\n"
              "  passes every gate, and shows invisible or wrong colours.\n"
              f"  All {len(REQUIRED_SLOTS)} slots are listed in "
              f"docs/22-plugin-contract.md and tools/tun_tokens.py.")


def load_token_css(core_files: tuple[str, ...] = CORE_TOKEN_ORDER,
                   prefer_plugin: bool = False,
                   palette: str | None = None) -> tuple[str, str]:
    """Return (css, source) with the palette first, validated, ready to inline.

    `core_files` exists because not every artefact wants the dark theme (examples/14 and
    15 ship light only). It is an explicit argument rather than a flag so the call site
    says which files it inlines.
    """
    path, source = palette_path(prefer_plugin=prefer_plugin, palette=palette)
    palette_css = path.read_text(encoding="utf-8")
    validate_palette(palette_css, source)
    parts = [palette_css]
    for name in core_files:
        f = CORE_TOKENS / name
        if not f.is_file():
            raise TokenError(f"core token file missing: {rel(f)}")
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts), source


def main() -> int:
    if "--list" in sys.argv:
        plugins = discover_plugins()
        if not plugins:
            print("no plugins installed (plugins/ absent or empty)")
        for p in plugins:
            print(f"{p.get('id'):<12} provides={p.get('provides')} "
                  f"private={p.get('private', False)} "
                  f"{p['_manifest'].relative_to(REPO)}")
        return 0
    prefer = "--prefer-plugin" in sys.argv
    path, source = palette_path(prefer_plugin=prefer)
    css = path.read_text(encoding="utf-8")
    missing = missing_slots(css)
    print(f"active palette : {rel(path)}")
    print(f"resolved via   : {source}")
    print(f"required slots : {len(REQUIRED_SLOTS)}")
    if missing:
        print(f"MISSING ({len(missing)})   : {', '.join(missing)}")
        return 1
    print("all required slots defined")
    return 0


if __name__ == "__main__":
    sys.exit(main())
