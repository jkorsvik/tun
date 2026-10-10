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

This site is the project's documentation, served from `docs/` on `main`. The project's
public page is [tun.community](https://tun.community). Credits are in
[AUTHORS.md](../AUTHORS.md). What is written down here is the plumbing: the awkward
constraints measured so that nobody has to rediscover them.

## Start here

| | |
|---|---|
| [Tenant constraints](01-tenant-constraints.md) | **Read this first.** What SharePoint and OneDrive actually do with an HTML file: measured in our tenant, not assumed, and one row retracted when a better test contradicted it |
| [Vision](00-vision.md) | Why an information tool should be a document, and who that serves |
| [Architecture](02-architecture.md) | The three delivery tiers, and what each one costs |
| [The skill tree](03-skill-tree.md) | The whole thing as verbs: build, check, ship |

## Building and shipping

| | |
|---|---|
| [Onboarding](04-onboarding.md) | From a new machine to something a colleague can open |
| [Toolchain](05-toolchain.md) | Skills, MCP servers and CLI tools, and what each is for |
| [Way of working](06-way-of-working.md) | How a round of work runs here |
| [Paired-mode data contract](13-paired-data-contract.md) | What `dash.html` and `data.js` exchange when the data is kept beside the file |
| [Working with real sources](25-working-with-real-sources.md) | Ask the owner, copy structure not rows, verify every quote, prove the numbers on the page |
| [Git hygiene](24-git-hygiene.md) | What to do when a repo has touched real data, learned the hard way |
| [Where it can live](26-hosting.md) | Each host, what runs there, and how to serve a page yourself |

## Design and craft

| | |
|---|---|
| [Usability and navigation](09-usability-and-navigation-principles.md) | Where the brand and the browser agree, and where they do not |
| [Chart colour palettes](10-chart-colour-palettes.md) | Categorical, sequential, diverging, light and dark |
| [Responsiveness and browser support](11-responsiveness-and-browser-support.md) | What is real today, and what is still a proposal |
| [Maintainability conventions](12-maintainability-conventions.md) | Source language, independent filters, and builds and gates that stay honest |

## Going further

| | |
|---|---|
| [A generic artifact model](08-generic-artifact-model.md) | The Layer 0 / Layer 1 split: what is dashboard-specific and what is simply "a portable artefact" |
| [The portable cube](07-portable-cube.md) | How Tier 1 stopped caring about row count: 4 M rows in 0.81 MB, exact to the øre |
| [The no-JavaScript question](15-no-javascript-findings.md) | What a file can still do when scripts never run, and one earlier finding falsified |
| [The hosted route](23-hosted-route-it-brief.md) | The one route that is not a file: what it needs, and the five questions only IT can answer |
| [Generic-layer manifest](14-generic-layer-manifest.md) | What another repo may vendor from this one |
| [What was built](27-what-was-built.md) | Applications made this way, by pattern, and the one lesson each taught |
| [Prior art](28-prior-art.md) | Similar projects and standards, what Tún takes from each, every quote checked against its page |

## Licence, name and release

| | |
|---|---|
| [Licensing](17-licensing.md) | **AGPL v3 plus the Tún Artefact Exception**, which layer each licence applies to, and why. Documents you generate are yours |
| [The name](18-naming.md) | What `Tún` and `tun` mean, what each is used for, and the coinage |

## What is measured, and what is direction

[Findings index](findings-index.md): where each finding from the September 2026 harvest now lives, checked by a test.

The distinction matters more here than in most projects, because the whole approach rests
on how one tenant behaves.

**Measured, in one Microsoft 365 tenant:** everything in
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
[The generic artifact model](08-generic-artifact-model.md) is the bridge already written,
and the rewrite of those two is the current piece of work. Where they disagree with this
page, this page is the newer statement of intent, and the tenant constraints outrank both.

## The rule that outranks the rest

Everything inside a generated file is readable by anyone who can open the file. If two
audiences must see different rows, the split is a **folder with its own permissions**,
never a filter inside one shared copy: a browser filter hides nothing, the rows are still
in the file. Where that is not acceptable, the honest answer is Power BI, and
[the vision](00-vision.md) says so plainly.
