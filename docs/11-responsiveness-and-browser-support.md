# Responsiveness, opening context and browser support — where the standard is real today, and where it's still a proposal

**Reader:** contributor — you are changing the toolkit, and need the constraint or the convention behind it.

**Status:** proposal, partially already true of the shipped templates (see §1), partially
not wired in anywhere yet. Graduates issue #5 the same way `docs/09` graduated
#12/#14/#15/#17/#20 — by separating *measured fact* (which stays in
`docs/01-tenant-constraints.md`, the one place that changes when the tenant or a browser
does), *normative principle* (this document), and *proven pattern* (an actual file under
`examples/`, not prose describing one).

Folds in #15 (topbar pattern, `examples/07-topbar-pattern-demo/`) and #22 (sharing-path
robustness, `examples/10-consolidated-standalone-demo/`) — both of which tested pieces of
#5 empirically after it was written. Where they found #5 was right, that is noted. Where
they found it incomplete or wrong, this document changes the principle rather than
repeating the old one next to the correction.

---

## 1. What the templates do today (measured, not assumed)

- **Viewport:** both templates carry `<meta name="viewport" content="width=device-width,
  initial-scale=1">`. Matches §2 below.
- **Layout:** fluid CSS Grid / flexbox, no fixed breakpoints — already noted in
  `docs/09` §1 for the same templates.
- **Print:** `single-file-dashboard.html` has `@media print` rules (hides the drop bar and
  filter controls, resets header colours). `cube-dashboard.html` has none. Not consistent
  between the two templates.
- **Accessibility: six rules are a gate since 2026-10-24, and the list of what is not
  covered is printed on every run.** `tools/verify_a11y.py` measures: `<html lang>` and a
  non-empty `<title>`; exactly one visible `<h1>` and no skipped heading level; an
  accessible name on every button, link, form control and meaningful inline SVG; WCAG AA
  text contrast (4.5:1, or 3:1 at 24 px and at 18.66 px bold) against the background
  actually composited behind the text; `aria-hidden` on something focusable, duplicate
  `id`s, and `tabindex` above zero. `tools/verify_documented.py` runs it over every
  artefact a README verifies, so a new example is covered by being documented.
  - **axe-core is not vendored, and the reason is a licence decision rather than an
    oversight.** It is MPL-2.0, and this repository's licence story is AGPL plus one
    carefully worded exception; adding 500 KB under a third licence is the project owner's
    call. The rules above are the subset that could be written and explained here, and
    `ROADMAP.md` A10 keeps the axe-core half open, named as open.
  - **The first run was wrong in a way only a real artefact could show.** It returned the
    first non-transparent ancestor background, so `background: rgba(0,52,62,.07)` over
    white read as solid dark blue: dark ink on dark ink, 1.00:1, on a button that is
    plainly legible. The background is now composited from the canvas inwards, and
    `tests/test_a11y_gate.py` keeps a 7% tint as a page that must pass.
  - **It found two real defects in shipped examples.** Three inlined matplotlib charts
    each numbered their internals from 1, so `id="figure_1"` existed three times in one
    document and every `url(#...)` reference resolved to whichever came first; the builder
    now prefixes them per chart. And a fullscreen icon was an unnamed graphic inside a
    named button; it is `aria-hidden="true"` now.
  - What it does not check, and says so: ARIA role and pattern conformance, live regions,
    focus order and focus visibility (needs interaction), reduced motion, screen-reader
    output. A green run means none of the six, not "accessible".
- **`lang` attribute:** every template now writes `lang="nb"` for Norwegian
  (`templates/i18n/*.strings`, key `html_lang`). `cube-dashboard.html` wrote `lang="no"`
  until 2026-10-13; `tests/test_i18n.py` records the change as a deliberate nb pair.
- **Touch targets: measured, and met in every example since 2026-10-24.**
  `tools/verify_viewports.py` checks every interactive element against 44×44px on the
  four touch viewports, and `tools/verify_documented.py` now runs it over every artefact
  a README documents, plus a second pass at the default floor over every verified
  artefact whose README does not declare one. So this is a gate in CI, not a measurement
  someone remembers to take.
  - The first run found five undersized targets in every dashboard built from the
    template (three `<select>` at 160×**37**px, reset at 69×**42**px); `min-height:2.75rem`
    fixed them.
  - **Chromium was the only engine where that held.** WebKit ignores padding, border and
    `min-height` on a native `<select>`: the same rule produced 160×**22**px in WebKit
    and 160×44px in Chromium, because the native control paints its own box. The
    dashboard's three filters were therefore 22 px tall on every iPhone. `appearance:
    none` (plus `-webkit-appearance:none`) hands the box back to the stylesheet, and a
    chevron drawn as a `background-image` replaces the one the native control drew. A
    target that is only big in one engine is not a target, so the measurement belongs in
    every engine the tool supports, not just the default one.
  - The cube's five-column detail table overflowed a 390 px phone by 3 px in WebKit
    (Chromium's minimum column widths happened to fit), clipping the last column. It now
    scrolls inside its own panel (`#tbl{overflow-x:auto}`), which keeps the overflow
    reachable instead of off the page.
  - Widening the gate to every example found the same class everywhere else: process
    tabs and toolbar buttons at **38.5 px**, `Vis i flyten` at 35 px, the day board's nav
    links and selects at 42 px, the editable document's tools at 35 px, the topbar icon
    buttons at 33–35 px, the deck's control buttons at 42 px and its section rail links
    at 21 px. All raised to 44 px. A target that is only big in the template that was
    inspected is not a target.
  - **One exemption, and it is a rule, not a waiver:** an `<a>` whose computed `display`
    is `inline` is a run of words inside a line of text, not a control — what a reader
    taps is the line box. Forcing prose links to 44 px would break every paragraph, and
    the platform guidance exempts them the same way. A link styled as a block, a pill or
    a list row is still measured.
- **Text floor: 14 px by default, declared where an artefact is a picture.**
  `--text-floor PX` sets the floor and `--text-floor-above WIDTH` limits it to viewports
  at least that wide; both are printed on every run, so a declaration is visible in CI
  output rather than hidden in a file. Three kinds of artefact cannot hold 14 px at every
  width without giving up what they exist for, and each says so in its own README:
    - the process diagram, fitted to its frame and panning below the size where its
      smallest text is 12 px (`--text-floor 12`);
    - a slide whose illustration is one scaled picture, or a dense measurement band whose
      card labels are 9–10 px by design (`--text-floor 9`, `--text-floor 11
      --text-floor-above 1366`);
    - a chart POC drawn in a fixed coordinate space and scaled to its card
      (`--text-floor 10 --text-floor-above 1366`).
  Overflow and touch targets are checked at every viewport regardless of the declared
  floor, and everything that is prose, chrome or a control holds 14 px.
- **Text floor, the measurement that started it:** the same tool reads the  smallest rendered text on every viewport, correcting for the SVG viewBox scale (14
  user units at scale .83 is 11.6 px on screen, which a CSS-only check cannot see). It
  found 11 px axis labels and 12 px KPI, table-header, footer and tooltip text — the
  dashboard shipped below this document's own floor. All of it is now `.875rem`, and
  `examples/01-hello-dashboard/` and `examples/02-paired-dashboard/` were rebuilt.
  - Raising the axis text exposed the layout assumption behind it: the bar chart angled
    names under upright bars and **overlapped** them below about 500 px, because the
    old rule guessed fit from a 16-character count. It now measures the labels it drew
    and falls back to the sideways layout when they touch, and the line chart keeps only
    the period labels that do not touch, always including the last one. Both measure
    with a canvas so the decision is right on the first paint, when the card is still
    hidden and every box reads zero.
- **JavaScript-resilience pattern (§4 below) is proven, not shipped:** it exists and is
  tested in `examples/10-consolidated-standalone-demo/`, and the fullscreen
  feature-detection half of it in `examples/07-topbar-pattern-demo/`. Neither template
  has it. A dashboard built today from `build_dashboard.py` ships with none of the
  degradation behaviour described in §4.
- **A stronger, separate pattern also exists, not yet reconciled with the one above:**
  issue #30 built three example demos, now merged into `examples/`:
  `examples/13-js-free-standalone-poc/`, `examples/14-chart-emulation-nojs-poc/`, and
  `examples/15-chart-library-comparison-poc/`. Together they tested whether navigation
  and charts can avoid *needing* JavaScript at all, rather than only degrading
  gracefully when it fails to run. Navigation, page switching, an info panel and a
  theme toggle were built with zero `<script>` dependency (`<input type="checkbox">` +
  CSS `:checked`, plus a radio group for page switching — `:target` was removed in
  #50, see the row-24 note in §3b) and verified to behave identically with JavaScript on or
  off. Twelve chart types were separately shown to be renderable as static CSS/SVG with
  no JavaScript at all, provided the data is known when the file is built — see
  `examples/14`'s README for which chart types that holds up well for and which are
  costlier to generalise. A third demo took the opposite starting assumption on purpose
  — it requires JavaScript — to put Chart.js, hand-rolled CSS/SVG and Matplotlib
  (Python, static SVG generated at build time) side by side on identical data,
  including a working print/export button (§8) and a JS-vs-CSS filtering comparison. Not
  reconciled with §3b below yet: whether a dashboard should *require* JavaScript (and only
  degrade per §3b when it fails) or avoid needing it in the first place (per #30) is an
  open decision, tracked in issue #30 (see its "Må testes videre" section), not resolved by
  this document.
- **This "require JS or not" question only applies to BUNDLED Tier 1** — the single-file,
  data-fully-inlined mode `docs/02-architecture.md`'s "Choosing a mode" section describes,
  which is the only shape where the content genuinely CAN exist without JavaScript ever
  running (data and markup are already the same static bytes). It does not apply to
  PAIRED (`docs/02` §"Updating the data": *"the payload has to be JavaScript"* — a
  `<script src="data.js">` tag is how a `file://` page reads its sibling data file at
  all, before any navigation or chart even enters the picture), and it does not apply to
  Tier 2 (Embedded) or Tier 3 (Live/DuckDB-WASM) — both need a running script environment
  to function by construction. #30's three demos are a BUNDLED-only exploration; nothing
  about them suggests PAIRED or Tier 2/3 dashboards could or should drop their existing
  JavaScript dependency.

## 2. General principles — devices, orientation, input

Unchanged from #5 §1, still normative:

- Desktop, laptop, tablet and mobile are all supported — no minimum width is too small to
  design for. Mobile adaptation of charts and tables is the default, not an add-on request.
- Both orientations must work without clipped or hidden content.
- Touch and mouse/keyboard are equal input methods — nothing should be reachable only via
  hover.
- Navigation: a collapsing topbar/slide-down menu is an **approved pattern**
  (`examples/07-topbar-pattern-demo/`, decided 2026-09-11 in `docs/09` §1) — proven to
  work, not just a stated preference. It is optional, not required, and a fixed sidebar
  remains acceptable too. Not wired into the production templates yet — same open item
  `docs/09` already carries for the same reason (`00-vision.md` principle 1: no CDN, no
  framework, hand-built HTML/CSS/JS only).

## 3. Browser support — two separate questions #5 ran together

#5 §2 asked one question ("which browsers do we support") and got, in effect, an
unverified guess. Splitting it in two, because #22 showed they fail independently and a
fix for one does nothing for the other:

### 3a. Which browser engine and version — three engines tested, versions and devices not

> **Caveat #5, narrowed:** Edge and Chrome, last two major versions, as *the* delivery
> browsers is still an assumption from past deliveries, not a confirmed Eksempel AS IT policy.
> What is now measured: every verify tool takes `--engines`, and CI on the public
> repository runs every documented example check (`tools/verify_documented.py`) in
> Playwright's Chromium, Firefox and WebKit on each pull request. That tests the three
> engines, not the shipped browsers: Playwright's WebKit is the engine behind Safari, not
> Safari on an iPhone, and no specific version is pinned. `probe/
> browser-capability-probe.py` (`docs/01-tenant-constraints.md` rows 19-20) still drives
> Chromium only.

- Supported and tested on every pull request: Chromium (Edge, Chrome), Firefox, and
  WebKit (Safari), in current Playwright builds.
- Edge and Chrome stay the assumed delivery browsers, pending confirmation above.
- Not supported: Internet Explorer.
- No polyfills. A file that breaks or looks wrong in Firefox or Safari is a bug.

### 3b. Whether JavaScript executes at all in the delivery context — measured, and the answer is more specific than "browser support"

This is the part #5 didn't ask, and #22 answered by accident while testing something
else: a fully supported, fully modern browser can still receive a page where the
project's own `<script>` tags never run — not because the *browser* rejected them, but
because the *viewer the file was opened in* did (an in-app preview, a sandboxed
document viewer, a WebView with scripting constrained). `docs/01-tenant-constraints.md`
rows 21–22 are the measured record:

- Row 21: a real iPhone, a real Teams message link — the page's own JavaScript ran fine;
  the one thing that broke was an unguarded `Fullscreen` API call, which the host WebView
  surfaced to the user as a visible script-error banner. Fixed by feature-detecting the
  API and disabling the button instead of calling it blind
  (`examples/07-topbar-pattern-demo/README.md`).
- Row 22: the same file, shared three ways from OneDrive. A raw "copy link" pasted into
  an e-mail ran on PC and did not run *at all* on mobile — no console, no error, nothing.
  The identical link opened via Teams' own preview card ran on both. The identical Teams
  message's plain-text link (not the card) rendered as source code, on both platforms —
  never executed as a page.

**The principle this produces, and the one #5 should have had from the start:** a
dashboard must assume its own JavaScript might not run at all, in an otherwise fully
supported browser, for reasons outside anything this project controls. The required
behaviour is not "make JavaScript run everywhere" (not possible — see row 22c) but "never
let 'JavaScript did not run' look like a broken page with no explanation." Concretely,
copy the pattern already built and tested in `examples/10-consolidated-standalone-demo/`:

1. A warning message that is visible **by default**, in plain HTML/CSS, requiring no
   JavaScript to display.
2. The earliest possible inline `<script>` in the document hides it — its own successful
   execution is the proof "some JavaScript ran." (`<noscript>` cannot do this job: it only
   fires when scripting is formally off, not when a host blocks the specific script tags
   while leaving scripting on in the spec's eyes.)
3. A second, later check confirms the *main* script actually finished (a completion flag
   set as its last line), not just started — so a script that started and crashed midway
   shows a distinct "something stopped partway" message instead of silently leaving stale
   content on screen.
4. Any environment self-diagnostics (screen size, browser, storage support) live on the
   page itself, not behind a menu that itself requires JavaScript to open — a diagnostic
   tool that depends on the thing it's meant to diagnose is a logical dead end, and this
   is a real bug #22 found and fixed, not a hypothetical.

This does not replace §3a — an unsupported browser is still an accepted failure. It adds
a second, independent failure mode that a supported browser does not protect against.

**Open question this section does not answer:** the pattern above assumes JavaScript is
still required and only adds a warning for when it fails. Issue #30 tested a different
answer — not requiring JavaScript in the first place for navigation and (within limits)
for charts — see §1 above and `examples/13-js-free-standalone-poc/` /
`examples/14-chart-emulation-nojs-poc/`. Which of the two becomes the standard, or whether
both stay valid choices depending on the dashboard, is not decided here. Scope note (see
§1's BUNDLED-only callout): this whole question — §3b's warning pattern vs. #30's
no-JS-by-construction pattern — is a choice between two ways of handling a BUNDLED
dashboard. A PAIRED or Tier 2/3 dashboard has no such choice to begin with; §3b's warning
pattern is the only one that can ever apply there, since those modes already require
JavaScript to load their data.

### 3c. A real blocked-JS case, and how the §3b pattern held up

Row 12 of the test matrix (§11 below) was closed by an actual production incident, not a
simulation: an internal dashboard project, sent as a raw file attachment over iMessage,
rendered broken on both iPhone and Mac. No client data or specifics from that project
belong in this doc — only the generalisable finding.

**Root cause, confirmed against independent sources, not assumed:** since iOS 13, Quick
Look — the preview engine behind tapping an HTML attachment in Messages, Mail, and Files
on both iOS and macOS — disables JavaScript. This is a deliberate Apple security
decision (arbitrary script must not run just from previewing an attachment), not a bug in
the file, and not something fixable from inside the HTML. `<noscript>` doesn't help
either (§3b point 2): scripting is still "on" in the spec's eyes, Quick Look just won't
run these specific script tags.

**What broke, concretely, and why it was worse than §3b's own worked example:**

- A view whose top-line numbers are built entirely by a JS render call into an
  initially-empty container showed the §3b banner correctly (the pattern worked exactly
  as designed) but every number under it was blank. A working warning banner sitting
  above empty boxes still reads as "broken," even though the pattern itself did its job.
- A second, slide-deck-style view showed *nothing at all*, not even a banner — worse than
  the first, because it had no §3b pattern in it to begin with. Root cause: each slide
  defaulted to `opacity:0`, and only a JS-added "active" class ever set `opacity:1`. With
  no JS, no slide ever became active, so the whole view was an invisible stack over a
  plain background colour.

**The fix, and the general pattern it generalises to:** don't stop at "show a banner
explaining it's broken" — pre-render the highest-value static facts directly into the
markup, using the *same values already computed at build time*, so the no-JS view shows
real information instead of an apology next to empty boxes.

- Slide/deck-style views: unblock the first slide's container **and** its individual
  text elements separately — a slide's inner elements often have their own independent
  `opacity:0` default, gated on the same missing class one level down
  (`.slide.active .step` vs `.slide.active`). Unblocking the container alone still shows
  a blank slide because its children stay separately hidden. Also worth prefilling any
  counter/animation spans with their final static value instead of `0` — safe, because a
  counter-animation script always resets to `0` and animates up from there on its own
  first line, so the two never conflict.
- Report/panel-style views: hand-add the two or three highest-value numbers as static
  markup inside whatever container the JS render would otherwise populate from empty,
  using data already available at build time. The JS render still overwrites the whole
  container wholesale when it does run, so there's no staleness risk — the static markup
  only exists in the window where JS didn't run at all.
- Reword any "this looks broken" banner text to be platform-neutral. A banner written for
  one specific delivery channel (e.g. "open it via the preview card this messaging app
  builds") is actively wrong guidance once the same file is opened through a different
  channel with different behaviour (e.g. an attachment preview with no such card).
  Instruct generically: save the file, then open it from downloads/files in an actual
  browser.

**Status of this pattern in the templates (2026-10-24):** all three have it. The process diagram carried the canary from the start. The rows dashboard and the cube now write their facts into the markup — totals and the first rows for a dashboard; the row, cell and dimension counts plus the dimension names for a cube, which cannot decode without scripting at all. `tests/test_nojs_fallback.py` opens both with scripting disabled, requires the numbers on screen to equal the source data, and deletes the canary to prove the class is what decides (25 checks).

**Detection mechanism — worth calling out on its own, since it's what makes the fixes
above possible without JS-in-JS bootstrapping:** the single canary line
`<script>document.documentElement.className+=" js"</script>`, placed as the first thing
in `<body>`, plus a pure-CSS rule keyed off its *absence* (`html:not(.js) …`). No
polling, no "try to detect if JS works" logic — the presence of the `.js` class on
`<html>` **is** the proof that some JavaScript executed, and every fallback rule is just
a normal CSS selector against a class that either got added or didn't. This is why
`<noscript>` isn't the right primitive here (§3b point 2) but a canary class is.

**Verification, not just claimed:** a Playwright Chromium context with
`java_script_enabled=False` — the same restriction Quick Look imposes — that loads the
file and fails if visible body text drops below a floor, is now the permanent regression
check for this failure mode: a real headless no-JS render, not a visual inspection or a
claim that the CSS "should" work.

**One more quirk, unrelated to JavaScript, hit while building preview images for this
fix:** Pillow (`PIL.Image`) on macOS returns from `Image.open()` with the file only
lazily opened, not decoded. Calling `.convert("RGB")` or `.save()` on that lazy handle
without an explicit `.load()` first silently produces a truncated ~32-byte output with no
exception — not a crash, just wrong data that looks like success until you check the
byte count. Fix: always call `img.load()` immediately after `Image.open()` before any
transform, when the pipeline isn't a single unbroken `Image.open(...).convert(...)`
expression.

**Still open (per row 12's superseded status, this section doesn't claim to have found
every blocked-JS surface, only this one):** no equivalent real-world test yet for Gmail's
own attachment preview, the Outlook mobile app's, or Android's file-preview surface —
those remain simulated-only via the same no-JS-context harness, not yet confirmed against
a real device.

## 4. Opening and sharing context — no longer one flat list

#5 §3 listed six channels as if they were interchangeable ("the file shall work
identically regardless of how it's opened"). §3b above already broke that claim for one
of them. The channel list survives, but sharing path is now its own variable, not a
detail nested inside "opening context":

| Channel | Status |
|---|---|
| Local disk (`file://`) | ✅ Proven — `docs/01-tenant-constraints.md` row 7 |
| OneDrive/SharePoint-synced folder | ✅ Proven — same tenant probe |
| Direct link opened in-browser (https) | Not separately measured from the row above |
| E-mail attachment opened from Outlook | iOS app, native preview, measured 2026-09-28 on a real iPhone: scripts do not run. The no-JS banner and the static layer show and are readable (§3b works in the wild). Desktop Outlook and Android are still not tested |
| "Copy link" pasted into an e-mail | ⚠️ Works on PC. Confirmed **not** to run at all on mobile — row 22a |
| Link shared in a Teams message, opened via Teams' own preview card | ✅ Confirmed working on both PC and mobile — row 22b |
| Same Teams message, plain-text link under the card | ❌ Confirmed broken on both PC and mobile (renders source code) — row 22c |
| Raw `.html` attachment uploaded to Slack | ⚠️ macOS opened it; iPhone preview rendered source. Saving/opening the same file through an installed browser rendered it — row 27 |

Always 100% offline-capable once opened: no CDN dependencies, everything embedded in one
`.html` file — unchanged from #5, not contradicted by anything above.

**Every dashboard is still expected to degrade per §3b regardless of which row above it
was opened through**, because which row applies is often outside the recipient's control
(they forward a link; they don't choose whether Teams renders it as a card).

## 5. Responsive design — technical principles

Unchanged from #5 §4, plus one concrete rule added by a real bug:

- Mobile adaptation of charts (Chart.js) and tables is the default build, not opt-in.
- Minimum touch target 44×44px on interactive elements on mobile — **measured, not
  yet satisfied** (see §1). `python3 tools/verify_viewports.py <artefact.html>`
  reports every element below the minimum, at six viewports covering desktop, laptop,
  tablet and phone in both orientations, and also fails on any horizontal overflow.
  It is a post-build check, not a build-time lint: the templates still do not
  guarantee the minimum.
- Images, canvas and grid scale down without horizontal scroll.
- **New, from #22:** images and logos need an explicit CSS *width*, not only height. A
  logo with only `height` set was invisible on mobile and happened to work on PC by
  accident — the kind of bug that only shows up on the platform nobody tested on.
- **Do not draw text into an SVG diagram that must work on a phone.** An SVG scales as one
  picture. A flow diagram in a pitch page was scaled to 0.48× at 390 px wide, and its labels
  ended up 6.25 px high. Rebuilt as flex columns, the same text stays at body size and
  wraps into cards below 640 px. Use SVG for shapes. Put the words in HTML.
- **A diagram that must stay a drawing fits down to a text floor, then pans.** The process
  diagram (`templates/process-diagram.html`) keeps its words in the SVG, so it cannot
  reflow. Measured 2026-10-16 on a five-lane, 18-step process: fitted to a 1084 px window
  its text was 8.9 px. So the CSS fits the drawing to its frame only down to the scale
  where its smallest text is 12 px (`min-width`), and the frame scrolls below that, with
  the lane names kept in view by a script (not `position:sticky`, see row 26). The page's
  own `max-width` went too: capped at 96rem, it made a wide screen scroll a drawing it
  had room for, and left an ultrawide screen mostly empty. The page has no cap now, the
  prose keeps its own measure, and the drawing grows up to 1.5x to fill the width. Growing
  alone cannot fill an ultrawide screen with a tall flow (a 28-step plan would need 2.2x,
  31 px text and 6100 px of height), so the file also carries the flow as rows, left to
  right, and shows that where it fits with less scrolling: the same plan fits one
  3440x1440 screen at 88 %. Rows must fit the window's height as well as its width, or
  the last lanes open below the edge (seen on a real 28-step plan below a long header:
  1308 px of drawing, 1092 px of room). Each rows lane is only as tall as its own boxes,
  which brought that plan to 1200 px. Every px of rows box width costs one px per
  layer, so 15 layers on a 3440 screen allow boxes of about 170 px.
  `tools/verify_process_diagram.py` checks this in seven windows, up to 3440x1440.
- **`overflow: hidden` on `body` alone does not stop a page from scrolling.** Hidden panels
  with `position: absolute` still made `body` taller than the viewport. The fix was to clamp
  both: `html, body { height: 100%; overflow: hidden; }`, with the scroll on the content
  pane only.

## 6. Accessibility

Unchanged from #5 §5: built on the `eksempel-brand` skill as the source of truth for colour,
contrast and typography — no parallel a11y standard invented here. Semantic HTML, `alt`
text, keyboard-navigable menus, layout that tolerates browser zoom/text scaling.
`docs/09` already covers the concrete gaps found in the real templates (sortable headers,
colour-only KPI deltas) — this document does not repeat that audit.

## 7. Performance — perceived load time under one second

Unchanged from #5 §6: the goal is *perceived* readability under a second, not necessarily
full data load. Critical CSS/skeleton shown immediately; heavy elements (charts)
lazy-initialised on first visit to a page; markup hidden until data is ready
(`visibility:hidden`/`opacity:0` → fade in) to avoid a visible flash of wrong/empty
content; Chart.js and other JS embedded locally; large datasets flagged and considered
for cube mode rather than raising the size budget.

## 8. Print and export

Unchanged from #5 §7: not built into every dashboard by default, but a documented,
reusable pattern (print CSS + optional export button) should exist to add on request
rather than designed from scratch each time. `single-file-dashboard.html`'s existing
`@media print` rules are a starting point; `cube-dashboard.html` has none yet (§1).

**That pattern now exists and is tested, not just called-for:** issue #30
(`examples/15-chart-library-comparison-poc/`) built and verified a
`window.print()` + `@media print` export button — no `html2canvas`/`jsPDF`, no extra
JS dependency — against a real headless PDF export, confirmed to capture a Chart.js
`<canvas>` (rasterised as it stood at export time), a hand-rolled CSS chart, and an
inlined static SVG together on one page. Still not wired into either production
template; still an open decision (see #30) whether this becomes the standard export
pattern or one of several.

## 9. Language

Unchanged from #5 §8: bokmål, nynorsk and English must all be supportable; date format
always follows Norwegian convention (dd.mm.åååå), independent of body-text language, in
every language version. The `lang="nb"` vs `lang="no"` inconsistency found in §1 was
reconciled on 2026-10-13: all templates use `nb`.

## 10. Security

Unchanged from #5 §9, now with measured backing instead of asserted rules:

- No external network calls in the shipped product: no CDN, no analytics/tracking, no
  third-party fonts loaded over the network.
- No dependency on a server, database or plugin beyond the browser itself.
- Embedded data sits in cleartext in the HTML source — never put anything in a file that
  everyone with file access shouldn't be able to read directly in source.
- Distribution only via approved Eksempel AS channels (OneDrive/SharePoint/Teams/e-mail), never
  public hosting. Backed by measurement, not assertion: anonymous/external sharing links
  are blocked tenant-wide (`docs/01-tenant-constraints.md` row 11).
- Carried over from issue #1: a sent file cannot be recalled. Classification must be
  checked before anything leaves the organisation — this belongs here as a security principle,
  not only in #1's onboarding narrative.

## 11. Minimum test matrix

Expanded from #5 §10. Rows already run manually are marked; the ones still open are
carried forward from #22 rather than re-listed as a new tracker — #22 stays the live
collector for further findings on this specific thread, on purpose (see its own text:
kept open deliberately to avoid the issue-sprawl #12/#14/#15/#17/#20 needed cleaning up).

| # | Test | Status |
|---|------|--------|
| 1 | Open via double-click (`file://`) on Windows | ✅ row 7 |
| 2 | Open from a OneDrive-synced folder | ✅ same tenant probe |
| 3 | Open directly in-browser via a OneDrive/SharePoint link (https) | Not separately measured |
| 4 | Mobile view (narrow, portrait) in Edge/Chrome mobile | ✅ rows 21–22, but only one phone/OS so far |
| 5 | Keyboard navigation through menu/interactive elements | Not tested against the real templates yet |
| 6 | Zoom to 150–200% in-browser | Not tested |
| 7 | Open in an unsupported browser, confirm no false sense of safety | Not tested |
| 8 | **New:** open the same link via each sharing path in §4's table | ⚠️ 3 of 7 rows measured (row 22), rest open in #22 |
| 9 | **New:** Android, any browser | ❌ open in #22 — no Android datapoint exists at all |
| 10 | **New:** real e-mail attachment (not a link) | ❌ open in #22 |
| 11 | **New:** named-recipient sharing scope, not just "everyone in the org" | ❌ open in #22 |
| 12 | **New:** the §3b warning pattern against a genuinely blocked-JS case, not a simulated one | ✅ real case, see §3c |
| 13 | **New:** raw Slack `.html` attachment on macOS and iPhone, then browser handoff on the phone | ⚠️ measured once — macOS opened the page, iPhone preview showed source, installed browser rendered the saved file; see row 27 |

## 12. Where this leaves the build pipeline

None of §3b's pattern or §5's touch-target/explicit-width rules should be hand-copied
into each new dashboard the way `examples/10`'s warning banner is today. They belong as
build-time helpers in `tools/build_dashboard.py` / `build_cube_dashboard.py` — assembled
into the output automatically, the same way `docs/09` proposes for the colour tokens. Not
done by this document, which only establishes the source pattern and where it already
lives.

## Open items this document does not resolve

- [ ] Confirm or correct the Edge/Chrome browser assumption (§3a) against actual Eksempel AS IT
      policy — carried over unchanged from #5, still not done.
- [ ] Run the comparison on real mobile devices (Safari on iOS, Chrome on Android). CI
      covers the three engines in emulation (§3a); `browser-capability-probe.py` still
      drives Chromium only.
- [ ] The still-open combinations from issue #22 (tracked there, not duplicated as a
      second list here): Android; Gmail and the Outlook mobile app specifically; a real
      e-mail attachment rather than a link; named-recipient sharing scope; mobile
      browsers distinguished from each other; the §3b warning pattern verified against a
      real blocked-JS case.
- [ ] Wire the §3b JavaScript-resilience pattern, and the §5 touch-target/explicit-width
      checks, into the actual build tooling — proven only in `examples/07` and
      `examples/10` so far, not shipped in either production template. **Now blocked on a
      prior decision, not just wiring:** issue #30 (`examples/13`, `examples/14`,
      `examples/15` — all three now in `examples/`, merged) proved a second, stronger
      pattern — not requiring JavaScript at all, rather than only degrading gracefully
      when it fails — for both navigation and (with per-chart-type caveats) charts, plus
      a working print/export button (§8) tested alongside a JS-requiring comparison page.
      Applies to `tools/build_dashboard.py`'s BUNDLED output specifically (see §1's
      scope note) — `build_cube_dashboard.py`'s cubes are also BUNDLED and in scope, but
      nothing about PAIRED output changes here. Whether the build tooling should offer the
      §3b pattern, the #30 pattern, or a per-dashboard choice between the two, needs
      deciding before this item is wired in, not after.
- [x] Reconcile `lang="nb"` vs `lang="no"` between the two templates (§1/§9). Done 2026-10-13.
- [ ] Add `@media print` rules to `cube-dashboard.html` to match `single-file-dashboard.html`
      (§8), or decide the gap is acceptable. §8 now has a tested reference pattern to copy
      from (`examples/15-chart-library-comparison-poc/`), not just a stated preference.

What a file can still do when scripts never run, and one earlier finding that a better test falsified: [the no-JavaScript question](15-no-javascript-findings.md).
