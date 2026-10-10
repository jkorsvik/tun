#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_no_real_data_gate.py — prove the real-data gate gates, and keeps gating.

Stdlib only.

    python3 tests/test_no_real_data_gate.py

Why this file is larger than the checks it tests
------------------------------------------------
This gate exists because one `git add -A` is enough to put a survey export with names and
e-mail addresses on main. The gate is the only automatic thing standing between a repeat and main, and
this repository has no CI, so "it passed locally" is the whole assurance. That makes the
gate a single point of failure and makes a green suite worth nothing on its own.

So every fixture asserts three things, not one:

  1. the gate fires                  — the right detector reports the fixture
  2. for the right reason            — the reported kind names the right class of data
  3. and nothing leaks into the log  — the redacted output must not contain the value

Plus a mutation pass: each detector is neutralised in turn and every fixture re-run. If a
fixture still fires with its detector disabled, that fixture was testing something else.
A suite that cannot tell a working gate from a deleted one is theatre; this repository has
already been bitten by exactly that.
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import check_no_real_data as gate  # noqa: E402
import tree_scan  # noqa: E402

passed = failed = 0


def chk(label: str, got, want) -> None:
    global passed, failed
    if got == want:
        print(f"  PASS {label}")
        passed += 1
    else:
        trim = lambda v: (r if len(r := repr(v)) <= 140 else r[:137] + "...")
        print(f"  FAIL {label}: got {trim(got)}, wanted {trim(want)}")
        failed += 1


# Fixture values are ASSEMBLED AT RUNTIME, never written as literals.
#
# This gate scans every tracked text file, including this one. The first version of this
# suite hard-coded a valid organisation number and a few addresses, and the gate correctly
# blocked the commit that added it. The tempting fix is to exempt the gate's own files, but
# a blanket exemption is exactly where real data would hide. Assembling the values instead
# keeps the gate universal with zero exemptions, and makes this file demonstrate the
# discipline it enforces.
def _join(*parts: str) -> str:
    return "".join(parts)


def _valid_orgnr() -> str:
    """Search for a checksum-valid organisation number so no literal is stored."""
    weights = (3, 2, 7, 6, 5, 4, 3, 2)
    for candidate in range(91234500, 91235500):
        base = str(candidate)
        total = sum(int(d) * w for d, w in zip(base, weights))
        check = 11 - (total % 11)
        if check == 11:
            check = 0
        if check == 10:
            continue
        number = base + str(check)
        if gate._orgnr_valid(number):
            return number
    raise SystemExit("could not construct a checksum-valid organisation number")


ORGNR = _valid_orgnr()
ADDRESS = _join("ola.nordmann", "@", "eksempelfirma", ".no")
COMPANY_ADDRESS = _join("gudrun.dahl", "@", "skodre-bedrift", ".no")
PHONE = _join("+47", " 22", " 31", " 20", " 00")


def _make_valid_fnr() -> str:
    w1 = (3, 7, 6, 1, 8, 9, 4, 5, 2)
    w2 = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    for serial in range(1000):
        base = f"010298{serial:03d}"
        k1 = 11 - (sum(int(d) * w for d, w in zip(base, w1)) % 11)
        if k1 == 11:
            k1 = 0
        if k1 > 9:
            continue
        ten = base + str(k1)
        k2 = 11 - (sum(int(d) * w for d, w in zip(ten, w2)) % 11)
        if k2 == 11:
            k2 = 0
        if k2 > 9:
            continue
        candidate = ten + str(k2)
        if gate._fnr_valid(candidate):
            return candidate
    raise SystemExit("could not construct a checksum-valid test identity number")


FNR = _make_valid_fnr()

# (text, expected kind or None, label)
FIXTURES: list[tuple[str, str | None, str]] = [
    (f"Kontakt: {ADDRESS}", "e-mail address", "a plain address"),
    (f"mailto:{ADDRESS}", "e-mail address", "a mailto address"),
    (f"Orgnr {ORGNR}", "organisation number", "a checksum-valid organisation number"),
    (f"Fodselsnummer {FNR}", "national identity number",
     "a checksum-valid identity number"),
    (f"Ring {PHONE}", "Norwegian phone number", "a Norwegian phone number"),
    # Must NOT fire. Each of these broke an earlier version of the gate.
    (_join("git clone git", "@", "forge.intern", ":org/dotfiles.git"), None,
     "an scp-style git remote"),
    (_join("ssh://git", "@", "forge.intern", "/x.git"), None, "ssh URL userinfo"),
    (_join("https://user", "@", "example.org", "/path"), None, "https URL userinfo"),
    (_join("Write to hello", "@", "example", ".com"), None,
     "an RFC 2606 documentation domain"),
    ('"coordinates": [884287641, 12]', None, "nine digits that fail the orgnr checksum"),
    ("Timestamp 17589312000 millis", None, "eleven digits that fail the fnr checksum"),
]

print("shape detection, both directions")
for text, want_kind, label in FIXTURES:
    kinds = [kind for _, kind, _ in gate.scan_text("fixture", text)]
    if want_kind is None:
        chk(f"{label} does not fire", kinds, [])
    else:
        chk(f"{label} fires as {want_kind}", kinds, [want_kind])

print("\nno fixture fires for a neighbouring reason")
for text, want_kind, label in FIXTURES:
    if want_kind is None:
        continue
    kinds = {kind for _, kind, _ in gate.scan_text("fixture", text)}
    chk(f"{label} reports only its own kind", kinds, {want_kind})

print("\nredaction: the log must not carry the value")
SECRET_ADDRESS = COMPANY_ADDRESS
shown = [s for _, _, s in gate.scan_text("f", f"Kontakt {SECRET_ADDRESS}")]
chk("the address itself is absent from the report", SECRET_ADDRESS in str(shown), False)
chk("the local part is not shown in full", "gudrun.dahl" in str(shown), False)
# The domain is the identifying half when respondents are companies. The first version of
# this gate printed it, and listed twelve real companies into a terminal in doing so.
chk("the company domain is not shown", "skodre-bedrift" in str(shown), False)
chk("enough is shown to locate the hit", shown and shown[0].endswith(".no"), True)
chk("the digit redaction hides the middle", gate.redact(ORGNR), f"{ORGNR[:2]}***{ORGNR[-1]} (9 digits)")

print("\nchecksum validators")
chk("a constructed organisation number validates", gate._orgnr_valid(ORGNR), True)
chk("the geojson nine-digit value does not", gate._orgnr_valid("884287641"), False)
chk("a sequential nine-digit value does not", gate._orgnr_valid("123456789"), False)
chk("the constructed identity number validates", gate._fnr_valid(FNR), True)
chk("an implausible month is rejected",
    gate._fnr_valid(_join("0199981234", "5")), False)

print("\ndata-file location rule")
for rel in sorted(gate.ALLOWED_DATA):
    chk(f"allowed: {rel}", gate.data_file_is_allowed(rel), True)
chk("a stray export is not allowed",
    gate.data_file_is_allowed("examples/07-topbar-pattern-demo/export.json"), False)
chk("every allowlist entry carries a reason",
    all(isinstance(v, str) and len(v) > 10 for v in gate.ALLOWED_DATA.values()), True)
# Assert the invariant, not an exact equality. An exact set here broke the moment a legitimate
# plugin manifest was added, and the pressure then is to widen the allowlist rather than to
# recognise the shape. Two directions instead: nothing tracked is disallowed, and no allowlist
# entry has gone stale.
_tracked_data = [f for f in tree_scan.tracked_paths()
                 if pathlib.Path(f).suffix.lower() in gate.DATA_SUFFIXES]
chk("no tracked data file is disallowed",
    [f for f in _tracked_data if not gate.data_file_is_allowed(f)], [])
chk("no allowlist entry has gone stale",
    [f for f in gate.ALLOWED_DATA if f not in _tracked_data], [])
chk("a plugin manifest is allowed by shape, not by allowlisting",
    (gate.data_file_is_allowed("plugins/anything/manifest.json"),
     "plugins/anything/manifest.json" in gate.ALLOWED_DATA), (True, False))
chk("a data file smuggled into a plugin is still refused",
    gate.data_file_is_allowed("plugins/eksempel/export.csv"), False)
chk("a nested manifest-shaped path is not allowed",
    gate.data_file_is_allowed("plugins/eksempel/examples/manifest.json"), False)
# The Claude Code manifests are allowed by exact path, and nothing else in that directory is.
for _rel in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
    chk(f"allowed by exact path, not by shape: {_rel}",
        (gate.data_file_is_allowed(_rel), _rel in gate.ALLOWED_DATA), (True, True))
chk("another JSON file in .claude-plugin/ is refused",
    gate.data_file_is_allowed(".claude-plugin/other.json"), False)
chk("a data file in .claude-plugin/ is refused",
    gate.data_file_is_allowed(".claude-plugin/export.csv"), False)
chk("the manifest names are not matched below another directory",
    gate.data_file_is_allowed("docs/.claude-plugin/plugin.json"), False)
chk("the manifest names are not matched at the wrong level",
    gate.data_file_is_allowed("plugin.json"), False)

print("\nassert_synthetic (the builder-side, allowlist form)")
COLUMNS = ("Kode", "Status")
VOCAB = {"Kode": r"ELEV-\d{2}", "Status": r"I rute|Venter|Avlyst"}
good = [{"Kode": "ELEV-01", "Status": "I rute"}]
bad = [{"Kode": "Ola Nordmann", "Status": "I rute"}]
try:
    gate.assert_synthetic(good, COLUMNS, VOCAB)
    got = "accepted"
except SystemExit:
    got = "rejected"
chk("synthetic rows are accepted", got, "accepted")
try:
    gate.assert_synthetic(bad, COLUMNS, VOCAB)
    got = "accepted"
except SystemExit:
    got = "rejected"
chk("a real-looking name is rejected", got, "rejected")
try:
    gate.assert_synthetic([{"Kode": "ELEV-01"}], COLUMNS, VOCAB)
    got = "accepted"
except SystemExit:
    got = "rejected"
chk("a missing column is rejected", got, "rejected")

print("\nscope")
chk("scope is non-empty", bool(gate.tracked_text()), True)
chk("binaries are excluded",
    [f for f in gate.tracked_text() if f.endswith(".png")], [])
with tempfile.TemporaryDirectory() as tmp:
    subprocess.run(["git", "init", "-q", tmp], check=True, env=tree_scan.clean_env())
    try:
        tree_scan.tracked_paths(pathlib.Path(tmp))
        got = "returned normally"
    except tree_scan.ScopeError:
        got = "raised ScopeError"
    chk("an empty scope raises rather than reporting a clean tree", got,
        "raised ScopeError")

# Git hooks export GIT_DIR and GIT_INDEX_FILE, and those override `git -C <path>`. This gate
# runs from a hook, so the scope has to be independent of the caller's git environment.
_saved = dict(os.environ)
os.environ["GIT_DIR"] = str(REPO / ".git")
os.environ["GIT_INDEX_FILE"] = str(REPO / ".git" / "index")
try:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True, env=tree_scan.clean_env())
        try:
            tree_scan.tracked_paths(pathlib.Path(tmp))
            got = "returned normally"
        except tree_scan.ScopeError:
            got = "raised ScopeError"
    chk("scope ignores an inherited GIT_DIR (the pre-commit hook case)", got,
        "raised ScopeError")
finally:
    os.environ.clear()
    os.environ.update(_saved)

# ---------------------------------------------------------------------------
# Mutation pass — neutralise each detector, confirm the fixtures notice
# ---------------------------------------------------------------------------
print("\nmutation pass — neutralise each detector, the suite must notice")

NEVER = re.compile(r"(?!x)x")  # matches nothing

DETECTORS = {
    "e-mail address": ("EMAIL", NEVER),
    "Norwegian phone number": ("PHONE_NO", NEVER),
    "organisation number": ("_orgnr_valid", lambda _n: False),
    "national identity number": ("_fnr_valid", lambda _n: False),
}

for kind, (attribute, replacement) in DETECTORS.items():
    fixtures_for_kind = [(t, l) for t, w, l in FIXTURES if w == kind]
    original = getattr(gate, attribute)
    setattr(gate, attribute, replacement)
    try:
        still_firing = [
            label for text, label in fixtures_for_kind
            if kind in {k for _, k, _ in gate.scan_text("fixture", text)}
        ]
        chk(f"{kind}: disabling {attribute} silences its fixture(s) "
            f"(detector was load-bearing)", still_firing, [])
        # And the other detectors must be unaffected, so one fixture cannot cover for
        # another's disabled detector.
        others_ok = all(
            other_kind in {k for _, k, _ in gate.scan_text("fixture", text)}
            for text, other_kind, _ in FIXTURES
            if other_kind is not None and other_kind != kind
        )
        chk(f"{kind}: the other detectors still fire", others_ok, True)
    finally:
        setattr(gate, attribute, original)

print("\nmutation pass — the location rule, which the detector loop cannot reach")
# The loop above neutralises TEXT detectors. data_file_is_allowed is a different kind of
# rule: it answers a question about a PATH. Nothing above would notice if it were deleted
# and replaced with "everything is fine", which is the shape a careless refactor takes.
_orig_allowed = gate.data_file_is_allowed
try:
    gate.data_file_is_allowed = lambda _rel: True
    chk("with the location rule forced open, a stray export stops being reported",
        gate.data_file_is_allowed("work/case/raw.json"), True)
    _tracked = [f for f in tree_scan.tracked_paths()
                if pathlib.Path(f).suffix.lower() in gate.DATA_SUFFIXES]
    chk("...and the tracked-tree check it feeds reports nothing",
        [f for f in _tracked if not gate.data_file_is_allowed(f)], [])
finally:
    gate.data_file_is_allowed = _orig_allowed
chk("restored: a stray export is refused again",
    gate.data_file_is_allowed("work/case/raw.json"), False)
chk("restored: the allowlist still admits the core packaging manifest",
    gate.data_file_is_allowed("plugin/manifest.json"), True)
# The two manifest paths differ by one letter and by one path segment, so assert that the
# shape rule and the allowlist each cover their own case and neither covers the other's.
chk("the shape rule alone does not admit the core packaging manifest",
    "plugin/manifest.json" in gate.ALLOWED_DATA, True)
chk("the allowlist alone does not admit a plugin manifest",
    "plugins/eksempel/manifest.json" in gate.ALLOWED_DATA, False)

# The two Claude Code manifest entries must be what admits them. Remove them and the
# manifests are refused, so the "allowed" checks above are not passing for another reason.
_saved = {k: gate.ALLOWED_DATA.pop(k) for k in
          (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json")}
try:
    chk("without their allowlist entries the two manifests are refused",
        [gate.data_file_is_allowed(k) for k in _saved], [False, False])
finally:
    gate.ALLOWED_DATA.update(_saved)
chk("restored: the two manifests are admitted again",
    [gate.data_file_is_allowed(k) for k in _saved], [True, True])

print("\nafter the mutation pass, every detector is live again")
for text, want_kind, label in FIXTURES:
    kinds = [k for _, k, _ in gate.scan_text("fixture", text)]
    chk(f"restored: {label}", kinds, [] if want_kind is None else [want_kind])

print("\n" + "─" * 66)
print(f"{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
