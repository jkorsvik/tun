# 26 — The KPI board: rates, English chrome, and a feedback link

Four builder flags had no example. This one uses all four on one artefact, so the
things a skill or a person can now do are visible rather than documented:

| flag | what it adds here |
|---|---|
| `--kpis total,per_period,rows,distinct` | a KPI strip you choose, instead of the four cards the builder always made |
| `--measure-kind rate` | tells the builder the measure is a per-unit quantity that still adds across rows, so it stops offering a mean-per-row |
| `--lang en` | English chrome from the same data, with the column names left as the source wrote them |
| `--feedback-to` | a "Gi tilbakemelding" / "Give feedback" link that opens a prefilled mail or a new issue |

Two artefacts, same data: [`sykefravaer.html`](sykefravaer.html) in Norwegian with
a `mailto:` link, and [`sick-leave.html`](sick-leave.html) in English with an
issue URL.

## The claim this example defends

> A rate is not a sum, and a builder that quietly averages it produces a number
> that means nothing.

Sick-leave **days** add up: across units, across months, into a total you can put
in a sentence. The mean per *row* does not: with 18 months and 8 units, it is
"days per unit-month", which nobody reports. So this build asks for
`--measure-kind rate`, and the builder refuses the misleading card:

```
$ python3 tools/build_dashboard.py ... --kpis mean --measure-kind rate
error: --kpis mean is the mean per row, which misleads for --measure-kind rate.
       Drop it, or use per_period.
```

A guard that only exists in prose is a wish. That message is the guard.

## Reproduce it

```bash
# 1. the data: seeded, stdlib only, 144 rows, invented
python3 examples/26-kpi-board/generate_data.py

# 2. the Norwegian board, with a feedback address
python3 tools/build_dashboard.py \
    --data examples/26-kpi-board/sykefravaer.csv \
    --title "Sykefravaer per enhet" \
    --dimension Enhet --measure Sykefravaersdager --time Maaned \
    --filters Seksjon,Enhet \
    --kpis total,per_period,rows,distinct --measure-kind rate \
    --source "Syntetiske data, 144 rader (8 enheter, 18 maneder)" \
    --requested-by "HR" --lang nb --feedback-to hei@tun.community \
    --out examples/26-kpi-board/sykefravaer.html

# 3. the English board, with an issue URL
python3 tools/build_dashboard.py \
    --data examples/26-kpi-board/sykefravaer.csv \
    --title "Sick leave by unit" \
    --dimension Enhet --measure Sykefravaersdager --time Maaned \
    --filters Seksjon,Enhet \
    --kpis total,per_period,rows,distinct --measure-kind rate \
    --source "Synthetic data, 144 rows (8 units, 18 months)" \
    --requested-by "HR" --lang en --feedback-to https://github.com/example/tun/issues/new \
    --out examples/26-kpi-board/sick-leave.html

# 4. prove both render, filter, and stay above the floor
uv run --extra verify python tools/verify_dashboard.py examples/26-kpi-board/sykefravaer.html --engines all
uv run --extra verify python tools/verify_viewports.py examples/26-kpi-board/sick-leave.html
```

`--engines all` is Chromium, Firefox and WebKit. A reader may open the file in
any of the three, so a template change is only safe when all three agree.

## What to look at

- **The KPI strip.** Four cards, the ones asked for, in that order. `per_period`
  divides the total by the number of months in the data, which is the number a
  manager actually asks for.
- **The chart labels.** 14 px, at every width, because `tools/verify_viewports.py`
  measures what a reader sees rather than what the CSS declares.
- **The feedback link.** It is a 44 × 44 px target, not a 17 px line of text: the
  same gate found the original one and it was fixed in `templates/_feedback-link.html`.
- **The provenance block.** Source, extract time, build time, requester, row count.
  A number nobody can trace back is a liability.

## The data is invented

`generate_data.py` seeds `random.Random(26)`, uses generic unit names, and contains
no real organisational unit, no real person and no real reporting line. Do not replace it
with real sick-leave data: `work/` is where a real deliverable lives, and it is
gitignored for that reason (`AGENTS.md`, rule 6).
