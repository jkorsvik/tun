#!/usr/bin/env python3
"""Data in a dashboard is text, never markup.

Found 2026-10-16: the single-file dashboard wrote cell values, column names and filter values
into `innerHTML` as they were. A CSV cell `<img src=x onerror=...>` then ran as script in every
reader's browser. Free-text survey answers are a real input, so any data value can hold markup.

This builds a dashboard whose data carries a payload in every path that reaches the page: a
column name, a filter value, a plain cell, and, in paired mode, the `source` and `generated`
lines of `data.js`. Each payload counts in `window.__injected` if it runs, and `<b class="inj">`
shows up if it is parsed. Both must stay at zero, the payload must be visible as text, and the
filter must still select the row whose value holds markup.

A mutation control builds the same file from a copy of the template whose `esc()` changes
nothing. That build must show the injection, or the checks above prove nothing.

Needs Playwright and Chromium, and FAILS without them: a browser check that reports success
without a browser is worse than none (AGENTS.md, verification gate).

    python3 tests/test_dashboard_escapes_data.py
"""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAYLOAD = '<img src=x onerror="window.__injected=(window.__injected||0)+1"><b class="inj">x</b>'
ESC_LINE = re.compile(r'const esc = \(v\) => String\(v \?\? ""\)\.replace\(/\[&<>"\']/g')

PASS = FAIL = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def csv_field(s: str) -> str:
    return '"' + s.replace('"', '""') + '"'


def write_data(path: pathlib.Path) -> None:
    # The payload is a column name (Merknad...), a filter value (Region) and a plain cell.
    head = ["Region", "Produkt", "Belop", "Maaned", "Merknad" + PAYLOAD]
    rows = [
        [PAYLOAD, "A", "100", "2026-01", "fritekst " + PAYLOAD],
        ["Bergen", "B", "200", "2026-02", "vanlig"],
        ["Oslo", "A", "300", "2026-03", "vanlig"],
    ]
    path.write_text("\n".join(",".join(csv_field(c) for c in r) for r in [head] + rows) + "\n",
                    encoding="utf-8")


def build(root: pathlib.Path, data: pathlib.Path, out: pathlib.Path, mode: str) -> bool:
    r = subprocess.run([sys.executable, str(root / "tools" / "build_dashboard.py"),
                        "--data", str(data), "--title", "Escape test", "--dimension", "Produkt",
                        "--measure", "Belop", "--time", "Maaned", "--filters", "Region,Produkt",
                        "--source", "test", "--requested-by", "test", "--mode", mode,
                        "--out", str(out)], capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-800:], r.stderr[-800:])
    return r.returncode == 0


def poison_data_js(out: pathlib.Path) -> bool:
    """Put the payload into the paired data.js source and generated lines."""
    data_js = out.parent / "data.js"
    text = data_js.read_text(encoding="utf-8")
    new, n = re.subn(r'("source"\s*:\s*)"[^"]*"', lambda m: m.group(1) + '"' + PAYLOAD.replace('"', '\\"') + '"', text, count=1)
    new, k = re.subn(r'("generated"\s*:\s*)"[^"]*"', lambda m: m.group(1) + '"' + PAYLOAD.replace('"', '\\"') + '"', new, count=1)
    data_js.write_text(new, encoding="utf-8")
    return n == 1 and k == 1


def probe(page, path: pathlib.Path) -> dict:
    page.goto(path.as_uri())
    page.wait_for_timeout(500)
    return page.evaluate("""() => ({
      injected: window.__injected || 0,
      parsed: document.querySelectorAll('b.inj').length,
      text: document.body.innerText,
      header: [...document.querySelectorAll('#tbl th')].some(th => th.textContent.includes('<img')),
      option: [...document.querySelectorAll('#controls option')].some(o => o.textContent.includes('<img')),
      rows: document.querySelectorAll('#tbl tbody tr').length,
      meta: (document.getElementById('meta') || {}).textContent || '',
    })""")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("FAIL: Playwright is not installed. Install with "
              "`uv sync --extra verify && uv run playwright install chromium`.")
        return 1

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="tun-escape-"))
    try:
        data = tmp / "data.csv"
        write_data(data)

        # Mutant: a copy of tools/ and templates/ whose esc() changes nothing.
        mut = tmp / "mutant"
        shutil.copytree(ROOT / "tools", mut / "tools")
        shutil.copytree(ROOT / "templates", mut / "templates")
        tpl = mut / "templates" / "single-file-dashboard.html"
        src = tpl.read_text(encoding="utf-8")
        mutated, n = ESC_LINE.subn('const esc = (v) => String(v ?? "").replace(/(?!)/g', src)
        tpl.write_text(mutated, encoding="utf-8")
        check("the mutant template has esc() disabled (the control is real)", n == 1, f"{n} matches")

        builds = {
            "bundled": (ROOT, tmp / "bundled" / "d.html", "bundled"),
            "paired": (ROOT, tmp / "paired" / "d.html", "paired"),
            "mutant": (mut, tmp / "mutant-out" / "d.html", "bundled"),
        }
        for name, (root, out, mode) in builds.items():
            check(f"{name}: builds", build(root, data, out, mode))
        check("paired: payload written into data.js source and generated",
              poison_data_js(builds["paired"][1]))

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:  # browser binary missing
                print(f"FAIL: Chromium could not start ({e.__class__.__name__}). "
                      "Run `uv run playwright install chromium`.")
                return 1
            page = browser.new_page()
            for name in ("bundled", "paired"):
                r = probe(page, builds[name][1])
                check(f"{name}: no payload ran", r["injected"] == 0, f"ran {r['injected']} times")
                check(f"{name}: no payload was parsed as markup", r["parsed"] == 0, f"{r['parsed']} elements")
                check(f"{name}: the payload shows as text", "<img" in r["text"])
                check(f"{name}: a column name with markup is a text header", r["header"])
                check(f"{name}: a filter value with markup is a text option", r["option"])
                check(f"{name}: all 3 rows are in the table", r["rows"] == 3, f"{r['rows']} rows")
                if name == "paired":
                    check("paired: the data.js source line shows its markup as text",
                          r["meta"].count("<img") == 2, repr(r["meta"][:120]))
                # The filter still finds the value that holds markup.
                page.select_option("#controls select[data-col='Region']", value=PAYLOAD)
                page.wait_for_timeout(200)
                n = page.evaluate("document.querySelectorAll('#tbl tbody tr').length")
                check(f"{name}: filtering on the markup value leaves its 1 row", n == 1, f"{n} rows")
            r = probe(page, builds["mutant"][1])
            check("mutant: the payload runs without esc() (the checks above can fail)",
                  r["injected"] > 0 and r["parsed"] > 0,
                  f"ran {r['injected']}, parsed {r['parsed']}")
            browser.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"PASS: {PASS}  FAIL: {FAIL}")
    return 1 if FAIL or not PASS else 0


if __name__ == "__main__":
    sys.exit(main())
