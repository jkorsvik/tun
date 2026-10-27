#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a standalone Sankey: where the volume went between stages, and that it balances.

A funnel (42) counts one cohort through declared stages. This traces volume through a network:
every row is a flow from one node to another, and the picture shows how much arrived at each
stage and what it split into.

    python3 tools/build_sankey.py \\
      --data examples/53-sankey/kanaler.csv \\
      --from Kanal --to Utfall --value Antall \\
      --title "Hvor ble henvendelsene av" \\
      --source "Syntetisk eksempeldata (kanaler.csv)" \\
      --requested-by "Kundesenteret" \\
      --out examples/53-sankey/kanaler.html

What is built in, rather than left to whoever assembles the file:

  * **a flow diagram that does not balance is decoration.** Every intermediate node must have
    the same total in as out, checked to the last unit, and the builder refuses by name when it
    does not. A picture where volume silently appears or vanishes between stages is worse than a
    table.
  * **one scale for the whole drawing.** A per-stage scale would let a ribbon change meaning
    between two nodes without saying so; here a stage that carries less volume is visibly
    shorter, and the page says the scale is shared.
  * **a cycle is refused.** A network where volume can return to an earlier stage has no
    stages, and a layered drawing of it would invent an order that is not there.
  * **every flow and every node total is in the table**, so a reader can add a column instead of
    trusting a ribbon's width.
  * **no negative or zero flows.** A zero flow draws a hairline nobody can see; a negative one
    has no width at all.
  * **there is no script.** A flow picture is a snapshot of one period.

Stdlib only, like the rest of tools/. Python 3.8+.
"""
from __future__ import annotations

import argparse
import html
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import build_size  # noqa: E402
import build_stamp  # noqa: E402
import feedback_link  # noqa: E402
import i18n  # noqa: E402
import tun_core  # noqa: E402
import tun_tokens  # noqa: E402
from tun_tokens import strip_css_comments  # noqa: E402
from tun_core import NOT_STATED, die  # noqa: E402

TEMPLATE = ROOT / "templates" / "sankey.html"
STRINGS = "sankey"
MAX_NODES = 40
MAX_EDGES = 90
MAX_LABEL = 26
TOL = 1e-6                     # a unit is a unit: flows are counted, not measured
MAX_BYTES = 40 * 1024 * 1024

W = 860
NODE_W = 16
PAD_T = 52
PAD_B = 44
GAP_MIN = 10                   # the least vertical space between two nodes in a layer
SIDE = 6


def decimals_of(values: list[float]) -> int:
    if all(float(v).is_integer() for v in values):
        return 0
    return 2 if any(round(v, 1) != round(v, 2) for v in values) else 1


def fmt(value: float, lang: str, dec: int) -> str:
    text = f"{value:,.{dec}f}"
    if lang == "nb":
        return text.replace(",", "\u00a0").replace(".", ",")
    return text.replace(",", "\u2009")


# ----------------------------------------------------------------------------------- load
def load(path: pathlib.Path, src_col: str, dst_col: str, value_col: str):
    if not path.is_file():
        die(f"{path} does not exist")
    rows = tun_core.coerce_numbers(tun_core.read_rows(path))
    if not rows:
        die(f"{path.name} has no rows")
    header = tun_core.columns(rows)
    for name, flag in ((src_col, "--from"), (dst_col, "--to"), (value_col, "--value")):
        if name not in header:
            die(f"{flag} names {name!r}, which is not a column in {path.name}. "
                f"Columns: {', '.join(header)}")
    if not tun_core.is_numeric_column(rows, value_col):
        die(f"--value names {value_col!r}, and that column is not numeric in every row. A Sankey "
            f"draws quantities; a category in that column is a count, so count it first.")

    edges: list[dict] = []
    seen: dict[tuple[str, str], float] = {}
    for i, row in enumerate(rows, 2):
        src = str(row.get(src_col) or "").strip()
        dst = str(row.get(dst_col) or "").strip()
        if not src or not dst:
            continue
        if src == dst:
            die(f"{path.name}:{i}: {src!r} flows to itself. A self-loop has no width on a "
                f"layered drawing; drop the row or fix the extract.")
        value = tun_core.to_number(row.get(value_col))
        if value is None:
            die(f"{path.name}:{i}: the flow {src!r} to {dst!r} has no number. A Sankey draws "
                f"quantities; an empty flow is not one.")
        if float(value) <= 0:
            die(f"{path.name}:{i}: the flow {src!r} to {dst!r} is {value}. A Sankey needs "
                f"positive flows: zero draws a hairline nobody can see, and a negative one has "
                f"no width at all.")
        key = (src, dst)
        if key in seen:
            die(f"{path.name}: the flow {src!r} to {dst!r} appears twice. Sum it in the extract "
                f"first, so the picture and the table agree on one number per pair.")
        seen[key] = float(value)
        for label in (src, dst):
            if len(label) > MAX_LABEL:
                die(f"{path.name}:{i}: the node name {label!r} is {len(label)} characters, past "
                    f"the {MAX_LABEL} this drawing holds. Shorten it; a truncated name is not a "
                    f"name.")
        edges.append({"src": src, "dst": dst, "value": float(value)})

    if not edges:
        die(f"no row in {path.name} has both ends of a flow and a number.")
    nodes = sorted({e["src"] for e in edges} | {e["dst"] for e in edges})
    if len(nodes) > MAX_NODES:
        die(f"{len(nodes)} nodes is past the {MAX_NODES}-node ceiling: the ribbons cross into a "
            f"web. Aggregate the stages, or split the picture by period.")
    if len(edges) > MAX_EDGES:
        die(f"{len(edges)} flows is past the {MAX_EDGES}-flow ceiling. Aggregate the smallest "
            f"together first.")
    return edges, nodes


def layers_of(nodes: list[str], edges: list[dict]) -> dict[str, int]:
    """The stage of each node, by longest path from a source. Refuses a cycle.

    A layered drawing invents an order, so the order has to exist in the data: if volume can
    return to an earlier stage there are no stages, and the picture would be a fiction.
    """
    incoming: dict[str, list[str]] = {n: [] for n in nodes}
    for edge in edges:
        incoming[edge["dst"]].append(edge["src"])
    layer: dict[str, int] = {}

    def depth(node: str, trail: tuple[str, ...]) -> int:
        if node in layer:
            return layer[node]
        if node in trail:
            cycle = " → ".join(trail[trail.index(node):] + (node,))
            die(f"the flows contain a cycle: {cycle}. A Sankey draws stages, and volume that "
                f"returns to an earlier stage has no stage to be drawn in. Break the cycle by "
                f"aggregating those nodes, or use the heatmap for the pair counts.")
        if not incoming[node]:
            layer[node] = 0
            return 0
        layer[node] = 1 + max(depth(parent, trail + (node,)) for parent in incoming[node])
        return layer[node]

    for node in nodes:
        depth(node, ())
    return layer


# ----------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True)
    ap.add_argument("--from", dest="src", required=True, help="the column the flow leaves")
    ap.add_argument("--to", dest="dst", required=True, help="the column the flow arrives at")
    ap.add_argument("--value", required=True, help="the quantity carried")
    ap.add_argument("--title", required=True)
    ap.add_argument("--source", default="")
    ap.add_argument("--requested-by", default="")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--feedback-to", default="", metavar="ADDRESS_OR_ISSUE_URL",
                    help=feedback_link.FLAG_HELP)
    i18n.add_lang_argument(ap)
    args = ap.parse_args(argv)
    t = i18n.load(STRINGS, args.lang)
    lang = args.lang

    edges, nodes = load(args.data, args.src, args.dst, args.value)
    layer = layers_of(nodes, edges)

    inflow = {n: 0.0 for n in nodes}
    outflow = {n: 0.0 for n in nodes}
    for edge in edges:
        outflow[edge["src"]] += edge["value"]
        inflow[edge["dst"]] += edge["value"]

    # The balance check: an intermediate node must pass on what arrived.
    unbalanced = [(n, inflow[n], outflow[n]) for n in nodes
                  if inflow[n] > TOL and outflow[n] > TOL
                  and abs(inflow[n] - outflow[n]) > TOL]
    if unbalanced:
        listed = "; ".join(f"{n} ({fmt(i, 'nb', 0)} in, {fmt(o, 'nb', 0)} out)"
                           for n, i, o in unbalanced[:4])
        die(f"{len(unbalanced)} node(s) do not balance: {listed}. A flow diagram where volume "
            f"appears or vanishes between stages is decoration. Add the missing flow, or leave "
            f"the node out of the middle of the picture.")

    sources = [n for n in nodes if inflow[n] <= TOL]
    sinks = [n for n in nodes if outflow[n] <= TOL]
    total = sum(outflow[n] for n in sources)

    # The layout: one common scale, so a ribbon has the same meaning at both ends.
    columns: dict[int, list[str]] = {}
    for node in nodes:
        columns.setdefault(layer[node], []).append(node)
    width_stage = max(columns) + 1
    totals = {stage: sum(outflow[n] + (inflow[n] if not outflow[n] else 0.0)
                         for n in members) for stage, members in columns.items()}
    tallest = max(totals.values())
    plot_h = 460
    scale = (plot_h - GAP_MIN * (max(len(m) for m in columns.values()) - 1)) / tallest

    positions: dict[str, dict] = {}
    step = (W - 2 * SIDE - NODE_W) / max(1, width_stage - 1)
    for stage in sorted(columns):
        members = sorted(columns[stage], key=lambda n: (-(outflow[n] or inflow[n]), n))
        used = sum((outflow[n] or inflow[n]) * scale for n in members)
        gaps = (plot_h - used) / (len(members) + 1)
        y = PAD_T + gaps
        for node in members:
            height = max(2.0, (outflow[node] or inflow[node]) * scale)
            positions[node] = {"x": SIDE + stage * step, "y": y, "h": height}
            y += height + gaps

    height = PAD_T + plot_h + PAD_B
    out = [f'<svg viewBox="0 0 {W} {height}" role="img" aria-labelledby="sk-t sk-d">',
           f'<title id="sk-t">{html.escape(t["svg_title"])}</title>',
           f'<desc id="sk-d">{html.escape(i18n.fill(t["svg_desc"], nodes=len(nodes), edges=len(edges), value=args.value, total=fmt(total, lang, decimals_of([total]))))}</desc>']

    # Ribbons first, so the node bars sit on top of their own ends.
    out_used = {n: 0.0 for n in nodes}
    in_used = {n: 0.0 for n in nodes}
    order = sorted(edges, key=lambda e: (layer[e["src"]], positions[e["src"]]["y"],
                                        positions[e["dst"]]["y"]))
    for edge in order:
        s, d = positions[edge["src"]], positions[edge["dst"]]
        thickness = max(1.0, edge["value"] * scale)
        y0 = s["y"] + out_used[edge["src"]]
        y1 = d["y"] + in_used[edge["dst"]]
        out_used[edge["src"]] += thickness
        in_used[edge["dst"]] += thickness
        x0, x1 = s["x"] + NODE_W, d["x"]
        mid = (x0 + x1) / 2
        path = (f"M{x0:.2f},{y0:.2f} C{mid:.2f},{y0:.2f} {mid:.2f},{y1:.2f} {x1:.2f},{y1:.2f} "
                f"L{x1:.2f},{y1 + thickness:.2f} "
                f"C{mid:.2f},{y1 + thickness:.2f} {mid:.2f},{y0 + thickness:.2f} "
                f"{x0:.2f},{y0 + thickness:.2f} Z")
        # The band's own geometry is written beside the path: a reader never sees it, and the
        # suite can check the drawn shape against the arithmetic instead of re-deriving the
        # curve.
        out.append(f'<path class="sk-flow" data-src="{html.escape(edge["src"])}" '
                   f'data-dst="{html.escape(edge["dst"])}" data-value="{edge["value"]:g}" '
                   f'data-y0="{y0:.2f}" data-y1="{y1:.2f}" data-thick="{thickness:.2f}" '
                   f'd="{path}">'
                   f'<title>{html.escape(edge["src"])} → {html.escape(edge["dst"])}: '
                   f'{html.escape(fmt(edge["value"], lang, decimals_of([edge["value"]])))}'
                   f'</title></path>')

    for node in nodes:
        p = positions[node]
        out.append(f'<rect class="sk-node" data-node="{html.escape(node)}" x="{p["x"]:.2f}" '
                   f'y="{p["y"]:.2f}" width="{NODE_W}" height="{p["h"]:.2f}" rx="2"/>')
        label_x = p["x"] - 8 if layer[node] > 0 else p["x"] + NODE_W + 8
        anchor = "end" if layer[node] > 0 else "start"
        out.append(f'<text class="sk-label" x="{label_x:.2f}" y="{p["y"] + p["h"] / 2 + 5:.2f}" '
                   f'text-anchor="{anchor}">{html.escape(node)}</text>')
    for stage in sorted(columns):
        # The last stage sits at the right edge, and a centred label there is clipped by the
        # canvas: the first build printed "Trinn" and lost the number.
        x = min(SIDE + stage * step + NODE_W / 2, W - 34)
        # Both edges need clamping: the first stage sits at x = 14, and a centred label there
        # runs off the left of the canvas, which the browser check reported.
        if x <= 40:
            anchor = "start"
            x = 2
        elif x >= W - 36:
            anchor = "end"
        else:
            anchor = "middle"
        out.append(f'<text class="sk-stage" x="{x:.2f}" y="{PAD_T - 18}" '
                   f'text-anchor="{anchor}">'
                   f'{html.escape(i18n.fill(t["stage_label"], n=stage + 1))}</text>')
    out.append("</svg>")
    drawing = "\n".join(out)

    dec = decimals_of([e["value"] for e in edges] + [total])
    biggest = max(edges, key=lambda e: e["value"])
    summary = i18n.fill(t["summary_line"], nodes=len(nodes), edges=len(edges),
                        start=len(sources), end=len(sinks), total=fmt(total, lang, dec))
    summary += " " + i18n.fill(t["summary_biggest"], src=biggest["src"], dst=biggest["dst"],
                               value=fmt(biggest["value"], lang, dec))
    summary += " " + t["summary_balanced"]

    notes = [t["note_balance"], t["note_scale"], t["note_layers"], t["note_positive"],
             t["note_table"]]

    table = []
    for edge in sorted(edges, key=lambda e: (-e["value"], e["src"], e["dst"])):
        share = edge["value"] / total * 100 if total else 0.0
        table.append(
            "<tr>"
            f"<td>{html.escape(edge['src'])}</td>"
            f"<td>{html.escape(edge['dst'])}</td>"
            f'<td class="num">{html.escape(fmt(edge["value"], lang, dec))}</td>'
            f'<td class="num">{html.escape(fmt(share, lang, 1))}</td>'
            "</tr>")
    node_rows = []
    for node in sorted(nodes, key=lambda n: (layer[n], -outflow[n], n)):
        node_rows.append(
            "<tr>"
            f"<td>{html.escape(node)}</td>"
            f'<td class="num">{layer[node] + 1}</td>'
            f'<td class="num">{html.escape(fmt(inflow[node], lang, dec))}</td>'
            f'<td class="num">{html.escape(fmt(outflow[node], lang, dec))}</td>'
            "</tr>")

    source = args.source or NOT_STATED
    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)

    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=built,
                                           source=source, lang=lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css)))
    for token, value in {
        "{{TITLE}}": html.escape(args.title),
        "{{SUBTITLE}}": html.escape(i18n.fill(t["sub_line"], nodes=len(nodes),
                                              edges=len(edges),
                                              total=fmt(total, lang, dec))),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(i18n.fill(t["source_line"], name=source, rows=len(edges))),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{ROWS_INLINED}}": str(len(edges)),
        "{{CAPTION}}": html.escape(t["caption"]),
        "{{SUMMARY}}": html.escape(summary),
        "{{DRAWING}}": drawing,
        "{{NOTES}}": "".join(f"<li>{html.escape(n)}</li>" for n in notes),
        "{{TABLE_ROWS}}": "\n".join(table),
        "{{NODE_ROWS}}": "\n".join(node_rows),
        "{{FEEDBACK_BLOCK}}": feedback,
    }.items():
        page = page.replace(token, value)
    if "{{" in page:
        left = sorted({piece.split("}}")[0] + "}}" for piece in page.split("{{")[1:]})
        die(f"the template still holds {', '.join(left)} after filling")

    data = page.encode("utf-8")
    if len(data) > MAX_BYTES:
        die(f"the file is {len(data) / 1048576:.1f} MB, over the 40 MB ceiling")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)

    print(f"nodes         : {len(nodes)} in {width_stage} stages")
    print(f"flows         : {len(edges)}, total {fmt(total, 'nb', dec)}")
    print(f"balanced      : {len(nodes) - len(sources) - len(sinks)} intermediate node(s)")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
