# Tún

**Information tools that are files, not services.**

One artefact is one self-contained HTML file: markup, data, charts, interaction, all
inlined. It opens from a folder, an attachment, a synced drive, a USB stick; offline, with
no licence, no workspace, no capacity, no admin approval and no install. A dashboard is
the case we measured first, not the boundary: the same format carries a report, a slide
deck, a click-through walkthrough, an infographic, a register, a form-shaped summary.

**A backend here is whatever the recipient already has.** The artefact does not ask for a
server; the *publishing* step adapts to the resources and capabilities of the person
receiving it. A filesystem is a backend. A OneDrive or SharePoint folder is a backend, and
its permissions are the access control. So is an Outlook attachment, a Slack upload, a
Vercel or Firebase project, an S3 bucket, Azure Blob, GCS. The question is never "which
platform do we buy"; it is "what does this reader already have, and what is the cheapest
route into it".

**Each job leaves the toolkit stronger.** Scripts, templates and tests are cumulative:
built for the task at hand, then kept, generalised and gated, so the next task starts
further along. [The skill tree](03-skill-tree.md) is the router. It takes what somebody
wants in their own words and routes it to the right shape, the right tier and the right
target, including the honest exit: if the requirement is row-level security, the answer is
Power BI and the skill says so.

This site is the project's documentation, served from `docs/` on `main`. It is internal
and unpublished; the public teaser lives at [tun.community](https://tun.community).

> **This is en kollega (Tunkallen) kollega's project.** The idea is his and the direction is
> his. What is written down here is the plumbing: the awkward constraints measured so
> that nobody has to rediscover them.

## Read this by who you are

Thirty-two documents is too many to read in order, and reading the wrong one wastes the
ten minutes that decides whether this project is for you. So every document opens with one
line saying who it is for, and this page files it under that same reader:

- **user** — you want an artefact out of your own data, and you are not changing the toolkit
- **contributor** — you are changing the toolkit, and need the constraint or the convention
  behind a decision
- **record** — a decision or a measurement, kept for *why* something is the way it is

Start with the section that matches you, and stop when you have what you came for.
`tests/test_docs_readers.py` keeps the filing honest: a document filed here under one
reader and marked as another fails the suite.

### If you use Tún

<!-- reader: user -->

| | |
|---|---|
| [Onboarding](04-onboarding.md) | **Start here.** From a spreadsheet to a shared dashboard in five minutes, on Windows or macOS, with no AI tool installed |
| [Which shape answers which question](33-artefact-shapes.md) | Twenty-six builders, the question each answers in the words people use, what to do when two shapes compete, and the five questions this format does not answer |
| [The skill tree](03-skill-tree.md) | What you can ask for, in your own words: build, check, ship, and the honest exit |
| [Vision](00-vision.md) | Why an information tool should be a document, and who that serves |
| [What was built](27-what-was-built.md) | Applications made this way, by pattern, and the one lesson each taught |
| [Working with real sources](25-working-with-real-sources.md) | Ask the owner, copy structure not rows, verify every quote, prove the numbers on the page |
| [Usability and navigation](09-usability-and-navigation-principles.md) | What a reader must be able to do, where the brand and the browser agree, and where they do not |
| [Where it can live](26-hosting.md) | Each host, what runs there, and how to serve a page yourself |
| [Atlassian Artifacts](29-atlassian-artifacts.md) | Publishing over the MCP server, what the viewer and a Confluence embed allow, measured |
| [The hosted route](23-hosted-route-it-brief.md) | The one route that is not a file: what it needs, and the five questions only IT can answer |
| [One word for one thing](30-glossary.md) | The vocabulary: **artefact** is the file, **dashboard** is one kind of it, **provenance block** says where a number came from |
| [Examples](../examples/README.md) | One row per working artefact: what each proves, how to rebuild it, how to check it |
| [The file that answers back](31-review-roundtrip.md) | A reader who disagrees with a number can say which row, in the file they already have, and hand it back as one text block: no server, no account, and it works by hand when scripting is off |

### If you are changing the toolkit

<!-- reader: contributor -->

| | |
|---|---|
| [Artefact ideas: what to build next](34-artefact-ideas.md) | The gaps the twenty shapes leave, each with the trap that makes it harder than it looks, plus the ideas that are not a chart, and the five things every new shape has to pay for |
| [Printable artefacts: one sheet, measured](32-printable-artefacts.md) | Why a one-pager is a different artefact rather than a print stylesheet, why its failure mode is growth rather than breakage, and how the page box, the HTML bars and the 9 pt floor are measured |
| [Tenant constraints](01-tenant-constraints.md) | **Read this first.** What SharePoint and OneDrive actually do with an HTML file: measured in our tenant, not assumed, and one row retracted when a better test contradicted it |
| [Architecture](02-architecture.md) | The three delivery tiers, and what each one costs |
| [Toolchain](05-toolchain.md) | Skills, MCP servers and CLI tools, and what each is for |
| [Way of working](06-way-of-working.md) | How a round of work runs here |
| [Maintainability conventions](12-maintainability-conventions.md) | Source language, independent filters, and builds and gates that stay honest |
| [Paired-mode data contract](13-paired-data-contract.md) | What `dash.html` and `data.js` exchange when the data is kept beside the file |
| [Responsiveness and browser support](11-responsiveness-and-browser-support.md) | What is real today, and what is still a proposal |
| [Chart colour palettes](10-chart-colour-palettes.md) | Categorical, sequential, diverging, light and dark |
| [The portable cube](07-portable-cube.md) | How Tier 1 stopped caring about row count: 4 M rows in 0.81 MB, exact to the øre |
| [A generic artefact model](08-generic-artifact-model.md) | The Layer 0 / Layer 1 split: what is dashboard-specific and what is simply "a portable artefact" |
| [Generic-layer manifest](14-generic-layer-manifest.md) | What another repo may vendor from this one |
| [Tiers: core, community, third party](21-plugin-architecture.md) | Where the boundary sits between what everyone gets and what a team adds |
| [The plugin contract](22-plugin-contract.md) | What a plugin may assume, and what it must never assume |
| [Git hygiene](24-git-hygiene.md) | What to do when a repo has touched real data, learned the hard way |
| [Findings index](findings-index.md) | Where each finding from the September 2026 harvest now lives, checked by a test |

## The record

<!-- reader: record -->

These are not instructions. Each one is the state of a decision or a measurement at a
point in time, and several are kept with their own history, including the parts that were
later contradicted. Read them when you need to know *why*, or before reopening something
that has already been argued.

| | |
|---|---|
| [Licensing](17-licensing.md) | **AGPL v3 plus the Tún Artefact Exception v1.1**, why AGPL, and which layer each licence applies to. Documents you generate are yours |
| [The name](18-naming.md) | What `Tún` and `tun` mean, what each is used for, the coinage, and where the name already lives |
| [The no-JavaScript question](15-no-javascript-findings.md) | What a file can still do when scripts never run, and one earlier finding falsified |
| [Publication readiness](20-publication-readiness.md) | What is left before this repository could be published, and what is deliberately not |
| [Prior art](28-prior-art.md) | Similar projects and standards, what Tún takes from each, every quote checked against its page |

## What is measured, and what is direction

The distinction matters more here than in most projects, because the whole approach rests
on how one tenant behaves.

**Measured, in the live Eksempel AS tenant:** everything in
[tenant constraints](01-tenant-constraints.md), row by row, with the method written next
to each result. Files are always served as a download; fragment navigation is blocked in
SharePoint's inline preview even though scripts run; the literal opening characters of a
script tag, typed as prose anywhere in a file, disable scripting for that whole page;
`position:sticky` and `position:fixed` are unreliable there.
Also measured: the cube numbers, the viewport behaviour, and what survives with scripting
off.

**Direction, not yet measured:** the full backend list above. Filesystem, OneDrive and
SharePoint are exercised daily. A raw Slack attachment has one measured iPhone/macOS
result (tenant constraints row 27), but a Slack publishing adapter does not exist. Outlook,
Vercel, Firebase, AWS, Azure and GCP are where the same artefact should land with a thin
publish adapter, and none of those adapters has been probed yet. The contract that would
make them interchangeable, roughly "put these bytes somewhere, tell me who can read them,
hand me a link", is not written down anywhere in this repo yet; [the toolchain](05-toolchain.md)
still speaks of one backend, singular. That is the next thing to name properly.

Two documents still carry the older, narrower framing where every artefact is a dashboard:
[the vision](00-vision.md) and, in places, [the architecture](02-architecture.md).
[The generic artefact model](08-generic-artifact-model.md) is the bridge already written,
and the rewrite of those two is the current piece of work. Where they disagree with this
page, this page is the newer statement of intent, and the tenant constraints outrank both.

## The rule that outranks the rest

Everything inside a generated file is readable by anyone who can open the file. If two
audiences must see different rows, the split is a **folder with its own permissions**,
never a filter inside one shared copy: a browser filter hides nothing, the rows are still
in the file. Where that is not acceptable, the honest answer is Power BI, and
[the vision](00-vision.md) says so plainly.

## The words

[One word for one thing](30-glossary.md) fixes the vocabulary. Read it before writing a
document about any of them; `tests/test_glossary.py` keeps the spelling half of it honest.
