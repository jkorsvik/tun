# 29 — One lead, two files: the audience split

The smallest honest answer to the question every dashboard project gets: *"can't we just
filter it so each team sees only their own numbers?"*

No. A browser filter is a suggestion. The rows are in the file, and anyone who opens the
file with a text editor sees them. The boundary has to be the file (AGENTS.md rule 1), so
the split happens before the data is written: one extract per audience, one dashboard per
extract, both built by the same command.

This example is that pair, from one made-up dataset.

| File | Rows | Total | Who it is for |
|---|---|---|---|
| `alle.html` | 24 | 5 483 000 kr | the sales lead, all three teams |
| `team-nord.html` | 8 | 1 916 000 kr | team Nord, and nobody else |

Same shell, same builder, same flags. Two files that look identical and share no rows.

## What is in here

- `generate_data.py` — writes both extracts from one table of rows: `salg-alle.csv` and
  `salg-team-nord.csv`. Deterministic, no clock, no seed. Run it from this directory.
- `salg-alle.csv`, `salg-team-nord.csv` — the two extracts. The narrow one is a filter of
  the wide one *made on disk*, not in a browser.
- `alle.html`, `team-nord.html` — the two dashboards.

## Rebuild

```bash
cd examples/29-audience-split
python3 generate_data.py            # writes both extracts

cd ../..
python3 tools/build_dashboard.py \
    --data examples/29-audience-split/salg-alle.csv \
    --title "Salg per produkt og måned, alle team" \
    --dimension Produkt --measure Belop --time Maaned --filters Produkt \
    --source "Syntetiske salgstall (generate_data.py) — salg-alle.csv" \
    --requested-by "Salgssjef" \
    --out examples/29-audience-split/alle.html

python3 tools/build_dashboard.py \
    --data examples/29-audience-split/salg-team-nord.csv \
    --title "Salg per produkt og måned, team Nord" \
    --dimension Produkt --measure Belop --time Maaned --filters Produkt \
    --source "Syntetiske salgstall (generate_data.py) — salg-team-nord.csv" \
    --requested-by "Teamleder Nord" \
    --out examples/29-audience-split/team-nord.html
```

`--requested-by` differs on purpose: a file nobody can trace back is a liability, and the
two files have different owners.

## Prove it

Both files render, and the numbers on them are the extract's numbers:

```bash
python3 tools/verify_dashboard.py examples/29-audience-split/alle.html
python3 tools/verify_dashboard.py examples/29-audience-split/team-nord.html
```

And the boundary itself, which no screenshot can show:

```bash
python3 tests/test_audience_split.py
```

Every row of this example is checked by reading the two pages back, not by trusting the
build log:

- the narrow page carries exactly the narrow extract's eight rows, and the wide page
  exactly the wide extract's twenty-four;
- every row in the narrow page's payload belongs to team Nord;
- none of the four sellers from the other two teams appears **anywhere** in the narrow
  file, and the same four names are found in the wide file, so the check is not blind;
- each page's rows sum to its own extract's total, read from the CSV;
- a mutation control: append one row from another team to a *copy* of the narrow extract,
  rebuild, and the checks above must fire. A test that passes because it inspected
  nothing cannot pass this.

## What this does not solve

- **Two files is two things to update.** A monthly refresh is two builds, and a build
  whose extract came from the wrong query is a leak that no test here can see: this
  proves the *files* are separate, not that the *extract* was right. Check the row count
  against the source system before you rebuild, and read the provenance line in the file.
- **The folder is the permission.** Whoever can open `team-nord.html` can read it. Put the
  files in the folders that already have the right audience, and share the link to the
  file, not the folder above it.
- **Aggregation is not anonymisation.** Eight rows for two sellers still describes those
  two sellers. If the audience must not know that, the numbers need to be coarser, which
  is a different build (see [`examples/27-survey-board`](../27-survey-board/README.md) for
  withholding small cells).
