# Git hygiene when a repo has touched real data

**Reader:** contributor — you are changing the toolkit, and need the constraint or the convention behind it.

Lessons from one incident in this project (September 2026). A working copy held real
records from a pilot. Some of that material reached the shared history. Cleaning it up
took a history rewrite, and one copy is still out of reach. Nothing here is specific to
Tún. It applies to any repo where real data and example code live close together.

The concrete facts of the incident (which ref, which ids) are kept in an internal note.
They are not part of this document.

## 1. Block pushes from a clone that holds real data

Set the push URL of that clone to a value that cannot work:

```sh
git config remote.origin.pushurl NO-PUSH-local-only-real-data
```

Fetch still works. Every push fails at once, with the reason in the error message. Use it
on any clone or worktree that holds real records, even for a short time. Remove it only
when the real data is gone from that clone.

## 2. `git add -A` in a shared checkout is a claim about files you do not own

A merge was staged with `git add -A` in a checkout where another task was writing
scratch files. The scratch files held real survey answers. They went into the merge
commit. Nothing in the conflict list showed them, because they were not conflicts.

- In a shared checkout, stage explicit paths.
- Before committing a merge, read `git status --porcelain` for entries you did not expect,
  not only for conflicts.

## 3. Repair after an accidental sweep

1. Untrack the files with `git rm --cached` in a new commit. Do not delete them: they may
   belong to someone else.
2. Ignore them by pattern, not by exact name.
3. Decide separately whether to rewrite history. Until you do, the blobs stay reachable
   in history. Who decides is the repo owner, not the person who made the mistake.

## 4. A history rewrite, and how to check it

- `git filter-repo` with the offending paths, over all branches.
- Prove that you removed only what you meant to remove: every other author's commits must
  be byte-for-byte identical outside the stripped paths. In the incident, all commits by
  the second author were compared this way.
- Then list every ref with `git for-each-ref`. Stale branches, tags, stashes and remote
  tracking refs keep old objects alive.
- `git gc --prune=now` cleans only your local copy. Commits that no ref points to stay
  reachable by SHA on the forge until the forge runs its own garbage collection.

## 5. The forge keeps refs you cannot delete

A pull request's head ref (`refs/pull/N/head`) is held by the server. A normal clone does
not fetch it, so a local audit does not see it. It cannot be deleted through the API, and
it keeps serving the old commits after a rewrite. Two obvious fixes do not work:

- Force-pushing the head branch does not move the pull ref. After the pull request is
  closed, the server stops following the branch, and the ref stays frozen.
- Garbage collection alone does not remove the commit, because the ref still reaches it.

Only a forge administrator can purge the ref. Until then, making the same repository
public also publishes that ref. A fresh repository built from a clean export does not
carry it. This is why Tún is exported to a new repository instead of opening the old one.

## 6. A ruleset that blocks force-push does not block direct writes

A ruleset that blocks deletion and force-push, but has no `pull_request` rule, still lets
anyone with write access push straight to the branch through the API. If review is the
control, the ruleset must require a pull request.

## 7. Archive a branch with real data before deleting it

An unpushed worktree is still found by anyone who lists worktrees or reads old session
notes. To retire one:

1. `git bundle create` for the branch, plus a `tar` of the working tree.
2. Verify the bundle (`git bundle verify`) and record the tip SHA.
3. Store both outside any synced or committed directory.
4. Delete the worktree, the local branch and any remote branch. Prune the refs. Run GC.

## 8. Check identity after a rename or a long pause

The repo was renamed while old notes still used the old name. The old clone's tracking
refs agreed with themselves, and a push through the rename redirect succeeded without
warning. So a green push is no proof that you are working on the current repository.
Before you act on old notes, resolve the repository by its forge identity and fetch the
branch tips again with `git ls-remote`.

Before any go-public step, the preconditions and what is deliberately still open: [publication readiness](20-publication-readiness.md).
