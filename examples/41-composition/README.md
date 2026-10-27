# 41. What the total is made of, and where the mix and the level disagree

Every artefact before this one answers a question about a level (a dashboard), a change in it
(timeline, comparison, waterfall), or the shape of one measure (distribution). None answers
the question a management report asks most often: what is this total made of, and how did the
mix move?

That question has a trap built in, and the trap is the reason this page exists. **A share is a
ratio, so it can rise while the figure it describes falls** — when the total falls faster. A
picture of shares alone cannot show it, and a reader who only sees shares will conclude the
opposite of what happened.

```bash
python3 examples/41-composition/generate_data.py

python3 tools/build_composition.py \
  --data examples/41-composition/bemanning.csv \
  --measure Timer --cat Oppgave --period-col Kvartal \
  --title "Hva timene gikk til: 2026" \
  --source "Syntetisk eksempeldata (bemanning.csv)" \
  --requested-by "Bemanningskontoret" \
  --out examples/41-composition/sammensetning.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_composition.py
uv run --extra verify python3 tools/verify_viewports.py examples/41-composition/sammensetning.html
uv run --extra verify python3 tools/verify_a11y.py examples/41-composition/sammensetning.html
```

## The six rules it carries

* **The shares are rounded so they add up.** Printed shares use the largest-remainder rule,
  so every column adds to exactly 100,0. In this example, rounding each share on its own would
  have produced a column that does not, and the suite asserts that the dataset is one where
  that is true: otherwise the rule is not being tested, only paid for.
* **The level is never hidden by the share.** Each period's total stands above its column, and
  the table carries each category's absolute figure under its share. The share is the headline;
  the figure is the fact.
* **A divergence is named in words.** One sentence per category whose share and level move in
  opposite directions, generated from the two ends of the page: *"Saksbehandling økte andelen
  fra 40,0 % til 42,7 % mens nivået falt fra 4 800 til 4 100, fordi totalen falt mer."* The
  suite decides that set from the source rows itself and requires the page's list to match it
  exactly, in both directions.
* **The bands are one ramp, not a verdict.** Four approved slots from dark blue to a tint of
  blue, dark to light, so the stack reads as an order. Fire Red is left out on purpose: a
  composition is not good news or bad news, and red on an ordinary category reads as an
  accusation the file has no basis for.
* **The largest categories are drawn and the rest is one band.** Its height is the exact sum
  of what it replaces, named with how many categories it holds, and every category is in the
  table. A stacked column with ten bands is a picture nobody can read, so the drawing is a
  summary and the table is the account.
* **A negative figure is refused.** A share of a total that holds a negative cannot be
  stacked: the bands would overflow their own column. The refusal says so and points at the
  waterfall instead, which is the artefact for a change that has negatives in it.

## What it is not

Not an attribution of cause, and not a claim that the mix matters. It decomposes a total into
the column it was given and reports both figures for every category, so the reader can decide
which of them the question was about. A single-period build says so instead of inventing a
comparison.

There is no script. A filter would re-lay the drawing, and the drawing is the claim.

## What the suite measures

`tests/test_composition.py` is 52 checks: the column sums, the rounding bound, the levels
against the source rows, the band geometry against the shares, the colour slots, the
divergence set, nine refusals, both languages, the committed file rebuilt byte for byte from a
pinned clock, and five mutations — including one where only the *printed* share is wrong, which
no guard in the builder can see and only the column sum can catch.
