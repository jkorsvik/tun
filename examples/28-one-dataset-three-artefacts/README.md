# 28 — one dataset, three artefacts

The same 285 rows, built three ways, so the choice between them stops being a guess.

`saksbehandling.csv` is synthetic: five teams, three priorities, four channels, nine
months, and the hours and case count each combination took. It is small on purpose. What
is being demonstrated is the **choice of artefact**, not the data.

| File | Built by | Answers |
|---|---|---|
| `oversikt.html` | `build_dashboard.py` | "Show me the whole thing, and let me filter it." Every row is in the file, so any question about these rows is answerable. |
| `styringskort.html` | `build_dashboard.py --kpis` | "Is it going the right way, and by how much?" Four numbers, one trend, no chart to read. |
| `kube.html` | `build_cube_dashboard.py` | "Give me every combination, fast, and stay small." Rows are pre-aggregated into cells, so a filter turns into an index lookup. |

Open them side by side. The numbers agree: 7 588 hours in the dashboard's total card and
7 587,8 in the cube's, the difference being the cube's one-decimal formatting of a sum the
dashboard rounds. That agreement is the point of building all three from one file — if the
three disagreed, one of them would be wrong and nobody would know which.

## The commands

```bash
# 1. every row, filterable
python3 tools/build_dashboard.py \
    --data examples/28-one-dataset-three-artefacts/saksbehandling.csv \
    --title "Saksbehandling per team" \
    --dimension Team --measure Timer --time Maaned \
    --filters Prioritet,Kanal \
    --source "Syntetiske data, 285 rader (5 team, 9 maneder)" \
    --requested-by "Prosjekteier" \
    --out examples/28-one-dataset-three-artefacts/oversikt.html

# 2. the four numbers, and nothing to read
python3 tools/build_dashboard.py \
    --data examples/28-one-dataset-three-artefacts/saksbehandling.csv \
    --title "Saksbehandling: styringstall" \
    --dimension Team --measure Timer --time Maaned \
    --filters Prioritet \
    --kpis total,per_period,rows,distinct \
    --source "Syntetiske data, 285 rader" \
    --requested-by "Prosjekteier" \
    --out examples/28-one-dataset-three-artefacts/styringskort.html

# 3. every combination, aggregated
python3 tools/build_cube_dashboard.py \
    --data examples/28-one-dataset-three-artefacts/saksbehandling.csv \
    --dims Team,Prioritet,Kanal --time Maaned --time-grain month \
    --measures "Timer:sum,Antall:sum" \
    --title "Saksbehandling: kube" \
    --source "Syntetiske data, 285 rader" \
    --requested-by "Prosjekteier" \
    --out examples/28-one-dataset-three-artefacts/kube.html
```

Then the same gate every dashboard goes through:

```bash
python3 tools/verify_dashboard.py examples/28-one-dataset-three-artefacts/oversikt.html
python3 tools/verify_dashboard.py examples/28-one-dataset-three-artefacts/styringskort.html
python3 tools/verify_dashboard.py examples/28-one-dataset-three-artefacts/kube.html
```

## Choosing, in one line each

- **Rows dashboard** when someone will ask a question you did not predict. It holds every
  row, so it answers them. The cost is size: 285 rows is 70 KB, and four million would not
  fit the budget at all.
- **KPI board** when the meeting is about one number and its direction. Nothing else to
  look at, so nothing else to argue about.
- **Cube** when the data is large and the questions are combinations of a few fixed
  dimensions. It pre-aggregates, so it stays small; the price is that a cell is a sum, and
  you cannot drill into a row that no longer exists in the file.

No row-level data in any of them beyond what the CSV already holds, and none of the three
is a filter-as-security-control: to show two audiences different numbers, build two files.

## Limits worth knowing

- The three artefacts do not share a look beyond the palette, because they are three
  templates. If a report needs them to feel like one thing, that is a shell, not a build
  flag — `docs/08` explains why there is no multi-block template yet.
- `--filters` takes the columns people are most likely to narrow by. Every filter is a
  dropdown built from the distinct values, so a column with 500 distinct values is a bad
  filter and a column with two is a good one.
- The cube's `--dims` are the cube's axes. Every combination of them becomes a cell, so
  four dimensions with ten values each is 10 000 cells — fine; six is not.
