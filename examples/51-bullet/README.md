# 51. Which of these is behind its target

A scorecard (39) judges a handful of measures over time. This judges a **list**: fourteen units,
each with a number and its own target, and the question is which of them is off plan. A table of
two columns makes the reader do the subtraction; a bar chart with no target line hides the only
thing that matters.

The trap is the one every target chart carries: **a target is a policy, not a measurement**. If
the page does not say where the target came from, a reader can only argue with the picture. The
second trap is direction: a rise is good for coverage and bad for waiting time, and a page that
does not know which way is better cannot say who is behind.

```bash
python3 examples/51-bullet/generate_data.py

python3 tools/build_bullet.py \
  --data examples/51-bullet/dekning.csv \
  --label Enhet --value Dekning --target Maal --direction up \
  --target-note "styremøtet 12.05.2026" \
  --title "Dekning mot mål per enhet" \
  --source "Syntetisk eksempeldata (dekning.csv)" \
  --requested-by "Fagavdelingen" \
  --out examples/51-bullet/dekning.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_bullet.py
uv run --extra verify python3 tools/verify_viewports.py examples/51-bullet/dekning.html
uv run --extra verify python3 tools/verify_a11y.py examples/51-bullet/dekning.html
```

## The rules it carries

* **`--direction` is required.** Without it the page would have to guess which way is better,
  and a guess is a verdict nobody asked for.
* **the target is a mark and a number**, and `--target-note` records where it came from, so the
  target can be argued with instead of the chart.
* **the gap is a signed number in the measure's own unit**, positive on the good side. The colour
  summarises; the number answers.
* **the axis starts at zero** when every value is positive, because a bar cut off at the bottom
  overstates a difference. The ticks prove it, and the gate asserts it: the first build printed
  `−2,9` while the page claimed zero, which is exactly the contradiction this check exists for.
* **the row order is stated**: furthest behind first, or by name.
* **the count is the sentence**: "seven of fourteen behind, worst 13,2" is the answer, and the
  rows are the evidence.

## Refusals

A row with no target ("a bullet chart without a target is a bar chart"), a column of words, more
than 30 rows, and a label past the ceiling — refused rather than truncated, because a truncated
unit name is not a name.

## What the suite measures

`tests/test_bullet.py` is 41 checks and four mutations. It reads the axis **off the printed
ticks** (slope and intercept), then re-derives from the extract: every target mark's position,
every bar's end, every printed gap with its sign, all three state words, both row orders, the
zero-anchored axis, and the committed file rebuilt byte for byte from a pinned clock.

The strongest check is not arithmetic: running the same numbers with `--direction down` must
move exactly the complementary set of units behind the target. A flag that changes nothing would
pass every positional check on the page.

In **Chromium at two widths** it measures that no label overlaps another and that every label is
at least 14 px.

Four mutations: the direction ignored, the gap printed unsigned, the axis padded below zero
(the defect this page actually had), and the target mark placed at the value.
