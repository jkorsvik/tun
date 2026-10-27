# 47. Do these two measures move together

Every other artefact here answers "how much" or "in what order". This one answers the question
behind half the requests that arrive as two columns and no chart: **do these two move together,
and which unit does not?**

The trap is that the picture is easy to draw and easy to trust. A cloud has a shape, the shape
has many explanations, and only one of them is "one of these causes the other". So the page
states what it draws, prints the axis span, and refuses to draw a trend line unless you ask for
one, and then prints the coefficient beside it.

```bash
python3 examples/47-scatter/generate_data.py

python3 tools/build_scatter.py \
  --data examples/47-scatter/enheter.csv \
  --label Enhet --x-col Svartid --y-col Tilfredshet \
  --trend \
  --title "Svartid mot tilfredshet, per enhet" \
  --source "Syntetisk eksempeldata (enheter.csv)" \
  --requested-by "Kundeservice" \
  --out examples/47-scatter/spredning.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_scatter.py
uv run --extra verify python3 tools/verify_viewports.py examples/47-scatter/spredning.html
uv run --extra verify python3 tools/verify_a11y.py examples/47-scatter/spredning.html
```

## The rules it carries

* **One point per unit, and the unit is named.** A scatter without names is a cloud: the reader
  can see that two measures move together and cannot see *which* unit sits apart, which is the
  only actionable thing on the page. Names are placed against a box model with four candidate
  positions, and a name with no free candidate becomes its number instead of landing on another
  point.
* **A label budget, declared.** Past about two dozen points, direct names collide and a legend
  does not help, because a legend identifies a colour and not a point. Above the budget every
  point carries a number and the names live in the table, and the page says which of the two you
  are looking at.
* **The axes span the data, not zero, and the page says so.** Forcing zero is right for a bar
  and wrong here: two measures can both sit far from zero, and zero at the bottom presses the
  whole cloud into a stripe that says nothing. The stated extremes are in the summary sentence,
  and the ticks are round numbers inside the span.
* **No fitted line unless it is asked for, and then `r` with `n`.** `--trend` draws a
  least-squares line and prints the coefficient and the count. Without the coefficient the line
  is an assertion; with the coefficient but no `n` it hides how little it rests on.
* **Points that share a place are counted.** Two units with identical values are one dot on the
  page and two rows in the table; the sentence above the table says how many, so the picture
  cannot be read as "fewer units than there are".
* **Groups get colour *and* shape.** `--group` uses `--cat-1..5` for colour and five marker
  shapes for the second channel, because colour alone stops identifying a group where two
  colours are hard to tell apart. Past five groups it refuses rather than decorating.
* **Every number is in a table**, numbered as the point, so the drawing can be checked instead
  of trusted.

## Refusals

Fewer than three units ("two points are a line and one is a dot"), a name used twice (a scatter
draws one point per unit, so a repeated name means the reader cannot tell which row is which), a
column that is not numeric in every row, one column asked for as both axes ("a measure against
itself is a straight line, and it would look like a perfect relationship"), more than 120 units
("above that the dots overlap into a blob; aggregate, or use the heatmap, which is built for
density"), more groups than the seam carries, and `--labels on` past the name budget.

## What the suite measures

`tests/test_scatter.py` is 51 checks and four mutations. It re-derives, from the extract: every
point's position against its own projection, that the largest value is drawn highest (an inverted
axis is silent otherwise), that no point sits on the frame (a crop), that the stated extremes are
the data's own and the ticks are round, that the table is every unit numbered as its point, the
label budget in both modes, the count of shared places, the coefficient recomputed by hand and
the drawn line's own endpoints, every refusal, and the committed file rebuilt byte for byte from
a pinned clock.

The label collisions are measured in **Chromium at two widths**, because a collision is the one
defect a static check cannot see: it found two on the first run of this suite, "Fosen" sitting on
"Numedal", which is what the placement rule above now prevents.

The four mutations are an inverted vertical axis, a coefficient with its sign dropped, shared
places no longer counted, and the label budget ignored. Each must break one named check.
