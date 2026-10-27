# 31. Two questions at once, and why that has an all-or-nothing rule

A survey board counts one question at a time. The moment someone asks "and how do those
two answers line up", the arithmetic changes: multiplying two questions is exactly how a
small group becomes a nameable person, so a cross-tab needs its own rule rather than the
per-cell floor the rest of the board uses.

This example is that rule, with the data built to show both outcomes:

* `Jeg får svar på det jeg spør om` × `Verktøyene jeg bruker passer til oppgaven`: every
  one of the 25 combinations holds five answers or more, so the table is printed with its
  row and column totals.
* `Jeg vet hvem som bestemmer i saken` × `Jeg har fått opplæring i verktøyene`: nine
  people answered the second question, so combinations fall under five and the table is
  **not** printed. The page says why in place of the table.

## The rule, and the reason it is blunt

The board prints the total for each question. That single fact decides the rule: with the
total showing, one withheld cell is not hidden at all, because the reader subtracts the
visible cells from the total. Partial suppression in a cross-tab therefore buys nothing
and hiding a second cell to block the subtraction starts a cascade that ends with the
whole matrix hidden anyway.

So: **a pair is printed only when every combination reaches the floor.** One combination
under five removes the table, and the page shows a reason instead of a number. A zero
cell is not identifying and does not block anything.

Two limits, stated in the page and here:

* the rule protects a count, not a pattern. The same group described across several
  tables is still a group, and nothing in this file notices that;
* it is deliberately coarse. On a 5 by 5 matrix a single small cell costs the whole
  table. If you need the table, collect more answers; do not lower the floor.

## A cross-tab needs one row per respondent

`--cross` needs `--wide`: one row per respondent, one column per question. It is the row
boundary that says which answers came from the same person, and the long format does not
carry one. Given a long-format file the builder refuses and says so rather than joining
answers by position, which would invent a table nobody could check.

The respondent number exists only in memory to join the two answers. It is never written
into the page: the file a reader gets holds counts, never people.

## Build it

```bash
python3 examples/31-survey-crosstab/generate_data.py

python3 tools/build_survey_dashboard.py \
  --data examples/31-survey-crosstab/survey-wide.csv --wide \
  --questions "Jeg får svar på det jeg spør om,Verktøyene jeg bruker passer til oppgaven,Jeg vet hvem som bestemmer i saken,Jeg har fått opplæring i verktøyene" \
  --cross "Jeg får svar på det jeg spør om|Verktøyene jeg bruker passer til oppgaven" \
  --cross "Jeg vet hvem som bestemmer i saken|Jeg har fått opplæring i verktøyene" \
  --segments Enhet,Rolle \
  --title "Arbeidsmiljø 2026 — krysstabeller" \
  --source "Syntetisk eksempeldata (survey-wide.csv)" \
  --requested-by "HR" \
  --out examples/31-survey-crosstab/survey-crosstab.html
```

The cross-tabs cover the whole selection, not the filter. Filtering hides them and shows
a note saying so: recomputing the rule under a filter would be a second implementation of
it in JavaScript, and the day the two disagreed the page would print a number it should
have withheld. One implementation, one place.

## Prove it

```bash
uv run --extra verify python tests/test_survey_crosstab.py
```

The suite re-derives the matrix from a file it writes itself and requires the printed
table to match, reconciles every total, proves the floor decides by feeding the same pair
a thick file and a thin one, checks the long-format refusal, checks both languages, and
loads the page in a browser to confirm the table is there, that a filter hides it, and
that reset brings it back.
