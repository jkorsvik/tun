# 39. Many measures, one period, with their targets

The monthly management report has the same shape almost everywhere: a short list of
measures, each with this period's figure, the change, the target and a status. Two things
make it useful, and neither existed in this repository before this artefact: a trend small
enough to sit beside the number, and a target to be measured against.

```bash
python3 examples/39-scorecard/generate_data.py

python3 tools/build_scorecard.py \
  --data examples/39-scorecard/manedstall.csv \
  --title "Månedsrapport oktober 2026" \
  --source "Syntetisk eksempeldata (manedstall.csv)" \
  --requested-by "Kvalitetsavdelingen" \
  --green-at 1.00 --amber-at 0.95 \
  --out examples/39-scorecard/manedsrapport.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_scorecard.py
uv run --extra verify python3 tools/verify_viewports.py examples/39-scorecard/manedsrapport.html
uv run --extra verify python3 tools/verify_a11y.py examples/39-scorecard/manedsrapport.html
```

## The six rules it carries

* **No direction, no verdict.** An increase is good news for revenue and bad news for
  complaints, and the file cannot know which it holds. Direction comes from a `Retning`
  column (`opp`/`ned`) or from `--lower-is-better`, and without one the page prints the
  figures and says nothing about whether they are good. The example's own file carries the
  column; the suite builds the same file without it and requires every card to lose its
  status.
* **No bands, no status word.** "Near target" is a policy, not a fact. `--green-at` and
  `--amber-at` are declared as fractions of the target, and a build without them says so on
  every card instead of guessing.
* **The gap is one subtraction, the same way round for every measure**: latest minus target.
  Only the status word knows which direction is good, so the number a reader checks by hand
  is the number on the page.
* **A missing period is a break, never a straight line.** The example's `Antall klager` has
  no figure for July: the drawing stops, and there is no dot for the month that is not there.
  An interpolation would be a figure nobody measured.
* **Every figure is also in a table**, period by period, so a card can be checked instead of
  trusted. The suite recomputes each dot's position from the table's own window.
* **There is no script.** A scorecard is a snapshot with its history behind it; a filter
  would be a different artefact, and re-laying seven trend lines in the browser is a second
  thing to get wrong.

## The status colour, and why there are only two

The approved status pair is Fire Red `#dc2a2a` and Success Green `#007b5e`, both measured at
WCAG AA on white (`tools/tokens/status-semantic.css`). There is no approved amber, and
inventing one would be a design decision nobody has taken, so the middle band uses the
approved neutral `#737373` and carries its meaning in the word beside it: *i mål*, *nær mål*,
*ikke i mål*. Colour is never the only signal, per WCAG 1.4.1.

That is also why the status is a word first and a colour second: a reader printing this page
in black and white still gets the verdict.

## What it deliberately is not

No commentary field, no forecast, no rolling average, no "traffic light" without a declared
band. A comment per line is the one thing a real monthly report usually has and this builder
does not: a comment is text a person wrote, not a number this file measured, and mixing the
two into one artefact makes the provenance of a sentence unanswerable.

Every trend has its own scale, so two cards cannot be compared in height. That is stated on
the page, and the figures are on the card and in the table for exactly that reason.

## On a phone

The cards stack, one per row, and the table pans sideways inside its own box rather than
putting the page into a horizontal scroll. Nothing on the page is under 14 px, and nothing
that can be clicked is under 44 px.
