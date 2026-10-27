#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_token_contrast.py: prove tools/check_token_contrast.py measures what it claims.

Stdlib only.

    python3 tests/test_token_contrast.py

Why this exists
---------------
`theme-dark.css` and `status-semantic.css` both carry contrast ratios in their comments.
A ratio in a comment beside a hex value is a claim: nothing re-measures it when the hex
changes. `tools/check_token_contrast.py` turns the claim into a check, and this suite
proves the check can fail. A gate that only ever prints PASS is worse than no gate,
because it is read as evidence.

The first run found five real defects in the dark theme (three low, two invisible). Those
are fixed. The two that remain are brand-level facts, not core bugs, and they are pinned
here as a *ratchet*: the set of failures must equal the set recorded below. A new failure
fails this suite, and so does fixing one without updating the record, so the record
cannot quietly go stale in either direction.
"""
from __future__ import annotations

import hashlib
import pathlib
import shutil
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import check_token_contrast as cc  # noqa: E402
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


def failures(rows):
    """The failing pairs as (theme, label) tuples, the shape the ratchet compares."""
    return sorted((r["theme"], r["label"]) for r in rows if not r["passes"])


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


#: Palettes that ship in this repo, and the pairs each is *known* to fail.
#:
#: Both remaining failures are brand facts recorded elsewhere, not core bugs:
#:
#:   brand palette, --series-2   the only accent the plugin intends as a fill measures
#:                    2.10:1 on white, which `status-semantic.css` already documents as
#:                    failing the 3:1 non-text minimum. No other sanctioned fill colour
#:                    exists, so this cannot be fixed by re-picking a value inside core:
#:                    it is the open chart-palette work in docs/10.
#:   tun palette, --bad on --bg  the status red measures 4.44:1 on this palette's paper
#:                    surface, 0.06 under the text minimum. It passes on pure white and
#:                    on the other surfaces, which is why core's status token is not
#:                    wrong: the palette's surface is simply warmer than the one the red
#:                    was chosen against. Fixing it means either a darker red for
#:                    near-white surfaces or a white backdrop behind status text; both
#:                    are decisions about the brand, not about this tool.
EXPECTED = {
    "plugins/tun/tokens/palette.css": [("light", "--series-2 on --bg")],
    "plugins/tun/tokens/palette.css": [("light", "--bad on --bg")],
}

PALETTES = [
    "tools/tokens/palette-neutral.css",
    "plugins/tun/tokens/palette.css",
    "plugins/tun/tokens/palette.css",
]

print("every shipped palette defines the whole seam, the ninth slot included")
for rel in PALETTES:
    path = REPO / rel
    css = path.read_text(encoding="utf-8")
    chk(f"{rel} defines all {len(tok.REQUIRED_SLOTS)} slots", tok.missing_slots(css), [])
    chk(f"{rel} defines --palette-primary-on-dark", "--palette-primary-on-dark:" in css, True)

print("\ncore's own palette passes every declared pair, in both themes")
neutral = (REPO / PALETTES[0]).read_text(encoding="utf-8")
rows = cc.measure(neutral)
# Every declared pair must produce a row: measure() walks the whole table, so a row count
# below it means one was skipped. The floor is a ratchet, not the table's own length, so
# losing rows from PAIRS is loud rather than quietly reducing what the gate covers.
chk("every declared pair is measured, and never fewer than 36",
    (len(rows) == len(cc.PAIRS), len(rows) >= 36), (True, True))
chk("light and dark are both covered",
    sorted({r["theme"] for r in rows}), ["dark", "light"])
chk("nothing fails on the neutral palette", failures(rows), [])
chk("no pair is unmeasurable", [r["label"] for r in rows if r["ratio"] is None], [])

print("\nthe dark theme's dark-mode roles are the measured ones, not the light values")
by_label = {(r["theme"], r["label"]): r for r in rows}
chk("--brand in dark is the on-dark slot",
    cc.theme_vars(neutral, "dark")["--brand"], "var(--palette-primary-on-dark)")
chk("--brand in dark clears 4.5:1", by_label[("dark", "--brand as link on --bg")]["ratio"] >= 4.5, True)
chk("--ok in dark clears 4.5:1", by_label[("dark", "--ok on --bg")]["ratio"] >= 4.5, True)
chk("--bad in dark clears 4.5:1", by_label[("dark", "--bad on --bg")]["ratio"] >= 4.5, True)
chk("the dark status chip label is readable",
    by_label[("dark", "--ink on --ok-bg")]["ratio"] >= 4.5, True)
chk("the dark status chip is a dark tint, not a light one",
    cc.theme_vars(neutral, "dark")["--ok-bg"].lower() != "var(--status-positive-bg-12)", True)

print("\nbrand palettes: measured failures equal the recorded set (a ratchet both ways)")
for rel in PALETTES[1:]:
    rows_p = cc.measure((REPO / rel).read_text(encoding="utf-8"))
    got = failures(rows_p)
    want = sorted(EXPECTED.get(rel, []))
    chk(f"{rel}: failures match the record", got, want)
    if got:
        print(f"       (recorded, with the reason in this file's header: {got})")

print("\nmutation control 1: reverting the dark brand colour to the light one is caught")
real_tokens = tok.CORE_TOKENS
tmp = pathlib.Path(tempfile.mkdtemp(prefix="tun-contrast-"))
try:
    for name in ("status-semantic.css", "theme-light.css", "theme-dark.css"):
        shutil.copy2(real_tokens / name, tmp / name)
    before = {n: sha(tmp / n) for n in ("theme-dark.css",)}
    dark = tmp / "theme-dark.css"
    original = dark.read_text(encoding="utf-8")
    # The exact pre-fix declaration. It must be a *mutation that applies*: if the string
    # is absent the edit is a no-op and a PASS below would mean nothing.
    mutated_text = original.replace(
        "--brand:      var(--palette-primary-on-dark);",
        "--brand:      var(--palette-primary);")
    chk("the mutation applied to theme-dark.css", mutated_text != original, True)
    dark.write_text(mutated_text, encoding="utf-8")
    chk("the mutated file really changed on disk", sha(dark) != before["theme-dark.css"], True)

    tok.CORE_TOKENS = tmp
    try:
        mrows = cc.measure(neutral)
        mfail = failures(mrows)
        chk("the gate reports the reverted brand as a failure",
            ("dark", "--brand as link on --bg") in mfail, True)
        # Two pairs read the brand colour, so reverting it breaks both: the link, and
        # the text drawn on a brand fill. Asserting the exact set keeps a future pair
        # from joining them unnoticed.
        chk("and it reports exactly the pairs that read --brand", mfail,
            sorted([("dark", "--brand as link on --bg"),
                    ("dark", "--on-brand on a --brand fill")]))
        mrow = {(r["theme"], r["label"]): r for r in mrows}[("dark", "--brand as link on --bg")]
        chk("with the ratio the token comment used to claim", round(mrow["ratio"], 2), 1.43)
    finally:
        tok.CORE_TOKENS = real_tokens

    dark.write_text(original, encoding="utf-8")
    chk("the mutation was restored byte for byte", sha(dark), before["theme-dark.css"])
    chk("and the clean tree measures clean again", failures(cc.measure(neutral)), [])
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    tok.CORE_TOKENS = real_tokens

print("\nmutation control 2: a light chip in the dark theme is caught")
tmp2 = pathlib.Path(tempfile.mkdtemp(prefix="tun-contrast-"))
try:
    for name in ("status-semantic.css", "theme-light.css", "theme-dark.css"):
        shutil.copy2(real_tokens / name, tmp2 / name)
    dark2 = tmp2 / "theme-dark.css"
    original2 = dark2.read_text(encoding="utf-8")
    mutated2 = original2.replace("--ok-bg: #12332c;", "--ok-bg: var(--status-positive-bg-12);")
    chk("the mutation applied to theme-dark.css", mutated2 != original2, True)
    dark2.write_text(mutated2, encoding="utf-8")
    tok.CORE_TOKENS = tmp2
    try:
        label = ("dark", "--ink on --ok-bg")
        row = {r["theme"] + "|" + r["label"]: r for r in cc.measure(neutral)}["dark|" + label[1]]
        chk("a light chip makes the dark chip label fail", row["passes"], False)
        chk("at the invisible ratio the fix removed", round(row["ratio"], 2), 1.04)
    finally:
        tok.CORE_TOKENS = real_tokens
    dark2.write_text(original2, encoding="utf-8")
    chk("restored byte for byte", sha(dark2), sha(real_tokens / "theme-dark.css"))
finally:
    shutil.rmtree(tmp2, ignore_errors=True)
    tok.CORE_TOKENS = real_tokens

print("\nmutation control 3: a palette missing the ninth slot is named, not silently defaulted")
stripped = neutral.replace("--palette-primary-on-dark: #9CC0E8;", "")
chk("the strip applied", "--palette-primary-on-dark" in stripped, False)
chk("the missing slot is reported by name",
    tok.missing_slots(stripped), ["--palette-primary-on-dark"])

print("\nmutation control 4: the ratio maths itself is WCAG's, not an approximation")
chk("black on white is 21:1", round(cc.contrast(cc.to_rgb("#000000"), cc.to_rgb("#ffffff")), 2), 21.0)
chk("white on white is 1:1", round(cc.contrast(cc.to_rgb("#ffffff"), cc.to_rgb("#ffffff")), 2), 1.0)
chk("order does not matter",
    round(cc.contrast(cc.to_rgb("#767676"), cc.to_rgb("#ffffff")), 4),
    round(cc.contrast(cc.to_rgb("#ffffff"), cc.to_rgb("#767676")), 4))
chk("a 3-digit hex expands", cc.to_rgb("#fff"), (255, 255, 255))
chk("a non-hex colour is refused rather than guessed", cc.to_rgb("rgba(0,0,0,.5)"), None)

print("\n" + "-" * 66)
print(f"{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
