#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
check_token_contrast.py: measure every declared token pair against WCAG 2.2 AA.

Stdlib only. Importable by a suite; also runnable as a check:

    python3 tools/check_token_contrast.py            # light and dark, active palette
    python3 tools/check_token_contrast.py --theme dark
    python3 tools/check_token_contrast.py --prefer-plugin
    python3 tools/check_token_contrast.py --palette plugins/tun/tokens/palette.css

Why this module exists
----------------------
`docs/09-usability-and-navigation-principles.md` §4 left two blockers before the dark
theme could graduate out of `examples/05-theme-toggle-demo/`. The first was:

    "Re-measure contrast for status colours and chart colours against the dark theme
     background once theme-dark.css has an actual reader to test against."

`theme-dark.css` carried measured numbers for its chip backgrounds only, and its own
comment said the status TEXT colours were "still UNCHECKED for the case of being read
directly on --bg/--panel". Nobody could check them without a tool, so the numbers in the
token files were partly measured and partly assumed. A ratio written in a comment beside
a hex value is a claim; nothing re-measured it when a value changed.

This tool turns the claim into a check. It parses the same token CSS the builders inline,
resolves the `var()` chains, computes WCAG relative luminance and contrast ratio for each
declared text-on-background pair in each theme, and fails when a pair falls under its
threshold. A changed hex value cannot quietly pass.

What it does NOT do
-------------------
It measures declared pairs. It cannot see a template that uses a token in a combination
nobody declared here, so a new role needs a row in PAIRS. It reads hex values only: a token
holding `rgba()`, a gradient or a keyword is reported as unmeasurable, not skipped in
silence.

What the first run found
------------------------
Three dark-theme roles failed, and two more were invisible rather than merely low:

  --brand as link on the dark background   1.43:1   a link nobody can see
  --ok  on the dark background             2.35:1
  --bad on the dark background             2.59:1
  --ink on the light chip --ok-bg          1.04:1   the chip label, invisible
  --ink on the light chip --bad-bg         1.04:1

The chip pair is the sharp one. theme-dark.css chose light near-white chips on the
argument that a light chip on a dark page is conventional. True, but only when the chip's
label is dark. Templates set the label to `var(--ink)`, which in the dark theme is light,
so the argument did not cover the code. The chips are now dark tints.

`--brand` needed a structural fix rather than a colour tweak: the light theme's primary is
chosen to read on white and cannot be reused on a dark surface, so core now requires a
ninth palette slot, `--palette-primary-on-dark` (docs/22-plugin-contract.md).
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import tun_tokens as tok  # noqa: E402

#: WCAG 2.2 minimums. Body text is 4.5:1 (1.4.3). Large text and non-text UI that conveys
#: meaning are 3:1 (1.4.3 large, 1.4.11 non-text).
TEXT = 4.5
LARGE = 3.0
NON_TEXT = 3.0

#: One row per combination a reader actually meets on the page. `fg` sits on `bg`.
#: Adding a role to a template without adding it here is how a theme goes unchecked, so
#: keep this table and the theme files in step.
#:
#:   theme  kind       label                                    fg                        bg                        min
PAIRS = (
    # --- light: the default, and the one with measured numbers behind it ---
    ("light", "text", "--ink on --bg", "--ink", "--bg", TEXT),
    ("light", "text", "--ink on --panel", "--ink", "--panel", TEXT),
    ("light", "text", "--muted on --bg", "--muted", "--bg", TEXT),
    ("light", "text", "--muted on --panel", "--muted", "--panel", TEXT),
    ("light", "text", "--brand as link on --bg", "--brand", "--bg", TEXT),
    ("light", "text", "--on-brand on a --brand fill", "--on-brand", "--brand", TEXT),
    ("light", "text", "--palette-on-dark on --brand-dark", "--palette-on-dark", "--brand-dark", TEXT),
    # A status chip renders --ink as its label and the status colour as its border
    # (templates/process-diagram.html .badge), so those are the two combinations to
    # measure, not status-on-status, which no template draws.
    ("light", "text", "--ink on --ok-bg", "--ink", "--ok-bg", TEXT),
    ("light", "text", "--ink on --bad-bg", "--ink", "--bad-bg", TEXT),
    ("light", "non-text", "--ok border on --ok-bg", "--ok", "--ok-bg", NON_TEXT),
    ("light", "non-text", "--bad border on --bad-bg", "--bad", "--bad-bg", NON_TEXT),
    ("light", "text", "--ok on --bg", "--ok", "--bg", TEXT),
    ("light", "text", "--bad on --bg", "--bad", "--bg", TEXT),
    ("light", "decorative", "--line on --bg", "--line", "--bg", NON_TEXT),
    ("light", "non-text", "--series-2 on --bg", "--series-2", "--bg", NON_TEXT),

    # --- dark: the experimental theme. The numbers here are the ones that were assumed. ---
    ("dark", "text", "--ink on --bg", "--ink", "--bg", TEXT),
    ("dark", "text", "--ink on --panel", "--ink", "--panel", TEXT),
    ("dark", "text", "--muted on --bg", "--muted", "--bg", TEXT),
    ("dark", "text", "--muted on --panel", "--muted", "--panel", TEXT),
    ("dark", "text", "--brand as link on --bg", "--brand", "--bg", TEXT),
    ("dark", "text", "--on-brand on a --brand fill", "--on-brand", "--brand", TEXT),
    ("dark", "text", "--palette-on-dark on --brand-dark", "--palette-on-dark", "--brand-dark", TEXT),
    ("dark", "text", "--ink on --ok-bg", "--ink", "--ok-bg", TEXT),
    ("dark", "text", "--ink on --bad-bg", "--ink", "--bad-bg", TEXT),
    ("dark", "non-text", "--ok border on --ok-bg", "--ok", "--ok-bg", NON_TEXT),
    ("dark", "non-text", "--bad border on --bad-bg", "--bad", "--bad-bg", NON_TEXT),
    ("dark", "text", "--ok on --bg", "--ok", "--bg", TEXT),
    ("dark", "text", "--bad on --bg", "--bad", "--bg", TEXT),
    ("dark", "decorative", "--line on --bg", "--line", "--bg", NON_TEXT),
    ("dark", "non-text", "--series-2 on --bg", "--series-2", "--bg", NON_TEXT),

    # templates/process-diagram.html paints six LANE ROLES, and a role is not a token: the
    # template maps each role onto a slot. In light the mapping is legible on white; three
    # of those slots are dark by design (primary-dark, primary, primary-darkest) and in dark
    # measure 1.00-1.79:1, which renders a lane colour as nothing, while --status-neutral and
    # --status-positive are inks chosen for white and measure 2.35-3.20:1 there. The dark
    # ramp is therefore declared here, against the surface it is drawn on, so it is measured
    # rather than asserted in a CSS comment. tests/test_process_diagram.py fails if this
    # table and the template's dark block ever disagree.
    ("dark", "non-text", "role c0 on --bg", "--palette-primary-on-dark", "--bg", NON_TEXT),
    ("dark", "non-text", "role c1 on --bg", "--palette-accent", "--bg", NON_TEXT),
    ("dark", "non-text", "role c2 on --bg", "--muted", "--bg", NON_TEXT),
    ("dark", "non-text", "role c3 on --bg", "--ok", "--bg", NON_TEXT),
    ("dark", "non-text", "role c4 on --bg", "--palette-on-dark", "--bg", NON_TEXT),
    ("dark", "non-text", "role c5 on --bg", "--palette-accent-light", "--bg", NON_TEXT),

    # The soft brand tint and the text that reads on it. It is a wash rather than a fill (a
    # hover, a note box, a group band), so the colour that reads there is dark ink in the
    # light theme and light ink in the dark one: one role, declared per theme, which is the
    # whole point of having one. It exists because templates/register.html lettered a
    # --brand-soft band with --brand-dark, and --brand-dark is the darkest surface in the
    # dark theme: dark on dark, unreadable, and no gate was measuring it.
    ("light", "text", "--on-brand-soft on --brand-soft", "--on-brand-soft", "--brand-soft", TEXT),
    ("dark", "text", "--on-brand-soft on --brand-soft", "--on-brand-soft", "--brand-soft", TEXT),
    # A hairline inside a card. Decorative: it separates rows that alignment already
    # separates, so it carries nothing a reader has to perceive.
    ("light", "decorative", "--rule on --panel", "--rule", "--panel", NON_TEXT),
    ("dark", "decorative", "--rule on --panel", "--rule", "--panel", NON_TEXT),
    # A negative figure read as TEXT on a card. Fire Red itself is 4.49:1 on --panel, under
    # AA by a hundredth, and passed for so long only because the panel used to be white.
    # --bad-ink is the same hue one step darker; see theme-light.css.
    ("light", "text", "--bad-ink on --panel", "--bad-ink", "--panel", TEXT),
    ("dark", "text", "--bad-ink on --panel", "--bad-ink", "--panel", TEXT),
    # the delta chip letters red on a red wash, not on the panel.
    ("light", "text", "--bad-ink on --bad-soft", "--bad-ink", "--bad-soft", TEXT),
    ("dark", "text", "--bad-ink on --bad-soft", "--bad-ink", "--bad-soft", TEXT),
    # A mark drawn on a card rather than a page colour. templates/timeline.html paints its
    # bars with this slot in dark, because the palette's primary is chosen to sit on white
    # and is 1.43:1 here: every row of the drawing would be blank. Non-text, so 3:1.
    ("dark", "non-text", "--palette-accent-light on --panel",
     "--palette-accent-light", "--panel", NON_TEXT),

    # The five categorical blocks a survey bar paints its answer options with. They sit
    # beside each other in one stacked bar and the table under it repeats every number, so
    # the bar is not the only carrier: 3:1 against the panel is the floor, not the goal.
    ("light", "non-text", "--cat-1 on --panel", "--cat-1", "--panel", NON_TEXT),
    ("light", "non-text", "--cat-2 on --panel", "--cat-2", "--panel", NON_TEXT),
    ("light", "non-text", "--cat-3 on --panel", "--cat-3", "--panel", NON_TEXT),
    ("light", "non-text", "--cat-4 on --panel", "--cat-4", "--panel", NON_TEXT),
    ("light", "non-text", "--cat-5 on --panel", "--cat-5", "--panel", NON_TEXT),
    ("dark", "non-text", "--cat-1 on --panel", "--cat-1", "--panel", NON_TEXT),
    ("dark", "non-text", "--cat-2 on --panel", "--cat-2", "--panel", NON_TEXT),
    ("dark", "non-text", "--cat-3 on --panel", "--cat-3", "--panel", NON_TEXT),
    ("dark", "non-text", "--cat-4 on --panel", "--cat-4", "--panel", NON_TEXT),
    ("dark", "non-text", "--cat-5 on --panel", "--cat-5", "--panel", NON_TEXT),
)

THEMES = ("light", "dark")

_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_BLOCK = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)
_DECL = re.compile(r"(--[a-zA-Z0-9-]+)\s*:\s*([^;]+)")
_VAR = re.compile(r"var\(\s*(--[a-zA-Z0-9-]+)\s*(?:,\s*([^)]*))?\)")
_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def strip_comments(css: str) -> str:
    """Comments carry the measured numbers this tool replaces. Removing them first means
    a ratio written in prose cannot be mistaken for a declaration."""
    return _COMMENT.sub("", css)


def declarations(css: str) -> dict[str, str]:
    """Every custom property declared in `css`, last declaration winning.

    Last wins because CSS does: the theme files deliberately restate a slot to override the
    palette. A parser that took the first value would measure the wrong colour.
    """
    found: dict[str, str] = {}
    for _selector, body in _BLOCK.findall(strip_comments(css)):
        for name, value in _DECL.findall(body):
            found[name] = value.strip()
    return found


def _selectors_for_theme(css: str, theme: str) -> dict[str, str]:
    """Declarations whose selector applies when `theme` is active.

    A theme is the union of what applies unconditionally (`:root`) and what applies to its
    own selector. `:root[data-theme="light"]` applies in light; `:root[data-theme="dark"]`
    applies in dark and must not leak into light. Later blocks override earlier ones, so a
    theme file placed after the palette wins, which is the documented load order.
    """
    wanted = {
        "light": {":root", ':root[data-theme="light"]'},
        "dark": {":root", ':root[data-theme="dark"]'},
    }[theme]
    found: dict[str, str] = {}
    for selector, body in _BLOCK.findall(strip_comments(css)):
        parts = {p.strip() for p in selector.split(",")}
        if not parts & wanted:
            continue
        for name, value in _DECL.findall(body):
            found[name] = value.strip()
    return found


def resolve(vars_map: dict[str, str], name: str, depth: int = 0) -> str | None:
    """Follow `var()` references to a literal value. Returns None if it never lands on one.

    A cycle or an undefined name returns None rather than recursing. An unresolved token is
    reported, because an unresolved `var()` renders as nothing and would measure as a
    colour that is not on the page.
    """
    if depth > 12:
        return None
    raw = vars_map.get(name)
    if raw is None:
        return None
    raw = raw.strip()
    while True:
        m = _VAR.fullmatch(raw)
        if not m:
            break
        inner = m.group(1)
        fallback = m.group(2)
        nxt = resolve(vars_map, inner, depth + 1)
        if nxt is None:
            if fallback is None:
                return None
            raw = fallback.strip()
            continue
        raw = nxt
        break
    return raw


def to_rgb(value: str) -> tuple[int, int, int] | None:
    """Parse a hex colour. Anything else returns None, which the caller reports."""
    m = _HEX.match(value.strip())
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _linear(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG 2.2 relative luminance."""
    r, g, b = rgb
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    """WCAG 2.2 contrast ratio. Order does not matter; the lighter colour goes on top."""
    a, b = luminance(fg), luminance(bg)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def theme_vars(palette_css: str, theme: str) -> dict[str, str]:
    """The resolved variable map for one theme, in the documented load order.

    Palette first, then the status tokens, then the theme file. `load_token_css` inlines in
    that order and CSS cascade means the last declaration wins, so a theme that restates a
    slot overrides the palette exactly as it does in a shipped artefact.
    """
    merged: dict[str, str] = {}
    merged.update(declarations(palette_css))
    # CORE_TOKEN_ORDER, not a second list copied here: a role added to the load order and
    # forgotten in this tool measures as "does not resolve", which is how the categorical
    # series was declared, inlined and reported missing in the same run.
    for name in tok.CORE_TOKEN_ORDER:
        merged.update(_selectors_for_theme(
            (tok.CORE_TOKENS / name).read_text(encoding="utf-8"), theme))
    return merged


def measure(palette_css: str, themes: tuple[str, ...] = THEMES) -> list[dict]:
    """Measure every pair in PAIRS. Returns one row per pair, in table order."""
    rows: list[dict] = []
    for theme in themes:
        vars_map = theme_vars(palette_css, theme)
        for pair_theme, kind, label, fg_name, bg_name, minimum in PAIRS:
            if pair_theme != theme:
                continue
            row = {
                "theme": theme,
                "kind": kind,
                "label": label,
                "fg": fg_name,
                "bg": bg_name,
                "min": minimum,
                "ratio": None,
                "fg_hex": None,
                "bg_hex": None,
                "reason": "",
            }
            fg_lit = resolve(vars_map, fg_name)
            bg_lit = resolve(vars_map, bg_name)
            if fg_lit is None:
                row["reason"] = f"{fg_name} does not resolve to a literal colour"
            elif bg_lit is None:
                row["reason"] = f"{bg_name} does not resolve to a literal colour"
            else:
                fg_rgb, bg_rgb = to_rgb(fg_lit), to_rgb(bg_lit)
                if fg_rgb is None:
                    row["reason"] = f"{fg_name} = {fg_lit!r} is not a hex colour"
                elif bg_rgb is None:
                    row["reason"] = f"{bg_name} = {bg_lit!r} is not a hex colour"
                else:
                    row["fg_hex"] = fg_lit.lower()
                    row["bg_hex"] = bg_lit.lower()
                    row["ratio"] = contrast(fg_rgb, bg_rgb)
            row["passes"] = bool(
                row["kind"] == "decorative"
                or (row["ratio"] is not None and row["ratio"] >= minimum))
            rows.append(row)
    return rows


def verdict(row: dict) -> str:
    if row["ratio"] is None:
        return "UNMEASURABLE"
    return "PASS" if row["passes"] else "FAIL"


def report(rows: list[dict], theme: str) -> str:
    """A fixed-width table. The ratio is printed to two decimals, the same precision the
    token comments use, so a number in a comment and a number here are comparable."""
    out = [f"theme: {theme}", ""]
    out.append(f"  {'pair':<44} {'fg':<10} {'bg':<10} {'ratio':>6} {'min':>5}  verdict")
    for row in rows:
        if row["theme"] != theme:
            continue
        ratio = f"{row['ratio']:.2f}" if row["ratio"] is not None else "-"
        fg = row["fg_hex"] or "-"
        bg = row["bg_hex"] or "-"
        line = (f"  {row['label']:<44} {fg:<10} {bg:<10} {ratio:>6} "
                f"{row['min']:>5.1f}  {verdict(row)}")
        if row["reason"]:
            line += f"  ({row['reason']})"
        out.append(line)
    out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else "")
    parser.add_argument("--theme", choices=("light", "dark", "both"), default="both",
                        help="which theme to measure (default: both)")
    parser.add_argument("--prefer-plugin", action="store_true",
                        help="use the single installed plugin's palette")
    parser.add_argument("--palette", help="path to a palette CSS file, relative to the repo root")
    args = parser.parse_args(argv)

    path, source = tok.palette_path(prefer_plugin=args.prefer_plugin, palette=args.palette)
    css = path.read_text(encoding="utf-8")
    missing = tok.missing_slots(css)
    if missing:
        print(f"palette {tok.rel(path)} does not define: {', '.join(missing)}")
        return 2

    themes = THEMES if args.theme == "both" else (args.theme,)
    rows = measure(css, themes)

    print(f"palette: {tok.rel(path)} ({source})")
    print()
    failures = 0
    for theme in themes:
        print(report(rows, theme))
        for row in rows:
            if row["theme"] == theme and not row["passes"]:
                failures += 1

    total = len(rows)
    print(f"{total - failures} of {total} pairs pass")
    if failures:
        print(f"{failures} FAIL:")
        for row in rows:
            if not row["passes"]:
                print(f"  {row['theme']:<5} {row['label']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
