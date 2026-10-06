#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
build_js_free_poc.py — generates js-free-standalone-poc.html

Proof of concept for JavaScript-free standalone HTML. Tests one
substitution rule against a real, renderable file instead of just describing
it in prose:

  1. Navigation (menu, page-switching, info panel, theme) is invisible-to-
     the-user-if-swapped, so it is rebuilt in plain HTML/CSS — the
     checkbox-hack + radio-group pattern — with ZERO JavaScript. This is not a
     fallback for when JS fails; it is the only implementation. There is no
     JS version of the menu anywhere in this file.
  2. The bar chart has a genuinely OK plain-HTML/CSS substitute (stacked
     divs sized by percentage width). So: JS draws a nicer canvas version
     WHEN JavaScript runs; the CSS version stays in the DOM and is only
     hidden once the JS version has actually rendered — never hidden
     speculatively.
  3. The scatter-plot-with-trend-line has NO honest plain-CSS substitute
     (computing a regression line and plotting arbitrary x/y pairs is not
     something CSS can do without JS). Where JS doesn't run, it says so
     directly — "Krever JavaScript som ikke er støttet i denne visningen."
     — instead of silently showing nothing or a fake/misleading chart.
  4. Fullscreen has no honest substitute of ANY kind (there is no CSS way to
     ask the browser to go fullscreen). The button stays `hidden` unless JS
     both runs AND confirms (by actually trying, not just feature-detecting
     — the lesson already learned in examples/07-topbar-pattern-demo/) that the
     browsing context actually grants it. No JS, or a rejected request: the
     button is never shown, not just disabled.

Does NOT touch any other example. This is a separate, standalone comparison
point for the JavaScript-driven examples, not a replacement for them.

No CDN, no framework, hand-built HTML/CSS/JS only (docs/00-vision.md
principle 1) — the JS that does exist here is hand-rolled canvas drawing,
not an embedded charting library, deliberately, in keeping with the "minimise
JavaScript" brief for this POC specifically.

    python3 build_js_free_poc.py

No dependencies beyond the standard library.
"""
from __future__ import annotations

import datetime
import pathlib

HERE = pathlib.Path(__file__).parent
OUT = HERE / "js-free-standalone-poc.html"
BUILD_DATE = datetime.date.today().isoformat()

# Assembled in three chunks (STYLE / BODY / SCRIPT) purely so no single
# Python string literal in this file gets unwieldy to edit — the shipped
# file concatenates them into one normal <html> document, in the usual
# head/body/script order.
STYLE = r"""
/* ---- tokens (values match plugins/eksempel/tokens/palette.css,
   theme-light.css, theme-dark.css — copied in as plain hex rather than
   read-and-inlined at build time, since this POC uses a different
   activation mechanism (checkbox-hack, not a JS-set [data-theme]
   attribute) and duplicating the small set of values used here is clearer
   than re-deriving a [data-theme] ruleset that would never match). ---- */
:root{
  --ink:#00141A; --muted:#5b6b70; --line:#ebebeb; --bg:#ffffff; --panel:#f8f8f8;
  --brand:#2F5D9E; --brand-dark:#1B2A4A; --focus:#ffbf47;
  --ok:#1F7A5C; --bad:#C9372C;
  --topbar-h:56px; /* single source of truth for header height — everything
    that needs to sit "below the header" (the wrapper below, the info
    panel, the nav menu's top padding) reads this variable instead of
    repeating 56px, so the mobile media query only has to change it once,
    here, and every dependent element follows. */
}
@media (max-width:480px){
  /* Mobile bug fix: the title ran into the fixed icon cluster on the
     right because the header stayed one line at a fixed 56px height no
     matter how little room the title text had. Below this width the
     title is allowed to wrap onto a second line, and the header grows to
     fit it — --topbar-h grows with it so nothing that positions itself
     "below the header" ends up hidden underneath it. */
  :root{ --topbar-h:74px; }
}
*{box-sizing:border-box}
/* App shell. docs/01-tenant-constraints.md row 26: position:sticky AND position:fixed
   both let the header overlap the content below it in SharePoint's inline preview. The
   shape that worked has no positioning property on the header at all — a non-scrolling
   100vh flex column with ONE scrolling container. body is position:relative so the
   body-level toggles below can be position:absolute instead of fixed; since body never
   scrolls, that is visually identical and keeps position:fixed out of the file. Gated by
   tools/verify_standalone_core.py, exercised by tools/verify_app_shell.py. */
html,body{height:100%;overflow:hidden}
body{margin:0;font-family:"Segoe UI",Arial,sans-serif;color:var(--ink);background:var(--bg);
  line-height:1.5;position:relative}
h1,h2,h3{line-height:1.25}
a{color:var(--brand)}
.visually-hidden{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);
  white-space:nowrap;border:0;padding:0;margin:-1px}

/* ---- "limited preview" notice: light red/pink box, visible by default in
   plain HTML/CSS (no JavaScript needed to show it — same rule the
   js-warning pattern in docs/11-responsiveness-and-browser-support.md §3b
   already establishes).
   Reused in three places: the global banner right under the header (hidden
   the moment ANY JavaScript proves it ran), and inside both chart blocks
   (hidden only once THAT specific chart's canvas has actually drawn
   successfully — not just because some other script ran, per the same
   "hide only after actual success" rule the chart fallbacks already
   follow). Colour is deliberately theme-INDEPENDENT (same light pink on
   both light and dark backgrounds) — a light warning chip on a dark page
   is the same deliberate, conventional pattern tools/tokens/theme-dark.css
   already documents for status colours. */
.preview-notice{background:#fbeded;border-left:4px solid var(--bad);color:#3d0d0d;
  padding:.7rem .9rem;border-radius:0 4px 4px 0;margin:0 0 1rem;font-size:.92rem}
.preview-notice strong{display:block;margin-bottom:.15rem}

/* ---- theme toggle: checkbox-hack, zero JavaScript ----
   #theme-toggle is a real, focusable <input type=checkbox> (not
   display:none) so Tab + Space operate it like any native control.
   Checked state re-points the CSS custom properties on #app-root — every
   colour on the page is read through a variable, nothing is hardcoded a
   second time for dark mode. */
#theme-toggle:checked ~ #app-root{
  --ink:#FFF8EE; --muted:#AEC3E3; --line:#2A3F5F; --bg:#1B2A4A; --panel:#101828;
  --brand:#2F5D9E; --brand-dark:#101828;
}
#app-root{background:var(--bg);color:var(--ink);position:relative;
  height:100vh;height:100dvh;display:flex;flex-direction:column;overflow:hidden}

/* ---- topbar: purely decorative row. The interactive controls are NOT
   inside it — see the "topbar toggles" block below for why. Left padding
   clears the hamburger toggle that sits on top of it (left:9px, width 38px)
   — without it, the logo (first flex child) renders directly underneath the
   hamburger and the two overlap. No position property: it is the first,
   non-shrinking row of #app-root's flex column (row 26). */
#topbar{flex:0 0 auto;height:var(--topbar-h);background:var(--brand-dark);
  color:#FFF8EE;display:flex;align-items:center;gap:.6rem;
  padding:0 145px 0 56px;z-index:10;transition:height .15s}
#topbar .logo{display:inline-flex;flex:none}
#topbar .logo svg{fill:currentColor}
#topbar .title{font-size:.95rem;font-weight:600;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;min-width:0}
.title-short{display:none}
/* Mobile: right padding above (145px) already permanently reserves room
   for the info+theme+fullscreen icon cluster on ALL screen sizes — the fix
   for "title text runs into the icons" was never conditional on screen
   width, a fixed header just never had that reservation at all. What DOES
   change below 480px is letting the title use that freed-up vertical room
   by wrapping instead of truncating with an ellipsis. */
@media (max-width:480px){
  /* Fullscreen is dropped entirely below this width, not just re-laid-out
     — rarely useful on a phone browser to begin with, and dropping its
     reserved slot is what makes room for the title to wrap onto two lines
     instead of four. This is a deliberate mobile scope reduction, not a
     bug: consistent with the "no honest substitute → hide it" rule this
     POC already applies to fullscreen everywhere else. */
  #fs-btn{display:none !important}
  #topbar{align-items:flex-start;padding-top:10px;padding-bottom:10px;
    padding-right:100px} /* only info+theme reserved now, not fullscreen's slot */
  #topbar .title{white-space:normal;overflow:visible;text-overflow:clip;
    line-height:1.3;font-size:.85rem}
  .title-full{display:none}
  .title-short{display:inline}
}

/* ---- topbar toggles: checkbox + adjacent <label>, positioned with
   `position:absolute` (against the non-scrolling <body>, which is why this
   is not position:fixed — row 26) to land visually inside the topbar row,
   even though in the DOM they sit BEFORE #app-root, as direct children of
   <body> — that
   placement is what lets `:checked ~ #nav-menu` etc. reach elements that
   are, in DOM terms, much later siblings (the CSS sibling combinator only
   works within one shared parent, so the checkbox cannot live nested
   inside <header> and still reach <nav> outside it).
   Payoff of this structure: the checkbox and its <label> ARE adjacent
   siblings, so `:hover`/`:focus-visible` + `label` gives a real,
   correctly-positioned hover/keyboard-focus indicator on the visible
   icon — the checkbox physically sits ON TOP of its own label (higher
   z-index, opacity:0, same size/position), which is also why the pointer
   is technically always hovering the checkbox, never the label
   underneath; styling `.toggle-label:hover` directly therefore never
   fires and had to be replaced with the sibling form below. */
.toggle{position:absolute;top:9px;width:38px;height:38px;opacity:0;z-index:12;cursor:pointer;margin:0}
.toggle-label{position:absolute;top:9px;width:38px;height:38px;z-index:11;display:flex;
  align-items:center;justify-content:center;border-radius:4px;cursor:pointer;color:#FFF8EE}
#menu-toggle,#menu-toggle-label{left:9px}
#info-toggle,#info-toggle-label{right:9px}
#theme-toggle,#theme-toggle-label{right:53px}
#fs-btn{position:absolute;top:9px;right:97px;width:38px;height:38px;z-index:11;
  display:flex;align-items:center;justify-content:center;border-radius:4px;
  background:transparent;border:0;color:#FFF8EE;cursor:pointer}
#fs-btn:hover{background:rgba(255,255,255,.12)}
#menu-toggle:hover + label,#menu-toggle:focus-visible + label,
#info-toggle:hover + label,#info-toggle:focus-visible + label,
#theme-toggle:hover + label,#theme-toggle:focus-visible + label{background:rgba(255,255,255,.12)}
#menu-toggle:focus-visible + label,
#info-toggle:focus-visible + label,
#theme-toggle:focus-visible + label,
#fs-btn:focus-visible{outline:3px solid var(--focus);outline-offset:1px}
/* Sun/moon: both icon spans must centre identically inside .toggle-label,
   otherwise swapping which one is display:none shifts the visible one —
   this was the "moon sits lower than the others" bug. */
.theme-icon-light,.theme-icon-dark{display:inline-flex;align-items:center;justify-content:center;
  width:18px;height:18px}
.theme-icon-dark{display:none}
/* Bug fixed: these two spans live inside #theme-toggle-label, which is a
   SIBLING of #app-root (both are direct children of <body>), not a
   descendant of it — the original selector scoped to "~ #app-root ..."
   could never match anything here. Target the label sibling directly. */
#theme-toggle:checked ~ #theme-toggle-label .theme-icon-light{display:none}
#theme-toggle:checked ~ #theme-toggle-label .theme-icon-dark{display:inline-flex}


/* ---- overlay + panels: same checkbox-hack. Two separate overlay <label>s
   (one per togglable checkbox) rather than one shared overlay, because a
   single <label for="..."> can only close ONE specific checkbox — there is
   no pure-CSS way to say "close whichever panel happens to be open".
   Known, accepted simplification: opening the menu does not auto-close an
   already-open info panel (see README, "known limitations"). ---- */
.overlay{position:absolute;inset:0;background:rgba(0,0,0,.35);opacity:0;pointer-events:none;
  transition:opacity .15s;z-index:8}
#menu-toggle:checked ~ #app-root #overlay-menu,
#info-toggle:checked ~ #app-root #overlay-info{opacity:1;pointer-events:auto}

#nav-menu{position:absolute;top:0;left:0;bottom:0;width:min(280px,86vw);background:var(--panel);
  color:var(--ink);transform:translateX(-100%);transition:transform .18s;z-index:9;
  padding:calc(var(--topbar-h) + 8px) 16px 16px;overflow-y:auto}
#menu-toggle:checked ~ #app-root #nav-menu{transform:translateX(0)}
#info-panel{position:absolute;top:var(--topbar-h);right:9px;width:min(320px,88vw);background:var(--panel);
  color:var(--ink);transform:translateY(-12px) scale(.98);opacity:0;pointer-events:none;
  transition:transform .15s,opacity .15s;z-index:9;padding:16px;border-radius:6px;
  box-shadow:0 8px 24px rgba(0,0,0,.25)}
#info-toggle:checked ~ #app-root #info-panel{transform:translateY(0) scale(1);opacity:1;
  pointer-events:auto}
.panel-close{display:inline-block;margin-bottom:.75rem;font-size:.9rem;cursor:pointer;
  color:var(--brand)}
.navlink{display:block;padding:.6rem .3rem;color:var(--ink);text-decoration:none;
  border-radius:4px;font-size:1rem;cursor:pointer}
.navlink:hover,.navlink:focus-visible{background:rgba(0,108,108,.12)}
.navlink:focus-visible{outline:3px solid var(--focus);outline-offset:-2px}

/* ---- content wrapper: the ONE scrolling container in the document, and the
   only flexible row of #app-root's column. It used to carry
   padding-top:var(--topbar-h) to clear a fixed header; with the row-26 shell
   the header is a flex sibling that cannot cover anything, so the
   compensation is gone rather than adjusted. min-height:0 is required — a
   flex item's default min-height:auto refuses to shrink below its content and
   the overflow would move to the page instead. */
#below-header{flex:1 1 auto;min-height:0;overflow-y:auto;-webkit-overflow-scrolling:touch}

/* ---- pages: a real radio group, NOT CSS :target ----
   An earlier revision used CSS `:target`. docs/01-tenant-constraints.md row 24:
   fragment navigation does not happen at all in SharePoint's inline preview,
   even though JavaScript runs there (row 25) — so `<a href="#page-x">` never
   makes #page-x the :target, the page never switches, and nothing reports an
   error. It works perfectly from file://, which is why the local headless
   verifier passed it for weeks.

   A radio group needs no fragment navigation: checking an input is not
   navigation, and it is the same mechanism as the menu/theme/info checkboxes
   already proven in this file. The radios sit before #app-root as direct
   children of <body> for the same sibling-combinator reason the toggles do.
   #page-home carries `checked`, so the default page comes from HTML state
   rather than from the absence of a fragment — and it no longer has to be
   last in the DOM.

   Bonus the :target version could not give: a visible current-page
   indicator, which docs/09 §5 (Nielsen Norman Group) asks for. Signalled by
   weight AND background, not colour alone (WCAG 2.2 1.4.1). */
main{padding:0 16px 40px;max-width:860px;margin:0 auto}

/* Off-canvas but still focusable and arrow-key navigable as a native radio
   group — deliberately not display:none, same reasoning as #theme-toggle. */
.page-radio{position:absolute;top:-200px;left:9px;width:1px;height:1px;opacity:0;margin:0}

.page{display:none}
#nav-home:checked ~ #app-root #page-home,
#nav-charts:checked ~ #app-root #page-charts,
#nav-principles:checked ~ #app-root #page-principles{display:block}

#nav-home:checked ~ #app-root .navlink[for="nav-home"],
#nav-charts:checked ~ #app-root .navlink[for="nav-charts"],
#nav-principles:checked ~ #app-root .navlink[for="nav-principles"]{
  background:rgba(0,108,108,.12);font-weight:600}

/* The radios are off-canvas, so their focus ring has to be forwarded to the
   visible label or keyboard users get no indicator at all. */
#nav-home:focus-visible ~ #app-root .navlink[for="nav-home"],
#nav-charts:focus-visible ~ #app-root .navlink[for="nav-charts"],
#nav-principles:focus-visible ~ #app-root .navlink[for="nav-principles"]{
  outline:3px solid var(--focus);outline-offset:-2px}

/* ---- bar chart: CSS version is the real, always-present substitute ---- */
.bar-row{display:flex;align-items:center;gap:.6rem;margin:.35rem 0}
.bar-row .label{width:110px;font-size:.85rem;color:var(--muted);flex:none}
.bar-track{flex:1;background:var(--line);border-radius:3px;height:22px;overflow:hidden}
.bar-fill{height:100%;background:var(--brand);border-radius:3px 0 0 3px}
.bar-row .value{width:44px;text-align:right;font-size:.85rem;font-variant-numeric:tabular-nums}
canvas{max-width:100%}
.chart-block{margin:1.5rem 0;padding:1rem;background:var(--panel);border-radius:6px}

.callout{background:var(--panel);border-left:4px solid var(--brand);padding:.9rem 1rem;
  margin:1rem 0;border-radius:0 6px 6px 0}
table{border-collapse:collapse;width:100%;margin:1rem 0}
th,td{text-align:left;padding:.5rem .6rem;border-bottom:1px solid var(--line);font-size:.92rem}
th{color:var(--muted);font-weight:600}
code{background:var(--panel);padding:.1rem .3rem;border-radius:3px;font-size:.9em}

@media print{ #topbar,.toggle,.toggle-label,.page-radio,#fs-btn,#nav-menu,#info-panel,.overlay{display:none} }
"""

BODY = r"""
<input type="checkbox" id="menu-toggle" class="toggle" aria-label="Åpne meny">
<label for="menu-toggle" id="menu-toggle-label" class="toggle-label" aria-hidden="true">
  <svg width="18" height="18" viewBox="0 0 16 16" fill="none"><path stroke="currentColor"
    stroke-linecap="round" stroke-width="1.5" d="M1 14h14M1 8h14M1 2h14"/></svg>
</label>

<input type="checkbox" id="theme-toggle" class="toggle" aria-label="Bytt lys/mørk tema">
<label for="theme-toggle" id="theme-toggle-label" class="toggle-label" aria-hidden="true">
  <span class="theme-icon-light"><svg width="18" height="18" viewBox="0 0 16 16" fill="none">
    <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.4"
    d="M14 9.1A6.2 6.2 0 1 1 6.9 2 5 5 0 0 0 14 9.1Z"/></svg></span>
  <span class="theme-icon-dark"><svg width="18" height="18" viewBox="0 0 16 16" fill="none">
    <circle cx="8" cy="8" r="3.2" stroke="currentColor" stroke-width="1.4"/><path stroke="currentColor"
    stroke-linecap="round" stroke-width="1.4" d="M8 .8v2M8 13.2v2M2.6 2.6l1.4 1.4M12 12l1.4 1.4M.8 8h2M13.2 8h2M2.6 13.4 4 12M12 4l1.4-1.4"/></svg></span>
</label>

<input type="checkbox" id="info-toggle" class="toggle" aria-label="Om denne POC-en">
<label for="info-toggle" id="info-toggle-label" class="toggle-label" aria-hidden="true">
  <svg width="18" height="18" viewBox="0 0 17 17" fill="none"><path stroke="currentColor"
  stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
  d="M10.04 11.581h-.513c-.567 0-1.027-.46-1.027-1.027V7.986a.514.514 0 0 0-.514-.513h-.513m.674-2.487h.024M16.203 8.5a7.703 7.703 0 1 1-15.406 0 7.703 7.703 0 0 1 15.406 0Z"/></svg>
</label>

<!-- Fullscreen: no checkbox, no CSS-only substitute exists for it at all
     (there is no declarative HTML/CSS way to request fullscreen). Starts
     `hidden` and ONLY becomes visible if JavaScript both runs and confirms,
     by actually trying, that this browsing context grants it — see
     SCRIPT. No JS at all: this stays hidden forever, which is the correct
     behaviour by design, not a bug. -->
<button id="fs-btn" type="button" hidden aria-pressed="false" title="Fullskjerm">
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path stroke="currentColor"
  stroke-linecap="round" stroke-linejoin="round" stroke-miterlimit="10" stroke-width="1.5"
  d="m1 15 4.978-4.978M1 11.89V15h3.111m5.911-9.022L15 1m-3.111 0H15v3.111M1 1l4.978 4.978M4.11 1H1v3.111m9.022 5.911L15 15m0-3.111V15h-3.111"/></svg>
</button>

<!-- Page selection. NOT <a href="#page-x"> + CSS :target — that is measured
     broken in SharePoint's inline file-preview (docs/01-tenant-constraints.md
     row 24), silently, while working perfectly from file://. A radio group
     involves no fragment navigation at all. #nav-home is `checked` so the
     landing page is explicit HTML state. -->
<input type="radio" name="page" id="nav-home" class="page-radio" checked aria-label="Hjem">
<input type="radio" name="page" id="nav-charts" class="page-radio" aria-label="Grafer: JS-forbedret vs. JS-avhengig">
<input type="radio" name="page" id="nav-principles" class="page-radio" aria-label="Prinsippene for JavaScript-fri standalone HTML">

<div id="app-root">

<div class="overlay" id="overlay-menu"></div>
<label class="overlay" id="overlay-info" for="info-toggle" aria-hidden="true"></label>

<header id="topbar">
  <span class="logo"><svg width="30" height="21" viewBox="0 0 116 80" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Plassholdermerke (nøytralt)">
    <rect x="6" y="44" width="24" height="30" rx="4" fill="currentColor"/>
    <rect x="40" y="26" width="24" height="48" rx="4" fill="currentColor"/>
    <rect x="74" y="8" width="24" height="66" rx="4" fill="currentColor"/>
  </svg></span>
  <span class="title">
    <span class="title-full">Javascript-løs standalone HTML — POC</span>
    <span class="title-short">JS-løs standalone HTML — POC</span>
  </span>
</header>

<nav id="nav-menu" aria-label="Sidenavigasjon">
  <label for="menu-toggle" class="panel-close">✕ Lukk</label>
  <label class="navlink" for="nav-home">Hjem</label>
  <label class="navlink" for="nav-charts">Grafer: JS-forbedret vs. JS-avhengig</label>
  <label class="navlink" for="nav-principles">Prinsippene for JavaScript-fri standalone HTML</label>
</nav>

<div id="info-panel">
  <label for="info-toggle" class="panel-close">✕ Lukk</label>
  <h3 style="margin-top:0">Om denne siden</h3>
  <p>Bevis-av-konsept for JavaScript-fri standalone HTML.
  Meny, sideskift og dette panelet bruker ingen JavaScript i det hele tatt —
  prøv å skru av JavaScript i nettleseren og se at ingenting endrer seg her.</p>
</div>

<div id="below-header">

<!-- Global "limited preview" notice: visible by default in plain HTML,
     needs no JavaScript to show — the earliest possible inline <script>,
     placed immediately after it, is what hides it, and only its OWN
     successful execution proves "some JavaScript ran" (same Layer-B
     reasoning documented in docs/11-responsiveness-and-browser-support.md
     §3b: a script being
     BLOCKED, e.g. by a sandboxed in-app viewer, is not the same thing as
     scripting being formally off, so <noscript> cannot do this job). This
     is deliberately a DIFFERENT, more general signal than the two
     chart-specific notices below — this one only means "did anything at
     all run", not "did this particular feature succeed". -->
<div id="preview-notice-global" class="preview-notice" role="status">
  <strong>Begrenset forhåndsvisning</strong>– bør åpnes i nettleser.
</div>
<script>document.getElementById('preview-notice-global').style.display = 'none';</script>

<main>

<section id="page-charts" class="page">
  <h2>Grafer: tre ulike svar på "hva om JavaScript ikke kjører"</h2>

  <div class="chart-block">
    <h3>1. Stolpediagram — god HTML/CSS-erstatning finnes</h3>
    <p>CSS-versjonen under er alltid i DOM-en og alltid korrekt. Kjører
    JavaScript, tegnes en finere canvas-versjon over den — men CSS-versjonen
    er aldri gjettet bort før JS beviselig har lyktes.</p>
    <div id="bar-chart-notice" class="preview-notice" role="status">
      <strong>Begrenset forhåndsvisning</strong>– bør åpnes i nettleser.
    </div>
    <div id="bar-chart-css">
      <div class="bar-row"><span class="label">Nord</span><div class="bar-track"><div class="bar-fill" style="width:42%"></div></div><span class="value">42</span></div>
      <div class="bar-row"><span class="label">Sør</span><div class="bar-track"><div class="bar-fill" style="width:78%"></div></div><span class="value">78</span></div>
      <div class="bar-row"><span class="label">Øst</span><div class="bar-track"><div class="bar-fill" style="width:55%"></div></div><span class="value">55</span></div>
      <div class="bar-row"><span class="label">Vest</span><div class="bar-track"><div class="bar-fill" style="width:90%"></div></div><span class="value">90</span></div>
      <div class="bar-row"><span class="label">Midt</span><div class="bar-track"><div class="bar-fill" style="width:33%"></div></div><span class="value">33</span></div>
      <div class="bar-row"><span class="label">Innlandet</span><div class="bar-track"><div class="bar-fill" style="width:61%"></div></div><span class="value">61</span></div>
    </div>
    <canvas id="bar-chart-canvas" width="600" height="220" hidden></canvas>
  </div>

  <div class="chart-block">
    <h3>2. Spredningsdiagram med trendlinje — ingen fullgod HTML/CSS-erstatning finnes</h3>
    <p>Å plassere vilkårlige punkt og beregne en regresjonslinje er ikke noe
    CSS kan gjøre uten JavaScript. Her forsøker vi ikke et falskt/misvisende
    forsøk — vi sier rett ut at det kreves JavaScript.</p>
    <div id="scatter-fallback" class="preview-notice" role="status">
      <strong>Begrenset forhåndsvisning</strong>– bør åpnes i nettleser.
      Krever JavaScript som ikke er støttet i denne visningen.
    </div>
    <canvas id="scatter-canvas" width="600" height="260" hidden></canvas>
  </div>


  <div class="chart-block">
    <h3>3. Fullskjerm — ingen erstatning, skjules i stedet</h3>
    <p>Fullskjerm-knappen øverst til høyre finnes kun i DOM-en som
    <code>hidden</code>. Uten JavaScript vises den aldri. Med JavaScript
    vises den bare hvis <code>requestFullscreen()</code> faktisk lykkes når
    den prøves — ikke bare fordi funksjonen finnes (se
    <code>examples/07-topbar-pattern-demo/</code> for hvorfor det skillet
    finnes).</p>
  </div>
</section>

<section id="page-principles" class="page">
  <h2>Prinsippene for JavaScript-fri standalone HTML</h2>
  <div class="callout">Dette er et separat sammenligningspunkt for de
  JavaScript-drevne eksemplene, ikke en erstatning for dem.</div>
  <table>
    <tr><th>Situasjon</th><th>Regel</th></tr>
    <tr><td>Usynlig for brukeren om det byttes (navigasjon, paneler, tema)</td>
        <td>Erstattes helt — null JavaScript, ren HTML/CSS</td></tr>
    <tr><td>God HTML/CSS-erstatning finnes (stolpediagram)</td>
        <td>JavaScript brukes når det støttes; ellers vises HTML/CSS-versjonen</td></tr>
    <tr><td>Ingen god erstatning finnes, men innhold forventes (spredningsdiagram)</td>
        <td>Vis tydelig melding: "Krever JavaScript som ikke er støttet i denne visningen."</td></tr>
    <tr><td>Ingen erstatning finnes, og funksjonen er en ren bonus (fullskjerm)</td>
        <td>Skjules helt for brukeren i stedet for å vises død/inaktiv</td></tr>
  </table>
</section>

<section id="page-home" class="page">
  <h2>Javascript-løs standalone HTML</h2>
  <p>Denne siden beviser mønsteret for JavaScript-fri standalone HTML:
  meny, sideskift, info-panel og tema-bryter over krever ingen JavaScript i
  det hele tatt. De er bygget med <code>&lt;input type="checkbox"&gt;</code> +
  <code>:checked</code> på avkrysningsbokser og radioknapper — ikke som en reserveløsning
  for når JavaScript feiler, men som eneste implementasjon.</p>
  <p>Gå til <a class="navlink" style="display:inline" href="#page-charts">grafer-siden</a>
  for de tre resterende svarene: JS-forbedret-med-CSS-fallback, JS-eneste-med-tydelig-melding,
  og skjult-uten-erstatning.</p>
</section>

</main>
</div><!-- /#below-header -->
</div><!-- /#app-root -->

"""
SCRIPT = r"""
(function () {
  "use strict";

  /* ---- 1. Bar chart: enhance only if canvas 2D context is actually
     available. The CSS version is never hidden speculatively — only after
     the canvas version has successfully drawn. */
  (function enhanceBarChart() {
    var canvas = document.getElementById('bar-chart-canvas');
    var cssVersion = document.getElementById('bar-chart-css');
    var notice = document.getElementById('bar-chart-notice');
    if (!canvas || !canvas.getContext) return;
    var ctx = canvas.getContext('2d');
    if (!ctx) return;

    var data = [
      ['Nord', 42], ['Sør', 78], ['Øst', 55],
      ['Vest', 90], ['Midt', 33], ['Innlandet', 61]
    ];
    var w = canvas.width, h = canvas.height;
    var padLeft = 90, padRight = 40, padTop = 10, padBottom = 10;
    var rowH = (h - padTop - padBottom) / data.length;
    var maxVal = Math.max.apply(null, data.map(function (d) { return d[1]; }));
    var brand = getComputedStyle(document.getElementById('app-root'))
      .getPropertyValue('--brand').trim() || '#2F5D9E';
    var ink = getComputedStyle(document.getElementById('app-root'))
      .getPropertyValue('--ink').trim() || '#00141A';
    var line = getComputedStyle(document.getElementById('app-root'))
      .getPropertyValue('--line').trim() || '#ebebeb';

    ctx.clearRect(0, 0, w, h);
    ctx.font = '13px "Segoe UI",Arial,sans-serif';

    ctx.textBaseline = 'middle';
    var trackW = w - padLeft - padRight;

    data.forEach(function (row, i) {
      var y = padTop + i * rowH + rowH / 2;
      var barH = rowH * 0.55;
      var barW = (row[1] / maxVal) * trackW;

      ctx.fillStyle = ink;
      ctx.textAlign = 'right';
      ctx.fillText(row[0], padLeft - 10, y);

      ctx.fillStyle = line;
      ctx.fillRect(padLeft, y - barH / 2, trackW, barH);

      ctx.fillStyle = brand;
      ctx.fillRect(padLeft, y - barH / 2, barW, barH);

      ctx.fillStyle = ink;
      ctx.textAlign = 'left';
      ctx.fillText(String(row[1]), padLeft + barW + 8, y);
    });

    /* Only now, after a successful draw, hide the CSS version. */
    canvas.hidden = false;
    if (cssVersion) cssVersion.hidden = true;
    if (notice) notice.hidden = true;

    /* Redraw on theme toggle so canvas colours track the CSS variables
       (the checkbox-hack theme switch is pure CSS and fires no event we
       can listen to directly — 'change' on the checkbox itself works
       fine, since it is a real <input>, not a JS re-implementation of the
       toggle). */
    var themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) themeToggle.addEventListener('change', enhanceBarChart);
  })();

  /* ---- 2. Scatter plot + trend line: JS-only, no CSS fallback attempted.
     Deliberately a chart type CSS genuinely cannot approximate — arbitrary
     point placement plus a computed regression line. */
  (function enhanceScatter() {
    var canvas = document.getElementById('scatter-canvas');
    var fallback = document.getElementById('scatter-fallback');
    if (!canvas || !canvas.getContext) return;
    var ctx = canvas.getContext('2d');
    if (!ctx) return;

    var points = [
      [2, 14], [5, 22], [7, 19], [9, 31], [12, 28], [14, 40],
      [16, 35], [19, 47], [21, 44], [24, 55], [26, 50], [29, 61]
    ];
    var w = canvas.width, h = canvas.height, pad = 36;
    var xs = points.map(function (p) { return p[0]; });
    var ys = points.map(function (p) { return p[1]; });
    var xMax = Math.max.apply(null, xs), yMax = Math.max.apply(null, ys);

    function px(x) { return pad + (x / xMax) * (w - pad * 2); }
    function py(y) { return h - pad - (y / yMax) * (h - pad * 2); }

    /* Ordinary least squares — the actual reason this needs JS: this is a
       real computation, not just "draw dots at fixed positions". */
    var n = points.length;
    var sumX = xs.reduce(function (a, b) { return a + b; }, 0);
    var sumY = ys.reduce(function (a, b) { return a + b; }, 0);
    var sumXY = points.reduce(function (a, p) { return a + p[0] * p[1]; }, 0);
    var sumXX = xs.reduce(function (a, x) { return a + x * x; }, 0);
    var slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
    var intercept = (sumY - slope * sumX) / n;

    var brand = getComputedStyle(document.getElementById('app-root'))
      .getPropertyValue('--brand').trim() || '#2F5D9E';
    var ink = getComputedStyle(document.getElementById('app-root'))
      .getPropertyValue('--ink').trim() || '#00141A';
    var muted = getComputedStyle(document.getElementById('app-root'))
      .getPropertyValue('--muted').trim() || '#5b6b70';

    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = muted;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad, pad); ctx.lineTo(pad, h - pad); ctx.lineTo(w - pad, h - pad);
    ctx.stroke();

    ctx.strokeStyle = ink;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(px(0), py(intercept));
    ctx.lineTo(px(xMax), py(intercept + slope * xMax));
    ctx.stroke();

    ctx.fillStyle = brand;
    points.forEach(function (p) {
      ctx.beginPath();
      ctx.arc(px(p[0]), py(p[1]), 4.5, 0, Math.PI * 2);
      ctx.fill();
    });

    canvas.hidden = false;
    if (fallback) fallback.hidden = true;
  })();

  /* ---- 3. Fullscreen: hidden unless JS runs AND an actual request
     succeeds. Feature-detection alone ("does the function exist") is not
     enough — examples/07-topbar-pattern-demo/ already found a real case
     where the function exists but a sandboxed viewer
     silently rejects it. Reacting only to an actual rejection, and hiding
     — not just disabling — is the same lesson applied one step further. */
  (function enableFullscreenIfItActuallyWorks() {
    var btn = document.getElementById('fs-btn');
    if (!btn || !document.documentElement.requestFullscreen) return;
    btn.hidden = false;
    btn.addEventListener('click', function () {
      if (document.fullscreenElement) {
        document.exitFullscreen().catch(function () {});
        return;
      }
      document.documentElement.requestFullscreen().catch(function () {
        btn.hidden = true; /* rejected in this context — hide, don't just disable */
      });
    });
    document.addEventListener('fullscreenchange', function () {
      btn.setAttribute('aria-pressed', document.fullscreenElement ? 'true' : 'false');
    });
  })();

  /* ---- 4. Menu auto-close on page selection: OPTIONAL enhancement, not
     required for navigation to work. A <label> can only ever operate the ONE
     control it points at, so there is no zero-JS way to both select a page and
     close the menu in a single tap — a nested interactive element's own
     default action suppresses the outer label's "activate my control"
     behaviour in every engine (tested in an earlier revision, when the nav items
     were still <a href="#page-x">). Without JavaScript the menu still fully
     works: the reader closes it with the visible "✕ Lukk" button or the
     hamburger icon, one extra tap. With JavaScript, this closes it for them.
     Core navigation does not depend on this running.

     Bound to the page radios' change event, not to the labels' click, since
     the <a href="#page-x"> nav items were replaced with <label for="nav-x">
     driving a radio group (row 24: fragment navigation does not happen in
     SharePoint's inline preview). `change` on the radio is the real signal —
     it fires for a label click, a direct click on the radio, and keyboard
     arrow-key selection alike, which a click listener on the labels would
     miss for the last of those. */
  (function autoCloseMenuOnNavigate() {
    var menuToggle = document.getElementById('menu-toggle');
    var radios = document.querySelectorAll('input.page-radio[name="page"]');
    if (!menuToggle || !radios.length) return;
    radios.forEach(function (r) {
      r.addEventListener('change', function () {
        if (r.checked) menuToggle.checked = false;
      });
    });
  })();
})();

"""

PLACEHOLDER_STYLE = "/*__STYLE__*/"
PLACEHOLDER_BODY = "<!--__BODY__-->"
PLACEHOLDER_SCRIPT = "//__SCRIPT__"

DOC = """<!doctype html>
<!--
  Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
  This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
  or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
  COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
  under terms of your choice, provided the Origin Notice is preserved.
  SPDX-License-Identifier: AGPL-3.0-or-later
-->
<!--
  PROVENANCE
    Source data : none, synthetic demonstration
    Repo        : tun
    Made with   : Tún — tun.community
    Generator   : examples/13-js-free-standalone-poc/build_js_free_poc.py
-->
<html lang="nb">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JavaScript-løs standalone HTML — POC</title>
<style>
""" + PLACEHOLDER_STYLE + """
</style>
</head>
<body>
""" + PLACEHOLDER_BODY + """
<script>
""" + PLACEHOLDER_SCRIPT + """
</script>
</body>
</html>
"""


def main() -> None:
    doc = DOC.replace(PLACEHOLDER_STYLE, STYLE).replace(PLACEHOLDER_BODY, BODY).replace(
        PLACEHOLDER_SCRIPT, SCRIPT
    )
    OUT.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
