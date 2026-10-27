# One word for one thing

**Reader:** user — you want an artefact out of your own data and do not intend to change the toolkit.

ROADMAP B6. This repository has one subject and about forty words for it. Half of the
confusion a new reader feels is not the topic, it is that two documents call the same thing
different names, and one document calls two different things the same name. So this page
fixes the vocabulary, and the gate at the bottom keeps the mechanical half of it.

Read it once. It is short on purpose.

## The four words that carry weight

**Artefact** (never "artifact", never "deliverable", never "output"). One file, built by an
engine in this repository, that a recipient opens. A dashboard is an artefact. A survey
board is an artefact. A process diagram is an artefact. A slide deck is an artefact. If you
find yourself writing "the dashboard" about a process diagram, the word you want is
artefact.

British spelling, one `i`, and that is a decision rather than an accident: it is the
spelling the licence and the public page use, and mixing the two inside one file is the
kind of drift this page exists to stop.

**Dashboard** is a *kind* of artefact, not a synonym for it. Use it only when the thing
has KPI cards, charts and a detail table, which is what the chart builders produce. It is
still the right word in the skills' names (`tun-new`, `tun-data`) because that is what a
user asks for, and the entry point has to speak the user's language.

**Provenance block** (never "metadata", never "header comment"). The marked block inside
the file that names the source data, when it was extracted, when the file was built, who
asked for it, and how many rows went in. It is provenance, not metadata: the claim it makes
is "this number came from here, at this time", and it is the only way a reader can check a
number without asking the builder. Norwegian output says *kilde* on the page and the word
"provenance block" stays in the code and the docs.

**Self-contained** (hyphenated, always). The property that the file needs no network, no
sibling files, and no server: it opens from `file://` and works. Say "self-contained", not
"standalone" and not "offline": *offline* describes the reader's situation, not the file,
and *standalone* is the word the older documents used before the property was measured.

## Words that are deliberately narrow

- **Paired mode** is the one exception to self-contained, written down in
  [the paired-data contract](13-paired-data-contract.md): a shell plus a sidecar `data.js`
  that the folder's permissions protect. Do not call it "split" or "external data".
- **Tenant** is Eksempel AS's SharePoint and OneDrive estate, with its forced
  `Content-Disposition: attachment`. It is a specific measured thing
  ([tenant constraints](01-tenant-constraints.md)), not a general word for a customer.
- **Row level** means the row is in the file. There is no "row-level security" here and the
  phrase must not appear, because it implies a filter where the design has a folder split.
- **Tier 1 / Tier 2 / Tier 3** are cost tiers, defined once in
  [the skill tree](03-skill-tree.md). They are not difficulty or quality levels.

## The rule that outlives the words

When two words seem to mean the same thing, the fix is not a synonym list. Find the
sentence where the two are used as if interchangeable, and rewrite it so only one of them
can be true. A glossary that lists alternatives teaches the drift it is meant to stop.

## What the gate checks, and what it cannot

`tests/test_glossary.py` enforces the mechanical part: this page defines each canonical
term, the US spelling does not appear in this repository's own prose, and "self contained"
without the hyphen appears only inside a quoted source. It prints how many files it resolved
and refuses to pass on an empty scan.

It cannot check meaning. Nothing can: whether a paragraph about a process diagram says
"dashboard" is a judgement, and the reviewer's. The gate is there so the spelling does not
drift while the reviewer spends attention on the judgement.

The exemptions are named here rather than left silent in the suite:

- `docs/08-generic-artifact-model.md` keeps the US spelling in its *filename*, because
  twenty-four files link to that path, including a vendored baseline and four example
  builders. Renaming it is its own change with its own verification; this page records the
  debt instead of hiding it. Links *to* it are stripped before the scan, so citing it does
  not trip the gate.
- The documents about the Atlassian route are exempt as a group
  ([22](22-plugin-contract.md), [23](23-hosted-route-it-brief.md), [26](26-hosting.md),
  [29](29-atlassian-artifacts.md), `tun-publish`) because in those files the word is a
  product name and its API keys, and the sentences around them are about the product too.
  That is a real hole in the scan, and it is worth its size: the alternative is a per-line
  whitelist that grows every time the product is mentioned.
- Code is not scanned. A function name, a JSON field and a shell variable carry the word
  legitimately, so only `.md`, `.html`, `.strings` and `.txt` are read, and inside those,
  backticked spans, `{{placeholders}}` and the template's `ARTIFACT_SPECIFIC_LINE` are
  stripped first. The gate is about sentences.
- `plugins/`, `internal/`, `work/` and `examples/` are out: shipped bundles, an archive, a
  build directory, and built artefacts. None of them is this repository speaking.
