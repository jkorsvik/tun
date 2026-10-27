# 31. The file that answers back

**Reader:** user — you want an artefact out of your own data and do not intend to change the toolkit.

ROADMAP A18. Every other artefact this repository builds is one-way: you make it, someone
opens it, and if they disagree with a number the only route back is a screenshot and a
sentence that names neither the row nor the build. "Tallet for mars ser feil ut" costs two
rounds of e-mail before anyone knows which of 776 rows is meant, or whether the reader was
looking at last week's version.

The review layer closes that loop without adding a server. The reader comments on rows
inside the file they already have, copies one text block, and pastes it into whatever they
already use to talk to you. A tool on your side reads the block and finds the rows again.

```
file with --annotate  ->  reader clicks a row, writes a comment
                      ->  "TUN-REVIEW 1" block on their clipboard
                      ->  pasted into an e-mail, a Teams message, an issue
                      ->  tools/read_review.py finds the row and the figure
```

## What the reader does

The artefact gets one button at the foot of the page, under the provenance block. Press
it, the table becomes clickable, click a row, type, add. The block appears, with a **Kopier**
button. Nothing is sent from the file: no fetch, no upload, no account, no token. What the
reader copies is assembled from what is already on the page.

With scripting off (Quick Look on iOS and macOS, a hardened viewer) the same section is a
sheet of text instead of a button: the build identity, the column order, and three of their
own rows already filled in, with a blank comment line under each. They can write the block
by hand and paste it into an e-mail. That is the honest degradation, and it is the reason
the block is `key: value` lines rather than JSON.

## What the block carries

```
TUN-REVIEW 1
artefact: Saksbehandling: kostnad per sak
file: saksbehandling.html
built: 2026-10-24 10:00 UTC
rows: 96
source: Syntetisk eksempeldata (saksbehandling.csv)
keys: Maaned, Enhet, Sakstype, Kanal
measure: Kostnad
--
row: 2026-03 | Sør | Etterlevelse | Nettbank
value: 79 200
comment: Dette er ikke tallet vi fikk oppgitt.
```

Three decisions are load-bearing here.

**The keys are the same in both languages.** The block is a data format, not prose: one
vocabulary for `read_review.py` to parse, whatever `--lang` the page was built with. Only
the words on screen are translated (`templates/i18n/_annotate.strings`).

**A row is named by its categorical cells, not by every cell.** A number that changes
between builds must not make the row unfindable, so the measure is never part of the name,
and neither is any other numeric column. On the example data the four categorical columns
are unique per row; where a source file holds genuine duplicates, the report says how many
rows share the name instead of pretending to know which one was meant.

**The block carries what the reader saw.** The `value:` line is the figure as displayed,
not the row's current figure. That is what makes a disagreement visible: the file holds one
number, the reader holds another, and the report shows both rather than choosing.

A register has no single measure, so there the block carries `cells:` instead: every numeric
column of the record, as the reader saw it (`cells: Dager=119; Belop=48518`). That does two
jobs. The analyst sees the figures the comment is about without opening the file, and when
several records share the same text cells, which a grouped register makes common, the
figures narrow the match to one before the report has to say "38 rows share that key".

## What you do with it

```bash
pbpaste | python3 tools/read_review.py saksbehandling.html -
python3 tools/read_review.py saksbehandling.html tilbakemelding.txt --out tilbakemelding.md
```

It reads the data out of the artefact itself, bundled `window.DASHBOARD_DATA` or the
`data.js` beside it in paired mode, so it needs no source file and no connection: the file
the reader had is the file that answers. For each comment it reports:

| the block | the file | what the report says |
|---|---|---|
| a row that exists, same figure | yes | `same` |
| a row that exists, a different figure | yes | `**block says 79 200**` |
| a row the file does not hold | no | `**not found**` |
| a block from another build | other `built` | the whole report is headed with the mismatch |

A missing row and a different figure are the findings, not faults in the block. The reader
is describing what they saw; the file is the other half of the disagreement. Nothing is
decided for you, which is the right division: only a person can say whether the invoice or
the extract is wrong.

## What a pasted mail does to it

Mail clients quote (`>` on every line), wrap long lines, and append a signature. The parser
treats all three as normal input:

* a leading run of `>` and a space is stripped from every line;
* a line that is not a field continues the field above it, so a wrapped comment is joined
  back together;
* a blank line ends a field, so a greeting above the block and a signature below it are
  reported as ignored instead of being glued onto the last comment.

Anything the parser did not use is listed in the report under `notes from the block`. A
comment is never silently dropped.

## The second artefact: a row, not a number

The register needed the block to carry `cells:`, because a record is a set of figures and one
number would be a choice the reader did not make. The comparison
(`build_comparison.py --annotate`) needed the opposite: one figure, and a reason why it can be
absent.

A comparison is the artefact where a reader disputes a *row*. `Nordvest` is in September and
not in October. Nothing is wrong with the number, and there is no number: the key is gone. So
the row carries `data-status` in the markup, the block carries `status: gone`, and the report
prints `same (gone)` beside the comment rather than a mismatch against an empty cell.

Three defects had to be fixed before that was true, and none was visible by reading:

* **A key cell that carries a tag reads as the wrong name.** The cell text is
  `Nordvest borte`, because the tag span lives inside it, so the comment was filed against a
  key the file does not hold. The artefact now puts its own key on the row (`data-key`), and
  the layer prefers it over the cell text.
* **The page writes a real minus sign (`U+2212`) and a leading plus.** Both are correct
  typography and neither is a number to a parser, so every comparison figure arrived as text
  and every row read as a changed value. `read_review.py` normalises both now.
* **The comparison's rows use short field names.** `k, b, a, d` is what a script wants; the
  block speaks the visible columns. The two vocabularies meet once, in `artefact()`, which is
  the loader that already had to know two shapes.

## Cost, and what it does not do

* **Off unless asked.** `--annotate` is a flag on `tools/build_dashboard.py`. Without it the
  artefact is byte for byte what it was, and `tests/test_review_roundtrip.py` asserts that.
* **Two artefacts, not six.** The layer is on the rows dashboard and on the register, which
  are the two that hold records a reader can disagree with line by line. The cube,
  comparison, timeline and slide-deck builders do not have it; each would need its own
  notion of "a row". Adding one is three things: the table's id, how that template names a
  column on a cell (`data-col` on the header, `data-label` on the cell), and which columns
  are the row's name.
* **Not a workflow.** Nothing stores comments, nothing notifies anyone, nothing merges two
  readers' blocks. If that is what you need, the file is the wrong shape and
  [the honest exit](03-skill-tree.md) applies.
* **Size.** The layer adds about 11 KB to the file: one style block, one section, one script.

## Where the parts live

| | |
|---|---|
| `templates/_annotate.html` | the layer: style, markup, script |
| `templates/i18n/_annotate.strings` | the words on screen, `nb` and `en` |
| `tools/review_layer.py` | fills the layer and puts it in the page |
| `tools/build_dashboard.py` | `--annotate` |
| `tools/read_review.py` | parses a block, finds the rows, writes the report |
| `examples/36-review-roundtrip/` | the worked example: data, artefact, block, report, all rebuildable |
| `examples/32-rows-register/` | the same layer on a grouped register: bands and the empty-search row are not records |
| `tests/test_review_roundtrip.py` | 71 checks, including the browser half for both artefacts |

The browser half is not optional. A layer that no one has clicked is a layer that does not
work, so the suite opens the file from a `file://` URL in Chromium, presses the button,
clicks a row, types, adds, and hands the block the browser produced to `read_review.py`.
If Playwright is missing the suite fails rather than skipping
([why](12-maintainability-conventions.md)).
