# 34. The page you land on

A folder of built files has no order. Someone shares `Saker/` with four artefacts in it, and
the reader sees four file names and picks one, or asks which one they were supposed to open.
The dashboards are fine; the folder is the part with no answer in it.

This example is the answer: `index.html` is one card per file, read out of that file's own
provenance block. What it answers, where the numbers came from, when it was built, and for
whom. None of it typed by hand, so it cannot drift from the files it describes.

```bash
python3 examples/34-folder-index/build_example.py
```

One dataset, three answers, one entrance:

| file | the question it answers |
|---|---|
| `saker-dashboard.html` | how do the cases distribute across teams and months |
| `saker-register.html` | give me the cases themselves, searchable |
| `saker-sammenligning.html` | what moved from September to October |
| `index.html` | which of these should I open |

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_folder_index.py
uv run --extra verify python3 tools/verify_viewports.py examples/34-folder-index/index.html
uv run --extra verify python3 tools/verify_a11y.py examples/34-folder-index/index.html
```

## The four rules it carries

* **Every fact is read from the file, never maintained twice.** `Source data`, `Built` and
  `Requested by` come from the artefact's own comment block, by label rather than position,
  so a builder that adds a line does not shift the page. A suite check compares each card's
  field against the file it names: a page that describes a dashboard wrongly is worse than
  no page.
* **A file that cannot account for itself is listed anyway, in its own section.** No
  provenance block, or one too damaged to read, means this page has nothing to say about the
  file, so it says exactly that. Dropping it hides a file someone will eventually open;
  describing it by guesswork is worse.
* **A missing field reads "ikke oppgitt"**, not as a blank. A blank looks like a rendering
  bug; the words say the artefact did not state it.
* **There is no script, at all.** A page whose whole job is a list of relative links does not
  need one, so a host that refuses to run scripts cannot break it, and Quick Look's
  attachment preview shows the folder as it is.

## What it will not do

It does not read the artefacts' contents, draw a thumbnail, or summarise their numbers: that
would mean executing them, and a front page that can be wrong about a dashboard's own numbers
is a second source of truth. It links, and it quotes.

A file that is not a document is skipped: `*.fragment.html` is the marker this repository uses
for a page fragment with no provenance of its own.

## Why this is not example 28 again

Example 28 proves the *builders* differ while the totals agree. This proves the *folder*
works: the four files above were built by four different builders, and the page that
introduces them was built by a fifth from what they said about themselves.
