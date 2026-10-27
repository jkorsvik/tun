---
name: template-on-the-seam
description: "Put a Tún chart or page template onto the shared colour seam so it follows the reader's system dark setting, and keep it there. Covers the mapping rules (which role goes to the seam, which stays template-local), the seven defects that recur on every template, the before/after gates, the blast radius when the seam itself moves, and the i18n pair protocol that a rebuilt artefact forces. Use when adding a template to the dark rollout, when a page or chart renders white for a reader whose system is dark, when a colour variable in a template collides with a seam name, or when the seam's token files change and every artefact has to be rebuilt."
license: Internal
metadata:
  title: Template on the seam
  version: 1.0.0
  tags: "theming, tokens, dark-mode, template, workflow"
  platforms: "darwin, linux, win32"
---

# Template on the seam

**Tier and cost, for the first reply:** none. It edits one template, one builder and one
suite, rebuilds the artefacts that template produces, and opens a branch. No approval chain,
no admin step. The only cost that is not obvious is the rebuild: touching
`tools/tokens/*.css` forces every seam-carrying artefact to be rebuilt in the same change.

A self-contained artefact has no stylesheet to link. Every colour it uses is written into the
file at build time, which is why a template that carries its own hexes renders a white page to
a reader whose system is dark. The seam fixes that once per template instead of once per
artefact, and the gate stops the next person from quietly giving it back.

## When to use

- A template or a built page renders white for a reader whose operating system asks for dark.
- You are adding a new template and want it themed from the start.
- A colour variable in a template shadows a seam name and something renders wrong.
- `tools/tokens/theme-*.css` changed and every inlining artefact must be rebuilt.

## The shape of the job

**One template, one branch, one PR.** The rollout was done fourteen times this way and each
merge was reviewable on its own. Batching two templates into one PR doubles the rebuild blast
radius for the same number of reviews.

Each PR touches the same five things, in this order:

1. the template (`templates/<name>.html`)
2. the builder (`tools/build_<name>.py`)
3. the template's own suite (`tests/test_<name>.py`)
4. the gate lists in `tests/test_dark_scheme_gate.py`
5. the artefact the builder produces, rebuilt with its pinned clock

## Step 1 — read the colour surface before changing it

Do not start from the diff you imagine. Count what is there:

```bash
sed -n '/:root{/,/^}/p' templates/<name>.html      # the declared variables
grep -n 'var(--' templates/<name>.html | head -40  # where each one is painted
grep -o '#[0-9a-fA-F]\{3,6\}' templates/<name>.html | sort | uniq -c
```

Two numbers decide the size of the job: how many variables are declared, and how many of them
are actually painted. In the flagship dashboard **forty** were declared and **ten** were used;
the other thirty were carried into every build and read by nothing. Deleting those is part of
the work, not a tidy-up.

## Step 2 — decide the mapping

Every chart template so far declared the same nine names over light hexes: `--bg`, `--panel`,
`--ink`, `--muted`, `--line`, `--brand`, `--brand-dark`, `--brand-soft`, `--on-brand`. Those
are already the seam's names, so the change is to **stop declaring them** and let the seam
supply them. Delete the `:root` block and put `{{TOKEN_CSS}}` where it was.

Then sort the remaining local roles into two groups. This is the judgement the rest of the
skill depends on.

**Goes to the seam** — a role with a shared meaning:

| local | seam | note |
|---|---|---|
| a surface, ink, border, muted label | `--bg`, `--ink`, `--line`, `--muted` | identical values in light, so the light page does not move |
| the primary data colour | `--brand` | |
| a header band fill | `--brand-dark` | see defect 1 before you use it |
| a hover wash, a note box, a group band | `--brand-soft` | needs its ink from `--on-brand-soft` |
| a positive or negative status pair | `--ok` / `--ok-bg`, `--bad` / `--bad-ink` / `--bad-soft` | the seam has already re-picked them for a dark page |
| a gridline or separator | `--rule` | |
| a categorical series | `--cat-1` … `--cat-5` | |
| a UI rule, a muted mark | `--rule`, `--muted` | |

**Stays template-local, with its own dark counterpart** — a design decision, not a role:

- a **ramp** whose steps mean something (a composition's four bands, a heatmap's five). The
  light ramp is mixed into white and is invisible on a dark panel, so it needs a second ramp
  mixed into the panel, and often the ink flips with it.
- a **mark** that must stand clear of the surface it sits on: a median rule, a total's level
  rule, a scale ceiling, a flat connector.
- **gridlines inside a chart panel**: a grey chosen to sit quietly on white is invisible on
  dark.

Name a local role so it cannot shadow a seam name. `--rule` used to mean a chart gridline in
two templates and a UI rule in the seam; both became `--sm-rule` / `--rc-flat-line`. **A name
collision is silent**: the template keeps working in light and renders wrongly in dark.

**Delete a role painted nowhere.** `--rule-top` was declared and used once; two timeline roles
existed with no consumer at all.

## Step 3 — the seven defects that recur

Every one of these was found by measurement, on a template whose light build looked perfect.

1. **A header band that fills `--brand-dark` and letters `--on-brand`.** In light that is
   white on ocean. In dark `--brand-dark` *is* the darkest surface and `--on-brand` resolves
   to `--bg`, so the title is dark on dark. Fix: `color` from the theme in a dark block.
2. **An ink on a `--brand-soft` wash.** `--brand-dark` on that wash is the same colour twice
   in dark. Fix: `--on-brand-soft`, which resolves to `--brand-dark` in light, so the light
   page is byte-identical.
3. **A mark or a text filled `--brand-dark`.** That colour *is* the panel in dark. Symptom:
   a rule drawn in the colour of the wall behind it, or a KPI figure at 1.00:1. Fix: `--brand`
   for a mark that should stand out, `--ink` / `--muted` for text.
4. **A wash or status colour chosen for white.** Fire Red as *text* is 4.49:1 on the panel,
   under AA by one hundredth. Fix: `--bad-ink` for text, `--bad` for a mark, `--bad-soft` for a
   wash.
5. **A ramp mixed into white.** blue on a dark panel is 1.31:1. Fix: a second ramp, and
   decide the ink per band per theme.
6. **A raw white surface, or a form control with no colour of its own.** `#fff` on a card is a
   white card under light ink. And a `button` or `select` with no `color` renders the browser's
   `CanvasText`, which stays black at 1.22:1 on the dark panel: a form control has to state its
   colour.
7. **Print.** `@media print` forces the sheet white; a dark block declared after it wins the
   cascade and paints the ink light. Every dark block is scoped to `screen and`, and a gate
   renders print media under a dark system to prove it.

## Step 4 — wire the builder

Two lines, in the builder's import block and at its page assembly:

```python
import tun_tokens
from tun_tokens import strip_css_comments
```

```python
token_css, _ = tun_tokens.load_token_css(auto_dark=True)
page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
        .replace("{{TOKEN_CSS}}", strip_css_comments(token_css)))
```

`auto_dark=True` is what derives the media query from `theme-dark.css`. A builder that forgets
it inlines the light theme only, and the page is white for a dark-system reader with no error
anywhere.

A colour that lives **only** in the dark theme must be declared in `theme-dark.css`, not in a
separate token file: `auto_dark_css()` reads the dark theme file, so anything else is silently
left out of the media query.

## Step 5 — the suite's scratch tree

Almost every chart suite copies the tool files into a temp directory and mutates one, to prove
a check can fail. The copy is a hand-written list, and it will not include the new import.

Symptom: `ModuleNotFoundError: No module named 'tun_tokens'` in a mutation, or a build that
produces no output file. Fix: add `tun_tokens.py` to the copied names **and** copy
`tools/tokens` alongside, because `tun_tokens` resolves the token files from its own location.

## Step 6 — rebuild the artefact

Find the pin in the suite (`PIN = "1792836000"`), read the build command from the example's
README, and run it with that clock and `TZ=UTC`:

```bash
SOURCE_DATE_EPOCH=<PIN> TZ=UTC python3 tools/build_<name>.py ... --out examples/<dir>/<file>.html
```

A rebuild without the pin rewrites the provenance stamps and the suite reports the committed
example as stale, which reads like a content difference and is not one.

## Step 7 — verify, and look

```bash
python3 tools/verify_a11y.py <artefact>            # light
python3 tools/verify_a11y.py <artefact> --dark     # the half no gate used to measure
python3 tests/test_<name>.py                       # the template's own suite
uv run --extra verify python3 tests/test_dark_scheme_gate.py
```

Then **open it in a browser at desktop width with the system set to dark and look at the
screenshot.** This is not ceremony: the heatmap passed every assertion with a white hatch on a
dark grid, and only the picture showed it. A clean assertion run says the assertions passed.

## Step 8 — move the ratchet, and mind the blast radius

`tests/test_dark_scheme_gate.py` holds two lists:

- `SEAM_PENDING` — every non-partial template that does **not** carry the seam, each with a
  reason. Delete the entry when the template gains the seam; the gate fails on a stale entry.
- `REQUIRED_FOLLOWERS` — artefacts that must keep following the system. Add the rebuilt
  artefact with the reason, so a later change cannot quietly drop the dark block.

If the change touched `tools/tokens/*.css` or `tools/tun_tokens.py`, **every** seam-carrying
artefact moved, not just this one. Rebuild them all and re-pin `tests/test_i18n.py`:

1. dump the current builds (`--dump`), which is one file per probe;
2. rewrite each recorded hash from the dump, matching the key to `<case>--<path>`;
3. if a *builder's output* changed, the suite's byte-for-byte check needs deliberate pairs:
   derive them from a line diff of the old and new builds, use anchors unique in the file, and
   **order matters** — an insertion pair whose anchor lives inside text another pair inserts
   must come after it;
4. verify the pairs by applying them to the old build and comparing with the new one byte for
   byte, across every probe, before splicing them in.

`python3 tools/check_core_is_generic.py --baseline > tools/core_generic_baseline.json` when the
gate reports the boundary moved. Removing a palette lowers the count, which is progress and
must be banked, or `check_tree` fails with "progress, bank it".

## Before the PR

```bash
uv run --extra verify python3 tools/check_all.py
uv run --extra verify python3 tools/verify_documented.py --engines chromium
```

Both. `check_all` alone does not measure rendered text or the accessibility sweep.

The PR body names what the template *was* and what it *is*, the defect the change found (every
one of the fourteen found something), and the numbers: which suite, how many checks, which
screenshots were looked at. "It now follows dark mode" is not a review.

## What this skill is not

It is not a checklist to run blind. The mapping in step 2 is a judgement: a role with a shared
meaning belongs on the seam, a design decision does not, and getting that wrong is how a
template ends up with eleven local colours that nobody dares change. When in doubt, ask what
the colour *means* rather than what it looks like.
