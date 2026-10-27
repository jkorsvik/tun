# 48. Which of these is wide, which is late, and which has a tail

A distribution per group is the honest answer to "how long does this take", and it stops working
at about six groups: six histograms is a wall. A box plot puts twenty groups on one axis, which
is the only shape here that answers the question for a whole list at once.

The trap is that every number in a box is a **convention**. Quartiles, whiskers and outliers are
all defined by a rule, two tools that pick different rules draw different pictures from the same
rows, and nothing on either page says so. So this one declares its rules and prints n.

```bash
python3 examples/48-boxplot/generate_data.py

python3 tools/build_boxplot.py \
  --data examples/48-boxplot/saksbehandlingstid.csv \
  --value Dager --group Enhet \
  --title "Saksbehandlingstid per enhet" \
  --source "Syntetisk eksempeldata (saksbehandlingstid.csv)" \
  --requested-by "Fagavdelingen" \
  --out examples/48-boxplot/boksplott.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_boxplot.py
uv run --extra verify python3 tools/verify_viewports.py examples/48-boxplot/boksplott.html
uv run --extra verify python3 tools/verify_a11y.py examples/48-boxplot/boksplott.html
```

## The rules it carries

* **n is printed at every box.** A box over four observations has a median that is an accident
  and quartiles that are interpolation, and it looks exactly like a box over four hundred. A
  group with fewer than three values is refused by name.
* **one declared quantile convention.** Interpolation between order statistics, stated on the
  page. The suite recomputes every quartile from the definition rather than reading the
  builder's answer back.
* **Tukey's whiskers**, the furthest observation within 1.5 IQR, and everything beyond drawn as
  a dot and counted. Min-and-max whiskers turn the whisker into a range and hide exactly the
  tail this chart exists to show.
* **precision comes from the statistics, not from the observations.** Whole observations can
  interpolate to a fractional quartile, and rounding `8,75` to `9` makes the page irreproducible
  from the rows underneath it. A whole number prints whole; an interpolated one prints as far as
  it needs.
* **the row order is a claim**, sorted by median or by name, and the page says which.
* **a box hides the shape, and the page says so.** Two groups with identical quartiles can be one
  peak or two. The distribution page is named as the one to use when the shape is the question.
* **all five numbers are in a table**, with the outlier count, so the drawing can be checked.

## Refusals

A group with fewer than three observations (named, with its count), more than 24 groups ("the row
labels collide; group the smallest, or use the distribution"), a value column that is not numeric
in every row, and a column that is not in the file.

## What the suite measures

`tests/test_boxplot.py` is 36 checks and three mutations. It re-derives, from the extract: every
box's width as a multiple of its own quartile distance (one projection for the whole page), the
median mark's position measured from the box edge, both whisker caps against its own Tukey
fences, every outlier dot and which group it belongs to, the row order for both rules, the
table's eight cells per group, every refusal, and the committed file rebuilt byte for byte from a
pinned clock.

The row names are measured in **Chromium at two widths**, and must all be at least 14 px.

Three mutations: whiskers as min and max (no outliers left to draw), the quantile snapped to the
nearest observation, and the row order ignored while the page still claims median order. Two of
the three were found by the suite on its first run, in the other direction: the page was rounding
its quartiles, and the suite's own position arithmetic measured from the wrong origin.
