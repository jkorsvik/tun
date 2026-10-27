#!/usr/bin/env python3
"""
render_preview.py: render the three Tún SVGs in a real browser, for a human to look at.

Needs Playwright, so run it through uv:

    uv run --extra verify python plugins/tun/assets/render_preview.py [OUT_DIR]

Writes, to OUT_DIR (default: this folder's preview/):
  * logo.png, mark.png, logo-mono.png: each file opened on its own from a file:// URL,
    the way a browser shows a downloaded .svg
  * preview.png: a contact sheet. The logo, the mark from 160 px down to favicon size
    (32 and 16 px), and the mono logo inlined on a light and a dark background, where it
    takes the text colour.

A clean run proves only that the browser drew something. Look at the images.
"""
from __future__ import annotations

import pathlib
import sys

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
NAMES = ("logo.svg", "mark.svg", "logo-mono.svg")
PAPER, INK = "#f7f7f5", "#0d2b21"


def _inline(name: str, width: str) -> str:
    svg = (HERE / name).read_text(encoding="utf-8")
    svg = svg[svg.find("<svg"):]
    return svg.replace("<svg ", f'<svg style="width:{width};height:auto;display:block" ', 1)


def contact_sheet() -> str:
    img = lambda name, px: (f'<figure><img src="{(HERE / name).as_uri()}" width="{px}">'
                            f"<figcaption>{name} {px}px</figcaption></figure>")
    marks = "".join(img("mark.svg", px) for px in (160, 64, 32, 16))
    return f"""<!doctype html><meta charset="utf-8">
<style>
 body{{margin:0;padding:24px;background:{PAPER};font:14px system-ui,sans-serif;color:{INK}}}
 .row{{display:flex;gap:32px;align-items:flex-end;margin-bottom:24px}}
 figure{{margin:0}} figcaption{{margin-top:6px;font-size:12px}}
 .dark{{background:{INK};color:{PAPER};padding:16px;border-radius:8px}}
</style>
<div class="row">{img("logo.svg", 300)}{img("logo-mono.svg", 300)}</div>
<div class="row">{marks}</div>
<div class="row">
 <figure style="color:{INK}">{_inline("logo-mono.svg", "240px")}
  <figcaption>logo-mono.svg inline, color {INK}</figcaption></figure>
 <figure class="dark">{_inline("logo-mono.svg", "240px")}
  <figcaption>logo-mono.svg inline, color {PAPER}</figcaption></figure>
</div>"""


def main(argv: list[str]) -> int:
    out = pathlib.Path(argv[0]) if argv else HERE / "preview"
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 640, "height": 360},
                                device_scale_factor=2)
        for name in NAMES:
            page.goto((HERE / name).as_uri())
            target = out / name.replace(".svg", ".png")
            page.locator("svg").screenshot(path=str(target))
            print(f"wrote {target}")
        sheet = out / ".contact-sheet.html"
        sheet.write_text(contact_sheet(), encoding="utf-8")
        try:
            page.set_viewport_size({"width": 720, "height": 600})
            page.goto(sheet.as_uri())
            page.screenshot(path=str(out / "preview.png"), full_page=True)
            print(f"wrote {out / 'preview.png'}")
        finally:
            sheet.unlink()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
