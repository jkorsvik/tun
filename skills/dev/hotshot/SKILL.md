---
name: hotshot
description: "Full change-to-reviewable-PR pipeline under one name — 'use hotshot' or 'implement this with hotshot'. Drive a change the user described in chat (bug, feature, refactor, wording, tooling) end to end: understand, implement, verify with whatever gate the repo documents, run the magnus-review loop and fix until it relents, run simplify, commit to a typed branch, push, open the PR. Repo-agnostic: it discovers the build/test/verify commands, the base branch and the forge rather than assuming them. Use when the user says 'hotshot', 'use hotshot', 'implement this with hotshot', or names the sequence (review → simplify → push → PR)."
license: Internal
metadata:
  title: Hotshot
  version: 2.0.0
  tags: "git, workflow, pr, review, agnostic"
  platforms: "darwin, linux, win32"
---

# Hotshot

**Tier and cost, for the first reply:** none. It opens a branch and a PR on the repo it is
run in; merging is the reviewer's decision, and it asks before any outward step.

One word instead of eight steps. The user describes a change; this drives it all the way to
a pull request someone can read.

**Nothing here is new.** It is the round any careful engineer has always done: write the
change, prove it works, hand it to someone who tries to break it, cut what turned out
unnecessary, submit it for approval. What is new is that it happens on one instruction
instead of eight, and the reviewer is relentless and never gets tired or polite.

**This skill is deliberately stack-agnostic.** It names no build tool, no test runner, no
branch convention and no forge. Those are *discovered* per repo, in steps 2 and 5. A pipeline
that hardcodes one project's tooling does the wrong thing in the next one, silently.

## When to use

- The user says "hotshot", "use hotshot", "implement this with hotshot".
- The user names the sequence: "review, simplify, push, open a PR".

**Not for a one-line wording fix.** Editing a sentence in a doc is one line, not a round.
Just make the edit.

## The flow

### 1. Understand before editing

Trace the thing behind the request before touching it. `rg` every distinctive term from the
user's description; read the whole file, not the matching line; find every place that depends
on what you are about to change.

If the request removes something, find the commit that added it
(`git log --all --grep=<term>`, `git show <sha> --stat`) and revert at that commit rather than
hand-unpicking hunks.

Check where your branch sits against its base before patching, and fast-forward if behind.

> **Careful with remote-tracking refs.** A single-branch clone
> (`remote.origin.fetch = +refs/heads/<one>:...`) never updates any other branch, and
> `git show origin/<other>:file` will happily serve months-old content with no warning.
> Resolve a tip with `git ls-remote origin refs/heads/<branch>` when it matters. If the forge
> contradicts local git, the forge is right.

### 2. Discover the verification gate, then run it

Do not guess the commands. Find what this repo says, in this order, and stop at the first hit:

1. `AGENTS.md`, `CLAUDE.md` or `.claude/CLAUDE.md` — look for a section named *verification*,
   *gate*, *testing* or *checks*. A repo that documents its gate has told you the answer.
2. `CONTRIBUTING.md`, or the README's build and test section.
3. The build files: `Makefile` targets, `package.json` scripts, `pyproject.toml`, `go.mod`,
   `Cargo.toml`, `*.gradle`, `*.csproj`.
4. CI config (`.github/workflows/*.yml`, `.gitlab-ci.yml`). Whatever CI runs is the real gate,
   whether or not anyone wrote it down.

Then run it and **read the real exit status.** Never assert "green" from a command whose output
you piped; redirect to a file and check `$?`, or run it and read the code directly.

> **A passing gate is not a correct result.** If the change produces an artefact a human looks
> at — a document, a page, a report, an image, a PDF — open the artefact and check it. A clean
> build log tells you the build succeeded, not that the output is right. Where there is a
> rendered layout, actually look at it.

> **Check the gate was capable of failing.** If a check derives its own list of things to
> inspect, log the resolved list and confirm it was non-empty. A validator that matched zero
> files reports success, which is worse than failing, because it manufactures assurance. Watch
> for `continue-on-error`, for pipelines that swallow exit status, and for steps that exist but
> assert nothing.

### 3. Magnus review loop

Invoke the `magnus-review` skill against `<base>..HEAD`. It reviews through two lenses:
correctness (try to falsify the author's story; every claim traced to file:line) and
architecture (data structures over code, wrong coupling, names that lie).

Fix each blocking finding, then re-review until the verdict is APPROVE and the architecture
verdict is BLESSED with nothing blocking.

**Do not skip the loop because the first pass looked clean.** The loop exists to prove
cleanliness, not to assume it.

### 4. Simplify pass

Invoke the `simplify` skill. Fix what is in scope. For anything pre-existing or out of scope,
say so with a stated reason rather than silently widening the change. Do not let the PR grow.

### 5. Commit and push

Discover the conventions rather than importing them:

- **Base branch:** `git symbolic-ref refs/remotes/origin/HEAD`, or
  `gh repo view --json defaultBranchRef` and the equivalent elsewhere. Some repos integrate on
  `dev` and release from `main`; read `git log --merges --oneline -10` if unsure.
- **Commit style:** read `git log` and match what is already there. Do not impose conventional
  commits on a repo that does not use them, or drop them from one that does.
- **Branch name:** `<type>/<slug>`, type matching the dominant change (`fix/`, `feat/`,
  `chore/`, `refactor/`, `docs/`, `perf/`). Use the user's type if they named one.
- **Hooks:** a pre-commit hook may need tools on `PATH` that your shell has and its environment
  does not. Read the hook before fighting it.

Never commit to the base branch directly. Run `git status` first and confirm what is staged.
Check `.gitignore` before adding generated data, build output or large binaries; something
committed by accident cannot be taken back out of the history cheaply.

**Confirm the branch name with the user before pushing.** Pushing is part of this skill because
the user's prompt is the explicit ask, but the name is theirs to veto.

### 6. Open the PR

Base against the branch discovered above. Write the body to a file first, then use whichever
forge this repo uses:

```bash
gh pr create   --base <base> --body-file <file>                    # GitHub (set GH_HOST for an enterprise host)
glab mr create --target-branch <base> --description-file <file>    # GitLab
```

The body must carry: what changed and why, the verification evidence (which commands ran and
what they actually reported), and the review verdicts. If the change is visible on screen,
include before and after screenshots. If merging will auto-close a referenced issue and the
user only wanted part of it closed, say so and let them veto.

### 7. Report

Give the user the PR link and two lines on what a reviewer should look at first.

## Review hygiene

- **Claims need evidence or silence.** Quote the actual counts and verdicts. Never write "tests
  pass" from an exit code nobody read.
- **Grep every removed name repo-wide.** Zero hits is a real finding; report it as a verified
  strength rather than an assumption.
- **A measurement written down is a claim.** If the change alters a number quoted in a doc,
  re-measure and update it in the same commit. A stale measurement is worse than none, because
  someone will trust it.
- **Fix the layer that actually runs.** If the same thing is defined in two places and only one
  is executed, changing the other is theatre that turns the scanner green. Find which path
  provisions reality, and fix every path that does.
- **If a review surface went unreviewed**, name which one. Never present partial coverage as
  complete.

## Output

- A pushed `<type>/<slug>` branch.
- An open PR against the repo's real base branch, with summary, changes, verification evidence
  and review verdicts.
- Both review loops closed: magnus APPROVE, architecture BLESSED, simplify clean or explicitly
  dispositioned.
