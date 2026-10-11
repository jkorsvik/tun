---
name: tun-verify
description: Prove a built dashboard actually renders and works before it is shared — opens it in a real browser from a file:// URL, checks it is self-contained, confirms charts and interactivity work, checks the size budget, and produces a screenshot for review. Use before publishing any dashboard, or when checking whether a dashboard file is broken or safe to share.
license: AGPL-3.0-or-later
---

# Verify a dashboard before it ships

This is a **gate, not a formality**. The entire premise of a portable dashboard is that
it works on *someone else's* machine, opened from *their* folder, with no server. The
only way to know that is to do it.

`tools/verify_dashboard.py` composes two layers (see `docs/08-generic-artifact-model.md`):
a generic core (`tools/verify_standalone_core.py` — self-contained, size, no leftover
`{{PLACEHOLDER}}`, provenance, console-clean render, screenshot) that any standalone-HTML
artefact can reuse, plus dashboard-only DOM assertions (KPI/chart/table/interactivity) on
top. You do not need to run the generic core separately — `verify_dashboard.py` already
calls it.

> A clean build is not evidence. Inspect the artefact.

## Run it

```bash
python3 tools/verify_dashboard.py <path-to-dashboard.html>
python3 tools/verify_dashboard.py <path-to-dashboard.html> --engines all   # + Firefox and WebKit
```

Readers open the file in Edge, Chrome, Safari or Firefox. Use `--engines all` before a
file goes to a wide audience: it runs every check in Chromium, Firefox and WebKit (Safari's
engine), and names the engine in each failure.

Exit `0` = safe to publish. Anything else = do not publish.

## What it checks, and why each matters

| Check | Why it would matter if it failed |
|---|---|
| **self-contained** | a `<script src="https://…">` means the dashboard breaks offline, breaks in a locked-down browser, and silently changes when the CDN does |
| **size budget** | >50 MB and it becomes painful to open and to sync; the Tier 1 promise breaks |
| **provenance intact** | numbers nobody can trace to a source become a liability the first time someone challenges them |
| **no stray `<script` text** | a literal `<script` outside a real script tag, even in a comment, makes SharePoint's preview disable *every* script in the file (docs/01 row 25). The page looks fine locally and is dead in the preview |
| **no unsubstituted placeholders** | `{{MEASURE_COL}}` shipped to a stakeholder is embarrassing and means the build half-failed |
| **console clean** | a JS error usually means charts are empty while the page still looks structurally fine |
| **JS executed** | asserts KPI cards exist *in the DOM* — proves the script ran, not just that markup was written |
| **charts have marks** | counts actual `<rect>`/`<circle>` elements. A chart container with no marks is the classic silent failure |
| **table has rows** | catches a data/column mismatch that leaves the detail table empty |
| **interactivity** | changes a filter and asserts the row count moved — proves the render loop is wired, not just the first paint |
| **screenshot** | the only check for "is this actually readable" |

Rows 24 (`:target` navigation) and 26 (sticky or fixed headers) are not checked by this tool. They are checked for every tracked file by `tools/check_tree.py`, which the pre-commit hook runs.

## Check every viewport, not just the desktop one

`verify_dashboard.py` renders at **one** desktop size. If the dashboard will be opened
on a phone or a tablet — and it will be, because people open links in Teams on their
phone — that single render proves nothing about it.

```bash
python3 tools/verify_viewports.py dashboards/<slug>/dash.html
```

Six viewports: conference 1600x900, laptop 1366x768, tablet 768x1024 and 1024x768,
phone 390x844 and 844x390. Per viewport it measures horizontal overflow (content wider
than the viewport = clipped content), interactive elements below 44x44px on the touch
sizes, and writes one screenshot each.

If that tool is not in the repo you are working in, do the same thing by hand with
Playwright: load the file at each size, screenshot, and look at all of them. Two sizes
is the floor, six is better.

Findings are usually small and real: a `<select>` at 37px tall, a button at 42px. Fix
the CSS; do not widen the rule.

## After it passes — look at the picture

**Always open the screenshot.** A clean measurement is not a clean layout. The
assertions cannot see:

- axis labels overlapping each other or the axis
- a bar chart with 400 categories, rendered as noise
- a title that says `Belop per Produkt` when the user calls it "omsetning per produkt"
- numbers formatted as `1234567.89` instead of `1 234 568`
- a KPI that is obviously wrong by an order of magnitude

Go through each screenshot in this order — text, layout, colour, motion — rather than
glancing at the whole thing:

**Text.** Nothing past the right edge. Nothing cut off at the bottom. Headline fits two
lines; if it wraps to three, shorten the words rather than the type. Nothing below ~16px
rendered: if it looks small in the screenshot, it is too small. Text on dark backgrounds
readable, not merely present.

**Layout.** Cards in a grid share a height, or expand cleanly. Nothing overlaps a fixed
header or rail. At the smallest size, nothing has shifted unexpectedly.

**Colour.** The accent is visible against both light and dark backgrounds. Nothing that
must be read is in the muted colour. Contrast survives a washed-out projector, which is
worse than your monitor.

**Motion.** Animations have actually fired before the screenshot — wait ~1.4s after load,
or you are reviewing the pre-animation state and will pass a broken reveal.

Show it to the user inline and let them react to it:

```
![dashboard](dashboards/salg.verify.png)
```

Then sanity-check one number out loud against the source if you can — *"total Belop
comes to 648 924 441 for Bergen, which matches the sum in the CSV"*. A dashboard that
renders beautifully and shows wrong numbers is worse than one that fails loudly.

## If it fails

Fix the cause, do not weaken the check.

| Failure | Usual cause | Fix |
|---|---|---|
| remote subresource | someone added a CDN chart library | inline it, or use the built-in SVG charts |
| size ceiling | too many rows inlined | pre-aggregate to the displayed grain, or go Tier 3 |
| console error | a column name with a quote, or a measure that isn't numeric | check the column, rebuild |
| 0 chart marks | measure column parsed as text | verify the numeric coercion; check for stray units like `kr` |
| 0 table rows | filter defaults excluding everything | check the filter columns exist and have values |
| filter changed nothing | may be legitimate (uniform data) — or the filter column is wrong | check by hand before dismissing it |

## If Playwright is missing

The script degrades to static checks only and says so. That is **not** a pass for
publishing purposes — the render checks are the valuable ones.

A check that cannot run must never print success. If you write one, make the missing
dependency an error with a non-zero exit, not a skip; a green line for work that never
happened is worse than a red one, because it trains everyone to stop reading the output.

Install it:

```bash
uv sync --extra verify && uv run playwright install chromium
uv run playwright install firefox webkit   # only for --engines all
```

`uv` only — never `pip`. Sources (PyPI) are in `pyproject.toml`.

## Notes

- The verifier opens the file via `file://`, deliberately — that is the origin a real
  recipient uses, and it is the origin where a CDN reference or an absolute path fails.
- It writes `<name>.verify.png` next to the dashboard. These are build artefacts; keep
  them out of git unless one is being used as documentation.

Something wrong or surprising in the result? `tun-feedback` records it and can file it as an issue.
