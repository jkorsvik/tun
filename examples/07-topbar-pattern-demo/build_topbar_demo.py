#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
build_topbar_demo.py — generates topbar-pattern-demo.html

A generated (never hand-written), self-contained HTML file that proves the
neutral topbar interaction pattern (docs/09-usability-and-navigation-principles.md) —

  1. non-scrolling topbar (app shell, NOT position:fixed — see row 26 note below)
  2. hamburger -> overlay + drop-down menu (not a sidebar)
  3. info button (ℹ️) -> overlay + info panel
  4. fullscreen button (⛶) -> requestFullscreen()/exitFullscreen()

Deliberately neutral: no Eksempel AS brand colours, no logo, no "Internt dokument"
pill. Brand styling is out of scope for this demo on purpose. The palette below is greyscale plus one generic slate accent,
chosen only to make focus/hover states visible, not to imply any brand.

This file exists to be sent as a real Teams message/link to a phone, so
the mobile-open hypotheses (does it work when opened from Teams on a phone?) can be tested against
reality instead of staying theoretical. It is not a dashboard: no rows, no
data, no filters — same reasoning as examples/04-generic-standalone-demo/,
kept deliberately free of dashboard vocabulary so the interaction pattern can
be judged on its own.

    python3 build_topbar_demo.py

No dependencies beyond the standard library.
"""
from __future__ import annotations

import datetime
import pathlib

OUT = pathlib.Path(__file__).parent / "topbar-pattern-demo.html"
BUILT = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

SECTIONS = [
    ("home", "Hjem",
     "Dette er standardsiden. Naviger med hamburgermenyen øverst til venstre "
     "— ikke en fast sidebar. Innholdet byttes med JavaScript (display:none / "
     "display:block) i samme fil, ingen separate HTML-sider."),
    ("section-b", "Side B",
     "En annen seksjon, kun for å vise at menyen faktisk bytter innhold og "
     "markerer hvilken side som er aktiv — kravet fra docs/09 §5 "
     "(Nielsen Norman Group: synlig nåværende-side-indikator)."),
    ("section-c", "Side C",
     "Tredje seksjon. Skroll ned på denne for å se at toppfeltet ligger fast "
     "i stedet for å rulle bort med resten av siden. Merk at det IKKE er "
     "position:fixed som gjør det — se docs/01-tenant-constraints.md rad 26."),
]

nav_items = "\n".join(
    f'      <button class="navbtn" data-target="{sid}" role="menuitem">{title}</button>'
    for sid, title, _ in SECTIONS
)
# Never rely on tap-outside alone on mobile: on a narrow viewport the panel
# itself can cover most of the "outside" area, shrinking the tap-to-close
# target to a thin strip -- found by verify_topbar_demo.py against a 390px
# viewport, not assumed up front. Every overlay panel gets an explicit close
# button as the primary affordance; click-outside stays as a secondary one.
CLOSE_BTN = '<button class="close-btn" onclick="closeAll()" aria-label="Lukk">✕ Lukk</button>'
sections_html = "\n".join(
    f'  <section id="{sid}" class="page" style="display:{"block" if i == 0 else "none"}">\n'
    f'    <h2>{title}</h2>\n    <p>{body}</p>\n'
    f'    <p style="color:var(--muted);font-size:.85rem">'
    f'Fyll-innhold for å teste scroll mot fast toppfelt.<br>' + ("Lorem ipsum. " * 40) + '</p>\n'
    f'  </section>'
    for i, (sid, title, body) in enumerate(SECTIONS)
)

HTML = f"""<!DOCTYPE html>
<!--
  Copyright (C) 2026 The Tún authors (see AUTHORS.md)
  This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
  or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
  COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
  under terms of your choice, provided the Origin Notice is preserved.
  SPDX-License-Identifier: AGPL-3.0-or-later
-->
<html lang="nb">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Topbar-mønster — demo</title>
<!--
  ============================================================================
  Topbar-mønster — demo (nøytral, ingen Eksempel AS-branding)
  ----------------------------------------------------------------------------
  PROVENANCE
    Source data : none — this is an interaction-pattern demo, not a report
    Built       : {BUILT}
    Requested by: the product owner
    Built by    : RAIWork, as the topbar pattern demo
    Repo        : tun
    Made with   : Tún — tun.community
    Generator   : examples/07-topbar-pattern-demo/build_topbar_demo.py
  ----------------------------------------------------------------------------
  Proves the topbar pattern (fixed topbar, hamburger->overlay menu,
  info panel, fullscreen toggle). The mobile/Teams open-path risk is
  NOT provable by this file alone -- it needs a human to open this exact file
  from a real Teams message on a real phone. That is the reason this demo
  exists as a shareable single file rather than only a description.
  ============================================================================
-->
<style>
  :root{{
    --ink:#262626; --muted:#666; --line:#e0e0e0; --bg:#fff; --panel:#f7f7f7;
    --accent:#3b4a5a; --accent-dark:#232c36; --sp-1:.5rem; --sp-2:1rem; --sp-3:1.5rem; --sp-4:2rem;
  }}
  *{{box-sizing:border-box}}
  /* App shell, not a pinned header. docs/01-tenant-constraints.md row 26: both
     position:sticky and position:fixed let the header overlap the content below it in
     SharePoint's inline preview. What worked is this — a non-scrolling 100vh flex
     column, a header with no positioning property at all, and ONE scrolling container.
     overflow:hidden on html as well as body, because the absolutely-positioned overlays
     still add to body's scrollHeight while hidden and would otherwise give the document
     its own scrollbar on a short viewport. Gated by tools/verify_standalone_core.py and
     exercised by tools/verify_app_shell.py. */
  html,body{{height:100%;overflow:hidden}}
  body{{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--ink);background:var(--bg);
    display:flex;flex-direction:column;height:100vh;height:100dvh;position:relative}}
  /* The sole scrolling container. */
  #scroll-area{{flex:1 1 auto;overflow-y:auto;-webkit-overflow-scrolling:touch}}

  #topbar{{
    flex:0 0 auto; height:56px; z-index:200;
    background:var(--accent-dark); color:#fff; display:flex; align-items:center;
    gap:var(--sp-2); padding:0 var(--sp-3);
  }}
  #topbar .title{{font-size:1rem;font-weight:600;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
  .icon-btn{{
    background:transparent;border:none;color:#fff;font-size:1.25rem;line-height:1;
    padding:.4rem .6rem;border-radius:.25rem;cursor:pointer;touch-action:manipulation;
  }}
  .icon-btn:hover, .icon-btn:focus-visible{{background:rgba(255,255,255,.15)}}

  /* No topbar compensation needed any more: the header is a flex sibling, not an
     overlay, so it cannot cover anything. The earlier "set padding-top in
     EVERY breakpoint" rule existed only to work around the fixed header and is now moot. */
  main{{padding:var(--sp-3) var(--sp-4) var(--sp-4);max-width:48rem;margin:0 auto}}
  @media (max-width:600px){{
    main{{padding-top:var(--sp-2);padding-left:var(--sp-2);padding-right:var(--sp-2)}}
  }}

  .page h2{{font-weight:600;margin-top:0}}
  .page p{{color:var(--ink);line-height:1.6}}

  /* shared overlay behind the menu AND the info panel */
  #overlay{{
    position:absolute; inset:0; background:rgba(0,0,0,.35); z-index:150;
    opacity:0; visibility:hidden; transition:opacity .15s;
  }}
  #overlay.open{{opacity:1;visibility:visible}}

  #nav-menu{{
    position:absolute; top:56px; left:0; z-index:160; background:#fff;
    min-width:220px; max-width:90vw; border-radius:0 0 .5rem 0;
    box-shadow:0 8px 24px rgba(0,0,0,.2); padding:var(--sp-1) 0;
    transform:translateY(-8px); opacity:0; visibility:hidden;
    transition:transform .15s,opacity .15s; display:flex; flex-direction:column;
  }}
  #nav-menu.open{{transform:translateY(0);opacity:1;visibility:visible}}
  .navbtn{{
    display:block; width:100%; text-align:left; background:none; border:none;
    padding:.75rem var(--sp-3); font-size:.95rem; color:var(--ink); cursor:pointer;
  }}
  .navbtn:hover, .navbtn:focus-visible{{background:var(--panel)}}
  .navbtn.active{{font-weight:700; color:var(--accent); border-left:3px solid var(--accent)}}
  .close-btn{{
    align-self:flex-end; background:none; border:none; color:var(--muted);
    font-size:.8rem; padding:.5rem var(--sp-2) 0; cursor:pointer; touch-action:manipulation;
  }}
  .close-btn:hover, .close-btn:focus-visible{{color:var(--ink)}}
  #info-panel .close-btn{{align-self:flex-end; padding:0 0 var(--sp-2)}}

  #info-panel{{
    position:absolute; top:56px; right:0; z-index:160; background:#fff;
    width:min(320px,90vw); border-radius:0 0 0 .5rem;
    box-shadow:0 8px 24px rgba(0,0,0,.2); padding:var(--sp-3);
    transform:translateY(-8px) scale(.98); opacity:0; visibility:hidden;
    transition:transform .15s,opacity .15s;
  }}
  #info-panel.open{{transform:translateY(0) scale(1);opacity:1;visibility:visible}}
  #info-panel h3{{margin:0 0 var(--sp-1);font-size:.95rem}}
  #info-panel p{{font-size:.85rem;line-height:1.55;color:var(--ink);margin:0 0 var(--sp-1)}}
  #info-panel p:last-child{{margin-bottom:0}}

  #fs-btn[aria-pressed="true"]{{background:rgba(255,255,255,.25)}}
</style>
</head>
<body>

<header id="topbar">
  <button id="hamburger-btn" class="icon-btn" aria-expanded="false" aria-controls="nav-menu"
          title="Meny" onclick="toggleMenu()">☰</button>
  <span class="title">Topbar-mønster — demo</span>
  <button id="info-btn" class="icon-btn" aria-expanded="false" aria-controls="info-panel"
          title="Om denne siden" onclick="toggleInfo()">ℹ️</button>
  <button id="fs-btn" class="icon-btn" aria-pressed="false"
          title="Fullskjerm" onclick="toggleFullscreen()">⛶</button>
</header>

<div id="overlay" onclick="closeAll()"></div>

<nav id="nav-menu" role="menu" aria-label="Sidenavigasjon">
{CLOSE_BTN}
{nav_items}
</nav>

<div id="info-panel" role="dialog" aria-label="Om denne siden">
  {CLOSE_BTN}
  <h3>Hva denne siden viser</h3>
  <p>En generert demo av topbar-mønsteret: fast toppfelt, hamburgermeny,
  denne info-knappen, og fullskjerm-knappen til høyre. Ingen ekte data.</p>
  <h3>Datakilde / oppdateringsfrekvens</h3>
  <p>Ingen datakilde — statisk demofil, bygget én gang av generatoren og ikke ment å
  oppdateres med nye tall.</p>
  <h3>Laget av</h3>
  <p>RAIWork, som bevis-artefakt for topbar-mønsteret.</p>
</div>

<div id="scroll-area">
<main>
{sections_html}
</main>
</div>

<script>
  var menu = document.getElementById('nav-menu');
  var info = document.getElementById('info-panel');
  var overlay = document.getElementById('overlay');
  var hamburgerBtn = document.getElementById('hamburger-btn');
  var infoBtn = document.getElementById('info-btn');

  function closeAll() {{
    menu.classList.remove('open');
    info.classList.remove('open');
    overlay.classList.remove('open');
    hamburgerBtn.setAttribute('aria-expanded', 'false');
    infoBtn.setAttribute('aria-expanded', 'false');
  }}

  function toggleMenu() {{
    var willOpen = !menu.classList.contains('open');
    closeAll();
    if (willOpen) {{
      menu.classList.add('open');
      overlay.classList.add('open');
      hamburgerBtn.setAttribute('aria-expanded', 'true');
    }}
  }}

  function toggleInfo() {{
    var willOpen = !info.classList.contains('open');
    closeAll();
    if (willOpen) {{
      info.classList.add('open');
      overlay.classList.add('open');
      infoBtn.setAttribute('aria-expanded', 'true');
    }}
  }}

  document.querySelectorAll('.navbtn').forEach(function(btn, i) {{
    if (i === 0) btn.classList.add('active');
    btn.addEventListener('click', function() {{
      document.querySelectorAll('.page').forEach(function(p) {{ p.style.display = 'none'; }});
      document.querySelectorAll('.navbtn').forEach(function(b) {{ b.classList.remove('active'); }});
      document.getElementById(btn.dataset.target).style.display = 'block';
      btn.classList.add('active');
      closeAll();
    }});
  }});

  function fullscreenSupported() {{
    var el = document.documentElement;
    return !!(el.requestFullscreen || el.webkitRequestFullscreen || el.msRequestFullscreen)
      && document.fullscreenEnabled !== false;
  }}

  function toggleFullscreen() {{
    // Never let this throw to the page/host: many in-app WebViews (Teams,
    // Outlook mobile) either lack requestFullscreen entirely or reject its
    // Promise, and an uncaught error here surfaced as a visible "Script
    // error" banner to the user in Teams-on-mobile testing --
    // even though hamburger/info (plain click handlers, no browser APIs)
    // worked fine in the same environment. Isolate the failure to this
    // control only.
    try {{
      if (document.fullscreenElement) {{
        var exitFn = document.exitFullscreen || document.webkitExitFullscreen || document.msExitFullscreen;
        var exitResult = exitFn && exitFn.call(document);
        if (exitResult && exitResult.catch) exitResult.catch(function() {{}});
      }} else {{
        var el = document.documentElement;
        var reqFn = el.requestFullscreen || el.webkitRequestFullscreen || el.msRequestFullscreen;
        if (!reqFn) return;
        var reqResult = reqFn.call(el);
        if (reqResult && reqResult.catch) reqResult.catch(function() {{}});
      }}
    }} catch (err) {{
      // swallow -- see comment above
    }}
  }}

  document.addEventListener('fullscreenchange', function() {{
    var isFs = !!document.fullscreenElement;
    document.getElementById('fs-btn').setAttribute('aria-pressed', isFs ? 'true' : 'false');
  }});

  // Feature-detect once at load: if this environment cannot go fullscreen at
  // all (confirmed on at least one mobile Teams in-app browser during
  // manual testing), disable the button instead of leaving a control that
  // does nothing -- or worse, one whose click handler can throw.
  (function() {{
    var btn = document.getElementById('fs-btn');
    if (!fullscreenSupported()) {{
      btn.disabled = true;
      btn.style.opacity = '.35';
      btn.style.cursor = 'not-allowed';
      btn.title = 'Fullskjerm er ikke tilgjengelig i denne visningen';
    }}
  }})();

  document.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape') closeAll();
  }});

  // Marker used only by tools/verify_standalone_core.py-style console checks
  // and by the Playwright interaction test in verify_topbar_demo.py.
  window.__TOPBAR_DEMO_READY__ = true;
</script>
</body>
</html>
"""

OUT.write_text(HTML, encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
print("next: python3 ../../tools/verify_standalone_core.py " + str(OUT))
