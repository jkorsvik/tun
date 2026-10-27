# 53. Where the volume went between stages, and that it adds up

A funnel (42) counts one cohort through declared stages in a line. This traces volume through a
**network**: several starts, several ends, flows that meet in the middle. The question is where
the volume went, and the picture is only worth having if it is arithmetically true.

The trap is that a flow picture is easy to fake. Volume can appear or vanish between two stages, a
band can change meaning at its two ends, or the bands can leave gaps in the node they leave from.
None of that is visible to a reader who is not adding the numbers, which is why the builder
refuses and the suite measures.

```bash
python3 examples/53-sankey/generate_data.py

python3 tools/build_sankey.py \
  --data examples/53-sankey/kanaler.csv \
  --from Kanal --to Utfall --value Antall \
  --title "Hvor ble henvendelsene av" \
  --source "Syntetisk eksempeldata (kanaler.csv)" \
  --requested-by "Kundesenteret" \
  --out examples/53-sankey/kanaler.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_sankey.py
uv run --extra verify python3 tools/verify_viewports.py examples/53-sankey/kanaler.html
uv run --extra verify python3 tools/verify_a11y.py examples/53-sankey/kanaler.html
```

## The rules it carries

* **a flow diagram that does not balance is decoration.** Every intermediate node must take in
  exactly what it passes on, checked to the last unit, and an extract that does not is refused by
  name with the two totals beside it.
* **one scale for the whole picture.** A per-stage scale would let a band mean one thing at one
  end and something else at the other. A stage carrying less volume is visibly shorter instead.
* **ribbons tile their node exactly**: no gap, no overflow, at both ends, and the band leaves with
  the thickness it arrives with.
* **a cycle is refused.** If volume can return to an earlier stage there are no stages, and a
  layered drawing of it would invent an order that is not there. The message names the cycle.
* **positive, unique flows only.** Zero draws a hairline nobody can see; a duplicated pair means
  the picture and the table would disagree about one number.
* **every flow and every node total is in a table**, so a reader can add a column instead of
  trusting a width.

## Refusals

A node that does not balance (named, with in and out), a cycle (the path is printed), a zero or
negative flow, the same pair twice, a self-loop, a name past the label ceiling, and more nodes or
flows than the drawing holds.

## What the suite measures

`tests/test_sankey.py` is 31 checks and three mutations. From the extract it re-derives: one bar
per node with its height on one shared pixels-per-unit, every ribbon's thickness on that same
scale, the **drawn curve** against the geometry written beside it (so a band cannot leave thin and
arrive wide), the ribbons tiling each node with no gap and no overflow at either end, the balance
at every middle node, the stage numbers as its own longest-path computation, and every cell of
both tables.

In **Chromium at two widths** it measures that no label runs past the canvas and that every label
is at least 14 px. That check found a real defect: the first stage label, centred at x = 14, ran
off the left edge, and the last one lost its number at the right.

Three mutations: bands on a 1,3× scale, bands that all start at the top of their node, and the
balance check disabled on an extract that does not balance.

Two defects were found by looking at the page: the last stage label was clipped to "Trinn", and
node labels sat on top of the ribbons with nothing behind them. Both are fixed in the template —
a clamped anchor and a `paint-order: stroke` halo in the panel colour.
