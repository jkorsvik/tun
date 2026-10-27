# 43. Where the mass is, and where there is none

A heatmap is the easiest artefact in this repository to draw wrongly, because every mistake is
invisible in a screenshot. A shade nobody can convert back into a number. A legend whose ranges
do not match the shades actually used. An empty cell drawn as zero. A ramp that has no
direction. White text on a pale cell. Each one looks fine and each one lies.

This page is one number per row-and-column pair, shaded on a stated scale, with the number
printed inside the cell.

```bash
python3 examples/43-heatmap/generate_data.py

python3 tools/build_heatmap.py \
  --data examples/43-heatmap/henvendelser.csv \
  --row Enhet --col Uke --measure Antall \
  --title "Henvendelser per enhet og uke" \
  --source "Syntetisk eksempeldata (henvendelser.csv)" \
  --requested-by "Kundeservice" \
  --out examples/43-heatmap/varmekart.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_heatmap.py
uv run --extra verify python3 tools/verify_viewports.py examples/43-heatmap/varmekart.html
uv run --extra verify python3 tools/verify_a11y.py examples/43-heatmap/varmekart.html
```

## The five rules it carries

* **The scale is stated, and the legend explains the drawing.** Every shade prints the numeric
  range it stands for, and the edges are rounded to what the page prints *before* they decide
  which band a cell gets. Otherwise the legend says "13–28" and "28–44" while a cell holding 28
  is drawn one band lighter: the one thing a legend may never do is disagree with the picture.
  The suite re-derives every cell's band from the printed ranges and compares it with the shade
  actually drawn.
* **The ends of the scale are on the page.** `--clamp` fixes the top, so a single outlier cannot
  flatten everything else into one pale block. Past the top the darkest shade means "at least",
  the legend says so, and the page counts how many cells sit above it.
* **An empty cell is not a zero.** No cases and no cases *recorded* are two different findings.
  A missing cell is hatched, carries a dash, and has its own legend entry; a cell that really
  holds 0 is shaded like any other value. The suite builds a file with a real zero to prove the
  two are drawn differently.
* **The ramp has one direction.** One hue, mixed out of the design system's blue, with strictly
  decreasing lightness, so a darker cell always means more. A hue ramp (blue to red through
  green) has no direction, and two shades can read as the same value.
* **Colour is never the only carrier.** The value is printed in every cell, and the ink is
  chosen per cell by *measured* contrast against that cell's own fill. `verify_a11y` does not
  catch white-on-pale SVG text, so the suite measures every cell at 4.5:1 itself, and one
  mutation paints all ink dark to prove the check bites.

## Totals that a reader can check

The table carries the same figures as the drawing, plus a total per row and per column, both
sums of the cells beside them. A total column headed "Sum" over a column of averages would be an
arithmetic lie a reader cannot see, so the heading moves with the aggregation: `--agg mean` gets
"Gjennomsnitt av rutene" and a sentence saying it is not the overall average, `--agg count` gets
"Antall rader".

The page also states which order it used. Rows are sorted by total, largest first, unless
`--row-order` gives one; columns sort ascending unless `--col-order` does. An order that leaves a
value out is refused, because a value nobody names disappears from the page and its absence is
not visible.

## Refusals

A negative value (a shade has one direction, so a value below zero belongs on a different
drawing), a column name wider than a cell, more columns than the page can label, more rows than
a heatmap can usefully carry, a measure that is not a number, an order that invents or drops a
value, and a clamp under the lowest value. Each names the number and the fix.

## What the suite measures

`tests/test_heatmap.py` is 65 checks: every figure re-aggregated from the extract by the suite,
every shade re-derived from the printed legend, the hatching of the empty cells against a real
zero, the ramp's monotonicity and single hue, the 4.5:1 contrast of every printed figure against
its own fill, the row and column totals as sums the suite takes itself, the clamp, both
aggregations and their labels, nine refusals, both languages, the committed file rebuilt byte for
byte from a pinned clock, and five mutations — including a legend whose ranges and shades
disagree, which no screenshot would show.
