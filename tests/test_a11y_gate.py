#!/usr/bin/env python3
"""The accessibility verifier must fail on a defect and pass on the artefact we ship.

A new gate that has only ever printed green is not evidence of anything: the first run of
`tools/verify_a11y.py` on the hello dashboard printed "0 findings" over three thousand text
runs, which is either a clean artefact or a probe that measures nothing. This suite settles
which, by planting one defect per rule in a copy of a clean page and requiring exactly that
rule to fire, and by running the real documented example through the tool.

Needs Playwright, like every other browser suite here, and fails rather than skipping
without it.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "verify_a11y.py"
EXAMPLE = ROOT / "examples" / "01-hello-dashboard" / "salg-dashboard.html"

passed = failed = 0


def chk(label, got, want):
    global passed, failed
    if got == want:
        print(f"  PASS {label}")
        passed += 1
    else:
        print(f"  FAIL {label}: got {got!r}, wanted {want!r}")
        failed += 1


CLEAN = """<!doctype html>
<html lang="nb">
<head><meta charset="utf-8"><title>Ren side</title>
<style>
  body { background:#ffffff; color:#10161a; font:16px/1.5 system-ui, sans-serif; }
  h1 { font-size:24px; }
  .btn { background:#2F5D9E; color:#ffffff; border:0; padding:12px 20px; min-height:44px; }
</style></head>
<body>
<h1>Salg per region</h1>
<h2>Tabell</h2>
<p>Ett tall per region.</p>
<button class="btn">Oppdater</button>
<a href="#detaljer">Se detaljer</a>
<label for="region">Region</label>
<select id="region"><option>Alle</option></select>
<svg role="img" aria-label="Søylediagram" width="120" height="40"><rect width="120" height="40" fill="#2F5D9E"></rect></svg>
<h2 id="detaljer">Detaljer</h2>
</body></html>
"""


def run(html: str, tmp: pathlib.Path, name: str) -> tuple[int, str]:
    path = tmp / name
    path.write_text(html, encoding="utf-8")
    done = subprocess.run([sys.executable, str(TOOL), str(path), "--quiet"],
                          capture_output=True, text=True)
    return done.returncode, done.stdout + done.stderr


def main() -> int:
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("ERROR: playwright is not installed, so nothing was measured.")
        print("       uv sync --extra verify && uv run playwright install chromium")
        return 2

    print("the probe runs, and a clean page is clean")
    chk("the tool is a file", TOOL.is_file(), True)
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        code, clean_out = run(CLEAN, tmp, "clean.html")
        chk("a clean page exits 0", code, 0)
        chk("and prints no rule name",
            [r for r in ("lang", "title", "heading", "control-name", "img-name",
                         "svg-name", "contrast", "duplicate-id", "tabindex",
                         "aria-hidden-focusable") if r + " " in clean_out], [])

        # One defect per rule. Each mutant must fail, and fail under its own rule name:
        # a page that trips the wrong rule would still "fail", so the name is the check.
        mutants = {
            "lang": CLEAN.replace('<html lang="nb">', "<html>"),
            "heading": CLEAN.replace("<h1>Salg per region</h1>", "<h1>Salg per region</h1><h1>Igjen</h1>"),
            "heading-levels": CLEAN.replace("<h2>Tabell</h2>", "<h4>Tabell</h4>"),
            "control-name": CLEAN.replace('<button class="btn">Oppdater</button>',
                                          '<button class="btn"></button>'),
            "label-gone": CLEAN.replace('<label for="region">Region</label>', ""),
            "svg-name": CLEAN.replace(' role="img" aria-label="Søylediagram"', ""),
            "contrast": CLEAN.replace("color:#10161a", "color:#bbbbbb"),
            "contrast-brand": CLEAN.replace('class="btn">Oppdater', 'class="btn" style="background:#ffffff;color:#ffffff">Oppdater'),
            "duplicate-id": CLEAN.replace("<p>Ett tall per region.</p>",
                                          '<p id="region">Ett tall per region.</p>'),
            "tabindex": CLEAN.replace('<button class="btn">', '<button class="btn" tabindex="3">'),
            "aria-hidden": CLEAN.replace('<button class="btn">',
                                         '<button class="btn" aria-hidden="true">'),
        }
        for name, html in mutants.items():
            code, out = run(html, tmp, f"{name}.html")
            rule = {"heading-levels": "heading", "label-gone": "control-name",
                    "contrast-brand": "contrast"}.get(name, name)
            chk(f"mutant {name}: exits 1", code, 1)
            chk(f"mutant {name}: reported under '{rule}'", rule in out, True)

        # The clean page must not carry the finding the mutant produced. Without this the
        # mutants above could be passing for a reason that was already in the fixture.
        for name in mutants:
            rule = {"heading-levels": "heading", "label-gone": "control-name",
                    "contrast-brand": "contrast"}.get(name, name)
            chk(f"the clean page does not already have '{rule}'",
                rule + " " in clean_out, False)

        # Two things the first version of the probe got wrong, kept as checks so they stay
        # wrong-free: a 7% tint is not solid paint, and an icon inside an aria-hidden
        # container is not an unnamed image. Both produced false findings on real artefacts.
        tinted = CLEAN.replace("h1 { font-size:24px; }",
                               "h1 { font-size:24px; }\n  .tint { background:rgba(0,52,62,.07); padding:8px; }")
        tinted = tinted.replace("<h2>Tabell</h2>", '<h2 class="tint">Tabell</h2>')
        code, out = run(tinted, tmp, "tinted.html")
        chk("a 7% tint behind dark text is not a contrast finding", code, 0)

        ICON = ('<svg width="16" height="16" viewBox="0 0 16 16">'
                '<circle cx="8" cy="8" r="3"></circle></svg>')
        hidden_icon = CLEAN.replace(
            '<svg role="img" aria-label="Søylediagram"',
            '<button class="btn" aria-label="Bytt tema">'
            + ICON.replace("<svg ", '<svg aria-hidden="true" ') + "</button>"
            '<span aria-hidden="true">' + ICON + "</span>"
            '<svg role="img" aria-label="Søylediagram"')
        code, out = run(hidden_icon, tmp, "hidden-icon.html")
        chk("an icon inside an aria-hidden container is not an unnamed image", code, 0)
        code, out = run(hidden_icon.replace('<span aria-hidden="true">', "<span>"),
                        tmp, "unhidden-icon.html")
        chk("and the same icon outside one is reported", code, 1)

        # A fragment is not a document: no lang, no title, no h1 by construction.
        code, out = run(CLEAN.split("<body>")[1].split("</body>")[0], tmp, "piece.fragment.html")
        chk("an HTML fragment is skipped, not failed", code, 0)
        chk("and says why", "fragment" in out, True)

        # A file that is not there is an error, not a pass.
        done = subprocess.run([sys.executable, str(TOOL), str(tmp / "gone.html"), "--quiet"],
                              capture_output=True, text=True)
        chk("a missing file exits 2", done.returncode, 2)

    print("the artefact we actually ship passes it")
    chk("the hello dashboard exists", EXAMPLE.is_file(), True)
    done = subprocess.run([sys.executable, str(TOOL), str(EXAMPLE)],
                          capture_output=True, text=True)
    chk("verify_a11y on the hello dashboard exits 0", done.returncode, 0)
    chk("and measured text rather than nothing",
        "text runs measured" in done.stdout, True)
    chk("and says what it did not check", "not checked here" in done.stdout, True)

    print()
    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
