# Tún licensing

Status: **the code licence is decided and applied.** `LICENSE` at the repo root is
the verbatim GNU AGPL v3 text, and `COPYING.ARTEFACT-EXCEPTION` at the repo root is
the adopted Artefact Exception. This is not legal advice.

## Decision

**GNU AGPL v3 or later, plus the Tún Artefact Exception v1.1.**

The goal decides it: the licence should keep people connected to where the project
lives, so they can contribute back.

Two mechanisms get confused here, and only one of them does that:

| | What it really does |
|---|---|
| **AGPL §13** | Requires *offering Corresponding Source* — and only if someone **modifies** Tún **and** their modified version is reached **over a network**. It never requires naming the project. |
| **§7(b)**, identical text in GPLv3 and AGPLv3 | Permits "requiring preservation of specified reasonable legal notices or author attributions". This is the referral lever. |

Read §13 against the realistic path by which a person meets Tún: a colleague sends them a
file. Nobody modified Tún, nothing was reached over a network, and the artefact is freed by
the Exception. AGPL is silent exactly there. So AGPL alone would not deliver the goal, and a
plain GPL-versus-AGPL comparison answers a different question.

Both were therefore adopted, for two different reasons:

1. **AGPLv3, for the hosted-fork case.** The layer table below already lists *Managed
   hosting* as a layer, and backends are on the roadmap. If Tún ever runs as a service, §13
   is the only thing that keeps a modified hosted fork's improvements reachable. GPLv3 gives
   that away.
2. **The Origin Notice, for referral.** Exception v1.1 conditions the artefact permission
   on preserving a provenance line naming Tún and where to find it (§1(b), §2). Gated by
   `tests/test_origin_notice.py`, which also fails if the condition is removed from the
   Exception, so the templates cannot end up enforcing a rule that no longer exists.

**It is deliberately not an advertising clause.** §2 says the notice need not be visible to
a reader, any visible "made with Tún" text is a removable default, and the condition lapses
entirely for a delivery format that cannot carry a notice. A consultant may hand a client an
unbranded report; the file still says where it came from to anyone who looks at its source.

One cost, accepted knowingly: §13 binds an organisation that **modifies** Tún and serves
it to its own colleagues over a network. Offering source internally is trivial, but it is a
compliance obligation somebody has to track.

## Why more than one licence

Tún has layers with different jobs. One licence across all of them either fails
to protect the commons, or reaches into documents that belong to the user.

| Layer | What it is | Licence | SPDX |
|---|---|---|---|
| Toolkit, skills, generator, platform | scripts, build tooling, hosting code | GNU AGPL v3 or later | `AGPL-3.0-or-later` |
| Artefact Runtime | the markup, CSS, JS and templates copied into every produced document | AGPL v3 with the Tún Artefact Exception | see note below |
| Generated Artefacts and user data | the user's report and their numbers | none. The user's own work | n/a |
| Documentation and samples | guides, sample data, screenshots | CC BY-SA 4.0 | `CC-BY-SA-4.0` |
| Built example files | Generated Artefacts kept as samples | AGPL v3 with the Tún Artefact Exception, as their header states | see note below |
| Name, logo, tun.community | identity | trademark policy, not a code licence | n/a |
| Managed hosting | operation and support | commercial service, source still offered | n/a |

## The reason the Exception exists

GNU is explicit that program output is not normally covered by the program's
licence, with one relevant carve-out: it is covered where substantial parts of
the program are copied into the output. The FAQ names Bison, which copies a
parser skeleton into its output and therefore needed its own exception.

Tún copies its runtime into every artefact. That is the same situation.

Without the Exception, every report a person generates becomes a covered work,
and anyone who receives that report could demand corresponding source under
copyleft. That blocks internal use and blocks sending a report to a
customer. The Exception removes that, and keeps copyleft where it belongs: on
the toolkit and the platform.

See `COPYING.ARTEFACT-EXCEPTION` at the repo root.

## Why AGPL rather than GPL for the toolkit

GPLv3 obligations attach on conveying. Running a modified version as a network
service is not conveying, so a hosted fork could stay closed. AGPL section 13
closes that: whoever modifies the program and offers remote network interaction
must offer those users the corresponding source.

This also binds the organisation running it. If an organisation runs a **modified** Tún that colleagues
reach over the network, section 13 applies to those users. Running it unmodified
does not trigger it. This should be a conscious choice, not a surprise.

## Selling and hosting

Copyleft does not prevent charging. The GPL allows selling copies with no price
limit, and under GPLv3 source must be offered through the same place at no
further charge. Charging for hosting, operation and support is fully compatible.
The margin buys relief from setup and operation, not access to the source.

## Plugins: a design decision, not only a licence decision

Whether a plugin must be GPL-compatible depends on how it is joined to the host.
Dynamic linking with shared data structures makes a single combined program.
Simple fork-and-exec without intimate communication leaves the plugin separate,
and GNU states that a main program separate from its plugins makes no
requirements for the plugins.

Decide this before the API shape decides it for us:

- If internal or closed plugins must be possible, use a separate process or a
  data-file boundary.
- If plugins should inherit copyleft, use in-process linking and say so.

## How it is applied

1. `LICENSE` at repo root: the verbatim AGPL-3.0 text from
   https://www.gnu.org/licenses/agpl-3.0.txt. Do not retype it. **Done.**
2. `COPYING.ARTEFACT-EXCEPTION` at repo root: the Exception text. **Done.**
3. Header in every toolkit source file (`.py`, git hooks). **Done.** A short form, not the
   full FSF boilerplate, because the LICENSE file carries the full text:

       Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
       This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
       SPDX-License-Identifier: AGPL-3.0-or-later

4. Header in every Artefact Runtime file (templates, token CSS, `tun_tokens.py`, every
   `build*.py`). **Done.** The same, plus the Exception in plain words, since the SPDX
   `WITH` operator only accepts exceptions on the SPDX list:

       This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
       or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
       COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
       under terms of your choice, provided the Origin Notice is preserved.

   Templates are copied into what they build, so generated documents carry this header
   too. That is deliberate for now: it tells a recipient where the permission comes from.
   `tests/test_licence_headers.py` fails if any source file lacks its header, or a runtime
   file lacks the Exception.

5. README section: one short paragraph saying the toolkit is AGPL, and that
   **documents you generate are yours** and carry no obligation. **Done.**

## Contributor terms

Recommend the Developer Certificate of Origin (`Signed-off-by`), not a CLA. A
CLA that assigns rights is heavier, deters contributors, and raises its own
questions for each contributor. A DCO keeps the bar low and the provenance clear.

Consequence to accept deliberately: without copyright assignment, relicensing
later requires every contributor's agreement. If keeping a relicensing option
matters, that must be decided before the first outside contribution, not after.

## Trademark

The code licence does not control the name. No trademark is registered for `Tún`; see
`docs/18-naming.md` for the checks still open. A short trademark policy later can allow
forks of the code while keeping the name tied to the project.

## Open item

**Review.** The Exception text is drafted from the structure of existing FSF
exceptions, but it is original wording and needs a lawyer to read it.
