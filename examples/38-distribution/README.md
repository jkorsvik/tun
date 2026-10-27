# 38. The shape of the data, not its total

Every other artefact this engine builds answers a question about a total. A total says
nothing about whether a typical case is typical: three cases of 1, 1 and 40 days have the
same sum as eleven cases of 4, and an average of 14 describes neither. Case handling time,
claim size, transaction amount, response time: the same thing is true of all of them, and
the figure people quote is the one the shape makes misleading.

This is the artefact for that question. One panel per unit, the same intervals in every
panel, and the median drawn where it actually sits.

```bash
python3 examples/38-distribution/generate_data.py

python3 tools/build_distribution.py \
  --data examples/38-distribution/saksbehandlingstid.csv \
  --measure-col Dager \
  --group-col Enhet \
  --title "Saksbehandlingstid per enhet" \
  --source "Syntetisk eksempeldata (saksbehandlingstid.csv)" \
  --requested-by "Fagavdelingen" \
  --out examples/38-distribution/behandlingstid.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_distribution.py
uv run --extra verify python3 tools/verify_viewports.py examples/38-distribution/behandlingstid.html
uv run --extra verify python3 tools/verify_a11y.py examples/38-distribution/behandlingstid.html
```

## The six rules it carries

* **Every case lands in exactly one interval, and the table's total is the row count.** The
  lower edge is inclusive, the upper edge is exclusive, and the last interval is closed at
  the top so the largest value is never the one that falls off the axis. The suite recounts
  the source rows using only the edges printed on the page, and requires the printed counts
  to match. A bar chart whose counts do not add up is the one defect a reader cannot see.
* **The edges are printed, in the caption and in every table row.** They come from a 1-2-5
  ladder, because an axis with edges at 3.47 and 6.94 is an axis nobody checks. A different
  width draws a different picture of the same rows, which is exactly why the width is on the
  page rather than in the builder's head.
* **The mean never appears alone.** The stat line carries the case count, the median, the
  mean, p90 and the largest value together. When the mean runs 1.5 times the median or more,
  the page says so in words, because that gap is the whole reason this artefact exists.
* **The median is allowed to be an average; p90 is not.** The median of an even number of
  cases is the average of the two middle ones, which is what a median is. p90 is the nearest
  *observed* value, because the page claims "90 per cent of the cases sit at or below it" and
  an interpolated figure between two cases would make that claim false.
* **A value that is not a number is refused by file and line.** Skipping it would move the
  total that the first rule is checked against. An empty measure is refused too, unless
  `--drop-missing` is passed, and then the page prints how many rows it left out.
* **There is no script.** A filter would re-lay the drawing, and what a script would have
  given the reader is already there: every count, in a table, per interval and per unit.

## Small groups, and why the floor is a flag

A histogram of four cases is a picture of four cases. `--min-group 5` leaves such a group out
of the drawing and names it under the picture with its count, so the page cannot pretend a
three-case unit has a shape. It is a flag rather than a default because the answer depends on
what the page is for:

```bash
python3 tools/build_distribution.py ... --min-group 5
```

The numbers are not hidden by it, they are in the source, and the page says so.

## What it deliberately is not

No mean without a median, no trend, no forecast, no fitted curve, no "normal range". A
distribution that runs off the top of the axis is a real finding and is left alone: a unit
whose longest case is 60 days against a median of 6,5 is the thing its manager needs to see,
not an outlier to be smoothed away.

The intervals are a presentation choice and the page says so. Nothing here claims the data
is normal, and nothing labels a case an outlier, because that is an argument for a person to
have, not a builder to make.

## Two intervals, one page

All panels share the same intervals, so a reader can compare a unit against a unit across
the page. They do **not** share a count axis, because one large unit would flatten a small
one into a line; every bar carries its own number instead, so the height is a cue and the
text is the figure.

## On a phone

The drawing keeps a minimum width so its text stays at 14 px, and pans sideways inside its
own box rather than shrinking. The table below is at full size, and the table is where a
reader checks a number anyway.
