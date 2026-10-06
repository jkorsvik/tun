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
not the numbers), not a separately maintained English source CSV. Neither builder has
this flag today; every dashboard built so far has shipped in the language its source data
already happened to be in.

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

## What this does not do

- Does not add a translation-table mechanism to either builder script — that is future
  work, tracked below, not delivered by this document.
- Does not add a lint or test that would catch a future violation of either rule. Both
  are currently conventions a human has to remember, same as most of `docs/09` before its
  tokens are wired into `tools/`.

## Open items this document does not resolve

- [ ] Design the translation-table mechanism for `tools/build_dashboard.py` /
      `build_cube_dashboard.py` — no dashboard has needed a second language yet, so this
      has never been forced into an actual shape.
- [ ] Decide whether a filter-independence check belongs in `tools/verify_dashboard.py`
      (it currently checks portability and DOM presence, not filter *logic* — see
      `docs/08`'s proposal to split that script, which this would sit alongside as a
      dashboard-specific check).
- [ ] No real dashboard in this repo has hit a case where AND-combining every dimension
      produces an empty result set the user didn't expect — worth a documented UX answer
      (e.g. "0 rows match" state) once one does, not designed speculatively here.
