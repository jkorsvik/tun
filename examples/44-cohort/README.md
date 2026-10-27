# 44. Of the people who started, how many are still here

A cohort grid is the one artefact in this repository whose column axis is not in the file. The
columns are *periods since each row's own start*, derived from every person's first date, and that
derivation is where the shape is drawn wrongly almost every time. Each mistake looks completely
normal in a screenshot.

This page is one row per cohort, one column per period since that cohort started, shaded by the
share still active, with the count and the share printed in every cell.

```bash
python3 examples/44-cohort/lag_data.py

python3 tools/build_cohort.py \
  --data examples/44-cohort/kunder.csv \
  --id Kunde --date Dato \
  --title "Hvor mange blir med videre" \
  --source "Syntetisk eksempeldata (kunder.csv)" \
  --requested-by "Kundeservice" \
  --out examples/44-cohort/kohort.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_cohort.py
uv run --extra verify python3 tools/verify_viewports.py examples/44-cohort/kohort.html
uv run --extra verify python3 tools/verify_a11y.py examples/44-cohort/kohort.html
```

## The rules it carries

* **The cohort is the earliest date per person, never the file's row order.** The suite builds
  the same extract reversed and compares the two grids cell for cell. A cohort taken from the
  first row of the file would make the same data tell a different story depending on the sort.
* **Every share is divided by that row's own cohort size.** Divided by the whole file, every cell
  is small and the picture says nothing. The denominator is printed under the cohort name, and
  the suite re-derives every count and every percent from the extract itself.
* **A cell that cannot exist yet is hatched, never zero.** "Nobody came back" and "the period has
  not happened" are opposite findings. The hatch has its own legend entry, and one mutation fills
  those cells with zeros to prove the check bites.
* **A cell counts people, not rows.** Three visits in one month is one person. Vertical counting
  is visible in a cohort grid and nowhere else, so the rule is asserted with a fixture that holds
  exactly that, and a mutation doubles every cell to prove it.
* **Column +0 is the cohort size, by definition.** It is the same number as the size beside the
  label, and the page says so rather than presenting it as a finding.
* **A cohort too small to speak about is named, not drawn.** A square with two people in it wears
  the same colour as a finding. Cohorts under `--min-cohort` are listed with their sizes in the
  notes instead.
* **The bands are fixed percentages, so two pages can be read against each other.** The shade is
  a second reading of a number that is already in the cell, and every cell's ink is chosen by
  measured contrast against its own fill.

## Refusals

A date it cannot read (which would silently join the wrong cohort), an `--id` or `--date` that is
not a column, a week period asked for month-only dates, a threshold above every cohort, a
`--max-periods` outside its range, more cohorts than a page can carry, and an extract where no
row has both columns filled. Each names the number and the fix.

## What the suite measures

`tests/test_cohort.py` is 48 checks: every count and every share re-derived from the extract by
the suite, column +0 against the cohort size, the drawn cells against the cells that are possible,
the order-independence of the derivation, the distinct-people rule, the ramp's monotonic
lightness, every cell's own band and its 4.5:1 ink contrast, the small-cohort threshold, seven
refusals, both languages, the committed file rebuilt byte for byte from a pinned clock, and five
mutations. The parser refuses markup it does not understand, so a cell shape it has never seen
cannot make the checks quietly pass.
