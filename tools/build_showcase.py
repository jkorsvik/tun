#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
build_showcase.py: one document that shows every example this repository has, and lets you
use each of them from inside it.

The point is not a catalogue. It is the proof, on one page, that each artefact exists, that
it renders, and that the command in its own README still produces it. So every reader here is
the real thing: the card shows a photograph, taken by a real browser from a file:// URL at
build time, and clicking it opens the actual page, embedded and runnable.

Both languages travel in the file. A reader switches between Norwegian and English in the
page itself, the way tun.community does, rather than asking the builder for one of them.

    python3 tools/build_showcase.py \
        --examples examples \
        --title "Tun: alle eksempel" \
        --source "the built examples in this repository" \
        --requested-by "Prosjekteier" \
        --out examples/54-showcase/oversikt.html

Requires Playwright, like the verifiers, and fails without it rather than shipping a page of
empty frames. Stdlib for everything else.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import build_stamp  # noqa: E402
import i18n  # noqa: E402

TEMPLATE = ROOT / "templates" / "showcase.html"
STRINGS = "showcase"

HEADING = re.compile(r"^#\s+(.+?)\s*$", re.M)
BASH = re.compile(r"```(?:bash|sh|console)\n(.*?)```", re.S)
NUMBERED = re.compile(r"^(\d+)-(.+)$")

CHIP_KEYS = ("chip_examples", "chip_builders", "chip_with_command", "chip_suites")


def read_example(folder: pathlib.Path) -> dict | None:
    """Title, one-line purpose and build command, read from the example's own README."""
    readme = folder / "README.md"
    if not readme.is_file():
        return None
    text = readme.read_text(encoding="utf-8", errors="replace")
    head = HEADING.search(text)
    title = head.group(1).strip() if head else folder.name
    body = text[head.end():] if head else text
    purpose = ""
    for para in re.split(r"\n\s*\n", body):
        line = " ".join(part.strip() for part in para.strip().splitlines())
        if not line or line.startswith(("#", "|", "```", "-", "*", ">", "!")):
            continue
        purpose = re.sub(r"[`*_]", "", line)
        break
    commands = BASH.findall(text)
    command = ""
    if commands:
        lines = [ln.strip() for ln in commands[0].strip().splitlines()]
        command = "\n".join(ln for ln in lines if ln and not ln.startswith("#"))
    built = sorted(folder.glob("*.html"), key=lambda f: f.stat().st_size, reverse=True)
    return {
        "dir": folder,
        "slug": folder.name,
        "title": title,
        "purpose": purpose,
        "command": command,
        "page": built[0] if built else None,
        "extra": len(built) - 1 if built else 0,
    }


SIBLING_JS = re.compile(r'<script\b[^>]*\bsrc="((?:\./)?[^"/:]+)"[^>]*>\s*</script>', re.I)
SIBLING_CSS = re.compile(r'<link\b[^>]*\bhref="((?:\./)?[^"/:]+)"[^>]*>', re.I)


def inline_siblings(page: pathlib.Path) -> bytes:
    """Fold a paired example's sibling files into the page, so it runs embedded.

    A paired dashboard keeps its rows in `data.js` beside it, and the page asks for that file
    by relative path. Inside a document that is not in that folder, the request goes nowhere
    and the reader sees an empty dashboard: correct behaviour, useless preview. So the sibling
    is inlined here, and the page becomes what it claims to be, self-contained.
    """
    text = page.read_text(encoding="utf-8", errors="replace")
    folder = page.parent
    folded = 0

    def js(match: re.Match) -> str:
        nonlocal folded
        candidate = folder / match.group(1)
        if not candidate.is_file():
            return match.group(0)
        body = candidate.read_text(encoding="utf-8", errors="replace")
        folded += 1
        return f"<script>\n{body}\n</script>"

    def css(match: re.Match) -> str:
        nonlocal folded
        candidate = folder / match.group(1)
        if not candidate.is_file() or candidate.suffix != ".css":
            return match.group(0)
        body = candidate.read_text(encoding="utf-8", errors="replace")
        folded += 1
        return f"<style>\n{body}\n</style>"

    text = SIBLING_JS.sub(js, text)
    text = SIBLING_CSS.sub(css, text)
    if folded:
        print(f"  folded {folded} sibling file(s) into {page.parent.name}/{page.name}", flush=True)
    return text.encode("utf-8")


def kind_of(slug: str) -> str:
    match = NUMBERED.match(slug)
    return match.group(2).replace("-", " ") if match else slug.replace("-", " ")


def shoot(pages: list[pathlib.Path], width: int, height: int, quality: int) -> dict[str, bytes]:
    """A JPEG per page, taken from a file:// URL. No browser, no page: fail loudly."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover - the gate exists for exactly this
        sys.exit("build_showcase: Playwright is required to photograph the examples.\n"
                 "  uv sync --extra verify && uv run playwright install chromium")
    shots: dict[str, bytes] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        for path in pages:
            page.goto(path.resolve().as_uri(), wait_until="load")
            page.wait_for_timeout(350)
            shots[path.name] = page.screenshot(type="jpeg", quality=quality)
            print(f"  photographed {path.parent.name}/{path.name}", flush=True)
        browser.close()
    return shots


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="One document that shows every example.")
    ap.add_argument("--examples", default="examples", help="the examples folder")
    ap.add_argument("--out", required=True, help="the HTML file to write")
    ap.add_argument("--title", default="Tun: alle eksempel")
    ap.add_argument("--source", required=True, help="what these artefacts came from, in words")
    ap.add_argument("--requested-by", required=True, help="a role, not a person")
    ap.add_argument("--width", type=int, default=900)
    ap.add_argument("--height", type=int, default=600)
    ap.add_argument("--quality", type=int, default=72, help="JPEG quality, 30-90")
    ap.add_argument("--start-lang", default="nb", choices=("nb", "en"),
                    help="the language the page opens in; the reader can switch")
    args = ap.parse_args(argv)

    folder = pathlib.Path(args.examples)
    if not folder.is_dir():
        sys.exit(f"build_showcase: no such folder: {folder}")
    own_dir = pathlib.Path(args.out).resolve().parent
    examples = [e for e in (read_example(p) for p in sorted(folder.iterdir()) if p.is_dir())
                if e and e["dir"].resolve() != own_dir]
    if not examples:
        sys.exit(f"build_showcase: no examples under {folder}")
    with_page = [e for e in examples if e["page"]]
    if not with_page:
        sys.exit("build_showcase: no built .html in any example, so there is nothing to show. "
                 "Build the examples first.")

    print(f"build_showcase: {len(examples)} example(s), {len(with_page)} with a built page")
    shots = shoot([e["page"] for e in with_page], args.width, args.height, args.quality)

    tables = i18n.load_all(STRINGS)
    strings = tables[args.start_lang]
    cards, embedded = [], 0
    for ex in examples:
        shot = shots.get(ex["page"].name) if ex["page"] else None
        alt = f"{ex['title']} - {kind_of(ex['slug'])}"
        blob = (f'<img src="data:image/jpeg;base64,{base64.b64encode(shot).decode("ascii")}" '
                f'alt="{html.escape(alt)}" loading="lazy">') if shot else ""
        more = f' <span>+{ex["extra"]}</span>' if ex["extra"] > 0 else ""
        search = " ".join([ex["title"], ex["purpose"], kind_of(ex["slug"]), ex["slug"]]).lower()
        command = (f'<details><summary data-i18n="card_command">'
                   f'{html.escape(strings["card_command"])}</summary>'
                   f'<code>{html.escape(ex["command"])}</code></details>') if ex["command"] else ""
        live = ""
        if ex["page"]:
            raw = inline_siblings(ex["page"])
            live = ' data-live="' + base64.b64encode(raw).decode("ascii") + '"'
            embedded += len(raw)
        cards.append(
            f'<li class="card"{live} data-search="{html.escape(search, quote=True)}">'
            f'<button class="shot" type="button" aria-label="{html.escape(alt)}">{blob}</button>'
            f'<div class="body"><span class="kind">{html.escape(kind_of(ex["slug"]))}'
            f' &middot; {html.escape(ex["slug"].split("-")[0])}{more}</span>'
            f'<h2>{html.escape(ex["title"])}</h2>'
            f'<p>{html.escape(ex["purpose"])}</p>{command}</div></li>')

    builders = len(list((ROOT / "tools").glob("build_*.py")))
    suites = len(list((ROOT / "tests").glob("test_*.py")))
    values = {"chip_examples": len(examples), "chip_builders": builders,
              "chip_with_command": len([e for e in examples if e["command"]]),
              "chip_suites": suites}
    chips = "".join(f'<li><span data-i18n="{key}">{html.escape(strings[key])}</span> '
                    f"<b>{values[key]}</b></li>" for key in CHIP_KEYS)

    def column(key: str, names: list[str]) -> str:
        items = "".join(f"<li>{html.escape(n)}</li>" for n in names)
        return (f'<div><h3 data-i18n="{key}">{html.escape(strings[key])}</h3>'
                f"<ul>{items}</ul></div>")

    def stems(glob: str, trim: str) -> list[str]:
        return sorted(p.stem.replace(trim, "").replace("_", " ")
                      for p in ROOT.glob(glob) if p.is_file())

    things = "".join([
        column("col_builders", stems("tools/build_*.py", "build_")),
        column("col_skills", sorted(p.parent.name for p in (ROOT / "skills").rglob("SKILL.md"))),
        column("col_suites", stems("tests/test_*.py", "test_")),
        column("col_docs", stems("docs/*.md", "")),
    ])

    newest = max(with_page, key=lambda e: e["page"].stat().st_mtime)["page"]
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), strings)
            .replace("{{LANG_JSON}}", json.dumps(tables, ensure_ascii=False))
            .replace("{{START_LANG}}", json.dumps(args.start_lang))
            .replace("{{TITLE}}", html.escape(args.title))
            .replace("{{CHIPS}}", chips)
            .replace("{{THINGS}}", things)
            .replace("{{CARDS}}", "\n".join(cards))
            .replace("{{COUNT_ONE_JS}}", json.dumps(strings["count_one"]))
            .replace("{{COUNT_MANY_JS}}", json.dumps(strings["count_many"]))
            .replace("{{SOURCE_DESCRIPTION}}", html.escape(args.source))
            .replace("{{EXTRACT_TIMESTAMP}}", build_stamp.from_mtime(newest, "%Y-%m-%d %H:%M", aware=False))
            .replace("{{BUILD_TIMESTAMP}}", build_stamp.naive())
            .replace("{{REQUESTED_BY}}", html.escape(args.requested_by))
            .replace("{{ROWS_INLINED}}",
                     f"{len(with_page)} runnable artefact(s) of {len(examples)}, "
                     f"{embedded / 1e6:.1f} MB of page carried in this file"))
    page = page.replace("{{T:count_all}}", i18n.fill(strings["count_all"], n=len(examples)))

    target = pathlib.Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")
    size = target.stat().st_size / (1024 * 1024)
    print(f"wrote {target} ({size:.1f} MB, {embedded / 1e6:.1f} MB of it embedded pages)")
    if size > 50:
        print("build_showcase: FAIL over 50 MB. Carry fewer pages or lower --quality.")
        return 1
    if size > 20:
        print("build_showcase: warning over 20 MB. Consider a lower --quality.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
