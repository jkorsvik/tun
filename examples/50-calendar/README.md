# 50. When in the week, and when in the year

A heatmap (43) compares two categories. This compares *days*: one cell per day, aligned to weekday
rows, so "Mondays are always bad" and "August is quiet" become shapes instead of two hundred rows
of a table.

The trap is that the alignment **is** the claim. A calendar whose week starts on the wrong day
invents a pattern out of its own layout, and nothing on the page says so. The second trap is
quieter: a day with no data drawn in a pale shade reads as "a little", which is a measurement
nobody took.

```bash
python3 examples/50-calendar/generate_data.py

python3 tools/build_calendar.py \
  --data examples/50-calendar/hendelser.csv \
  --date Dato --value Antall --clamp 40 \
  --title "Hendelser per dag, 2026" \
  --source "Syntetisk eksempeldata (hendelser.csv)" \
  --requested-by "Driftsavdelingen" \
  --out examples/50-calendar/kalender.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_calendar.py
uv run --extra verify python3 tools/verify_viewports.py examples/50-calendar/kalender.html
uv run --extra verify python3 tools/verify_a11y.py examples/50-calendar/kalender.html
```

## The rules it carries

* **the week starts on Monday, and the page says so.** The gate measures every cell's row against
  its own weekday in a real browser, so a wrong offset cannot ship.
* **a day with no data is hatched, never pale.** Missing days are counted in the summary and the
  hatch is a legend entry of its own.
* **zero is a value.** A day that recorded 0 takes the lowest band and is never the same cell as a
  day with no row.
* **the scale is round, and printed.** Edges come from a 1-2-5 ladder snapped to round numbers,
  so the legend reads `0–10, 10–20, 20–30, ≥ 30` rather than five arbitrary boundaries.
* **`--clamp` is a declared choice, not a hidden one.** One 96-count day against a typical 18
  collapsed the whole year into two shades on the first build, which hid the weekday rhythm the
  page **is**. The top band then prints a minimum, the page says how many days were folded, and
  both tables keep the true numbers.
* **one value per day.** Several rows on one date is refused by name: a calendar cannot show a
  sum and a level at once without saying which it drew.
* **the tables are half the answer**: seven weekday means with their min and max, and the ten
  highest days, so a single peak can be looked up.

## Refusals

A duplicated date (named, with its count), a `dd.mm` date, a column of words, a range past 400
days, and a `--clamp` at or below the lowest value.

## What the suite measures

`tests/test_calendar.py` is 35 checks and three mutations. It re-derives from the extract: the
hatched set against the days the CSV does not hold, every shaded day's band against the edges
**printed in the legend**, the zero days against the lowest band, and the committed file rebuilt
byte for byte from a pinned clock.

In **Chromium** it measures every cell's vertical centre against its weekday row (3 px tolerance)
and that all seven weekday labels are at least 14 px. That is the check that makes the alignment
a fact rather than a comment.

Three mutations: a missing day drawn as the lowest band, the week shifted to start on Sunday, and
one shade for every day. Each trips exactly one check.
