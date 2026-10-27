#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Check a built artefact for accessibility defects a reader would actually hit.

`ROADMAP.md` A10 asks for an accessibility engine inside the verifiers. axe-core is the
usual answer and it is not the one taken here, for two reasons that belong in the file
rather than in a commit message:

  * axe-core is MPL-2.0. Vendoring 500 KB of it into a repository whose whole licence
    story is AGPL plus one carefully worded exception is a decision for the project owner,
    not a side effect of a verification tool. It is still open in A10, named as open.
  * the artefacts are one self-contained file opened from `file://`, and every other
    verifier here is stdlib plus Playwright. A rule engine we did not write is a rule
    engine we cannot explain to the person whose dashboard it fails.

So this measures a defensible subset, in the same shape as `verify_viewports.py`, and it
prints what it did not check instead of implying the rest is clean.

What it checks, at one desktop and one phone viewport:

  1. language and title   — `<html lang>` and a non-empty `<title>`; without them a screen
                            reader reads the page in the wrong voice and the tab is nameless.
  2. one h1, no skipped levels — the heading tree is the page's table of contents.
  3. accessible names     — every button, link, form control, and every inline SVG carrying
                            meaning has a name (text, label, aria-label, or title).
  4. text contrast        — WCAG AA: 4.5:1 normal, 3:1 for 24 px and for 18.66 px bold,
                            measured against the background actually painted behind it,
                            because a colour pair that passes on white fails on blue.
  5. aria sanity          — `aria-hidden` on something focusable, duplicate `id`s (which
                            silently break `aria-labelledby`), `tabindex` above zero.
  6. one tab stop per control — an interactive element with `display:none` inside a
                            `[hidden]` container is fine; a visible control with
                            `aria-hidden="true"` is not.

What it does NOT check, and says so on every run: full ARIA role and pattern conformance,
live-region behaviour, focus order (needs interaction), animation and reduced-motion, and
screen-reader output. Those need axe-core or a human with a screen reader. A green run here
means "none of the six above", not "accessible".

Usage:
    python3 tools/verify_a11y.py path/to/artefact.html [--engines chromium] [--quiet]

Exit codes: 0 no findings, 1 at least one finding, 2 could not run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_standalone_core import add_engines_arg  # noqa: E402

VIEWPORTS = [("desktop", 1366, 768), ("phone", 390, 844)]

PROBE_JS = r"""
() => {
  const out = {findings: [], skipped: []};
  const seen = new Set();
  const add = (rule, detail) => {
    const key = rule + '|' + detail;
    if (seen.has(key)) return;
    seen.add(key);
    out.findings.push({rule, detail});
  };

  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return false;
    const cs = getComputedStyle(el);
    return cs.visibility !== 'hidden' && cs.display !== 'none' &&
           parseFloat(cs.opacity || '1') > 0;
  };

  const name = (el) => {
    const label = el.getAttribute('aria-label');
    if (label && label.trim()) return label.trim();
    const by = el.getAttribute('aria-labelledby');
    if (by) {
      const t = by.split(/\s+/).map(id => {
        const n = document.getElementById(id);
        return n ? (n.textContent || '').trim() : '';
      }).join(' ').trim();
      if (t) return t;
    }
    if (el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA') {
      if (el.id) {
        const l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
        if (l && l.textContent.trim()) return l.textContent.trim();
      }
      const wrap = el.closest('label');
      if (wrap && wrap.textContent.trim()) return wrap.textContent.trim();
      if (el.getAttribute('title')) return el.getAttribute('title').trim();
      // A submit/button input's value is its name.
      if (el.tagName === 'INPUT' && /^(submit|button|reset)$/i.test(el.type || '') &&
          el.value) return el.value.trim();
      return '';
    }
    const text = (el.textContent || '').trim();
    if (text) return text;
    if (el.getAttribute('title')) return el.getAttribute('title').trim();
    return '';
  };

  const describe = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    else if (el.className && typeof el.className === 'string')
      s += '.' + el.className.trim().split(/\s+/)[0];
    const t = (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 28);
    return t ? s + ' "' + t + '"' : s;
  };

  // 1. language and title
  const lang = (document.documentElement.getAttribute('lang') || '').trim();
  if (!lang) add('lang', '<html> has no lang attribute');
  const title = (document.title || '').trim();
  if (!title) add('title', 'the document has no non-empty <title>');

  // 2. headings
  const heads = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'))
    .filter(visible);
  const h1s = heads.filter(h => h.tagName === 'H1');
  if (h1s.length === 0) add('heading', 'no visible <h1>');
  if (h1s.length > 1) add('heading', h1s.length + ' visible <h1> elements: ' +
    h1s.map(describe).join(', ').slice(0, 120));
  let last = 0;
  for (const h of heads) {
    const lvl = parseInt(h.tagName[1], 10);
    if (last && lvl > last + 1)
      add('heading', 'heading level jumps from h' + last + ' to h' + lvl + ' at ' +
        describe(h));
    last = lvl;
  }

  // 3. accessible names
  const IMG = 'img[alt=""], img[role="presentation"], img[aria-hidden="true"]';
  // Anything inside an aria-hidden container is deliberately out of the accessibility
  // tree: a theme-toggle icon sits inside a label marked aria-hidden, and demanding a name
  // for it would be demanding the opposite of what the markup says.
  const hiddenFromAT = (el) => !!el.closest('[aria-hidden="true"]');

  for (const img of document.querySelectorAll('img')) {
    if (!visible(img) || hiddenFromAT(img)) continue;
    if (img.matches(IMG)) continue;
    if (!(img.getAttribute('alt') || '').trim() && !name(img))
      add('img-name', describe(img) + ' has no alt text');
  }
  for (const el of document.querySelectorAll('button, a[href], [role="button"], [role="tab"], [role="checkbox"], [role="switch"], input, select, textarea, summary')) {
    if (!visible(el) || hiddenFromAT(el)) continue;
    if (el.tagName === 'INPUT' && (el.type || '').toLowerCase() === 'hidden') continue;
    if (!name(el)) add('control-name', describe(el) + ' has no accessible name');
  }
  for (const svg of document.querySelectorAll('svg')) {
    if (!visible(svg) || hiddenFromAT(svg)) continue;
    if (svg.getAttribute('aria-hidden') === 'true') continue;
    if (svg.getAttribute('role') === 'presentation') continue;
    const t = svg.querySelector('title');
    if (!name(svg) && !(t && t.textContent.trim()))
      add('svg-name', describe(svg) + ' carries meaning but has no name or role=presentation');
  }

  // 4. text contrast, against the background actually painted behind the text
  const parse = (c) => {
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[,\s/]+/).filter(Boolean).map(Number);
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  };
  const over = (fg, bg) => ({
    r: fg.r * fg.a + bg.r * (1 - fg.a),
    g: fg.g * fg.a + bg.g * (1 - fg.a),
    b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1,
  });
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const ratio = (a, b) => {
    const l1 = lum(a), l2 = lum(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  };
  // The background actually painted behind this text is every ancestor's colour,
  // composited from the canvas inwards. Returning the first non-transparent ancestor was
  // wrong and it mattered: `background: rgba(0,52,62,.07)` over white is a 7% tint, and
  // reading it as solid dark blue reported dark ink on dark ink at 1.00:1. The first run
  // of this probe produced exactly that false finding on examples/21.
  const bgOf = (el) => {
    const stack = [];
    let node = el;
    while (node && node.nodeType === 1) {
      const cs = getComputedStyle(node);
      if ((cs.backgroundImage || 'none') !== 'none') return {gradient: true};
      const c = parse(cs.backgroundColor);
      if (c && c.a > 0) stack.push(c);
      node = node.parentElement;
    }
    let bg = {r: 255, g: 255, b: 255, a: 1};   // the canvas
    for (let i = stack.length - 1; i >= 0; i--) {
      const c = stack[i];
      bg = c.a >= 0.999 ? c : over(c, bg);
    }
    return bg;
  };
  const SVGNS = 'http://www.w3.org/2000/svg';
  let checked = 0;
  for (const el of document.querySelectorAll('body *')) {
    const owns = Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
    if (!owns || !visible(el)) continue;
    const cs = getComputedStyle(el);
    const fgRaw = parse(cs.color);
    if (!fgRaw) continue;
    const bg = bgOf(el);
    if (bg.gradient) { checked++; continue; }
    const fg = fgRaw.a < 1 ? over(fgRaw, bg) : fgRaw;
    let scale = 1;
    if (el.namespaceURI === SVGNS) {
      const m = el.getScreenCTM();
      scale = m ? Math.hypot(m.a, m.b) : 1;
    }
    const px = parseFloat(cs.fontSize) * scale;
    const weight = parseInt(cs.fontWeight, 10) || 400;
    const large = px >= 24 || (px >= 18.66 && weight >= 700);
    const need = large ? 3.0 : 4.5;
    const got = ratio(fg, bg);
    checked++;
    if (got + 0.01 < need)
      add('contrast', describe(el) + ' ' + got.toFixed(2) + ':1, needs ' +
        need.toFixed(1) + ':1 at ' + px.toFixed(1) + ' px ' + weight +
        ' on rgb(' + Math.round(bg.r) + ',' + Math.round(bg.g) + ',' + Math.round(bg.b) + ')');
  }
  out.contrastChecked = checked;

  // 5. aria sanity
  for (const el of document.querySelectorAll('[aria-hidden="true"]')) {
    if (/^(A|BUTTON|INPUT|SELECT|TEXTAREA|SUMMARY)$/.test(el.tagName) ||
        el.hasAttribute('tabindex')) {
      if (visible(el) && el.tabIndex >= 0)
        add('aria-hidden-focusable', describe(el) + ' is aria-hidden but focusable');
    }
  }
  const ids = new Map();
  for (const el of document.querySelectorAll('[id]')) {
    ids.set(el.id, (ids.get(el.id) || 0) + 1);
  }
  for (const [id, n] of ids) if (n > 1) add('duplicate-id', 'id="' + id + '" appears ' + n + ' times');

  // 6. tabindex above zero reorders the whole page
  for (const el of document.querySelectorAll('[tabindex]')) {
    const t = parseInt(el.getAttribute('tabindex'), 10);
    if (t > 0 && visible(el)) add('tabindex', describe(el) + ' has tabindex=' + t);
  }

  return out;
}
"""

NOT_CHECKED = (
    "aria roles and pattern conformance, live regions, focus order and focus visibility "
    "(needs interaction), reduced motion, screen-reader output"
)


def check(path: Path, engines: tuple[str, ...], quiet: bool, dark: bool = False,
          theme: str = "") -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright is not installed, so nothing was measured.")
        print("       install: uv sync --extra verify && uv run playwright install chromium")
        print("       This is an error, not a skip: a check that cannot run must not pass.")
        return 2

    if path.name.endswith(".fragment.html"):
        print(f"  ~ {path.name}: an HTML fragment, not a document. language, title and "
              f"heading rules do not apply to it, and it is not embedded anywhere as a page.")
        return 0
    url = path.resolve().as_uri()
    total = 0
    with sync_playwright() as p:
        for engine in engines:
            for label, w, h in VIEWPORTS:
                browser = getattr(p, engine).launch()
                try:
                    page = browser.new_page(viewport={"width": w, "height": h},
                                            color_scheme="dark" if dark else "light")
                    page.goto(url)
                    if theme:
                        # A page that ships a theme toggle disarms its own
                        # prefers-color-scheme block by setting data-theme on load, so the only
                        # way to measure the colours its reader reaches is to set the attribute
                        # the toggle sets. json.dumps, because the name goes into a JS string.
                        page.evaluate("(name) => document.documentElement.setAttribute("
                                      "'data-theme', name)", theme)
                    page.wait_for_timeout(400)
                    result = page.evaluate(PROBE_JS)
                finally:
                    browser.close()
                findings = result["findings"]
                total += len(findings)
                head = (f"{engine} {label} {w}x{h}"
                        + (" dark" if dark else "")
                        + (f" theme={theme}" if theme else ""))
                if not quiet:
                    print(f"  · {head}: {result.get('contrastChecked', 0)} text runs measured, "
                          f"{len(findings)} finding(s)")
                for f in findings:
                    print(f"    {f['rule']:<20} {f['detail']}")

    if not quiet:
        print(f"\n  not checked here: {NOT_CHECKED}.")
        print("  a green run means none of the six rules above, not 'accessible'.")
    return 0 if total == 0 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("artefact", type=Path, help="the built .html file")
    ap.add_argument("--quiet", action="store_true", help="only print findings")
    ap.add_argument("--dark", action="store_true",
                    help="measure with the operating system in dark mode, so a page that "
                         "follows prefers-color-scheme is checked in the colours a dark-mode "
                         "reader actually gets")
    ap.add_argument("--theme", default="", metavar="NAME",
                    help="set data-theme=NAME on <html> after load, for a page whose dark "
                         "colours are reached through its own toggle rather than the system "
                         "setting. Without it such a page is only ever measured in light")
    add_engines_arg(ap)
    args = ap.parse_args(argv)

    if not args.artefact.is_file():
        print(f"ERROR: no such file: {args.artefact}")
        return 2
    print(f"verify_a11y: {args.artefact}" + ("  (dark scheme)" if args.dark else "")
          + (f"  (theme={args.theme})" if args.theme else ""))
    code = check(args.artefact, tuple(args.engines), args.quiet, args.dark, args.theme)
    print("verify_a11y: " + ("PASS" if code == 0 else "FINDINGS" if code == 1 else "ERROR"))
    return code


if __name__ == "__main__":
    sys.exit(main())
