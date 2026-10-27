#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
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
**forbidden** must be empty, always. Trademark artwork is the case that matters: the brand
wordmark's path data was embedded in two core examples, and artwork cannot be "reduced" in good
conscience. It is either out of core or it is not.

**ratcheted** carries a baseline that must match exactly. Deviation in either direction fails:

  * more than the baseline -> a regression; core drifted back towards the organisation
  * fewer than the baseline -> progress that must be banked by updating the baseline

Banking progress is deliberate friction. An allowance that silently absorbs improvement stops
being a ratchet and becomes a ceiling nobody lowers. `--baseline` makes the update mechanical,
so the cost is a reviewable diff rather than bookkeeping.

Why a ratchet at all: the organisation appears in dozens of core files. A single commit that
edited all of them would be unreviewable, and would be approved without being read. Increments
against a ratchet are reviewable.

Exit codes
    0  matches the baseline, and every forbidden category is empty
    1  a regression, or banked progress that needs the baseline updated
    2  the scope could not be resolved, or resolved empty
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tree_scan  # noqa: E402

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

#: Categories the attribution region is exempt from. Deliberately just the two that name
#: humans and the organisation they did it at. A brand hex or an internal hostname inside
#: an attribution block is still a leak, so those keep counting everywhere.
ATTRIBUTION_EXEMPT = ("person-name", "org-name")


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
#: path and the shape of these two manifests, and it requires a human name in each. Exactly one
#: value per file is exempt: the one at this key path. A name in `description`, `keywords` or
#: anywhere else in the same file still counts, because the exemption subtracts the hits inside
#: that one parsed value rather than skipping the file. Only person-name is exempt: an
#: organisation, host or colour inside the name field is still a leak. A declared manifest
#: that is not plain JSON (see manifest_subjects) is a problem of its own, never a fallback.
JSON_ATTRIBUTION: dict[str, tuple[str, ...]] = {
    ".claude-plugin/marketplace.json": ("owner", "name"),
    ".claude-plugin/plugin.json": ("author", "name"),
}
JSON_ATTRIBUTION_EXEMPT = ("person-name",)


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


def _no_constants(name: str) -> float:
    """parse_constant: refuse NaN, Infinity and -Infinity. Python's json accepts them;
    JSON does not, so a manifest that holds one is not plain JSON."""
    raise ValueError(f"not a JSON value: {name}")


class NotPlainJson(ValueError):
    """A declared manifest the gate cannot parse as plain, unambiguous JSON."""


def manifest_subjects(rel: str, text: str) -> tuple[str, str] | None:
    """For a declared JSON manifest, the two texts the person-name scan reads, else None.

    Returns (raw text with the attribution value removed, decoded strings with that one
    value blanked). A hit in either counts: the raw form catches a literal name, the
    decoded form catches one written as \\u escapes. Duplicate keys are refused at any
    depth, because json.loads keeps only the last value and the first would ship unseen.

    Raises NotPlainJson for anything that does not parse: invalid JSON, a repeated key, a
    leading BOM, trailing data, nesting too deep. There is no fallback and no exemption,
    because a validator that tolerates the file is not evidence that a scan of it is
    complete. The gate reports it as a problem instead."""
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
        for form in {json.dumps(value), json.dumps(value, ensure_ascii=False)}:
            raw = raw.replace(form, '""')
    return raw, decoded


# name -> (regex, kind, why it matters)
CATEGORIES: dict[str, tuple[str, str, str]] = {
    "logo-artwork": (
        r"M111\.797|M28\.0464|M74\.6848", "forbidden",
        "trademark wordmark path data; cannot be partially present"),
    "brand-token": (
        r"--dnb-[a-z0-9-]+", "ratcheted",
        "brand palette variable names leaking into core CSS"),
    "brand-hex": (
        r"(?i)#(?:006C6C|003842|0F1E26|00CC88|33FF77|99FF99|DDFFCC|F7FFE8|FFFFE8|7733FF|884DFF)\b",
        "ratcheted", "brand colour values from an access-controlled brandbook"),
    "internal-host": (
        r"\b[a-z0-9-]+\.(?:tech\.)?dnb\.no\b", "ratcheted",
        "internal endpoints, useless and revealing outside the network"),
    "internal-forge": (
        r"\bdnb\.ghe\.com\b", "ratcheted", "internal forge links, unreachable publicly"),
    "atlassian-site": (
        r"\b(?!example\.)[a-z0-9][a-z0-9-]*\.atlassian\.net\b"
        r"|\bari:cloud:[a-z-]+:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        "forbidden",
        "one organisation's Atlassian Cloud site, or an ARI carrying its site id. Core finds the "
        "site at run time (getAccessibleAtlassianResources); a plugin's tenant facts may name it"),
    "internal-system": (
        r"\b(?:INFA|Konsernjuridisk|dnbasa-[a-z0-9_]+)\b", "ratcheted",
        "internal programme, team and account names"),
    "org-name": (
        r"\bDNB\b", "ratcheted", "the organisation named in core prose"),
    "design-system": (
        r"\bEufemia\b", "ratcheted", "the organisation's design system named in core"),
    "person-name": (
        # Composed from fragments: this file is the one that forbids these names, so it
        # must also be a file that does not carry them. The pattern is identical at run
        # time; splitting it only defeats a scanner reading the raw text.
        r"\b(?:" + r"Per" + " " + r"Harald|" + r"Pel" + r"le|Jon-Mikkel|Korsvik" + r")\b", "ratcheted",
        "colleagues named in core; roles carry the same meaning"),
}


def total(hits: dict[str, int]) -> int:
    """The occurrence count for a category. DERIVED, never stored.

    An earlier version of the baseline stored this alongside the per-file counts. Two
    numbers describing one fact can disagree, and nothing checked that they agreed, so a
    hand-edit of either would have produced a ratchet that quietly compared against a
    number with no basis in the tree.
    """
    return sum(hits.values())


# Compiled once. `re.compile` caches internally anyway, but holding them removes the
# lookup from a function that runs ten thousand times per suite.
_COMPILED = {name: re.compile(pat) for name, (pat, _k, _w) in CATEGORIES.items()}

#: {category: {text: hits}}. `scan_texts` is pure over its input, so the same text always
#: yields the same count, and the boundary suite calls it once per check with one file
#: swapped. Measuring that suite is what put this here: 34 whole-tree scans at 0.55 s each,
#: and 0.55 s of it is regex work over the same 6.8 MB thirty-four times. The cache holds
#: references, not copies, and a mutated text is a new object, so a test that swaps one
#: file in re-scans exactly that file. ROADMAP C1.
_COUNTS: dict[str, dict[str, int]] = {}


def counts(name: str, subject: str) -> int:
    """Occurrences of one category in one text, memoised on the text itself."""
    per_cat = _COUNTS.setdefault(name, {})
    if len(per_cat) > 20_000:
        per_cat.clear()      # a long-lived process must not grow a text cache forever
    try:
        return per_cat[subject]
    except KeyError:
        pass
    hits = len(_COMPILED[name].findall(subject))
    per_cat[subject] = hits
    return hits


def scan_texts(texts: dict[str, str]) -> dict[str, dict]:
    """Return {category: {rel: count}} for {rel: text}, plus "_scope".

    Pure over its input, so a hypothetical tree can be scanned without touching git."""
    out: dict[str, dict] = {n: {} for n in CATEGORIES}
    shape: dict[str, str] = {}
    for rel, text in texts.items():
        attributed = strip_attribution(text) if ATTRIBUTION_START in text else text
        try:
            subjects = manifest_subjects(rel, text)
        except NotPlainJson:
            subjects = None
            shape[rel] = "not plain JSON"
        for name in CATEGORIES:
            subject = attributed if name in ATTRIBUTION_EXEMPT else text
            hits = counts(name, subject)
            if subjects is not None and name in JSON_ATTRIBUTION_EXEMPT:
                hits = max(counts(name, t) for t in subjects)
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
    return [f"manifest-shape: {rel} is not plain JSON" for rel in sorted(current["_shape"])]


def problems_for(current: dict[str, dict], baseline: dict[str, dict[str, int]]) -> list[str]:
    """Every problem the CLI would print for this scan, in order."""
    out = []
    for name, (_pat, kind, why) in CATEGORIES.items():
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
        print(json.dumps({n: current[n] for n in CATEGORIES},
                          indent=2, sort_keys=True))
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
        print("─" * 78)

    width = max(len(n) for n in CATEGORIES)
    for name, (_pat, kind, why) in CATEGORIES.items():
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
