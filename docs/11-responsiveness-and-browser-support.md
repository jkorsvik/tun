# Responsiveness, opening context and browser support — where the standard is real today, and where it's still a proposal

**Status:** proposal, partially already true of the shipped templates (see §1), partially
not wired in anywhere yet. It takes the original browser-support requirements and
separates *measured fact* (which stays in
`docs/01-tenant-constraints.md`, the one place that changes when the tenant or a browser
does), *normative principle* (this document), and *proven pattern* (an actual file under
`examples/`, not prose describing one).

Folds in the topbar pattern (`examples/07-topbar-pattern-demo/`) and the sharing-path
tests (`docs/01-tenant-constraints.md` rows 21-22), both of which tested pieces of the
original requirements after they were written. Where they found the requirements right,
that is noted. Where
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
- **`lang` attribute is inconsistent:** `single-file-dashboard.html` uses `lang="nb"`;
  `cube-dashboard.html` uses `lang="no"`. Found while writing this document, not
  previously reported. Should be reconciled — see open items.
- **Touch targets: now measured, still not met.** `tools/verify_viewports.py` checks
  every interactive element against 44×44px on the four touch viewports. Nothing in
  `tools/build_dashboard.py` or the templates' CSS guarantees it, and the first run
  proved that: `examples/01-hello-dashboard/salg-dashboard.html` has five undersized
  targets on every touch viewport — three `<select>` at 160×**37**px and the reset
  `<button>` at 69×**42**px. Small shortfalls, real ones.
- **JavaScript-resilience pattern (§4 below) is proven, not shipped:** it exists and is
  described in §3b, and the fullscreen feature-detection half of it is in
  `examples/07-topbar-pattern-demo/`. Neither template
  has it. A dashboard built today from `build_dashboard.py` ships with none of the
  degradation behaviour described in §4.
- **A stronger, separate pattern also exists, not yet reconciled with the one above:**
  three example demos (see also `docs/15-no-javascript-findings.md`):
  `examples/13-js-free-standalone-poc/`, `examples/14-chart-emulation-nojs-poc/`, and
  `examples/15-chart-library-comparison-poc/`. Together they tested whether navigation
  and charts can avoid *needing* JavaScript at all, rather than only degrading
  gracefully when it fails to run. Navigation, page switching, an info panel and a
  theme toggle were built with zero `<script>` dependency (`<input type="checkbox">` +
  CSS `:checked`, plus a radio group for page switching; `:target` was removed, see
  `docs/01-tenant-constraints.md` row 24) and verified to behave identically with JavaScript on or
  off. Twelve chart types were separately shown to be renderable as static CSS/SVG with
  no JavaScript at all, provided the data is known when the file is built — see
  `examples/14`'s README for which chart types that holds up well for and which are
  costlier to generalise. A third demo took the opposite starting assumption on purpose
  — it requires JavaScript — to put Chart.js, hand-rolled CSS/SVG and Matplotlib
  (Python, static SVG generated at build time) side by side on identical data,
  including a working print/export button (§8) and a JS-vs-CSS filtering comparison. Not
  reconciled with §3b below yet: whether a dashboard should *require* JavaScript (and only
  degrade per §3b when it fails) or avoid needing it in the first place (per examples
  13-15) is an open decision, tracked in `docs/15-no-javascript-findings.md`, not resolved
  by this document.
- **This "require JS or not" question only applies to BUNDLED Tier 1** — the single-file,
  data-fully-inlined mode `docs/02-architecture.md`'s "Choosing a mode" section describes,
  which is the only shape where the content genuinely CAN exist without JavaScript ever
  running (data and markup are already the same static bytes). It does not apply to
  PAIRED (`docs/02` §"Updating the data": *"the payload has to be JavaScript"* — a
  `<script src="data.js">` tag is how a `file://` page reads its sibling data file at
  all, before any navigation or chart even enters the picture), and it does not apply to
  Tier 2 (Embedded) or Tier 3 (Live/DuckDB-WASM) — both need a running script environment
  to function by construction. The three no-JS demos are a BUNDLED-only exploration; nothing
  about them suggests PAIRED or Tier 2/3 dashboards could or should drop their existing
  JavaScript dependency.

## 2. General principles — devices, orientation, input

Unchanged from the original requirements, still normative:

- Desktop, laptop, tablet and mobile are all supported — no minimum width is too small to
  design for. Mobile adaptation of charts and tables is the default, not an add-on request.
- Both orientations must work without clipped or hidden content.
- Touch and mouse/keyboard are equal input methods — nothing should be reachable only via
  hover.
- Navigation: a collapsing topbar/slide-down menu is an **optional pattern**
  (`examples/07-topbar-pattern-demo/`, see `docs/09` §1), proven to
  work, not just a stated preference. It is optional, not required, and a fixed sidebar
  remains acceptable too. Not wired into the production templates yet — same open item
  `docs/09` already carries for the same reason (`00-vision.md` principle 1: no CDN, no
  framework, hand-built HTML/CSS/JS only).

## 3. Browser support — two separate questions the original requirements ran together

The original requirements asked one question ("which browsers do we support") and got, in
effect, an unverified guess. Splitting it in two, because the sharing-path tests showed
they fail independently and a fix for one does nothing for the other:

### 3a. Which browser engine and version — still not measured

> **Same caveat the original requirements carried, unchanged:** Edge and Chrome, last two major versions, is
> still an assumption based on what has come up anecdotally in past deliveries — not a
> confirmed IT policy, and not something this repo has tested. `probe/
> browser-capability-probe.py` (`docs/01-tenant-constraints.md` rows 19-20) only drives
> Chromium; it does not compare Edge, Chrome, Safari and Firefox against each other. This
> open item is carried forward, not resolved, by the topbar or sharing-path work.

- Officially supported (full QA responsibility): Microsoft Edge, Google Chrome (last two
  major versions) — pending confirmation above.
- Explicitly not supported/tested: Firefox, Safari, Internet Explorer, and any other
  browser.
- No polyfills or fallback code are built for browsers outside that list. "Doesn't work /
  looks wrong" in an unsupported browser is an accepted outcome, not a bug.

### 3b. Whether JavaScript executes at all in the delivery context — measured, and the answer is more specific than "browser support"

This is the part the original requirements didn't ask, and the sharing-path tests
answered by accident while testing something else: a fully supported, fully modern browser can still receive a page where the
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

**The principle this produces, and the one the requirements should have had from the
start:** a
dashboard must assume its own JavaScript might not run at all, in an otherwise fully
supported browser, for reasons outside anything this project controls. The required
behaviour is not "make JavaScript run everywhere" (not possible — see row 22c) but "never
let 'JavaScript did not run' look like a broken page with no explanation." Concretely:

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
   is a real bug the sharing-path tests found and fixed, not a hypothetical.

This does not replace §3a — an unsupported browser is still an accepted failure. It adds
a second, independent failure mode that a supported browser does not protect against.

**Open question this section does not answer:** the pattern above assumes JavaScript is
still required and only adds a warning for when it fails. Examples 13-15 tested a
different answer — not requiring JavaScript in the first place for navigation and (within limits)
for charts — see §1 above and `examples/13-js-free-standalone-poc/` /
`examples/14-chart-emulation-nojs-poc/`. Which of the two becomes the standard, or whether
both stay valid choices depending on the dashboard, is not decided here. Scope note (see
§1's BUNDLED-only callout): this whole question — §3b's warning pattern vs. the
no-JS-by-construction pattern — is a choice between two ways of handling a BUNDLED
dashboard. A PAIRED or Tier 2/3 dashboard has no such choice to begin with; §3b's warning
pattern is the only one that can ever apply there, since those modes already require
JavaScript to load their data.

### 3c. A real blocked-JS case, and how the §3b pattern held up

Row 12 of the test matrix (§11 below) was closed by a real blocked-JS case, not a
simulation: a dashboard sent as a raw file attachment over iMessage rendered broken on
both iPhone and Mac. Only the generalisable finding belongs in this doc.

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

The original requirements listed six channels as if they were interchangeable ("the file shall work
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
`.html` file — unchanged from the original requirements, not contradicted by anything
above.

**Every dashboard is still expected to degrade per §3b regardless of which row above it
was opened through**, because which row applies is often outside the recipient's control
(they forward a link; they don't choose whether Teams renders it as a card).

## 5. Responsive design — technical principles

Unchanged from the original requirements, plus one concrete rule added by a real bug:

- Mobile adaptation of charts (Chart.js) and tables is the default build, not opt-in.
- Minimum touch target 44×44px on interactive elements on mobile — **measured, not
  yet satisfied** (see §1). `python3 tools/verify_viewports.py <artefact.html>`
  reports every element below the minimum, at six viewports covering desktop, laptop,
  tablet and phone in both orientations, and also fails on any horizontal overflow.
  It is a post-build check, not a build-time lint: the templates still do not
  guarantee the minimum.
- Images, canvas and grid scale down without horizontal scroll.
- **New, from the sharing-path tests:** images and logos need an explicit CSS *width*, not only height. A
  logo with only `height` set was invisible on mobile and happened to work on PC by
  accident — the kind of bug that only shows up on the platform nobody tested on.
- **Do not draw text into an SVG diagram that must work on a phone.** An SVG scales as one
  picture. A flow diagram in a pitch page was scaled to 0.48× at 390 px wide, and its labels
  ended up 6.25 px high. Rebuilt as flex columns, the same text stays at body size and
  wraps into cards below 640 px. Use SVG for shapes. Put the words in HTML.
- **`overflow: hidden` on `body` alone does not stop a page from scrolling.** Hidden panels
  with `position: absolute` still made `body` taller than the viewport. The fix was to clamp
  both: `html, body { height: 100%; overflow: hidden; }`, with the scroll on the content
  pane only.

## 6. Accessibility

Unchanged from the original requirements: built on the active brand plugin's tokens and WCAG 2.2 as
the source of truth for colour, contrast and typography — no parallel a11y standard
invented here. Semantic HTML, `alt`
text, keyboard-navigable menus, layout that tolerates browser zoom/text scaling.
`docs/09` already covers the concrete gaps found in the real templates (sortable headers,
colour-only KPI deltas) — this document does not repeat that audit.

## 7. Performance — perceived load time under one second

Unchanged from the original requirements: the goal is *perceived* readability under a second, not necessarily
full data load. Critical CSS/skeleton shown immediately; heavy elements (charts)
lazy-initialised on first visit to a page; markup hidden until data is ready
(`visibility:hidden`/`opacity:0` → fade in) to avoid a visible flash of wrong/empty
content; Chart.js and other JS embedded locally; large datasets flagged and considered
for cube mode rather than raising the size budget.

## 8. Print and export

Unchanged from the original requirements: not built into every dashboard by default, but a documented,
reusable pattern (print CSS + optional export button) should exist to add on request
rather than designed from scratch each time. `single-file-dashboard.html`'s existing
`@media print` rules are a starting point; `cube-dashboard.html` has none yet (§1).

**That pattern now exists and is tested, not just called-for:**
`examples/15-chart-library-comparison-poc/` built and verified a
`window.print()` + `@media print` export button — no `html2canvas`/`jsPDF`, no extra
JS dependency — against a real headless PDF export, confirmed to capture a Chart.js
`<canvas>` (rasterised as it stood at export time), a hand-rolled CSS chart, and an
inlined static SVG together on one page. Still not wired into either production
template; still an open decision (see `docs/15-no-javascript-findings.md`) whether
this becomes the standard export
pattern or one of several.

## 9. Language

Unchanged from the original requirements: bokmål, nynorsk and English must all be supportable; date format
always follows Norwegian convention (dd.mm.åååå), independent of body-text language, in
every language version. The `lang="nb"` vs `lang="no"` inconsistency found in §1 should be
reconciled as part of implementing this, not left as-is.

## 10. Security

Unchanged from the original requirements, now with measured backing instead of asserted rules:

- No external network calls in the shipped product: no CDN, no analytics/tracking, no
  third-party fonts loaded over the network.
- No dependency on a server, database or plugin beyond the browser itself.
- Embedded data sits in cleartext in the HTML source — never put anything in a file that
  everyone with file access shouldn't be able to read directly in source.
- Distribution only via approved channels (OneDrive/SharePoint/Teams/e-mail), never
  public hosting. Backed by measurement, not assertion: anonymous/external sharing links
  are blocked tenant-wide (`docs/01-tenant-constraints.md` row 11).
- A sent file cannot be recalled. Classification must be checked before anything leaves
  the organisation. This belongs here as a security principle, not only in the
  onboarding narrative.

## 11. Minimum test matrix

Expanded from the original requirements. Rows already run manually are marked; the ones
still open are carried forward from the sharing-path tests.

| # | Test | Status |
|---|------|--------|
| 1 | Open via double-click (`file://`) on Windows | ✅ row 7 |
| 2 | Open from a OneDrive-synced folder | ✅ same tenant probe |
| 3 | Open directly in-browser via a OneDrive/SharePoint link (https) | Not separately measured |
| 4 | Mobile view (narrow, portrait) in Edge/Chrome mobile | ✅ rows 21–22, but only one phone/OS so far |
| 5 | Keyboard navigation through menu/interactive elements | Not tested against the real templates yet |
| 6 | Zoom to 150–200% in-browser | Not tested |
| 7 | Open in an unsupported browser, confirm no false sense of safety | Not tested |
| 8 | **New:** open the same link via each sharing path in §4's table | ⚠️ 3 of 7 rows measured (row 22), rest open |
| 9 | **New:** Android, any browser | ❌ open — no Android datapoint exists at all |
| 10 | **New:** real e-mail attachment (not a link) | ❌ open |
| 11 | **New:** named-recipient sharing scope, not just "everyone in the org" | ❌ open |
| 12 | **New:** the §3b warning pattern against a genuinely blocked-JS case, not a simulated one | ✅ real case, see §3c |
| 13 | **New:** raw Slack `.html` attachment on macOS and iPhone, then browser handoff on the phone | ⚠️ measured once — macOS opened the page, iPhone preview showed source, installed browser rendered the saved file; see row 27 |

## 12. Where this leaves the build pipeline

None of §3b's pattern or §5's touch-target/explicit-width rules should be hand-copied
into each new dashboard by hand. They belong as
build-time helpers in `tools/build_dashboard.py` / `build_cube_dashboard.py` — assembled
into the output automatically, the same way `docs/09` proposes for the colour tokens. Not
done by this document, which only establishes the source pattern and where it already
lives.

## Open items this document does not resolve

- [ ] Confirm or correct the Edge/Chrome browser assumption (§3a) against actual IT
      policy — carried over unchanged from the original requirements, still not done.
- [ ] Run a real cross-browser comparison (Edge, Chrome, Safari, Firefox) on mobile —
      `browser-capability-probe.py` only drives Chromium today.
- [ ] The still-open sharing-path combinations: Android; Gmail and the Outlook mobile app specifically; a real
      e-mail attachment rather than a link; named-recipient sharing scope; mobile
      browsers distinguished from each other; the §3b warning pattern verified against a
      real blocked-JS case.
- [ ] Wire the §3b JavaScript-resilience pattern, and the §5 touch-target/explicit-width
      checks, into the actual build tooling — proven only in `examples/07` so far, not
      shipped in either production template. **Now blocked on a prior decision, not just
      wiring:** `examples/13`, `examples/14` and `examples/15` proved a second, stronger
      pattern — not requiring JavaScript at all, rather than only degrading gracefully
      when it fails — for both navigation and (with per-chart-type caveats) charts, plus
      a working print/export button (§8) tested alongside a JS-requiring comparison page.
      Applies to `tools/build_dashboard.py`'s BUNDLED output specifically (see §1's
      scope note) — `build_cube_dashboard.py`'s cubes are also BUNDLED and in scope, but
      nothing about PAIRED output changes here. Whether the build tooling should offer the
      §3b pattern, the no-JS pattern, or a per-dashboard choice between the two, needs
      deciding before this item is wired in, not after.
- [ ] Reconcile `lang="nb"` vs `lang="no"` between the two templates (§1/§9).
- [ ] Add `@media print` rules to `cube-dashboard.html` to match `single-file-dashboard.html`
      (§8), or decide the gap is acceptable. §8 now has a tested reference pattern to copy
      from (`examples/15-chart-library-comparison-poc/`), not just a stated preference.
