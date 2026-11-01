#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a self-contained spatial view of one declared sequence.

The input is a CSV with a step id, a title, a description and X/Y/Z coordinates. The
row order is the sequence. Coordinates place the view; they are never a measure of
value or progress. The same rows also become a static SVG and a full table, so the
WebGL view is never the only route to the facts.

  python3 tools/build_task_space.py \
    --data examples/55-task-space/trinn.csv \
    --step Step --label Title --description Description --x X --y Y --z Z \
    --title "Fra spørsmål til leser" --source "Syntetisk arbeidsflyt (trinn.csv)" \
    --requested-by "Prosjekteier" --out examples/55-task-space/arbeidsflyt.html

The builder refuses fewer than two or more than twelve steps, duplicate ids or points,
non-numeric coordinates, and coordinates outside the declared [-3, 3] display volume.
For branches, ownership or decisions, use the process diagram instead. Stdlib only.
"""
from __future__ import annotations

import argparse
import html
import json
import math
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

TEMPLATE = ROOT / "templates" / "task-space.html"
STRINGS = "task-space"
MIN_STEPS, MAX_STEPS = 2, 12
LIMIT = 3.0


def load(path: pathlib.Path, names: dict[str, str], lang: str) -> list[dict]:
    if not path.is_file():
        die(f"{path} does not exist")
    rows = tun_core.coerce_numbers(tun_core.read_rows(path))
    if not rows:
        die(f"{path.name} has no rows")
    header = tun_core.columns(rows)
    for role, name in names.items():
        if name not in header and f"{name}_{lang}" not in header:
            die(f"--{role} names {name!r}, which is not a column in {path.name}. "
                f"Columns: {', '.join(header)}")
    if not MIN_STEPS <= len(rows) <= MAX_STEPS:
        die(f"{path.name} has {len(rows)} steps. A task space holds {MIN_STEPS} to "
            f"{MAX_STEPS}; split the sequence or use a process diagram for a larger flow.")

    def text(row: dict, name: str) -> str:
        return str(row.get(f"{name}_{lang}", row.get(name, "")) or "").strip()

    tasks, ids, points = [], set(), set()
    for line, row in enumerate(rows, 2):
        step = text(row, names["step"])
        label = text(row, names["label"])
        description = text(row, names["description"])
        if not step or not label or not description:
            die(f"{path.name}:{line}: step, title and description must all be present")
        if step in ids:
            die(f"{path.name}:{line}: duplicate step id {step!r}; each step needs a unique id")
        ids.add(step)
        coords = []
        for axis in ("x", "y", "z"):
            name = names[axis]
            value = tun_core.to_number(row.get(name))
            if value is None or not math.isfinite(float(value)):
                die(f"{path.name}:{line}: {axis.upper()} must be numeric, got {row.get(name)!r}")
            if abs(float(value)) > LIMIT:
                die(f"{path.name}:{line}: {axis.upper()}={value} is outside [-3, 3]. "
                    "Move the point inside the declared display volume")
            coords.append(float(value))
        point = tuple(coords)
        if point in points:
            die(f"{path.name}:{line}: another step already occupies {point}; overlapping "
                "points would hide one of the steps")
        points.add(point)
        tasks.append({"step": step, "label": label, "title": label, "text": description,
                      "pos": coords})
    return tasks


def fallback_svg(tasks: list[dict], t: dict[str, str]) -> str:
    def project(pos: list[float]) -> tuple[float, float]:
        x, y, z = pos
        return 400 + x * 110 + z * 35, 205 - y * 82 + z * 24

    points = [project(task["pos"]) for task in tasks]
    out = [f'<svg class="fallback-svg" viewBox="0 0 800 410" role="img" aria-labelledby="ts-t ts-d">',
           f'<title id="ts-t">{html.escape(t["svg_title"])}</title>',
           f'<desc id="ts-d">{html.escape(i18n.fill(t["svg_desc"], count=len(tasks)))}</desc>']
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        out.append(f'<line class="fb-edge" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
    for i, (task, (x, y)) in enumerate(zip(tasks, points), 1):
        anchor = "end" if x > 650 else "start" if x < 150 else "middle"
        dy = -16 if y > 205 else 25
        out.append(f'<circle class="fb-node" cx="{x:.1f}" cy="{y:.1f}" r="9"/>')
        out.append(f'<text class="fb-label" x="{x:.1f}" y="{y + dy:.1f}" text-anchor="{anchor}">'
                   f'{i}. {html.escape(task["label"])}</text>')
    out.append("</svg>")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True)
    ap.add_argument("--step", default="Step")
    ap.add_argument("--label", default="Title")
    ap.add_argument("--description", default="Description")
    ap.add_argument("--x", default="X")
    ap.add_argument("--y", default="Y")
    ap.add_argument("--z", default="Z")
    ap.add_argument("--title", required=True)
    ap.add_argument("--source", default="")
    ap.add_argument("--requested-by", default="")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--feedback-to", default="", metavar="ADDRESS_OR_ISSUE_URL",
                    help=feedback_link.FLAG_HELP)
    i18n.add_lang_argument(ap)
    args = ap.parse_args(argv)
    lang = args.lang
    t = i18n.load(STRINGS, lang)
    names = {axis: getattr(args, axis) for axis in ("step", "label", "description", "x", "y", "z")}
    tasks = load(args.data, names, lang)
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

    rows = []
    for index, task in enumerate(tasks, 1):
        rows.append(f'<tr data-step="{html.escape(task["step"])}"><td>{index}</td>'
                    f'<td>{html.escape(task["label"])}</td><td>{html.escape(task["text"])}</td>'
                    + "".join(f'<td class="num" data-{axis}="{value:g}">{value:g}</td>'
                              for axis, value in zip(("x", "y", "z"), task["pos"])) + "</tr>")
    payload = json.dumps(tasks, ensure_ascii=False).replace("</", "<\\/")
    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css)))
    for token, value in {
        "{{TITLE}}": html.escape(args.title),
        "{{SUBTITLE}}": html.escape(i18n.fill(t["sub_line"], count=len(tasks))),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(i18n.fill(t["source_line"], name=source, count=len(tasks))),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{ROWS_INLINED}}": str(len(tasks)),
        "{{CAPTION}}": html.escape(t["caption"]),
        "{{SUMMARY}}": html.escape(t["summary"]),
        "{{NOTES}}": "".join(f"<li>{html.escape(t[key])}</li>" for key in
                             ("note_shape", "note_interaction", "note_fallback")),
        "{{FALLBACK_SVG}}": fallback_svg(tasks, t),
        "{{TABLE_ROWS}}": "\n".join(rows),
        "{{TASKS_JSON}}": payload,
        "{{FEEDBACK_BLOCK}}": feedback,
    }.items():
        page = page.replace(token, value)
    if "{{" in page:
        left = sorted({piece.split("}}")[0] + "}}" for piece in page.split("{{")[1:]})
        die(f"the template still holds {', '.join(left)} after filling")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    print(f"steps         : {len(tasks)}")
    print(f"wrote         : {args.out} ({args.out.stat().st_size / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
