---
name: adding-an-artefact-kind
description: "Add a new kind of artefact to Tún end to end: a builder in tools/, a template on the colour seam, two languages, a pinned example, a suite that re-derives the drawing and can fail, and the eight registration points that keep the gates honest. Use when adding a new chart or page shape, when a documented shape has no builder, when a new artefact must ship through every gate, or when the count of kinds in the docs has to move."
license: Internal
metadata:
  title: Adding an artefact kind
  version: 1.0.0
  tags: "workflow, artefact-kind, gates, tdd, i18n"
  platforms: "darwin, linux, win32"
---

# Adding an artefact kind

**Tier and cost, for the first reply:** none beyond the gates you were going to run anyway. One
branch, one PR, and about a day: the builder and the template are the quick part, and the suite
that can actually fail is the rest. No approval chain, no admin step. It does add a row to five
documents and a suite to `check_all`, so the next PR runs one suite longer.

Five kinds were added this way in one week (scatter, box plot, Gantt, calendar, bullet). Every
one of them shipped a defect that no amount of reading caught and a measurement did, so the
order below is the one that finds them early.

## 0. Before you write code

- **The shape must answer a question another shape does not.** Read
  `docs/33-artefact-shapes.md` (what exists) and `docs/34-artefact-ideas.md` (what is missing and
  why it is hard). If the candidate is already in that list, its trap is written down there; take
  it seriously, it is the failure mode you will hit.
- **Name the one thing the shape refuses to do.** If you cannot, the shape is not designed yet.
  Every builder here refuses something, and the refusals that matter are the cases where a
  drawing would be *true and misleading*.

## 1. The builder, `tools/build_<kind>.py`

Copy the shape of a recent one (`build_boxplot.py`, `build_bullet.py`). The order that works:

1. `tun_core.coerce_numbers(tun_core.read_rows(path))` **first**. `is_numeric_column` answers
   about Python numbers, so asking it about raw CSV rows rejects every numeric column. Two kinds
   lost a build to this before it was written down.
2. `die()` with the fix in the sentence: name the column, the row, the flag, and what to do.
3. The statistics are computed here. If the number is a **convention** (a quartile, a target, a
   direction), print the convention on the page.
4. Precision comes from the **statistics**, not from the observations: whole observations can
   interpolate to a fractional quartile, and rounding it makes the page irreproducible.
5. `build_stamp.naive()` and `build_stamp.from_mtime()` for the provenance block, `build_size.enforce`
   for the budget, `feedback_link.block` guarded behind `if args.feedback_to`.
6. Fill the template, then **fail if any `{{` remains**. A missing placeholder ships as literal
   braces and nobody notices for a month.

## 2. The template, `templates/<kind>.html`

Put it on the seam from the first line: see `template-on-the-seam`. Two things bite on new
templates specifically:

- **The min-width floor must be the DRAWING's width**, and where that width varies (a calendar's
  week count), emit it from the builder as `style="min-width:{w}px"`. A fixed `min-width` scaled
  a phone to 8.9 px text, and `verify_viewports` was the only thing that noticed.
- **The `@media print` block comes before the dark block**, and the dark block is scoped to
  `@media screen`, or a dark-mode reader prints light ink on white paper.

## 3. The strings, `templates/i18n/<kind>.strings`

- A key must be **used as a literal**: `t["state_late"]`, not `t["state_" + state]`. The i18n gate
  greps the source for the quoted key, so a computed key is invisible to it and reported as
  unused. Declare a dict of literals instead.
- An English value may hold **no apostrophe and no quote**. "the box's height", `"a little"` and
  `Tukey's` are all rejected; rewrite the sentence.
- `nb` is what a Norwegian reader gets; the hash of every existing page must not move, so only
  add.

## 4. The example, `examples/<nn>-<kind>/`

- `generate_data.py` writes the CSV from a **fixed** sequence or a hand-written table. Never
  `random`: an example that changes between runs cannot be checked against its own output.
- Build with a pinned clock: `SOURCE_DATE_EPOCH=1792836000 TZ=UTC`.
- Open the result in a browser at two widths and **look at it**. Every kind so far had something
  visible that no assertion had caught.
- A `README.md` with the rebuild and verify commands, the rules the page carries, and the
  refusals.

## 5. The suite, `tests/test_<kind>.py`

This is the part that decides whether the kind is worth having.

- **Re-derive from the source.** Parse the CSV yourself, compute the number yourself, and compare
  against the page. A suite that calls the builder's own function proves the function agrees with
  itself.
- **Read the axis off the page**: take the printed ticks, compute slope and intercept, then
  predict every bar, mark and label. Wrong intercept arithmetic in the *suite* once reported a
  39-unit error on a correct drawing — fix the suite, not the builder, and say which it was.
- **At least three mutations**, each breaking exactly one named check, with a plausible wrong
  version (min-and-max whiskers; "assume it started on plan"; a second scale). Assert the
  mutation still builds, then assert the specific check sees it.
- **Mutation anchors must match the source exactly.** A stray trailing space silently aborts the
  patch; verify the file changed after writing it.
- **Measure what only a browser can see**: label collisions, text under 14 px, a mark printing
  through another. This catches the defect class that all assertions pass.
- **Pin the example**: a rebuild byte-for-byte equal to the committed file.

## 6. The eight registration points

Miss one and a gate goes red, or worse, stays green while the artefact is invisible.

| # | Where | What |
|---|---|---|
| 1 | `skills/tun-new/SKILL.md` | a section with a runnable block (`test_skill_routes` requires it, and every printed flag must exist) |
| 2 | `tools/check_no_real_data.py` → `ALLOWED_DATA` | the example CSV and a one-line reason; "it was already there" is not a reason |
| 3 | `tests/test_dark_scheme_gate.py` → `REQUIRED_FOLLOWERS` | the example path and what it proves |
| 4 | `tools/core_generic_baseline.json` | bank AFTER `git add`, or the scan cannot see the new files |
| 5 | `docs/33-artefact-shapes.md` | a row, the count in the title, and the competing-shape note |
| 6 | `docs/34-artefact-ideas.md` | remove the candidate, and say it shipped |
| 7 | `docs/index.md` | the count in the blurb |
| 8 | `ROADMAP.md` | the count and the names, including how many are on the seam |

`tests/test_gate_inputs.py` also requires every example path the suite resolves to be git-tracked,
so `git add` the example before running the gate or it reports the file as untracked.

## 7. The gates, in this order

```bash
uv run --extra verify python3 tools/check_all.py
uv run --extra verify python3 tools/verify_documented.py --engines chromium
uv run --extra verify python3 tools/verify_a11y.py examples/<nn>-<kind>/<slug>.html
uv run --extra verify python3 tools/verify_a11y.py examples/<nn>-<kind>/<slug>.html --dark
```

`verify_documented` takes four to eight minutes and has more than once exceeded a foreground
timeout: run it in the background and watch it. A red suite's full log is kept in
`$TMPDIR/tun-check-all/<name>.log` by `check_all`, and the failing lines are printed with it.

## 8. The defects this has caught, so you know what you are looking for

- **Labels collide.** Measured in the browser at two widths; fixed with collision-aware placement,
  never by weakening the check.
- **The page rounds its own numbers.** Precision from the statistics, not the observations.
- **A note contradicts the drawing.** The bullet chart said the axis starts at zero and printed
  `−2,9`; the calendar said missing days are hatched and drew them pale. Read the notes against
  the picture.
- **The drawing scales below its own text floor.** The min-width is the drawing's width.
- **One outlier flattens the scale** and hides the pattern the page exists to show. Make the
  clamp a declared, printed choice (`--clamp`), never a silent one.
