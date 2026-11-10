#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
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

import json
import os
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


# No exfiltration or remote endpoint: the marker changes one local boolean only.
BOUNDARY_MARKER = '<svg onload=window.__boundary=1></svg>'
BOUNDARY_TEXT = '</ScRiPt>' + BOUNDARY_MARKER + '&\u2028\u2029'


def boundary_build(root: pathlib.Path, folder: pathlib.Path, case: str) -> pathlib.Path:
    """Use the real CLI. Each case isolates one input-to-output boundary."""
    folder.mkdir(parents=True, exist_ok=True)
    dim, measure, time_col = 'Category', 'Value', 'Month'
    row = {dim: 'A', measure: 1, time_col: '2026-01'}
    source = 'Synthetic test'
    mode = 'paired' if case.startswith('paired-') else 'bundled'
    extra = []
    if case == 'row' or case == 'paired-row':
        row[dim] = BOUNDARY_TEXT
    elif case == 'meta':
        source = BOUNDARY_TEXT
    elif case in ('dimension', 'measure', 'time', 'filter'):
        column = BOUNDARY_TEXT + 'end'
        if case == 'dimension':
            row[column] = row.pop(dim); dim = column
        elif case == 'measure':
            row[column] = row.pop(measure); measure = column
        elif case == 'time':
            row[column] = row.pop(time_col); time_col = column
        else:
            row[column] = 'A'; extra += ['--filters', column]
    elif case == 'paired-source':
        source = 'Synthetic\nwindow.__boundary=1;//\r\u2028\u2029'
    elif case == 'paired-filename':
        pass
    elif case in ('kpi-label', 'kpi-measure'):
        # No script terminator: this reaches innerHTML after safe JavaScript parsing.
        if case == 'kpi-label':
            dim = BOUNDARY_MARKER
            row[dim] = row.pop('Category')
        else:
            measure = BOUNDARY_MARKER
            row[measure] = row.pop('Value')
    elif case == 'placeholder':
        dim = '+(window.__boundary=1)+'
        row[dim] = row.pop('Category')
        row['Note'] = '{{FILTER_COLS_JSON}}'
    elif case == 'static-placeholder':
        dim = '{{FEEDBACK_BLOCK}}'
        row[dim] = row.pop('Category')
        extra += ['--feedback-to', 'https://example.org/feedback']
    elif case != 'export':
        raise AssertionError(case)
    data = folder / 'input.json'
    data.write_text(json.dumps([row]), encoding='utf-8')
    out = folder / ('page\u2028control.html' if case == 'paired-filename' else 'page.html')
    command = [sys.executable, str(root / 'tools/build_dashboard.py'), '--data', str(data),
               '--title', 'Boundary test', '--dimension', dim, '--measure', measure,
               '--time', time_col, '--source', source, '--requested-by', 'Test role',
               '--mode', mode, '--out', str(out), *extra]
    result = subprocess.run(command, capture_output=True, text=True,
                            env=dict(os.environ, SOURCE_DATE_EPOCH='1794265200'))
    if result.returncode:
        raise AssertionError((case, result.stdout, result.stderr))
    return out


def boundary_probe(browser, path: pathlib.Path, case: str, folder: pathlib.Path) -> dict:
    context = browser.new_context(accept_downloads=True)
    remote, errors = [], []
    context.route(re.compile(r'^https?://'), lambda route: (remote.append(route.request.url), route.abort())[1])
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(path.as_uri())
    page.wait_for_timeout(120)
    exported = None
    if case == 'export':
        # Same source field the normal file refresh/export UI reads. A filename can
        # contain a line break on supported desktop filesystems.
        page.evaluate("source => { DATA_META.source = source; document.getElementById('export').disabled = false; }",
                      'Synthetic\nwindow.__boundary=1;//\r\u2028\u2029')
        with page.expect_download() as info:
            page.click('#export')
        sidecar = folder / 'download.js'
        info.value.save_as(sidecar)
        exported = sidecar.read_text(encoding='utf-8')
        # Read the downloaded JavaScript as the next paired recipient does.
        target = folder / 'recipient.html'
        target.write_text('<!doctype html><script src="./download.js"></script>')
        page.goto(target.as_uri())
    observed = page.evaluate("""() => ({
        marker: window.__boundary === 1,
        parsed: document.querySelectorAll('svg[onload]').length,
        rows: (window.DASHBOARD_DATA || []).length,
        data: window.DASHBOARD_DATA,
        source: (window.DASHBOARD_META || {}).source,
        tableRows: document.querySelectorAll('#tbl tbody tr').length,
        staticHeaders: [...document.querySelectorAll('#nojs th')].map(e => e.textContent),
    })""")
    observed.update(errors=errors, remote=remote, exported=exported)
    context.close()
    return observed


def script_boundaries(tmp: pathlib.Path, pw, root: pathlib.Path = ROOT) -> dict:
    cases = ('row', 'meta', 'dimension', 'measure', 'time', 'filter', 'paired-row',
             'paired-source', 'paired-filename', 'kpi-label', 'kpi-measure', 'placeholder', 'static-placeholder', 'export')
    outputs = {case: boundary_build(root, tmp / case, case) for case in cases}
    receipts = {}
    for engine in ('chromium', 'webkit'):
        browser = getattr(pw, engine).launch()
        for case, path in outputs.items():
            got = boundary_probe(browser, path, case, path.parent)
            receipts[(engine, case)] = got
            check(f'{engine}/{case}: no marker or markup crosses the output boundary',
                  not got['marker'] and not got['parsed'])
            check(f'{engine}/{case}: JavaScript and data survive',
                  not got['errors'] and got['rows'] == 1, str(got['errors']))
            check(f'{engine}/{case}: no remote request', not got['remote'])
            if case in ('row', 'paired-row'):
                check(f'{engine}/{case}: original cell survives exactly',
                      got['data'][0]['Category'] == BOUNDARY_TEXT if got['data'] else False)
            if case == 'meta':
                check(f'{engine}/{case}: original source survives exactly', got['source'] == BOUNDARY_TEXT)
            if case == 'static-placeholder':
                check(f'{engine}/{case}: no HTML template expansion in static headers',
                      '{{FEEDBACK_BLOCK}}' in got['staticHeaders'])
            if case == 'placeholder':
                check(f'{engine}/{case}: no JSON template expansion',
                      got['data'][0]['Note'] == '{{FILTER_COLS_JSON}}' if got['data'] else False)
        browser.close()
    return receipts


def literal_boundaries(tmp: pathlib.Path, pw) -> None:
    tmp.mkdir(parents=True, exist_ok=True)
    literal = '{{DATA_MODE}} {{REQUESTED_BY}} {{FEEDBACK_BLOCK}}'
    data = tmp / 'literal.json'
    data.write_text(json.dumps([{literal: literal, 'Value': 1}]), encoding='utf-8')
    out = tmp / 'literal.html'
    result = subprocess.run([sys.executable, str(ROOT / 'tools/build_dashboard.py'),
        '--data', str(data), '--title', literal, '--dimension', literal, '--measure', 'Value',
        '--source', literal, '--requested-by', literal, '--feedback-to', 'https://example.org/feedback',
        '--out', str(out)], capture_output=True, text=True)
    check('literal dashboard: template-shaped caller text builds', result.returncode == 0, result.stderr)
    if result.returncode:
        return
    for engine in ('chromium', 'webkit'):
        browser = getattr(pw, engine).launch()
        for scripting in (True, False):
            context = browser.new_context(java_script_enabled=scripting)
            page = context.new_page();page.goto(out.as_uri())
            check(f'{engine}/{scripting}: static header and cell keep all literal tokens',
                  literal in page.locator('#nojs th').all_text_contents()
                  and literal in page.locator('#nojs td').all_text_contents())
            check(f'{engine}/{scripting}: heading keeps literal tokens', page.locator('h1').inner_text() == literal)
            if scripting:
                check(f'{engine}: source and row keep literal tokens',
                      page.evaluate('window.DASHBOARD_META.source') == literal
                      and page.evaluate('window.DASHBOARD_DATA[0]', ) == {literal: literal, 'Value': 1})
            context.close()
        browser.close()


def boundary_mutations(tmp: pathlib.Path, pw) -> None:
    """Delete each boundary guard independently in a private copy, never this tree."""
    mutations = (
        ('rows', 'row', 'tools/build_dashboard.py',
         'payload = tun_core.as_script_json(rows)', 'payload = json.dumps(rows)'),
        ('meta', 'meta', 'tools/build_dashboard.py',
         'meta_js = tun_core.as_script_json({', 'meta_js = json.dumps({'),
        ('filter', 'filter', 'tools/build_dashboard.py',
         'tun_core.as_script_json(filters or [args.dimension], separators=None)',
         'json.dumps(filters or [args.dimension])'),
        ('keys', 'time', 'tools/build_dashboard.py',
         'tun_core.as_script_json(value)', 'json.dumps(value)'),
        ('source fallback', 'meta', 'tools/build_dashboard.py',
         '"DATA_META.source || " + tun_core.as_script_json(source_name)',
         '"DATA_META.source || " + json.dumps(source_name)'),
        ('KPI dimension', 'kpi-label', 'tools/build_dashboard.py',
         '${esc(META.dimension)}`, value: fmt(dims)', '${META.dimension}`, value: fmt(dims)'),
        ('KPI measure', 'kpi-measure', 'tools/build_dashboard.py',
         '${esc(META.measure)}`, value: fmt(total)', '${META.measure}`, value: fmt(total)'),
        ('sidecar source', 'paired-source', 'tools/build_dashboard.py',
         're.sub(r"[\\r\\n\\u2028\\u2029]", " ", source_name)', 'source_name'),
        ('sidecar filename', 'paired-filename', 'tools/build_dashboard.py',
         're.sub(r"[\\r\\n\\u2028\\u2029]", " ", args.out.name)', 'args.out.name'),
        ('single-pass fill', 'static-placeholder', 'tools/build_dashboard.py',
         'page = re.sub(pattern, lambda match: replacements[match[0]], page)',
         'for key, value in replacements.items(): page = page.replace(key, value)'),
        ('client export', 'export', 'templates/single-file-dashboard.html',
         '.replace(/[\\r\\n\\u2028\\u2029]/g, " ")', ''),
    )
    tree = tmp / 'tree'
    for name in ('tools', 'templates', 'plugins'):
        shutil.copytree(ROOT / name, tree / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    browser = pw.chromium.launch()
    for label, case, rel, before, after in mutations:
        path = tree / rel
        original = path.read_text(encoding='utf-8')
        count = original.count(before)
        check(f'mutation/{label}: applied to exactly one guard', count == 1, str(count))
        if count != 1:
            continue
        path.write_text(original.replace(before, after, 1), encoding='utf-8')
        try:
            out = boundary_build(tree, tmp / label.replace(' ', '-'), case)
            got = boundary_probe(browser, out, case, out.parent)
            check(f'mutation/{label}: boundary assertions catch its removal',
                  got['marker'] or got['parsed'] > 0 or bool(got['errors'])
                  or case == 'static-placeholder' and '{{FEEDBACK_BLOCK}}' not in got['staticHeaders'],
                  str(got))
        finally:
            path.write_text(original, encoding='utf-8')
    # Unknown placeholders in the template still fail closed; inserted data is not
    # an unresolved template. This is independent of every guard-removal control.
    template = tree / 'templates/single-file-dashboard.html'
    template.write_text(template.read_text(encoding='utf-8') + '{{UNFILLED}}', encoding='utf-8')
    failed = False
    try:
        boundary_build(tree, tmp / 'missing-template', 'row')
    except AssertionError as error:
        failed = 'UNFILLED' in str(error)
    check('unknown dashboard template token is refused by name', failed)
    template.write_text(template.read_text(encoding='utf-8').replace('{{UNFILLED}}', '{{DIMENSION_COL}}'), encoding='utf-8')
    failed = False
    try:
        boundary_build(tree, tmp / 'unquoted-template', 'row')
    except AssertionError as error:
        failed = 'DIMENSION_COL' in str(error)
    check('unquoted column template token is refused by name', failed)
    browser.close()


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
            script_boundaries(tmp / 'script-boundaries', p)
            literal_boundaries(tmp / 'literal-boundaries', p)
            boundary_mutations(tmp / 'boundary-mutants', p)
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
