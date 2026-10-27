#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The release route as one checklist (ROADMAP C4).

Six steps sit between "merged on the internal forge" and "a new version in the
Marketplace". Each has its own guard, and each guard was written after the step went
wrong once, so a checklist that merely lists them is worth nothing. This runs the ones
that can be decided from git state and prints the ones that cannot.

    1. the internal forge is at the release state    decided here
    2. the export branch carries that main           decided here
    3. the export output is the export branch        decided here
    4. the public tree is that output, byte for byte decided here
    5. the public CI run is green                    needs `gh`, else SKIP
    6. the Marketplace packager names that commit    needs the packager, else SKIP

Statuses, and why there are three:

    PASS   decided here, from the refs and the trees
    FAIL   decided here, and it says do not ship
    SKIP   cannot be decided from here. The exact command that decides it is printed.

A tool that printed "9 checks passed" while three of them were never run would be the
gate-that-cannot-fail this repository keeps finding. So a SKIP is not quietly a pass: the
exit status is 3 when nothing failed but something was left undecided, and `--require-all`
turns every SKIP into a failure for the final sign-off.

    python3 tools/release_check.py                       # defaults, from this checkout
    python3 tools/release_check.py --require-all         # before saying "released"
    python3 tools/release_check.py --json                # for a script to read

Exit: 0 every step passed, 1 a step failed, 2 git is missing, 3 undecided (no failure).

The export route itself (export.sh, the public clone, the packager) lives outside this
repository on purpose: it holds the never-named list and the public identity. So every
path is a flag with a default, and nothing here assumes the numbers in one home directory.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

DEFAULTS = {
    "export_dir": "~/dev/work/tun-export",
    "export_branch": "chore/sanitise-for-export",
    "internal": "internal,plugins/tun",
    "packager": "~/dev/personal/raiwork-tun-plugin",
}
#: The public repository, as owner/name. Configuration, not a constant: the tree
#: that ships carries no personal handle, and whoever runs the tool sets
#: TUN_PUBLIC_REPO locally.
PUBLIC_REPO = os.environ.get("TUN_PUBLIC_REPO", "example/tun")


class Undecidable(Exception):
    """A step whose inputs are not on this machine. SKIP, with the reason."""


class Bad(Exception):
    """A step decided here, and the answer is no."""


def git(cwd: pathlib.Path, *args: str) -> str:
    """Run git in `cwd` and return stdout. A failure is the caller's to interpret."""
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=120
    )
    if proc.returncode != 0:
        raise Bad(
            f"git {' '.join(args)} failed in {cwd}: "
            f"{(proc.stderr or proc.stdout).strip().splitlines()[:1]}"
        )
    return proc.stdout.strip()


def remote_tip(cwd: pathlib.Path, branch: str) -> str:
    """The remote's own answer for one branch. Never a tracking ref: those go stale."""
    out = git(cwd, "ls-remote", "origin", f"refs/heads/{branch}")
    if not out:
        raise Bad(f"origin has no branch {branch}")
    return out.split()[0]


def tree(repo: pathlib.Path, rev: str, drop: tuple[str, ...] = ()) -> dict[str, str]:
    """path -> blob sha for a revision. A blob sha is a hash of the content, so two
    repositories agree exactly when the files agree, with no bytes read."""
    out = git(repo, "ls-tree", "-r", rev)
    files: dict[str, str] = {}
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) < 3 or parts[1] != "blob":
            continue
        if any(path == d or path.startswith(d + "/") for d in drop):
            continue
        files[path] = parts[2]
    return files


def diff_note(want: dict[str, str], got: dict[str, str], want_name: str, got_name: str) -> str:
    """One line naming what differs, capped so a full-tree difference stays readable."""
    missing = sorted(set(want) - set(got))
    extra = sorted(set(got) - set(want))
    differ = sorted(p for p in set(want) & set(got) if want[p] != got[p])
    bits = []
    for label, paths in ((f"only in {want_name}", missing), (f"only in {got_name}", extra),
                         ("content differs", differ)):
        if paths:
            shown = ", ".join(paths[:6]) + (f" and {len(paths) - 6} more" if len(paths) > 6 else "")
            bits.append(f"{label}: {shown}")
    return f"{len(want)} file(s) in {want_name}, {len(got)} in {got_name}; " + "; ".join(bits)


# --------------------------------------------------------------------------- the steps


def step_forge(repo: pathlib.Path) -> str:
    """1. The internal forge is at the release state: merged, fetched, nothing undecided."""
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if branch != "main":
        raise Bad(f"HEAD is {branch}, not main: the route starts after the merge lands")
    dirty = git(repo, "status", "--porcelain")
    if dirty:
        raise Bad(f"{len(dirty.splitlines())} uncommitted path(s): a release is built from a commit, "
                  "not from a working tree")
    tracked = git(repo, "rev-parse", "origin/main")
    actual = remote_tip(repo, "main")
    if tracked != actual:
        raise Bad(f"origin/main is {tracked[:7]} locally and {actual[:7]} on the forge: fetch, "
                  "because every comparison below trusts this ref")
    return f"origin/main {actual[:7]}, worktree clean"


def step_export_branch(repo: pathlib.Path, branch: str) -> str:
    """2. The export branch carries this main. If it does not, the export ships old code."""
    tip = remote_tip(repo, branch)
    git(repo, "fetch", "-q", "origin", f"+refs/heads/{branch}:refs/remotes/origin/{branch}")
    local = git(repo, "rev-parse", f"origin/{branch}")
    if local != tip:
        raise Bad(f"origin/{branch} is {local[:7]} locally and {tip[:7]} on the forge")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "origin/main", tip],
        cwd=str(repo), capture_output=True, text=True,
    )
    if ancestor.returncode != 0:
        behind = git(repo, "rev-list", "--count", f"{tip}..origin/main")
        raise Bad(f"{branch} does not contain main: {behind} commit(s) would not be exported. "
                  f"Merge origin/main into {branch} and sanitise again")
    return f"{branch} {tip[:7]} contains origin/main"


def step_export_output(repo: pathlib.Path, branch: str, out: pathlib.Path,
                       internal: tuple[str, ...]) -> str:
    """3. The export output is the export branch, minus the internal paths. This is the
    guard export.sh needed on 2026-10-11, when a stale local branch archived 220 files
    instead of 261 and every later check passed."""
    if not out.is_dir():
        raise Undecidable(f"no export output at {out}")
    want = tree(repo, f"origin/{branch}", drop=internal)
    try:
        got = tree(out, "HEAD")
    except Bad as exc:
        raise Undecidable(f"{out.name} is not a git repository: {exc}") from exc
    if want != got:
        raise Bad(f"{out.name} is not origin/{branch}: " + diff_note(want, got, "the branch", out.name))
    for path in internal:
        if path in got:
            raise Bad(f"{out.name} still holds the internal path {path}")
    return f"{out.name} == origin/{branch} minus {len(internal)} internal path(s), {len(got)} file(s)"


def step_public(export_out: pathlib.Path, public: pathlib.Path) -> str:
    """4. The public tree is that export output, byte for byte.

    Two failures this catches, and neither is visible from either side alone: a file that
    was never copied (the public page keeps serving old bytes), and a public-only edit
    that the next sync will silently revert.
    """
    if not (public / ".git").exists():
        raise Undecidable(f"no public clone at {public}")
    want = tree(export_out, "HEAD")
    try:
        got = tree(public, "HEAD")
    except Bad as exc:
        raise Undecidable(f"{public} has no HEAD: {exc}") from exc
    if want != got:
        raise Bad(diff_note(want, got, "the export", "the public tree"))
    return f"{len(got)} file(s) identical to the export output"


def step_public_ci(public: pathlib.Path, runs: list | None = None) -> str:
    """5. The public CI run for that commit is green. It is the only three-engine gate.

    A merge commit often has no run of its own: the workflow runs on the branch, and the
    merge only joins the results. So the question asked here is the honest one: is there a
    green run for a commit this one contains, and none of them red? A missing run is
    undecided, never a pass.
    """
    if runs is None:                     # the suite passes a list, so it needs no network
        try:
            proc = subprocess.run(
                ["gh", "api", f"repos/{PUBLIC_REPO}/actions/runs?per_page=20"],
                capture_output=True, text=True, timeout=90,
            )
        except (FileNotFoundError, OSError):
            raise Undecidable("gh is not installed")
        if proc.returncode != 0:
            raise Undecidable(f"gh could not read {PUBLIC_REPO}: {(proc.stderr or '').strip()[:120]}")
        try:
            runs = json.loads(proc.stdout or "{}").get("workflow_runs", [])
        except (json.JSONDecodeError, AttributeError):
            raise Undecidable("gh returned something that is not a run list")
    if not (public / ".git").exists():
        raise Undecidable("the public clone is needed to tell which commits this one contains")
    head = git(public, "rev-parse", "HEAD")

    contained = []
    for run in runs:
        sha = run.get("head_sha", "")
        if not sha:
            continue
        inside = subprocess.run(["git", "merge-base", "--is-ancestor", sha, head],
                                cwd=str(public), capture_output=True)
        if inside.returncode == 0:
            contained.append(run)
    if not contained:
        raise Undecidable(f"no run among the last 20 is for a commit {head[:7]} contains: "
                          f"open https://github.com/{PUBLIC_REPO}/actions")
    red = [r for r in contained if r.get("conclusion") not in ("success", "skipped")]
    if red:
        raise Bad("; ".join(f"{r.get('name')} on {r['head_sha'][:7]}: {r.get('conclusion')}"
                            for r in red[:3]))
    newest = contained[0]
    mine = [r for r in contained if r.get("head_sha") == head]
    if mine:
        return f"{mine[0].get('name')} green on the release commit {head[:7]}"
    return (f"no run for the merge commit {head[:7]} itself; the newest run for a commit it "
            f"contains is {newest.get('name')} on {newest['head_sha'][:7]}: success")


def step_packager(packager: pathlib.Path, public: pathlib.Path) -> str:
    """6. The Marketplace packager builds from that public commit. A packager pinned to an
    older commit ships a plugin whose docs link at a SHA the repository no longer serves."""
    if not packager.is_dir():
        raise Undecidable(f"no packager at {packager}")
    if not (public / ".git").exists():
        raise Undecidable("the packager check needs the public clone to compare against")
    sha = git(public, "rev-parse", "HEAD")
    pin_file = packager / "UPSTREAM_COMMIT"
    if not pin_file.is_file():
        raise Bad(f"no UPSTREAM_COMMIT file in {packager.name}: the build would use whatever "
                  "is cloned")
    pinned = pin_file.read_text(encoding="utf-8").strip()
    if len(pinned) != 40 or any(c not in "0123456789abcdef" for c in pinned):
        raise Bad(f"UPSTREAM_COMMIT holds {pinned[:20]!r}, not a 40-character SHA: "
                  "tools/fetch_upstream.sh refuses this")
    if not sha.startswith(pinned[:7]) and not pinned.startswith(sha[:7]):
        behind = subprocess.run(["git", "merge-base", "--is-ancestor", pinned, sha],
                                cwd=str(public), capture_output=True)
        relation = ("an ancestor of it, so the plugin is behind" if behind.returncode == 0
                    else "not in the public history at all")
        raise Bad(f"UPSTREAM_COMMIT is {pinned[:7]}, public main is {sha[:7]} ({relation}). "
                  f"Write {sha} to UPSTREAM_COMMIT, run tools/build.sh, then make-public")
    if not (packager / "dist" / "unpacked").is_dir():
        raise Undecidable("no dist/unpacked yet: build with tools/build.sh, then re-run")
    return f"UPSTREAM_COMMIT {pinned[:7]} == public main, dist/unpacked present"


# --------------------------------------------------------------------------- the runner


def newest_output(export_dir: pathlib.Path) -> pathlib.Path | None:
    """export.sh names its output out-YYYYmmdd-HHMMSS, so the names sort by build time."""
    if not export_dir.is_dir():
        return None
    outs = sorted(p for p in export_dir.glob("out-*") if p.is_dir())
    return outs[-1] if outs else None


def run(args) -> int:
    repo = pathlib.Path(args.repo).expanduser().resolve()
    export_dir = pathlib.Path(args.export_dir).expanduser()
    internal = tuple(p.strip() for p in args.internal.split(",") if p.strip())
    steps = []

    def record(name: str, fn, *fargs):
        try:
            steps.append((name, "PASS", fn(*fargs)))
        except Bad as exc:
            steps.append((name, "FAIL", str(exc)))
        except Undecidable as exc:
            steps.append((name, "SKIP", str(exc)))

    record("1 internal forge at the release state", step_forge, repo)
    record("2 the export branch carries that main", step_export_branch, repo, args.export_branch)
    out = pathlib.Path(args.out).expanduser() if args.out else newest_output(export_dir)
    if out is None:
        steps.append(("3 the export output is that export branch", "SKIP",
                      f"no out-* directory in {export_dir}: run export.sh {args.export_branch}"))
        steps.append(("4 the public tree is that output, byte for byte", "SKIP",
                      "no export output to compare the public tree with"))
    else:
        record("3 the export output is that export branch", step_export_output,
               repo, args.export_branch, out, internal)
        record("4 the public tree is that output, byte for byte", step_public, out,
               pathlib.Path(args.public).expanduser())
    runs = None
    if args.runs_json:                   # an offline sign-off, from a saved run list
        try:
            runs = json.loads(pathlib.Path(args.runs_json).expanduser().read_text(encoding="utf-8"))
            if isinstance(runs, dict):        # the gh body, or a bare list of runs
                runs = runs.get("workflow_runs", [])
            if not isinstance(runs, list):
                raise ValueError("expected a run list or a {workflow_runs: [...]} body")
        except (OSError, json.JSONDecodeError) as exc:
            steps.append(("5 public CI is green on that commit", "FAIL",
                          f"--runs-json could not be read: {exc}"))
            runs = "unreadable"
    if runs != "unreadable":
        record("5 public CI is green on that commit", step_public_ci,
               pathlib.Path(args.public).expanduser(), runs)
    record("6 the Marketplace packager names that commit", step_packager,
           pathlib.Path(args.packager).expanduser(), pathlib.Path(args.public).expanduser())

    if args.json:
        print(json.dumps({"repo": str(repo), "steps": [
            {"step": n, "status": s, "detail": d} for n, s, d in steps]}, indent=2))
    else:
        width = max(len(n) for n, _, _ in steps)
        print()
        for name, status, detail in steps:
            print(f"  {status:4}  {name.ljust(width)}  {detail}")
        counts = {s: sum(1 for _, st, _ in steps if st == s) for s in ("PASS", "FAIL", "SKIP")}
        print(f"\nrelease check: {counts['PASS']} passed, {counts['FAIL']} failed, "
              f"{counts['SKIP']} undecided")
        if counts["FAIL"]:
            print("release check: FAIL - do not ship")
        elif counts["SKIP"]:
            print("release check: UNDECIDED - the steps above were not checked, so nothing "
                  "here says this is releasable")

    if any(status == "FAIL" for _, status, _ in steps):
        return 1
    if args.require_all and any(status == "SKIP" for _, status, _ in steps):
        print("release check: FAIL - --require-all and a step was undecided", file=sys.stderr)
        return 1
    return 3 if any(status == "SKIP" for _, status, _ in steps) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".", help="the internal checkout (default: cwd)")
    parser.add_argument("--export-dir", default=DEFAULTS["export_dir"],
                        help=f"the export route's home (default: {DEFAULTS['export_dir']})")
    parser.add_argument("--export-branch", default=DEFAULTS["export_branch"])
    parser.add_argument("--out", default=None, help="the out-* directory to check (default: newest)")
    parser.add_argument("--public", default=None,
                        help="the public clone (default: <export-dir>/jk-tun)")
    parser.add_argument("--packager", default=DEFAULTS["packager"])
    parser.add_argument("--internal", default=DEFAULTS["internal"],
                        help="comma-separated paths that never leave the internal forge")
    parser.add_argument("--runs-json", default=None,
                        help="a saved `gh api .../actions/runs` body, so the CI step can be "
                             "decided without a network call")
    parser.add_argument("--require-all", action="store_true",
                        help="an undecided step fails the run, for the final sign-off")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.public is None:
        args.public = str(pathlib.Path(args.export_dir).expanduser() / "jk-tun")

    if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
        print("release check: FAIL - git is not on PATH", file=sys.stderr)
        return 2
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
