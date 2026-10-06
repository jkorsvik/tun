#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_core_boundary_gate.py — prove the core/plugin boundary gate gates.

Stdlib only.

    python3 tests/test_core_boundary_gate.py

The gate holds invariant 4 of docs/22-plugin-contract.md: core names no organisation, design
system, internal host or person. It works by comparing a scan against a committed baseline, and
a baseline comparison is exactly the kind of check that can pass without doing anything: if the
scan silently returned nothing, every ratchet would read as "clean" and the gate would report
success forever.

So the assertions here are about the gate's ability to FAIL, in all four directions it must:
a forbidden category becoming non-empty, a ratchet rising, a ratchet falling without being
banked, and a new file appearing in a category.
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))


def _j(*parts: str) -> str:
    """Fixtures are ASSEMBLED AT RUNTIME. This gate scans core, and this file is core, so a
    literal fixture would register in the category it tests. Same discipline as
    tests/test_no_real_data_gate.py."""
    return "".join(parts)


# The identity categories come from a local denylist that is not in the repository. Point
# the gate at a fixture denylist of invented terms BEFORE importing it, so this suite is
# hermetic: it tests the mechanism, never the maintainer's private list.
_DENY = pathlib.Path(tempfile.mkdtemp(prefix="tun-core-gate-")) / "deny.txt"
_DENY.write_text("\n".join([
    "# fixture",
    "person\t" + _j("zyx", "qorp"),
    "person\t" + _j("vuw", "tenk"),
    "org\t" + _j("\\bqorp", "corp\\b"),
    "host\t" + _j("intra\\.qorp", "\\.example"),
]) + "\n", encoding="utf-8")
os.environ["TUN_DENYLIST"] = str(_DENY)

import check_core_is_generic as gate  # noqa: E402
import tree_scan  # noqa: E402

passed = failed = 0


def chk(label, got, want):
    global passed, failed
    if got == want:
        print(f"  PASS {label}")
        passed += 1
    else:
        print(f"  FAIL {label}: got {got!r}, wanted {want!r}")
        failed += 1


print("scope")
current = gate.scan()
chk("scope is non-empty", current["_scope"]["files"] > 0, True)
chk("plugins/ is outside core", gate.in_core("plugins/eksempel/tokens/palette.css"), False)
chk("core files are inside core", gate.in_core("tools/tokens/theme-light.css"), True)
chk("binaries are skipped", gate.in_core("docs/assets/probe-local-render.png"), False)
# The baseline file lists every pattern it tracks, so scanning it would count its own contents.
chk("the baseline file excludes itself",
    gate.in_core("tools/core_generic_baseline.json"), False)
chk("the gate source excludes itself",
    gate.in_core("tools/check_core_is_generic.py"), False)

print("\nthe derived categories found something to look for")
# A derived pattern that resolves to nothing would make its category pass vacuously.
for _n in ("logo-artwork", "brand-token", "brand-hex"):
    chk(f"{_n}: derived from plugins/, not empty", bool(gate.CATEGORIES[_n][0]), True)
chk("every fixture denylist label became a category",
    sorted(n for n in gate.CATEGORIES if n.startswith("local:")),
    ["local:host", "local:org", "local:person"])

print("\nthe forbidden categories are actually empty")
for _n, (_p, _k, _w) in gate.CATEGORIES.items():
    if _k == "forbidden":
        chk(f"{_n} is absent from core", gate.total(current[_n]), 0)

print("\nthe baseline matches reality (else the ratchet is fiction)")
baseline = gate.load_baseline()
for name, (_pat, kind, _why) in gate.CATEGORIES.items():
    if kind != "ratcheted":
        continue
    chk(f"{name}: baseline counts match the scan", current[name], baseline.get(name, {}))

print("\nthe total is derived, so it cannot disagree with the per-file counts")
chk("total() sums the counts", gate.total({"a": 2, "b": 3}), 5)
chk("total() of nothing is 0", gate.total({}), 0)
# The stored total was removed precisely because it could drift. Assert the stored shape
# cannot carry one, rather than trusting that nobody will add it back.
chk("no category in the baseline stores a total",
    [n for n, v in baseline.items() if "total" in v], [])
chk("no category in the baseline nests under 'files'",
    [n for n, v in baseline.items() if "files" in v], [])

print("\nevery category has a stated reason and a valid kind")
for name, (pat, kind, why) in gate.CATEGORIES.items():
    chk(f"{name}: kind is known", kind in ("forbidden", "ratcheted"), True)
    chk(f"{name}: has a reason", len(why) > 20, True)

print("\npatterns fire on what they claim to, and not on near misses")
import re  # noqa: E402

CASES = [
    ("logo-artwork", _j('d="M8 8h56', 'v14H22v11h36"'), True),
    ("logo-artwork", _j('d="M8 8h57', 'v14H22"'), False),
    ("brand-token", _j("var(--", "eksem", "pel-blue)"), True),
    ("brand-token", "var(--palette-primary)", False),
    ("brand-hex", _j("#2F", "5D9E"), True),
    ("brand-hex", "#2B4C7E", False),          # core's own neutral primary
    ("brand-hex", "#FFFFFF", False),          # a shared neutral belongs to nobody
    ("local:person", _j("by Zyx", "qorp"), True),
    ("local:person", "by Per Hansen", False),
    ("local:org", _j("a Qorp", "corp laptop"), True),
    ("local:org", _j("qorp", "corpse"), False),
    ("local:host", _j("intra.qorp", ".example"), True),
    ("local:host", "example.com", False),
]
for name, text, want in CASES:
    rx = re.compile(gate.CATEGORIES[name][0])
    chk(f"{name}: {text!r} fires={want}", bool(rx.search(text)), want)

print("\nwithout a denylist the identity categories are absent, never silently clean")
_none = gate.build_categories(pathlib.Path("/nonexistent/denylist.txt"))
chk("no local: categories without a denylist",
    [n for n in _none if n.startswith("local:")], [])

print("\nthe gate can fail in all four directions (simulated against the real baseline)")


def verdict(scanned: dict, base: dict | None = None) -> str:
    """Classify a scan the way the CLI does.

    This is a REIMPLEMENTATION, which is a real weakness: main() could drift from it and
    this suite would still pass. It exists because main() takes no scan argument, so the
    only way to test a hypothetical tree is to model the comparison. It is mitigated
    directly below, where the real main() is run against the real tree and its exit code
    is required to agree with this function's verdict. Divergence in the case that
    actually ships is therefore caught; divergence in the simulated cases is not, and
    that is the honest limit of this design.
    """
    base = baseline if base is None else base
    for name, (_p, kind, _w) in gate.CATEGORIES.items():
        hits = scanned[name]
        got_total, got_files = gate.total(hits), set(hits)
        if kind == "forbidden":
            if got_total:
                return "forbidden-present"
            continue
        want = base.get(name, {})
        if got_files - set(want):
            return "new-file"
        if got_total > gate.total(want):
            return "regression"
        if got_total < gate.total(want):
            return "unbanked-progress"
    return "pass"


import copy  # noqa: E402

chk("unmodified scan passes", verdict(copy.deepcopy(current)), "pass")

m = copy.deepcopy(current)
m["logo-artwork"] = {"docs/00-vision.md": 1}
chk("artwork in core is refused", verdict(m), "forbidden-present")

# The ratchet simulations need a non-empty ratchet. Seed one file in both the scan and a
# copy of the baseline, so the test does not depend on how much debt happens to remain.
_base = copy.deepcopy(baseline)
_seed = copy.deepcopy(current)
_base.setdefault("brand-hex", {})["docs/zz-seed.md"] = 2
_seed["brand-hex"]["docs/zz-seed.md"] = 2
chk("the seeded scan passes against the seeded baseline", verdict(_seed, _base), "pass")

m = copy.deepcopy(_seed)
m["brand-hex"]["docs/zz-seed.md"] += 1
chk("a ratchet rising is refused", verdict(m, _base), "regression")

m = copy.deepcopy(_seed)
m["brand-hex"]["docs/zz-seed.md"] -= 1
chk("a ratchet falling unbanked is refused", verdict(m, _base), "unbanked-progress")

m = copy.deepcopy(current)
m["brand-token"]["docs/zz-new.md"] = 1
chk("a new file in a category is refused", verdict(m), "new-file")

print("\nthe REAL main() agrees with the model on the tree that actually ships")
# Without this, the four simulations above only prove the model self-consistent. Running
# the real entry point ties the model to the code under test: if main()'s comparison were
# deleted or inverted, its exit code would stop matching.
import contextlib  # noqa: E402
import io  # noqa: E402

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    real_rc = gate.main()
chk("main() exit code matches the model's verdict for the real tree",
    (real_rc == 0), (verdict(copy.deepcopy(current)) == "pass"))
chk("main() printed a report rather than nothing", len(buf.getvalue()) > 0, True)

print("\nload_baseline refuses a shape it cannot trust")


def _reject(payload) -> bool:
    """True when load_baseline refuses this payload."""
    import json as _json
    import tempfile
    orig = gate.BASELINE_PATH
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        _json.dump(payload, fh)
        tmp = pathlib.Path(fh.name)
    try:
        gate.BASELINE_PATH = tmp
        try:
            gate.load_baseline()
            return False
        except SystemExit:
            return True
    finally:
        gate.BASELINE_PATH = orig
        tmp.unlink(missing_ok=True)


chk("the old nested shape with a stored total is refused",
    _reject({"brand-hex": {"files": {"a.md": 1}, "total": 1}}), True)
chk("a non-object category is refused", _reject({"brand-hex": []}), True)
chk("a non-integer count is refused", _reject({"brand-hex": {"a.md": "many"}}), True)
chk("the current shape is accepted", _reject({"brand-hex": {"a.md": 1}}), False)
chk("the shared baseline holds ratcheted categories only",
    sorted(baseline), sorted(n for n, (_p, k, _w) in gate.CATEGORIES.items() if k == "ratcheted"))

print("\nattribution is protected, not eroded")
# The inverted assertion. Every other check here says "this must not grow"; this one says
# the credit must be PRESENT. A gate that only ever removes names would, taken to its
# conclusion, strip the authors out of their own project.
_authors = REPO / "AUTHORS.md"
chk("AUTHORS.md exists", _authors.is_file(), True)
_auth_text = _authors.read_text(encoding="utf-8") if _authors.is_file() else ""
for _role in ("product owner", "maintainer"):
    chk(f"AUTHORS.md credits the {_role}", _role in _auth_text, True)

print("\nthe attribution region is narrow, and not a hole")
_name_rx = re.compile(gate.CATEGORIES["local:person"][0])
_S, _E = gate.ATTRIBUTION_START, gate.ATTRIBUTION_END
_WHO = (_j("Zyx", "qorp One"), _j("Vuw", "tenk Two"))
_OUT1, _OUT2 = _j("zyx", "qorp"), _j("vuw", "tenk")
_sample = (f"{_OUT1} here\n{_S}\nBy {_WHO[0]} and {_WHO[1]}\n{_E}\n{_OUT2} there\n")
chk("names inside a closed region are not counted",
    len(_name_rx.findall(gate.strip_attribution(_sample))), 2)
chk("names outside the region are still counted",
    all(w in gate.strip_attribution(_sample) for w in (_OUT1, _OUT2)), True)
chk("line numbers survive stripping",
    gate.strip_attribution(_sample).count("\n"), _sample.count("\n"))
# A stray opening marker must not exempt the rest of the file.
chk("an unterminated region is NOT stripped",
    len(_name_rx.findall(gate.strip_attribution(f"x\n{_S}\n{_WHO[0]}\n"))), 1)
chk("only the two identity categories are exempt",
    sorted(gate.ATTRIBUTION_EXEMPT), ["local:org", "local:person"])
# A leak is still a leak inside an attribution block.
_leak = (f"{_S}\nby {_OUT2}, colour " + _j("#2F", "5D9E") + ", host "
         + _j("intra.qorp", ".example") + f"\n{_E}\n")
for _cat in ("brand-hex", "local:host"):
    chk(f"{_cat} is not exempt from attribution regions",
        _cat in gate.ATTRIBUTION_EXEMPT, False)
    chk(f"{_cat} matches inside a region, so scan() catches it there",
        bool(re.search(gate.CATEGORIES[_cat][0], _leak)), True)
chk("a name inside a region is gone from what local:person sees",
    _OUT2 in gate.strip_attribution(_leak), False)

print("\nthe attribution exemption is load-bearing (mutation, on a scratch tree)")
# scan() over a one-file tree whose only names sit inside a region: with stripping the
# person category is empty, with stripping disabled it is not. That proves the exemption
# is what keeps credit legal, rather than the credit happening to be absent.
_scratch = pathlib.Path(tempfile.mkdtemp(prefix="tun-core-attr-"))
(_scratch / "AUTHORS.md").write_text(f"# Authors\n{_S}\n{_WHO[0]}\n{_E}\n", encoding="utf-8")
_orig_repo, _orig_paths, _orig_strip = gate.tree_scan.REPO, gate.tree_scan.tracked_paths, gate.strip_attribution
try:
    gate.tree_scan.REPO = _scratch
    gate.tree_scan.tracked_paths = lambda *a, **k: ["AUTHORS.md"]
    chk("with the exemption, a credited name is not a finding",
        gate.total(gate.scan()["local:person"]), 0)
    gate.strip_attribution = lambda text: text
    chk("disabling the exemption makes the same name a finding",
        gate.total(gate.scan()["local:person"]), 1)
finally:
    gate.tree_scan.REPO, gate.tree_scan.tracked_paths, gate.strip_attribution = _orig_repo, _orig_paths, _orig_strip
chk("restored: the real scan is unchanged", gate.scan()["brand-hex"], current["brand-hex"])

print("\na copyright notice may name its holder in core (mutation, on a scratch tree)")
_scratch2 = pathlib.Path(tempfile.mkdtemp(prefix="tun-core-notice-"))
(_scratch2 / "x.py").write_text(f"# Copyright (C) 2026 {_WHO[0]}\nx = 1\n", encoding="utf-8")
(_scratch2 / "y.py").write_text(f"# Copyright (C) 2026 {_WHO[0]}\n# by {_WHO[0]}\n", encoding="utf-8")
_orig_notice = gate.strip_copyright_lines
try:
    gate.tree_scan.REPO = _scratch2
    gate.tree_scan.tracked_paths = lambda *a, **k: ["x.py", "y.py"]
    chk("the holder on the notice line is not a finding; the same name elsewhere is",
        gate.scan()["local:person"], {"y.py": 1})
    chk("only the person category is exempt", gate.NOTICE_EXEMPT, ("local:person",))
    gate.strip_copyright_lines = lambda text: text
    chk("disabling the exemption makes the notice a finding",
        gate.scan()["local:person"], {"x.py": 1, "y.py": 2})
finally:
    gate.tree_scan.REPO, gate.tree_scan.tracked_paths = _orig_repo, _orig_paths
    gate.strip_copyright_lines = _orig_notice

print("\n" + "-" * 66)
print(f"{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
