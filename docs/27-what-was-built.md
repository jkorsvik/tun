# 27. What has been built with this method

**Reader:** user — you want an artefact out of your own data and do not intend to change the toolkit.

> **Status:** a catalogue, written 2026-10-08. Written generically on purpose: no person,
> organisation, dataset or customer is named. Where a fact was not recorded anywhere this
> page could check, the cell says **not recorded**. Synthetic examples link to their folder
> in this repository. Real deliverables do not, because their data never enters this
> repository ([AGENTS.md](../AGENTS.md) rule 6).

Each entry gives the kind of application, its pattern, where it lives, its scale, and the
one lesson it taught. The lessons are the point: each one is now a gate, a constraints row,
or a rule. Hosts are explained in [where a Tún artefact can live](26-hosting.md).

## Standalone files

| What it is | Host | Scale | The lesson |
|---|---|---|---|
| A case-room dashboard, used for real case work | A SharePoint document library, opened in the inline preview | Not recorded. Real data, not in this repository | A literal script-tag opener, typed as prose inside an HTML comment, stopped every script on the page in the preview. Now [constraints row 25](01-tenant-constraints.md), enforced by `check_no_stray_script_text()` in the publish gate |
| A consumer-trends summary for a non-technical audience | Not recorded | 48 products, illustrative figures | Not recorded |
| A one-page pitch ([`examples/19-tun-pitch`](../examples/19-tun-pitch/)) | A file, sent as a link or attachment | 15 KB, no code that runs | A page with no script cannot be dead in a hostile preview. The worst case is that it looks plainer |
| A cohort grid of who came back ([`examples/44-cohort`](../examples/44-cohort/)) | A file, sent as a link or attachment | 496 invented accounts, 9 cohorts | The one artefact whose column axis is not in the file. Derived per row from each person's earliest date, so row order cannot change the story, and a cell that cannot exist yet is hatched rather than drawn as zero. Now `tests/test_cohort.py`, 48 checks |
| A small multiple of one measure across groups ([`examples/45-smallmultiples`](../examples/45-smallmultiples/)) | A file, sent as a link or attachment | 9 invented units, 10 weeks, 84 values | The only chart whose whole claim is its axis. A panel that scales itself makes 4 to 8 look like 400 to 800 with every number still true, and no accessibility rule can see it. Now `tests/test_smallmultiples.py`, 51 checks and six mutations |
| A rank change between two periods ([`examples/46-rank-change`](../examples/46-rank-change/)) | A file, sent as a link or attachment | 13 invented products, two quarters, one shared rank | A line between two columns has no direction of its own, so a flipped subtraction draws every climber as a fall and nothing looks wrong. The first draft had that, plus a backwards change column and the leaver's word on the newcomer's side. Now `tests/test_rank_change.py`, 49 checks and five mutations |

## Standalone with a dense cube

| What it is | Host | Scale | The lesson |
|---|---|---|---|
| A liquidity analysis | A file | About 4 000 000 source rows in a 0.81 MB file, exact, about 0.1 ms per filter click. The same figures are reproducible on synthetic data in [`examples/03-cube-dashboard`](../examples/03-cube-dashboard/) ([07](07-portable-cube.md)) | Reproducing the source product exactly proves the copy, not the truth. In one month a large group entered the source for the first time, with only part of its value. That made a false dip, and the reproduction gate copied it faithfully. Check for jumps in the sample size before calling a series a trend |

The cube has three costs, stated before anyone builds one: filters are fixed at build time,
there is no drill to single rows, and only additive measures work.

## Paired

| What it is | Host | Scale | The lesson |
|---|---|---|---|
| A transport day board for an organisation with three régimes and three owners ([`examples/17-multi-regime-day-board`](../examples/17-multi-regime-day-board/)) | Built for a synced folder: `oversikt.html` plus `data.js` | 84 synthetic rows | An overview that flattens three régimes with three owners into one list is wrong, however good it looks. The file is a view. The real editor lives elsewhere, with one writer ([01](01-tenant-constraints.md), *More than one editor*) |

## A local deliverable: workbook plus report

| What it is | Host | Scale | The lesson |
|---|---|---|---|
| A survey analysis: a form-tool CSV in, an Excel workbook and a Tún HTML report out | Kept local. The data was real | 22 responses, 74 columns | Keep manual corrections in a side file, so a fresh export does not undo them ([25](25-working-with-real-sources.md)). |

## Static sites

| What it is | Host | Scale | The lesson |
|---|---|---|---|
| The project's public teaser page | One self-contained page embedded in a stdlib Go binary, `FROM scratch` image, a home server behind a tunnel ([AGENTS.md](../AGENTS.md) §8) | One page, gated at 64 KB, no script | A fixed `Last-Modified` let an old `If-Modified-Since` keep returning readers on the old page. A content-derived `ETag` with `Cache-Control: no-cache` fixed it ([26](26-hosting.md), *Serving it yourself*) |
| A public architecture and pitch site | Same server shape: five self-contained pages, each also served as a download | Five pages, one with a cost calculator | The edge rewrites HTML. A bot-protection feature injected a script into served pages and left downloads alone, while e-mail obfuscation stripped comment fences from both. A byte-compare gate must name which cause it found ([26](26-hosting.md), *Serving it yourself*) |
| A voting-advice style app | Same server shape, from a home server. Structured evidence files embedded at build time, no database | 57 statements, 589 evidence files (2026-10-02) | Every verbatim excerpt and every recorded vote is checked against its source by a script. A quote counts only when it is an exact substring of the fetched source ([25](25-working-with-real-sources.md)) |
| A committee page with a task board | Not recorded | Not recorded | Not recorded |

## Portable documents

| What it is | Host | Scale | The lesson |
|---|---|---|---|
| Pitch decks as portable slide files ([`examples/18-portable-slide-deck`](../examples/18-portable-slide-deck/), [`examples/21-slide-deck-detail-overlay`](../examples/21-slide-deck-detail-overlay/)) | A file, sent through chat and opened on desktop and phone | One file each, about 38 KB for example 18 | The attachment preview is not a browser: one phone preview showed source, and the same file ran after a handoff to a browser ([constraints row 27](01-tenant-constraints.md)). Make controls visible on touch, and guard fullscreen |
| A whitepaper with figures | A PDF | Not recorded | A clean build log is not evidence. A cross-reference to a missing label printed `??` in the PDF while the build exited 0 with no warning. Check the rendered output, and look at each figure as an image |
| A decision memo, edited in the browser before it was sent ([`examples/24-editable-document`](../examples/24-editable-document/)) | A file, edited after it is opened from disk. Read-only in the tenant's inline preview | One file, about 20 KB. The real memo's text is not in this repository | Telling a reader to change an artefact in a text editor is a handover problem. Edit in place and save as a new download (constraints row 18). Build the copy from the page as it was opened, so no live edit state can reach it. The inline preview runs the file in a sandbox that blocks downloads ([constraints row 28](01-tenant-constraints.md)): the first version let a reader edit there and lose the text. Offer no edit you cannot save |

## What the catalogue shows

- **Most of the rules came from real use.** Constraints rows 25 and 27, the `ETag` rule and
  the edge byte-compare all came from something real breaking, not from a design review.
- **The standalone file covers most cases.** The entries that are not plain files are
  public sites, each served by one small stdlib binary with its content embedded.
- **Real data stays out.** Three entries used real data. None of it is in this repository.
  They are described here only by their shape.
