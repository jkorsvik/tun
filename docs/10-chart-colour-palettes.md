# Chart colour palettes — categorical, sequential, diverging, and light/dark

**Reader:** contributor — you are changing the toolkit, and need the constraint or the convention behind it.

**Status:** proposal, written for review. Nothing here is wired into `templates/` yet,
and — measured, not assumed — **neither is Chart.js**: `templates/single-file-dashboard.html`
and `templates/cube-dashboard.html` render their bar/line charts with hand-rolled inline
`<svg>` + vanilla JS (`barChart()`, `lineChart()` in the template), not Chart.js. This
document and its demo are scoped to the question "if Chart.js is added, what should its
colour rules be" — they do not decide *whether* Chart.js replaces or supplements the SVG
charts. That is a separate, larger decision (bundle size: Chart.js UMD is ~205 KB, which
is small against the Tier 1 budget in `tools/verify_dashboard.py` but not free) and is out
of scope here.

Follow-up to `docs/09-usability-and-navigation-principles.md`, same scoping split as that
doc drew for status colour vs. brand colour: this covers the palette used for **chart
series** — the colours mapped to categories/values inside a chart — which `docs/09` did
not cover (it covers KPI delta colour via `status-semantic.css`, and page chrome via
`eksempel-brand-2026.css`). Those two files are unaffected by anything below.

---

## 1. Rule set — v0

| # | Rule |
|---|---|
| **A** | Pick the palette **family** from the data's encoding, not from the chart type: categorical/unordered data → qualitative palette; continuous, one direction → sequential; signed deviation from a baseline → diverging. The chart type changes how strict the requirement is (§2), not which family applies. |
| **B** | Maximum colours per chart follows chart type, not a single fixed number — see §2, column "safe max". Past the limit: group into "other", don't add another hue. |
| **C** | **No swatch is reused unmodified between a light and a dark background.** Same principle `theme-dark.css` already applies to status chips (same token name, different measured value) — every series colour needs a light-mode value and a dark-mode value, each measured against the background it will actually sit on, not derived by inverting lightness. |
| **D** | Wherever colour is the **only** channel identifying a data point — pie/doughnut/polar-area segments, stacked-area bands — pair it with a redundant channel: a contrasting stroke around the segment, and a direct data label rather than colour+legend alone (WCAG 2.2, 1.4.1, *Use of Color*). Wherever marks are drawn individually — lines, scatter points — pair colour with a line-dash pattern or point shape. |
| **E** | Contrast target for the mark itself (bar fill, line stroke, point, pie segment) against its background is **3:1** — WCAG 2.2, 1.4.11 (*Non-text Contrast*), not the 4.5:1 text minimum. 4.5:1 still applies to any text drawn on or over a chart (data labels, legend text, tooltip body). |
| **F** | Measure each candidate swatch against the backgrounds the file actually ships with — not a generic white/black. For this repo that means the light template background and `--tun-green` / `--eksempel-ocean` for dark, the same two tokens `theme-dark.css` already targets. Same "measure the tenant, not the doc" discipline the rest of this repo uses for SharePoint/OneDrive behaviour, applied to colour. |

## 2. Assessment per Chart.js chart type

| Chart type | Palette family | Safe max | Main risk | Light/dark note |
|---|---|---|---|---|
| Bar (grouped/stacked) | Qualitative | ~8 | Stacked: hue-to-category order must stay identical across every chart in the dashboard | A fixed-opacity border on every bar helps on both backgrounds — don't make the border semi-transparent |
| Line | Qualitative | ~6–8 | Past ~6 lines, colour alone stops being distinguishable even with a good palette — needs dash pattern or marker shape | The stroke should stay at full opacity regardless of theme; only an optional fill-under-line needs a per-theme alpha |
| Area (line + fill) | Qualitative for the fill; sequential if stacked bands encode magnitude | ~5–6 | Overlapping semi-transparent fills blend into colours outside the chosen palette — worse on a dark background, where the same alpha value produces a different blended colour than on light | Fill alpha must be measured per theme, not reused as one value for both |
| Pie / Doughnut | Qualitative, strictest case | ~6 | Colour is the **only** channel — the single worst case for colour-vision deficiency in this whole table | Always pair with a segment stroke and a direct label, never legend-plus-colour alone |
| Polar area | Qualitative | ~6 | Same as pie — angle is fixed per segment, only colour distinguishes | Same requirement as pie |
| Radar | Qualitative, low count | ~4 | Overlapping filled polygons — the same colour-blend problem as area, compounded | Default to stroke-only or a low fill alpha (~15–20%), not full fill, regardless of theme |
| Scatter | Qualitative + point shape as a second channel | ~6 | A point can be small enough to fail 3:1 even with a nominally safe colour — actual contrast depends on point size, not only the swatch | Always pair colour with `pointStyle` (circle/triangle/square/etc.) per category |
| Bubble | Qualitative for category; sequential only if colour *also* encodes a third value | ~6 | Using colour for magnitude and category at once is two encodings sharing one channel | If magnitude needs colour, switch that chart to a pure sequential palette — don't mix it with the categorical one |

## 3. Palette shortlist

All of the following are **published, colour-vision-deficiency-tested schemes** — none
invented here. Hex values are taken from the cited source, not re-derived.

| Family | Palette | Source | Note |
|---|---|---|---|
| Qualitative | Okabe–Ito (8) | Okabe & Ito, 2008 — the original colour-blind-safe qualitative set, widely adopted since | Includes black; substitute `#999999` where black would clash with dark-theme chrome |
| Qualitative | ColorBrewer Set2 (8) | colorbrewer2.org | Muted; the other qualitative default candidate |
| Qualitative | Tableau 10 | Tableau's 2016 default palette | **Caveat, not pre-cleared:** popular and widely used, but not fully deuteranopia-tested pair-by-pair the way Okabe–Ito and ColorBrewer are. Included in the demo as a reference point, not a recommended default. |
| Sequential | Viridis (8) | matplotlib reference implementation, evenly sampled | Colour-vision-deficiency tested, perceptually uniform |
| Sequential | Cividis (9) | Nuñez, Anderton & Renslow 2018 / matplotlib | Purpose-built for colour-vision deficiency — the strictest sequential option |
| Diverging | PRGn (7) | colorbrewer2.org | Purple–green, colour-blind safe |
| Diverging | PuOr (7) | colorbrewer2.org | Purple–orange, colour-blind safe — the alternative offered in the demo, since PRGn's green end can read close to the brand's own green chrome |

**Deliberately excluded:** any red–green diverging scheme (e.g. ColorBrewer RdYlGn). The
two anchor colours can each individually be fine in isolation, but a multi-step diverging
scale interpolates *through* the red-green boundary, which is exactly the failure mode for
the most common form of colour-vision deficiency (deuteranopia). This is a stricter reading
than `status-semantic.css`, which uses a fixed two-colour red/green pair (no interpolated
midpoints) for KPI deltas — that fixed-pair use case is not affected by this exclusion.

## 4. Where the palette values live for now

Not promoted to `tools/tokens/` yet. Doing so would imply Chart.js is the decided charting
approach for production templates, which — per the opening note — has not been decided.
The concrete hex values and the light/dark pairing logic live in
`examples/06-chart-palette-demo/build_chart_palette_demo.py`, generated the same way
`build_theme_toggle_demo.py` generates its demo: a throwaway artefact to look at, not a
production decision.

## 5. What the demo proves, and does not decide

`examples/06-chart-palette-demo/chart-palette-demo.html` — see that folder's own header
comment for the full provenance block. In scope:

- All eight chart types in §2 rendered from the same synthetic dataset, so a palette can be
  compared across chart types rather than judged on one favourable case.
- A palette switcher per family (qualitative / sequential / diverging) and a light/dark
  toggle, so both axes in §1 rule C can be exercised together.
- A **live-computed** contrast ratio next to every swatch, against the background actually
  on screen at that moment — rule E/F implemented as code, not asserted in prose. Numbers
  are computed via the WCAG relative-luminance formula at render time; nothing here is a
  claimed number that was not actually run.

Not in scope, and not decided by this demo existing:

- Whether Chart.js is adopted at all for `templates/*.html` (see opening note).
- Whether any specific palette becomes the repo default — the demo is for comparing
  candidates, not for picking a winner.
- Any change to `status-semantic.css` or `eksempel-brand-2026.css` — both are untouched.

## 6. Checked and ruled out: the `frontend-design` marketplace skill

Before writing this document, checked whether the marketplace skill `frontend-design`
(Anthropic-authored, not Eksempel AS) had any colour guidance that should feed into it. It does,
but for a different problem than this one: it asks for a palette described as "4–6 named
hex values" as part of a creative brainstorming pass, and it explicitly warns *against*
three cliché AI-generated palettes (cream/terracotta, near-black/neon accent, hairline-rule
broadsheet) in favour of deliberate visual distinctiveness per brief. No mention of
contrast, WCAG, or colour-vision deficiency anywhere in it.

More importantly, its own frontmatter says it is "NOT an official Eksempel AS tool... Best for
standalone visual exploration, not production Eksempel AS UI" — and its stated goal (take a
visible aesthetic risk, avoid looking reusable across briefs) points the opposite direction
from this document's goal (a measured, reusable, accessibility-first default). Not used as
a source anywhere above; noted here so the question doesn't get re-asked later.

## Open items this document does not resolve

- [ ] **Chart.js vs. the existing hand-rolled SVG charts in `templates/*.html` — not
      decided, not this document's job to decide. Needs vedlikeholderen's read/comment. Now
      four candidates on the table, not two** — issue #30 (`examples/13`, `14`, `15`, all
      merged) explored two more approaches beyond the original "Chart.js + JS" vs.
      "hand-rolled SVG + JS" framing this item started with:
      1. **Hand-rolled SVG/CSS with no JavaScript at all** — `examples/14-chart-emulation-nojs-poc/`,
         computed once at build time instead of in the browser, for twelve chart types
         (nine of them the same ones assessed in §2 above). See that example's README for
         the per-chart-type findings.
      2. **Matplotlib (Python, static SVG at build time)** — `examples/15-chart-library-comparison-poc/`
         put Chart.js, hand-rolled CSS/SVG, and Matplotlib side by side on identical data.
         Two concrete points worth carrying forward: Matplotlib already has Viridis/Cividis
         as a reference implementation (§3 above currently hand-copies those hex values),
         and its static-SVG output combines cleanly with the print/export pattern now
         referenced in `docs/11-responsiveness-and-browser-support.md` §8 — same
         `window.print()` approach, no extra JS library, no canvas-tainting issues.

      Neither is decided or recommended here — both are still unproven beyond
      bar/donut/pie/map; see #30's "Må testes videre" section for what's still open.
- [ ] Feeds into the item above, needs reconciling either way it lands: `AGENTS.md`
      rejected inlining the design system's ~150 KB base64 font as "too heavy" for every dashboard,
      yet `examples/06-chart-palette-demo/` vendors and inlines ~205 KB of Chart.js. Scope
      differs (one experimental demo vs. every production file), so it's not a direct
      contradiction today — but if Chart.js moves into `templates/*.html`, the "too heavy"
      argument from the font decision needs to be revisited on its merits, not bypassed by
      precedent.
- [ ] `bunfig.toml`'s comment ("There is NO JavaScript dependency in this repo today, and
      that is deliberate") is now imprecise regardless of how the item above lands: it
      describes the absence of a package-manager-controlled dependency (no `bun install`,
      no `node_modules`), not the absence of any JS in a shipped file — the vendored
      Chart.js file already contradicts a literal reading. Worth tightening the wording.
- [ ] If Chart.js is adopted, whether these palettes get promoted into `tools/tokens/` as
      `chart-series-light.css` / `chart-series-dark.css` following the pattern in
      `docs/09-usability-and-navigation-principles.md §6`.
- [ ] Real-device check of the demo's contrast numbers under an actual colour-vision
      deficiency simulator (e.g. browser DevTools' vision-deficiency emulation) — the
      contrast-ratio maths is verified, but ratio-passes-3:1 is necessary, not sufficient,
      for two categories to stay visually distinct under deuteranopia/protanopia/tritanopia.
- [ ] Whether Tableau 10 should be dropped from the shortlist entirely once someone has
      looked at it next to Okabe-Ito/Set2 in the demo, given the caveat in §3.
