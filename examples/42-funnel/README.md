# 42. How many reach each stage, and where the cohort leaks

Most operational reporting is a funnel: how many cases start, how many get assessed, how many
are decided, how many are paid out. It is drawn badly almost everywhere, in two ways. The
stages are inferred from the data rather than declared, so the order is a guess presented as a
fact. And the drop between two stages is left as a gap in a picture, when the number a reader
actually wants is the difference.

```bash
python3 examples/42-funnel/generate_data.py

python3 tools/build_funnel.py \
  --data examples/42-funnel/soknader.csv \
  --id Soknadsnr --stage Status \
  --stages "Mottatt,Vurdert,Innstilt,Utbetalt" \
  --title "Søknader gjennom behandlingen" \
  --source "Syntetisk eksempeldata (soknader.csv)" \
  --requested-by "Saksbehandlingen" \
  --out examples/42-funnel/tratt.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_funnel.py
uv run --extra verify python3 tools/verify_viewports.py examples/42-funnel/tratt.html
uv run --extra verify python3 tools/verify_a11y.py examples/42-funnel/tratt.html
```

## The six rules it carries

* **The stages are declared, never inferred.** `--stages "Mottatt,Vurdert,Innstilt,Utbetalt"`
  gives the order. Inferring one from the data would be a guess with a picture drawn on top of
  it, and a stage the file holds but `--stages` omits is refused by name.
* **The nesting is checked, because that is what makes it a funnel.** Reaching stage n+1 means
  the same record passed stage n. A record that appears at a later stage without an earlier one
  is a defect in the extract, so the builder refuses and names the pair and the count. With
  `--allow-skips` it draws anyway, and then the page says on its face which pair is out of
  order instead of presenting four counts as a conversion.
* **The width is the only dimension carrying the count.** Every bar has the same height. Two
  scaled dimensions turn a fall of half the records into a loss of three quarters of the area;
  the suite asserts both the equal heights and the width ratios.
* **Both conversion rates are printed.** Of the first stage (overall) and of the stage before
  (step). They answer different questions, and a page that shows one invites the reader to
  answer the other with it.
* **The drop is a number, not a gap.** "84,0 % · −64" beside the stage, and a column for it in
  the table.
* **The worst step is named in words**, computed from the counts: *"Det største fallet er
  mellom Innstilt og Utbetalt: 72 saker, 25,5 % av dem som nådde Innstilt."* The suite decides
  which pair that is itself and requires the sentence to name it.

## A duplicate row is counted once, and the page says how many

An extract that joins two event tables easily holds the same `(record, stage)` row twice. The
count is distinct records per stage, so a duplicate cannot inflate it, and the provenance line
prints how many were collapsed rather than hiding the fact that the extract is not clean.

## What it is not

Not a process description and not a claim about why records fall out. It counts the cohort
that passes through the stages it was given: the reasons a case stops are a different report,
and this file has no column for them.

There is no script. A filter would re-lay the drawing, and the drawing is the claim.

## What the suite measures

`tests/test_funnel.py` is 50 checks: the distinct-record counts and the nesting from the
extract, the one-dimensional geometry, both rates and the lost figures as this suite's own
subtractions, the worst-step sentence, six refusals, the duplicate rule, both languages, the
committed file rebuilt byte for byte from a pinned clock, and four mutations — including a bar
whose width is the square root of its count, which is exactly how a funnel exaggerates.
