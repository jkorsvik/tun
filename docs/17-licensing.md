# Tún licensing

**Reader:** record — a decision or a measurement, kept for why something is the way it is.

Status: **the code licence is decided and applied.** `LICENSE` at the repo root is
the verbatim GNU AGPL v3 text, and `COPYING.ARTEFACT-EXCEPTION` at the repo root is
the adopted Artefact Exception. This is not legal advice.

## Decision, 2026-09-24

**GNU AGPL v3 or later, plus the Tún Artefact Exception v1.1.**

This reverses the plain-GPLv3 decision taken earlier the same day and restores this
document's original recommendation. What settled it was naming the actual goal: the licence
should keep people connected to where the project lives, so they can contribute back.

Two mechanisms get confused here, and only one of them does that:

| | What it really does |
|---|---|
| **AGPL §13** | Requires *offering Corresponding Source* — and only if someone **modifies** Tún **and** their modified version is reached **over a network**. It never requires naming the project. |
| **§7(b)**, identical text in GPLv3 and AGPLv3 | Permits "requiring preservation of specified reasonable legal notices or author attributions". This is the referral lever. |

Read §13 against the realistic path by which a person meets Tún: a colleague sends them a
file. Nobody modified Tún, nothing was reached over a network, and the artefact is freed by
the Exception. AGPL is silent exactly there. So AGPL alone would not have delivered the
goal, and the earlier GPL-versus-AGPL argument was answering a different question.

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

Two costs, accepted knowingly:

1. §13 binds an organisation that **modifies** Tún and serves it to its own colleagues over
   a network. Offering source internally is trivial, but it is a compliance obligation
   somebody has to track.
2. **Some organisations prohibit AGPL outright in their open-source policy.** This has *not*
   been verified for the employer in question, and it is the one answer that could make
   AGPL self-defeating, since blocking internal adoption would remove the project's whole
   point. Ask it together with the ownership question. Two things reduce the exposure: a
   *reader* of a Generated Artefact is unencumbered by design, and using Tún **unmodified**
   as a build tool triggers nothing in §13.

The ownership question is settled (see "Status", item 1). The project belongs to the
authors in `AUTHORS.md`, and the notices name them.

## Why more than one licence

Tún has layers with different jobs. One licence across all of them either fails
to protect the commons, or reaches into documents that belong to the user.

| Layer | What it is | Licence | SPDX |
|---|---|---|---|
| Toolkit, skills, generator, platform | scripts, build tooling, hosting code | GNU AGPL v3 or later | `AGPL-3.0-or-later` |
| Artefact Runtime | the markup, CSS, JS and templates copied into every produced document | AGPL v3 with the Tún Artefact Exception | see note below |
| Generated Artefacts and user data | the user's report and their numbers | none. The user's own work | n/a |
| Documentation and examples | guides, sample artefacts | CC BY-SA 4.0 | `CC-BY-SA-4.0` |
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

## How to apply it, when unblocked

1. `LICENSE` at repo root: the verbatim AGPL-3.0 text from
   https://www.gnu.org/licenses/agpl-3.0.txt. Do not retype it. **Done.**
2. `COPYING.ARTEFACT-EXCEPTION` at repo root: the Exception text. **Done.**
3. Header in every toolkit source file:

       Copyright (C) <year> <copyright holder>
       This file is part of Tún.
       Tún is free software: you can redistribute it and/or modify it under the
       terms of the GNU Affero General Public License as published by the Free
       Software Foundation, either version 3 of the License, or (at your option)
       any later version.
       This program is distributed in the hope that it will be useful, but
       WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
       General Public License for more details.
       You should have received a copy of the GNU Affero General Public License
       along with this program. If not, see <https://www.gnu.org/licenses/>.
       SPDX-License-Identifier: AGPL-3.0-or-later

4. Header in every Artefact Runtime file: the same block, plus

       As a special exception, the copyright holders give permission to convey
       documents generated by this software under terms of your choice, as set
       out in COPYING.ARTEFACT-EXCEPTION.

   SPDX note: the `WITH` operator only accepts exceptions on the SPDX exception
   list. Until ours is registered, use a `LicenseRef-` identifier and state the
   exception in plain words in the file header and the README.

5. README section: one short paragraph saying the toolkit is AGPL, and that
   **documents you generate are yours** and carry no obligation.

## Contributor terms

Recommend the Developer Certificate of Origin (`Signed-off-by`), not a CLA. A
CLA that assigns rights is heavier, deters contributors, and raises its own
questions with an employer. A DCO keeps the bar low and the provenance clear.

Consequence to accept deliberately: without copyright assignment, relicensing
later requires every contributor's agreement. If keeping a relicensing option
matters, that must be decided before the first outside contribution, not after.

## Trademark

The code licence does not control the name. Keeping `Tún` unused for now, as
the naming proposal recommends, is consistent with this. The trademark policy is now
[`TRADEMARK.md`](../TRADEMARK.md). It keeps the name tied to the project while the code can be
forked. A fork that changes the code takes another name. Who holds the mark follows item 1 under
"Status" below.

## Status

1. **Ownership. Settled (2026-10-11).** The project and its code belong to the
   authors in [`AUTHORS.md`](../AUTHORS.md). No employer holds rights in it. This
   document applies. It is no longer a draft.
2. **Provenance. Settled** by the same answer.
3. **Review. Open.** The Exception text is drafted from the structure of existing FSF
   exceptions, but it is original wording and needs a lawyer to read it.
4. **History sanitisation.** On 2026-09-21 real client survey data (a task's
   `work/øvelse/**` scratch directory, ~142 files: a report, a deck, their
   builders, source JSON, and survey submissions, plus `uv.lock`) was found
   reachable from every branch in this repo's history, via two merge commits
   from a `git add -A` run in a shared checkout. All 16 branches were rewritten
   (`git filter-repo`) and force-pushed; every working tree and worktree was
   reset to match. One residue could not be removed through git or the API:
   `refs/pull/53/head`, a merged PR's frozen snapshot, which GitHub Enterprise
   keeps server-side and refuses to delete (`refs/pull/* is read-only`, HTTP
   422). Confirmed directly visible today in that PR's own "Files changed"
   tab — not an obscure raw-ref thing, the normal UI anyone with repo read
   access would see. Decision as of 2026-09-21: acceptable while the repo
   stays internal to the tenant; **not acceptable before any of the following:**
   - making this same repo public within the internal Enterprise instance,
   - publishing it as OSS (AGPLv3 per this document), on this host or a new one.
   Closing it needs one of: a GHE admin purging `refs/pull/53/head` server-side
   (keeps issue/PR numbers, requires a third party and a ticket), or deleting
   and recreating the repository from clean history (self-service, loses all
   issue/PR numbers and review threads — the open PRs at that time would need
   reopening fresh). Either way this is a **hard precondition on this
   document going from draft to applied**, not a nice-to-have — check it's
   actually done, not just planned, before flipping any visibility switch.
   **Status 2026-10-11:** the public repository was made from a flattened export
   with its own clean history (first commit 2026-10-06). No commit in it holds the
   data. The residue stays on the internal host, so the precondition still applies
   to that repository if it is ever made public.

## Which layer each licence applies to

Formerly `16-licensing-layers.md`, folded in here because two documents that answer "what
does the licence cover" is one document too many (`ROADMAP.md` B3). The layer split below
is the part that decides which licence a file, a skill and a plugin each fall under.

Status: local research note. Nothing published. No licence file added anywhere. No name adopted.

### 1. The proposed split

<!-- attribution:start -->
The split in this section is en kollega's ("Tunkallen") proposal.
<!-- attribution:end -->

From `panel-tun-community.html` (third run, overwritten each run, no versioning):

- Internal, Gartner TIME/PACE: the HTML core is **Invest, core only**. Avoid the word "plattform".
- Internal, Wardley: HTML/CSS/JS rendering is moving to **commodity**. The "dashboard-regime" stays custom and differentiating. Break the core loose from the regime.
- tun.community, Rogers: do not launch broadly. Name and contact 2 to 3 real innovators first.
- Unresolved and gating at the time: the secondary work/IP question with legal. Settled 2026-10-11 (`17-licensing.md`, "Status").
- The proposal's own conclusion: continue MVPs on concrete problems, consolidate later, keep the name open, do not use Tún anywhere yet.

Assessment: the split is right. Two cautions.

1. "Consolidate later" is cheap only if the MVPs already agree on a small contract: provenance fields (data through, generated, version), one data-to-HTML convention, and one feedback payload shape. Without that, consolidation is a rewrite.
2. "Core" must be defined by what it guarantees, not by which files it contains. Suggested core promise: one artefact carries data, presentation, interaction and provenance, with no required external resource.

### 2. Layers to licence separately

| Layer | What it is | Licence intent |
|---|---|---|
| Toolkit and generator | skills, scripts, templates, build tooling | strong copyleft |
| Embedded runtime and templates | CSS/JS/markup copied into every artefact | explicit exception, or permissive |
| Generated artefacts and user data | the user's report, their numbers | user's own, no Tún terms |
| Docs and examples | guides, sample artefacts | copyleft or CC BY-SA |
| Name, logo, tun.community | identity | trademark policy, not a code licence |
| Managed hosting | operation, support | commercial, source still offered |

### 3. Verified licence facts

Linux kernel: **GPL-2.0-only** with the `Linux-syscall-note` exception, SPDX `GPL-2.0 WITH Linux-syscall-note`
(https://www.kernel.org/doc/html/latest/process/license-rules.html). The claim that Linux uses GPLv3 is wrong.
Note the pattern: the kernel needed an explicit exception so that userspace is not infected.

GNU GPL FAQ, output (`#GPLOutput`, `#WhatCaseIsOutputGPL`, `#CanIUseGPLToolsForNF`):
- "copyright law does not give you any say in the use of the output people make from their data using your program".
- "the only way you have a say in the use of the output is if substantial parts of the output are copied (more or less) from text in your program".
- Bison copies a standard parser into its output; that copied text is covered, which is why Bison needed an explicit exception.

GPLv3 §2: "The output from running a covered work is covered by this License only if the output, given its content, constitutes a covered work." Running an unmodified program is unlimited. Private modification without conveying carries no obligation.

GPLv3 §5(c): the whole work must be licensed under the GPL to anyone who receives a copy. §5 aggregate: mere aggregation on a medium does not extend the licence to independent works. §7: additional permissions may apply to part of the program.

GPL FAQ plugins (`#GPLPlugins`, `#GPLAndPlugins`): whether host and plug-in form one combined program depends on technical integration. Dynamic linking with function calls and shared data structures is one combined program. Simple fork and exec without intimate communication leaves the plug-in separate. "A main program that is separate from its plug-ins makes no requirements for the plug-ins."

AGPL-3.0 §13: if you **modify** the Program and your version supports remote network interaction, you must prominently offer those remote users the Corresponding Source of your version, from a network server, at no charge.

Selling: the GPL allows selling copies with no price limit. Under GPLv3 you must offer equivalent access to source through the same place at no further charge.

### 4. The consequence that decides the design

Tún copies its own CSS and JavaScript into every artefact. That is exactly the Bison situation.

Without an explicit exception, a plain GPL/AGPL toolkit makes each generated report a covered work, so every recipient of a shared report could demand corresponding source under copyleft. That is unacceptable for internal use and for anyone sending a report to a customer.

Required: a Bison-style / GCC-runtime-style additional permission under GPLv3 §7 covering the embedded runtime and templates, so artefacts carry no copyleft obligation. Alternative: licence the runtime and templates permissively and keep copyleft on the generator and platform.

Second consequence: AGPL §13 would also bind the organisation running a **modified** Tún that colleagues reach over a network. That is a real internal obligation, not only an anti-Amazon clause; unmodified operation does not trigger it. This consequence is one reason the adopted licence is plain GPLv3, which has no section 13 (see `docs/17`).

Third consequence: the plug-in boundary is an architecture decision. If closed or internal-only plug-ins must be possible, define a separate-process or data-file boundary rather than in-process linking.

### 5. Gating items before any licence file

1. Ownership. Settled 2026-10-11. No employer holds rights in the project (`17-licensing.md`, "Status").
2. Contributor terms: DCO or CLA, and whether relicensing later must stay possible.
3. Trademark: keeping the name unused, as the proposal recommends, is consistent with this.
4. Provenance of existing code. Settled by the same answer.

None of this is legal advice.

### 6. Recommendation

- Toolkit and generator: AGPL-3.0-or-later.
- Embedded runtime and templates: explicit §7 additional permission, so artefacts are unencumbered.
- Artefacts and data: the user's own.
- Managed hosting: permitted and compatible, source offered as required.
- Keep the name and any company step blocked on the legal answer. Answered 2026-10-11.
