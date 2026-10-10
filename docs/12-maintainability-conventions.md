# Maintainability conventions — source language and filter independence

**Status:** proposal, not enforced by any tool yet. It covers the one piece of the
original architecture principles that neither `docs/08` nor `docs/11` picked up.

Both rules below already hold in the one example that has real data behind it
(`examples/01-hello-dashboard/`, `examples/02-paired-dashboard/`), but neither is checked
by `tools/verify_dashboard.py` or documented anywhere a future contributor would find
before reinventing the question.

---

## 1. Source data stays in its original language; translation happens only at render

The rule: keep source data (column names, category values) in Norwegian, and
translate only when the dashboard renders — via a lookup table the build script applies,
never by writing a second, translated copy of the source file.

**Why this is a maintainability rule, not a nice-to-have:** a source file that gets
hand-translated once, for one dashboard's English version, silently forks from the
original the next time the source is updated — someone has to remember to translate the
delta by hand, and nothing catches it if they don't. A lookup table applied at build time
can't drift from the source the way a duplicated, translated copy can: there is only ever
one source file, and every rebuild re-applies the same table to whatever is in it now.

**Consequence for `tools/build_dashboard.py` and `build_cube_dashboard.py`:** an
English-language dashboard is a build-time flag plus a translation table
(`{"Region": "Region", "Kanal": "Channel", ...}` — column headers and category labels,
not the numbers), not a separately maintained English source CSV. The page chrome now
has its flag, `--lang` (section 5). The data-label table does not exist yet: your column
names and category values come out exactly as they went in.

## 2. Independent filter dimensions combine with AND logic, never merged into one control

The rule: if a dashboard has more than one filter dimension (region, category,
channel), each is its own control, and selecting values across dimensions narrows the
result set by intersection (AND) — never collapsed into a single multi-select box that
mixes values from different dimensions.

**Why this is a maintainability rule:** a single merged filter control has to encode,
somewhere in its own logic, which values belong to which dimension and how they interact
— that mapping has to be maintained by hand and re-verified every time a category is
added or renamed. Independent AND-combined controls need no such mapping: each control
only ever needs to know its own dimension's values, which the build script already reads
directly from the source data.

**Already true, not yet written down:** every real template
(`single-file-dashboard.html`, `cube-dashboard.html`) already implements filters this way
— one `<select>` per dimension, combined with AND in the filter function. This section
exists so the next dashboard (or the next contributor extending these templates) has a
stated reason to keep it that way, rather than merging controls the first time someone
asks for a "simpler-looking" filter bar.

## 3. Column-oriented storage for large embedded datasets — an observed technique, not yet a rule

Field evidence, from a review of an unrelated external dashboard: rather than embedding rows
as an array of objects, it stores each column as its own typed array (e.g. a `Uint8Array`
per dimension) and computes a boolean mask over row indices for filtering, instead of
filtering an array of objects. For a dataset in the tens of thousands of rows bundled
into a single Tier 1 file, this is both smaller on the wire (no repeated key names) and
faster to filter/aggregate than array-of-objects — directly relevant to the Tier 1 size
budget in `docs/01-tenant-constraints.md` and to `build_dashboard.py`'s job of embedding
a dataset into one file.

**Not proposed as a rule here** — no dashboard in this repo has yet had a dataset large
enough for this to matter, so there is no real case to generalise from. Documented so the
next contributor who *does* hit that case does not have to rediscover the pattern from
scratch.

## 4. Builds and gates that stay honest

**A rebuild gives the same bytes.** Builders write archives with a fixed `mtime` and keep
input order stable, so the same data gives the same file (`tools/build_cube_dashboard.py`).
When the examples were rebuilt from their sources, the only drift was the build timestamp.
Any other difference after a rebuild is a real change and must be explained.

**A number that can be derived is derived, then locked.** If a document quotes a number that
code can compute (a count, a size, a total), compute it in code, write it to a fact file, and
lock the document to it with a hash of that file. The build fails when the number drifts.
A number typed by hand goes stale on the first edit and nothing complains.

**A gate must prove it ran.** A verify script called with a wrong relative path checked
nothing, wrote zero screenshots and still looked green. A gate prints what it checked ("N
files", "N screenshots") and fails when N is zero. Look at the count, not at the colour.

**A static scan has a blind spot.** A markup scan sees only what is in the file. A sidecar
that a script loads after render (built by `document.createElement`) does not show up. Such
a page needs a render-time check as well.

**Shell globs can stop a build.** In zsh, a glob with no matches is an error by default, and
the whole command chain stops (one build never wrote its README this way). Check that files
exist before you glob over them, or use `(N)`, the null-glob qualifier.

**Never run an in-place mutation harness under a foreground timeout.** A harness that
mutates a file, runs the suite and restores the file was killed by a 30-second tool timeout
between "mutate" and "restore". It left a broken file and an empty screenshot folder that
looked like a real build. Run such a harness in the background, or work on a copy. After any
kill, rebuild from source before you trust the tree.

## 5. The page speaks nb or en: `--lang`

`tools/build_dashboard.py`, `build_cube_dashboard.py`, `build_process_diagram.py` and
`build_slide_deck.py` take `--lang nb|en`. The default is `nb`, and `nb` output is byte for
byte what the builders wrote before the flag existed. `en` has no Norwegian in it.

- **One table per template**, in `templates/i18n/<template>.strings`, with a `[nb]` and an
  `[en]` section. The format is described at the top of `tools/i18n.py`: `key = value`, the
  value is everything after the first `= `, no escaping.
- **The template holds `{{T:key}}`** where a person reads a word. The builder swaps the
  tokens for one language before it puts any data in, so data is never scanned for tokens.
  Words the builder writes itself (the process diagram's step cards, the cube's source line)
  are read from the same table in Python.
- **What changes with the language:** labels, buttons, aria-labels, titles, the number
  format and sort order, `<html lang>`, the feedback link, and the sample slides of the deck.
- **What does not:** your data, element ids (`tab-flyt`, `panel-steg`: nobody reads them,
  the verifiers use them), the spec keywords of a `.process.txt` (`beskrivelse:`), the
  provenance comment's English labels, and what a builder prints in the terminal.
- **Add a string:** add the key to both sections and put the token in the template.
  **Add a language:** add a section to every table and the code to `LANGS` in
  `tools/i18n.py`. A key missing in one section stops the build, naming the key.
- **en copy** is written as English, not translated word for word, and holds no quote,
  backslash or backtick, because a value is pasted into HTML, a JavaScript string or a comment.
- `nb` keeps its old wording even where it is a little off (a diagram with one role says
  "1 roller"), so that the frozen output stays frozen. Fix those on purpose, and move the
  baseline hash in the same commit.

`tests/test_i18n.py` enforces all of it: same keys in both sections, every token exists,
the nb build of each case has the sha256 it had before, the en build of an English fixture
has no `æøåÆØÅ` and none of the nb strings, and a damaged copy of the tables is noticed.
The verifiers read the page's `<html lang>` where wording matters
(`tools/verify_process_diagram.py` takes its tab names from the table).

## What this does not do

- Does not add a translation-table mechanism to either builder script — that is future
  work, tracked below, not delivered by this document.
- Does not add a lint or test that would catch a future violation of either rule. Both
  are currently conventions a human has to remember, same as most of `docs/09` before its
  tokens are wired into `tools/`.

## Open items this document does not resolve

- [x] Design the translation-table mechanism for the page chrome: section 5, `--lang`.
- [ ] Translate data labels (column headers, category values) at render: not built.
- [ ] Decide whether a filter-independence check belongs in `tools/verify_dashboard.py`
      (it currently checks portability and DOM presence, not filter *logic* — see
      `docs/08`'s proposal to split that script, which this would sit alongside as a
      dashboard-specific check).
- [ ] No real dashboard in this repo has hit a case where AND-combining every dimension
      produces an empty result set the user didn't expect — worth a documented UX answer
      (e.g. "0 rows match" state) once one does, not designed speculatively here.
