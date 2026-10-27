#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
verify_process_diagram.py — prove a built process diagram renders, reads and behaves
correctly in real browsers, from file://, the way a recipient opens it.

    uv run --extra verify python tools/verify_process_diagram.py DIAGRAM.html --spec SPEC.process.txt
    uv run --extra verify python tools/verify_process_diagram.py DIAGRAM.html --spec SPEC --max-crossings 2
    uv run --extra verify python tools/verify_process_diagram.py DIAGRAM.html --spec SPEC --mutation-check

What it checks
--------------
Static, no browser (the generic core from tools/verify_standalone_core.py): no external
references, no unsubstituted {{TOKEN}}, a provenance block with the Origin Notice, no stray
"<script" text (row 25), no :target navigation (row 24), no sticky/fixed positioning
(row 26), size budget. Plus: the script never reads or writes the URL fragment and never
fetches, imports or starts a worker, because none of that works from file://.

The drawing, in Chromium, Firefox and WebKit, against what was actually rendered:
  * node and connection counts match the spec, id for id; so do the flagged steps
  * steps are numbered 1..N once each, and each card carries its node's number
  * no two node boxes overlap; every node's text sits inside its own outline
  * no connection runs through a box it does not start or end at, or along another
  * forward connections leave a bottom and enter a top; loops back (which the verifier
    works out from the spec, not from the file) leave a right side and enter a side
  * every connection ends in an arrowhead at its last point
  * branch labels sit on pills that cover no box, no other pill, and no other line
  * lane names sit inside their header
  * crossings are counted, and --max-crossings makes a ceiling of the count
  * no text on the page is under 12 px at natural size, in any panel

The interactive layer, in the same three engines:
  * a WAI-ARIA tablist of five tabs in order; arrow keys, Home and End move focus and
    selection; exactly one panel shows; every panel has its content
  * clicking a node, or Enter on a focused one, opens the detail panel for that node
  * hovering a node highlights exactly its own connections and dims the rest
  * a role chip keeps one lane and dims the others
  * the drawing starts fitted to its frame (never past natural size, never so small that
    text drops under 12 px); 100 %, zoom and fit change its size
  * "Vis i flyten" on a step card and on an improvement point switches to the flow and
    puts focus on the right node
  * print shows every panel and hides the controls
  * zero console errors, zero network requests

In seven windows (375x812 to 3440x1440), in each engine, against the spec: the page never
scrolls sideways; a phone starts on the step cards; the frame spans the window (so a
max-width cap on the page fails) and the drawing fills it, from the 12 px floor up to
FIT_CEILING times natural size, with no text under 12 px; where it fits readably every
lane is in view, and where it does not it pans in a frame no taller than the window and,
scrolled down, keeps every lane's name over its lane. One screenshot per width. The page carries the flow twice, lanes as columns
and lanes as rows; auto must show the one that fits the frame with the least scrolling
(the columns when none fits), and where it fits it fills at least 90 % of the frame or
stops at FIT_CEILING, with no step cut off.

The rows drawing, switched on by its button, gets every geometry check above in its own
frame (coordinates transposed), and its lane names while it pans sideways. Print gives
the columns, whichever drawing was on screen.

With JavaScript off (Chromium): all five panels show, one after the other, with their
content, and no control that needs the script is visible.

Expected counts come from parsing the spec, never from the HTML, so a diagram cannot
vouch for itself.

--mutation-check breaks copies of the file, in a temp directory, once per behaviour, and
requires each break to be caught by the check aimed at it. The real file is never edited,
so a killed run cannot leave a mutated artefact behind. Several mutations edit exact
lines of the template's script and CSS; when one of those lines changes, the mutation
check stops with "mutation anchor missing" and names it, so the anchor is updated here
instead of a mutation silently doing nothing.

Fails (exit 1) without Playwright rather than skipping the browser half: a verifier that
reports success without opening a browser is worse than one that reports nothing.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_process_diagram as bpd  # noqa: E402
import i18n  # noqa: E402
import verify_standalone_core as core  # noqa: E402
VIEWPORT = {"width": 1280, "height": 900}
TOL = 0.75          # rendering rounds; anything under a pixel is not a visible overlap
MIN_FONT_PX = 12
TAB_KEYS = ("tab_flow", "tab_steps", "tab_roles", "tab_flags", "tab_text")
TABS = tuple(i18n.load("process-diagram", "nb")[k] for k in TAB_KEYS)   # set per page by use_page_lang()
PANELS = ("panel-flyt", "panel-steg", "panel-roller", "panel-forbedring", "panel-tekst")
SETTLE_MS = 300     # the dimming has a 0.15 s transition

# Gathers the rendered geometry in SVG user units, so it compares directly with the
# path data. getBBox is local; the CTM chain maps it to the root.
COLLECT_JS = r"""
() => {
  const svg = document.querySelector('svg.pd.on');
  if (!svg) return null;
  const inv = svg.getScreenCTM().inverse();
  const box = (el) => {
    const b = el.getBBox();
    const m = inv.multiply(el.getScreenCTM());
    const p1 = new DOMPoint(b.x, b.y).matrixTransform(m);
    const p2 = new DOMPoint(b.x + b.width, b.y + b.height).matrixTransform(m);
    return [Math.min(p1.x, p2.x), Math.min(p1.y, p2.y), Math.max(p1.x, p2.x), Math.max(p1.y, p2.y)];
  };
  const pointsOf = (el) => {
    const m = inv.multiply(el.getScreenCTM());
    return Array.from(el.points).map(p => {
      const q = new DOMPoint(p.x, p.y).matrixTransform(m); return [q.x, q.y];
    });
  };
  const nodes = Array.from(svg.querySelectorAll('g.node')).map(g => {
    const shape = g.querySelector('.node-shape');
    const text = g.querySelector('.node-label');
    const num = g.querySelector('.step-no text');
    return {
      id: g.getAttribute('data-node'),
      kind: (g.getAttribute('class').match(/node-(start|step|decision|end)/) || [])[1] || null,
      flagged: g.classList.contains('flagged'),
      number: num ? num.textContent.trim() : null,
      lines: Array.from(g.querySelectorAll('.node-label tspan')).map(t => t.textContent.trim()),
      shape: shape ? box(shape) : null,
      polygon: shape && shape.tagName === 'polygon' ? pointsOf(shape) : null,
      rx: shape && shape.tagName === 'rect' ? parseFloat(shape.getAttribute('rx') || '0') : 0,
      text: text && text.textContent.trim() ? box(text) : null,
    };
  });
  const edges = Array.from(svg.querySelectorAll('g.edge')).map(g => {
    const path = g.querySelector('.edge-line');
    const arrow = g.querySelector('.edge-arrow');
    const label = g.querySelector('.edge-label');
    return {
      from: g.getAttribute('data-from'), to: g.getAttribute('data-to'),
      loop: g.hasAttribute('data-loop'),
      d: path ? path.getAttribute('d') : '',
      arrow: arrow ? arrow.getAttribute('d') : '',
      label: label ? box(label) : null,
      labelText: label ? label.textContent : null,
    };
  });
  const lanes = Array.from(svg.querySelectorAll('g.lane')).map(g => ({
    head: box(g.querySelector('.lane-head')), name: box(g.querySelector('.lane-name')),
  }));
  const ta = document.querySelector('#panel-tekst');
  const steps = ta ? Array.from(ta.querySelectorAll('li[data-node]')).map(li => ({
    id: li.getAttribute('data-node'), text: li.textContent.replace(/\s+/g, ' ').trim(),
  })) : [];
  const refs = ta ? Array.from(ta.querySelectorAll('[data-from][data-to]')).map(
    el => [el.getAttribute('data-from'), el.getAttribute('data-to')]) : [];
  const cards = Array.from(document.querySelectorAll('#panel-steg .step-card')).map(c => ({
    id: c.getAttribute('data-node'),
    number: (c.querySelector('.num') || {}).textContent || null,
    text: c.textContent.replace(/\s+/g, ' ').trim(),
  }));
  return {
    nodes, edges, lanes, steps, refs, cards,
    roleCards: document.querySelectorAll('#panel-roller .role-card').length,
    flagCards: Array.from(document.querySelectorAll('#panel-forbedring .flag-card')).map(
      c => c.getAttribute('data-node')),
    js: document.documentElement.classList.contains('js'),
  };
}
"""

# The smallest rendered font size per element that owns visible text. SVG sizes are in
# user units, so they are scaled by the drawing's current screen matrix.
FONTS_JS = r"""
() => {
  const out = [];
  document.querySelectorAll('body *').forEach(el => {
    if (!el.getClientRects().length) return;
    const own = Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
    if (!own) return;
    let px = parseFloat(getComputedStyle(el).fontSize);
    if (el instanceof SVGElement && el.getScreenCTM) {
      const m = el.getScreenCTM();
      if (m) px *= Math.hypot(m.a, m.b);
    }
    out.push([Math.round(px * 100) / 100, el.tagName.toLowerCase(), el.textContent.trim().slice(0, 30)]);
  });
  return out;
}
"""

STATE_JS = r"""
() => {
  const tabs = Array.from(document.querySelectorAll('[role=tablist] [role=tab]'));
  return {
    names: tabs.map(t => t.textContent.trim()),
    selected: tabs.map(t => t.getAttribute('aria-selected') === 'true'),
    tabindex: tabs.map(t => t.tabIndex),
    controls: tabs.map(t => t.getAttribute('aria-controls')),
    panels: tabs.map(t => {
      const p = document.getElementById(t.getAttribute('aria-controls'));
      return p ? {role: p.getAttribute('role'), labelledby: p.getAttribute('aria-labelledby'),
                  shown: p.getClientRects().length > 0, text: p.innerText.trim().length} : null;
    }),
    ids: tabs.map(t => t.id),
    active: document.activeElement ? document.activeElement.id : null,
  };
}
"""

# Which controls that need the script are visible: tabs, toolbar, detail panel, buttons.
CONTROLS_JS = r"""
() => ['.tabs', '.toolbar', '#detail', '.show-in-flow'].map(
  s => Array.from(document.querySelectorAll(s)).some(el => el.getClientRects().length > 0))
"""

VISIBLE_JS = r"""
(ids) => ids.map(id => {
  const el = document.getElementById(id);
  if (!el || !el.getClientRects().length) return null;
  return el.getBoundingClientRect().top;
})
"""


class Report:
    """Collects (check key, message) failures. The key names which check fired, so the
    mutation check can require the *intended* check to catch a break, not any check."""

    def __init__(self, quiet: bool = False) -> None:
        self.failures: list[tuple[str, str]] = []
        self.passed = 0
        self.quiet = quiet
        self.crossings: dict[str, int] = {}

    def say(self, text: str) -> None:
        if not self.quiet:
            print(text)

    def check(self, key: str, label: str, ok: bool, detail: str = "") -> None:
        if ok:
            self.passed += 1
            self.say(f"    ✓ {label}")
        else:
            self.failures.append((key, f"{label}: {detail}" if detail else label))
            self.say(f"    ✗ {label}" + (f": {detail}" if detail else ""))


# --------------------------------------------------------------------------- geometry
def norm(text: str) -> str:
    """Collapse whitespace, the way innerText and the spec's labels are compared."""
    return " ".join(text.split())


def overlap(a, b, tol: float = TOL) -> bool:
    return a[0] < b[2] - tol and b[0] < a[2] - tol and a[1] < b[3] - tol and b[1] < a[3] - tol


def parse_path(d: str) -> list[tuple[float, float]] | None:
    """The corners of a path made of M, L and Q commands, the only shape the builder
    writes. A Q's control point is the original corner and its end lies on the next
    stretch, so reading every coordinate pair in order gives a right-angled polyline;
    collinear points are then merged. Anything else is a path this verifier cannot reason
    about, which is a failure, not a pass."""
    if not re.fullmatch(r"\s*M[\d.\s-]+((L|Q)[\d.\s-]+)*", d or ""):
        return None
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", d)]
    if len(nums) % 2 or len(nums) < 4:
        return None
    pts = list(zip(nums[0::2], nums[1::2]))
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) < 1e-6 and abs(p[1] - out[-1][1]) < 1e-6:
            continue
        if len(out) >= 2:
            (ax, ay), (bx, by) = out[-2], out[-1]
            if (abs(ax - bx) < TOL and abs(bx - p[0]) < TOL) or (abs(ay - by) < TOL and abs(by - p[1]) < TOL):
                out[-1] = p
                continue
        out.append(p)
    return out


def point_in_polygon(x: float, y: float, poly: list) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def inside_shape(n: dict, x: float, y: float) -> bool:
    if n["polygon"]:
        return point_in_polygon(x, y, n["polygon"])
    s = n["shape"]
    return s[0] < x < s[2] and s[1] < y < s[3]


def text_inside(n: dict) -> bool:
    t, s = n["text"], n["shape"]
    if n["polygon"]:
        return all(point_in_polygon(x, y, n["polygon"])
                   for x in (t[0] + 0.5, t[2] - 0.5) for y in (t[1] + 0.5, t[3] - 0.5))
    inset = n["rx"] * (1 - 2 ** -0.5)   # a rounded corner's inner square
    return (t[0] >= s[0] + inset - TOL and t[2] <= s[2] - inset + TOL
            and t[1] >= s[1] + inset - TOL and t[3] <= s[3] - inset + TOL)


def seg_through(seg, rect) -> bool:
    """A zero-width segment passing through a rectangle's interior (shrunk by TOL)."""
    x1, y1, x2, y2 = seg
    return x1 < rect[2] - TOL and x2 > rect[0] + TOL and y1 < rect[3] - TOL and y2 > rect[1] + TOL


def collinear_overlap(a, b) -> bool:
    if abs(a[1] - a[3]) < TOL and abs(b[1] - b[3]) < TOL and abs(a[1] - b[1]) < 2:
        return a[0] < b[2] - TOL and b[0] < a[2] - TOL
    if abs(a[0] - a[2]) < TOL and abs(b[0] - b[2]) < TOL and abs(a[0] - b[0]) < 2:
        return a[1] < b[3] - TOL and b[1] < a[3] - TOL
    return False


def seg_cross(a, b) -> bool:
    """A horizontal and a vertical segment crossing strictly inside both."""
    ah, bh = abs(a[1] - a[3]) < TOL, abs(b[1] - b[3]) < TOL
    if ah == bh:
        return False
    h, v = (a, b) if ah else (b, a)
    return h[0] + TOL < v[0] < h[2] - TOL and v[1] + TOL < h[1] < v[3] - TOL


def to_segs(pts: list) -> list:
    return [(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            for (x1, y1), (x2, y2) in zip(pts, pts[1:])]


def geometry_checks(r: Report, data: dict, spec: bpd.Spec, tag: str, max_crossings: int | None) -> None:
    nodes, edges = data["nodes"], data["edges"]
    spec_ids = {n.id for n in spec.nodes}
    spec_edges = {(e.src, e.dst) for e in spec.edges}
    _layer, back = bpd.assign_layers(spec)
    loops = {(e.src, e.dst) for e in spec.edges if e.order in back}
    r.check("count-nodes", f"[{tag}] {len(spec.nodes)} nodes drawn",
            len(nodes) == len(spec.nodes), f"found {len(nodes)}")
    r.check("count-nodes", f"[{tag}] node ids match the spec",
            {n["id"] for n in nodes} == spec_ids,
            f"missing {sorted(spec_ids - {n['id'] for n in nodes})}, "
            f"extra {sorted({n['id'] for n in nodes} - spec_ids)}")
    r.check("count-nodes", f"[{tag}] node kinds match the spec",
            all(n["kind"] == spec.node(n["id"]).kind for n in nodes if n["id"] in spec_ids))
    r.check("count-edges", f"[{tag}] {len(spec.edges)} connections drawn",
            len(edges) == len(spec.edges), f"found {len(edges)}")
    r.check("count-edges", f"[{tag}] connections match the spec",
            {(e["from"], e["to"]) for e in edges} == spec_edges)
    r.check("loops", f"[{tag}] the {len(loops)} loops back in the spec are drawn as loops",
            {(e["from"], e["to"]) for e in edges if e["loop"]} == loops,
            f"drawn {sorted((e['from'], e['to']) for e in edges if e['loop'])}")
    want_flags = {n.id for n in spec.nodes if n.improve}
    r.check("flags", f"[{tag}] {len(want_flags)} flagged steps drawn and listed",
            {n["id"] for n in nodes if n["flagged"]} == want_flags
            and set(data["flagCards"]) == want_flags and len(data["flagCards"]) == len(want_flags),
            f"drawn {sorted(n['id'] for n in nodes if n['flagged'])}, listed {data['flagCards']}")
    numbers = sorted(n["number"] or "" for n in nodes)
    card_num = {c["id"]: (c["number"] or "").strip() for c in data["cards"]}
    r.check("numbers", f"[{tag}] steps numbered 1..{len(spec.nodes)}, the same on every card",
            numbers == sorted(str(i) for i in range(1, len(spec.nodes) + 1))
            and all(card_num.get(n["id"]) == n["number"] for n in nodes),
            f"numbers {numbers}")

    shapes = {n["id"]: n["shape"] for n in nodes if n["shape"]}
    by_id = {n["id"]: n for n in nodes}
    clashes = [(a, b) for i, a in enumerate(shapes) for b in list(shapes)[i + 1:]
               if overlap(shapes[a], shapes[b])]
    r.check("overlap", f"[{tag}] no two node boxes overlap ({len(shapes)} boxes)", not clashes,
            f"{clashes[:3]}")
    cut = [n["id"] for n in nodes if n["id"] in spec_ids
           and not breaks_only_between_words(spec.node(n["id"]).label, n.get("lines") or [])]
    r.check("words", f"[{tag}] every label breaks between words, never inside one", not cut,
            f"cut inside a word: {cut[:4]}")
    clipped = [n["id"] for n in nodes if not n["text"] or not n["shape"] or not text_inside(n)]
    r.check("text", f"[{tag}] every node label sits inside its outline", not clipped,
            f"outside or missing: {clipped}")

    bad_paths, through, ends, collinear, arrows = [], [], [], [], []
    segs_by_edge = []
    for e in edges:
        pts = parse_path(e["d"])
        name = f"{e['from']}->{e['to']}"
        if not pts or len(pts) < 2 or any(abs(x1 - x2) > TOL and abs(y1 - y2) > TOL
                                          for (x1, y1), (x2, y2) in zip(pts, pts[1:])):
            bad_paths.append(name)
            continue
        src, dst = by_id.get(e["from"]), by_id.get(e["to"])
        if not src or not dst or not src["shape"] or not dst["shape"]:
            ends.append(name)
            continue
        (x0, y0), (x1, y1) = pts[0], pts[1]
        (x8, y8), (x9, y9) = pts[-2], pts[-1]
        if (e["from"], e["to"]) in loops:
            leaves = inside_shape(src, x0 - 2, y0) and not inside_shape(src, x0 + 2, y0) and x1 > x0
            enters = ((inside_shape(dst, x9 - 2, y9) and not inside_shape(dst, x9 + 2, y9) and x8 > x9)
                      or (inside_shape(dst, x9 + 2, y9) and not inside_shape(dst, x9 - 2, y9) and x8 < x9))
            where = ("right side", "side")
        else:
            leaves = inside_shape(src, x0, y0 - 2) and not inside_shape(src, x0, y0 + 2) and y1 > y0
            enters = inside_shape(dst, x9, y9 + 2) and not inside_shape(dst, x9, y9 - 2) and y8 < y9
            where = ("bottom", "top")
        if not leaves:
            ends.append(f"{name} (does not leave the {where[0]})")
        if not enters:
            ends.append(f"{name} (does not enter the {where[1]})")
        tip = parse_path(e["arrow"].replace("Z", "").replace("z", "")) if e["arrow"] else None
        if not tip or abs(tip[0][0] - x9) > 1 or abs(tip[0][1] - y9) > 1:
            arrows.append(name)
        segs = to_segs(pts)
        for i, seg in enumerate(segs):
            for nid, s in shapes.items():
                if (i == 0 and nid == e["from"]) or (i == len(segs) - 1 and nid == e["to"]):
                    continue
                if seg_through(seg, s):
                    through.append(f"{name} through {nid}")
        segs_by_edge.append((name, segs, e))
    crossings = 0
    for i, (na, sa, _ea) in enumerate(segs_by_edge):
        for nb, sb, _eb in segs_by_edge[i + 1:]:
            if any(collinear_overlap(a, b) for a in sa for b in sb):
                collinear.append(f"{na} / {nb}")
            crossings += sum(1 for a in sa for b in sb if seg_cross(a, b))
    r.crossings[tag] = crossings
    r.check("paths", f"[{tag}] every connection is a right-angled line", not bad_paths, f"{bad_paths}")
    r.check("ends", f"[{tag}] forward lines leave a bottom and enter a top, loops leave a right side and enter a side",
            not ends, f"{ends[:4]}")
    r.check("arrows", f"[{tag}] every connection ends in an arrowhead", not arrows, f"{arrows}")
    r.check("through", f"[{tag}] no connection runs through another box", not through,
            f"{through[:3]}")
    r.check("collinear", f"[{tag}] no two connections run along each other", not collinear,
            f"{collinear[:3]}")
    if max_crossings is not None:
        r.check("crossings", f"[{tag}] {crossings} crossings, ceiling {max_crossings}",
                crossings <= max_crossings, f"{crossings} > {max_crossings}")
    else:
        r.say(f"    · {crossings} crossings (no ceiling given)")

    labels = [(e["labelText"], e["label"], f"{e['from']}->{e['to']}") for e in edges if e["label"]]
    want_labels = sum(1 for e in spec.edges if e.label)
    r.check("labels", f"[{tag}] {want_labels} branch labels drawn", len(labels) == want_labels,
            f"found {len(labels)}")
    on_box = [t for t, b, _ in labels for s in shapes.values() if overlap(b, s)]
    on_label = [(a[0], b[0]) for i, a in enumerate(labels) for b in labels[i + 1:]
                if overlap(a[1], b[1])]
    crossed = [t for t, b, own in labels for name, segs, _ in segs_by_edge if name != own
               for seg in segs if seg_through(seg, b)]
    r.check("labels", f"[{tag}] branch label pills cover no box, no other pill and no line",
            not on_box and not on_label and not crossed,
            f"on boxes {on_box}, on pills {on_label}, crossed {crossed[:3]}")
    lane_bad = [i for i, ln in enumerate(data["lanes"])
                if not (ln["name"][0] >= ln["head"][0] - TOL and ln["name"][2] <= ln["head"][2] + TOL
                        and ln["name"][1] >= ln["head"][1] - TOL and ln["name"][3] <= ln["head"][3] + TOL)]
    r.check("lanes", f"[{tag}] {len(spec.lanes)} lanes, every name inside its header",
            len(data["lanes"]) == len(spec.lanes) and not lane_bad, f"lanes {lane_bad}")


def content_checks(r: Report, data: dict, spec: bpd.Spec, tag: str) -> None:
    """What every panel must hold, from the spec: a card per step, per role and per flag,
    and a text version with every step and connection."""
    listed = {s["id"]: s["text"] for s in data["steps"]}
    missing = [n.id for n in spec.nodes if n.id not in listed]
    wrong = [n.id for n in spec.nodes
             if n.id in listed and norm(n.label) not in listed[n.id]]
    r.check("textalt", f"[{tag}] text version lists all {len(spec.nodes)} steps",
            not missing and not wrong and len(data["steps"]) == len(spec.nodes),
            f"missing {missing}, label absent for {wrong}, items {len(data['steps'])}")
    refs = {tuple(x) for x in data["refs"]}
    r.check("textalt", f"[{tag}] text version names all {len(spec.edges)} connections",
            refs == {(e.src, e.dst) for e in spec.edges} and len(data["refs"]) == len(spec.edges),
            f"found {len(data['refs'])}")
    cards = {c["id"]: c["text"] for c in data["cards"]}

    def facts_of(n: bpd.Node) -> list:
        imp = n.improve
        return [n.label, *n.fields.values(),
                *([imp.text, imp.problem, imp.proposal] if imp else [])]

    bad_cards = [n.id for n in spec.nodes if n.id not in cards
                 or any(norm(v) not in cards[n.id] for v in facts_of(n) if v)]
    r.check("panels", f"[{tag}] «Steg» has a card per step, with every field and improvement from the spec",
            not bad_cards and len(data["cards"]) == len(spec.nodes),
            f"wrong or missing {bad_cards}, cards {len(data['cards'])}")
    r.check("panels", f"[{tag}] «Roller» has a card per role",
            data["roleCards"] == len(spec.lanes), f"found {data['roleCards']}")


# --------------------------------------------------------------------------- behaviour
def tab_checks(r: Report, page, tag: str) -> None:
    st = page.evaluate(STATE_JS)
    r.check("tabs", f"[{tag}] a tablist of {len(TABS)} tabs in order", tuple(st["names"]) == TABS,
            f"found {st['names']}")
    if tuple(st["names"]) != TABS:
        return
    r.check("tabs", f"[{tag}] every tab controls a tabpanel labelled by it",
            all(p and p["role"] == "tabpanel" and p["labelledby"] == st["ids"][i]
                for i, p in enumerate(st["panels"])) and tuple(st["controls"]) == PANELS,
            f"{st['panels']}")

    def one_selected(i: int) -> bool:
        s = page.evaluate(STATE_JS)
        return (s["selected"] == [k == i for k in range(len(TABS))]
                and [p["shown"] for p in s["panels"]] == [k == i for k in range(len(TABS))]
                and s["tabindex"] == [0 if k == i else -1 for k in range(len(TABS))]
                and s["active"] in (s["ids"][i], None, ""))

    r.check("tabs", f"[{tag}] starts on «Flyt», one panel shown, roving tabindex", one_selected(0))
    page.focus("#tab-flyt")
    moves = []
    for key, want in (("ArrowRight", 1), ("ArrowRight", 2), ("End", 4), ("ArrowRight", 0),
                      ("ArrowLeft", 4), ("Home", 0)):
        page.keyboard.press(key)
        s = page.evaluate(STATE_JS)
        if not (one_selected(want) and s["active"] == s["ids"][want]):
            moves.append(f"{key} -> wanted {TABS[want]}, selected {s['selected']}, focus {s['active']}")
    r.check("tabs", f"[{tag}] arrow keys, Home and End move focus and selection", not moves,
            f"{moves[:2]}")
    empty = []
    for i, tab_id in enumerate(st["ids"]):
        page.click(f"#{tab_id}")
        s = page.evaluate(STATE_JS)
        if not one_selected(i) or s["panels"][i]["text"] < 20:
            empty.append(TABS[i])
    r.check("panels", f"[{tag}] clicking each tab shows its panel, and none is empty", not empty,
            f"{empty}")
    page.click("#tab-flyt")


def font_checks(r: Report, page, tag: str) -> None:
    small = []
    for tab_id in ("tab-flyt", "tab-steg", "tab-roller", "tab-forbedring", "tab-tekst"):
        page.click(f"#{tab_id}")
        small += [f for f in page.evaluate(FONTS_JS) if f[0] < MIN_FONT_PX - 0.01]
    page.click("#tab-flyt")
    r.check("type", f"[{tag}] no text under {MIN_FONT_PX} px in any panel", not small, f"{small[:3]}")


def node(page, node_id: str):
    return page.locator(f'svg.pd.on g.node[data-node="{node_id}"]')


def detail_of(page) -> tuple:
    return page.evaluate("""() => { const d = document.getElementById('detail');
        return [d && !d.hidden && d.getClientRects().length > 0, d ? d.getAttribute('data-node') : null,
                d ? d.innerText.replace(/\\s+/g, ' ') : '']; }""")


def detail_checks(r: Report, page, spec: bpd.Spec, tag: str) -> None:
    a, b = spec.nodes[len(spec.nodes) // 2], spec.nodes[-2]
    node(page, a.id).click()
    shown, which, text = detail_of(page)
    r.check("detail", f"[{tag}] clicking «{a.label}» opens its details",
            shown and which == a.id and norm(a.label) in text, f"shown {shown}, node {which}")
    node(page, b.id).focus()
    page.keyboard.press("Enter")
    shown, which, text = detail_of(page)
    r.check("detail", f"[{tag}] Enter on a focused node opens its details",
            shown and which == b.id and norm(b.label) in text, f"shown {shown}, node {which}")
    page.keyboard.press("Escape")
    shown, _, _ = detail_of(page)
    focused = page.evaluate("() => document.activeElement && document.activeElement.getAttribute('data-node')")
    r.check("detail", f"[{tag}] Escape closes the details and keeps focus on the node",
            not shown and focused == b.id, f"shown {shown}, focus {focused}")


def opacity_of(page) -> dict:
    """Computed opacity and highlight state of every node and connection, after the
    0.15 s dimming transition has finished."""
    page.wait_for_timeout(SETTLE_MS)
    return page.evaluate("""() => Object.fromEntries(
        Array.from(document.querySelectorAll('svg.pd.on g.node, svg.pd.on g.edge')).map(g => [
          g.classList.contains('node') ? 'n:' + g.getAttribute('data-node')
            : 'e:' + g.getAttribute('data-from') + '->' + g.getAttribute('data-to'),
          [parseFloat(getComputedStyle(g).opacity), g.classList.contains('hl')]]))""")


def highlight_checks(r: Report, page, spec: bpd.Spec, tag: str) -> None:
    target = next((n for n in spec.nodes if sum(1 for e in spec.edges if n.id in (e.src, e.dst)) >= 2),
                  spec.nodes[0])
    mine = {f"e:{e.src}->{e.dst}" for e in spec.edges if target.id in (e.src, e.dst)}
    node(page, target.id).hover()
    op = opacity_of(page)
    lit = {k for k, (_o, hl) in op.items() if hl and k.startswith("e:")}
    dim_ok = all(o < 0.5 for k, (o, _h) in op.items() if k.startswith("n:") and k != f"n:{target.id}")
    r.check("highlight", f"[{tag}] hovering «{target.label}» lights its {len(mine)} connections and dims the rest",
            lit == mine and op[f"n:{target.id}"][0] > 0.99 and dim_ok, f"lit {sorted(lit)}")
    page.mouse.move(2, 2)
    r.check("highlight", f"[{tag}] moving away restores every node",
            all(o > 0.99 for o, _h in opacity_of(page).values()))


def filter_checks(r: Report, page, spec: bpd.Spec, tag: str) -> None:
    if len(spec.lanes) < 2:
        # One lane leaves nothing to dim, so any filter would "pass". Say so, count nothing.
        r.say(f"    · [{tag}] role filter not checked: one lane, nothing to dim")
        return
    lane = 1
    page.click(f'.chip[data-lane="{lane}"]')
    op = opacity_of(page)
    wrong = [n.id for n in spec.nodes
             if (op[f"n:{n.id}"][0] > 0.99) != (n.lane == lane)]
    r.check("filter", f"[{tag}] the «{spec.lanes[lane]}» chip keeps that lane and dims the others",
            not wrong, f"wrong {wrong}")
    page.click('.chip[data-lane=""]')
    r.check("filter", f"[{tag}] «Alle roller» brings every lane back",
            all(o > 0.99 for o, _h in opacity_of(page).values()))


def zoom_checks(r: Report, page, tag: str) -> None:
    nat = page.evaluate("() => parseFloat(document.querySelector('svg.pd.on').getAttribute('width'))")
    width = lambda: page.evaluate("() => document.querySelector('svg.pd.on').getBoundingClientRect().width")  # noqa: E731
    fig = page.evaluate("() => document.querySelector('.figure').clientWidth")
    w0 = width()
    page.click("#zoom-reset")
    w1 = width()
    page.click("#zoom-in")
    w2 = width()
    page.click("#fit")
    w3 = width()
    page.click("#zoom-reset")
    w4 = width()
    r.check("zoom", f"[{tag}] the drawing starts fitted, and 100 %, zoom in and fit change its size",
            abs(w0 - expected_width(nat, fig)) < 2 and abs(w1 - nat) < 1 and abs(w2 - nat * 1.25) < 1
            and abs(w3 - fig) < 2 and abs(w4 - nat) < 1,
            f"natural {nat}, start {w0} (want {expected_width(nat, fig):.1f}), 100 % {w1}, "
            f"zoomed {w2}, fit {w3} (figure {fig}), reset {w4}")


FILL = 0.9            # where the drawing fits, it fills this much of its frame, or stops at the ceiling


def start_scale(d: dict, frame: float, room: float) -> float:
    """The scale auto starts a drawing at: the frame's width within its CSS range, and for
    rows no taller than the window below the frame's top (room). 0 when that would put
    text under the floor: it does not fit. Written from the template's startScale()."""
    k = min(frame, d["max"]) / d["w"]
    if d["orient"] == "lr":
        k = min(k, room / d["h"])
    return k if k * d["w"] >= d["min"] - 1 else 0


def expected_orient(drawings: list, frame: float, room: float) -> str:
    """The drawing auto must show: of those that fit, the one that needs the least
    scrolling down; with none, the first (columns)."""
    best, best_h = None, float("inf")
    for d in drawings:
        k = start_scale(d, frame, room)
        if k and d["h"] * k < best_h - 1:
            best, best_h = d, d["h"] * k
    return (best or drawings[0])["orient"]


def breaks_only_between_words(label: str, lines: list) -> bool:
    """The lines put back together give the label, and every break is at a space or just
    after a "/" or "-" the label has: no word is cut, and no hyphen is added."""
    rebuilt = lines[0] if lines else ""
    for ln in lines[1:]:
        if rebuilt.endswith(("/", "-")) and label.startswith(rebuilt + ln):
            rebuilt += ln
        else:
            rebuilt += " " + ln
    return rebuilt == " ".join(label.split())


def transpose(data: dict) -> dict:
    """A rows drawing seen in its own frame (flow down, lanes across), so every geometry
    check written for columns applies unchanged: x and y swap everywhere."""
    def box(b):
        return [b[1], b[0], b[3], b[2]] if b else b

    def path(d):
        toks = re.findall(r"[A-Za-z]|-?\d+(?:\.\d+)?", d or "")
        nums = [t for t in toks if not t.isalpha()]
        if len(nums) % 2:
            return d
        swapped = iter(nums[i ^ 1] for i in range(len(nums)))
        return " ".join(t if t.isalpha() else next(swapped) for t in toks)
    out = dict(data)
    out["nodes"] = [dict(n, shape=box(n["shape"]), text=box(n["text"]),
                         polygon=[[y, x] for x, y in n["polygon"]] if n["polygon"] else None)
                    for n in data["nodes"]]
    out["edges"] = [dict(e, d=path(e["d"]), arrow=path(e["arrow"]), label=box(e["label"]))
                    for e in data["edges"]]
    out["lanes"] = [dict(ln, head=box(ln["head"]), name=box(ln["name"])) for ln in data["lanes"]]
    return out


def rows_checks(r: Report, page, spec: bpd.Spec, tag: str, max_crossings: int | None) -> None:
    """The rows drawing, switched on by its button: the same geometry checks as the
    columns, in its own frame, and the lane names while it pans sideways."""
    button = page.locator('#orient button[data-orient="lr"]')
    if not button.is_visible():
        r.check("rows", f"[{tag}] the page offers the rows drawing", False, "no rows button")
        return
    button.click()
    page.wait_for_timeout(100)
    data = page.evaluate(COLLECT_JS)
    shown = page.evaluate("() => Array.from(document.querySelectorAll('svg.pd')).filter("
                          "d => d.getClientRects().length).map(d => d.getAttribute('data-orient'))")
    r.check("rows", f"[{tag}] «rows» shows the rows drawing, and only that", shown == ["lr"], f"{shown}")
    if data:
        geometry_checks(r, transpose(data), spec, tag, max_crossings)
    pans = page.evaluate("() => document.querySelector('.figure-wrap').classList.contains('pan')")
    if pans:
        st = page.evaluate(STRIP_JS)
        over = all(abs(a - h[0]) < 2 and abs(b - h[1]) < 2 for (_n, a, b, _px), h in zip(st["names"], st["heads"]))
        r.check("rows", f"[{tag}] scrolled sideways, the lane names stay beside their lanes",
                st["shown"] and st["rows"] and over
                and [n for n, *_x in st["names"]] == [norm(x) for x in spec.lanes],
                f"shown {st['shown']}, beside lanes {over}")
        page.evaluate("() => { const f = document.querySelector('.figure'); f.scrollTop = 0; f.scrollLeft = 0; }")
    page.click('#orient button[data-orient="auto"]')
    page.wait_for_timeout(50)


def expected_width(nat: float, frame: float) -> float:
    """What the page must draw before the reader zooms: the frame's width, but never past
    FIT_CEILING times natural size and never below the size where the smallest text is
    MIN_FONT_PX."""
    return max(min(frame, nat * bpd.FIT_CEILING), nat * bpd.FIT_FLOOR)


def crosslink_checks(r: Report, page, spec: bpd.Spec, tag: str) -> None:
    sources = [("#tab-steg", f'#panel-steg .show-in-flow[data-node="{spec.nodes[-1].id}"]',
                spec.nodes[-1].id, "a step card")]
    flagged = [n for n in spec.nodes if n.improve]
    if flagged:
        sources.append(("#tab-forbedring", f'#panel-forbedring .show-in-flow[data-node="{flagged[-1].id}"]',
                        flagged[-1].id, "an improvement point"))
    for tab, button, want, what in sources:
        page.click(tab)
        page.click(button)
        page.wait_for_timeout(100)
        st = page.evaluate(STATE_JS)
        focused = page.evaluate("() => document.activeElement && document.activeElement.getAttribute('data-node')")
        shown, which, _ = detail_of(page)
        r.check("crosslink", f"[{tag}] «Vis i flyten» on {what} lands on «{spec.node(want).label}»",
                st["selected"][0] and focused == want and shown and which == want,
                f"flow selected {st['selected'][0]}, focus {focused}, detail {which}")
    page.click("#detail-close")
    page.click("#tab-flyt")


# In print the frame holds the whole drawing and the panning aids are gone, even when the
# page was panning (scrolled down, lane names shown) the moment the reader printed.
PRINT_FRAME_JS = r"""
() => {
  const fig = document.querySelector('.figure'), svg = document.querySelector('svg.pd-tb');
  const strip = document.getElementById('lane-strip');
  const rows = document.querySelector('svg.pd-lr');
  return [fig.getBoundingClientRect().height >= svg.getBoundingClientRect().height - 1,
          strip.getClientRects().length > 0,
          svg.getClientRects().length > 0 && !(rows && rows.getClientRects().length > 0)];
}
"""


def print_checks(r: Report, page, tag: str) -> None:
    rows = page.locator('#orient button[data-orient="lr"]')
    if rows.is_visible():
        rows.click()             # print must give the columns, whichever drawing shows
    page.evaluate(STRIP_JS)      # if the drawing pans, scroll it so the lane names show
    page.click("#tab-roller")    # leave a non-first tab open: print must still show all
    page.emulate_media(media="print")
    tops = page.evaluate(VISIBLE_JS, list(PANELS))
    controls = page.evaluate(CONTROLS_JS)
    whole, strip, columns = page.evaluate(PRINT_FRAME_JS)
    page.emulate_media(media="screen")
    page.click("#tab-flyt")
    if rows.is_visible():
        page.click('#orient button[data-orient="auto"]')
    page.evaluate("() => { const f = document.querySelector('.figure'); f.scrollTop = 0; f.scrollLeft = 0; }")
    r.check("print", f"[{tag}] print shows all {len(PANELS)} panels in order and hides the controls",
            all(t is not None for t in tops) and tops == sorted(tops) and not any(controls),
            f"panel tops {tops}, controls visible {controls}")
    r.check("print", f"[{tag}] print shows the whole drawing, without the panning aids",
            whole and not strip, f"frame holds the drawing {whole}, lane strip shown {strip}")
    r.check("print", f"[{tag}] print shows the columns drawing and only that, even from rows",
            columns, f"columns alone {columns}")


# --------------------------------------------------------------------------- viewports
# Windows a reader opens the file in: phone, tablet, small laptop, laptop, desktop and two
# ultrawide screens. The drawing must use the width it is given (fit, and grow up to
# FIT_CEILING on a wide screen), never show text under MIN_FONT_PX (so below the floor it
# pans), and keep the lane names in view while it pans.
VIEWPORTS = ((375, 812), (768, 1024), (1084, 900), (1440, 900), (1920, 1080), (2560, 1080),
             (3440, 1440), (3840, 1080))
PHONE_MAX = 640       # the template's (max-width: 40rem): a phone starts on the step cards
WIDE_SLACK = 100      # the frame spans the window but for this much (page padding, frame
                      # border and a Windows scrollbar): no width cap on the page

LAYOUT_JS = r"""
() => {
  const svg = document.querySelector('svg.pd.on'), fig = svg.closest('.figure');
  const wrap = fig.parentNode, f = fig.getBoundingClientRect(), s = svg.getBoundingClientRect();
  const heads = Array.from(svg.querySelectorAll('g.lane .lane-head')).map(h => {
    const b = h.getBoundingClientRect(); return [b.left, b.right]; });
  let svgMin = Infinity;
  svg.querySelectorAll('text').forEach(t => {
    if (!t.getClientRects().length) return;
    const m = t.getScreenCTM();
    svgMin = Math.min(svgMin, parseFloat(getComputedStyle(t).fontSize) * Math.hypot(m.a, m.b));
  });
  const nodes = Array.from(svg.querySelectorAll('g.node')).map(g => {
    const b = g.getBoundingClientRect(); return [b.left, b.right]; });
  const drawings = Array.from(document.querySelectorAll('svg.pd')).map(d => {
    const cs = getComputedStyle(d);
    return {orient: d.getAttribute('data-orient'), w: parseFloat(d.getAttribute('width')),
            h: parseFloat(d.getAttribute('height')), min: parseFloat(cs.minWidth) || 0,
            max: parseFloat(cs.maxWidth) || 1e9, shown: d.getClientRects().length > 0};
  });
  const bands = Array.from(svg.querySelectorAll('g.lane .lane-band')).map(b => {
    const r = b.getBoundingClientRect(); return [r.top, r.bottom]; });
  return {
    nodes, drawings, bands, innerH: innerHeight, figTop: f.top + scrollY,
    orient: svg.getAttribute('data-orient'),
    page: document.documentElement.scrollWidth, nat: parseFloat(svg.getAttribute('width')),
    svgW: s.width, frame: fig.clientWidth, frameH: fig.getBoundingClientRect().height,
    scrollW: fig.scrollWidth, pan: wrap.classList.contains('pan'), svgMin,
    heads, frameL: f.left + fig.clientLeft, frameR: f.left + fig.clientLeft + fig.clientWidth,
    flowSelected: document.getElementById('tab-flyt').getAttribute('aria-selected') === 'true',
  };
}
"""

STRIP_JS = r"""
() => {
  const fig = document.querySelector('.figure'), strip = document.getElementById('lane-strip');
  fig.scrollTop = fig.scrollHeight / 2; fig.scrollLeft = (fig.scrollWidth - fig.clientWidth) / 2;
  fig.dispatchEvent(new Event('scroll'));
  const rows = document.querySelector('svg.pd.on').getAttribute('data-orient') === 'lr';
  const shown = !strip.hidden && strip.getClientRects().length > 0;
  const span = b => rows ? [b.top, b.bottom] : [b.left, b.right];
  const heads = Array.from(document.querySelectorAll('svg.pd.on g.lane .lane-head')).map(
    h => span(h.getBoundingClientRect()));
  const names = Array.from(strip.children).map(sp => {
    const b = span(sp.getBoundingClientRect());
    return [sp.textContent.trim(), b[0], b[1], parseFloat(getComputedStyle(sp).fontSize)]; });
  return {shown, heads, names, rows};
}
"""


def viewport_checks(r: Report, browser, engine: str, path: pathlib.Path, spec: bpd.Spec,
                    shots: bool) -> None:
    """The drawing in every window in VIEWPORTS, each in a fresh page."""
    for w, h in VIEWPORTS:
        tag = f"{engine} {w}x{h}"
        ctx = browser.new_context(viewport={"width": w, "height": h})
        try:
            page = ctx.new_page()
            page.goto(path.resolve().as_uri())
            page.wait_for_timeout(100)
            first = page.evaluate(LAYOUT_JS)["flowSelected"]
            r.check("viewports", f"[{tag}] starts on «{TABS[0] if w > PHONE_MAX else TABS[1]}»",
                    first == (w > PHONE_MAX), f"flow tab selected {first}")
            page.click("#tab-flyt")
            page.wait_for_timeout(50)
            m = page.evaluate(LAYOUT_JS)
            room = m["innerH"] - m["figTop"] - 8
            mine = next(d for d in m["drawings"] if d["orient"] == m["orient"])
            k = start_scale(mine, m["frame"], room)
            rows = m["orient"] == "lr"
            want = m["nat"] * k if rows and k else expected_width(m["nat"], m["frame"])
            r.check("viewports", f"[{tag}] no sideways scroll on the page itself",
                    m["page"] <= w + 1, f"page is {m['page']} px wide")
            r.check("viewports", f"[{tag}] the drawing uses the width it is given "
                    f"({want / m['nat']:.0%} of natural size)",
                    abs(m["svgW"] - want) < 2 and m["frame"] >= w - WIDE_SLACK,
                    f"drawn {m['svgW']:.0f} px, want {want:.0f}, frame {m['frame']} px, natural {m['nat']}")
            r.check("viewports", f"[{tag}] no text in the drawing under {MIN_FONT_PX} px",
                    m["svgMin"] >= MIN_FONT_PX - 0.01, f"smallest {m['svgMin']:.2f} px")
            want_o = expected_orient(m["drawings"], m["frame"], room)
            r.check("viewports", f"[{tag}] auto shows the {'rows' if want_o == 'lr' else 'columns'} "
                    "drawing, the one that fits with the least scrolling", m["orient"] == want_o
                    and sum(d["shown"] for d in m["drawings"]) == 1,
                    f"shows {m['orient']}, want {want_o}")
            fits = bool(k) if rows else m["nat"] * bpd.FIT_FLOOR <= m["frame"] + 1
            if fits:
                at_ceiling = m["svgW"] >= m["nat"] * bpd.FIT_CEILING - 2
                by_height = rows and abs(k - room / mine["h"]) < 1e-6
                r.check("viewports", f"[{tag}] the drawing fills at least {FILL:.0%} of the frame, "
                        f"or stops at {bpd.FIT_CEILING}x, or (rows) at the window's height",
                        m["svgW"] >= FILL * m["frame"] or at_ceiling or by_height,
                        f"drawn {m['svgW']:.0f} of {m['frame']} px ({m['svgW'] / m['frame']:.0%})")
                if rows:
                    r.check("viewports", f"[{tag}] rows: every lane is inside the window as the page opens",
                            all(t >= -1 and b <= m["innerH"] + 1 for t, b in m["bands"]),
                            f"lane bottoms {[round(b) for _t, b in m['bands']]}, window {m['innerH']}")
                r.check("viewports", f"[{tag}] no step is cut off at the side",
                        all(m["frameL"] - 1 <= a and b <= m["frameR"] + 1 for a, b in m["nodes"]),
                        f"{sum(1 for a, b in m['nodes'] if a < m['frameL'] - 1 or b > m['frameR'] + 1)} cut")
                r.check("viewports", f"[{tag}] every lane is in view, no panning",
                        not m["pan"] and m["scrollW"] <= m["frame"] + 1
                        and all(m["frameL"] - 1 <= a and b <= m["frameR"] + 1 for a, b in m["heads"]),
                        f"pan {m['pan']}, frame {m['frame']}, content {m['scrollW']}")
            else:
                r.check("viewports", f"[{tag}] too narrow to fit readably: it pans in a frame "
                        "no taller than the window",
                        m["pan"] and m["frameH"] <= h + 1,
                        f"pan {m['pan']}, frame height {m['frameH']:.0f}")
                st = page.evaluate(STRIP_JS)
                page.wait_for_timeout(50)
                st = page.evaluate(STRIP_JS)
                lanes_ok = [n for n, _a, _b, _px in st["names"]] == [norm(x) for x in spec.lanes]
                over = all(abs(a - h[0]) < 2 and abs(b - h[1]) < 2
                           for (_n, a, b, _px), h in zip(st["names"], st["heads"]))
                r.check("viewports", f"[{tag}] scrolled down, the lane names stay over their lanes",
                        st["shown"] and lanes_ok and over
                        and all(px >= MIN_FONT_PX for *_x, px in st["names"]),
                        f"shown {st['shown']}, names {[n for n, *_x in st['names']]}, over lanes {over}")
            if shots:
                page.evaluate("() => { const f = document.querySelector('.figure');"
                              " f.scrollTop = 0; f.scrollLeft = 0; f.scrollIntoView(); }")
                page.wait_for_timeout(50)
                shot = path.with_name(f"{path.stem}.{engine}.{w}x{h}.verify.png")
                page.screenshot(path=str(shot))
                r.say(f"    screenshot: {shot}")
        except Exception as exc:  # noqa: BLE001 - a broken page is a finding, not a crash
            r.check("viewports", f"[{tag}] the viewport checks could not run on this page", False,
                    f"{type(exc).__name__}: {str(exc).splitlines()[0][:120]}")
        finally:
            ctx.close()


# --------------------------------------------------------------------------- runs
def static_checks(r: Report, html: str, path: pathlib.Path) -> None:
    for key, fn in (("self-contained", core.check_self_contained),
                    ("placeholders", core.check_no_leftover_placeholders),
                    ("provenance", core.check_provenance),
                    ("row-25", core.check_no_stray_script_text),
                    ("row-24", core.check_no_target_driven_visibility),
                    ("row-26", core.check_no_scroll_persistent_positioning)):
        ok, msg = fn(html)
        r.check(key, f"[static] {key}: {msg}", ok)
    r.check("provenance", "[static] Origin Notice (Made with Tún, tun.community)",
            "Made with" in html and "Tún" in html and "tun.community" in html)
    banned = [t for t in ("location.hash", "hashchange", "fetch(", "new Worker", "import(",
                          "XMLHttpRequest", 'href="#') if t in html]
    r.check("file-url", "[static] no URL fragment, fetch, import or worker (none work from file://)",
            not banned, f"found {banned}")
    level, msg, _mb = core.check_size(path)
    r.check("size", f"[static] size: {msg}", level != "fail")


def run_engine(browser, engine: str, path: pathlib.Path, spec: bpd.Spec, r: Report,
               shot: pathlib.Path | None, max_crossings: int | None) -> None:
    r.say(f"\n  -- {engine} --")
    ctx = browser.new_context(viewport=VIEWPORT)
    try:
        page = ctx.new_page()
        errors: list[str] = []
        requests: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = path.resolve().as_uri()
        page.on("request", lambda q: requests.append(q.url) if q.url.split("#")[0] != url else None)
        page.goto(url)
        page.wait_for_timeout(150)
        data = page.evaluate(COLLECT_JS)
        if data is None:
            r.check("count-nodes", f"[{engine}] an svg.pd drawing exists", False)
            return
        r.check("js", f"[{engine}] the page script ran", data["js"])
        geometry_checks(r, data, spec, engine, max_crossings)
        content_checks(r, data, spec, engine)
        if shot:
            page.screenshot(path=str(shot), full_page=True)
            r.say(f"    screenshot: {shot}")
        page.set_default_timeout(3000)
        for key, fn, args in (("tabs", tab_checks, ()), ("type", font_checks, ()),
                              ("zoom", zoom_checks, ()), ("highlight", highlight_checks, (spec,)),
                              ("filter", filter_checks, (spec,)), ("detail", detail_checks, (spec,)),
                              ("crosslink", crosslink_checks, (spec,)), ("print", print_checks, ())):
            # A broken page must fail the check aimed at it, not crash the verifier: an
            # exception here is a finding about the file, recorded under the check's key.
            try:
                fn(r, page, *args, engine) if args else fn(r, page, engine)
            except Exception as exc:  # noqa: BLE001 - Playwright raises several types
                r.check(key, f"[{engine}] {key}: the check could not run on this page", False,
                        f"{type(exc).__name__}: {str(exc).splitlines()[0][:120]}")
                page.emulate_media(media="screen")
        # After the reader-driven checks, which start from the page as it opened.
        try:
            rows_checks(r, page, spec, f"{engine} rows", max_crossings)
        except Exception as exc:  # noqa: BLE001
            r.check("rows", f"[{engine} rows] the rows checks could not run on this page", False,
                    f"{type(exc).__name__}: {str(exc).splitlines()[0][:120]}")
        r.check("console", f"[{engine}] zero console errors", not errors, f"{errors[:2]}")
        r.check("network", f"[{engine}] zero network requests", not requests, f"{requests[:2]}")
    finally:
        ctx.close()


def run_nojs(browser, path: pathlib.Path, spec: bpd.Spec, r: Report) -> None:
    r.say("\n  -- chromium, JavaScript off --")
    ctx = browser.new_context(java_script_enabled=False, viewport=VIEWPORT)
    try:
        page = ctx.new_page()
        page.goto(path.resolve().as_uri())
        data = page.evaluate(COLLECT_JS)   # evaluate runs even with page scripts off
        tops = page.evaluate(VISIBLE_JS, list(PANELS))
        controls = page.evaluate(CONTROLS_JS)
        r.check("nojs", f"[no-js] all {len(PANELS)} panels show, one after the other",
                all(t is not None for t in tops) and tops == sorted(tops), f"panel tops {tops}")
        r.check("nojs", "[no-js] no control that needs the script is visible", not any(controls),
                f"tabs, toolbar, detail, buttons: {controls}")
        r.check("nojs", f"[no-js] drawing has {len(spec.nodes)} nodes and {len(spec.edges)} connections",
                bool(data) and len(data["nodes"]) == len(spec.nodes) and len(data["edges"]) == len(spec.edges))
        if data:
            content_checks(r, data, spec, "no-js")
        shown = page.evaluate("() => Array.from(document.querySelectorAll('svg.pd')).filter("
                              "d => d.getClientRects().length).map(d => d.getAttribute('data-orient'))")
        r.check("nojs", "[no-js] one drawing shows, the columns", shown == ["tb"], f"{shown}")
        box = page.locator("svg.pd.on").bounding_box()
        r.check("nojs", "[no-js] drawing has a real size",
                bool(box) and box["width"] > 100 and box["height"] > 100, f"{box}")
    finally:
        ctx.close()


def use_page_lang(html: str) -> str:
    """The tab names the page should carry, from its <html lang>. Returns the language."""
    m = re.search(r'<html lang="([a-z]+)"', html)
    lang = m.group(1) if m else i18n.DEFAULT_LANG
    global TABS
    TABS = tuple(i18n.load("process-diagram", lang)[k] for k in TAB_KEYS)
    return lang


def verify(path: pathlib.Path, spec: bpd.Spec, engines, shots: bool, quiet: bool = False,
           max_crossings: int | None = None) -> Report:
    from playwright.sync_api import sync_playwright
    r = Report(quiet)
    lang = use_page_lang(path.read_text(encoding="utf-8"))
    r.say(f"verify {path.name} against {spec.name} (page language {lang})")
    static_checks(r, path.read_text(encoding="utf-8"), path)
    with sync_playwright() as pw:
        # The no-JS pass always runs in Chromium, whichever engines were asked for.
        for engine in dict.fromkeys(engines + ("chromium",)):
            browser = getattr(pw, engine).launch()
            try:
                if engine in engines:
                    shot = path.with_name(f"{path.stem}.{engine}.verify.png") if shots else None
                    run_engine(browser, engine, path, spec, r, shot, max_crossings)
                    viewport_checks(r, browser, engine, path, spec, shots)
                if engine == "chromium":
                    run_nojs(browser, path, spec, r)
            finally:
                browser.close()
    return r


# --------------------------------------------------------------------------- mutations
def _lines(html: str, prefix: str, at_least: int = 1) -> list[str]:
    """Lines starting with prefix, per the output contract in
    build_process_diagram.render_svg(). Too few means the anchor moved, which must stop
    the mutation check rather than let it 'mutate' nothing."""
    found = [ln for ln in html.splitlines() if ln.startswith(prefix)]
    if len(found) < at_least:
        raise SystemExit(f"mutation anchor missing: fewer than {at_least} lines start with {prefix!r}")
    return found


def _node_lines(html: str) -> list[str]:
    # 'node node-', not 'node': the container <g class="nodes"> must not match.
    return _lines(html, '<g class="node node-', 2)


def _swap(html: str, old: str, new: str) -> str:
    if old not in html:
        raise SystemExit(f"mutation anchor missing: {old[:60]!r}")
    return html.replace(old, new, 1)


def mutate_drop_node(html: str) -> str:
    return html.replace(_node_lines(html)[0] + "\n", "", 1)


def mutate_drop_edge(html: str) -> str:
    return html.replace(_lines(html, '<g class="edge"')[0] + "\n", "", 1)


def mutate_overlap(html: str) -> str:
    a, b = _node_lines(html)[:2]
    ta = re.search(r'transform="[^"]+"', a).group(0)
    return html.replace(b, re.sub(r'transform="[^"]+"', ta, b, count=1), 1)


def mutate_through(html: str) -> str:
    """Re-route the first connection straight down through the middle of a box it has
    nothing to do with."""
    edge = _lines(html, '<g class="edge"')[0]
    src = re.search(r'data-from="([^"]+)"', edge).group(1)
    dst = re.search(r'data-to="([^"]+)"', edge).group(1)
    other = next(ln for ln in _node_lines(html)
                 if f'data-node="{src}"' not in ln and f'data-node="{dst}"' not in ln)
    tx, ty = map(float, re.search(r'translate\(([\d.]+) ([\d.]+)\)', other).groups())
    d = f'd="M{tx + 90} {ty - 40} L{tx + 90} {ty + 120}"'
    return html.replace(edge, re.sub(r'class="edge-line" d="[^"]+"', f'class="edge-line" {d}',
                                     edge, count=1), 1)


def mutate_clip_text(html: str) -> str:
    line = _node_lines(html)[0]
    return html.replace(line, re.sub(r'(<tspan x=")[\d.]+', r'\g<1>400', line), 1)


def mutate_drop_textalt(html: str) -> str:
    item = _lines(html, "<li data-node=")[0]
    return html.replace(item, "<li>(fjernet)</li>", 1)


def mutate_console(html: str) -> str:
    tag = "scr" + "ipt"   # keep the literal out of this source; row 25 scans HTML, not .py
    return html.replace("</body>", f'<{tag}>throw new Error("mutation")</{tag}>\n</body>', 1)


def mutate_add_crossing(html: str) -> str:
    """One line made to cut straight across the whole drawing."""
    w, h = map(float, re.search(r'class="pd[^"]*" data-orient="tb" width="([\d.]+)" height="([\d.]+)"', html).groups())
    edge = _lines(html, '<g class="edge"')[0]
    return html.replace(edge, re.sub(r'class="edge-line" d="[^"]+"',
                                     f'class="edge-line" d="M4 {h / 2} L{w - 4} {h / 2}"', edge, count=1), 1)


def mutate_tab_keys(html: str) -> str:
    return _swap(html, 'if (ev.key === "ArrowRight") j = (i + 1) % n;', 'if (ev.key === "ArrowRight") j = i;')


def mutate_drop_card(html: str) -> str:
    return html.replace(_lines(html, '<article class="card step-card')[0] + "\n", "", 1)


def mutate_hide_panel_nojs(html: str) -> str:
    return _swap(html, '<section class="panel" id="panel-roller"', '<section hidden class="panel" id="panel-roller"')


def mutate_print(html: str) -> str:
    return _swap(html, "  .panel[hidden]{display:block}\n", "")


def mutate_wrong_detail(html: str) -> str:
    return _swap(html, 'var card = doc.getElementById("step-" + id);',
                 'var card = doc.querySelector(".step-card");')


def mutate_wrong_crosslink(html: str) -> str:
    return _swap(html, 'var id = b.getAttribute("data-node"), n = nodeById(id);',
                 'var id = b.getAttribute("data-node"), n = nodes[0];')


def mutate_no_highlight(html: str) -> str:
    return _swap(html, 's.classList.toggle("focusing", !!id);', 's.classList.toggle("focusing", false);')


def mutate_no_filter(html: str) -> str:
    return _swap(html, 's.classList.toggle("lane-filter", lane !== "");',
                 's.classList.toggle("lane-filter", false);')


def mutate_small_type(html: str) -> str:
    return _swap(html, "</style>", ".facts dd{font-size:10px}\n</style>")


def mutate_no_zoom(html: str) -> str:
    return _swap(html, 'zoomBy(0.25); });', 'zoomBy(0); });')


def mutate_cap_page(html: str) -> str:
    """The page width capped again, whatever the drawing needs (the wide-screen bug)."""
    return _swap(html, "main{max-width:none;", "main{max-width:96rem;")


def mutate_no_growth(html: str) -> str:
    """The drawing stops at natural size on a wide screen, with the width left empty."""
    nat = re.search(r'class="pd[^"]*" data-orient="tb" width="([\d.]+)"', html).group(1)
    return _sub(html, r"max-width:[\d.]+px;min-width:", f"max-width:{nat}px;min-width:")


def mutate_no_fit(html: str) -> str:
    """The drawing kept at natural size: it scrolls even where it would fit readably."""
    return _sub(html, r"\.pd\{display:block;width:100%;height:auto;", ".pd{display:block;")


def mutate_no_floor(html: str) -> str:
    """No floor: the drawing shrinks to the frame and its text with it."""
    return _sub(html, r"min-width:[\d.]+px\}", "min-width:0}")


def mutate_print_strip(html: str) -> str:
    """Print keeps the lane-name strip of a panning frame, on top of the drawing."""
    return _swap(html, "  html.js .pan .lane-strip:not([hidden]){display:none}\n", "")


def mutate_no_strip(html: str) -> str:
    return _swap(html, "strip.hidden = !first || (rows ? first.right > f.left + 1 : first.bottom > f.top + 1);",
                 "strip.hidden = true;")


def _sub(html: str, pattern: str, new: str) -> str:
    out, n = re.subn(pattern, new, html, count=1)
    if not n:
        raise SystemExit(f"mutation anchor missing: {pattern[:60]!r}")
    return out


def mutate_never_rows(html: str) -> str:
    """Auto keeps the columns whatever the window: an ultrawide screen stays mostly empty."""
    return _swap(html, "    if (forced) return forced;\n", "    return svgs[0];\n")


def mutate_rows_ignore_height(html: str) -> str:
    """Rows start at the frame's width alone, so on a short window the last lanes fall
    below its bottom edge."""
    return _swap(html, "      k = Math.min(k, (window.innerHeight - top - 8) / r.h);\n", "")


def mutate_cut_word(html: str) -> str:
    """A label line ends inside a word, with a hyphen the label does not have."""
    m = re.search(r'(<text class="node-label" x="([\d.]+)"[^>]*><tspan x="[\d.]+" dy="0">)'
                  r'([^<]*?)\b([A-Za-zæøåÆØÅ]{3})([A-Za-zæøåÆØÅ]{3,})', html)
    if not m:
        raise SystemExit("mutation anchor missing: no label word of six letters to cut")
    head, x, before, a, b = m.groups()
    return html[:m.start()] + f'{head}{before}{a}-</tspan><tspan x="{x}" dy="{bpd.LINE_H}">{b}' + html[m.end():]


def mutate_drop_rows_node(html: str) -> str:
    """A node missing from the rows drawing only, which the default view never shows."""
    rows = html.index('data-orient="lr"')
    line = next(ln for ln in _node_lines(html) if html.index(ln) > rows)
    return html.replace(line + "\n", "", 1)


def mutate_print_rows(html: str) -> str:
    """Print gives whichever drawing was on screen, so rows run off a portrait page."""
    return _swap(html, "  html .pd.pd-tb{display:block}\n  html .pd.pd-lr{display:none}\n", "")


def mutate_loop_from_bottom(html: str) -> str:
    """A loop back drawn as if it left the bottom of its box: the side-entry contract."""
    return _swap(html, ' data-loop="1"', "")


MUTATIONS = (
    ("drop a node", mutate_drop_node, "count-nodes"),
    ("drop a connection", mutate_drop_edge, "count-edges"),
    ("move a box onto another", mutate_overlap, "overlap"),
    ("route a line through a box", mutate_through, "through"),
    ("push a label out of its box", mutate_clip_text, "text"),
    ("drop a step from the text version", mutate_drop_textalt, "textalt"),
    ("throw a script error", mutate_console, "console"),
    ("add a crossing", mutate_add_crossing, "crossings"),
    ("unmark a loop back", mutate_loop_from_bottom, "loops"),
    ("break ArrowRight in the tablist", mutate_tab_keys, "tabs"),
    ("drop a step card", mutate_drop_card, "panels"),
    ("hide a panel without JavaScript", mutate_hide_panel_nojs, "nojs"),
    ("let print hide the other panels", mutate_print, "print"),
    ("open the wrong step's details", mutate_wrong_detail, "detail"),
    ("send «Vis i flyten» to the wrong node", mutate_wrong_crosslink, "crosslink"),
    ("stop the hover highlight", mutate_no_highlight, "highlight"),
    ("stop the role filter", mutate_no_filter, "filter"),
    ("stop zoom in", mutate_no_zoom, "zoom"),
    ("shrink card text to 10 px", mutate_small_type, "type"),
    ("cap the page width again", mutate_cap_page, "viewports"),
    ("stop fitting the drawing to its frame", mutate_no_fit, "viewports"),
    ("stop the drawing growing on a wide screen", mutate_no_growth, "viewports"),
    ("let the drawing shrink below 12 px text", mutate_no_floor, "viewports"),
    ("hide the lane names while panning", mutate_no_strip, "viewports"),
    ("let print show the lane names of a panning frame", mutate_print_strip, "print"),
    ("let auto never choose the rows drawing", mutate_never_rows, "viewports"),
    ("let rows ignore the window's height", mutate_rows_ignore_height, "viewports"),
    ("cut a label inside a word", mutate_cut_word, "words"),
    ("drop a node from the rows drawing only", mutate_drop_rows_node, "count-nodes"),
    ("print the rows drawing", mutate_print_rows, "print"),
)


def mutation_check(path: pathlib.Path, spec: bpd.Spec) -> int:
    print(f"mutation check on copies of {path.name} (the original is never edited)")
    original = path.read_text(encoding="utf-8")
    baseline = verify(path, spec, ("chromium",), shots=False, quiet=True)
    if baseline.failures:
        print(f"✗ the unmutated file already fails: {baseline.failures[:3]}")
        return 1
    ceiling = baseline.crossings["chromium"]
    print(f"  unmutated file: {baseline.passed} checks pass, {ceiling} crossings (used as the ceiling)")
    missed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, fn, key in MUTATIONS:
            mutated = fn(original)
            if mutated == original:
                print(f"  ✗ {name}: the mutation changed nothing, so it proves nothing")
                missed += 1
                continue
            copy = pathlib.Path(tmp) / path.name
            copy.write_text(mutated, encoding="utf-8")
            rep = verify(copy, spec, ("chromium",), shots=False, quiet=True, max_crossings=ceiling)
            keys = sorted({k for k, _ in rep.failures})
            if key in keys:
                print(f"  ✓ {name}: caught by '{key}' ({len(rep.failures)} failure(s): {', '.join(keys)})")
            else:
                print(f"  ✗ {name}: NOT caught by '{key}' (saw {keys or 'no failures'})")
                missed += 1
    if missed:
        print(f"✗ FAIL mutation check: {missed} of {len(MUTATIONS)} breaks went unnoticed")
        return 1
    print(f"✓ PASS mutation check: all {len(MUTATIONS)} breaks caught by the check aimed at them")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", type=pathlib.Path)
    ap.add_argument("--spec", type=pathlib.Path, required=True,
                    help="the .process.txt the diagram was built from; expected counts come from it")
    core.add_engines_arg(ap, default=core.ENGINES)
    ap.add_argument("--max-crossings", type=int, default=None,
                    help="fail if any engine renders more crossings than this")
    ap.add_argument("--mutation-check", action="store_true",
                    help="prove the checks fail on broken copies, then exit")
    args = ap.parse_args(argv)
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("✗ FAIL: Playwright is not installed, so nothing was opened in a browser.\n"
              "  Run: uv run --extra verify python tools/verify_process_diagram.py ...",
              file=sys.stderr)
        return 1
    if not args.html.is_file():
        print(f"✗ FAIL: {args.html} does not exist", file=sys.stderr)
        return 1
    try:
        spec = bpd.parse_spec(args.spec.read_text(encoding="utf-8-sig"), args.spec.name)
    except (OSError, bpd.SpecError) as exc:
        print(f"✗ FAIL: cannot read the spec: {exc}", file=sys.stderr)
        return 1
    if args.mutation_check:
        return mutation_check(args.html, spec)
    engines = args.engines
    r = verify(args.html, spec, engines, shots=True, max_crossings=args.max_crossings)
    print()
    if r.failures:
        for key, msg in r.failures:
            print(f"  ✗ [{key}] {msg}")
        print(f"✗ FAIL: {len(r.failures)} check(s) failed, {r.passed} passed")
        return 1
    crossings = ", ".join(f"{e} {n}" for e, n in r.crossings.items())
    print(f"✓ PASS: {r.passed} checks, {len(spec.nodes)} nodes, {len(spec.edges)} connections, "
          f"{len(engines)} engine(s) + no-JS; crossings {crossings}. Now look at the screenshots.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
