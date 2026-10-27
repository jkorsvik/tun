# 37. The printable one-pager

Everything else in this repository is read on a screen. This one is handed over: printed, or
sent as a PDF, and read in a meeting where nobody can filter it.

That changes what it is. A dashboard answers the question the reader has; a one-pager answers
the question the writer had. So the sheet carries four numbers, the chart behind them, and the
sentences that say what moved — because the person holding paper cannot sort by the biggest
change to find out.

```bash
python3 examples/37-printable-onepager/generate_data.py
python3 tools/build_onepager.py \
  --data examples/37-printable-onepager/salgsdata.csv \
  --title "Salg per produkt, september 2026" \
  --dimension Produkt --measure Belop --period Maaned \
  --source "Syntetisk eksempeldata (salgsdata.csv)" \
  --requested-by "Salgsavdelingen" \
  --out examples/37-printable-onepager/ett-ark.html
```

`--period` decides what the sheet is about: the latest value in that column is the period it
prints, and the one before it is what change is measured against. `--top` decides how many
bars fit — six by default, and the builder refuses more than twelve, because a sheet with
twelve bars is a report that lost its argument.

## Measure the page, do not look at the screen

```bash
uv run --extra verify python tools/verify_print.py examples/37-printable-onepager/ett-ark.html
uv run --extra verify python tools/verify_viewports.py examples/37-printable-onepager/ett-ark.html \
    --text-floor 12
uv run --extra verify python tools/verify_a11y.py examples/37-printable-onepager/ett-ark.html
```

`verify_print.py` opens the file, switches to print media, and fails when the document is
taller or wider than one A4 page box, when anything reaches past the right edge or below the
page, when the sheet does not fill the page, when any text renders under 12 px (9 pt), when
the PDF Chromium produces is more than one page, or when something needs the network. The
characteristic failure of this artefact is not a broken layout — it is a page that quietly
became two, with the footer alone on the second one, and nothing on screen to show it.

`--text-floor 12` is the one place this example lowers a gate, and the reason is the artefact
itself: it is typeset for paper, where 9 pt is a normal reading size and 12 px at 96 dpi is
that 9 pt. On a screen it is a preview of the page, not a responsive page, and raising the type
to the 14 px screen floor would make the screen version a different document from the printed
one — which is the thing this example exists to prevent.

The design record — why the page box is the sheet, why the bars are HTML and not SVG, and
where the 9 pt floor comes from — is in [`docs/32`](../../docs/32-printable-artefacts.md).

## What it does not do

No filter, no hover, no scroll, no detail table. A printed sheet cannot do any of those, and
a sheet that pretends to is a worse dashboard. If the question needs exploring, the answer is
[`../01-hello-dashboard/`](../01-hello-dashboard/) and this sheet is the summary of it.

Data is synthetic: `generate_data.py` writes `salgsdata.csv` from a seeded walk, with one
deliberate jump in September and one deliberate fall, so "what moved" has something true to
say. Nothing here is a real figure.
