# 32. Sometimes the question is "give me the list"

Half of what people share as a spreadsheet is not a chart waiting to happen. It is a list
someone wants to search: the open deviations, the cases past their deadline, the contracts
in that unit. Tún could already count rows and draw them; it could not hand over the rows
themselves with a search field that works from a `file://` page in a synced folder.

This example is that artefact. `avvik.csv` holds 1,200 synthetic deviation cases; the
build writes one self-contained file that searches, sorts and pages them, and refuses to
be anything other than what it says.

## The four rules it carries

* **Every row that went in is in the file.** A reader with the file can search all of it,
  so a register is not a filtered view. When two audiences must see different rows, the
  split happens before the build and produces two files (AGENTS rule 1: the boundary is
  the folder, not a filter inside the file). The builder drops a column that was not named
  *before* anything is written — `Saksbehandler` is in the CSV and is not in this page.
* **A numeric column sorts as a number.** Sorting `9` after `10` is a silent wrong answer,
  and a table that looks sorted is harder to distrust than one that looks broken. An empty
  cell sorts last in both directions, because "no amount" is not zero.
* **A search that matches nothing says so, in words, in the table body**, and the count
  reads `0 av 1 200` rather than standing still.
* **A cell is text.** A value holding `</script>` cannot end the script element: the payload
  is escaped at `<`, `>` and `&`, and a hostile cell is a check in the suite, not an
  assumption. A CSV cell once ran script in this repository.

## The no-JS view is the first page, not a banner

The first 25 rows are written into the markup, at the opening sort, with the count and one
sentence saying it is the first page of a longer list. A reader whose browser will not run
the script sees the list; they lose the search, and the page tells them so. `Apple Quick
Look`, a locked-down browser and a mail preview all land here.

## Rebuild

```bash
python3 examples/32-rows-register/generate_data.py

python3 tools/build_register.py \
  --data examples/32-rows-register/avvik.csv \
  --title "Avvik 2026" \
  --columns Saksnummer,Enhet,Avvik,Mottatt,Status,Dager,Belop \
  --numeric Dager,Belop --sort Dager --desc \
  --source "Syntetisk eksempeldata (avvik.csv)" \
  --requested-by "Kvalitet" \
  --out examples/32-rows-register/register.html
```

## Verify

```bash
uv run --extra verify python3 tests/test_register.py --engines chromium,webkit
uv run --extra verify python3 tools/verify_viewports.py examples/32-rows-register/register.html
uv run --extra verify python3 tools/verify_viewports.py examples/32-rows-register/avvik-per-enhet.html
uv run --extra verify python3 tools/verify_a11y.py examples/32-rows-register/avvik-per-enhet.html
```

The suite is 75 checks: the group bands (counts and sums checked against arithmetic the suite
itself does on the CSV), the file's contents against the CSV, three refusals at build time,
and in two engines the sort (numeric and reversed), the search, the empty result, paging,
reset, the 14 px and 44 px floors, 320 px with no sideways scroll, the hostile cell, and
the no-script page.

## Grouping, when a list is easier to read in parts

`avvik-per-enhet.html` beside this README is the same rows, grouped:

```bash
python3 tools/build_register.py \
    --data examples/32-rows-register/avvik.csv --title "Avvik per enhet" \
    --columns Enhet,Status,Dager,Belop --numeric Dager,Belop \
    --group-by Enhet --sort Dager --desc \
    --source "Syntetisk eksempeldata (avvik.csv)" --requested-by Kvalitet \
    --annotate \
    --out examples/32-rows-register/avvik-per-enhet.html
```

`--group-by Enhet` puts a band above each group: the group's name, how many rows it holds,
and what its numeric columns sum to. The count and the sums are taken over the rows in the
current view, not over the page on screen, so a search narrows them and a group split across
two pages does not appear to hold two different totals. It is still a list: the band states
numbers that are visible in the rows below it, and nothing is aggregated away.

## Commenting on a row

`--annotate` adds one button under the register. Press it, the rows become clickable, click
the row you mean, write, and copy the block it produces. That block names the rows by their
text columns, so whoever built the file finds them again:

```bash
pbpaste | python3 tools/read_review.py examples/32-rows-register/avvik-per-enhet.html -
```

A register is the artefact most likely to come back with "this row is wrong", which is why
it carries the layer too. There is no single figure under discussion in a list, so the block
carries the row's name only, and `read_review.py` prints the row's own numbers beside the
comment. Band rows and the empty-search row are not clickable: neither is a record. The
reasoning, and what the layer does not do, is in
[`docs/31-review-roundtrip.md`](../../docs/31-review-roundtrip.md).

## What it does not do

No pivot and no chart: that is what `../01-hello-dashboard/` and `../27-survey-board/` are
for, and a register that started drawing the numbers would be a worse dashboard. No edit, no
save: a comment is not an edit. It is copied into the reader's own mail or chat, and the file
keeps the bytes it was built with; a file that stored an edit would need a server, which is
the one thing this project does not build. No column chooser — the columns
are the build's decision, made once, so that two readers cannot see two different tables
and believe they compared the same thing.
