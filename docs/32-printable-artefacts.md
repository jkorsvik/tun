# 32. Printable artefacts: one sheet, measured

**Reader:** contributor — you are changing the toolkit, or adding an artefact that is printed
rather than explored.

Status: as-built. `examples/37-printable-onepager/` is the artefact, `tools/build_onepager.py`
the builder, `tools/verify_print.py` the gate.

## Why this is a separate artefact, not a print stylesheet

Every other artefact here is explored. A one-pager is *handed over*: printed, or sent as a
PDF, and read in a meeting where nobody can filter it, sort it, or open the detail table. The
person holding it cannot ask the file a question, so the file has to have asked the questions
already.

That is a different product, not a different stylesheet. A dashboard with `@media print` still
carries filters, a table and a scroll; printing it produces a screenshot of a screen. What a
sheet carries instead is the four numbers the writer thought mattered, the chart behind them,
and the sentences that say what moved — because the reader cannot sort by the biggest change
to find out.

## The failure mode: it grows

A one-pager does not break. It grows. Someone adds a fifth bullet, a sentence runs long, the
chart gets one more bar — and the page that was one page becomes two, with the footer alone at
the top of the second. Nothing on screen shows it, because on screen everything scrolls. Anyone
who has printed a web page has seen this and blamed the printer.

So the gate measures the page:

* the document is not taller or wider than the A4 page box at 96 dpi (794 × 1123 px);
* no element reaches past the right edge or below the page;
* the sheet fills the page (a sheet at 60 % height prints as a page with an empty third);
* every text run renders at 12 px or more, which is 9 pt at 96 dpi — a printed page cannot be
  zoomed;
* the PDF Chromium produces really is one page, because a CSS height can be right and the
  printer output wrong;
* nothing is loaded from the network or from a sibling script.

The last one matters more than it looks: a sheet that needs a file next to it prints blank from
Outlook's preview, which is where most of these are opened first.

## The page box is the sheet

`@page{size:A4;margin:0}` and the sheet itself carries a 14 mm inner padding, at exactly
210 × 297 mm. Two reasons:

* what the screen shows is what the printer gets — same box, same margins, same line breaks.
  A sheet laid out at 1000 px and printed at 794 px reflows, and the reflow is where the second
  page comes from;
* a printer's own non-printable edge can clip a border drawn at the paper edge, but cannot clip
  content that sits 14 mm inside it.

The consequence is a real constraint: the sheet is a fixed canvas, so text does not reflow for
a narrower window, because there is no narrower window. That is why the builder refuses
`--top` above 12 rather than shrinking the type to make room.

## The bars are HTML, not SVG

The other artefacts draw charts as hand-rolled SVG with a `viewBox`. Here the bars are a CSS
grid: a name column, a track, a value.

The reason is measured, not stylistic. An SVG `viewBox` scales its labels with the drawing, so
9 pt inside a `viewBox` that is scaled up on a wider canvas prints at 6 pt or 12 pt depending
on the sheet's width. `verify_viewports.py` measures rendered text and would catch it, but the
simpler answer is to not have the problem: in a CSS grid, the type size in the stylesheet is
the type size on the paper.

## What print cannot do, and the sheet says so

No filter, no hover, no scroll, no detail table, no "click a row". A printed sheet that
pretends to have them is a worse dashboard. If the question needs exploring, the answer is a
dashboard, and the sheet is its summary — which is also why the sheet names the source, the
extract time, the build time and the requester in its footer: a page with no provenance is a
number nobody can trace.

## Adding one

`tools/build_onepager.py` takes `--dimension`, `--measure` and `--period`; the last column's
latest value is the period printed, and the one before it is what change is measured against.
The i18n strings live in `templates/i18n/onepager.strings`, so `--lang en` works.

The gate is `python3 tools/verify_print.py <file>`, and the suite is
`tests/test_onepager.py` — which runs the verifier twice more on deliberately broken copies, so
a rule that has never fired is a rule nobody knows works.
