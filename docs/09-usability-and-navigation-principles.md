# Usability, navigation and colour — where the brand and the browser agree, and where they don't

**Status:** proposal, written for review. Nothing here is wired into `templates/` yet,
except two cheap, low-risk items (`:focus-visible` and `prefers-reduced-motion` in both
real templates, see §1 and §5) and the two settled rules below (§3 colour, §1
navigation). It exists to make the reasoning
behind `tools/tokens/*` and `examples/05-theme-toggle-demo/` checkable, instead of leaving
those files to speak for themselves.

**Field evidence (a review of an unrelated external dashboard, built with no knowledge of
this repo):** that file independently implements a tab-based nav (`role="tablist"`), `:focus-visible`,
`prefers-reduced-motion`, and one-colour-one-meaning status signalling — including landing
on a red close to Ember (`#C9372C`) for its negative status colour as
`docs/09` §3 recommends. That does not make any of this a standard by itself,
but it is evidence these are cheap, low-risk patterns that work in practice, not just on
paper — useful weight when deciding what to prioritise wiring in.

A companion to `docs/08-generic-artifact-model.md`, but scoped to a different
question: not *how a file is delivered*, but *how readable and navigable it is once
someone has it open*. Written after auditing the actual templates against the two things
that are authoritative for this work — the active brand plugin's palette and the
core status tokens — and against external,
industry-standard usability sources (WCAG 2.2, Nielsen Norman Group, the W3C ARIA APG).

---

## 1. What the templates do today (measured, not assumed)

- **Navigation:** none of the real templates (`single-file-dashboard.html`,
  `cube-dashboard.html`) have a `<nav>` element yet. The topbar-with-toggle pattern
  (`examples/04-generic-standalone-demo/`, `examples/07-topbar-pattern-demo/`) is **an
  optional navigation pattern**: a dashboard MAY use it in place of a fixed sidebar. It is not required, and not yet
  ported into the two production templates; that remains a separate, larger
  implementation step (template redesign, not a CSS-only change), tracked in
  `ROADMAP.md` rather than done here.
- **Colour:** a full brand token set is defined in `:root`, but only
  two of its ~13 colours are ever actually used — Blue (header accent) and Navy
  (header background).
- **Responsiveness:** `<meta name="viewport">` is present; layout uses CSS Grid with
  `auto-fit`/`minmax` (fluid, no fixed breakpoints).
- **Accessibility:** real `<label for>` and `<select>` elements on filters (good); sortable
  table headers are plain `<th>` with a click handler and no keyboard path; chart hover
  tooltips fire only on `mousemove`, no keyboard or `aria-label` equivalent. **Corrected:**
  `single-file-dashboard.html`'s `renderKpis()` does not currently render any
  delta at all — the earlier claim that "positive/negative KPI deltas are signalled by
  colour alone" described dead CSS (`.kpi .delta.up/.down`), not a live gap. That CSS has
  been updated to the icon+text-ready shape already proven in
  `examples/05-theme-toggle-demo/`, so if a real delta is wired in later, it inherits the
  right pattern rather than a colour-only one. `:focus-visible` and
  `prefers-reduced-motion` are now present in both real templates.
- **Verification:** `tools/verify_dashboard.py` checks portability (self-contained, size,
  renders, provenance) — none of its 7 checks look at usability or accessibility.

## 2. The colour palette is out of date, independent of anything else in this document

Brands refresh their palettes, and a template that hardcodes last year's colours keeps
shipping them. The fix is structural: brand colours live in a plugin, never in core. The
example plugin (fictional Eksempel AS) carries these values:

| Role | Colour | Hex |
|---|---|---|
| Primary / header | Blue | `#2F5D9E` |
| Dark background | Navy | `#1B2A4A` |
| Darkest background | Night | `#101828` |
| Accent (used sparingly only — never a fill or body text colour) | Plum | `#6B3FA0` |
| Text on dark background | Cream | `#FFF8EE` |
| Body text | Black | `#000000` |

This table is `plugins/eksempel/tokens/palette.css` in CSS-variable form. It supersedes
the colour block currently hardcoded into both templates. **Not applied
to the templates yet** — that is a separate, later step once this doc and the tokens are
reviewed.

## 3. Positive/negative colour: brand-marketing palette and UI-functional palette are not the same thing

A brand palette is chosen to look good, not to be read. It often has no usable red, and
its accent may be reserved for decoration only. That is workable for a slide background;
it is not workable for a KPI delta that a reader needs to parse at a glance across a table
of rows.

So status colour is a **separate, core-owned token set** (`tools/tokens/status-semantic.css`),
independent of whichever plugin supplies the brand:

| Use | Colour | Hex | Contrast vs. white | WCAG AA text (needs 4.5:1) |
|---|---|---|---|---|
| Negative | Ember | `#C9372C` | 5.16:1 | Pass |
| Negative, background tint | Ember 8% | `#fbeded` | — (background only) | — |
| Positive | Moss | `#1F7A5C` | 5.25:1 | Pass |
| Positive, background tint | Moss 12%/25% | `#eaf5f0` / `#d7ece3` | — (background only) | — |

For comparison, the example plugin's warm accents fail this job outright: Amber
measures 2.47:1 against white (fails even the 3:1 large-text/icon minimum), Flame
2.84:1 (also fails the 3:1 icon minimum), so neither brand accent is usable here.
Their values live in `plugins/eksempel/tokens/palette.css`.

**Default status pair: Ember / Moss** (WCAG AA, see the contrast table above). An
unrelated external dashboard independently chose a near-identical red for its own
negative status signal. **The default is not exclusive:** it names one confirmed-good
combination, not the only acceptable one. A project that already has its own tested,
WCAG-AA-passing negative/positive pair may use that instead. Brand rules written for
marketing material do not govern a dashboard's functional status colour, which is a
UX/functional concern. This is `tools/tokens/status-semantic.css`.

## 4. Light default, dark as an option — not yet a live toggle

Light stays the default: a dashboard is read repeatedly and at length, which is exactly
the case Nielsen Norman Group and general dashboard-UX guidance argue for a neutral,
low-chroma background with colour reserved for data — not the bold, colour-dominant
background pattern typical of brand slide templates.

A dark variant is worth having as an *option*, because the example brand already has a
dark aesthetic (Night/Navy background, Cream text) rather than needing to invent one. `tools/tokens/theme-dark.css` captures it.

**Decision this round: the toggle is not going into the production templates yet.** It
will exist and be visibly testable in `examples/05-theme-toggle-demo/` only, so it can be
looked at before anyone decides it belongs in a real dashboard. Two things need checking
before it could graduate: the contrast numbers in §3 were measured against a *white*
background only and must be re-measured against Navy/Night; and whether `localStorage`
actually persists per file (not just per browser) under `file://` is unverified — this
project's own rule is to measure the tenant rather than trust the docs, and that applies
here too, not just to SharePoint headers.

## 5. Navigation and layout: hand-built patterns, cited to WCAG and the ARIA APG

Design principle 1 in `00-vision.md` ("the artefact is a file... no CDN, no server") rules
out importing a component library, however good its components are. The resolution is to
hand-build the *pattern*: keyboard-reachable menu items, a visible current-page state, a
skip-to-content link, in plain HTML/CSS/JS.

Two layout rules apply cleanly, and the templates already follow them:
- **Fluid layout over fixed breakpoints**, so content reflows in the same order a screen
  reader reads it (WCAG 2.2, 1.4.10 Reflow and 1.3.2 Meaningful Sequence). The templates'
  `auto-fit`/`minmax` grid already does this.
- **8px spacing grid** — the templates' `--sp-1: 0.5rem` etc. already resolve to multiples
  of 8px at the default root font size.

Sources used for the gaps identified in §1:
- **WCAG 2.2, 1.4.1 (Use of Color):** a signal conveyed by colour must also be conveyed by
  at least one other means (shape, icon, text) — applies directly to the KPI delta gap.
- **WCAG 2.2, 2.1.1 (Keyboard):** anything reachable by mouse must be reachable by
  keyboard — applies to the sortable table headers and the chart tooltips.
- **WCAG 2.2, 2.4.1 (Bypass Blocks):** a skip-to-content link lets a keyboard user pass
  the navigation.
- **W3C ARIA Authoring Practices Guide, Sortable Table pattern:** a sortable column header
  should be a real `<button>` inside the `<th>`, with
  `aria-sort="ascending"/"descending"/"none"` on the `<th>` itself.
- **W3C ARIA Authoring Practices Guide, Disclosure Navigation Menu pattern:** a topbar
  needs a visible current-page indicator (`aria-current="page"`) and a button with
  `aria-expanded` for its collapse behaviour on narrow screens, not just "hidden until
  clicked."

## 6. Where this leaves the build pipeline

None of the above should end up hand-copied into each new dashboard the way the current
hardcoded colour block is. The proposal is a small, versioned set of build-time-only
files under `tools/tokens/`, read and inlined by the builder scripts (`tools/build_*.py`)
into the final single-file output. The shipped `.html` stays exactly as dependency-free as
it is today — nothing here is fetched by the file at open-time, only assembled into it
when it's built. `plugins/eksempel/tokens/palette.css` and `status-semantic.css` get revised in one place
when the brand or the WCAG numbers change; every dashboard built after that revision
picks it up automatically the next time it's rebuilt.

## Open items this document does not resolve

- [x] Default status colour: Ember / Moss, not exclusively (§3). Other
      WCAG-AA-passing pairs may be used without reopening this.
- [ ] Re-measure contrast for status colours and chart colours against the dark theme
      background once `theme-dark.css` has an actual reader to test against.
- [ ] Measure whether `localStorage` persists per-file (or per-browser, or not at all)
      under `file://`, and log the result in `docs/01-tenant-constraints.md` alongside the
      other measured rows, before any theme-toggle graduates out of the demo.
- [ ] Decide, once `examples/05-theme-toggle-demo/` has been looked at, whether a
      light/dark toggle belongs in the production templates at all.
- [ ] Wire `tools/tokens/*` into `tools/build_dashboard.py` and `tools/build_cube_dashboard.py`
      — not done by this document, which only establishes the source-of-truth files.
