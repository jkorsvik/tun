#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
build_process_diagram.py — turn a small text spec into one self-contained process diagram.

Stdlib only, like the rest of tools/.

    python3 tools/build_process_diagram.py SPEC.process.txt --out diagram.html
    python3 tools/build_process_diagram.py SPEC.process.txt --check   # parse + lay out only

The output is ONE .html file with an inline SVG. It renders fully with JavaScript off,
carries a text alternative (every step, per lane, with its branches), prints on one
landscape page, and takes its colours from the token contract (tools/tun_tokens.py).

The spec format
---------------
A plain text file, one statement per line. Indentation is for the reader; the parser
goes by the first word. `#` starts a comment line.

    title: Slik lager vi en rapport            <- required
    source: Intervju med teamet, mars          <- required, where the process came from
    requested-by: Teamleder                    <- required, a role is fine
    description: Én setning under tittelen     <- optional
    palette: plugins/tun/tokens/palette.css    <- optional; default is core's neutral palette

    lane Bestiller                             <- a lane is an actor: a role, team or system
      start request: Behov meldt               <- <kind> <id>: <label>
      step describe: Beskriver spørsmålet
        beskrivelse: Hva som skjer, i én eller to setninger      <- optional step fields,
        input: Det steget trenger                                   any subset, any order
        output: Det steget leverer
        verktøy: Teams, e-post
        varighet: 10 minutter
        improve: Kommer ofte uten eksempel     <- flags the step above as "improve here"
          problem: Hva som går galt, utdypet   <- optional, under improve:
          forslag: Hva som bør endres
    lane Analytiker
      decision ok: Godkjent?

    flow                                       <- everything after this is a connection
      request -> describe -> ok                <- a chain is several connections
      ok -> describe [nei]                     <- [label] on a single arrow
      ok -> done [ja]

Kinds: start, step, decision, end. Rules the builder enforces, with the line number:
a decision has at least two outgoing connections and every one is labelled; a start has
no incoming and an end no outgoing connection; every step is reachable from a start;
`improve:` belongs to a step or a decision; `problem:` and `forslag:` come after the
`improve:` they explain. The step fields fill the step cards in the «Steg» tab and the
detail panel; a spec without them still builds, and the cards then show what the
diagram knows (role, where the step leads, the improvement point).

Why text and not JSON: a `.json` file in this repo trips the data-file gate
(tools/check_no_real_data.py), and a person describing their own process writes lines,
not braces. A `.txt` suffix also opens in Notepad on a double click.

Layout
------
Top to bottom. Each lane is a column with its name at the top; steps flow downwards in
layers: a step's layer is one past its furthest predecessor, ignoring connections that
loop back. Each (lane, layer) cell holds at most one step, so boxes cannot overlap by
construction. Connections leave from the bottom of a box and arrive at the top. They are
routed at right angles through the gaps between layers ("channels") and between lanes
("gutters"), each on its own track; a candidate route is rejected if it crosses a box,
runs along another connection, or crosses a branch label. A route has no repeated point
and no bend that does not turn: a "bend" that sits on another line's track would hide
that crossing from the cost. If a gap runs out of tracks it gets one more and routing
starts again. Same spec in, same file out.

Why top to bottom: most processes are a long chain across a few roles. Drawn left to
right, an 11-step chain was 3058 px wide, which is about 4 px text on a printed page.
Top to bottom the same chain is a little over 1000 px tall and prints readably.

The same layout runs a second time with the flow to the right and lanes as rows
(Orient LR): the engine is the same, in the same abstract axes, and only the box sizes,
the pill direction and the lane header differ. The page carries both drawings and shows
the one that fits the window with the least scrolling; columns are the floor without the
script and in print. Both number the steps the same, so the cards and the text version
are one list for both.

Why the smallest text is 14 units: the page fits the drawing to the window, down to
FIT_FLOOR (12/14) of natural size, where that text is 12 px. With 12-unit text the floor
would be 1:1 and nothing could fit. Narrower than the floor, the page pans.

check_layout() re-checks every one of those properties on the finished geometry, and the
build refuses to write a file that fails it. tools/verify_process_diagram.py checks the
same properties again in three real browsers, on what was actually rendered.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import math
import os
import pathlib
import re
import sys
from dataclasses import dataclass, field
from typing import Callable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_size
import build_stamp  # noqa: E402
import i18n  # noqa: E402
import tun_tokens  # noqa: E402
from tun_tokens import strip_css_comments  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "templates" / "process-diagram.html"
STRINGS = "process-diagram"   # named, not derived from TEMPLATE, which a test may point at a copy
BUILT_BY = "tools/build_process_diagram.py"

KINDS = ("start", "step", "decision", "end")
# The words the builder writes per step. templates/i18n/process-diagram.strings holds them
# in both languages; the template holds the page chrome. T is the table for the language
# being built: use_lang() fills it, and nb is loaded at import so a plain build() is as before.
T: dict[str, str] = {}


def use_lang(lang: str) -> None:
    T.clear()
    T.update(i18n.load(STRINGS, lang))


use_lang(i18n.DEFAULT_LANG)

LANE_COLOURS = 6      # role colour classes c0..c5; templates/process-diagram.html maps them
HEADERS = ("title", "source", "requested-by", "description", "palette")
# Optional fields under a step, in the order a step card shows them. The key is what the
# spec author writes; "verktoy" is accepted for keyboards without ø.
STEP_FIELDS = {"beskrivelse": "description", "input": "input", "output": "output",
               "verktøy": "tool", "verktoy": "tool", "varighet": "duration"}
FLAG_FIELDS = {"problem": "problem", "forslag": "proposal"}   # keys of an Improvement
MAX_FIELD = 300
REQUIRED_HEADERS = ("title", "source", "requested-by")
ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
NODE_RE = re.compile(r"^(start|step|decision|end)\s+([^\s:]+)\s*:\s*(.*)$")
LABEL_RE = re.compile(r"^(.*?)\s*\[([^\[\]]*)\]\s*$")

MAX_LABEL = 90       # a step label; detail belongs in improve: or the text around the file
MAX_EDGE_LABEL = 24  # a branch answer: "ja", "nei", "trenger endring"
MAX_LANE = 40

# Geometry, in SVG user units. At natural size one unit is one CSS px.
# No text is smaller than 14 units, so the page may shrink the drawing to FIT_FLOOR (12/14)
# to fit the window and still show no text under MIN_TEXT_PX. Below that it scrolls.
BOX_W = 212           # box width, across the lane
FONT = 14             # step labels and lane names
LABEL_FONT = 14       # branch labels, step numbers, badges: as big as FONT, see FIT_FLOOR
LINE_H = 18
CHAR_W = 7.9          # a deliberately wide average for a 14-unit system sans-serif
CHAR_W_BOLD = 8.4
LABEL_CHAR_W = 8.2
HEX = 18              # how far a decision's side points stick out
NUM_R = 11            # radius of the step number disc inside each box
BADGE_R = 11          # radius of the improvement badge on a box corner
LANE_PAD = 20         # space beside a box inside its lane; the last branch pill may use it
HEAD_PAD = 12         # lane name padding inside its header
PORT_MARGIN = 28      # ports stay this far from a box's ends, on the flat part of the outline
PORT_MIN = 22         # minimum gap between two lines leaving one box
SIDE_GAP = 26         # gap between two loop ports on a box's right side: one pill plus air
PILL_H = 20           # a branch label's pill
PILL_PAD = 7
BASELINE = 0.35       # a centred line's baseline sits this many ems below the centre
TRACK = 12            # spacing between parallel lines
MIN_ZONE = 16         # minimum last stretch into a box, room for the arrowhead
MARGIN = 16
MIN_SEP = 3           # closer than this, two parallel lines read as one
PORT_CLEAR = 8        # least gap between a box's in-ports and the out-ports of the box above
CORNER = 6            # radius of a line's rounded bend
ARROW_L, ARROW_W = 10, 8
MIN_TEXT_PX = 12      # the smallest text a reader is shown, in CSS px, at any window width
FIT_FLOOR = MIN_TEXT_PX / min(FONT, LABEL_FONT)   # how far the page may shrink the drawing
FIT_CEILING = 1.5     # how far it may grow to fill a wide screen: 14 units become 21 px
# Rows (the flow left to right). A box is narrower, so labels wrap sooner and the boxes
# grow downwards, which a wide screen has room for.
BOX_W_LR = 160
PORT_MARGIN_LR = 26   # ports keep clear of a decision's slant and a start's round corner
HEAD_W_LR = 150       # the lane-name column on the left, with its gap
# Routing costs. A crossing outweighs any detour the drawing can offer, so the router only
# accepts one when every crossing-free route is blocked.
CROSS_COST = 1000
BEND_COST = 15
RIPUP_PASSES = 3
EXTRA_TRACK_TRIES = 6


class SpecError(ValueError):
    """A spec the builder cannot honour. The message names the file and line."""


class LayoutError(RuntimeError):
    """The spec is valid but could not be drawn without breaking a layout rule."""


@dataclass
class Improvement:
    """A flagged step's improvement point: what goes wrong in one sentence (the spec's
    `improve:` line), and optionally the problem in more detail and a proposal."""
    text: str
    problem: str | None = None
    proposal: str | None = None


@dataclass
class Node:
    id: str
    kind: str
    label: str
    lane: int
    line: int
    order: int
    improve: Improvement | None = None
    fields: dict = field(default_factory=dict)   # STEP_FIELDS values, by internal name


@dataclass
class Edge:
    src: str
    dst: str
    label: str | None
    line: int
    order: int


@dataclass
class Spec:
    headers: dict
    lanes: list
    nodes: list
    edges: list
    name: str = "spec"

    @property
    def title(self) -> str:
        return self.headers["title"]

    def node(self, node_id: str) -> Node:
        return next(n for n in self.nodes if n.id == node_id)


# --------------------------------------------------------------------------- parsing
def parse_spec(text: str, name: str = "spec") -> Spec:
    # Notepad and Excel can save UTF-8 with a byte-order mark. Left in, it glues itself
    # to the first header and "title:" becomes an unknown header.
    text = text.lstrip("\ufeff")
    headers: dict[str, str] = {}
    lanes: list[str] = []
    lane_lines: list[int] = []
    nodes: list[Node] = []
    edges: list[Edge] = []
    section = "header"

    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        def fail(msg: str) -> None:
            raise SpecError(f"{name}:{lineno}: {msg}\n    {raw.rstrip()}")

        if line == "flow":
            if section == "flow":
                fail("'flow' appears twice")
            section = "flow"
            continue

        if section == "flow":
            label = None
            m = LABEL_RE.match(line)
            body = line
            if m:
                body, label = m.group(1), m.group(2).strip()
                if not label:
                    fail("empty [label]; drop the brackets or write the answer")
                if len(label) > MAX_EDGE_LABEL:
                    fail(f"a connection label is at most {MAX_EDGE_LABEL} characters")
            parts = [p.strip() for p in body.split("->")]
            if len(parts) < 2 or any(not p for p in parts):
                fail("expected 'from -> to', optionally followed by [label]")
            if label and len(parts) > 2:
                fail("a [label] belongs to a single arrow; split the chain into lines")
            for a, b in zip(parts, parts[1:]):
                edges.append(Edge(a, b, label, lineno, len(edges)))
            continue

        word = line.split(None, 1)[0]
        if word == "lane":
            lane = line[4:].strip()
            if not lane:
                fail("a lane needs a name: 'lane <who does this>'")
            if len(lane) > MAX_LANE:
                fail(f"a lane name is at most {MAX_LANE} characters")
            if lane in lanes:
                fail(f"lane {lane!r} is declared twice; put all its steps under one 'lane' line")
            lanes.append(lane)
            lane_lines.append(lineno)
            section = "lanes"
            continue

        m = NODE_RE.match(line)
        if m:
            kind, node_id, label = m.group(1), m.group(2), m.group(3).strip()
            if not lanes:
                fail("a step must come after a 'lane' line, so it is clear who does it")
            if not ID_RE.match(node_id):
                fail(f"id {node_id!r} may only use letters, digits, '-' and '_'")
            if any(n.id == node_id for n in nodes):
                fail(f"id {node_id!r} is used twice")
            if not label:
                fail(f"{kind} {node_id!r} has no label after the ':'")
            if len(label) > MAX_LABEL:
                fail(f"a label is at most {MAX_LABEL} characters; move the detail to improve:"
                     " or to the text around the diagram")
            nodes.append(Node(node_id, kind, label, len(lanes) - 1, lineno, len(nodes)))
            continue

        if word.lower() in ("improve:", "improve"):
            why = line.split(":", 1)[1].strip() if ":" in line else ""
            if not nodes or section != "lanes":
                fail("'improve:' must sit under the step it is about")
            if not why:
                fail("'improve:' needs a reason: what goes wrong here")
            target = nodes[-1]
            if target.kind not in ("step", "decision"):
                fail(f"'improve:' marks a step or decision, not a {target.kind}")
            if target.improve:
                fail(f"{target.id!r} already has an improve: line; merge them")
            target.improve = Improvement(why)
            continue

        # Field keys are matched in lower case: "Input:" and "input:" are the same field.
        key = line.split(":", 1)[0].strip().lower() if ":" in line else ""
        if key in STEP_FIELDS or key in FLAG_FIELDS:
            value = line.split(":", 1)[1].strip()
            if not nodes or section != "lanes":
                fail(f"'{key}:' must sit under the step it describes")
            target = nodes[-1]
            if not value:
                fail(f"'{key}:' is empty; drop the line or fill it in")
            if len(value) > MAX_FIELD:
                fail(f"'{key}:' is at most {MAX_FIELD} characters")
            if key in FLAG_FIELDS:
                if not target.improve:
                    fail(f"'{key}:' explains an improvement point; put it under an 'improve:' line")
                if getattr(target.improve, FLAG_FIELDS[key]) is not None:
                    fail(f"{target.id!r} already has '{key}:'; merge the lines")
                setattr(target.improve, FLAG_FIELDS[key], value)
            else:
                if STEP_FIELDS[key] in target.fields:
                    fail(f"{target.id!r} already has '{key}:'; merge the lines")
                target.fields[STEP_FIELDS[key]] = value
            continue
        if key and key not in HEADERS and section == "lanes" and NODE_RE.match(line) is None \
                and line.split(None, 1)[0].rstrip(":").lower() not in KINDS:
            fail(f"unknown field '{key}:' under a step; the fields are "
                 f"{', '.join(dict.fromkeys(STEP_FIELDS))}, and under improve: "
                 f"{', '.join(FLAG_FIELDS)}")

        if ":" in line and NODE_RE.match(line) is None and word.rstrip(":") in KINDS:
            fail(f"expected '{word.rstrip(':')} <id>: <label>'")
        if ":" in line:
            key, value = (s.strip() for s in line.split(":", 1))
            if section != "header":
                fail("headers (title:, source:, ...) go before the first 'lane' line")
            if key not in HEADERS:
                fail(f"unknown header {key!r}; expected one of {', '.join(HEADERS)}")
            if key in headers:
                fail(f"header {key!r} is given twice")
            if not value:
                fail(f"header {key!r} is empty")
            headers[key] = value
            continue
        fail("cannot read this line; expected a header, 'lane <name>', "
             "'<kind> <id>: <label>', 'improve: <why>', 'flow', or 'a -> b'")

    spec = Spec(headers, lanes, nodes, edges, name)
    _validate(spec, lane_lines)
    return spec


def _validate(spec: Spec, lane_lines: list[int]) -> None:
    name = spec.name
    for key in REQUIRED_HEADERS:
        if key not in spec.headers:
            raise SpecError(f"{name}: missing header '{key}:' (required: "
                            f"{', '.join(REQUIRED_HEADERS)}); it goes into the provenance block")
    if not spec.lanes:
        raise SpecError(f"{name}: no 'lane' lines; a process needs at least one actor")
    for i, lane in enumerate(spec.lanes):
        if not any(n.lane == i for n in spec.nodes):
            raise SpecError(f"{name}:{lane_lines[i]}: lane {lane!r} has no steps")
    ids = {n.id: n for n in spec.nodes}
    seen = set()
    for e in spec.edges:
        where = f"{name}:{e.line}"
        for end in (e.src, e.dst):
            if end not in ids:
                raise SpecError(f"{where}: unknown id {end!r} in the flow")
        if e.src == e.dst:
            raise SpecError(f"{where}: {e.src!r} connects to itself")
        if (e.src, e.dst) in seen:
            raise SpecError(f"{where}: {e.src} -> {e.dst} is listed twice")
        seen.add((e.src, e.dst))
    outs = {n.id: [e for e in spec.edges if e.src == n.id] for n in spec.nodes}
    ins = {n.id: [e for e in spec.edges if e.dst == n.id] for n in spec.nodes}
    if not any(n.kind == "start" for n in spec.nodes):
        raise SpecError(f"{name}: no 'start'; say where the process begins")
    if not any(n.kind == "end" for n in spec.nodes):
        raise SpecError(f"{name}: no 'end'; say where the process is finished")
    for n in spec.nodes:
        where = f"{name}:{n.line}"
        if n.kind == "start" and ins[n.id]:
            raise SpecError(f"{where}: start {n.id!r} has an incoming connection")
        if n.kind == "end" and outs[n.id]:
            raise SpecError(f"{where}: end {n.id!r} has an outgoing connection")
        if n.kind != "end" and not outs[n.id]:
            raise SpecError(f"{where}: {n.id!r} leads nowhere; connect it, or make it an end")
        if n.kind != "start" and not ins[n.id]:
            raise SpecError(f"{where}: nothing leads to {n.id!r}")
        if n.kind == "decision":
            labels = [e.label for e in outs[n.id]]
            if len(labels) < 2:
                raise SpecError(f"{where}: decision {n.id!r} needs at least two outcomes")
            if any(not lb for lb in labels):
                raise SpecError(f"{where}: every outcome of decision {n.id!r} needs a "
                                "[label], e.g. [ja] and [nei]")
            if len(set(labels)) != len(labels):
                raise SpecError(f"{where}: decision {n.id!r} has two outcomes with the same label")
    reached = set()
    stack = [n.id for n in spec.nodes if n.kind == "start"]
    while stack:
        cur = stack.pop()
        if cur in reached:
            continue
        reached.add(cur)
        stack.extend(e.dst for e in outs[cur])
    for n in spec.nodes:
        if n.id not in reached:
            raise SpecError(f"{name}:{n.line}: {n.id!r} cannot be reached from any start")


# --------------------------------------------------------------------------- geometry
# The engine works in two abstract axes: u runs along the flow (down the page), v runs
# across the lanes (left to right). Everything is computed in (u, v); render_svg() is the
# only place that turns a point into screen x = v, y = u. Keeping the axes abstract is what
# lets the router read as "channels between layers, gutters between lanes" without a
# screen direction baked into every comparison.
def pieces(word: str) -> list[str]:
    """A word in the pieces a line may end after: "før/etter" is "før/" and "etter"."""
    return re.findall(r"[^/-]+[/-]*|[/-]+", word)


def longest_piece(text: str) -> int:
    """The longest run of characters a line can never break: the box must hold it."""
    return max((len(p) for w in text.split() for p in pieces(w)), default=0)


def wrap(text: str, width: float, char_w: float) -> list[str]:
    """Greedy wrap by an estimated character width. A line breaks at a space, or just after
    a "/" or "-" the text already has, never inside a word: "inventorie-d" reads as a
    typo, and a hyphen added to a file name changes it. A piece longer than a line keeps
    its own line; plan_layout() makes the boxes wide enough for it."""
    per_line = max(4, int(width // char_w))
    lines: list[str] = []
    cur = ""
    for word in text.split():
        for i, piece in enumerate(pieces(word)):
            sep = "" if i else " "
            if not cur:
                cur = piece
            elif len(cur) + len(sep) + len(piece) <= per_line:
                cur += sep + piece
            else:
                lines.append(cur)
                cur = piece
    if cur:
        lines.append(cur)
    return lines


def inset(kind: str) -> float:
    """How far a box's outline sits in from its bounding box at mid-height, on the left:
    the step number sits just inside it and the label starts after the number."""
    return HEX if kind == "decision" else (14 if kind in ("start", "end") else 10)


def text_span(kind: str, box_w: float = BOX_W) -> tuple[float, float]:
    """(left, right) of the label area inside a box box_w wide, in box-local units."""
    left = inset(kind) + 2 * NUM_R + 10
    right = box_w - inset(kind) - 8
    return left, right


def text_width(kind: str, box_w: float = BOX_W) -> float:
    left, right = text_span(kind, box_w)
    return right - left


def pill_width(label: str) -> float:
    return len(label) * LABEL_CHAR_W + 2 * PILL_PAD


@dataclass(frozen=True)
class Orient:
    """Which way the flow runs on screen. The engine works in (u, v) either way, u along
    the flow and v across the lanes; this holds the few things that depend on the screen.
    "tb": the flow runs down and lanes are columns (x = v, y = u). "lr": the flow runs to
    the right and lanes are rows (x = u, y = v). A box's labels wrap to its width on
    screen. A branch label's pill is always horizontal on screen, so along the flow it is
    PILL_H long in "tb" and as long as its text in "lr"."""
    name: str
    box_w: float          # a box's width on screen
    port_margin: float    # ports stay this far from the ends of a box's flow edge
    head_w: float = 0     # "lr": width of the lane-name column

    def pill_along(self, label: str) -> float:
        return PILL_H if self.name == "tb" else pill_width(label)

    def pill_across(self, label: str) -> float:
        return pill_width(label) if self.name == "tb" else PILL_H

    def screen(self, u: float, v: float) -> tuple:
        return (v, u) if self.name == "tb" else (u, v)

    def text_kind(self, kind: str) -> str:
        """The kind whose insets a label follows. A decision's points stick out across the
        flow: sideways in columns, so its text keeps clear of them; up and down in rows,
        where its sides are straight, so its text is as wide as a step's."""
        return "step" if self.name == "lr" and kind == "decision" else kind


TB = Orient("tb", BOX_W, PORT_MARGIN)
LR = Orient("lr", BOX_W_LR, PORT_MARGIN_LR, HEAD_W_LR)

# The rows drawing is for wide, short screens. Its boxes are as wide as a 3440 x 1440
# window lets them be with every text at 12 px: wider boxes mean shorter labels and a
# shorter drawing, but every px of box width costs one px per layer of drawing width.
ROWS_FIT_W = 3374     # the frame in a 3440 px window (page padding and border)
ROWS_FIT_H = 1220     # what a 1440 px high window leaves below the page header
ROWS_BOX_MAX = 280
ROWS_BOX_STEP = 10
ROWS_BOX_READ = 240   # when no width fits that window: rows are opened by hand, so read well


def box_width_for(spec: Spec, o: "Orient") -> float:
    """o.box_w, or wider if a label holds a piece no line can break (see wrap())."""
    return max([o.box_w] + [longest_piece(n.label) * CHAR_W
                            + (o.box_w - text_width(o.text_kind(n.kind), o.box_w)) + 1
                            for n in spec.nodes])


def rows_orient(spec: Spec) -> Orient:
    """The rows orientation for this spec: the widest box, from ROWS_BOX_MAX down to
    BOX_W_LR in ROWS_BOX_STEP, whose drawing fits ROWS_FIT_W x ROWS_FIT_H at the 12 px
    floor. A layout costs seconds on a long plan, so it starts from an estimate: the
    drawing grows by about one px per layer for each px of box width."""
    def fits(w: int):
        try:
            lay = layout(spec, Orient("lr", w, PORT_MARGIN_LR, HEAD_W_LR))
        except LayoutError:
            return None
        return lay.screen_w * FIT_FLOOR <= ROWS_FIT_W and lay.screen_h * FIT_FLOOR <= ROWS_FIT_H, lay
    base = fits(int(BOX_W_LR))
    if not base or base[1].screen_w * FIT_FLOOR > ROWS_FIT_W:
        return Orient("lr", ROWS_BOX_READ, PORT_MARGIN_LR, HEAD_W_LR)
    room = (ROWS_FIT_W / FIT_FLOOR - base[1].screen_w) / base[1].layers
    w = int(min(ROWS_BOX_MAX, BOX_W_LR + room // ROWS_BOX_STEP * ROWS_BOX_STEP))
    while w > BOX_W_LR:
        got = fits(w)
        if got and got[0]:
            return Orient("lr", w, PORT_MARGIN_LR, HEAD_W_LR)
        w -= ROWS_BOX_STEP
    return Orient("lr", int(BOX_W_LR), PORT_MARGIN_LR, HEAD_W_LR) if base[0] else \
        Orient("lr", ROWS_BOX_READ, PORT_MARGIN_LR, HEAD_W_LR)


@dataclass
class Box:
    """A step's box. u/du: position and extent along the flow; v/dv: across the lanes."""
    id: str
    kind: str
    lane: int
    layer: int
    u: float
    v: float
    du: float
    dv: float
    lines: list
    number: int
    flag: int | None = None
    in_ports: dict = field(default_factory=dict)     # edge order -> v, on the top
    out_ports: dict = field(default_factory=dict)    # edge order -> v, on the bottom
    side_ports: dict = field(default_factory=dict)   # edge order -> u, on the right side

    def rect(self) -> tuple:
        return (self.u, self.v, self.u + self.du, self.v + self.dv)

    def right_at(self, u: float) -> float:
        """The v of the right-hand outline at height u. A decision's side is two slants
        meeting in a point at mid-height; everything else is straight."""
        if self.kind != "decision":
            return self.v + self.dv
        mid = self.u + self.du / 2
        return self.v + self.dv - HEX * abs(u - mid) / (self.du / 2)

    def left_at(self, u: float) -> float:
        """The mirror of right_at: the v of the left-hand outline at height u."""
        return self.v + (self.v + self.dv - self.right_at(u))


@dataclass
class Route:
    edge: Edge
    points: list                      # (u, v) pairs
    loop: bool = False                # drawn as a loop back: side out, side in
    label_rect: tuple | None = None   # u1, v1, u2, v2 of the label's pill


@dataclass
class Layout:
    width: float
    height: float
    boxes: dict
    routes: list
    lane_bands: list          # (v1, v2) per lane
    lane_lines: list          # wrapped lane names
    head_h: float
    box_h: float
    order: list = field(default_factory=list)   # node ids in reading order
    orient: Orient = TB

    @property
    def layers(self) -> int:
        return 1 + max(b.layer for b in self.boxes.values())

    @property
    def screen_w(self) -> float:
        return self.orient.screen(self.height, self.width)[0]

    @property
    def screen_h(self) -> float:
        return self.orient.screen(self.height, self.width)[1]


def assign_layers(spec: Spec) -> tuple[dict, set]:
    """Return ({node id: layer}, {orders of connections that loop back}).

    A step's layer is one past its furthest predecessor, ignoring loops back; a lane holds
    at most one step per layer, so a step that would collide moves one layer further.
    Ties break on spec order, so the same spec always gives the same picture."""
    order = {n.id: n.order for n in spec.nodes}
    outs: dict[str, list[Edge]] = {n.id: [] for n in spec.nodes}
    for e in spec.edges:
        outs[e.src].append(e)
    back: set[int] = set()
    state: dict[str, int] = {}

    def dfs(start: str) -> None:
        # Iterative DFS; a connection to a node still on the stack loops back.
        stack = [(start, iter(outs[start]))]
        state[start] = 1
        while stack:
            cur, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[cur] = 2
                stack.pop()
                continue
            s = state.get(nxt.dst, 0)
            if s == 1:
                back.add(nxt.order)
            elif s == 0:
                state[nxt.dst] = 1
                stack.append((nxt.dst, iter(outs[nxt.dst])))

    for n in spec.nodes:
        if n.kind == "start" and n.id not in state:
            dfs(n.id)

    fwd_in: dict[str, list[str]] = {n.id: [] for n in spec.nodes}
    indeg = {n.id: 0 for n in spec.nodes}
    for e in spec.edges:
        if e.order not in back:
            fwd_in[e.dst].append(e.src)
            indeg[e.dst] += 1
    ready = sorted((order[k], k) for k, v in indeg.items() if v == 0)
    layer: dict[str, int] = {}
    taken: set[tuple[int, int]] = set()
    lane = {n.id: n.lane for n in spec.nodes}
    while ready:
        _, cur = ready.pop(0)
        c = max((layer[p] + 1 for p in fwd_in[cur]), default=0)
        while (lane[cur], c) in taken:
            c += 1
        layer[cur] = c
        taken.add((lane[cur], c))
        for e in outs[cur]:
            if e.order in back:
                continue
            indeg[e.dst] -= 1
            if indeg[e.dst] == 0:
                ready.append((order[e.dst], e.dst))
                ready.sort()
    return layer, back


def even_ports(edges: list, v0: float, dv: float, margin: float = PORT_MARGIN) -> dict:
    span = dv - 2 * margin
    return {e.order: round(v0 + margin + span * (i + 1) / (len(edges) + 1), 1)
            for i, e in enumerate(edges)}


def out_ports(node: Node, edges: list, v0: float, dv: float, o: Orient = TB) -> dict:
    """Outgoing ports along the bottom of a box. A branch label's pill sits just under the
    box, to the right of its own line, so the next line must start past the pill. The
    last pill may run past the box into the lane padding, never into the gutter."""
    m = o.port_margin
    if not any(e.label for e in edges):
        return even_ports(edges, v0, dv, m)
    gaps = [max(PORT_MIN, o.pill_across(e.label) + 8 if e.label else 0) for e in edges[:-1]]
    span = sum(gaps)
    last_w = o.pill_across(edges[-1].label) + 4 if edges[-1].label else 0
    start = v0 + dv / 2 - span / 2
    start = min(start, v0 + dv + LANE_PAD - 6 - last_w - span)
    start = max(start, v0 + m)
    if start + span > v0 + dv - m + 1e-6 or \
            start + span + last_w > v0 + dv + LANE_PAD - 6 + 1e-6:
        raise LayoutError(
            f"the outcome labels of {node.id!r} are too long to sit side by side under the "
            f"box; shorten them (together about {int((dv - 2 * m) // LABEL_CHAR_W)}"
            " characters fit)")
    ports, v = {}, start
    for i, e in enumerate(edges):
        ports[e.order] = round(v, 1)
        if i < len(gaps):
            v += gaps[i]
    return ports


def side_ports(edges: list, u0: float, du: float, gap: float = SIDE_GAP) -> dict:
    """Ports on the right side of a box for loops back, centred on mid-height and one
    pill apart, so a branch label under one line never sits on the next. Loops leaving
    sit above loops arriving: a leaving loop goes up, an arriving one mostly comes up from
    below, and in that order the two never cross at the box."""
    mid = u0 + du / 2
    n = len(edges)
    return {e.order: round(mid + (i - (n - 1) / 2) * gap, 1) for i, e in enumerate(edges)}


def clear_in_ports(boxes: dict, edges: list, margin: float = PORT_MARGIN) -> None:
    """Move a box's in-ports until none sits within PORT_CLEAR of an out-port of the
    nearest box above it in the same lane. Both sets of stubs share the channel between
    the two boxes, and two stubs a couple of pixels apart can never be routed apart:
    every track gives two lines that read as one.

    First choice: a connection straight down from that box keeps its port exactly under
    the out-port (a straight line), and the other in-ports are placed around it. Second
    choice: shift all in-ports sideways as a group."""
    for t in sorted(boxes.values(), key=lambda b: (b.lane, b.layer)):
        above = [b for b in boxes.values() if b.lane == t.lane and b.layer < t.layer]
        if not above or not t.in_ports:
            continue
        s = max(above, key=lambda b: b.layer)
        lo, hi = t.v + margin, t.v + t.dv - margin

        def clear(v: float, own: int | None) -> bool:
            return all(abs(v - sv) >= PORT_CLEAR or sk == own for sk, sv in s.out_ports.items())

        straight = next((e.order for e in edges if e.src == s.id and e.dst == t.id
                         and e.order in s.out_ports and e.order in t.in_ports), None)
        if straight is not None:
            placed = aligned_ports(list(t.in_ports), straight, s.out_ports[straight], lo, hi, clear)
            if placed:
                t.in_ports = placed
                continue
        for off in (step * sign for step in range(0, int(t.dv), 4) for sign in (1, -1)):
            moved = {k: round(v + off, 1) for k, v in t.in_ports.items()}
            if all(lo - 1e-6 <= v <= hi + 1e-6 and clear(v, k) for k, v in moved.items()):
                t.in_ports = moved
                break


def aligned_ports(order: list, anchor_edge: int, anchor: float, lo: float, hi: float,
                  clear: Callable[[float, int | None], bool]) -> dict | None:
    """In-ports with anchor_edge pinned at anchor, the rest walked outwards from it in
    their existing order, each at least PORT_MIN from its neighbour and clear of the box
    above. None if they do not fit on the box."""
    if not lo - 1e-6 <= anchor <= hi + 1e-6:
        return None
    i = order.index(anchor_edge)
    ports = {anchor_edge: anchor}
    for side, step in ((order[i + 1:], 1), (list(reversed(order[:i])), -1)):
        v = anchor
        for k in side:
            v += step * PORT_MIN
            while not clear(v, k):
                v += step * 2
            if not lo - 1e-6 <= v <= hi + 1e-6:
                return None
            ports[k] = round(v, 1)
    return {k: ports[k] for k in order}


def crosses(a: tuple, b: tuple) -> bool:
    """Two segments cross at a right angle, strictly inside both. Touching at an end, or
    running in the same direction, is not a crossing."""
    if a[0] == b[0]:
        return False
    eps = 1e-6
    return a[2] + eps < b[1] < a[3] - eps and b[2] + eps < a[1] < b[3] - eps


def count_crossings(lay: Layout) -> int:
    """How many times one connection crosses another. tests/test_process_diagram.py pins
    a ceiling for examples/23, so a router change that makes the picture busier fails."""
    segs = [(r.edge.order, s) for r in lay.routes for s in segments(r.points)]
    return sum(1 for i, (ea, a) in enumerate(segs) for eb, b in segs[i + 1:]
               if ea != eb and crosses(a, b))


def path_length(pts: list) -> float:
    return sum(abs(u1 - u2) + abs(v1 - v2) for (u1, v1), (u2, v2) in zip(pts, pts[1:]))


@dataclass
class Plan:
    """Everything about a layout that does not depend on how many tracks each gap has:
    layers, which connections loop back, port order, box and header sizes, numbers.
    plan_layout() makes it once; route() places and routes for a given set of capacities."""
    spec: Spec
    layer: dict          # node id -> layer
    back: set            # orders of connections that loop back
    lane: dict           # node id -> lane
    nlayers: int
    nlanes: int
    fwd_out: dict        # node id -> forward connections leaving its bottom, in port order
    fwd_in: dict         # node id -> forward connections entering its top, in port order
    side: dict           # node id -> loops on its right side, leaving above arriving
    lines: dict          # node id -> wrapped label
    box_h: float         # a box's extent along the flow (du)
    lane_lines: list
    head_h: float
    right_pad: dict      # lane -> padding right of its boxes, room for loop pills
    out_zone: dict       # channel -> room under the boxes above it, for branch pills
    number: dict         # node id -> step number
    flags: dict          # node id -> improvement point number
    reading: list        # node ids in reading order
    route_order: list    # connections in the order they are first routed
    o: Orient = TB
    box_dv: float = BOX_W    # a box's extent across the lanes
    side_gap: float = SIDE_GAP
    lane_dv: dict = field(default_factory=dict)   # per lane, when lanes differ (rows)


def plan_layout(spec: Spec, o: Orient = TB) -> Plan:
    layer, back = assign_layers(spec)
    nodes = {n.id: n for n in spec.nodes}
    nlayers = max(layer.values()) + 1
    nlanes = len(spec.lanes)

    lane = {n.id: n.lane for n in spec.nodes}

    def lane_of(i: str) -> int:
        return lane[i]

    fwd_out: dict[str, list] = {n.id: [] for n in spec.nodes}
    fwd_in: dict[str, list] = {n.id: [] for n in spec.nodes}
    side: dict[str, list] = {n.id: [] for n in spec.nodes}
    for e in spec.edges:
        if e.order in back:
            side[e.src].append(e)
            side[e.dst].append(e)
        else:
            fwd_out[e.src].append(e)
            fwd_in[e.dst].append(e)

    # Barycentre ordering. In a swimlane each lane is a column and a layer holds at most
    # one box per lane, so boxes have no freedom inside a layer; what can move is the
    # order of the lines along a box. Each port goes where the other end of its line
    # sits (its lane, then how far away), which is the barycentre of a one-neighbour set.
    for k in fwd_out:
        fwd_out[k].sort(key=lambda e: (lane_of(e.dst) - lane_of(e.src), layer[e.dst], e.order))
        fwd_in[k].sort(key=lambda e: (lane_of(e.src) - lane_of(e.dst), -layer[e.src], e.order))
        leaving = sorted((e for e in side[k] if e.src == k), key=lambda e: (layer[e.dst], e.order))
        arriving = sorted((e for e in side[k] if e.dst == k), key=lambda e: (layer[e.src], e.order))
        side[k] = leaving + arriving

    box_w = box_width_for(spec, o)
    lines = {n.id: wrap(n.label, text_width(o.text_kind(n.kind), box_w), CHAR_W) for n in spec.nodes}
    most_side = max((len(v) for v in side.values()), default=0)
    text_h = max(len(v) for v in lines.values()) * LINE_H + 22
    if o.name == "tb":
        side_gap = SIDE_GAP
        box_h = max(52, text_h, (most_side + 1) * side_gap)
        box_dv = box_w
        lane_lines = [wrap(name, box_w + 2 * LANE_PAD - 2 * HEAD_PAD, CHAR_W_BOLD)
                      for name in spec.lanes]
        head_h = max(len(ll) for ll in lane_lines) * LINE_H + 22
    else:
        # Loops leave along the bottom of a box here, each pill to the right of its line,
        # so two loop ports sit a pill apart. In and out ports share a box's short side,
        # so the box is as tall as they need: PORT_MIN apart, outcome pills stacked.
        side_gap = max([SIDE_GAP] + [pill_width(e.label) + 10 for e in spec.edges
                                     if e.order in back and e.label])
        box_h = max(box_w, (most_side + 1) * side_gap)
        # Wrap to the box as it is drawn, which loop ports may have made wider than box_w.
        lines = {n.id: wrap(n.label, text_width(o.text_kind(n.kind), box_h), CHAR_W) for n in spec.nodes}
        text_h = max(len(v) for v in lines.values()) * LINE_H + 22

        def need(edges: list) -> float:
            if any(e.label for e in edges):
                return sum(max(PORT_MIN, o.pill_across(e.label) + 8 if e.label else 0)
                           for e in edges[:-1]) + PORT_MIN
            return (len(edges) + 1) * PORT_MIN
        lane_lines = [wrap(name, o.head_w - 8 - 2 * HEAD_PAD, CHAR_W_BOLD) for name in spec.lanes]
        head_h = o.head_w
        # Lanes are the short axis here, so each is only as tall as its own boxes need:
        # their labels, their ports, and the lane's name in its header.
        lane_dv = {}
        for ln in range(nlanes):
            mine = [n for n in spec.nodes if lane_of(n.id) == ln]
            lane_dv[ln] = max([52, len(lane_lines[ln]) * LINE_H + 8]
                              + [len(lines[n.id]) * LINE_H + 22 + HEX for n in mine]
                              + [2 * o.port_margin + need(d[n.id]) for n in mine
                                 for d in (fwd_in, fwd_out) if d[n.id]])
        box_dv = max(lane_dv.values())

    # A lane's right padding holds the pills of loops leaving from its boxes.
    right_pad = {ln: LANE_PAD for ln in range(nlanes)}
    for e in spec.edges:
        if e.order in back and e.label:
            ln = lane_of(e.src)
            right_pad[ln] = max(right_pad[ln], o.pill_across(e.label) + 12)

    out_zone = {k: MIN_ZONE for k in range(-1, nlayers)}
    for e in spec.edges:
        if e.label and e.order not in back:
            out_zone[layer[e.src]] = max(out_zone[layer[e.src]], o.pill_along(e.label) + 8)

    # Steps are numbered, and flags too, in reading order: layer, then lane.
    reading = sorted(nodes, key=lambda i: (layer[i], lane_of(i), nodes[i].order))
    number = {i: k + 1 for k, i in enumerate(reading)}
    flags = {}
    for i in reading:
        if nodes[i].improve:
            flags[i] = len(flags) + 1
    route_order = sorted(spec.edges, key=lambda e: (e.order in back,
                                                    abs(layer[e.dst] - layer[e.src]), e.order))
    return Plan(spec, layer, back, lane, nlayers, nlanes, fwd_out, fwd_in, side, lines, box_h,
                lane_lines, head_h, right_pad, out_zone, number, flags, reading, route_order,
                o, box_dv, side_gap, lane_dv if o.name == "lr" else {})


def initial_caps(plan: Plan) -> dict:
    """One track per channel, none in the gutters between lanes, one in the loop gutter of
    every lane that a loop back leaves or enters."""
    cap_loop = {ln: 0 for ln in range(plan.nlanes)}
    for e in plan.spec.edges:
        if e.order in plan.back:
            cap_loop[plan.lane[e.src]] = cap_loop[plan.lane[e.dst]] = 1
    return {"ch": {k: 1 for k in range(-1, plan.nlayers)},
            "gut": {b: 0 for b in range(plan.nlanes + 1)}, "loop": cap_loop}


def needs(plan: Plan, e: Edge) -> list:
    """The track pools a connection draws on, so a failure can grow one of them.

    A forward connection that needs a gutter names only its preferred one, so a failure
    widens the drawing in the one place that serves it best. route() still offers routes
    through any other gutter, but those have tracks only if another connection grew them."""
    ls, lt, ks, kt = plan.lane[e.src], plan.lane[e.dst], plan.layer[e.src], plan.layer[e.dst]
    if e.order in plan.back:
        return [("loop", ls)] if ls == lt else [("loop", ls), ("ch", kt - 1), ("loop", lt)]
    pools = [("ch", ks)]
    if kt - 1 != ks:
        pools += [("gut", gutter_preference(ls, lt, plan.nlanes)[0]), ("ch", kt - 1)]
    return pools


def route(plan: Plan, caps: dict) -> tuple:
    """Place and route everything once, for the given capacities. Returns (Layout, None),
    or (None, pools) naming what the first connection that could not be routed needed."""
    spec, layer, back, nlayers, nlanes = plan.spec, plan.layer, plan.back, plan.nlayers, plan.nlanes
    fwd_out, fwd_in, side, lines, box_h = plan.fwd_out, plan.fwd_in, plan.side, plan.lines, plan.box_h
    lane_lines, head_h, right_pad, out_zone = plan.lane_lines, plan.head_h, plan.right_pad, plan.out_zone
    number, flags, reading, route_order = plan.number, plan.flags, plan.reading, plan.route_order
    cap_ch, cap_gut, cap_loop = caps["ch"], caps["gut"], caps["loop"]
    o = plan.o
    dv_of = lambda ln: plan.lane_dv.get(ln, plan.box_dv)  # noqa: E731

    # ---- place lanes and layers for the current track capacities
    gut_left: dict[int, float] = {}
    box_left: dict[int, float] = {}
    loop_left: dict[int, float] = {}
    v = MARGIN
    for b in range(nlanes + 1):
        gut_left[b] = v
        v += (cap_gut[b] + 1) * TRACK
        if b < nlanes:
            box_left[b] = v + LANE_PAD
            loop_left[b] = box_left[b] + dv_of(b) + right_pad[b]
            v = loop_left[b] + ((cap_loop[b] + 1) * TRACK if cap_loop[b] else 0)
    width = v + MARGIN

    ch_top: dict[int, float] = {}
    row_top: dict[int, float] = {}
    u = MARGIN + head_h
    for k in range(-1, nlayers):
        if k >= 0:
            row_top[k] = u
            u += box_h
        ch_top[k] = u
        u += out_zone[k] + (cap_ch[k] + 1) * TRACK + MIN_ZONE
    height = u + MARGIN

    def track_u(k: int, i: int) -> float:
        return ch_top[k] + out_zone[k] + (i + 1) * TRACK

    def gut_v(b: int, j: int) -> float:
        return gut_left[b] + (j + 1) * TRACK

    def loop_v(ln: int, j: int) -> float:
        return loop_left[ln] + (j + 1) * TRACK

    boxes: dict[str, Box] = {}
    for n in spec.nodes:
        bv, bu = box_left[n.lane], row_top[layer[n.id]]
        box_dv = dv_of(plan.lane[n.id])
        b = Box(n.id, n.kind, n.lane, layer[n.id], bu, bv, box_h, box_dv, lines[n.id],
                number[n.id], flags.get(n.id))
        b.in_ports = even_ports(fwd_in[n.id], bv, box_dv, o.port_margin)
        b.out_ports = out_ports(n, fwd_out[n.id], bv, box_dv, o)
        b.side_ports = side_ports(side[n.id], bu, box_h, plan.side_gap)
        boxes[n.id] = b
    clear_in_ports(boxes, spec.edges, o.port_margin)
    occupied = {(b.lane, b.layer) for b in boxes.values()}

    labels: dict[int, tuple] = {}
    for e in spec.edges:
        if not e.label:
            continue
        s = boxes[e.src]
        if e.order in back:
            pu, pv = s.side_ports[e.order], s.right_at(s.side_ports[e.order])
        else:
            pu, pv = s.u + s.du, s.out_ports[e.order]
        labels[e.order] = (pu + 3, pv + 4, pu + 3 + o.pill_along(e.label),
                           pv + 4 + o.pill_across(e.label))

    placed: dict[int, list] = {}   # edge order -> its segments

    def ok(pts: list, e: Edge) -> bool:
        segs = segments(pts)
        for idx, seg in enumerate(segs):
            for b in boxes.values():
                if (idx == 0 and b.id == e.src) or (idx == len(segs) - 1 and b.id == e.dst):
                    continue
                if seg_hits_rect(seg, b.rect(), 3):
                    return False
            for other, osegs in placed.items():
                if other == e.order:
                    continue
                for o, fixed, lo, hi in osegs:
                    if o == seg[0] and abs(fixed - seg[1]) < MIN_SEP \
                            and lo < seg[3] + MIN_SEP and hi > seg[2] - MIN_SEP:
                        return False
            for order, rect in labels.items():
                if order != e.order and seg_hits_rect(seg, rect, 1):
                    return False
        return True

    def cost(pts: list, e: Edge) -> float:
        segs = segments(pts)
        n_cross = sum(1 for other, osegs in placed.items() if other != e.order
                      for a in segs for b in osegs if crosses(a, b))
        return n_cross * CROSS_COST + path_length(pts) + (len(segs) - 1) * BEND_COST

    def candidates(e: Edge):
        s, t = boxes[e.src], boxes[e.dst]
        ks, kt = s.layer, t.layer
        if e.order in back:
            us, ut = s.side_ports[e.order], t.side_ports[e.order]
            vs, vt = s.right_at(us), t.right_at(ut)
            if s.lane == t.lane:
                for j in range(cap_loop[s.lane]):
                    x = loop_v(s.lane, j)
                    yield [(us, vs), (us, x), (ut, x), (ut, vt)]
                return
            if t.lane == s.lane + 1:
                # The source lane's loop gutter runs right beside the target's left
                # side, so the loop can climb it and enter there: shorter, and it
                # never crosses the channel above the target.
                for j in range(cap_loop[s.lane]):
                    x = loop_v(s.lane, j)
                    yield [(us, vs), (us, x), (ut, x), (ut, t.left_at(ut))]
            for j in range(cap_loop[s.lane]):
                for i in range(cap_ch[kt - 1]):
                    for j2 in range(cap_loop[t.lane]):
                        x1, x2, uc = loop_v(s.lane, j), loop_v(t.lane, j2), track_u(kt - 1, i)
                        yield [(us, vs), (us, x1), (uc, x1), (uc, x2), (ut, x2), (ut, vt)]
            return
        us, vs = s.u + s.du, s.out_ports[e.order]
        ut, vt = t.u, t.in_ports[e.order]
        direct = kt > ks and all((t.lane, k) not in occupied for k in range(ks + 1, kt))
        if direct and abs(vs - vt) < 1e-6:
            yield [(us, vs), (ut, vt)]
        elif direct:
            # A jog through the channel, only when the ports are apart. With them in line
            # it would be the straight drop with a bend that does not turn, sitting on a
            # track; crosses() cannot see a line cross where the other one "bends", so
            # that fake bend hid a crossing and won (and rounded_path divided by zero).
            for i in range(cap_ch[ks]):
                ui = track_u(ks, i)
                yield [(us, vs), (ui, vs), (ui, vt), (ut, vt)]
        if kt - 1 != ks:
            for b in gutter_preference(s.lane, t.lane, nlanes):
                for j in range(cap_gut[b]):
                    for i in range(cap_ch[ks]):
                        for k in range(cap_ch[kt - 1]):
                            yield [(us, vs), (track_u(ks, i), vs), (track_u(ks, i), gut_v(b, j)),
                                   (track_u(kt - 1, k), gut_v(b, j)), (track_u(kt - 1, k), vt),
                                   (ut, vt)]

    def best(e: Edge) -> tuple | None:
        scored = ((cost(p, e), p) for p in candidates(e) if ok(p, e))
        return min(scored, key=lambda cp: cp[0], default=None)

    chosen: dict[int, list] = {}
    for e in route_order:
        found = best(e)
        if found is None:
            return None, needs(plan, e)
        chosen[e.order] = found[1]
        placed[e.order] = segments(found[1])

    for _pass in range(RIPUP_PASSES):
        improved = False
        for e in route_order:
            current = cost(chosen[e.order], e)
            del placed[e.order]
            found = best(e)
            if found is not None and found[0] < current - 1e-6:
                chosen[e.order] = found[1]
                improved = True
            placed[e.order] = segments(chosen[e.order])
        if not improved:
            break
    routes = [Route(e, chosen[e.order], e.order in back, labels.get(e.order))
              for e in spec.edges]
    bands = [(gut_left[ln], gut_left[ln + 1] if ln + 1 < nlanes else width - MARGIN)
             for ln in range(nlanes)]
    return Layout(width, height, boxes, routes, bands, lane_lines, head_h, box_h,
                  reading, o), None


def layout(spec: Spec, o: Orient = TB) -> Layout:
    """Place every box and route every connection.

    Forward connections leave a box's bottom and enter the top of a box further down,
    through the channels between layers and, when a straight drop is blocked, a gutter
    between lanes. Loops back leave the right side, climb in their lane's own loop gutter,
    and enter the target's right side (or its left side, when the target's lane is the
    next one to the right), so they stay out of the middle of the drawing.

    Each connection takes the cheapest route that breaks no rule, where a crossing costs
    far more than length: CROSS_COST per crossing, plus length, plus BEND_COST per bend.
    After everything is routed, each connection is torn up and re-routed against all the
    others, up to RIPUP_PASSES times, because the first ones routed could not see the
    rest. If a gap runs out of tracks it gets one more and everything starts again."""
    plan = plan_layout(spec, o)
    caps = initial_caps(plan)
    # Grow the scarcest pool the failed connection needed until everything routes.
    for _attempt in range(400):
        lay, failed = route(plan, caps)
        if lay is not None:
            break
        kind, key = min(failed, key=lambda r: caps[r[0]][r[1]])
        caps[kind][key] += 1
        if caps[kind][key] > len(spec.edges) + 2:
            break
    if lay is None:
        raise LayoutError(
            f"{spec.name}: could not route every connection without lines running into each "
            "other. Reorder the 'flow' lines, or split a step that has many connections.")

    # Then buy crossings away with space. Two lines can block each other from swapping
    # tracks, and no single re-route fixes that; one more track in a pool they use often
    # does. Each extra track is kept only if the drawing gets fewer crossings.
    for _try in range(EXTRA_TRACK_TRIES):
        current = count_crossings(lay)
        if current == 0:
            break
        crossing = {r.edge.order for r in lay.routes for o in lay.routes if o is not r
                    and any(crosses(a, b) for a in segments(r.points) for b in segments(o.points))}
        pools = sorted({p for e in spec.edges if e.order in crossing for p in needs(plan, e)})
        for kind, key in pools:
            caps[kind][key] += 1
            trial, _ = route(plan, caps)
            if trial is not None and count_crossings(trial) < current:
                lay = trial
                break
            caps[kind][key] -= 1
        else:
            break
    return lay


def gutter_preference(ls: int, lt: int, nlanes: int) -> list[int]:
    """Which gutter a forward connection should travel in, best first. Gutter b runs left
    of lane b; gutter nlanes is right of the last lane. Loops back never use these: they
    have their lane's own loop gutter."""
    if ls == lt:
        first = [ls, ls + 1]
    elif lt > ls:
        first = list(range(ls + 1, lt + 1))
    else:
        first = list(range(ls, lt, -1))
    rest = sorted((b for b in range(nlanes + 1) if b not in first),
                  key=lambda b: (min(abs(b - ls), abs(b - lt)), b))
    return first + rest


def segments(pts: list) -> list:
    """Axis-aligned segments of a polyline: ("u", v, lo, hi) runs along the flow at a
    fixed v; ("v", u, lo, hi) runs across the lanes at a fixed u. Zero-length dropped."""
    segs = []
    for (u1, v1), (u2, v2) in zip(pts, pts[1:]):
        if abs(v1 - v2) < 1e-6 and abs(u1 - u2) > 1e-6:
            segs.append(("u", v1, min(u1, u2), max(u1, u2)))
        elif abs(u1 - u2) < 1e-6 and abs(v1 - v2) > 1e-6:
            segs.append(("v", u1, min(v1, v2), max(v1, v2)))
    return segs


def seg_hits_rect(seg: tuple, rect: tuple, pad: float) -> bool:
    """Does a segment pass through the interior of a (u1, v1, u2, v2) rectangle grown by
    pad? Touching the outline from outside does not count."""
    u1, v1, u2, v2 = rect[0] - pad, rect[1] - pad, rect[2] + pad, rect[3] + pad
    o, fixed, lo, hi = seg
    if o == "u":
        return v1 < fixed < v2 and lo < u2 and hi > u1
    return u1 < fixed < u2 and lo < v2 and hi > v1


def rects_overlap(a: tuple, b: tuple) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def check_layout(lay: Layout) -> list[str]:
    """Re-check the finished geometry. Returns a list of problems; empty means sound.

    Independent of how the router got there, so a router change that breaks a property is
    caught here rather than shipped. tests/test_process_diagram.py breaks each property on
    purpose to prove this function notices."""
    problems: list[str] = []
    boxes = list(lay.boxes.values())
    o = lay.orient
    m = o.port_margin
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if rects_overlap(a.rect(), b.rect()):
                problems.append(f"boxes overlap: {a.id} and {b.id}")
        if len(a.lines) * LINE_H + 2 > o.screen(a.du, a.dv)[1]:
            problems.append(f"label of {a.id} is taller than its box")
        for ln in a.lines:
            if len(ln) * CHAR_W > text_width(o.text_kind(a.kind), o.screen(a.du, a.dv)[0]) + 1e-6:
                problems.append(f"a label line of {a.id} is wider than its box: {ln!r}")
    by_route = []
    for r in lay.routes:
        e, pts = r.edge, r.points
        name = f"{e.src}->{e.dst}"
        if len(pts) < 2:
            problems.append(f"{name}: fewer than two points")
            continue
        for (u1, v1), (u2, v2) in zip(pts, pts[1:]):
            if abs(u1 - u2) > 1e-6 and abs(v1 - v2) > 1e-6:
                problems.append(f"{name}: a diagonal segment")
            elif abs(u1 - u2) <= 1e-6 and abs(v1 - v2) <= 1e-6:
                problems.append(f"{name}: a zero-length segment (a point repeated)")
        # A middle point where the line goes straight on is a bend that does not turn.
        # Nothing draws it, and it splits a segment where another line may cross, so
        # crossing counts that go by segments would miss that crossing.
        for (u1, v1), (u2, v2), (u3, v3) in zip(pts, pts[1:], pts[2:]):
            if (abs(u1 - u2) <= 1e-6 and abs(u2 - u3) <= 1e-6) or \
                    (abs(v1 - v2) <= 1e-6 and abs(v2 - v3) <= 1e-6):
                problems.append(f"{name}: a bend that does not turn at ({fmt(u2)}, {fmt(v2)})")
        if any(not (0 <= u <= lay.height and 0 <= v <= lay.width) for u, v in pts):
            problems.append(f"{name}: leaves the drawing")
        s, t = lay.boxes[e.src], lay.boxes[e.dst]
        (su, sv), (tu, tv) = pts[0], pts[-1]
        if r.loop:
            # A loop leaves the right side going right, and enters a side from outside:
            # the right side going left, or the left side going right.
            if not (s.u < su < s.u + s.du and abs(sv - s.right_at(su)) <= 1 and pts[1][1] > sv):
                problems.append(f"{name}: does not leave from the right side of {e.src}")
            from_right = abs(tv - t.right_at(tu)) <= 1 and pts[-2][1] > tv
            from_left = abs(tv - t.left_at(tu)) <= 1 and pts[-2][1] < tv
            if not (t.u < tu < t.u + t.du and (from_right or from_left)):
                problems.append(f"{name}: does not arrive at a side of {e.dst}")
        else:
            # Ports stay on the flat part of the outline, clear of rounded or pointed ends.
            if abs(su - (s.u + s.du)) > 1 or not s.v + m - 1 <= sv <= s.v + s.dv - m + 1:
                problems.append(f"{name}: does not leave from the bottom of {e.src}")
            if abs(tu - t.u) > 1 or not t.v + m - 1 <= tv <= t.v + t.dv - m + 1:
                problems.append(f"{name}: does not arrive at the top of {e.dst}")
        segs = segments(pts)
        for idx, seg in enumerate(segs):
            for b in boxes:
                if (idx == 0 and b.id == e.src) or (idx == len(segs) - 1 and b.id == e.dst):
                    continue
                if seg_hits_rect(seg, b.rect(), 0):
                    problems.append(f"{name}: runs through the box of {b.id}")
        if segs and segs[-1][3] - segs[-1][2] < MIN_ZONE - 1e-6:
            problems.append(f"{name}: the last stretch is too short for its arrowhead")
        by_route.append((r, segs))
    for i, (ra, sa) in enumerate(by_route):
        for rb, sb in by_route[i + 1:]:
            if any(a[0] == b[0] and abs(a[1] - b[1]) < MIN_SEP and a[2] < b[3] and b[2] < a[3]
                   for a in sa for b in sb):
                problems.append(f"{ra.edge.src}->{ra.edge.dst} and "
                                f"{rb.edge.src}->{rb.edge.dst} run along each other")
    labelled = [r for r in lay.routes if r.label_rect]
    for i, r in enumerate(labelled):
        for b in boxes:
            if rects_overlap(r.label_rect, b.rect()):
                problems.append(f"label [{r.edge.label}] covers the box of {b.id}")
        for o in labelled[i + 1:]:
            if rects_overlap(r.label_rect, o.label_rect):
                problems.append(f"labels [{r.edge.label}] and [{o.edge.label}] overlap")
        for o, segs in by_route:
            if o is not r and any(seg_hits_rect(seg, r.label_rect, 0) for seg in segs):
                problems.append(f"label [{r.edge.label}] is crossed by "
                                f"{o.edge.src}->{o.edge.dst}")
    return problems


# --------------------------------------------------------------------------- render
def esc(text: str) -> str:
    """HTML-escape, and neutralise '{' so user text can never look like a {{TOKEN}}."""
    return html.escape(text, quote=True).replace("{", "&#123;").replace("}", "&#125;")


def fmt(n: float) -> str:
    return f"{n:.1f}".rstrip("0").rstrip(".")


def corners(pts: list) -> list:
    """The points where a polyline really turns, plus both ends: repeated points and
    points it runs straight through are dropped. check_layout() rejects a route that has
    either, so this changes nothing in a sound drawing; it keeps the two drawing functions
    below from dividing by a zero length if one ever gets through."""
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) <= 1e-6 and abs(p[1] - out[-1][1]) <= 1e-6:
            continue
        if len(out) >= 2:
            (ax, ay), (bx, by) = out[-2], out[-1]
            if (abs(ax - bx) <= 1e-6 and abs(bx - p[0]) <= 1e-6) or \
                    (abs(ay - by) <= 1e-6 and abs(by - p[1]) <= 1e-6):
                out[-1] = p
                continue
        out.append(p)
    return out


def rounded_path(pts: list) -> str:
    """An SVG path through screen points with every bend rounded by a quadratic curve.
    The curve's control point is the original corner, so the path still names every
    corner of the route: tools/verify_process_diagram.py rebuilds the polyline from it."""
    pts = corners(pts)
    d = [f"M{fmt(pts[0][0])} {fmt(pts[0][1])}"]
    for (ax, ay), (cx, cy), (bx, by) in zip(pts, pts[1:], pts[2:]):
        la, lb = abs(cx - ax) + abs(cy - ay), abs(bx - cx) + abs(by - cy)
        r = min(CORNER, la / 2, lb / 2)

        def toward(px: float, py: float, length: float) -> tuple:
            return (cx + (px - cx) * r / length, cy + (py - cy) * r / length)

        (x1, y1), (x2, y2) = toward(ax, ay, la), toward(bx, by, lb)
        d.append(f"L{fmt(x1)} {fmt(y1)} Q{fmt(cx)} {fmt(cy)} {fmt(x2)} {fmt(y2)}")
    d.append(f"L{fmt(pts[-1][0])} {fmt(pts[-1][1])}")
    return " ".join(d)


def arrowhead(pts: list) -> str:
    """A filled triangle whose tip is the route's last point, pointing along the last
    stretch. Drawn as its own shape rather than an SVG marker so it takes the line's
    highlight colour in every engine and prints the same."""
    (ax, ay), (bx, by) = corners(pts)[-2:]
    length = abs(bx - ax) + abs(by - ay)
    dx, dy = (bx - ax) / length, (by - ay) / length
    cx, cy = bx - dx * ARROW_L, by - dy * ARROW_L
    px, py = -dy * ARROW_W / 2, dx * ARROW_W / 2
    return (f"M{fmt(bx)} {fmt(by)} L{fmt(cx + px)} {fmt(cy + py)} "
            f"L{fmt(cx - px)} {fmt(cy - py)} Z")


def render_svg(spec: Spec, lay: Layout) -> str:
    """The only function that maps (u, v) to the screen: lay.orient.screen() (x = v, y = u
    for columns, x = u, y = v for rows).

    Output contract: every lane, connection and node is ONE line, starting with
    '<g class="lane', '<g class="edge"' or '<g class="node node-'. The text alternative
    does the same with '<li data-node='. tools/verify_process_diagram.py --mutation-check
    edits copies by those lines, and tests/test_process_diagram.py pins the counts. The
    columns drawing comes first in the page, so a mutation of the first such line breaks
    the drawing that shows by default."""
    o = lay.orient
    tb = o.name == "tb"
    pid = "pd" if tb else "pd-lr"            # ids, unique when the page carries both drawings
    sw, sh = lay.screen_w, lay.screen_h
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="pd pd-{o.name}{" on" if tb else ""}" '
        f'data-orient="{o.name}" width="{fmt(sw)}" '
        f'height="{fmt(sh)}" viewBox="0 0 {fmt(sw)} {fmt(sh)}" '
        f'role="img" aria-labelledby="{pid}-title {pid}-desc" font-size="{FONT}">',
        f'<title id="{pid}-title">{esc(spec.title)}</title>',
        f'<desc id="{pid}-desc">' + i18n.fill(
            T["svg_desc"], steps=i18n.plural(T, "n_steps", len(spec.nodes)),
            lanes=i18n.plural(T, "n_lanes", len(spec.lanes))) + '</desc>',
        f'<defs><filter id="{pid}-shadow" x="-10%" y="-20%" width="120%" height="150%">'
        '<feDropShadow dx="0" dy="2" stdDeviation="2.2" flood-opacity="0.22"/>'
        '</filter></defs>',
        '<g class="lanes">',
    ]
    body_top, body_h = MARGIN + lay.head_h, lay.height - 2 * MARGIN - lay.head_h
    for i, (name, (x1, x2)) in enumerate(zip(spec.lanes, lay.lane_bands)):
        ll = lay.lane_lines[i]
        head_h = lay.head_h - 8
        if tb:
            cx = (x1 + x2) / 2
            ty = MARGIN + 4 + (head_h - 4 - len(ll) * LINE_H) / 2 + 13.5
            band = (x1, body_top, x2 - x1, body_h)
            head = (x1 + 2, MARGIN, x2 - x1 - 4, head_h)
            stripe = (x1 + 2, MARGIN, x2 - x1 - 4, 4)
        else:
            # The lane's name sits in a column on the left, its colour stripe on the left edge.
            cx = MARGIN + 4 + (head_h - 4) / 2
            ty = (x1 + x2) / 2 - len(ll) * LINE_H / 2 + 13.5
            band = (body_top, x1, body_h, x2 - x1)
            head = (MARGIN, x1 + 2, head_h, x2 - x1 - 4)
            stripe = (MARGIN, x1 + 2, 4, x2 - x1 - 4)
        tspans = "".join(f'<tspan x="{fmt(cx)}" dy="{0 if j == 0 else LINE_H}">{esc(t)}</tspan>'
                         for j, t in enumerate(ll))
        rect = lambda r: (f'x="{fmt(r[0])}" y="{fmt(r[1])}" '  # noqa: E731
                          f'width="{fmt(r[2])}" height="{fmt(r[3])}"')
        out.append(
            f'<g class="lane {lane_class(i)}" data-lane="{i}">'
            f'<rect class="lane-band" {rect(band)}/>'
            f'<rect class="lane-head" {rect(head)} rx="8"/>'
            f'<rect class="lane-stripe" {rect(stripe)} rx="2"/>'
            f'<text class="lane-name" x="{fmt(cx)}" y="{fmt(ty)}" text-anchor="middle" '
            f'font-weight="700">{tspans}</text></g>')
    out.append('</g>')
    out.append('<g class="edges">')
    for r in lay.routes:
        pts = [o.screen(u, v) for u, v in r.points]
        label = ""
        if r.edge.label:
            u1, v1, u2, v2 = r.label_rect
            (x1, y1), (x2, y2) = o.screen(u1, v1), o.screen(u2, v2)
            label = (f'<g class="edge-label"><rect class="pill" x="{fmt(x1)}" y="{fmt(y1)}" '
                     f'width="{fmt(x2 - x1)}" height="{fmt(y2 - y1)}" rx="{fmt(PILL_H / 2)}"/>'
                     f'<text x="{fmt((x1 + x2) / 2)}" y="{fmt(y1 + PILL_H / 2 + BASELINE * LABEL_FONT)}" text-anchor="middle" '
                     f'font-size="{LABEL_FONT}">{esc(r.edge.label)}</text></g>')
        loop = ' data-loop="1"' if r.loop else ""
        out.append(
            f'<g class="edge" data-from="{esc(r.edge.src)}" data-to="{esc(r.edge.dst)}"{loop}>'
            f'<path class="edge-line" d="{rounded_path(pts)}"/>'
            f'<path class="edge-arrow" d="{arrowhead(pts)}"/>{label}</g>')
    out.append('</g>')
    out.append('<g class="nodes">')
    for node_id in lay.order:
        n = spec.node(node_id)
        b = lay.boxes[node_id]
        bx0, by0 = o.screen(b.u, b.v)
        w, h = o.screen(b.du, b.dv)
        if b.kind == "decision" and tb:
            pts = (f"{HEX},0 {fmt(w - HEX)},0 {fmt(w)},{fmt(h / 2)} {fmt(w - HEX)},{fmt(h)} "
                   f"{HEX},{fmt(h)} 0,{fmt(h / 2)}")
        elif b.kind == "decision":
            # The points stick out across the flow, as in columns: here that is up and down.
            pts = (f"0,{HEX} {fmt(w / 2)},0 {fmt(w)},{HEX} {fmt(w)},{fmt(h - HEX)} "
                   f"{fmt(w / 2)},{fmt(h)} 0,{fmt(h - HEX)}")
        if b.kind == "decision":
            shape = f'<polygon class="node-shape" points="{pts}" filter="url(#{pid}-shadow)"/>'
        else:
            rx = min(h / 2, 24) if b.kind in ("start", "end") else 6
            shape = (f'<rect class="node-shape" width="{fmt(w)}" height="{fmt(h)}" '
                     f'rx="{fmt(rx)}" filter="url(#{pid}-shadow)"/>')
        left, right = text_span(o.text_kind(b.kind), w)
        tx = (left + right) / 2
        first = (h - len(b.lines) * LINE_H) / 2 + 13.5
        # A space ends every line but the last, and the step number. SVG does not draw
        # it, but a screen reader and a speech-input user read the words apart:
        # "spørsmålet og", not "spørsmåletog" (axe label-content-name-mismatch).
        last = len(b.lines) - 1
        tspans = "".join(f'<tspan x="{fmt(tx)}" dy="{0 if j == 0 else LINE_H}">{esc(t)}'
                         f'{" " if j < last else ""}</tspan>' for j, t in enumerate(b.lines))
        nx = inset(o.text_kind(b.kind)) + NUM_R + 2
        number = (f'<g class="step-no"><circle cx="{fmt(nx)}" cy="{fmt(h / 2)}" r="{NUM_R}"/>'
                  f'<text x="{fmt(nx)}" y="{fmt(h / 2 + BASELINE * LABEL_FONT)}" text-anchor="middle" '
                  f'font-size="{LABEL_FONT}" font-weight="700">{b.number} </text></g>')
        tip = f"{b.number}. {n.label}" + (f" ({T['flag']} {b.flag}: {n.improve.text})"
                                          if n.improve else "")
        badge = ""
        if b.flag:
            # On the top right corner of the outline.
            bx = w - HEX if b.kind == "decision" and tb else w
            by = HEX if b.kind == "decision" and not tb else 0
            # A sibling of the node, not a child: the node is a button, and its name already
            # says "Forbedringspunkt {flag}". A bare digit inside it would not match the name.
            badge = (f'<g class="flag-badge" data-node="{esc(node_id)}" data-lane="{b.lane}" '
                     f'aria-hidden="true" transform="translate({fmt(bx0)} {fmt(by0)})">'
                     f'<circle cx="{fmt(bx)}" cy="{fmt(by)}" r="{BADGE_R}"/>'
                     f'<text x="{fmt(bx)}" y="{fmt(by + BASELINE * LABEL_FONT)}" text-anchor="middle" font-size="{LABEL_FONT}" '
                     f'font-weight="700">{b.flag}</text></g>')
        classes = f"node node-{b.kind} {lane_class(b.lane)}" + (" flagged" if b.flag else "")
        out.append(
            f'<g class="{classes}" data-node="{esc(node_id)}" data-lane="{b.lane}" '
            f'transform="translate({fmt(bx0)} {fmt(by0)})"><title>{esc(tip)}</title>{shape}'
            f'{number}<text class="node-label" x="{fmt(tx)}" y="{fmt(first)}" '
            f'text-anchor="middle">{tspans}</text></g>{badge}')
    out.append('</g>')
    out.append('</svg>')
    return "\n".join(out)


def size_css(*lays: Layout) -> str:
    """Per drawing, how far the page may shrink and grow it (see FIT_FLOOR, FIT_CEILING)."""
    return "\n".join(f".pd-{lay.orient.name}{{max-width:{fmt(math.floor(lay.screen_w * FIT_CEILING))}px;"
                     f"min-width:{fmt(math.ceil(lay.screen_w * FIT_FLOOR))}px}}" for lay in lays)


def lane_class(i: int) -> str:
    """Role colours cycle through LANE_COLOURS classes; the template maps each to a token."""
    return f"c{i % LANE_COLOURS}"


def step_ref(spec: Spec, lay: Layout, node_id: str, lane: bool = True) -> str:
    n, b = spec.node(node_id), lay.boxes[node_id]
    return (f"{b.number}. {T['q_open']}{esc(n.label)}{T['q_close']}"
            + (f" ({esc(spec.lanes[n.lane])})" if lane else ""))


def render_text_alternative(spec: Spec, lay: Layout) -> str:
    """Every step, per lane, in flow order, with where each one leads. This is what a
    screen reader reads, what the SharePoint preview can show, and what prints last."""
    nodes = {n.id: n for n in spec.nodes}
    lane_name = spec.lanes

    def target(e: Edge) -> str:
        t = nodes[e.dst]
        return f"{T['q_open']}{esc(t.label)}{T['q_close']} ({esc(lane_name[t.lane])})"

    parts = []
    for li, lane in enumerate(spec.lanes):
        items = [i for i in lay.order if nodes[i].lane == li]
        parts.append(f'<h3>{esc(lane)}</h3>\n<ol class="lane-steps">')
        for node_id in items:
            n = nodes[node_id]
            outs = [e for e in spec.edges if e.src == node_id]
            b = lay.boxes[node_id]
            stop = "" if n.label.rstrip()[-1:] in ".?!:" else "."
            body = f'<strong>{T[n.kind]} {b.number}:</strong> {esc(n.label)}{stop}'
            if n.kind == "decision":
                branches = "".join(
                    f'<li data-from="{esc(e.src)}" data-to="{esc(e.dst)}">{T["if"]} {T["q_open"]}{esc(e.label)}{T["q_close"]}: '
                    f'{T["next"].lower()} {target(e)}.</li>' for e in outs)
                body += f'\n  <ul class="branches">{branches}</ul>'
            elif outs:
                nexts = f' {T["and"]} '.join(
                    f'<span data-from="{esc(e.src)}" data-to="{esc(e.dst)}">{target(e)}'
                    + (f' [{esc(e.label)}]' if e.label else "") + '</span>' for e in outs)
                body += f' {T["next"]} {nexts}.'
            if n.improve:
                body += (f'\n  <p class="flag-note">{T["flag"]} {b.flag}: '
                         f'{esc(n.improve.text)}</p>')
            parts.append(f'<li data-node="{esc(node_id)}">{body}</li>')
        parts.append('</ol>')
    return "\n".join(parts)


def facts(rows: list) -> str:
    """A <dl> of (term, html) rows, skipping empty ones."""
    items = "".join(f'<div><dt>{t}</dt><dd>{d}</dd></div>' for t, d in rows if d)
    return f'<dl class="facts">{items}</dl>' if items else ""


def show_in_flow(node_id: str) -> str:
    return (f'<p class="card-actions"><button type="button" class="show-in-flow" '
            f'data-node="{esc(node_id)}">{T["show"]}</button></p>')


def render_steps(spec: Spec, lay: Layout) -> str:
    """One card per step, in reading order: what the spec says about it, where it leads
    and where it comes from. The detail panel in «Flyt» shows a copy of the same card."""
    cards = []
    for node_id in lay.order:
        n, b = spec.node(node_id), lay.boxes[node_id]
        outs = [e for e in spec.edges if e.src == node_id]
        ins = [e for e in spec.edges if e.dst == node_id]
        nexts = "<br>".join(step_ref(spec, lay, e.dst) + (f' [{esc(e.label)}]' if e.label else "")
                            for e in outs)
        prevs = "<br>".join(step_ref(spec, lay, e.src) + (f' [{esc(e.label)}]' if e.label else "")
                            for e in ins)
        rows = [(T["role"], esc(spec.lanes[n.lane]))]
        rows += [(T[k], esc(n.fields[k])) for k in ("description", "input", "output",
                                                     "tool", "duration") if k in n.fields]
        rows += [(T["from"], prevs), (T["to"], nexts)]
        flag = ""
        if n.improve:
            extra = "".join(f'<p><strong>{T[k]}:</strong> {esc(getattr(n.improve, k))}</p>'
                            for k in ("problem", "proposal") if getattr(n.improve, k))
            flag = (f'<div class="card-flag"><p><span class="badge">{b.flag}</span> '
                    f'<strong>{T["flag"]} {b.flag}:</strong> {esc(n.improve.text)}</p>{extra}</div>')
        cards.append(
            f'<article class="card step-card {lane_class(n.lane)}" id="step-{esc(node_id)}" '
            f'data-node="{esc(node_id)}">'
            f'<header class="card-head"><span class="num">{b.number}</span>'
            f'<h3>{esc(n.label)}</h3></header>'
            f'<p class="card-kind">{T[n.kind]}</p>{facts(rows)}{flag}{show_in_flow(node_id)}'
            '</article>')
    return '<div class="cards">\n' + "\n".join(cards) + '\n</div>'


def render_roles(spec: Spec, lay: Layout) -> str:
    """Per role: its steps in order, and every hand-off into and out of the lane."""
    nodes = {n.id: n for n in spec.nodes}
    cards = []
    for li, lane in enumerate(spec.lanes):
        mine = [i for i in lay.order if nodes[i].lane == li]
        steps = "".join(f'<li data-step="{esc(i)}">{step_ref(spec, lay, i, lane=False)}</li>'
                        for i in mine)
        handins = [e for e in spec.edges if nodes[e.dst].lane == li and nodes[e.src].lane != li]
        handouts = [e for e in spec.edges if nodes[e.src].lane == li and nodes[e.dst].lane != li]

        def handoffs(edges: list) -> str:
            if not edges:
                return f'<p class="none">{T["none"]}</p>'
            return "<ul>" + "".join(
                f'<li data-from="{esc(e.src)}" data-to="{esc(e.dst)}">{step_ref(spec, lay, e.src)} '
                f'→ {step_ref(spec, lay, e.dst)}' + (f' [{esc(e.label)}]' if e.label else "")
                + "</li>" for e in edges) + "</ul>"

        cards.append(
            f'<section class="card role-card {lane_class(li)}" data-lane="{li}">'
            f'<header class="card-head"><span class="dot" aria-hidden="true"></span>'
            f'<h3>{esc(lane)}</h3></header>'
            f'<p class="card-kind">{i18n.plural(T, "n_steps", len(mine))} · '
            f'{i18n.fill(T["role_in"], n=len(handins))} · '
            f'{i18n.fill(T["role_out"], n=len(handouts))}</p>'
            f'<h4>{T["steps"]}</h4><ul class="role-steps">{steps}</ul>'
            f'<h4>{T["handins"]}</h4>{handoffs(handins)}'
            f'<h4>{T["handouts"]}</h4>{handoffs(handouts)}</section>')
    return '<div class="cards">\n' + "\n".join(cards) + '\n</div>'


def render_flags(spec: Spec, lay: Layout) -> str:
    """Each improvement point with the step it belongs to, the problem and the proposal."""
    flagged = [i for i in lay.order if lay.boxes[i].flag]
    if not flagged:
        return f'<p class="none">{T["noflags"]}</p>'
    items = []
    for i in flagged:
        n, b = spec.node(i), lay.boxes[i]
        rows = [(T["step"], step_ref(spec, lay, i))]
        rows += [(T[k], esc(getattr(n.improve, k))) for k in ("problem", "proposal")
                 if getattr(n.improve, k)]
        items.append(
            f'<li class="card flag-card" data-flag="{b.flag}" data-node="{esc(i)}">'
            f'<header class="card-head"><span class="badge">{b.flag}</span>'
            f'<h3>{esc(n.improve.text)}</h3></header>{facts(rows)}{show_in_flow(i)}</li>')
    return '<ol class="cards flag-list">\n' + "\n".join(items) + '\n</ol>'


def render_chips(spec: Spec) -> str:
    chips = [f'<button type="button" class="chip" data-lane="" aria-pressed="true">'
             f'{T["all"]}</button>']
    chips += [f'<button type="button" class="chip {lane_class(i)}" data-lane="{i}" '
              f'aria-pressed="false"><span class="dot" aria-hidden="true"></span>{esc(lane)}</button>'
              for i, lane in enumerate(spec.lanes)]
    return "".join(chips)


def build_timestamp() -> str:
    """Local time, or SOURCE_DATE_EPOCH (the reproducible-builds convention) in UTC."""
    return build_stamp.local()


def render_html(spec: Spec, lay: Layout, spec_name: str, lang: str = i18n.DEFAULT_LANG,
                lr: Layout | None = None) -> str:
    """The page. lay is the columns drawing, which shows without the script and in print;
    lr, when given, is the rows drawing the script may switch to. Cards, roles and the text
    version come from lay; both layouts number the steps the same way."""
    use_lang(lang)
    # auto_dark: this artefact follows the operating system's theme with no script, no
    # storage and no toggle, so a reader whose OS is dark gets a dark diagram instead of
    # a white page at midnight. The diagram's own role ramp has a dark counterpart in the
    # template; the palette it sits on comes from theme-dark.css.
    token_css, token_source = tun_tokens.load_token_css(palette=spec.headers.get("palette"),
                                                        auto_dark=True)
    n_flags = sum(1 for b in lay.boxes.values() if b.flag)
    counts = (f"{len(spec.nodes)} steps, {len(spec.edges)} connections, "
              f"{len(spec.lanes)} lanes, {n_flags} flagged")
    meta = (f"{i18n.plural(T, 'n_steps', len(spec.nodes))} · "
            f"{i18n.plural(T, 'n_lanes', len(spec.lanes))}"
            + (f" · {i18n.plural(T, 'n_flags', n_flags)}" if n_flags else ""))
    description = spec.headers.get("description", "")
    subs = {
        "ARTIFACT_TITLE": esc(spec.title),
        "TITLE": esc(spec.title),
        "DESCRIPTION": f'<p class="lede">{esc(description)}</p>' if description else "",
        "META": esc(meta),
        "SOURCE_DESCRIPTION": esc(spec.headers["source"]),
        "BUILD_TIMESTAMP": esc(build_timestamp()),
        "REQUESTED_BY": esc(spec.headers["requested-by"]),
        "BUILT_BY": BUILT_BY,
        "SPEC_NAME": esc(spec_name),
        "COUNTS": counts,
        "PALETTE": esc(tun_tokens.provenance_label(token_source)),
        "TOKEN_CSS": strip_css_comments(token_css),
        "SVG": render_svg(spec, lay) + ("\n" + render_svg(spec, lr) if lr else ""),
        "PD_SIZES": size_css(*([lay, lr] if lr else [lay])),
        "CHIPS": render_chips(spec),
        "STEPS": render_steps(spec, lay),
        "ROLES": render_roles(spec, lay),
        "FLAGS": render_flags(spec, lay),
        "TEXT_ALTERNATIVE": render_text_alternative(spec, lay),
    }
    template = i18n.apply(TEMPLATE.read_text(encoding="utf-8"), T)
    wanted = set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", template))
    if wanted != set(subs):
        raise SystemExit(f"error: template and builder disagree on placeholders: "
                         f"template only {sorted(wanted - set(subs))}, "
                         f"builder only {sorted(set(subs) - wanted)}")
    # One pass, so a value can never be re-scanned for placeholders.
    return re.sub(r"\{\{([A-Z0-9_]+)\}\}", lambda m: subs[m.group(1)], template)


def build(spec_path: pathlib.Path, lang: str = i18n.DEFAULT_LANG,
          notes: list | None = None) -> tuple[Spec, Layout, str]:
    """Parse, lay out both ways, check, render. The columns drawing must succeed. The rows
    drawing is an extra: if it cannot be drawn, the page carries columns only, and a note
    says why (notes, when given, collects it)."""
    spec = parse_spec(spec_path.read_text(encoding="utf-8-sig"), spec_path.name)
    lay = layout(spec)
    problems = check_layout(lay)
    if problems:
        raise LayoutError(f"{spec_path.name}: the layout breaks its own rules:\n  "
                          + "\n  ".join(problems))
    try:
        lr = layout(spec, rows_orient(spec))
        bad = check_layout(lr)
        if bad:
            raise LayoutError("; ".join(bad[:3]))
    except LayoutError as exc:
        lr = None
        if notes is not None:
            notes.append(f"rows drawing left out: {exc}")
    return spec, lay, render_html(spec, lay, spec_path.name, lang, lr=lr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=pathlib.Path, help="the .process.txt spec")
    ap.add_argument("--out", type=pathlib.Path, help="the .html file to write")
    ap.add_argument("--check", action="store_true",
                    help="parse and lay out only; write nothing")
    i18n.add_lang_argument(ap)
    args = ap.parse_args(argv)
    if not args.check and not args.out:
        ap.error("give --out <file.html>, or --check to only validate the spec")
    try:
        notes: list[str] = []
        spec, lay, page = build(args.spec, args.lang, notes)
    except (SpecError, LayoutError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    crossings = count_crossings(lay)
    summary = (f"{len(spec.nodes)} steps, {len(spec.edges)} connections, "
               f"{len(spec.lanes)} lanes, {lay.layers} layers, "
               f"{crossings} crossing{'' if crossings == 1 else 's'}, "
               f"{fmt(lay.width)}x{fmt(lay.height)} px")
    for note in notes:
        print(f"note: {note}")
    if args.check:
        print(f"ok {args.spec}: {summary}")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    print(f"built {args.out}  ({args.out.stat().st_size / 1024:.1f} KB; {summary})")
    # No builder ships an artefact past the Tier 1 ceiling (tools/build_size.py).
    build_size.enforce(args.out)
    print(f"  next: uv run --extra verify python tools/verify_process_diagram.py "
          f"{args.out} --spec {args.spec}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
