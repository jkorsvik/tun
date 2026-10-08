#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_process_diagram.py — the process-diagram builder, without a browser.

Stdlib only. Browser behaviour belongs in tools/verify_process_diagram.py.

    python3 tests/test_process_diagram.py

What it pins
------------
* every spec rule the builder promises is enforced, with a line number;
* check_layout() catches each layout fault it claims to: each fault is injected into a
  sound layout and must be reported (a checker that cannot fail proves nothing);
* the committed example is exactly what the builder produces from its spec, so the
  example can never be hand-edited into something the builder would not draw;
* the same spec gives the same bytes;
* colours come only from the token contract, and user text cannot inject a script tag
  or a {{PLACEHOLDER}} into the output;
* a harder spec (five lanes, parallel paths, three loops) still lays out cleanly;
* the drawing stays as uncluttered as it is today: a crossing ceiling for examples/23
  (1, down from 6 before loops back moved to their own gutters) and for the harder spec;
* optional step fields and improvement fields parse, and a spec without them still builds;
* the page carries one card per step, per role and per improvement point, and its script
  uses nothing that fails from file:// (no URL fragment, fetch, import or worker).
"""
from __future__ import annotations

import copy
import os
import pathlib
import re
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import build_process_diagram as bpd  # noqa: E402
import tun_tokens  # noqa: E402
import verify_standalone_core as core  # noqa: E402

EXAMPLE_DIR = REPO / "examples" / "23-process-diagram"
EXAMPLE_SPEC = EXAMPLE_DIR / "tun-workflow.process.txt"
EXAMPLE_HTML = EXAMPLE_DIR / "tun-workflow.html"
TEMPLATE = REPO / "templates" / "process-diagram.html"
# Ceilings, not targets: lower them when the router improves, never raise them to pass.
EXAMPLE_MAX_CROSSINGS = 1   # was 6 when loops back crossed the middle of the drawing
HARD_MAX_CROSSINGS = 2      # was 7

passed = failed = 0


def chk(label: str, got, want) -> None:
    global passed, failed
    if got == want:
        passed += 1
        print(f"  PASS {label}")
    else:
        failed += 1
        r = repr(got)
        print(f"  FAIL {label}: got {r[:200]}, wanted {want!r}")


HEAD = "title: T\nsource: S\nrequested-by: R\n"
GOOD = HEAD + """
lane A
  start s: Start
  decision d: Ok?
lane B
  step x: Do it
    improve: slow
  end e: Done
flow
  s -> d
  d -> x [ja]
  d -> e [nei]
  x -> e
"""


def spec_error(text: str) -> str:
    try:
        bpd.parse_spec(text, "t.process.txt")
    except bpd.SpecError as exc:
        return str(exc)
    return ""


def main() -> int:
    print("the spec rules are enforced, each with its line")
    spec = bpd.parse_spec(GOOD, "good")
    chk("a good spec parses: 4 nodes, 4 connections, 2 lanes",
        (len(spec.nodes), len(spec.edges), len(spec.lanes)), (4, 4, 2))
    chk("improve: attaches to the step above it", spec.node("x").improve, bpd.Improvement("slow"))
    chk("a chain is several connections",
        len(bpd.parse_spec(HEAD + "lane A\nstart a: a\nstep b: b\nend c: c\nflow\na -> b -> c",
                           "c").edges), 2)
    cases = [
        ("missing title", GOOD.replace("title: T\n", ""), "missing header 'title:'"),
        ("missing source", GOOD.replace("source: S\n", ""), "missing header 'source:'"),
        ("unknown header", "colour: red\n" + GOOD, "t.process.txt:1: unknown header 'colour'"),
        ("step before any lane", HEAD + "step x: y\n", "t.process.txt:4: a step must come after"),
        ("bad id", GOOD.replace("step x:", "step x!y:"), "may only use letters"),
        ("duplicate id", GOOD.replace("end e:", "end x:"), "id 'x' is used twice"),
        ("unknown id in flow", GOOD.replace("x -> e", "x -> nope"), "unknown id 'nope'"),
        ("self loop", GOOD.replace("x -> e", "x -> x"), "connects to itself"),
        ("duplicate connection", GOOD + "  x -> e\n", "listed twice"),
        ("label on a chain", GOOD.replace("x -> e", "s -> x -> e [hm]"), "single arrow"),
        ("decision with one outcome", GOOD.replace("  d -> e [nei]\n", "  s -> e\n"),
         "at least two outcomes"),
        ("unlabelled outcome", GOOD.replace("d -> e [nei]", "d -> e"), "needs a [label]"),
        ("same label twice", GOOD.replace("[nei]", "[ja]"), "same label"),
        ("start with incoming", GOOD + "  x -> s\n", "start 's' has an incoming"),
        ("end with outgoing", GOOD.replace("x -> e", "x -> e\n  e -> x"),
         "end 'e' has an outgoing"),
        ("dead end", GOOD.replace("  x -> e\n", ""), "'x' leads nowhere"),
        ("unreachable", GOOD.replace("lane B\n", "lane B\n  step z: Z\n  step w: W\n")
         + "  z -> w\n  w -> z\n  w -> e\n", "'z' cannot be reached"),
        ("empty lane", GOOD.replace("lane B\n", "lane Tom\nlane B\n"), "lane 'Tom' has no steps"),
        ("improve on a start", GOOD.replace("  start s: Start\n",
                                            "  start s: Start\n    improve: no\n"),
         "marks a step or decision"),
        ("improve without a reason", GOOD.replace("improve: slow", "improve:"), "needs a reason"),
        ("label too long", GOOD.replace("Do it", "x" * 91), "at most 90 characters"),
        ("garbage line", GOOD.replace("flow", "hello world\nflow"), "cannot read this line"),
        ("no start", GOOD.replace("start s: Start", "step s: Start"), "no 'start'"),
    ]
    for name, text, want in cases:
        chk(f"rejects: {name}", want in spec_error(text), True)
    chk("a byte-order mark (Notepad, Excel) is accepted", spec_error("\ufeff" + GOOD), "")

    print("\noptional step and improvement fields")
    rich = GOOD.replace("  step x: Do it\n    improve: slow\n",
                        "  step x: Do it\n    beskrivelse: What happens\n    input: In\n"
                        "    output: Out\n    verktoy: Tool\n    varighet: 5 min\n"
                        "    improve: slow\n      problem: Too slow\n      forslag: Faster\n")
    x = bpd.parse_spec(rich, "rich").node("x")
    chk("step fields attach to the step above them", x.fields,
        {"description": "What happens", "input": "In", "output": "Out", "tool": "Tool",
         "duration": "5 min"})
    chk("problem: and forslag: belong to the improvement point", x.improve,
        bpd.Improvement("slow", "Too slow", "Faster"))
    chk("field keys are not case sensitive",
        bpd.parse_spec(GOOD.replace("    improve: slow\n", "    Input: I\n    improve: slow\n"),
                       "case").node("x").fields, {"input": "I"})
    chk("'verktøy' with ø is the same field",
        bpd.parse_spec(GOOD.replace("    improve: slow\n", "    verktøy: T\n    improve: slow\n"),
                       "o").node("x").fields, {"tool": "T"})
    for name, text, want in (
            ("problem without improve", GOOD.replace("    improve: slow\n", "    problem: p\n"),
             "put it under an 'improve:' line"),
            ("field before any step", HEAD + "input: x\n" + GOOD[len(HEAD):],
             "must sit under the step"),
            ("empty field", GOOD.replace("    improve: slow\n", "    input:\n    improve: slow\n"),
             "is empty"),
            ("field twice", GOOD.replace("    improve: slow\n", "    input: a\n    input: b\n"),
             "already has 'input:'"),
            ("field too long", GOOD.replace("    improve: slow\n", f"    input: {'x' * 301}\n"),
             "at most 300 characters"),
            ("problem twice", GOOD.replace("    improve: slow\n",
                                           "    improve: slow\n      problem: a\n      problem: b\n"),
             "already has 'problem:'"),
            ("unknown field", GOOD.replace("    improve: slow\n", "    eier: Ola\n    improve: slow\n"),
             "unknown field 'eier:'"),
            ("a header after the lanes", GOOD.replace("flow", "description: sent\nflow"),
             "headers (title:, source:, ...) go before the first 'lane' line")):
        chk(f"rejects: {name}", want in spec_error(text), True)
    plain = bpd.parse_spec(GOOD, "plain")
    plain_page = bpd.render_html(plain, bpd.layout(plain), "plain")
    chk("a spec without fields still builds, with a card per step and no empty rows",
        (plain_page.count('<article class="card step-card'), "Hva skjer" in plain_page), (4, False))
    chk("the error quotes the offending line",
        "    step x!y: Do it" in spec_error(GOOD.replace("step x:", "step x!y:")), True)

    print("\nthe example lays out cleanly and is up to date")
    ex = bpd.parse_spec(EXAMPLE_SPEC.read_text(encoding="utf-8"), EXAMPLE_SPEC.name)
    lay = bpd.layout(ex)
    chk("example: 11 steps, 13 connections, 3 lanes, 2 flags",
        (len(ex.nodes), len(ex.edges), len(ex.lanes), sum(1 for n in ex.nodes if n.improve)),
        (11, 13, 3, 2))
    chk("example: check_layout finds nothing", bpd.check_layout(lay), [])
    chk(f"example: at most {EXAMPLE_MAX_CROSSINGS} crossings",
        bpd.count_crossings(lay) <= EXAMPLE_MAX_CROSSINGS, True)
    chk("example: every step and decision has a description",
        [n.id for n in ex.nodes if n.kind in ("step", "decision") and "description" not in n.fields], [])
    with tempfile.TemporaryDirectory() as tmp:
        outs = []
        for i in range(2):
            out = pathlib.Path(tmp) / f"d{i}.html"
            r = subprocess.run([sys.executable, str(REPO / "tools" / "build_process_diagram.py"),
                                str(EXAMPLE_SPEC), "--out", str(out)],
                               capture_output=True, text=True,
                               env=dict(os.environ, SOURCE_DATE_EPOCH="1790000000"))
            chk(f"build {i + 1} exits 0", r.returncode, 0)
            outs.append(out.read_text(encoding="utf-8") if out.exists() else "")
        chk("same spec, same bytes", outs[0] == outs[1] and bool(outs[0]), True)
        over = pathlib.Path(tmp) / "override.html"
        subprocess.run([sys.executable, str(REPO / "tools" / "build_process_diagram.py"),
                        str(EXAMPLE_SPEC), "--out", str(over)], capture_output=True, text=True,
                       env=dict(os.environ, TUN_PALETTE="tools/tokens/palette-neutral.css"))
        chk("TUN_PALETTE beats the spec's palette: header (the person building decides)",
            "Palette     : TUN_PALETTE=tools/tokens/palette-neutral.css"
            in (over.read_text(encoding="utf-8") if over.exists() else ""), True)
        mask = lambda s: re.sub(r"(Built       : |Laget )[^\n.]*", r"\1<stamp>", s)  # noqa: E731
        committed = EXAMPLE_HTML.read_text(encoding="utf-8")
        chk("the committed example is what the builder makes (apart from the build time)",
            mask(committed) == mask(outs[0]), True)

    print("\nthe output passes the generic core and the colour contract")
    html_text = EXAMPLE_HTML.read_text(encoding="utf-8")
    for fn in (core.check_self_contained, core.check_no_leftover_placeholders,
               core.check_provenance, core.check_no_stray_script_text,
               core.check_no_target_driven_visibility, core.check_no_scroll_persistent_positioning):
        chk(f"example: {fn.__name__}", fn(html_text)[0], True)
    lines = html_text.splitlines()
    n_flags = sum(1 for n in ex.nodes if n.improve)
    chk("output contract: one line per lane, node, connection, text step and card",
        tuple(sum(ln.startswith(p) for ln in lines) for p in (
            '<g class="lane ', '<g class="node node-', '<g class="edge"', "<li data-node=",
            '<article class="card step-card', '<section class="card role-card',
            '<li class="card flag-card')),
        (len(ex.lanes), len(ex.nodes), len(ex.edges), len(ex.nodes), len(ex.nodes),
         len(ex.lanes), n_flags))
    chk("example: the palette is the one its spec asks for",
        "Palette     : spec:plugins/tun/tokens/palette.css" in html_text, True)
    tpl = TEMPLATE.read_text(encoding="utf-8")
    colour = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")
    chk("template: no colour literal of its own", colour.findall(tpl), [])
    token_css, _ = tun_tokens.load_token_css(("status-semantic.css", "theme-light.css"),
                                             palette=ex.headers.get("palette"))
    hexes = set(m.lower() for m in re.findall(r"#[0-9a-fA-F]{3,8}\b", html_text))
    tok_hexes = set(m.lower() for m in re.findall(r"#[0-9a-fA-F]{3,8}\b", token_css))
    chk("example: every colour value comes from the token files", hexes - tok_hexes, set())
    chk("example: inlined token comments are stripped (they name a brand)",
        any(s in html_text for s in ("Status / semantic colour tokens", "Palette: neutral")),
        False)
    chk(f"template: one role colour class per LANE_COLOURS ({bpd.LANE_COLOURS})",
        sorted(set(re.findall(r"\.c(\d+)\{--role:", tpl)), key=int),
        [str(i) for i in range(bpd.LANE_COLOURS)])
    chk("template: the script uses nothing that fails from file://",
        [t for t in ("location.hash", "hashchange", "fetch(", "Worker", "import(",
                     "XMLHttpRequest", 'href="#', "localStorage") if t in tpl], [])
    own = set(re.findall(r"(--[a-z0-9-]+)\s*:", tpl))
    chk("template: all colour variables used are defined by the token CSS or the template",
        sorted(set(re.findall(r"var\((--[a-z0-9-]+)\)", tpl))
               - set(re.findall(r"(--[a-z0-9-]+)\s*:", token_css)) - own), [])
    chk("template: its own variables (role colours) are built only from token variables",
        sorted(v for m in re.finditer(r"--[a-z0-9-]+\s*:\s*([^;}]+)", tpl)
               for v in re.findall(r"var\((--[a-z0-9-]+)", m.group(1))
               if v not in set(re.findall(r"(--[a-z0-9-]+)\s*:", token_css))), [])

    print("\nuser text cannot inject markup or placeholders")
    nasty = (HEAD + "lane A\n  start s: Hei {{TOKEN_CSS}} <script>alert(1)</script>\n"
             "  end e: --> slutt\nflow\n  s -> e\n")
    page = bpd.render_html(bpd.parse_spec(nasty, "n"), bpd.layout(bpd.parse_spec(nasty, "n")), "n")
    chk("a {{TOKEN}} in a label is neutralised", core.check_no_leftover_placeholders(page)[0], True)
    chk("a script tag in a label stays text (row 25)", core.check_no_stray_script_text(page)[0], True)
    chk("'-->' in a label cannot close the provenance comment",
        page.count("-->") == tpl.count("-->"), True)

    print("\ncheck_layout catches every fault it claims to")
    base = bpd.layout(ex)

    def broken(mutate) -> list[str]:
        m = copy.deepcopy(base)
        mutate(m)
        return bpd.check_layout(m)

    def overlap(m):
        a, b = list(m.boxes.values())[:2]
        b.u, b.v = a.u + 5, a.v + 5

    def through(m):
        r = m.routes[0]
        other = next(b for b in m.boxes.values() if b.id not in (r.edge.src, r.edge.dst))
        mid_v = other.v + other.dv / 2
        r.points = [r.points[0], (r.points[0][0], mid_v), (other.u + other.du + 40, mid_v),
                    (other.u + other.du + 40, r.points[-1][1]), r.points[-1]]

    def collinear(m):
        m.routes[1].points = list(m.routes[0].points)

    def label_hit(m):
        r = next(r for r in m.routes if r.label_rect)
        o = next(o for o in m.routes if o is not r)
        u1, v1, u2, v2 = r.label_rect
        o.points = o.points[:1] + [(o.points[0][0], (v1 + v2) / 2), ((u1 + u2) / 2, (v1 + v2) / 2)] + \
                   [((u1 + u2) / 2, o.points[-1][1]), o.points[-1]]

    def diagonal(m):
        r = m.routes[0]
        r.points = [r.points[0], r.points[-1]] if r.points[0][1] != r.points[-1][1] else \
                   [r.points[0], (r.points[-1][0], r.points[-1][1] + 5)]

    def off_port(m):
        r = m.routes[0]
        r.points[0] = (r.points[0][0] - 20, r.points[0][1])

    def outside(m):
        r = m.routes[0]
        r.points = [r.points[0], (r.points[0][0] + 20, r.points[0][1]),
                    (r.points[0][0] + 20, -30), (r.points[-1][0] - 20, -30),
                    (r.points[-1][0] - 20, r.points[-1][1]), r.points[-1]]

    def loop_from_bottom(m):
        r = next(r for r in m.routes if r.loop)
        s = m.boxes[r.edge.src]
        r.points = [(s.u + s.du, s.v + s.dv / 2), (s.u + s.du + 20, s.v + s.dv / 2),
                    (s.u + s.du + 20, r.points[1][1])] + r.points[1:]

    def text_tall(m):
        next(iter(m.boxes.values())).lines = ["x"] * 9

    for name, fn, want in (("two boxes overlapping", overlap, "boxes overlap"),
                           ("a line through a box", through, "runs through the box"),
                           ("two lines along each other", collinear, "run along each other"),
                           ("a line across a label", label_hit, "is crossed by"),
                           ("a diagonal line", diagonal, "diagonal"),
                           ("a line not leaving its box", off_port, "does not leave"),
                           ("a line leaving the drawing", outside, "leaves the drawing"),
                           ("a loop not leaving a right side", loop_from_bottom,
                            "does not leave from the right side"),
                           ("a label taller than its box", text_tall, "taller than its box")):
        problems = broken(fn)
        chk(f"catches {name}", any(want in p for p in problems), True)

    print("\na harder spec still lays out cleanly")
    hard = HEAD + """
lane Kunde
  start k1: Sender søknad
  step k2: Sender inn manglende dokumenter
  end k3: Får svar
lane Saksbehandler
  step s1: Registrerer saken
  decision s2: Komplett?
  step s3: Vurderer saken
  decision s4: Trenger kreditt?
  step s5: Skriver vedtak
    improve: Vedtaksmalen har fem varianter som sier det samme
lane Kreditt
  step c1: Kredittvurdering
  decision c2: Innvilget?
lane Kontroll
  step q1: Stikkprøve av vedtak
lane Arkiv
  step a1: Arkiverer
flow
  k1 -> s1 -> s2
  s2 -> s3 [ja]
  s2 -> k2 [nei]
  k2 -> s1
  s3 -> s4
  s4 -> c1 [ja]
  s4 -> s5 [nei]
  c1 -> c2
  c2 -> s5 [ja]
  c2 -> s3 [nei, ny runde]
  s5 -> q1
  s5 -> a1
  q1 -> a1
  a1 -> k3
"""
    hs = bpd.parse_spec(hard, "hard")
    hl = bpd.layout(hs)
    chk("hard: 5 lanes, 12 steps, 15 connections",
        (len(hs.lanes), len(hs.nodes), len(hs.edges)), (5, 12, 15))
    chk("hard: check_layout finds nothing", bpd.check_layout(hl), [])
    chk(f"hard: at most {HARD_MAX_CROSSINGS} crossings", bpd.count_crossings(hl) <= HARD_MAX_CROSSINGS, True)
    long_word = HEAD + ("lane A\n  start s: Trygdeavgiftsberegningsforskriften gjelder\n"
                        "  end e: Ferdig\nflow\n  s -> e\n")
    lw = bpd.layout(bpd.parse_spec(long_word, "lw"))
    chk("a long compound word is split with a hyphen and fits",
        (bpd.check_layout(lw), lw.boxes["s"].lines[0].endswith("-")), ([], True))
    crowded = HEAD + ("lane A\n  start s: S\n  decision d: Hva nå?\n  end e: E\n  end f: F\n"
                      "  end g: G\nflow\n  s -> d\n  d -> e [svar nummer en]\n"
                      "  d -> f [svar nummer to]\n  d -> g [svar nummer tre]\n")
    try:
        bpd.layout(bpd.parse_spec(crowded, "crowded"))
        msg = ""
    except bpd.LayoutError as exc:
        msg = str(exc)
    chk("outcome labels too long to sit side by side fail with advice",
        "too long to sit side by side" in msg and "shorten" in msg, True)

    print(f"\nPASS: {passed}  FAIL: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
