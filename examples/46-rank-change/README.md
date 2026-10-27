# 46. Who moved, and how far

"Who is top now" is a sorted list. "Who moved" is a different question, and a table answers it
badly: the reader compares two long columns by eye and gives up somewhere in the middle. Two
ranked columns with a line per entity answers it in one glance.

The glance is also where this chart lies, in four ways, and every one of them produces a page
that looks entirely right:

* **rank is drawn as if it were value.** A product climbs four places on a rounding difference,
  and another falls one place while growing 22 per cent. The number is printed at both ends.
* **a newcomer is drawn as a mover.** A line from an empty row to a filled one invents an ascent
  nobody made.
* **a tie is drawn as a difference.** Two equal values are ranks 1, 1, 3.
* **the movement's sign is the easiest thing to get backwards.** A line between two columns has
  no inherent direction, so a flipped subtraction draws every climber as a fall, everywhere at
  once, with nothing looking wrong. The first draft of this page did exactly that, and two more:
  the table's change column subtracted the other way round, and the word for a leaver was drawn
  on the side that had the newcomer. All three are now checks.

```bash
python3 examples/46-rank-change/lag_data.py

python3 tools/build_rank_change.py \
  --data examples/46-rank-change/produkter.csv \
  --entity Produkt --period Kvartal --measure Omsetning \
  --from 2026-K1 --to 2026-K2 \
  --title "Hvem klatret, hvem falt" \
  --source "Syntetisk eksempeldata (produkter.csv)" \
  --requested-by "Salg" \
  --out examples/46-rank-change/rang.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_rank_change.py
uv run --extra verify python3 tools/verify_viewports.py examples/46-rank-change/rang.html
uv run --extra verify python3 tools/verify_a11y.py examples/46-rank-change/rang.html
```

## The rules it carries

* **both ranks are derived from the values, never from row order**, and printed beside every
  name on both sides. The same extract sorted differently gives the same page.
* **only an entity present in both periods is connected.** A newcomer and a leaver are drawn as
  a stub with the word for it, counted in the notes, and left out of the movement sentence.
* **a shared rank is shared and stated:** 1, 1, 3 rather than 1, 2, 3, with a line on the page
  explaining that the ranks skip.
* **the value is printed at both ends**, because rank alone cannot tell a move on a rounding
  difference from a collapse.
* **the movement sentence is computed**: the count in both periods, how many climbed, fell and
  held, the largest climb and the largest fall by rank. It cannot disagree with the drawing.
* **direction is carried twice.** A solid line climbs and a dashed line falls, and the geometry
  says the same thing, so the style is never the only carrier.
* **a solid line means "climbed", not "good".** The page does not know which direction anybody
  wanted. That is the scorecard's job, and it needs a declared direction and two bands.

## Refusals

A `--entity`, `--period` or `--measure` that is not a column (the message lists the columns), a
period the data does not hold, `--from` equal to `--to`, two rows for one entity in one period
(two numbers for one rank), a value that is not a number, more entities than the page can show
(above eighteen it is a list again), and two populations with nobody in both (nothing can have
moved).

## What the suite measures

`tests/test_rank_change.py` is 49 checks and five mutations. It re-derives, from the extract:
both column orders, both rank sequences including the tie, every printed value, the set of lines
and their direction, the marker words and which side each belongs on, the summary counts and the
two named movers, and the table's arithmetic in both the value and the rank columns. Then both
languages, the committed file rebuilt byte for byte from a pinned clock, and five mutations: a
line for a stub, ranks through a tie, a flipped movement sign, swapped stub words, and a
backwards change column.
