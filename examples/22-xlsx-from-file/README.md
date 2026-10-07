# 22 — Reading a real .xlsx from file://, with no library

An `.xlsx` is a ZIP archive holding SpreadsheetML XML. `xlsx-from-file.html` unpacks one
with nothing but what a modern browser already ships: `DecompressionStream('deflate-raw')`
to inflate each ZIP entry, and `DOMParser` to read the XML parts. No xlsx library, no
bundler, one file.

This was measured once on a real, 9-sheet workbook: **160–250 ms** to parse, in Chromium,
Firefox and WebKit. This example reproduces the same pattern against a small synthetic
workbook so the claim can be checked by anyone, without a real spreadsheet lying around.

## Why this matters for Tún

`fetch()` and `XMLHttpRequest` are both blocked from a `file://` page (docs/01 row 16). So
a dashboard can't read a user's spreadsheet by asking for it — the user has to hand it
over via `<input type="file">`, a real user gesture. Once the bytes are in hand, though,
nothing stops a page from being its own unzip-and-parse tool. This is the building block
`dashboard-data`-style skills would use to accept ".xlsx" input directly on a `file://`
page, with zero dependencies to vendor.

## What's in the workbook

`build_workbook.py` writes `demo-workbook.xlsx` (not committed — see below) with three
sheets, covering every cell shape the HTML parser has to handle:

| Sheet | Rows (incl. header) | Exercises |
|---|---|---|
| `Produkter` | 6 | shared strings, plain numbers, **an explicit empty cell** (Lagerbeholdning for "Penn sort"), a real Excel date serial |
| `Ordrer` | 5 | shared strings incl. æøå names (Åse Lund, Per Øverland), numbers, dates |
| `Kommentarer æøå` | 4 | æøå **in the sheet name itself**, plus free-text comments using every Norwegian letter: æ Æ ø Ø å Å |

Dates are written as real Excel serials (`xl/styles.xml` carries one custom date number
format, `yyyy-mm-dd`) — not pre-formatted strings. The HTML parser has to read the style
sheet, recognise the date format, and convert the serial back with the same 1899-12-30
epoch Excel itself uses (including the deliberate 1900-leap-year bug every spreadsheet
tool reproduces for compatibility).

All data is invented: generic product names, generic customer names, no real organisation
or person.

## Measured parse times

From a verify run on this machine (synthetic 3-sheet workbook, so faster than the
160–250 ms measured on a real 9-sheet one — the point is that it works in all three
engines, not the absolute number):

| Engine | Parse time |
|---|---|
| Chromium | 4.1 ms |
| Firefox | 5.0 ms |
| WebKit | 10.0 ms |

Re-run `verify_xlsx_from_file.py` to get current numbers — they vary run to run like any
micro-benchmark, and the table above is one real, observed sample, not a promise.

This is a different format string on the same API docs/01 already relies on for the
cube template (`DecompressionStream('gzip')`, verified there in Chromium only). It is not
the same claim — `deflate-raw` and `gzip` are separate format strings an engine could
support independently — but it is one more real data point for the open question "is
`DecompressionStream` available in every browser the tenant actually deploys", now
covering Chromium, Firefox **and** WebKit for the `deflate-raw` variant specifically.
Still unverified: the actual locked-down browser versions in the estate, not just current
desktop engines.

## The limitation

Opening the file **does not** load the workbook automatically. `fetch('./demo-workbook.xlsx')`
from a `file://` page is blocked in every engine tested (docs/01 row 16) — the user must
click "Choose File" and pick it, a real gesture, even though the file can sit right next
to the HTML. There is no way around this from inside the page; it's the same constraint
`docs/01` row 19/20 already documents for other file-reading approaches.

## Reproduce

```bash
# 1. Build the synthetic workbook (stdlib only: zipfile + hand-written XML)
python3 examples/22-xlsx-from-file/build_workbook.py

# 2. Open examples/22-xlsx-from-file/xlsx-from-file.html directly in a browser
#    (double-click it, or a file:// URL) and pick demo-workbook.xlsx via the button.

# 3. Automated proof, in Chromium, Firefox AND WebKit:
uv sync --extra verify
uv run playwright install chromium firefox webkit   # once
uv run --extra verify python examples/22-xlsx-from-file/verify_xlsx_from_file.py
```

Must print `✓ PASS`. Then **look at the screenshots** it writes
(`xlsx-from-file.<engine>.verify.png`, gitignored like every other `*.verify.png` in this
repo) — a clean exit code is not evidence a table rendered correctly.

### Mutation self-check

`verify_xlsx_from_file.py` also proves it can actually fail, not just pass:

```bash
python3 examples/22-xlsx-from-file/verify_xlsx_from_file.py --mutation-check
```

This breaks shared-string resolution in `xlsx-from-file.html` on purpose, re-runs the
Chromium checks expecting failure, restores the file byte-for-byte, and reports what it
saw. Last run: 3 checks failed as expected ("Penn sort" row, "Åse Lund" row, and the æøå
comment text all disappeared once shared strings stopped resolving), and the file was
confirmed restored with `git diff` showing no changes afterwards.

## Why `demo-workbook.xlsx` isn't committed

It's deterministic output of `build_workbook.py` — three sheets of invented data,
regenerated identically on every run. Committing it would need a one-line exception in
`tools/check_no_real_data.py`'s `ALLOWED_DATA` for no real benefit (same reasoning
`examples/03-cube-dashboard/` already applies to its much larger `transaksjoner.csv`).
`.gitignore` excludes this one file by exact path; `verify_xlsx_from_file.py` rebuilds it
automatically before every run.

## Files

- `build_workbook.py` — writes `demo-workbook.xlsx`, stdlib only (`zipfile` + hand-rolled
  SpreadsheetML XML strings, no `openpyxl`)
- `xlsx-from-file.html` — the self-contained parser + table renderer
- `verify_xlsx_from_file.py` — Playwright verification across Chromium, Firefox, WebKit,
  plus the `--mutation-check` self-test
