#!/usr/bin/env python3
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

import pathlib
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

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
chk("plugins/ is outside core", gate.in_core("plugins/dnb/tokens/palette.css"), False)
chk("internal/ is outside core", gate.in_core("internal/ops.md"), False)
chk("the internal/ exclusion is narrow", gate.in_core("docs/internal-notes.md"), True)
chk("core files are inside core", gate.in_core("tools/tokens/theme-light.css"), True)
chk("binaries are skipped", gate.in_core("docs/assets/probe-local-render.png"), False)
# The baseline file lists every pattern it tracks, so scanning it would count its own contents.
chk("the baseline file excludes itself",
    gate.in_core("tools/core_generic_baseline.json"), False)
chk("the gate source excludes itself",
    gate.in_core("tools/check_core_is_generic.py"), False)

print("\nthe forbidden category is actually empty")
chk("logo artwork is absent from core", gate.total(current["logo-artwork"]), 0)

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
# Fixtures are ASSEMBLED AT RUNTIME. This gate scans core, and this file is core, so a
# literal fixture would register as a new file in every category -- and the artwork fragment
# would trip the forbidden category, which is exactly what happened on the first run. The
# alternative is exempting this file, and an exemption in a boundary gate is where the next
# leak lives. Same discipline as tests/test_no_real_data_gate.py.
def _j(*parts: str) -> str:
    return "".join(parts)


CASES = [
    ("logo-artwork", _j('d="M', "111.797", ' 39.9"'), True),
    ("logo-artwork", _j('d="M', "111.8", ' 39.9"'), False),
    ("brand-token", _j("var(--", "dnb", "-sea)"), True),
    ("brand-token", "var(--palette-primary)", False),
    ("brand-hex", _j("#00", "6C6C"), True),
    ("brand-hex", "#2B4C7E", False),
    ("internal-host", _j("nexus.tech.", "dnb", ".no"), True),
    ("internal-host", "example.com", False),
    ("internal-forge", _j("dnb", ".ghe.", "com"), True),
    ("atlassian-site", _j("acme-corp", ".atlassian", ".net/wiki"), True),
    ("atlassian-site", _j("https://", "example", ".atlassian", ".net"), False),
    ("atlassian-site", _j("ari:cloud:confluence:", "1234abcd-0000-4000-8000-", "00000000abcd", ":space/1"), True),
    ("atlassian-site", "ari:cloud:identity::user/<accountId>", False),
    ("org-name", _j("a ", "DN", "B laptop"), True),
    ("org-name", _j("dnb", "nor"), False),
    ("design-system", _j("Eufem", "ia tokens"), True),
    ("person-name", _j("Per ", "Harald"), True),
    ("person-name", "Per Hansen", False),
    ("internal-system", _j("INF", "A platform"), True),
]
for name, text, want in CASES:
    rx = re.compile(gate.CATEGORIES[name][0])
    chk(f"{name}: {text!r} fires={want}", bool(rx.search(text)), want)

print("\nthe gate can fail in all four directions (simulated against the real baseline)")


def verdict(scanned: dict) -> str:
    """Classify a scan the way the CLI does.

    This is a REIMPLEMENTATION, which is a real weakness: main() could drift from it and
    this suite would still pass. It exists because main() takes no scan argument, so the
    only way to test a hypothetical tree is to model the comparison. It is mitigated
    directly below, where the real main() is run against the real tree and its exit code
    is required to agree with this function's verdict. Divergence in the case that
    actually ships is therefore caught; divergence in the simulated cases is not, and
    that is the honest limit of this design.
    """
    for name, (_p, kind, _w) in gate.CATEGORIES.items():
        hits = scanned[name]
        got_total, got_files = gate.total(hits), set(hits)
        if kind == "forbidden":
            if got_total:
                return "forbidden-present"
            continue
        want = baseline.get(name, {})
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

# A scrubbed tree banks every category to zero, which is what a ratchet is for. The two
# counting verdicts therefore need a baseline that records a file, or every hit is classified
# as a new file and neither branch is exercised.
m = copy.deepcopy(current)
_f = "AGENTS.md"
m["org-name"] = {_f: 1}
_saved = baseline
baseline = {**baseline, "org-name": {_f: 0}}
chk("a ratchet rising is refused", verdict(m), "regression")
baseline = {**baseline, "org-name": {_f: 2}}
chk("a ratchet falling unbanked is refused", verdict(m), "unbanked-progress")
baseline = _saved

m = copy.deepcopy(current)
m["design-system"]["docs/zz-new.md"] = 1
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
    _reject({"org-name": {"files": {"a.md": 1}, "total": 1}}), True)
chk("a non-object category is refused", _reject({"org-name": []}), True)
chk("a non-integer count is refused", _reject({"org-name": {"a.md": "many"}}), True)
chk("the current shape is accepted", _reject({"org-name": {"a.md": 1}}), False)

print("\nattribution is protected, not eroded")
# The inverted assertion. Every other check here says "this must not grow"; this one says
# the credit must be PRESENT. A gate that only ever removes names would, taken to its
# conclusion, strip the authors out of their own project.
_authors = REPO / "AUTHORS.md"
chk("AUTHORS.md exists", _authors.is_file(), True)
_auth_text = _authors.read_text(encoding="utf-8") if _authors.is_file() else ""
_WHO = (_j("Tunk", "allen"), _j("Jon-", "Mikkel"))
# A name the gate forbids OUTSIDE an attribution region. Tunkallen is credited by
# design and is deliberately not one of them, so it cannot stand in for a leak.
_PERSON = _j("Jon-", "Mikkel")
for _who in _WHO:
    chk(f"AUTHORS.md names {_who}", _who in _auth_text, True)
_readme = (REPO / "README.md").read_text(encoding="utf-8")
chk("the README credits both authors", all(w in _readme for w in _WHO), True)

print("\nthe attribution region is narrow, and not a hole")
_name_rx = re.compile(gate.CATEGORIES["person-name"][0])
_S, _E = gate.ATTRIBUTION_START, gate.ATTRIBUTION_END
_OUT1, _OUT2 = _j("Kors", "vik"), _j("Pel", "le")
_sample = (f"{_OUT1} here\n{_S}\nBy {_WHO[0]} and {_WHO[1]}\n{_E}\n{_OUT2} there\n")
chk("names inside a closed region are not counted",
    len(_name_rx.findall(gate.strip_attribution(_sample))), 2)
chk("names outside the region are still counted",
    all(w in gate.strip_attribution(_sample) for w in (_OUT1, _OUT2)), True)
chk("line numbers survive stripping",
    gate.strip_attribution(_sample).count("\n"), _sample.count("\n"))
# A stray opening marker must not exempt the rest of the file. That would be a hole with
# a comment on it, and the comment would make it look reviewed.
chk("an unterminated region is NOT stripped",
    len(_name_rx.findall(gate.strip_attribution(f"x\n{_S}\n{_PERSON}\n"))), 1)
chk("only the two identity categories are exempt",
    sorted(gate.ATTRIBUTION_EXEMPT), ["org-name", "person-name"])
# A leak is still a leak inside an attribution block. scan() passes the ORIGINAL text for
# any category outside ATTRIBUTION_EXEMPT, so the assertion is that these categories are
# not exempt and their patterns match the raw region -- not that they survive stripping,
# which is a path scan() never takes for them.
_leak = (f"{_S}\nby {_OUT2}, colour " + _j("#00", "6C6C") + ", host "
         + _j("nexus.tech.", "dnb", ".no") + f"\n{_E}\n")
for _cat in ("brand-hex", "internal-host"):
    chk(f"{_cat} is not exempt from attribution regions",
        _cat in gate.ATTRIBUTION_EXEMPT, False)
    chk(f"{_cat} matches inside a region, so scan() catches it there",
        bool(re.search(gate.CATEGORIES[_cat][0], _leak)), True)
# And the identity categories really are exempt, which is the pair that makes the
# distinction meaningful rather than decorative.
chk("person-name IS exempt", "person-name" in gate.ATTRIBUTION_EXEMPT, True)
chk("a name inside a region is gone from what person-name sees",
    _OUT2 in gate.strip_attribution(_leak), False)

print("\nthe attribution exemption is load-bearing (mutation)")
# If stripping were disabled, the person-name count would rise above the banked baseline
# and the ratchet would fail. That proves the exemption is what keeps the credit legal,
# rather than the credit happening to fall below a threshold.
_orig_strip = gate.strip_attribution
try:
    gate.strip_attribution = lambda text: text
    _unstripped = gate.scan()
    chk("disabling the exemption makes person-name exceed the baseline",
        gate.total(_unstripped["person-name"]) > gate.total(baseline["person-name"]), True)
finally:
    gate.strip_attribution = _orig_strip
chk("restored: the scan matches the baseline again",
    gate.scan()["person-name"], baseline["person-name"])

print("\nthe two Claude Code manifests: one attribution value each, nothing else")
# Fixtures are assembled at runtime for the same reason as above. They are scanned as
# hypothetical files (scan_texts), so this block proves the same thing whether or not the real
# manifests are tracked yet.
import json  # noqa: E402

_FULL = _j("Jon-", "Mikkel Ryen Kors", "vik")
_PLUGIN, _MARKET = ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"


def _plugin(description="A plain description.", author=_FULL, keywords=("reporting",)) -> str:
    return json.dumps({"name": "x", "description": description,
                       "author": {"name": author}, "keywords": list(keywords)}, indent=2)


def _market(owner=_FULL, description="A plain description.") -> str:
    return json.dumps({"name": "x", "description": description, "owner": {"name": owner},
                       "plugins": [{"name": "x", "source": "./"}]}, indent=2)


_core = gate.read_core()


def _problems(**override) -> list[str]:
    texts = dict(_core)
    texts.update(override)
    return gate.problems_for(gate.scan_texts(texts), baseline)


def _esc(s: str) -> str:
    """A JSON string literal with every character written as a \\uXXXX escape."""
    return '"' + "".join("\\u%04x" % ord(c) for c in s) + '"'


def _doc(description: str = '"Plain"', author: str = "Example Team", tail: str = "") -> str:
    """Hand-built manifest text; `description` is an already-quoted JSON value."""
    return ('{"name":"x","author":{"name":"' + author + '"},"description":'
            + description + tail + "}")


_SHAPE = [f"manifest-shape: {_PLUGIN} is not plain JSON"]

# (a) the two manifests pass
chk("both real manifests are tracked, so the next check is not vacuous",
    (_PLUGIN in _core, _MARKET in _core), (True, True))
chk("the real tree, with both real manifests, has no problems", _problems(), [])
chk("both manifests with the owner name only: no problems",
    _problems(**{_PLUGIN: _plugin(), _MARKET: _market()}), [])
_escaped_author = _doc(author=_FULL).replace(_FULL, _esc(_FULL)[1:-1])
chk("the escaped fixture really differs from the raw name", _FULL in _escaped_author, False)
chk("an author written fully as \\u escapes is the exempt value too",
    _problems(**{_PLUGIN: _escaped_author}), [])

# (b) a name anywhere else in those files still counts, alone, with the exact message
_exact = f"person-name: 1 new file(s): {_PLUGIN}"
chk("a person name in plugin.json description fails with exactly one problem",
    _problems(**{_PLUGIN: _plugin(description=f"Made by {_WHO[1]}.")}), [_exact])
chk("a person name in plugin.json keywords fails the same way",
    _problems(**{_PLUGIN: _plugin(keywords=(_PERSON,))}), [_exact])
chk("a person name in marketplace.json description fails the same way",
    _problems(**{_MARKET: _market(description=_OUT1)}),
    [f"person-name: 1 new file(s): {_MARKET}"])
# The full name is two matches (first name, surname). Author field exempt, description not.
chk("the owner name repeated in the description still counts (2 matches, not 0)",
    gate.scan_texts({_PLUGIN: _plugin(description=_FULL)})["person-name"], {_PLUGIN: 2})
chk("an organisation in author.name still counts (only person-name is exempt)",
    _problems(**{_PLUGIN: _plugin(author=_j("DN", "B"))}),
    [f"org-name: 1 new file(s): {_PLUGIN}"])
chk("an exempt key path in the wrong file exempts nothing",
    gate.scan_texts({".claude-plugin/other.json": _plugin()})["person-name"],
    {".claude-plugin/other.json": 2})
chk("a non-string name is not exempt",
    gate.scan_texts({_PLUGIN: json.dumps({"author": {"name": [_FULL]}})})["person-name"],
    {_PLUGIN: 2})
chk("a name written as \\u escapes in the description of a clean manifest fails",
    _problems(**{_PLUGIN: _doc(description=_esc(_FULL))}), [_exact])
chk("the same in marketplace.json",
    _problems(**{_MARKET: _doc(description=_esc(_FULL)).replace('"author"', '"owner"')}),
    [f"person-name: 1 new file(s): {_MARKET}"])

# A declared manifest that does not parse as plain JSON is a problem of its own. Every case
# below hides an escaped name that a raw-text fallback would miss, and strict
# `claude plugin validate` accepts the duplicate and BOM variants.
_hidden = _esc(_FULL)
_dup = _doc(description='"Plain"', tail=',"description":' + _hidden)
_cases = {
    "a repeated key": _dup,
    "a repeated key at depth": _doc(author=_FULL).replace(
        '"name":"' + _FULL + '"}', '"name":"x","name":' + _hidden + "}"),
    "a repeated key inside a list": _doc(tail=',"l":[{"a":' + _hidden + ',"a":"b"}]'),
    "a leading BOM": "\ufeff" + _doc(description=_hidden),
    "trailing data": _doc(description=_hidden) + " {}",
    "nesting too deep": "[" * 1200 + _hidden + "]" * 1200,
    "NaN (Python json accepts it, JSON does not)": _doc(tail=',"k":[NaN]'),
    "Infinity": _doc(tail=',"k":Infinity'),
    "-Infinity": _doc(tail=',"k":-Infinity'),
}
for _label, _text in _cases.items():
    chk(f"{_label}: fails with exactly the manifest-shape message, and only that",
        _problems(**{_PLUGIN: _text}), _SHAPE)
# A truncated file also carries the literal name, so it fails twice. The shape message must
# still be there.
chk("invalid JSON: reported as manifest-shape",
    _SHAPE[0] in _problems(**{_PLUGIN: '{"author": {"name": "' + _FULL}), True)
chk("a repeated key in marketplace.json is reported for that file",
    _problems(**{_MARKET: _dup.replace('"author"', '"owner"')}),
    [f"manifest-shape: {_MARKET} is not plain JSON"])
chk("a file that is not a declared manifest is never reported as one",
    gate.scan_texts({"docs/x.json": "{not json"})["_shape"], {})
import contextlib as _ctx  # noqa: E402
import io as _io  # noqa: E402

_orig_read_core = gate.read_core
try:
    gate.read_core = lambda: {**_core, _PLUGIN: _dup}
    _buf = _io.StringIO()
    with _ctx.redirect_stdout(_buf):
        _rc = gate.main()
finally:
    gate.read_core = _orig_read_core
chk("main() exits 1 and prints the manifest-shape problem",
    (_rc, _SHAPE[0] in _buf.getvalue()), (1, True))

print("\nthe JSON exemption is load-bearing, and narrow (mutation)")
_orig_sub = gate.manifest_subjects
_orig_nodup = gate._no_duplicates


def _old_fallback(rel, text):
    """The previous behaviour: a manifest that will not parse is scanned as raw text."""
    try:
        return _orig_sub(rel, text)
    except gate.NotPlainJson:
        return None


try:
    gate.manifest_subjects = lambda rel, text: None
    chk("exemption removed: the owner name alone now fails (so the pass above was earned)",
        _problems(**{_PLUGIN: _plugin(), _MARKET: _market()}),
        [f"person-name: 2 new file(s): {_MARKET}, {_PLUGIN}"])
    gate.manifest_subjects = lambda rel, text: ("", "") if rel in gate.JSON_ATTRIBUTION else None
    chk("exemption widened to the whole file: the description check stops firing, so it "
        "is the check that would notice",
        _problems(**{_PLUGIN: _plugin(description=f"Made by {_WHO[1]}.")}) == [_exact], False)
    gate.manifest_subjects = _old_fallback
    for _label, _text in _cases.items():
        chk(f"raw fallback re-enabled: the '{_label}' test would notice",
            _problems(**{_PLUGIN: _text}) == _SHAPE, False)
    gate.manifest_subjects = _orig_sub
    gate._no_duplicates = lambda pairs: dict(pairs)
    chk("duplicate check removed: the repeated-key test would notice",
        _problems(**{_PLUGIN: _dup}) == _SHAPE, False)
finally:
    gate.manifest_subjects = _orig_sub
    gate._no_duplicates = _orig_nodup
chk("restored: a repeated key is refused again", _problems(**{_PLUGIN: _dup}), _SHAPE)
chk("restored: a description name fails again",
    _problems(**{_PLUGIN: _plugin(description=f"Made by {_WHO[1]}.")}), [_exact])

print("\nthe scan is memoised, and the memo cannot lie (ROADMAP C1)")

# The suite calls `scan_texts` once per check, each time with one file swapped. That was
# 34 whole-tree scans at 0.55 s of regex work each, and 23.7 s in the pre-commit hook.
# The count for a (category, text) pair is pure, so it is memoised on the subject itself.
# Three things have to hold, and the third is the one that makes the first two worth
# anything: a warm cache returns the same verdict, a mutated text gets its own count, and
# a scan really is faster the second time.
_core_now = gate.read_core()
_first = gate.scan_texts(_core_now)
t0 = time.monotonic()
_second = gate.scan_texts(_core_now)
_warm = time.monotonic() - t0
chk("a warm cache returns exactly the same counts", _second, _first)
_swapped = gate.scan_texts({**_core_now, _PLUGIN: _plugin(author="A Completely Different Author")})
chk("a mutated file is counted afresh, not served from the cache",
    _swapped["person-name"] == _first["person-name"], True)
t0 = time.monotonic()
gate._COUNTS.clear()
_cold = gate.scan_texts(_core_now)
_cold_s = time.monotonic() - t0
chk("the cold scan and the warm scan agree", _cold, _first)
chk("the warm scan is at least twice as fast as the cold one",
    _warm < _cold_s / 2, True)

print("\n" + "-" * 66)
print(f"{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
