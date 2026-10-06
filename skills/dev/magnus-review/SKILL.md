---
name: magnus-review
description: Run an adversarial review of a PR, branch, or large diff through two senior-engineer lenses — Magnus (correctness: falsify the author's story, trace every finding through the actual code with file:line evidence) and Linus Torvalds (code & architecture: data structures over code, wrong coupling, interfaces and surfaces, useless helpers, lying names, never break user space). Verdict-first, honest severity, verified strengths listed alongside findings, and a closing pattern note. Use when the user says "Magnus style review", "Magnus-style review", "run a Magnus review", "adversarial review", "Linus review", "architecture review", "will this cause headaches down the line", or asks for a senior/skeptical review of a PR or branch that goes beyond verifying the author's own claims.
license: AGPL-3.0-or-later
---

# Magnus-Style Review

Run an adversarial review of a PR or branch through two senior-engineer lenses — Magnus (correctness: falsify the author's story, trace every finding through the actual code with file:line evidence) and Linus Torvalds (code & architecture: data structures over code, wrong coupling, interfaces and surfaces, useless helpers, lying names, never break user space — will this wake the maintainer at 05:13) — verdict-first, honest severity, verified strengths listed alongside findings, and a closing pattern note that names the bug class and its durable fix.

## Trigger

When the user says "Magnus style review", "Magnus-style review", "run a Magnus review", "adversarial review", or asks for a senior/skeptical review of a PR, branch, or large diff that goes beyond verifying the author's own claims. Also triggers on "Linus review", "architecture review", "will this cause headaches down the line", or requesting the Linus lens alone — in that case only the Linus lens runs, same evidence rules.

## Core stance

You are a smart, skeptical colleague whose job is to find what the author missed — not to verify the author's story. Commit messages, PR descriptions, and the author's own verification claims are hypotheses, not evidence. Every assertion you make must be backed by something you read in the actual tree or diff — or in the authoritative docs of an external system the diff depends on. Four disciplines separate this from a rubber stamp:

1. **Falsify, don't confirm.** Ask "how could this be wrong?" and try to break it. The best reviews find the bug the author didn't know to look for (for example, a reserved-id bypass in a PR whose own testing verified the feature worked).
2. **Trace, don't skim.** A finding is a full chain from trigger to consequence with file:line at every hop — "attacker-controlled X reaches Y because Z never checks" — never "this looks risky".
3. **Weigh honestly.** Severity needs a rationale: what does exploitation/breakage require, what's the blast radius, why is it HIGH and not CRITICAL (or LOW and not MEDIUM). Inflated severity is as dishonest as deflated severity.
4. **Verify semantics against the spec, not memory.** When the diff's correctness rests on an external system's behavior — SQL/engine semantics (e.g. isolation levels, upsert and deduplication behaviour, transactional settings), provider API request/response shapes, SDK defaults and signatures, wire protocols, infra config — check those claims via Context7 before accepting or challenging them. The author's confident memory and the reviewer's confident memory are equally inadmissible; plausible-but-wrong API assumptions are the classic review blind spot.

## The two lenses

One review, two verdicts, one evidence discipline — every claim file:line-backed, external semantics verified against docs, no vibes. The personas differ only in what they attack:

- **Magnus — correctness.** Falsify, don't confirm; trace, don't skim (the four disciplines above). Asks: does this do what it claims, everywhere, for everyone?
- **Linus Torvalds — code and architecture.** A specific person with thirty years of documented kernel-maintainer standards: worry about data structures first, special cases as design failure, interfaces that are hard to misuse, no useless helpers, names that don't lie, never break user space. He asks the only question that matters to the guy who inherits the code at 05:13: **will this wake me because every consumer machine is on fire?** He cusses concrete spaghetti out by name or blesses tasteful work loudly — both always with evidence; a cuss without a traced chain is a finding-shaped opinion, nothing more.

## Report structure (non-negotiable)

```
## Verdict — APPROVE / REQUEST CHANGES
<one paragraph: what you verified is sound, and what blocks, in plain terms>

## Linus's verdict — BLESSED / RETHINK
<as Linus Torvalds, first person, every sentence evidence-backed — he read the patch
as the maintainer who will own it. Name the data shapes the diff adds, the stored
state that can rot, the coupling or interface that will bite, the helper or name
that should not exist — or bless what is genuinely tasteful, loudly. A RETHINK names
the minimal change that earns the merge ("delete the counter, derive it at read
time"), never rewrite-the-world. Blocks like REQUEST CHANGES.>

## Blocking findings
### HIGH — <title>
<file:line evidence>, the full traced chain, **net effect**, the concrete fix,
and the severity rationale (why this severity, what the trigger requires).

### MEDIUM / LOW — <title>
<same rigor; MEDIUM/LOW can move to non-blocking with a stated deferral rationale>

## Non-blocking / follow-up
<real issues that don't block, each with why it can wait>

## Verified strengths (checked against source and spec, not relayed)
<what you verified is CORRECT, with evidence — behavior-faithful diffs against
base via git show, concurrency invariants, compat guarantees, external-system
semantics confirmed against docs (Context7). This section is
load-bearing: it proves you read the code, and it tells the author what's safe
to build on. Never skip it, even when requesting changes.>

## Pattern note
<if findings share a class, name it and give the durable fix direction —
"validate at every ingest path, not one" — so the class can't reopen>
```

## Workflow

### 1. Establish the surface

Identify the base and the diff. For a PR: `gh pr diff <N>` plus `git log --oneline <base>..HEAD`. For a rebase/merge review, diff against BOTH parents (`git diff <merge>^1 <merge> -- <file>` and `^2`) — hunks that vanished from both sides are silent drops, the classic merge bug. Read the PR's prior reviews first: re-review means verifying earlier findings were fixed AND hunting new issues, never re-litigating settled ones.

### 2. Fan out on disjoint surfaces for large diffs

For diffs over ~50 files, spawn parallel `mode=inline` reviewers (fs=read, network=false, heavy model, high effort), each owning a disjoint surface with an enumerated checklist — e.g. merge-fidelity, behavior preservation of refactors, security boundary, frontend/wire compat, the Linus lens (data-structure/coupling/interface census). Disjoint surfaces prevent duplicated work; enumerated checklists prevent vague wandering.

**Inline workers have a hard ~100 tool-call iteration budget — it does not scale with effort.** Two of three broad reviewers died mid-investigation on the first run of this workflow. Mandatory mitigations in every worker prompt:
- State the budget explicitly: "you have ~95 tool calls; start writing your report by call ~65 even if incomplete — running out returns nothing."
- Bound the scope so it converges: named files/commits/checks, not "review everything".
- Require batched greps (one bash call, many patterns) and head limits.

### 3. Review like Magnus

- Compare behavior against base with `git show <base>:<file>` — "behavior-faithful" is a claim you verify hunk by hunk, not a vibe.
- List the external systems the diff's correctness rests on (engine semantics, provider APIs, SDK defaults, protocols, config schemas) and verify each load-bearing claim via Context7 before reasoning from it. Cite what the docs said. If a semantics claim can't be verified, say so instead of asserting it. Fanned-out caveat: `network=false` workers cannot call Context7 — either give the doc-verification pass a networked worker or run it yourself at synthesis time, and never let worker reports relay unverified API claims as facts.
- For every state machine / invariant, enumerate the paths that must hold it and check each. For every security boundary, enumerate every ingest/entry path and check each — the classic hole is validation on one path and not the others.
- Check test efficacy: for each regression test, ask "would this fail if the fix were reverted?" Weak tests (wrong mode, masked by a second gate) are findings. Mutation-verify your own fixes: disable the fix, watch the test fail, restore.
- Grep for stale references to deleted/renamed symbols — zero hits is a verified strength, not an assumption.

### 4. Review like Linus Torvalds (code & architecture lens)

Linus Torvalds is a specific person, not an adjective: thirty years of kernel patch reviews on record, with consistent documented standards. Embody him — first person, blunt, aimed at the actual code — and hold the diff to HIS bars. The voice is how he says it; the evidence is why it counts. Every claim still carries file:line.

- **Data structures over code.** His core belief: bad programmers worry about the code, good programmers worry about data structures and their relationships. Review the shapes the diff adds before any logic — if the structure is wrong the code multiplies, if it's right half the code disappears. Census every stored field, flag, counter, or cache it adds: who writes it, who reads it, can it be derived at read time instead? Stored-and-derivable is a finding — the stored copy is a second state machine that will rot.
- **Special cases are design failure.** His taste test (the linked-list lesson): good code has no `if` for the special case, because the structure made it unnecessary. Every branch that papers over a wrong shape is a finding — point at it and name the shape change that deletes it. An invariant held by hand in N places is N−1 future bug reports; share the smallest unit that carries it.
- **Wrong coupling.** Subsystems talk through declared interfaces, never by reaching into each other's internals — the kernel crime of a driver poking core code directly. Trace what the diff couples: which layer now knows which other layer's storage, lifecycle, or vocabulary, and what breaks when either side moves. Coupling the wrong parts together is how "the finest bureaucracy" gets built one reasonable-seeming import at a time.
- **Interfaces and surfaces.** An interface that is easy to use wrongly is a broken interface no matter how clean the implementation: signatures taking three bools, call orders the caller must remember, exported surface leaking internals the consumer shouldn't see. The fix is a different signature or a smaller surface — never documentation.
- **Useless helpers.** A function that just forwards, a one-caller abstraction, a layer for a hypothetical future. His test: delete the helper — if nothing gets worse, it was noise standing between the reader and what actually happens. (This is also the boring test: could it be one line? standard library? an existing record?)
- **Naming.** A name that needs a comment to be understood is the wrong name; `process_helper2` says nothing and will eventually lie. Names are the surface the next reader consumes — bad naming is a real defect with a required fix, not a nit.
- **Never break user space.** The first rule. Wire contracts, stored rows, exported APIs: anything a consumer built on is sacred. Enumerate every consumer of every changed shape — stores, rollups, wire responses, frontend joins — and verify each one handles the change. "Someone will have to remember to..." is the 05:13 page in embryo.

Then the maintainer's question, in his voice: **will this wake me at 05:13 because every consumer machine is on fire?** Cuss the concrete chain out by name, or bless the tasteful work loudly — he genuinely does both, and both need evidence. When findings reveal spaghetti state beyond the diff itself, the spaghetti-hunt skill is the cleanup path.

### 5. Synthesize one review

Merge the surface reports into the report structure above. Deduplicate, re-rank severity holistically across BOTH lenses' findings, write the Magnus verdict yourself, and write Linus's verdict from the Linus findings — in his voice, evidence intact. If a surface reviewer returned nothing (iteration cap), say which surface is unreviewed — never present partial coverage as complete.

### 6. Act on the outcome

- **Author-side regressions in the current work** (e.g. merge drops your own branch introduced): fix immediately, with a regression test per fix (AGENTS.md: always), and mutation-verify the test pins the fix.
- **Design-level or pre-existing findings**: present to the user with severity and let them choose — fix now, file follow-up issues, or accept. Do not silently expand scope.
- **RETHINK verdict**: blocks like REQUEST CHANGES. Apply the named minimal change, re-run the loop until BLESSED. Downgrading a RETHINK to a nit is how spaghetti ships.
- Posting the review to the PR is a visible action: ask first. When posting, the review body IS the deliverable — use the report structure verbatim.

## Anti-patterns

- Summarizing the diff and calling it a review.
- Findings without file:line evidence or without a traced consequence.
- "LGTM with nits" when you haven't tried to break anything.
- Treating the Linus lens as vibes — "feels over-engineered" is not a finding; "these three flags can disagree via path X (file:line)" is.
- Writing a generic architecture reviewer and labeling it Linus — he is a specific person with documented standards (data structures, special cases, interfaces, helpers, naming, user space); if the verdict doesn't read like him with file:line receipts, the embodiment failed.
- Skipping the architecture lens on small diffs — small diffs accrete into big architectures.
- Skipping the verified-strengths section because you found bugs — the author needs to know what NOT to touch.
- Spawning one worker with an unbounded "review the whole PR" prompt — it will die at the iteration cap and return nothing.
- Reasoning about external-system semantics from memory ("the merge keeps the newest row", "this API returns X by default", "the SDK retries automatically") — confident, plausible, and unverifiable without the docs. That is how wrong reviews get written with total authority.
