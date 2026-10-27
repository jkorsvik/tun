#!/usr/bin/env python3
"""
build_showcase.py: one document that shows every example this repository has.

The point is not a catalogue. It is the proof, on one page, that each artefact exists, that
it renders, and that the command in its own README still produces it. So every picture here
is taken by a real browser from a file:// URL at build time, never drawn by hand: a clean
build is not evidence, and a mock-up is less.

    python3 tools/build_showcase.py \
        --examples examples \
        --title "Tun: alle eksempel" \
        --source "the examples in this repository" \
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
    i18n.add_lang_argument(ap)
    args = ap.parse_args(argv)

    folder = pathlib.Path(args.examples)
    if not folder.is_dir():
        sys.exit(f"build_showcase: no such folder: {folder}")
    examples = [e for e in (read_example(p) for p in sorted(folder.iterdir()) if p.is_dir()) if e]
    if not examples:
        sys.exit(f"build_showcase: no examples under {folder}")
    with_page = [e for e in examples if e["page"]]
    if not with_page:
        sys.exit("build_showcase: no built .html in any example, so there is nothing to show. "
                 "Build the examples first.")

    print(f"build_showcase: {len(examples)} example(s), {len(with_page)} with a built page")
    shots = shoot([e["page"] for e in with_page], args.width, args.height, args.quality)

    strings = i18n.load(STRINGS, args.lang)
    cards = []
    for ex in examples:
        shot = shots.get(ex["page"].name) if ex["page"] else None
        alt = f"{ex['title']} - {kind_of(ex['slug'])}"
        blob = (f'<img src="data:image/jpeg;base64,{base64.b64encode(shot).decode("ascii")}" '
                f'alt="{html.escape(alt)}" loading="lazy">') if shot else ""
        more = f' <span>+{ex["extra"]}</span>' if ex["extra"] > 0 else ""
        search = " ".join([ex["title"], ex["purpose"], kind_of(ex["slug"]), ex["slug"]]).lower()
        command = (f'<details><summary>{html.escape(strings["card_command"])}</summary>'
                   f'<code>{html.escape(ex["command"])}</code></details>') if ex["command"] else ""
        cards.append(
            f'<li class="card" data-search="{html.escape(search, quote=True)}">'
            f'<button class="shot" type="button" aria-label="{html.escape(alt)}">{blob}</button>'
            f'<div class="body"><span class="kind">{html.escape(kind_of(ex["slug"]))}'
            f' &middot; {html.escape(ex["slug"].split("-")[0])}{more}</span>'
            f'<h2>{html.escape(ex["title"])}</h2>'
            f'<p>{html.escape(ex["purpose"])}</p>{command}</div></li>')

    builders = len(list((ROOT / "tools").glob("build_*.py")))
    suites = len(list((ROOT / "tests").glob("test_*.py")))
    chips = "".join(
        f"<li>{label} <b>{value}</b></li>" for label, value in
        (("Eksempel" if args.lang == "nb" else "Examples", len(examples)),
         ("Byggjarar" if args.lang == "nb" else "Builders", builders),
         ("Med kommando" if args.lang == "nb" else "With a command",
          len([e for e in examples if e["command"]])),
         ("Testar" if args.lang == "nb" else "Suites", suites)))

    def column(heading: str, names: list[str]) -> str:
        items = "".join(f"<li>{html.escape(n)}</li>" for n in names)
        return f"<div><h3>{html.escape(heading)}</h3><ul>{items}</ul></div>"

    def stems(glob: str, trim: str) -> list[str]:
        return sorted(p.stem.replace(trim, "").replace("_", " ")
                      for p in ROOT.glob(glob) if p.is_file())

    nb = args.lang == "nb"
    things = "".join([
        column("Byggjarar" if nb else "Builders", stems("tools/build_*.py", "build_")),
        column("Ferdigheiter" if nb else "Skills",
               sorted(p.parent.name for p in (ROOT / "skills").rglob("SKILL.md"))),
        column("Testar" if nb else "Suites", stems("tests/test_*.py", "test_")),
        column("Dokument" if nb else "Docs", stems("docs/*.md", "")),
    ])
    newest = max(with_page, key=lambda e: e["page"].stat().st_mtime)["page"]
    out = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), strings)
           .replace("{{TITLE}}", html.escape(args.title))
           .replace("{{SUBTITLE}}", html.escape(strings["footer_how"]))
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
                    f"{len(with_page)} photographed artefact(s) of {len(examples)}"))
    out = out.replace("{{T:count_all}}", i18n.fill(strings["count_all"], n=len(examples)))

    target = pathlib.Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(out, encoding="utf-8")
    size = target.stat().st_size / (1024 * 1024)
    print(f"wrote {target} ({size:.1f} MB)")
    if size > 50:
        print("build_showcase: FAIL over 50 MB. Photograph fewer pages or lower --quality.")
        return 1
    if size > 20:
        print("build_showcase: warning over 20 MB. Consider a lower --quality.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
