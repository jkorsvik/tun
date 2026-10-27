# Usability, navigation and colour — where the brand and the browser agree, and where they don't

**Reader:** user — you want an artefact out of your own data and do not intend to change the toolkit.

**Status:** proposal, written for review. Nothing here is wired into `templates/` yet,
except the two cheap, low-risk items landed 2026-09-11 directly (`:focus-visible` and
`prefers-reduced-motion` in both real templates — see §1 and §5) and the two decisions
below (§3 colour, §1 navigation) resolved the same day. It exists to make the reasoning
behind `tools/tokens/*` and `examples/05-theme-toggle-demo/` checkable, instead of leaving
those files to speak for themselves.

**Field evidence, 2026-09-11 (`html-sammenligning` review of an external, unrelated
dashboard — `søknadstrakt-dashboard.html`, built with no knowledge of this repo):**
that file independently implements a tab-based nav (`role="tablist"`), `:focus-visible`,
`prefers-reduced-motion`, and one-colour-one-meaning status signalling — including landing
on the exact same Fire Red (`#dc2a2a`) for its negative status colour as `docs/09` §3
recommends. That does not make any of this Eksempel AS-approved by itself, but it is evidence
these are cheap, low-risk patterns that work in practice, not just on paper — useful
weight when deciding what to prioritise wiring in.

Follow-up to issue #4 (`docs/08-generic-artifact-model.md`), but scoped to a different
question: not *how a file is delivered*, but *how readable and navigable it is once
someone has it open*. Written after auditing the actual templates against the two things
that already exist and are authoritative for Eksempel AS work — the design system design system, and
the `tun-presentation` skill's 2026 palette — and against external, non-Eksempel AS usability
sources (WCAG 2.2, Nielsen Norman Group, the W3C ARIA APG).

---

## 1. What the templates do today (measured, not assumed)

- **Navigation:** none of the real templates (`single-file-dashboard.html`,
  `cube-dashboard.html`) have a `<nav>` element yet. **Decided 2026-09-11:** the
  topbar-with-toggle pattern (`examples/04-generic-standalone-demo/`,
  `examples/07-topbar-pattern-demo/`) is **approved as an optional navigation pattern** —
  a dashboard MAY use it in place of a fixed sidebar. It is not required, and not yet
  ported into the two production templates; that remains a separate, larger
  implementation step (template redesign, not a CSS-only change), tracked in
  `ROADMAP.md` rather than done here.
- **Colour:** the full the design system "Profile" token set is defined in `:root`, but only two of
  its ~13 colours are ever actually used — blue (header accent) and purple
  (header background).
- **Responsiveness:** `<meta name="viewport">` is present; layout uses CSS Grid with
  `auto-fit`/`minmax` (fluid, no fixed breakpoints).
- **Accessibility:** real `<label for>` and `<select>` elements on filters (good);
  sortable table headers **fixed 2026-10-24**: each header is a real `<button>` inside
  its `<th>`, `aria-sort` sits on the `<th>` (`ascending`/`descending`/`none`), the caret
  is `aria-hidden`, and the button is a 44 px target; chart hover tooltips still fire
  only on `mousemove`, with no keyboard or `aria-label` equivalent. **Corrected
  2026-09-11:** `single-file-dashboard.html`'s `renderKpis()` does not currently render any
  delta at all — the earlier claim that "positive/negative KPI deltas are signalled by
  colour alone" described dead CSS (`.kpi .delta.up/.down`), not a live gap. That CSS has
  been updated to the icon+text-ready shape already proven in
  `examples/05-theme-toggle-demo/`, so if a real delta is wired in later, it inherits the
  right pattern rather than a colour-only one. `:focus-visible` and
  `prefers-reduced-motion` are now present in both real templates (added 2026-09-11).
- **Verification:** `tools/verify_dashboard.py` checks portability (self-contained, size,
  renders, provenance) — none of its 7 checks look at usability or accessibility.

## 2. The colour palette is out of date, independent of anything else in this document

`tun-presentation`'s SKILL.md documents a 2026 brand refresh, confirmed by en fagfelle on
2026-08-26, that retires the Teal/Yellow/Orange-era "Profile" palette already baked into
these templates. The design system pages the templates cite are themselves now marked
"(deprecated)". Current values:

| Role | Colour | Hex |
|---|---|---|
| Primary / header | blue | `#006C6C` |
| Dark background | purple | `#003842` |
| Darkest background | dark blue | `#0F1E26` |
| Accent (used sparingly only — never a fill or body text colour) | Purple | `#7733FF` |
| Text on dark background | Light Yellow | `#FFFFE8` |
| Body text | Black | `#000000` |

This table is `plugins/<your-brand>/tokens/palette.css` in CSS-variable form. It supersedes the
`--color-blue` etc. block currently hardcoded into both templates. **Not applied to
the templates yet** — that is a separate, later step once this doc and the tokens are
reviewed.

## 3. Positive/negative colour: brand-marketing palette and UI-functional palette are not the same thing

The 2026 refresh removed the only colours the old palette used for warning/negative
signalling (orange, orange), and its one surviving accent (Purple) is
explicitly reserved for "microscopic decoration only — never a fill, never body text."
That is workable for a slide background; it is not workable for a KPI delta that a reader
needs to parse at a glance across a table of rows.

the design system carries a **separate token category, "UX/functional,"** that was not touched by
the 2026 marketing refresh — because it is not a marketing palette, it is the set already
used inside the design system's own components for error/success states:

| Use | Colour | Hex | Contrast vs. white | WCAG AA text (needs 4.5:1) |
|---|---|---|---|---|
| Negative | Fire Red | `#dc2a2a` | 4.76:1 | Pass |
| Negative, background tint | Fire Red 8% | `#fdeeee` | — (background only) | — |
| Positive | Success Green | `#007b5e` | 5.26:1 | Pass |
| Positive, background tint | light blue 12%/25% | `#f4fbf9` / `#e9f8f4` | — (background only) | — |

For comparison, the 2026 marketing greens fail this job outright: purple `#00CC88`
measures 2.10:1 against white (fails even the 3:1 large-text/icon minimum), orange
`#E8912D` measures 3.22:1 (passes only for icons, not text).

**Decided 2026-09-11: Fire Red / Success Green are approved for dashboard status colour.**
Field evidence from `html-sammenligning`'s review of an unrelated external dashboard
— which independently chose the identical Fire Red (`#dc2a2a`) for its own negative status
signal — supports these as a solid, WCAG-AA-passing default. **This approval is not
exclusive:** it names one confirmed-good combination, not the only acceptable one. A
different status-colour pair may also be approved later (e.g. if a project already has
its own tested, WCAG-AA-passing negative/positive pair) — this decision does not need to
be revisited to allow that, only extended. `tun-presentation`'s "not brand-sanctioned, ask
[the design owner]" caveat was written for marketing/presentation material; it does not
block a dashboard's functional status colour, which is a UX/functional concern, not a
brand-marketing one. This is `tools/tokens/status-semantic.css` (comment updated to
match).

## 4. Light default, dark as a system route — graduated out of the demo

Light stays the default: a dashboard is read repeatedly and at length, which is exactly
the case Nielsen Norman Group and general dashboard-UX guidance argue for a neutral,
low-chroma background with colour reserved for data — not the bold, colour-dominant
background pattern `tun-presentation` documents for slides.

A dark variant is worth having as an *option*, because Eksempel AS already has one real designed
dark aesthetic (Ocean/Emerald background, Light Yellow text, from the presentation
pattern) rather than needing to invent one. `tools/tokens/theme-dark.css` captures it.

**Decision that round: no manual toggle in the production templates.** The work below
changed what is shipped, but not that decision: a reader gets the system's setting with no
control to operate and nothing to persist. A visible toggle stays a demo.

Two things had to be checked before it could graduate.

**Checked 2026-10-25 — contrast.** `tools/check_token_contrast.py` now measures every
declared token pair per theme against WCAG 2.2 AA, and `tests/test_token_contrast.py`
proves it can fail. The first run found five real defects, all in the dark theme:

| pair | was | now |
|---|---|---|
| `--brand` as link on the dark background | 1.43:1 | 6.54:1 |
| `--ok` on the dark background | 2.35:1 | 6.37:1 |
| `--bad` on the dark background | 2.59:1 | 4.89:1 |
| `--ink` on the `--ok-bg` chip | 1.04:1 | 12.54:1 |
| `--ink` on the `--bad-bg` chip | 1.04:1 | 12.62:1 |

The two chip rows are the ones worth remembering. `theme-dark.css` had chosen light
near-white chips on the argument that a light chip on a dark page is conventional — true,
but only when the chip's *label* is dark. The templates set the label to `var(--ink)`,
which is light in that theme, so the labels measured 1.04:1: invisible on screen while
the file's comment claimed the combination was checked. The chips are now dark tints of
the same status hue.

`--brand` needed a structural fix rather than a new hex. A primary colour chosen to read
on white cannot also read on a dark surface, so core now requires a ninth palette slot,
`--palette-primary-on-dark` (docs/22). The neutral palette maps it to a lightened slate,
and each brand plugin supplies its own.

Two failures remain, both brand facts rather than core bugs, and both recorded in
`tests/test_token_contrast.py` as a ratchet so neither can change unnoticed: the brand
plugin's only sanctioned fill accent (purple) is 2.10:1 on white, which is the open
chart-palette work in docs/10; and Fire Red is 4.44:1 on Tún's paper background, 0.06
under the text minimum, while passing on white.

**The system route, 2026-10-25.** The second blocker was about a *manual toggle*, and
the answer is to not need one. `tun_tokens.auto_dark_css()` derives a
`@media (prefers-color-scheme: dark)` block from `theme-dark.css` and applies it to
`:root:not([data-theme])`, so a reader whose operating system asks for dark gets it with
no script, no storage and nothing to persist, and a reader who has chosen a theme keeps
it. Example 05 is built with it.

The block is generated rather than written twice. CSS has no way to share one
declaration block between a media query and a selector, so the values must appear twice
in a shipped file; two hand-maintained copies is how a theme drifts. `auto_dark_css()`
derives the second copy from the first, and `tests/test_system_dark.py` asserts the
declarations are identical, that the media query is what gates the change (a mutation
that removes it forces a light system dark), and that an explicit choice wins in a real
browser.

`localStorage` under `file://` therefore stays unmeasured, and it now only matters to the
demo's button: a stored choice is a convenience on top of a route that already works
without one.

**The route was shipped dead, 2026-10-25.** It was carried by the page and disarmed by it.
Example 05's script ran `saved = localStorage.getItem(KEY) || 'light'; apply(saved)` on
every load, so `<html>` always got `data-theme="light"` and the media query, which is
scoped to `:root:not([data-theme])`, never applied. A reader whose system is dark got a
white page, and this page said the opposite. Nothing caught it: `verify_a11y` measured
every artefact in the light scheme only, and the demo's own suite asserted that a *chosen*
theme wins, which it did.

The script now sets the attribute only when the reader has actually chosen, and reads the
effective theme from the system otherwise, so the button's label and `aria-pressed` follow
the operating system until someone touches them. `tests/test_dark_scheme_gate.py` is the
gate that found it and keeps it: every page carrying the media query is either measured in
the dark scheme it follows (`verify_a11y --dark`) or, when it deliberately disarms the
block with its own toggle, measured through that toggle (`verify_a11y --theme dark`) with
the reason recorded in the suite. A page that disarms the block without a reason fails.

**Graduated out of the demo, 2026-10-25.** Example 05 was the only artefact that followed
the system setting, and that made the gate above read green over a mostly white product.
The gate measured the pages that *happened* to carry the media query, which answers "is
this page's dark block correct" and never "does this page have one". The process diagram
had none: `tools/build_process_diagram.py` hard-listed `theme-light.css`, so every reader
whose operating system is dark got a white page at midnight, and every gate was green.

Three things changed, and the third is the one that generalises:

1. The builder loads the theme through `load_token_css(auto_dark=True)`. A builder that
   inlines tokens with `auto_dark=True` gets the system route with no further work.
2. A lane role is *not* a token. `templates/process-diagram.html` maps six roles onto
   slots, and in dark three of those slots measure 1.00 to 1.79:1, which draws a lane
   colour as nothing. The template now carries its own dark ramp, and the six pairs that
   measure it are rows in `tools/check_token_contrast.py` rather than a claim in a comment.
   `tests/test_process_diagram.py` fails if the painting list and the measuring list ever
   disagree, and a mutation control proves that comparison can fail.
3. `tests/test_dark_scheme_gate.py` holds `REQUIRED_FOLLOWERS`. A builder on that list may
   not stop following the system setting, and cannot leave the scan. The list only grows;
   adding an artefact to it is the moment its dark surface is measured.

**The folder index, same day.** `tools/build_index.py` did not inline tokens: it carried
nine hand-picked hexes in its template, so it had drifted from the seam in three values
(`--panel`, `--muted`, `--line`) and could not follow the system setting. It now loads them
with `auto_dark=True` and the template holds none. Two of its slots had to be remapped in
dark, and both were invisible there before the change was made: the header band filled with
`--brand-dark` and wrote `--on-brand` on it, which in dark are two darks (1.39:1), and card
links used `--brand-dark` on a `--panel` card, which is the same colour twice (1.00:1).
Both are now pairs the theme actually defines.

**The register, same day, and the seam grew.** `templates/register.html` needed a soft brand tint
for its group band, and a tint needs text chosen for it, so the two theme files gained
`--brand-soft`, `--on-brand-soft` and `--rule` as declared roles. That is the seam doing its
job: a second consumer is the point at which a template-local hex becomes a role. The band
had been lettered with `--brand-dark`, which in dark is the darkest surface in the theme,
so the band read dark on dark and nothing measured it. Both themes' values are now rows in
`tools/check_token_contrast.py`, 10.57:1 and 11.24:1 on the neutral palette.

**The comparison, same day.** Two more seam facts came out of it. Fire Red as *text* on the token panel is 4.49:1, under AA by a hundredth, which passed only while the panel was pure white; the seam gained `--bad-ink`, the same hue one step darker at 4.82:1. And the review layer's own button painted a raw white behind the theme's light ink, 1.09:1 in dark, so it now uses `--panel`: one fix for every artefact that carries that layer.

**The timeline, same day.** A drawing shows the seam's limit more sharply than a list does: a bar fill is a mark on a card, not text, and the palette's primary is chosen to sit on white (1.43:1 on a dark panel), so every row would have been blank. The template re-points `--bar` to `--palette-accent-light` in dark and its 14 px group headings to `--brand`. Two roles it declared and painted nowhere went with the change.

**The survey, same day, and a lesson about where a value lives.** Its five distribution colours were painted by a string built at runtime, so reading the template said nobody used them. They are now `--cat-1` to `--cat-5`, declared in the two theme files rather than in a file of their own: `auto_dark_css()` derives the media query from the dark theme, so a role declared elsewhere reaches no reader whose system is dark. The five are measured as ten rows in `tools/check_token_contrast.py`; two light values were under the 3:1 floor and are one step deeper.

**Two surfaces stay light, on purpose, and now say so.** `tests/test_dark_scheme_gate.py` gained a `LIGHT_BY_DESIGN` list beside `REQUIRED_FOLLOWERS`, and every entry is checked twice: the file exists, and it really carries no media query. An entry that quietly gains one is a comment that has become a lie. The two:

- `examples/37-printable-onepager/ett-ark.html` is one A4 sheet, read on paper or as a PDF, and its `@media print` forces white. A dark screen preview would preview something that cannot be printed.
- `examples/18-portable-slide-deck/maalebandet.html` and its overlay sibling are projected decks whose own palette **is** the design: a dark teal stage, a paper slide, and slides the author marked `.slide.dark` to invert on purpose. Following the reader's setting would override that choice on every slide at once.

**The cube, same day, and the one surface no token reaches.** A `button` or a `select` with no colour of its own renders the browser's `CanvasText`, which stays black whatever the page does: 1.22:1 on the dark panel, and invisible. A form control has to state its colour. The cube also painted a raw white on four card surfaces, and used `#fff` as the line chart's marker fill, which is `--panel` now so the marker still reads as a gap in the line.

**The flagship, last because it was largest.** Forty hand-written the design system values became the inlined seam, and ten palette names were used out of forty declared: the other thirty were carried into every build and read by nothing. Three defects surfaced. A KPI figure was lettered `--brand-dark` on a `--panel` card, and in dark `--brand-dark` *is* the panel: 1.00:1, four invisible headline numbers. A bar's hover darkened to `--brand-dark`, so the bar vanished under the pointer; it takes `--series-2`, a second colour for the same shape that differs in both themes. And the delta chips needed a wash to letter red on, distinct from `--bad-bg`, which is a badge fill, so the seam gained `--bad-soft`.

**Measured 2026-10-26, and the rollout is not complete.** Eight templates carry `{{TOKEN_CSS}}` and follow the system setting: `process-diagram`, `single-file-dashboard`, `index`, `register`, `compare-dashboard`, `timeline`, `cube-dashboard`, `survey-dashboard`. Two more carry none and never will, for the reasons above: `onepager`, which is read on paper, and `portable-slide-deck`, whose palette is the design. The three `_`-prefixed partials are fragments spliced into pages that already carry the seam, so they are not counted; the test skips them by name.

The nine that remain are the charts built in the days around the rollout — `cohort`, `composition`, `distribution`, `funnel`, `heatmap`, `rank-change`, `scorecard`, `smallmultiples`, `waterfall` — each still carrying nine to fourteen colour variables of its own, so a reader whose system is dark gets a white page. They are named in `SEAM_PENDING` in `tests/test_dark_scheme_gate.py`, which enumerates every template and refuses one that is neither seam-carrying nor recorded with a reason. Delete an entry as its template gains the seam; the gate fails if an entry is stale, so the list is a measurement and can only shrink.

That list exists because this section claimed the rollout was complete when it was not. The claim came from the memory of what had merged, and no gate had ever counted. Each of the nine inlines its own aliases rather than going through `tun_tokens`, so each needs its own mapping onto these tokens before it can be added to `REQUIRED_FOLLOWERS`.

## 5. Navigation and layout: where the design system's real components can't be used, and where its rules still apply

the design system ships accessible navigation components — `Menu`, `Breadcrumb`, `SkipContent` — but
they are React components distributed via the `the design system package` package. Design principle 1
in `00-vision.md` ("the artefact is a file... no CDN, no server") makes importing that
package a non-starter for this tool, independent of how good the component is. The
resolution is to hand-build the *pattern* the design system's components imply — keyboard-reachable
menu items, a visible current-page state, a skip-to-content link — in plain HTML/CSS/JS,
not to import the library.

Two the design system rules apply cleanly with no such conflict, and the templates already happen to
follow them without ever citing them:
- **Fluid layout over fixed breakpoints** — the design system's own designer accessibility checklist
  recommends this specifically so content reflows in the same order a screen reader would
  read it. The templates' `auto-fit`/`minmax` grid already does this.
- **8px spacing grid** — the templates' `--sp-1: 0.5rem` etc. already resolve to multiples
  of 8px at the default root font size.

External, non-Eksempel AS sources used for the gaps identified in §1 that Eksempel AS's own material
doesn't cover:
- **WCAG 2.2, 1.4.1 (Use of Color):** a signal conveyed by colour must also be conveyed by
  at least one other means (shape, icon, text) — applies directly to the KPI delta gap.
- **WCAG 2.2, 2.1.1 (Keyboard):** anything reachable by mouse must be reachable by
  keyboard — met for the sortable table headers (2026-10-24, above); still open for the
  chart tooltips.
- **W3C ARIA Authoring Practices Guide, Sortable Table pattern; GOV.UK/MOJ Design System,
  Sortable Table component:** a sortable column header should be a real `<button>` inside
  the `<th>`, with `aria-sort="ascending"/"descending"/"none"` on the `<th>` itself.
- **Nielsen Norman Group, menu-design and mobile-navigation guidance:** a topbar needs a
  visible current-page indicator and a distinct, tested collapse behaviour on narrow
  screens — not just "hidden until clicked."

## 5b. Keyboard shortcuts: evaluated, not adopted

Evaluated on 2026-09-19. The approach that holds across platforms: do not look for one
physical key combination that is the same everywhere. Define one *semantic* shortcut per
action and map it to each platform's own convention. The primary modifier is `Ctrl` on
Windows, Linux and Android, and `⌘ Command` on macOS and iPadOS. This matches what VS Code,
Microsoft 365, Google Docs, GNOME and Android already do, so developers, data users and
Office users all meet keys they know. A draft table covered 25 common actions (copy, cut,
paste, undo, redo, save, find, replace, navigation and so on).

**Status: not adopted.** Rows 24 and 26 in `docs/01` came first: navigation that breaks in
the SharePoint preview matters more than shortcuts. Before a shortcut standard can be wired
in, someone must measure which key events the SharePoint preview and the mobile previews
pass through to the page and which they keep for themselves. Until then, the templates use
navigation keys in the slide deck (arrows, Page Up/Down, space, Home, End, and `f` for
fullscreen) and the browser's own Tab order.

## 6. Where this leaves the build pipeline

None of the above should end up hand-copied into each new dashboard the way the current
`--color-blue` block is. The proposal is a small, versioned set of build-time-only
files under `tools/tokens/`, read and inlined by the builder scripts (`tools/build_*.py`)
into the final single-file output. The shipped `.html` stays exactly as dependency-free as
it is today — nothing here is fetched by the file at open-time, only assembled into it
when it's built. `eksempel-brand-2026.css` and `status-semantic.css` get revised in one place
when the brand or the WCAG numbers change; every dashboard built after that revision
picks it up automatically the next time it's rebuilt.

## Open items this document does not resolve

- [x] Confirm with a brand owner whether Fire Red / Success Green are acceptable for
      dashboard status colour — **decided 2026-09-11: approved, not exclusively** (§3).
      Other WCAG-AA-passing combinations may also be approved later without reopening
      this decision.
- [ ] Re-measure contrast for status colours and chart colours against the dark theme
      background once `theme-dark.css` has an actual reader to test against.
- [ ] Measure whether `localStorage` persists per-file (or per-browser, or not at all)
      under `file://`, and log the result in `docs/01-tenant-constraints.md` alongside the
      other measured rows, before any theme-toggle graduates out of the demo.
- [ ] Decide, once `examples/05-theme-toggle-demo/` has been looked at, whether a
      light/dark toggle belongs in the production templates at all.
- [ ] Wire `tools/tokens/*` into `tools/build_dashboard.py` and `tools/build_cube_dashboard.py`
      — not done by this document, which only establishes the source-of-truth files.

The palettes themselves, categorical, sequential and diverging, light and dark: [chart colour palettes](10-chart-colour-palettes.md).
