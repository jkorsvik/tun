#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
check_core_is_generic.py — hold the core / plugin boundary.

Stdlib only.

    python3 tools/check_core_is_generic.py             # check against the baseline
    python3 tools/check_core_is_generic.py --baseline  # print a fresh baseline to paste
    python3 tools/check_core_is_generic.py --detail brand-token   # show where the hits are

Why this exists
---------------
`docs/21-plugin-architecture.md` argues that organisation-specific material is a third-party
plugin rather than contamination, and `docs/22-plugin-contract.md` states the invariants. This
is invariant 4: core names no organisation, design system, internal host or person.

A one-off scrub cannot hold that line, because it decays from the next commit onwards. A
boundary has to be checked continuously, which is what this does.

Two kinds of category
---------------------
**forbidden** must be empty, always. Trademark artwork is the case that matters: artwork
cannot be "reduced" in good conscience. It is either out of core or it is not.

**ratcheted** carries a baseline that must match exactly. Deviation in either direction fails:

  * more than the baseline -> a regression; core drifted back towards the organisation
  * fewer than the baseline -> progress that must be banked by updating the baseline

Banking progress is deliberate friction. An allowance that silently absorbs improvement stops
being a ratchet and becomes a ceiling nobody lowers. `--baseline` makes the update mechanical,
so the cost is a reviewable diff rather than bookkeeping.

Why a ratchet at all: when a brand is spread across dozens of core files, a single commit that
edits all of them is unreviewable, and gets approved without being read. Increments against a
ratchet are reviewable.

Blind spot, and its cover: brand categories are derived from the plugins that exist. Delete a
brand's plugin and its hexes stop being brand hexes here, while every copy left in core stays.
Retiring a brand therefore means adding its values to the local denylist first, so the
`local:*` categories keep seeing them.

Exit codes
    0  matches the baseline, and every forbidden category is empty
    1  a regression, or banked progress that needs the baseline updated
    2  the scope could not be resolved, or resolved empty
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tree_scan  # noqa: E402
import check_export_clean as export_gate  # noqa: E402

G, R, Y, D, B, Z = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
if not sys.stdout.isatty():
    G = R = Y = D = B = Z = ""

BASELINE_PATH = tree_scan.REPO / "tools" / "core_generic_baseline.json"

SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".mov", ".xlsx", ".xls",
}

# Paths outside core. plugins/ is the point of the exercise; the baseline file itself would
# otherwise match every pattern it lists. internal/ holds internal-only notes and archives:
# the export removes it (and fails if it is still there), so it never ships as core. The
# real-data gate still scans it.
def in_core(rel: str) -> bool:
    if rel.startswith(("plugins/", "internal/")):
        return False
    if rel in ("tools/core_generic_baseline.json", "tools/check_core_is_generic.py"):
        return False
    return pathlib.Path(rel).suffix.lower() not in SKIP_SUFFIXES


#: A declared attribution region; defined in tools/check_export_clean.py, one definition
#: for both gates. Region-based rather than file-based, so a name cannot drift into an
#: unrelated paragraph and count as attribution.
ATTRIBUTION_START = export_gate.ATTRIBUTION_START
ATTRIBUTION_END = export_gate.ATTRIBUTION_END

#: Categories the attribution region is exempt from. Deliberately just the two local-denylist
#: labels that name humans and the organisation they did it at. A brand hex or an internal hostname inside
#: an attribution block is still a leak, so those keep counting everywhere.
ATTRIBUTION_EXEMPT = ("local:person", "local:org")


#: The copyright notice names its holder; see tools/check_export_clean.py. Same rule,
#: one definition: only the person category, only on the notice line.
NOTICE_EXEMPT = tuple(f"local:{label}" for label in export_gate.NOTICE_EXEMPT)
strip_copyright_lines = export_gate.strip_copyright_lines


strip_attribution = export_gate.strip_attribution


#: Attribution in JSON, where the comment markers above cannot live (the two Claude Code
#: manifests). Defined in tools/check_export_clean.py, one definition for both gates: exactly
#: one value per file is exempt, only the person label is exempt, and a declared manifest that
#: is not plain JSON is a problem of its own (see export_gate.manifest_subjects).
JSON_ATTRIBUTION = export_gate.JSON_ATTRIBUTION
JSON_ATTRIBUTION_EXEMPT = tuple(f"local:{label}" for label in export_gate.JSON_ATTRIBUTION_EXEMPT)
NotPlainJson = export_gate.NotPlainJson


# --- Where the patterns come from -------------------------------------------------------
#
# Nothing identifying is written in this file. A tracked list of the organisation's name,
# hosts and people would itself carry what the boundary keeps out of core. So:
#
#   * brand categories are DERIVED from plugins/: each plugin's manifest id gives its token
#     prefix, its palette files give its hex values, its examples give its artwork. Adding
#     a brand plugin extends the gate with no edit here.
#   * identity categories (people, the organisation, internal hosts and programmes) come
#     from the local, untracked denylist shared with tools/check_export_clean.py:
#     $TUN_DENYLIST, or else ~/.config/tun/denylist.txt, one `label<TAB>regex` per line.
#     Each label becomes a forbidden category named `local:<label>`. Without a denylist
#     these categories are reported as skipped, loudly, never as clean.

PLUGINS = tree_scan.REPO / "plugins"
NEUTRAL_PALETTE = tree_scan.REPO / "tools" / "tokens" / "palette-neutral.css"
DENYLIST = pathlib.Path(os.environ.get("TUN_DENYLIST")
                        or pathlib.Path.home() / ".config" / "tun" / "denylist.txt").expanduser()

_HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")
_PATH_D = re.compile(r'\bd="(M[^"]{15,})"')


def _plugin_manifests() -> list[dict]:
    out = []
    for m in sorted(PLUGINS.glob("*/manifest.json")):
        try:
            out.append(json.loads(m.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def _plugin_files(*patterns: str) -> list[pathlib.Path]:
    return sorted({f for pat in patterns for f in PLUGINS.glob(pat) if f.is_file()})


def _alternation(items) -> str | None:
    items = sorted(set(items))
    return "(?:" + "|".join(items) + ")" if items else None


def brand_token_pattern() -> str | None:
    ids = [re.escape(m["id"]) for m in _plugin_manifests() if m.get("id")]
    alt = _alternation(ids)
    return rf"--{alt}-[a-z0-9-]+" if alt else None


def brand_hex_pattern() -> str | None:
    """Hex values a plugin palette declares that core's own neutral palette does not.
    Shared neutrals (#FFFFFF, #000000 ...) belong to nobody and are not a leak."""
    neutral = {h.upper() for h in _HEX.findall(NEUTRAL_PALETTE.read_text(encoding="utf-8"))} \
        if NEUTRAL_PALETTE.is_file() else set()
    neutral |= {"#FFFFFF", "#000000", "#757575", "#CCCCCC"}
    declared = {h.upper() for f in _plugin_files("*/tokens/*.css")
                for h in _HEX.findall(f.read_text(encoding="utf-8"))}
    alt = _alternation(re.escape(h[1:]) for h in declared - neutral)
    return rf"(?i)#{alt}\b" if alt else None


_LOGO_SVG = re.compile(r'<svg\b[^>]*\brole="img"[^>]*>(.*?)</svg>', re.S)


def artwork_pattern() -> str | None:
    """The opening of every path inside a plugin's logo, read from its built examples.
    A logo is the SVG marked role="img"; UI icons are aria-hidden and belong to nobody.
    Artwork is all-or-nothing: 16 characters of a path show it was copied into core."""
    frags = {d.group(1)[:16]
             for f in _plugin_files("*/examples/**/*.html", "*/assets/**/*.svg")
             for svg in _LOGO_SVG.finditer(f.read_text(encoding="utf-8", errors="replace"))
             for d in _PATH_D.finditer(svg.group(1))}
    return _alternation(re.escape(x) for x in frags)


def load_local_denylist(path: pathlib.Path | None = None) -> list[tuple[str, str]]:
    """[(label, regex)] from the local denylist, or [] when there is none."""
    path = path or DENYLIST
    if not path.is_file():
        return []
    rules = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        label, sep, rx = line.partition("\t")
        rules.append((label.strip(), rx.strip()) if sep else ("term", line))
    return rules


def build_categories(denylist: pathlib.Path | None = None) -> dict[str, tuple[str | None, str, str]]:
    """name -> (regex or None when there is nothing to look for, kind, why it matters)."""
    cats: dict[str, tuple[str | None, str, str]] = {
        "logo-artwork": (artwork_pattern(), "forbidden",
                         "a plugin's wordmark/icon path data; artwork cannot be partially present"),
        "brand-token": (brand_token_pattern(), "ratcheted",
                        "brand palette variable names leaking into core CSS"),
        "brand-hex": (brand_hex_pattern(), "ratcheted",
                      "brand colour values a plugin owns, hardcoded in core"),
        "atlassian-site": (
            r"\b(?!example\.)[a-z0-9][a-z0-9-]*\.atlassian\.net\b"
            r"|\bari:cloud:[a-z-]+:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            "forbidden",
            "one organisation's Atlassian Cloud site, or an ARI carrying its site id. Core finds the "
            "site at run time (getAccessibleAtlassianResources); a plugin's tenant facts may name it"),
    }
    by_label: dict[str, list[str]] = {}
    for label, rx in load_local_denylist(denylist):
        by_label.setdefault(label, []).append(rx)
    for label, rxs in sorted(by_label.items()):
        cats[f"local:{label}"] = ("(?i)" + _alternation(f"(?:{r})" for r in rxs), "forbidden",
                                  f"identifying text listed under '{label}' in the local denylist")
    return cats


CATEGORIES = build_categories()


def total(hits: dict[str, int]) -> int:
    """The occurrence count for a category. DERIVED, never stored.

    An earlier version of the baseline stored this alongside the per-file counts. Two
    numbers describing one fact can disagree, and nothing checked that they agreed, so a
    hand-edit of either would have produced a ratchet that quietly compared against a
    number with no basis in the tree.
    """
    return sum(hits.values())


def scan_texts(texts: dict[str, str]) -> dict[str, dict]:
    """Return {category: {rel: count}} for {rel: text}, plus "_scope".

    Pure over its input, so a hypothetical tree can be scanned without touching git."""
    compiled = {name: re.compile(pat) for name, (pat, _k, _w) in CATEGORIES.items() if pat}
    out: dict[str, dict] = {n: {} for n in CATEGORIES}
    shape: dict[str, str] = {}
    for rel, text in texts.items():
        attributed = strip_attribution(text) if ATTRIBUTION_START in text else text
        try:
            subjects = export_gate.manifest_subjects(rel, text)
        except NotPlainJson:
            subjects = None
            shape[rel] = "not plain JSON"
        for name, rx in compiled.items():
            subject = attributed if name in ATTRIBUTION_EXEMPT else text
            if name in NOTICE_EXEMPT:
                subject = strip_copyright_lines(subject)
            hits = len(rx.findall(subject))
            if subjects is not None and name in JSON_ATTRIBUTION_EXEMPT:
                hits = max(len(rx.findall(t)) for t in subjects)
            if hits:
                out[name][rel] = hits
    out["_scope"] = {"files": len(texts)}
    out["_shape"] = shape
    return out


def read_core() -> dict[str, str]:
    """{rel: text} for every tracked core file."""
    files = [f for f in tree_scan.tracked_paths() if in_core(f)]
    if not files:
        raise tree_scan.ScopeError(
            "resolved zero core files — the scope is broken, not clean")
    texts: dict[str, str] = {}
    for rel in files:
        path = tree_scan.REPO / rel
        if not path.exists():
            raise tree_scan.ScopeError(f"tracked file missing from the working tree: {rel}")
        texts[rel] = path.read_text(encoding="utf-8", errors="replace")
    return texts


def scan() -> dict[str, dict]:
    """Return {category: {rel: count}} over core files, plus "_scope"."""
    return scan_texts(read_core())


def load_baseline() -> dict[str, dict[str, int]]:
    """Read the baseline and reject a shape it cannot trust.

    A baseline is only meaningful if it is exactly {category: {path: count}}. Anything
    else means a half-finished edit or an older format, and comparing against it would
    produce a confident verdict from a structure nobody validated.
    """
    if not BASELINE_PATH.is_file():
        raise SystemExit(
            f"no baseline at {BASELINE_PATH}.\n"
            f"Create one with: python3 tools/check_core_is_generic.py --baseline"
            f" > {BASELINE_PATH.relative_to(tree_scan.REPO)}")
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    for name, hits in data.items():
        if not isinstance(hits, dict):
            raise SystemExit(
                f"baseline category {name!r} is {type(hits).__name__}, expected an object "
                f"of path -> count. Regenerate with --baseline.")
        if "files" in hits or "total" in hits:
            raise SystemExit(
                f"baseline category {name!r} uses the old nested shape with a stored "
                f"'total'. The total is derived now, so a stored one can disagree with "
                f"the tree.\n  Regenerate: python3 tools/check_core_is_generic.py "
                f"--baseline > tools/core_generic_baseline.json")
        for path, count in hits.items():
            if not isinstance(count, int):
                raise SystemExit(
                    f"baseline {name}/{path} has a non-integer count {count!r}. "
                    f"Regenerate with --baseline.")
    return data


def judge(name: str, kind: str, why: str, hits: dict[str, int],
          want: dict[str, int]) -> tuple[str | None, str, str, str]:
    """Compare one category to its baseline. Returns (problem or None, icon, colour, note)."""
    got_total, got_files = total(hits), set(hits)
    if kind == "forbidden":
        if got_total:
            return (f"{name}: forbidden, found {got_total} occurrence(s) in "
                    f"{len(got_files)} file(s) — {why}", "✗", R, f"{got_total} FORBIDDEN")
        return None, "✓", G, "absent, as required"
    want_total, want_files = total(want), set(want)
    new = got_files - want_files
    if new:
        return (f"{name}: {len(new)} new file(s): " + ", ".join(sorted(new)[:5]),
                "✗", R, f"{len(new)} NEW file(s)")
    if got_total > want_total:
        return (f"{name}: {got_total} occurrences, baseline {want_total} — core drifted back",
                "✗", R, f"{got_total} > {want_total}")
    if got_total < want_total:
        return (f"{name}: {got_total} occurrences, baseline {want_total} — progress,"
                f" bank it with --baseline", "✗", Y, f"{got_total} < {want_total}, bank it")
    if got_total:
        return None, "•", Y, f"{got_total} in {len(got_files)} file(s)"
    return None, "✓", G, "clean"


def shape_problems(current: dict[str, dict]) -> list[str]:
    """One problem per declared manifest that is not plain JSON."""
    return [f"{export_gate.MANIFEST_SHAPE}: {rel} is not plain JSON" for rel in sorted(current["_shape"])]


def problems_for(current: dict[str, dict], baseline: dict[str, dict[str, int]]) -> list[str]:
    """Every problem the CLI would print for this scan, in order."""
    out = []
    for name, (pat, kind, why) in CATEGORIES.items():
        if not pat:
            continue      # nothing to look for: main() says so, and judges nothing
        problem = judge(name, kind, why, current[name], baseline.get(name, {}))[0]
        if problem:
            out.append(problem)
    return out + shape_problems(current)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baseline", action="store_true",
                    help="print a fresh baseline as JSON and exit")
    ap.add_argument("--detail", metavar="CATEGORY",
                    help="list the files and counts for one category")
    ap.add_argument("--quiet", action="store_true", help="print only problems")
    args = ap.parse_args()

    try:
        current = scan()
    except tree_scan.ScopeError as exc:
        print(f"{R}✗ scope error{Z} {exc}", file=sys.stderr)
        return 2

    if args.baseline:
        # Ratcheted categories only: forbidden ones must be empty, and the local ones depend
        # on a file that is not in the repository, so they cannot be part of a shared baseline.
        print(json.dumps({n: current[n] for n, (_p, k, _w) in CATEGORIES.items()
                          if k == "ratcheted"}, indent=2, sort_keys=True))
        return 0

    if args.detail:
        name = args.detail
        if name not in CATEGORIES:
            print(f"unknown category {name!r}. Known: {', '.join(CATEGORIES)}",
                  file=sys.stderr)
            return 2
        print(f"{B}{name}{Z} — {CATEGORIES[name][2]}")
        for rel, n in sorted(current[name].items(), key=lambda kv: -kv[1]):
            print(f"  {n:5d}  {rel}")
        print(f"  {total(current[name])} occurrence(s) in "
              f"{len(current[name])} file(s)")
        return 0

    baseline = load_baseline()
    problems: list[str] = []

    if not args.quiet:
        print(f"{B}core / plugin boundary{Z}")
        print(f"  scope: {current['_scope']['files']} core file(s)"
              f" {D}(plugins/ excluded by design){Z}")
        if not any(n.startswith("local:") for n in CATEGORIES):
            print(f"  {Y}• identity checks SKIPPED{Z} — no local denylist at {DENYLIST}."
                  f"\n    {D}People, organisation and internal-host checks need it; see the"
                  f" note above build_categories().{Z}")
        print("─" * 78)

    width = max(len(n) for n in CATEGORIES)
    for name, (pat, kind, why) in CATEGORIES.items():
        if not pat:
            if not args.quiet:
                print(f"  {D}- {name:<{width}}  {kind:<10} nothing to look for (no plugin declares it){Z}")
            continue
        problem, icon, colour, note = judge(name, kind, why, current[name],
                                            baseline.get(name, {}))
        if problem:
            problems.append(problem)
        if not args.quiet:
            print(f"  {colour}{icon}{Z} {name:<{width}}  {D}{kind:<10}{Z} {colour}{note}{Z}")
    problems += shape_problems(current)

    if not args.quiet:
        print("─" * 78)

    if problems:
        print(f"\n{R}✗ FAIL{Z} — the core boundary moved:")
        for p in problems:
            print(f"    • {p}")
        print(f"\n  See where with: python3 tools/check_core_is_generic.py --detail <category>"
              f"\n  Bank real progress with:  python3 tools/check_core_is_generic.py --baseline"
              f" > tools/core_generic_baseline.json")
        return 1

    remaining = sum(total(current[n]) for n, (_p, k, _w) in CATEGORIES.items()
                    if k == "ratcheted")
    if not args.quiet:
        print(f"\n{G}✓ PASS{Z} — no forbidden content, and every ratchet matches."
              f"\n  {Y}{remaining} occurrence(s) of organisation-specific text remain{Z} in core,"
              f"\n  tracked in tools/core_generic_baseline.json. The list may only shrink.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
