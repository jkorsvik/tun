# 20 — Publication readiness

**Reader:** record — a decision or a measurement, kept for why something is the way it is.

Status: record of measured state, written before publication. This is not legal advice.
The gating item was sideoppdrag and IP with Juridisk (`docs/16`). It is settled
(2026-10-11), and the code is public through the sanitised export (`docs/17`, "Status").

## Why this file exists

Two real cases were worked inside this repository as learning material: a øvelse survey
(`work/øvelse`) and a school-transport pattern (`examples/17`). The decision is that the
real material stays local and never enters git; only the method, the scripts, the templates,
the measured quirks and the tests belong here, on synthetic data.

That decision is only safe while it is written down somewhere the publication decision will
actually read. This is that place.

## "Clean enough to publish" has three categories, not one

A secret scanner would pass this repository today and it would still leak. The three
categories need different remedies, and only one of them is a scanner:

| Category | Remedy | Can a purge fix it? |
|---|---|---|
| 1. Personal data in history | history rewrite, then a server-side GC | partly; see below |
| 2. Internal references in prose | a reading pass | no |
| 3. Secrets and credentials | a scanner | yes, if any are found |

Category 2 is the largest here and the one most easily forgotten.

## Category 1: personal data. One vector remains, and it is measured

**Branch history is clean.** `work/` no longer appears in any commit reachable from any remote
branch. This was re-verified after the history rewrite, by walking every commit of every
remote head.

**One vector is left.** `refs/pull/53/head` still resolves to a commit whose tree contains
`work/øvelse/{raw,clean,facts}.json`: 13 respondent rows, with fields for company name,
contact person, that person's title, and their e-mail address.

This is measured, not inferred. An empty repository can still obtain them:

```
git init probe && cd probe
git remote add origin <this repo>
git fetch --depth=1 origin refs/pull/53/head
git ls-tree -r --name-only FETCH_HEAD -- work/
```

That returns the three files, and the served `raw.json` still carries 13 rows and the
contact-e-mail field. Anyone with read access can do this today.

**We cannot fix this ourselves, and three plausible routes were tried and ruled out.**

| Attempt | Result |
|---|---|
| Reopen the pull request, then rewrite its head | Refused. The API answers HTTP 422, "state cannot be changed. The pull request cannot be reopened." GitHub permits reopening only a pull request that was closed *without* merging. |
| Force-push the head branch so the pull ref follows | Does not work, and this is already demonstrated in this repository. The head branch was rewritten and now points at a clean commit with no `work/` in its history, while `refs/pull/53/head` stayed frozen at the pre-rewrite commit. The server stops tracking the branch once the pull request is closed. |
| Ask an administrator to garbage-collect | Not sufficient on its own. Garbage collection removes objects that are *unreachable*, and this commit is reachable from `refs/pull/53/head`. The old merge commit is still fetchable by direct SHA for the same reason. |

**The remedy therefore has two parts, in order.** A GHE site administrator has to delete
`refs/pull/53/head` itself, which needs server-side access rather than the API, and only then
does garbage collection remove the objects. A ticket that asks only for a GC will come back
reporting success while the data is still served.

The self-service alternative is to publish from a fresh repository rather than this one, which
costs the issue and pull-request history.

## Category 2: internal references. A reading pass, not a tool

A purge cannot help here, because the text is legitimate repository content that simply must
not leave Eksempel AS. Known classes, to drive the pass:

- internal hostnames and endpoints, for example the Nexus host in `pyproject.toml`
- `example.com` links, issue and pull-request numbers, and CI run ids
- internal programme and system names, for example plattformen, and Snowflake connection names
- colleague names, including those used in onboarding and review prose
- the øvelse case content: it names a regulated sector and describes obligations of real
  companies, even where the data itself is gone

`tools/scan_history.py` greps for these so the pass is repeatable, but a human has to make each
call: some references should be generalised, some deleted, some kept because they are part of
the public story.

## Category 3: secrets. Unknown until scanned

This repository has never been scanned. `tools/scan_history.py` runs `gitleaks` over full
history. "We have not committed secrets" is a belief until that command has printed a result.

## Before anything is published

In order, because later items are wasted effort if an earlier one fails:

1. Juridisk clears sideoppdrag and IP (`docs/16`). Done 2026-10-11.
2. A licence is adopted, with the artefact exception settled (`docs/17`).
3. `tools/scan_history.py` runs clean for category 3.
4. The category 2 reading pass is done, and its decisions recorded.
5. The category 1 vector is closed: an administrator has deleted `refs/pull/53/head` **and**
   garbage-collected, confirmed by re-running the fetch test above from an empty repository
   and getting nothing. A GC alone is not confirmation. Or publication happens from a fresh
   repository instead.
6. `python3 tools/check_tree.py` passes, so no new payload arrived while the above ran.

## The licence question, recorded as input only

`docs/17` drafts AGPL-3.0 with an artefact exception. AGPL-3.0 and GPL-3.0 are the same licence
except for section 13, verified against the licence texts themselves
(https://www.gnu.org/licenses/agpl-3.0.txt and https://www.gnu.org/licenses/gpl-3.0.txt):

- GPL-3.0 section 13, "Use with the GNU Affero General Public License", imposes no obligation.
  It only permits combining with AGPL-3.0 code. GPL-3.0 has no network clause of its own.
- AGPL-3.0 section 13, "Remote Network Interaction", requires that if you modify the program
  and users interact with your modified version remotely over a network, you must offer those
  users the Corresponding Source of your version, from a network server, at no charge.

What that means for this toolkit:

| Scenario | GPL-3.0 | AGPL-3.0 |
|---|---|---|
| Someone runs the tools locally to build an artefact | no obligation | no obligation; section 13 needs network interaction |
| Someone improves the toolkit and ships it onward | source must be offered | source must be offered |
| Someone improves it and runs it as a hosted generator, distributing nothing | changes may stay private | source must be offered |
| The artefact a recipient actually receives | unencumbered, via the artefact exception | unencumbered, via the artefact exception |

The only row where the two differ is the hosted generator; that is precisely the "managed
hosting" layer `docs/16` reserves. AGPL-3.0 protects it and GPL-3.0 leaves it open.

The cost of AGPL-3.0 is adoption friction: many organisations refuse AGPL-licensed code by
blanket policy, and such policies rarely distinguish running from redistributing. The artefact
exception reduces the exposure, because what a recipient receives is the artefact rather than
the generator, but the friction is real for anyone who wants to vendor the toolkit itself.

This section records the difference. It does not choose.
