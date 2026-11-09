# Tún

**New here? [Start here](START-HERE.md): build one file, open it, share it.**

**Interactive dashboards that are files, not services.** Built as single self-contained
HTML artefacts, distributed through SharePoint and OneDrive, openable by anyone who can
open the folder, with no Power BI licence, no workspace, no capacity and no admin approval.

<!-- attribution:start -->
> **Tún is a passion project, credited to the product owner and the maintainer.** <3
>
> The idea is Tunkallen's, the name is Tunkallen's, and the direction is his; deliberately
> open-ended. Jon-Mikkel builds the plumbing: the awkward platform constraints measured
> so nobody has to rediscover them, a working template, the gates that keep it honest,
> and a set of RAIWork skills so building and sharing an artefact is a sentence rather
> than a project. Scaffolding, not a specification.
>
> Nobody asked for this and nothing depends on it. That is the point: it exists because
> sharing a number with a colleague should not cost a licence, a workspace and three
> weeks, and because finding out exactly *why* it does was interesting enough to keep
> going.
<!-- attribution:end -->


---

## The idea in one paragraph

Building a dashboard is easy. *Sharing* one is where Eksempel AS loses weeks. It takes licences per
viewer, a workspace, a capacity, a publish step, and still no way to show it to someone
without a Pro seat. So people fall back to a screenshot in PowerPoint, which is dead on
arrival. Instead: make the dashboard **a document**. One `.html` file with the data,
charts and interaction logic inside it. Drop it in a SharePoint library. Everyone
already knows how to share a document, and SharePoint already handles permissions,
versioning, audit, sync and offline. Reuse that machinery instead of fighting it.

## Status

| | |
|---|---|
| **Bundled mode** (one self-contained file) | ✅ **working, verified end to end** |
| **Paired mode** (dashboard + syncing `data.js`) | ✅ **working**. Swap the data and everyone sees new numbers, no rebuild |
| **Update with no tooling** | ✅ drag a CSV onto the dashboard, click *Lagre datafil*, drop the result in the folder |
| Internal sharing (SharePoint link) | ✅ works (`scope: organization`) |
| **External sharing** | ✅ **as a file** (email/attach), but ❌ *not* via SharePoint links (anonymous sharing blocked tenant-wide) |
| **Cube mode** (millions of rows, one file) | ✅ **working, verified**. 4 M rows → 0.81 MB, 0.10 ms per filter click |
| **[Portable slide deck](examples/18-portable-slide-deck/README.md)** (one file, offline) | ✅ **working**. Responsive portrait/landscape controls, Chromium/WebKit matrix, guarded fullscreen |
| In-page embedding (SPFx) | 🔶 designed, **blocked** on proving SPFx is approvable at Eksempel AS |
| Tier 3 (Parquet + DuckDB-WASM) | 🔶 designed. HTTP Range **measured and confirmed**, but it **cannot run from a portable file** and needs Tier 2 to host it |
| Skills | ✅ 9 written (`tun-help`, `-new`, `-data`, `-verify`, `-publish`, `-process`, `-feedback`, `tun-powerbi-escape`, `tun-for-communicators`) |
| Onboarding | ✅ [zero to published, Windows or macOS](docs/04-onboarding.md) |
| Shapes | ✅ 19 builders, and a chooser: [which shape answers which question](docs/33-artefact-shapes.md) |

## Try it

**[Start here](START-HERE.md).** One command builds a real dashboard from the included
synthetic data. Open the HTML file, try it, then use the same route with your own CSV.

The short guide also covers verification, sharing, Windows, and the sentence to ask your AI
tool. The [full onboarding](docs/04-onboarding.md) remains the reference for installation and
publishing. [Tool compatibility and prior art](docs/28-prior-art.md) records what was tested.

![Example dashboard](examples/01-hello-dashboard/preview.png)

That file is **0.10 MB**, has zero external dependencies, works offline, and needs no
licence to open.

---

## The awkward fact we had to design around

SharePoint and OneDrive **will not render your HTML as a web page.** Every file comes
back with `Content-Disposition: attachment`. Renaming it to `.aspx` gets the MIME type
downgraded to `application/octet-stream`. Anonymous embed links are blocked. The
`/preview` endpoint returns SharePoint's own viewer chrome with a Download button, not
your page.

All of this was **measured against the live Eksempel AS tenant**, not read in a doc. Microsoft's
documentation was materially incomplete on the two facts that mattered most.
See **[`docs/01-tenant-constraints.md`](docs/01-tenant-constraints.md)** for the full
header dumps.

The reframe that makes it work:

> **The download is not a failure. It is the delivery mechanism.**
> SharePoint is a permissioned document CDN, not a web server.

And the finding that opens up the ceiling: a **dense OLAP cube**, gzipped and inlined,
inflated by the browser's native `DecompressionStream`. **Measured: 4 000 000 rows in a
0.81 MB single file**, filter clicks at a median of 0.10 ms, exact against DuckDB on the
raw data. Row count stops being the constraint. See
**[`docs/07-portable-cube.md`](docs/07-portable-cube.md)**.

SharePoint also honours HTTP `Range` requests (`206 Partial Content`, confirmed), which
makes Parquet + DuckDB-WASM real, but **only from a hosted origin.** DuckDB-WASM cannot
boot from a `file://` page at all, so that path needs an SPFx web part. Measured and
corrected; the details are in the constraints doc.

## Read in this order

1. **[`docs/00-vision.md`](docs/00-vision.md)** (why, and the honest scope boundary vs Power BI)
2. **[`docs/01-tenant-constraints.md`](docs/01-tenant-constraints.md)** (what actually happens, measured)
3. **[`docs/02-architecture.md`](docs/02-architecture.md)** (the three delivery tiers and their governance cost)
4. **[`docs/03-skill-tree.md`](docs/03-skill-tree.md)** (the skills and how they compose)
5. **[`docs/04-onboarding.md`](docs/04-onboarding.md)** (zero to published, no dev experience assumed)
6. **[`docs/05-toolchain.md`](docs/05-toolchain.md)** (the skills, MCP servers and CLI tools needed, and why each)
7. **[`docs/06-way-of-working.md`](docs/06-way-of-working.md)** (the habits, `hotshot`, and which general skills help)
8. **[`docs/07-portable-cube.md`](docs/07-portable-cube.md)** (how millions of rows fit in a portable file, and what that costs you)

## Check your machine

```bash
python3 setup.py
```

Reports what's present, what's missing, and the exact command to fix each gap. Then it runs
a real build smoke test, and verifies it in a browser when Playwright is installed. It
changes two things: it points this clone's `core.hooksPath` at `tools/hooks` (the pre-commit
gate), and it installs the skills for your tool. Safe to re-run. `python3 setup.py --check`
changes nothing.


## The one rule

> **Never write a row into a file whose audience should not see it.**

The security boundary is the **folder**, not a filter. So when different people need
different data: **split the data before writing it** and give each audience its own folder.
Same dashboard shell, one `data.js` each. SharePoint enforces access, visibly and
auditably, which beats reasoning about a filter expression.

A filter in the browser hides nothing. The data is still in the file.

## Questions people ask

**Why not just use Power BI?**
Use Power BI when the answer depends on who is looking. A Tún file is a snapshot: you
rebuild it to refresh the numbers. It is for the many small reports where a licence per
viewer, a workspace and a publish step cost more than the report.
[docs/07](docs/07-portable-cube.md) has the table.

**Can I hide some rows from some readers?**
No. Everything in the file is readable by whoever opens it, so split the data and give each
audience its own folder ([the one rule](#the-one-rule)).

**Does it work on a phone?**
It depends on how the file arrives. Opened from a Teams preview card, it worked on a PC and
a phone. A OneDrive link pasted into an e-mail worked on the PC and did nothing on the phone
([docs/01](docs/01-tenant-constraints.md), row 22).

**Why are the charts empty in the Mac or iPhone preview?**
Quick Look turns JavaScript off on purpose. Open the file in a browser instead
([docs/11](docs/11-responsiveness-and-browser-support.md)).

**Can I send it outside my organisation?**
Yes, as an e-mail attachment. Anonymous SharePoint links were blocked in the tenant we
measured, and a file you have sent cannot be recalled, so check what is in it first
([docs/01](docs/01-tenant-constraints.md), row 11).

**How much data fits?**
A bundled dashboard carries its rows. For large data, the cube mode put 4 000 000 rows into
a 0.81 MB file, at a median of 0.10 ms per filter click
([docs/07](docs/07-portable-cube.md)).

**Does the file load anything from the internet?**
No. `tools/verify_dashboard.py` fails any file that references an outside http(s) resource,
and it renders the file from `file://` in a real browser.

**Can I use the files I make for paid work?**
Yes. You may share the files you generate under terms of your choice, on two conditions:
keep the Origin Notice (the provenance block in the file), and the file must not itself be
a tool that produces documents from data and templates the way Tún does
([Licence](#licence), [COPYING.ARTEFACT-EXCEPTION](COPYING.ARTEFACT-EXCEPTION)).

## Layout

```
docs/          vision, measured constraints, architecture, skill tree, onboarding
skills/        the RAIWork skills (plain English, edit these freely)
templates/     dashboard, cube and portable slide-deck templates; no framework
tools/         builders and generic/browser verification tools
probe/         tenant-probe.py, re-verify the constraints in any tenant
examples/      working dashboards, reports and slide decks with sample data
```

## Contributing

The skills are prose, not code. If RAIWork does something the wrong way, fix the
instruction in `skills/*/SKILL.md`. Business knowledge about how reports are really
consumed is more valuable here than engineering.

Two standing rules:

1. **`tun-verify` must pass before anything is published.** A clean build is not
   evidence; inspect the artefact.
2. **If a tenant constraint changes, update `docs/01-tenant-constraints.md` in the same
   commit** as whatever you change in response. Re-check with
   `python3 probe/tenant-probe.py`.
3. **Never commit real customer/client data into this repo, not even in scratch form.**
   `work/<task>/` is where a real deliverable gets built; it's gitignored on purpose. See
   `AGENTS.md` rule 6 for what happens when that boundary slips.

See [`ROADMAP.md`](ROADMAP.md) for what's next.

## Project files

- [`CONTRIBUTING.md`](CONTRIBUTING.md): how to run the gates and the tests
- [`SECURITY.md`](SECURITY.md): what is in scope and how to report a problem privately
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md): Contributor Covenant 2.1
- [`CHANGELOG.md`](CHANGELOG.md): what changed

## Licence

Tún is free software under the **GNU Affero General Public License v3 or later**
([`LICENSE`](LICENSE)).

**Documents you generate are yours.** Tún copies its own markup, CSS and templates into
every dashboard, deck or report it builds, so without an explicit permission each of those
documents could count as a covered work and its recipient could demand corresponding
source. The [Tún Artefact Exception](COPYING.ARTEFACT-EXCEPTION), an additional permission
under AGPLv3 section 7, removes that: you may convey a generated artefact, and the data it
carries, under any terms you like.

Two conditions, both narrow. The artefact must not itself be a competing generator, and it
must keep its **Origin Notice**: the provenance line naming Tún and where to find the
project. That notice does **not** have to be visible to a reader. Keeping it in the
provenance block is enough, and any visible "made with Tún" text is a removable default. So
an unbranded client report is fine; the file still says where it came from to anyone who
opens its source. `tests/test_origin_notice.py` gates it.

Modifying Tún itself, and passing that modified version to someone else, stays under the
AGPL: share the corresponding source. Section 13 extends that to making a **modified**
version available to users over a network. That is deliberate, and it is what keeps a hosted
fork's improvements reachable. Running an unmodified copy triggers nothing. See
[`docs/17-licensing.md`](docs/17-licensing.md) for why AGPL was chosen over GPL, and why
that choice does not by itself achieve attribution.

Documentation and examples are CC BY-SA 4.0. The name and logo are not covered by the code
licence; see [`docs/18-naming.md`](docs/18-naming.md).
The trademark policy is [`TRADEMARK.md`](TRADEMARK.md).
