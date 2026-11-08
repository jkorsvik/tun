# 35. Tún visual identity and style guide

**Reader:** contributor — you are changing a public Tún page and need the shared brand decisions.

Tún has one visual identity across [tun.community](https://tun.community), the Explorer and
public documentation. Layouts can differ because the pages do different jobs. The brand mark,
colour roles, typography and component language must not drift.

This is the public Tún identity, not an organisation's design system. Do not add an employer's
logo, brand colours or hosted assets. Every page keeps the self-contained guarantee.

## The idea

The dark forest surface is the place where the work gathers. The green tick is the completed
journey from source to useful file. Mint is the action colour on that surface. Warm off-white
is the reading surface below it.

The result should feel practical, calm and exact. Colour supports the content. It does not turn
a data artefact into a marketing campaign.

## Brand mark

The mark is a rounded square containing one ascending tick. Its SVG path is:

```text
M4 15 10 20 21 4
```

Use a 24 by 24 `viewBox`, a 3-unit stroke, round caps and a round join. The square is 2 units.
Keep the mark inline in the HTML. Do not fetch a logo file or add an image service.

- Use `--ink` for the mark on a light surface and `--on-night` on a dark surface.
- Put `Tún` beside the mark in the system font, at 700 weight or heavier.
- A product name such as `Explorer` can follow in small monospace capitals and `--mint`.
- Keep clear space of at least half the mark's width around it.
- Do not stretch, rotate, outline twice, add a shadow or place the tick over a busy picture.

## Palette

These are the measured brand values. Reuse them. Do not introduce a nearby hex for the same role.

| Token | Value | Use |
|---|---|---|
| `--deep` | `#030a07` | Deepest hero and navigation background |
| `--night` | `#07150f` | Dark brand surface |
| `--ink` | `#0d2b21` | Primary text on light, primary button fill |
| `--ink-soft` | `#28473c` | Secondary text on light |
| `--mint` | `#b4c6bb` | Subdued action, focus and active state on dark |
| `--accent` | `#3f8f3f` | Data strokes and decorative ticks on light, not small text |
| `--on-night` | `#effcf4` | Primary text on dark |
| `--sage` | `#c1d3c9` | Secondary text on dark |
| `--slate` | `#486155` | Borders and inactive strokes on dark |
| `--paper` | `#f7f7f5` | Reading surface |
| `--panel` | `#ffffff` | Cards and raised reading surfaces |
| `--line` | `#dfe3e0` | Borders on light |
| `--muted` | `#5d6b65` | Metadata on light |

Measured WCAG contrast pairs:

| Foreground on background | Ratio | Use |
|---|---:|---|
| `--on-night` on `--night` | 17.72:1 | Primary dark-surface text |
| `--sage` on `--night` | 11.96:1 | Secondary dark-surface text |
| `--mint` on `--night` | 10.45:1 | Links, active states and focus |
| `--ink` on `--mint` | 8.48:1 | Primary button text |
| `--ink` on `--paper` | 14.14:1 | Primary light-surface text |
| `--ink-soft` on `--paper` | 9.52:1 | Secondary light-surface text |
| `--muted` on `--paper` | 5.21:1 | Metadata |
| `--accent` on `--paper` | 3.76:1 | Non-text marks only |

The Explorer can switch its reading surface with `prefers-color-scheme`. The brand hero stays
dark in both schemes. Use `--night`, `--on-night`, `--sage`, `--slate` and `--mint` there.

## Typography

Use the local system stack. No font download, font CDN or embedded corporate typeface.

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
```

- Body text: 1rem or 1.0625rem, line-height 1.5 to 1.65.
- Hero heading: weight 720, line-height about 0.9 to 0.94, letter-spacing -0.065em.
- Section headings: weight 650, tight but not compressed letter-spacing.
- Kickers, metrics and product labels: the local monospace stack, 0.875rem or larger.
- Never declare text below 0.875rem. Measure the rendered result on narrow screens.
- Use Norwegian or English as the page declares. Keep `Tún` and artefact terminology unchanged.

## Components

### Actions

A primary action on a dark surface has a `--mint` fill and `--ink` text. A secondary action has
a transparent fill, a visible border and `--on-night` text. On a light surface, reverse the
primary pair: `--ink` fill and `--on-night` text.

All actions have a minimum target of 44 by 44 CSS pixels. Focus uses a 2 or 3-pixel `--mint`
outline on dark and `--ink` or another measured visible outline on light. Hover never removes
the border or relies on movement alone.

### Cards and panels

Use `--panel` on `--paper`, with a 1-pixel `--line` border. Small cards use a 0.6rem radius;
large interactive panels can use 0.75rem to 1rem. Shadows stay quiet and are never the only
boundary. Dark panels use `--night` or `--deep`, with `--slate` borders.

### Navigation

The brand mark and `Tún` come first. Language controls remain visible and have a clear current
state. The Explorer may use a segmented control; the home page may use links. Both use the same
colour pairs and 44-pixel target minimum.

### Data graphics

The public brand palette does not replace the measured chart palettes in
[chart colour palettes](10-chart-colour-palettes.md). Use `--accent` for a single data series or
a simple tick on a light surface. Use `--mint` for the equivalent mark on dark. Status colours
keep their declared meanings.

## Page-specific expression

The home page can use a moving field and a large campaign hero. The Explorer puts a working
artefact beside its introduction and needs a quieter background. These are different expressions
of the same identity, not two themes.

Do not copy the home page's motion into the Explorer. Do not give the home page the Explorer's
tool panels. Share the mark, palette, type and component rules instead.

## Change control

When a token or the mark changes, update this document, the home page and the Explorer template
in the same change. Rebuild the Explorer, run both repositories' gates, and inspect desktop and
mobile screenshots in Chromium and WebKit. Check the contrast table again before changing a pair.
