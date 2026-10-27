#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Sankey: flows that balance, one scale, and ribbons that tile their nodes exactly.

A flow picture is easy to draw and easy to fake: volume can appear or vanish between stages, a
band can change meaning at its two ends, or the bands can leave gaps in the node they leave from.
None of that is visible to a reader who is not adding the numbers, so all three are checked here.

  1. one bar per node and one ribbon per flow
  2. every node's height is its own total on ONE shared scale
  3. every ribbon's drawn shape matches the geometry written beside it
  4. the ribbons leaving a node tile its bar exactly, and so do the ribbons arriving at it
  5. every intermediate node takes in exactly what it passes on, in the extract and in the table
  6. the stages are the longest path from a source, and a cycle is refused
  7. refusals: an unbalanced node, a cycle, a zero flow, a duplicate pair, a self-loop
  8. the committed example is the builder's own output, byte for byte
  9. no script, and the English build carries no Norwegian
 10. no label sits outside the canvas, measured in a browser
 11. three mutations, each breaking exactly one of the checks above

    python3 tests/test_sankey.py
"""
from __future__ import annotations

import csv
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_sankey.py"
EXAMPLE = ROOT / "examples" / "53-sankey"
DATA = EXAMPLE / "kanaler.csv"
PAGE = EXAMPLE / "kanaler.html"
PIN = "1792836000"

FAILURES: list[str] = []
CHECKS = 0

NODE = re.compile(r'<rect class="sk-node" data-node="([^"]*)" x="([-\d.]+)" y="([-\d.]+)" '
                  r'width="[-\d.]+" height="([-\d.]+)"')
FLOW = re.compile(r'<path class="sk-flow" data-src="([^"]*)" data-dst="([^"]*)" '
                  r'data-value="([\d.]+)" data-y0="([\d.]+)" data-y1="([\d.]+)" '
                  r'data-thick="([\d.]+)" d="([^"]*)"')
LABEL = re.compile(r'<text class="sk-label" x="[-\d.]+" y="[-\d.]+"[^>]*>([^<]*)</text>')


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


def run(data: pathlib.Path, out: pathlib.Path, *extra: str, lang: str = "nb",
        tools: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    builder = (tools / "build_sankey.py") if tools else BUILDER
    args = [sys.executable, str(builder), "--data", str(data), "--from", "Kanal",
            "--to", "Utfall", "--value", "Antall",
            "--title", "Hvor ble henvendelsene av",
            "--source", "Syntetisk eksempeldata (kanaler.csv)",
            "--requested-by", "Kundesenteret", "--lang", lang, "--out", str(out), *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env)


def scratch(root: pathlib.Path, *pairs: tuple[str, str]) -> pathlib.Path:
    tools = root / "tools"
    tools.mkdir(parents=True)
    shutil.copy2(BUILDER, tools / "build_sankey.py")
    for name in ("build_size.py", "build_stamp.py", "feedback_link.py", "i18n.py",
                 "tun_core.py", "tun_tokens.py"):
        shutil.copy2(ROOT / "tools" / name, tools / name)
    shutil.copytree(ROOT / "tools" / "tokens", tools / "tokens")
    shutil.copytree(ROOT / "templates", root / "templates")
    target = tools / "build_sankey.py"
    text = target.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            raise SystemExit(f"the mutation does not apply: {old[:70]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")
    return tools


def own_edges(path: pathlib.Path = DATA) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [{"src": row["Kanal"], "dst": row["Utfall"], "value": float(row["Antall"])}
                for row in csv.DictReader(fh, delimiter=";")]


def own_layers(edges: list[dict]) -> dict[str, int]:
    nodes = sorted({e["src"] for e in edges} | {e["dst"] for e in edges})
    incoming = {n: [] for n in nodes}
    for edge in edges:
        incoming[edge["dst"]].append(edge["src"])
    layer: dict[str, int] = {}

    def walk(node: str) -> int:
        if node in layer:
            return layer[node]
        layer[node] = 0 if not incoming[node] else 1 + max(walk(p) for p in incoming[node])
        return layer[node]

    for node in nodes:
        walk(node)
    return layer


def table_rows(page: str, which: int = 0) -> list[list[str]]:
    bodies = re.findall(r"<tbody>(.*?)</tbody>", page, re.S)
    body = bodies[which]
    return [[re.sub(r"<[^>]+>", "", cell).strip()
             for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            for row in re.findall(r"<tr>(.*?)</tr>", body, re.S)]


def num(text: str) -> float:
    return float(text.replace("\u00a0", "").replace("\u2009", "")
                 .replace("\u2212", "-").replace(",", ".").strip())


def main() -> int:
    if not DATA.is_file():
        raise SystemExit(f"{DATA} is missing; run examples/53-sankey/generate_data.py")
    edges = own_edges()
    nodes = sorted({e["src"] for e in edges} | {e["dst"] for e in edges})
    inflow = {n: 0.0 for n in nodes}
    outflow = {n: 0.0 for n in nodes}
    for edge in edges:
        outflow[edge["src"]] += edge["value"]
        inflow[edge["dst"]] += edge["value"]
    total = sum(outflow[n] for n in nodes if inflow[n] == 0)
    layer = own_layers(edges)

    with tempfile.TemporaryDirectory() as raw:
        work = pathlib.Path(raw)
        out = work / "s.html"
        done = run(DATA, out)
        print("1. one bar per node and one ribbon per flow")
        chk(done.returncode == 0, "the builder exits 0", (done.stderr or "")[-500:])
        page = out.read_text(encoding="utf-8")
        bars = {name: (float(x), float(y), float(h)) for name, x, y, h in NODE.findall(page)}
        flows = [{"src": s, "dst": d, "value": float(v), "y0": float(y0), "y1": float(y1),
                  "thick": float(t), "d": path}
                 for s, d, v, y0, y1, t, path in FLOW.findall(page)]
        chk(sorted(bars) == nodes, f"one bar for each of the {len(nodes)} nodes",
            f"{sorted(bars)}")
        chk(len(flows) == len(edges), "one ribbon per flow", f"{len(flows)} vs {len(edges)}")

        print("\n2. every node height is its own total on one shared scale")
        biggest = max((outflow[n] or inflow[n]) for n in nodes)
        tallest = max(bars[n][2] for n in nodes)
        scale = tallest / biggest
        wrong = [n for n in nodes
                 if abs(bars[n][2] - (outflow[n] or inflow[n]) * scale) > 0.6]
        chk(not wrong, "each bar is its own total times one pixels-per-unit", str(wrong[:3]))
        wrong_flow = [f"{f['src']}→{f['dst']}" for f in flows
                      if abs(f["thick"] - f["value"] * scale) > 0.6]
        chk(not wrong_flow, "and every ribbon's thickness uses the same scale",
            str(wrong_flow[:3]))

        print("\n3. every ribbon's drawn shape matches the geometry beside it")
        bad_path = []
        for flow in flows:
            numbers = [float(v) for v in re.findall(r"-?\d+\.\d+", flow["d"])]
            # M x0,y0 C mid,y0 mid,y1 x1,y1 L x1,y1+t C mid,y1+t mid,y0+t x0,y0+t Z
            if len(numbers) < 14:
                bad_path.append(f"{flow['src']}→{flow['dst']}: {len(numbers)} points")
                continue
            x0, y0, _m1, _y0b, _m2, y1, _x1, _y1b, _x1b, y1t, _m3, _y1t, _m4, y0t = numbers[:14]
            if (abs(y0 - flow["y0"]) > 0.05 or abs(y1 - flow["y1"]) > 0.05
                    or abs((y1t - y1) - flow["thick"]) > 0.05
                    or abs((y0t - y0) - flow["thick"]) > 0.05):
                bad_path.append(f"{flow['src']}→{flow['dst']}")
        chk(not bad_path,
            "the curve leaves at one end with the thickness it arrives with at the other",
            str(bad_path[:3]))

        print("\n4. the ribbons tile their node exactly, at both ends")
        problems = []
        for node in nodes:
            for attr, x_index in (("y0", 1), ("y1", 1)):
                mine = [f for f in flows if (f["src"] if attr == "y0" else f["dst"]) == node]
                if not mine:
                    continue
                mine.sort(key=lambda f: f[attr])
                top = bars[node][1]
                span = bars[node][2]
                if abs(mine[0][attr] - top) > 0.6:
                    problems.append(f"{node}: first band starts {mine[0][attr]:.1f}, bar {top:.1f}")
                for one, other in zip(mine, mine[1:]):
                    if abs((one[attr] + one["thick"]) - other[attr]) > 0.6:
                        problems.append(f"{node}: gap or overlap between bands")
                if abs((mine[-1][attr] + mine[-1]["thick"]) - (top + span)) > 0.6:
                    problems.append(f"{node}: bands end past the bar")
        chk(not problems, "no gap and no overflow at either end of every node",
            str(problems[:3]))

        print("\n5. every intermediate node takes in what it passes on")
        middle = [n for n in nodes if inflow[n] > 0 and outflow[n] > 0]
        chk(middle, "the example has intermediate nodes", str(middle))
        chk(all(abs(inflow[n] - outflow[n]) < 1e-6 for n in middle),
            "the extract balances at every one of them", str(middle))
        node_table = {cells[0]: cells for cells in table_rows(page, 1)}
        bad_table = []
        for node in nodes:
            cells = node_table[node]
            if (abs(num(cells[2]) - inflow[node]) > 0.001
                    or abs(num(cells[3]) - outflow[node]) > 0.001
                    or int(cells[1]) != layer[node] + 1):
                bad_table.append(f"{node}: {cells[1:4]}")
        chk(not bad_table, "and the node table repeats every in, out and stage",
            str(bad_table[:3]))
        flow_table = {f"{c[0]}→{c[1]}": num(c[2]) for c in table_rows(page, 0)}
        chk(all(abs(flow_table[f"{e['src']}→{e['dst']}"] - e["value"]) < 0.001 for e in edges),
            "the flow table repeats every quantity", str(len(flow_table)))

        print("\n6. the stages are the longest path from a source")
        chk(all(int(node_table[n][1]) == layer[n] + 1 for n in nodes),
            "every stage number is this suite's own", str(layer))
        chk(max(layer.values()) >= 2, "and there are at least three stages, so the layering "
                                     "is doing work", str(max(layer.values()) + 1))

        print("\n7. refusals name what to fix")
        unbalanced = work / "unbalanced.csv"
        unbalanced.write_text("Kanal;Utfall;Antall\nA;Midt;10\nMidt;B;7\n", encoding="utf-8")
        done = run(unbalanced, work / "u.html")
        chk(done.returncode != 0 and "do not balance" in (done.stderr or ""),
            "a node that does not pass on what it received is refused",
            (done.stderr or "")[-240:])

        cycle = work / "cycle.csv"
        cycle.write_text("Kanal;Utfall;Antall\nA;B;5\nB;C;3\nC;A;2\n", encoding="utf-8")
        done = run(cycle, work / "c.html")
        chk(done.returncode != 0 and "cycle" in (done.stderr or ""),
            "a cycle is refused", (done.stderr or "")[-240:])

        zero = work / "zero.csv"
        zero.write_text("Kanal;Utfall;Antall\nA;B;0\n", encoding="utf-8")
        done = run(zero, work / "z.html")
        chk(done.returncode != 0 and "positive flows" in (done.stderr or ""),
            "a zero flow is refused", (done.stderr or "")[-240:])

        twice = work / "twice.csv"
        twice.write_text("Kanal;Utfall;Antall\nA;B;4\nA;B;6\n", encoding="utf-8")
        done = run(twice, work / "t.html")
        chk(done.returncode != 0 and "appears twice" in (done.stderr or ""),
            "a duplicated pair is refused by name", (done.stderr or "")[-240:])

        loop = work / "loop.csv"
        loop.write_text("Kanal;Utfall;Antall\nA;A;4\n", encoding="utf-8")
        done = run(loop, work / "l.html")
        chk(done.returncode != 0 and "itself" in (done.stderr or ""),
            "a self-loop is refused", (done.stderr or "")[-240:])

        print("\n8. the committed example is the builder's own output")
        pinned = work / "pinned.html"
        done = run(DATA, pinned)
        chk(done.returncode == 0 and pinned.read_bytes() == PAGE.read_bytes(),
            "a pinned rebuild equals the committed file byte for byte")

        print("\n9. no script, and the English build is English")
        chk("<script" not in page, "the page carries no script")
        out_en = work / "en.html"
        done = run(DATA, out_en, lang="en")
        page_en = out_en.read_text(encoding="utf-8")
        chk(done.returncode == 0 and '<html lang="en">' in page_en, "the English build runs")
        # "Node" is a Norwegian AND an English word here, so it proves nothing; the rest do.
        norwegian = [w for w in ("Trinn", "Kilde:", "Bygget", "kollega", "Noder") if w in page_en]
        chk(not norwegian, "the English page keeps no Norwegian chrome", str(norwegian))

        print("\n10. nothing sits outside the canvas, measured in a browser")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            chk(False, "playwright is installed (this suite measures text)")
            report()
            return 1
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for width in (1100, 1500):
                ctx = browser.new_context(viewport={"width": width, "height": 1000})
                view = ctx.new_page()
                view.goto(PAGE.resolve().as_uri())
                view.wait_for_selector(".sk-node")
                measured = view.evaluate(
                    """() => {
                         const svg = document.querySelector('.figure svg').getBoundingClientRect();
                         return [...document.querySelectorAll('.sk-label, .sk-stage')].map(e => {
                           const r = e.getBoundingClientRect();
                           return {t: e.textContent.trim(), x: r.x, right: r.right,
                                   svgX: svg.x, svgRight: svg.right,
                                   size: parseFloat(getComputedStyle(e).fontSize)}; });
                       }""")
                outside = [m["t"] for m in measured
                           if m["x"] < m["svgX"] - 1 or m["right"] > m["svgRight"] + 1]
                chk(not outside, f"no label runs past the canvas at {width} px",
                    str(outside[:3]))
                small = [m["t"] for m in measured if m["size"] < 14]
                chk(not small, f"and every label is at least 14 px at {width} px",
                    str(small[:3]))
                ctx.close()
            browser.close()

        print("\n11. the mutations")
        with tempfile.TemporaryDirectory() as mraw:
            mraw = pathlib.Path(mraw)

            # a. the thickness on a second scale, which is the defect a picture cannot show.
            tools = scratch(mraw / "scale",
                            ('        thickness = max(1.0, edge["value"] * scale)',
                             '        thickness = max(1.0, edge["value"] * scale * 1.3)'))
            out_m = mraw / "scale.html"
            done = run(DATA, out_m, tools=tools)
            chk(done.returncode == 0, "the wider-band mutation still builds",
                (done.stderr or "")[-200:])
            mflows = [{"src": s, "dst": d, "value": float(v), "thick": float(t)}
                      for s, d, v, _y0, _y1, t, _p in FLOW.findall(out_m.read_text(encoding="utf-8"))]
            mbad = [f["dst"] for f in mflows if abs(f["thick"] - f["value"] * scale) > 0.6]
            chk(bool(mbad), "and the bands no longer match the scale, so check 2 sees it",
                str(mbad[:3]))

            # b. the bands all starting at the top of their node: gaps appear.
            tools = scratch(mraw / "stack",
                            ('        y0 = s["y"] + out_used[edge["src"]]',
                             '        y0 = s["y"]'))
            out_m = mraw / "stack.html"
            done = run(DATA, out_m, tools=tools)
            chk(done.returncode == 0, "the unstacked-band mutation still builds",
                (done.stderr or "")[-200:])
            mpage = out_m.read_text(encoding="utf-8")
            mflows = [{"src": s, "dst": d, "thick": float(t), "y0": float(y0)}
                      for s, d, _v, y0, _y1, t, _p in FLOW.findall(mpage)]
            overlaps = 0
            for node in nodes:
                mine = sorted((f for f in mflows if f["src"] == node), key=lambda f: f["y0"])
                if len(mine) > 1 and len({round(f["y0"], 2) for f in mine}) != len(mine):
                    overlaps += 1
            chk(overlaps > 0,
                "and ribbons leaving the same node start on top of each other, so check 4 sees "
                "it", str(overlaps))

            # c. the balance check disabled, on an extract that does not balance.
            tools = scratch(mraw / "balance",
                            ("    if unbalanced:", "    if False:"))
            out_m = mraw / "balance.html"
            done = run(unbalanced, out_m, tools=tools)
            chk(done.returncode == 0,
                "with the check disabled the unbalanced extract builds, so check 7 sees it",
                (done.stderr or "")[-200:])

    report()
    return 1 if FAILURES else 0


def report() -> None:
    print()
    if FAILURES:
        print(f"{CHECKS - len(FAILURES)} passed, {len(FAILURES)} failed")
        for name in FAILURES:
            print(f"  - {name}")
    else:
        print(f"{CHECKS} checks passed")


if __name__ == "__main__":
    raise SystemExit(main())
