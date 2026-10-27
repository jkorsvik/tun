# 35. When it happens, and what overlaps

A plan in a spreadsheet is two date columns and a hope that the reader compares them by eye.
The question people actually ask is "what overlaps" — which work runs beside which, and
where the crunch is. That is a picture, not a pair of columns.

```bash
python3 examples/35-timeline/generate_data.py

python3 tools/build_timeline.py \
  --data examples/35-timeline/milepaeler.csv \
  --title "Utredningen: når skjer det" \
  --source "Syntetisk eksempeldata (milepaeler.csv)" \
  --requested-by "Programmet" \
  --out examples/35-timeline/tidslinje.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_timeline.py
uv run --extra verify python3 tools/verify_viewports.py examples/35-timeline/tidslinje.html
uv run --extra verify python3 tools/verify_a11y.py examples/35-timeline/tidslinje.html
```

## The five rules it carries

* **The picture and the table are the same rows, in the same order.** The suite counts both
  and compares them, because a drawing that quietly drops a row is a plan that quietly drops
  a task. The table carries the dates written out, so a reader can check a bar instead of
  trusting it.
* **Every bar is placed by its own dates, to scale.** The suite recomputes each bar's x and
  width from the window the page prints, not from numbers the builder kept: a bar in the
  wrong place is a plausible picture of a wrong plan.
* **A row that cannot be drawn is refused by name.** An end before its start, a date that is
  not `YYYY-MM-DD`, a label long enough to run over the bars, more rows than the drawing can
  hold. Each refusal says which row and why. Guessing a `dd.mm` from an `mm.dd` is how a
  timeline ends up a month off.
* **The ruler is chosen from the span, and named on the page.** Ten days, two hundred,
  two thousand: one axis over each is a different drawing, and the page says which ruler it
  used.
* **There is no script.** A timeline is a picture; a filter would have to re-lay the drawing,
  and a re-laid drawing is a second thing to get wrong. The numbers live in the table below,
  which is also what a screen reader and a printer read.

## What it deliberately is not

No dependencies, no critical path, no percent complete, no resource levelling, and no colour
by status. Those are claims about the future. This file knows the dates it was given, and a
picture that implies a critical path it does not hold is worse than a table that never
claimed one. Status stays a column in the table, where it is a value rather than a colour a
reader has to decode with a legend.

## On a phone

The drawing keeps a minimum width so its text stays at 14 px, and pans sideways inside its
own box rather than shrinking. The page itself never scrolls sideways, and every row is in
the table below at full size. That is the same trade `../23-process-diagram/` makes, for the
same reason: a drawing scaled to fit a phone is a drawing nobody can read.
