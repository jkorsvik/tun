# 40. The steps that add up to a change

Reporting usually stops at "the number went from 12,1 to 13,1 million". The next question is
always the same: which parts account for it, and do they add up? That answer lives in a
spreadsheet somebody keeps by hand, where the arithmetic is invisible and the total is
whatever the last person typed. Here it is an artefact: one self-contained file where every
step is drawn, every contributor is written out with its own two figures, and the column adds
up on the page.

```bash
python3 examples/40-waterfall/generate_data.py

python3 tools/build_waterfall.py \
  --data examples/40-waterfall/omsetning.csv \
  --measure Omsetning --dim Produkt --period-col Måned \
  --from September --to Oktober \
  --title "Omsetning per produkt: september mot oktober" \
  --source "Syntetisk eksempeldata (omsetning.csv)" \
  --requested-by "Innsikt" \
  --out examples/40-waterfall/bro.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_waterfall.py
uv run --extra verify python3 tools/verify_viewports.py examples/40-waterfall/bro.html
uv run --extra verify python3 tools/verify_a11y.py examples/40-waterfall/bro.html
```

## The seven rules it carries

* **The bridge closes.** Opening plus every step equals closing, and the page prints the
  three figures in one line so a reader can check the claim by adding a column. The builder
  also checks it before writing, and it checks the level the drawn steps actually arrive at,
  not the closing figure it already knows: a step left out of the drawing must fail loudly
  rather than produce a picture whose total is wrong.
* **Nothing is dropped.** The drawing carries the largest steps by size, and the rest are one
  bar whose height is their exact net, named with how many steps it holds. Every contributor
  is still in the table, so the picture is a summary and the table is the whole account. The
  suite narrows the drawing to three steps and requires the closing figure to stay the same.
* **A figure is summed per contributor, not read off one row.** The input is a transaction
  extract: every product-month in the example arrives as two rows, and the first row is 60
  per cent of the figure, so a first-row reading is visibly wrong instead of plausibly wrong.
* **A contributor that exists in one period only is a step, not a hole.** It is named *ny*
  or *borte* and contributes its whole value, because that is what happened to the total.
* **The axis does not start at zero, and the page says so.** A bridge drawn from zero cannot
  show steps that are small against the level; a bridge whose axis is unstated exaggerates
  them. The figures under the drawing say where the axis begins and ends, and each step is
  also printed as a share of the opening figure.
* **A total is a level, not a bar.** On a truncated axis a total drawn as a column is a
  two-pixel sliver labelled with a large number, which reads as a defect. The opening and the
  closing are drawn as rules at their own height, with the figure above, and the steps float
  between the levels they move the total across.
* **Direction is geometry and a sign; colour claims nothing on its own.** A step up goes up,
  a step down goes down, and every step carries a signed number. Colour stays neutral unless
  the caller states which direction is good news (`--meaning up|down`), because more revenue
  and more overtime are the same arithmetic and only one of them is good.

## What it is not

Not a forecast, and not an attribution of cause: it decomposes a change into the contributors
the source column names, and it knows nothing about why they moved. Not a second model of the
data either: every figure is the sum of the source rows, and the table lets a reader check
that one contributor at a time.

There is no script. A filter would re-lay the drawing, and the drawing is the claim.

## What the suite measures, and why it has to

`tests/test_waterfall.py` is 71 checks: the arithmetic recounted from the CSV, the level
chain, every bar's height against the axis printed on the page, the top-N arithmetic, eight
refusals, both languages, and the committed file rebuilt byte for byte from a pinned clock.
Two things are worth calling out:

* **Label collisions are measured in a browser**, because a collision is the one defect no
  static check can see. This is not hypothetical: the first build of this page put
  "Betalingskort" and "Kontantkort" through each other, and the number labels were drawn off
  the left edge of the axis. The check reads every label's box at two viewport widths.
* **Three mutations, none of them caught by the builder's own guard.** A bar printing twice
  its own change, a wrap budget wide enough to collide, and a verdict colour with no declared
  direction. One more proves the guard itself bites: a step left out of the chain must stop
  the build.
