# 52. Which few explain most of it

A composition (41) asks what a total is made of and draws every part. This asks which parts
*matter*: categories sorted by size, with the cumulative share, and a long tail folded into one
bar that carries its count.

The trap is the sort. A Pareto in source order is a bar chart with a line drawn over it, and the
line then says nothing. The second trap is arithmetic: the cumulative line has to end at the total
it was computed from, which means a folded tail must be summed, not dropped.

```bash
python3 examples/52-pareto/generate_data.py

python3 tools/build_pareto.py \
  --data examples/52-pareto/henvendelser.csv \
  --label Arsak --value Antall \
  --title "Henvendelser per årsak" \
  --source "Syntetisk eksempeldata (henvendelser.csv)" \
  --requested-by "Kundesenteret" \
  --out examples/52-pareto/arsaker.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_pareto.py
uv run --extra verify python3 tools/verify_viewports.py examples/52-pareto/arsaker.html
uv run --extra verify python3 tools/verify_a11y.py examples/52-pareto/arsaker.html
```

## The rules it carries

* **the sort is the claim and is stated on the page**: largest first.
* **the values must be additive.** A rate or an average is not a Pareto, because summing it means
  nothing. Count first, then build.
* **the folded tail keeps its arithmetic.** Past `--top` categories the rest become one bar
  labelled with how many it stands for, so the total does not move and the cumulative line still
  ends at 100 %.
* **the shares add up.** They are rounded by largest remainder, so the column is exactly 100,0 and
  a reader who adds them does not find 99,9 and assume they were wrong.
* **two axes, both labelled**: bars in the measure's own unit, the cumulative line in percent on
  the right. The page says so, because a line read against the left axis is a meaningless number.
* **the vital few are counted over real categories**, never over the folded bar: "the largest
  thirteen" would otherwise include one bar that stands for ten categories.
* **negatives are refused by name.** A credit makes the cumulative line run backwards; that is the
  waterfall's question.

## Refusals

A negative value (named, with the row), an all-zero extract, `--top 1`, a threshold outside
0–100, and more bars than the ceiling.

## What the suite measures

`tests/test_pareto.py` is 46 checks and three mutations. From the extract it re-derives: the
drawn set against the twelve largest, every bar's width on one shared pixels-per-unit, every
cumulative dot's position from **the printed right axis**, the share column summing to exactly
100,0, the cumulative column as the exact running share, the folded bar as the exact sum of what
it stands for, and the vital-few count.

In **Chromium at two widths** it measures that no label overlaps another, that no category name
runs off the canvas, and that every label is at least 14 px.

Three mutations: the bars left in source order, the shares computed against a wrong denominator,
and the tail dropped instead of folded (the line then stops short of 100 %).

Four defects were found while building this page, all by looking at it rather than by assertion:
a gutter wider than the longest name was needed (the first build clipped "Fakturafeil" to
"kturafeil"), the right-axis title needed its own space, the value labels could not sit outside
the bar (the cumulative line printed through them) nor inside it (a short bar is narrower than its
own number, so they now have their own column), and the table caption leaked a literal `{sum}`
until the slot was filled.
