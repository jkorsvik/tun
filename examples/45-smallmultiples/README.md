# 45. Which of these groups behaves differently

A small multiple is the one chart that answers a comparison question, and it has exactly one
requirement: every panel must share a vertical scale. Give each panel its own axis and a group
moving between 4 and 8 looks precisely like one moving between 400 and 800. Every number in the
picture is still true, the page is beautiful, and the reading is wrong. `verify_a11y` sees
nothing, because nothing is unreadable.

So the shared scale is the deliverable, and the page prints it.

```bash
python3 examples/45-smallmultiples/lag_data.py

python3 tools/build_smallmultiples.py \
  --data examples/45-smallmultiples/ko.csv \
  --group Enhet --period Uke --measure Saker \
  --title "Saker i ko, per enhet og uke" \
  --source "Syntetisk eksempeldata (ko.csv)" \
  --requested-by "Driftsavdelingen" \
  --out examples/45-smallmultiples/smaaflater.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_smallmultiples.py
uv run --extra verify python3 tools/verify_viewports.py examples/45-smallmultiples/smaaflater.html
uv run --extra verify python3 tools/verify_a11y.py examples/45-smallmultiples/smaaflater.html
```

## The rules it carries

* **One scale, derived from every value, printed on the page.** The two rules drawn in each
  panel are the top of that scale and its floor, and the numbers stand in a gutter at the left
  of every row of panels. The suite checks every single dot against the scale the page itself
  prints, panel by panel, so a panel that scaled itself cannot pass.
* **The axis starts at zero unless you say otherwise.** `--truncate` is allowed, because a level
  that barely moves is invisible under a zero floor, and then a warning names the floor and says
  in words that it is a choice. What is never allowed is a truncated axis nobody mentions.
* **A missing period is a break, never a bridge and never a zero.** Drawn as a gap, counted on
  the page. The suite re-derives how many unbroken runs each panel must hold from the extract.
* **The period order is declared or sorted as text, never taken from row order.** `--periods`
  sets it. The same extract sorted differently must give the same page.
* **The panel order is the order that was asked for**, computed from the drawn numbers
  (`--order name|latest|change`), and the page says which rule it used and what that rule
  claims.
* **Each panel prints its own latest value.** The shape says "different", the number says how
  different, and a reader who only reads numbers still gets the answer.
* **The summary is computed, not judged.** Highest latest, lowest latest, widest movement, all
  named from the numbers that were drawn.

## Refusals

A `--group`, `--period` or `--measure` that is not a column (the message lists the columns), a
measure cell that is not a number (it names the row, because a text value on a numeric axis is a
scale that means nothing), more groups than the page can carry, fewer than three periods ("that
is a difference, not a shape"), and `--periods` that leaves a period in the data without a place
on the axis.

## What the suite measures

`tests/test_smallmultiples.py` is 51 checks and six mutations. It parses the SVG itself and
re-derives, from the extract: one geometry for the scale, every dot's position against the
printed numbers, one width per period across panels, the number of unbroken runs per panel, the
latest value in each panel, the table's first, latest, lowest, highest and period count, the
panel order for all three rules, the truncated-axis warning, both languages, and the committed
file rebuilt byte for byte from a pinned clock.

The six mutations are the two lies this artefact can tell (a per-panel scale, and dots scaled
while the axis rules stay shared), a bridged gap, an ignored `--order`, a latest label that
contradicts its own dots, and an unannounced truncated floor. Each must break one named check,
and the two scaling mutations must be caught by *different* checks, which the suite asserts.
