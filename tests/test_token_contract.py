#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
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
chk("there are 9 required slots", len(tok.REQUIRED_SLOTS), 9)
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
    _palettes.append("plugins/tun/tokens/palette.css")
    _palettes.append("plugins/tun/tokens/palette.css")
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
        token_providers = [p for p in tok.discover_plugins()
                           if "tokens" in (p.get("provides") or [])]
        if len(token_providers) > 1:
            # The real tree now has more than one plugin that can supply tokens
            # (eksempel and tun). The contract's own claim is that the automatic pick is
            # refused rather than resolved last-wins -- so that is exactly what this
            # asserts, instead of assuming there is only ever one plugin.
            provider_ids = sorted(str(p.get("id")) for p in token_providers)
            try:
                tok.palette_path(prefer_plugin=True)
                chk(f"prefer_plugin raises with {len(token_providers)} token "
                    f"providers ({', '.join(provider_ids)})", False, True)
            except SystemExit as exc:
                chk(f"prefer_plugin raises with {len(token_providers)} token "
                    f"providers ({', '.join(provider_ids)})", True, True)
                chk("the error names every provider",
                    all(pid in str(exc) for pid in provider_ids), True)
            # TUN_PALETTE is the side-by-side mechanism: explicit selection must
            # resolve correctly for EACH real token-providing plugin, not just
            # whichever one happens to sort first.
            for p in token_providers:
                pid = str(p.get("id"))
                palette_rel = (p.get("tokens") or {}).get("palette")
                plugin_palette = (p["_dir"] / palette_rel).resolve()
                os.environ["TUN_PALETTE"] = str(plugin_palette.relative_to(REPO))
                try:
                    sel_path, sel_source = tok.palette_path()
                    chk(f"TUN_PALETTE selects plugin {pid!r} explicitly",
                        sel_path.resolve(), plugin_palette)
                    chk(f"...and reports its source as TUN_PALETTE",
                        sel_source.startswith("TUN_PALETTE="), True)
                finally:
                    os.environ.pop("TUN_PALETTE", None)
        elif len(token_providers) == 1:
            plugin_path, plugin_source = tok.palette_path(prefer_plugin=True)
            chk("prefer_plugin resolves to the plugin that provides tokens",
                plugin_path.is_file() and "plugins/" in str(plugin_path), True)
            chk("and names the plugin", plugin_source.startswith("plugin:"), True)
        else:
            # Plugins exist but none declare tokens (e.g. an assets-only plugin).
            chk("prefer_plugin falls back to neutral when no plugin provides tokens",
                tok.palette_path(prefer_plugin=True)[1], "core:neutral")
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
    discovered_ids = {p.get("id") for p in found}
    # The brand plugin's id, composed: the export excludes that plugin, so an exported tree
    # must not carry its name as text either.
    # The public tree ships the fictional brand plugin, so that is the one to discover.
    _brand = "eksempel"
    chk(f"{_brand} and tun are both discovered", {_brand, "tun"}.issubset(discovered_ids), True)
    chk("the manifest is actually parsed, not just located",
        found[0].get("provides"), ["tokens", "assets", "tenant_facts"])
    chk("private is carried through", found[0].get("private"), True)
else:
    chk("no plugins discovered on a core-only tree", found, [])

print("\nassets: every file a manifest maps is a self-contained SVG")
# docs/22 says assets are inlined at build time and nothing is ever fetched. An SVG can
# fetch (an external href, a url() or @import to a host) and can run code (<script>, an
# on* handler, <foreignObject> HTML), so each of those is a reason to refuse the file.
import xml.etree.ElementTree as ET  # noqa: E402

SVG_NS = "{http://www.w3.org/2000/svg}"


def svg_problems(text: str) -> list[str]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return [f"not well-formed XML ({exc})"]
    problems = []
    if root.tag != SVG_NS + "svg":
        problems.append("root is not <svg> in the SVG namespace")
    if not root.get("viewBox"):
        problems.append("no viewBox")
    if root.get("role") != "img" or not root.get("aria-label"):
        problems.append("no role=img with an aria-label")
    if re.search(r"""url\((?!\s*['"]?#)|@import""", text):
        problems.append("fetches through url() or @import")
    for el in root.iter():
        local = el.tag.split("}")[-1]
        if local in ("script", "foreignObject"):
            problems.append(f"has <{local}>")
        # SMIL can rewrite an href after load, so the static href check alone misses it.
        if local in ("set", "animate") and el.get("attributeName", "").endswith("href"):
            problems.append(f"<{local}> rewrites href")
        for key, value in el.attrib.items():
            attr = key.split("}")[-1]
            if attr.lower().startswith("on"):
                problems.append(f"has event handler {attr}")
            if attr == "href" and not value.startswith("#"):
                problems.append(f"references {value}")
    return problems


GOOD_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1" role="img" '
            'aria-label="x"><rect width="1" height="1"/></svg>')
chk("a clean SVG has no problems", svg_problems(GOOD_SVG), [])
# Each bad case must trip exactly its own rule, alone. A fixture that trips a neighbouring
# rule would keep the suite green with the rule under test deleted.
for label, bad, want in (
    ("no SVG namespace", GOOD_SVG.replace(' xmlns="http://www.w3.org/2000/svg"', ""),
     "root is not <svg> in the SVG namespace"),
    ("no viewBox", GOOD_SVG.replace(' viewBox="0 0 1 1"', ""), "no viewBox"),
    ("no aria-label", GOOD_SVG.replace(' aria-label="x"', ""),
     "no role=img with an aria-label"),
    ("a remote url()", GOOD_SVG.replace("<rect", '<rect fill="url(https://e.x/a)"'),
     "fetches through url() or @import"),
    ("a script", GOOD_SVG.replace("<rect", "<script>1</script><rect"), "has <script>"),
    ("foreignObject", GOOD_SVG.replace("<rect", "<foreignObject/><rect"),
     "has <foreignObject>"),
    ("an onload handler", GOOD_SVG.replace("<rect", '<rect onload="x()"'),
     "has event handler onload"),
    ("an external href", GOOD_SVG.replace("<rect", '<image href="https://e.x/a.png"/><rect'),
     "references https://e.x/a.png"),
    ("a SMIL href rewrite",
     GOOD_SVG.replace("<rect", '<set attributeName="href" to="https://e.x/a"/><rect'),
     "<set> rewrites href"),
):
    chk(f"rejects {label}, and only for that", svg_problems(bad), [want])
chk("an internal #ref is allowed",
    svg_problems(GOOD_SVG.replace("<rect", '<use href="#a"/><rect')), [])
chk("a quoted internal url('#a') is allowed",
    svg_problems(GOOD_SVG.replace("<rect", "<rect fill=\"url('#a')\"")), [])

assets_checked = 0
for p in tok.discover_plugins():
    amap = p.get("assets")
    if amap is None:
        continue
    pid = p.get("id")
    chk(f"{pid}: an assets map means 'assets' is in provides",
        "assets" in (p.get("provides") or []), True)
    chk(f"{pid}: the assets map is name -> path",
        isinstance(amap, dict) and all(isinstance(v, str) for v in amap.values()), True)
    for name, rel_path in (amap.items() if isinstance(amap, dict) else ()):
        path = (p["_dir"] / rel_path).resolve()
        inside = p["_dir"].resolve() in path.parents
        chk(f"{pid}:{name} stays inside the plugin", inside, True)
        exists = path.is_file()
        chk(f"{pid}:{name} exists", exists, True)
        if inside and exists:
            chk(f"{pid}:{name} is a self-contained SVG",
                svg_problems(path.read_text(encoding="utf-8")), [])
            assets_checked += 1
print(f"  ({assets_checked} asset file(s) checked)")

# tenant_facts (docs/22, capability 5): declaring it and shipping the file go together, and
# the file must parse. A skill reads it (tun-publish, destination C), so a malformed or missing
# file would silently remove a classification ceiling from a publish decision.
facts_checked = 0
for p in tok.discover_plugins():
    pid, declared = p.get("id"), "tenant_facts" in (p.get("provides") or [])
    rel_facts = p.get("tenant_facts")
    chk(f"{pid}: 'tenant_facts' in provides exactly when a tenant_facts file is named",
        declared, rel_facts is not None)
    if not (declared and isinstance(rel_facts, str)):
        continue
    fpath = (p["_dir"] / rel_facts).resolve()
    chk(f"{pid}: tenant facts stay inside the plugin", p["_dir"].resolve() in fpath.parents, True)
    try:
        facts = json.loads(fpath.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        chk(f"{pid}: tenant facts parse as JSON", repr(e), "parsed")
        continue
    chk(f"{pid}: tenant facts carry the schema tag", facts.get("schema"), "tun.tenant-facts/v1")
    art = (facts.get("atlassian") or {}).get("artifacts")
    if art is not None:
        chk(f"{pid}: atlassian.artifacts states a classification ceiling",
            isinstance(art.get("classification_ceiling"), str) and len(art["classification_ceiling"]) > 20,
            True)
    facts_checked += 1
print(f"  ({facts_checked} tenant-facts file(s) checked)")
if HAVE_PLUGINS:
    chk("at least one installed plugin's tenant facts were checked", facts_checked >= 1, True)
if HAVE_PLUGINS:
    # Refuse a vacuous pass: the tun plugin ships three assets, so zero checked means the
    # loop above never ran, not that everything is fine.
    tun = next((p for p in found if p.get("id") == "tun"), {})
    chk("tun maps its logo, square mark and mono logo",
        sorted((tun.get("assets") or {}).keys()), ["logo", "logo-mono", "mark"])
    chk("at least those three asset files were checked", assets_checked >= 3, True)

    # mark.svg and logo-mono.svg are derived from logo.svg and stored. A stored derived
    # file must be re-derived by a check, or a hand edit desynchronises it in silence.
    import subprocess  # noqa: E402
    derive = REPO / "plugins" / "tun" / "assets" / "derive_marks.py"
    run = subprocess.run([sys.executable, str(derive), "--check"],
                         capture_output=True, text=True)
    chk("tun's derived marks match logo.svg (derive_marks.py --check)",
        run.returncode, 0)
    with tempfile.TemporaryDirectory() as td:
        copy = pathlib.Path(td)
        for f in derive.parent.glob("*.svg"):
            shutil.copy(f, copy / f.name)
        shutil.copy(derive, copy / derive.name)
        mark = copy / "mark.svg"
        mark.write_text(mark.read_text(encoding="utf-8").replace('x="80"', 'x="81"'),
                        encoding="utf-8")
        run = subprocess.run([sys.executable, str(copy / derive.name), "--check"],
                             capture_output=True, text=True)
        chk("...and --check notices a hand-edited mark", (run.returncode, "stale: mark.svg"
            in run.stdout), (1, True))

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
