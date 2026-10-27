#!/usr/bin/env python3
"""The release check decides, and it can decide no (ROADMAP C4).

`tools/release_check.py` answers one question: is what is on this machine the state a
release is built from, all six steps of it? A tool like that fails in two ways worth a
test suite. It can say yes when the state is wrong, which ships a stale export or a plugin
pinned to a commit the repository no longer serves. Or it can say "passed" while some of
its steps were never run, which is the gate-that-cannot-fail this repository keeps
finding.

So every scenario here builds real git repositories in a temp directory, breaks exactly
one thing, and requires the tool to name it:

    the working tree is dirty                     -> step 1 fails
    origin/main moved and was not fetched          -> step 1 fails, and says fetch
    main has commits the export branch lacks       -> step 2 fails, with the count
    the output is an older export (one file short) -> step 3 fails
    the internal path was not removed              -> step 3 fails
    one file's content drifted in the output        -> step 3 fails
    the public tree never got the sync              -> step 4 fails
    the public tree was edited on its own           -> step 4 fails
    the packager pins an older commit               -> step 6 fails
    the packager pin is not a SHA                   -> step 6 fails
    a step could not be decided                     -> exit 3, and fail under --require-all

And the control at the end: the same scenarios with nothing broken must all pass, so none
of the failures above is the normal answer.

stdlib only, no network, no browser. Run: python3 tests/test_release_check.py
"""
from __future__ import annotations

import contextlib
import io
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "release_check.py"
sys.path.insert(0, str(ROOT / "tools"))

import release_check  # noqa: E402

FAILURES: list[str] = []
CHECKS = 0


def check(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if ok:
        print(f"  \u2713 {what}")
    else:
        print(f"  \u2717 {what}" + (f"  [{detail}]" if detail else ""))
        FAILURES.append(what)


def git(cwd: pathlib.Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=test",
         "-c", "commit.gpgsign=false", *args],
        cwd=str(cwd), capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} in {cwd}: {proc.stderr}")
    return proc.stdout.strip()


def write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_scenario(base: pathlib.Path) -> dict[str, pathlib.Path]:
    """A whole release route in miniature: forge, export branch, output, public, packager."""
    base.mkdir(parents=True, exist_ok=True)
    forge = base / "forge.git"
    forge.mkdir()
    git(forge, "init", "-q", "--bare", "-b", "main")

    src = base / "src"
    git(base, "clone", "-q", str(forge), "src")
    write(src / "a.txt", "alpha\n")
    write(src / "docs" / "b.txt", "beta\n")
    write(src / "internal" / "secret.txt", "never exported\n")
    write(src / "plugins" / "eksempel" / "x.txt", "never exported\n")
    write(src / "export.sh", "#!/bin/sh\nSRC=src\n")
    git(src, "add", "-A")
    git(src, "commit", "-q", "-m", "main: the real tree")
    git(src, "push", "-q", "origin", "main")

    # The export branch: main with the internal paths removed, exactly as sanitise does.
    git(src, "checkout", "-q", "-b", "chore/sanitise-for-export")
    shutil.rmtree(src / "internal")
    shutil.rmtree(src / "plugins")
    git(src, "add", "-A")
    git(src, "commit", "-q", "-m", "sanitise: internal paths out")
    git(src, "push", "-q", "origin", "chore/sanitise-for-export")
    git(src, "checkout", "-q", "main")
    git(src, "fetch", "-q", "origin")

    # The export output: a fresh single-commit repository, as export.sh leaves it.
    out = base / "out-20260101-000000"
    out.mkdir()
    git(out, "init", "-q", "-b", "main")
    for rel in ("a.txt", "docs/b.txt", "export.sh"):
        write(out / rel, (src / rel).read_text(encoding="utf-8"))
    git(out, "add", "-A")
    git(out, "commit", "-q", "-m", "Tun: initial import")

    # The public clone: the same files, byte for byte.
    public = base / "public"
    public.mkdir()
    git(public, "init", "-q", "-b", "main")
    for rel in ("a.txt", "docs/b.txt", "export.sh"):
        write(public / rel, (out / rel).read_text(encoding="utf-8"))
    git(public, "add", "-A")
    git(public, "commit", "-q", "-m", "Merge pull request #1 from example/sync/x")
    public_sha = git(public, "rev-parse", "HEAD")

    packager = base / "packager"
    write(packager / "UPSTREAM_COMMIT", public_sha + "\n")
    (packager / "dist" / "unpacked").mkdir(parents=True)
    write(packager / "tools" / "build.sh", "#!/bin/sh\n")

    # A relative remote, so a copied scenario keeps pointing at its own forge.
    git(src, "remote", "set-url", "origin", "../forge.git")
    return {"forge": forge, "src": src, "out": out, "public": public, "packager": packager}


def clone_scenario(template: pathlib.Path, dest: pathlib.Path) -> dict[str, pathlib.Path]:
    """A copy of a built scenario. Building one costs about twenty git calls; the cases
    only differ by one file each, so copying is most of the suite's wall clock saved."""
    shutil.copytree(template, dest)
    return {"forge": dest / "forge.git", "src": dest / "src", "out": dest / "out-20260101-000000",
            "public": dest / "public", "packager": dest / "packager"}


def run_tool(sc: dict[str, pathlib.Path], *extra: str, runs: list | None = None) -> tuple[int, str]:
    argv = ["--repo", str(sc["src"]), "--export-dir", str(sc["out"].parent),
            "--out", str(sc["out"]), "--public", str(sc["public"]),
            "--packager", str(sc["packager"]), *extra]
    if runs is None:
        runs = [{"head_sha": git(sc["public"], "rev-parse", "HEAD"), "conclusion": "success",
                 "status": "completed", "name": "gates"}]
    if runs is not False:                # False leaves the CI step to the network
        path = sc["src"].parent / "runs.json"
        path.write_text(json.dumps({"workflow_runs": runs}), encoding="utf-8")
        argv += ["--runs-json", str(path)]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            code = release_check.main(argv)
        except SystemExit as exc:            # argparse
            code = int(exc.code or 0)
    return code, buf.getvalue()


def step_line(output: str, number: int) -> str:
    """The verdict line for one step, whatever its status word is."""
    marker = re.compile(rf"^\s*(PASS|FAIL|SKIP)\s+{number}\s")
    for line in output.splitlines():
        if marker.match(line):
            return line.strip()
    return ""


def main() -> int:
    base = pathlib.Path(tempfile.mkdtemp(prefix="release-check-"))
    try:
        make_scenario(base / "template")
        template = base / "template"
        print("\n1. nothing broken: every step passes, and the three undecidable ones are named")
        sc = clone_scenario(template, base / "clean")
        code, out = run_tool(sc)
        check(code == 0, "a clean release route exits 0", f"exit {code}")
        check("6 passed, 0 failed" in out, "six steps pass", out.strip().splitlines()[-1])
        for n in range(1, 7):
            check("PASS" in step_line(out, n), f"step {n} is PASS", step_line(out, n)[:90])
        # Step 5 reads GitHub, so the suite calls it with a run list instead of the network.
        runs = [{"head_sha": git(sc["public"], "rev-parse", "HEAD"), "conclusion": "success",
                 "status": "completed", "name": "gates"}]
        try:
            detail = release_check.step_public_ci(sc["public"], runs=runs)
            check("green on the release commit" in detail, "a green run on that commit passes", detail)
        except (release_check.Bad, release_check.Undecidable) as exc:
            check(False, "a green run on that commit passes", str(exc))
        try:
            release_check.step_public_ci(sc["public"], runs=[])
            check(False, "no run at all is undecided, never a pass")
        except release_check.Undecidable:
            check(True, "no run at all is undecided, never a pass")
        try:
            release_check.step_public_ci(sc["public"], runs=[
                {"head_sha": git(sc["public"], "rev-parse", "HEAD"), "conclusion": "failure",
                 "status": "completed", "name": "gates"}])
            check(False, "a red run on that commit fails")
        except release_check.Bad:
            check(True, "a red run on that commit fails")
        try:
            release_check.step_public_ci(sc["public"], runs=[
                {"head_sha": git(sc["public"], "rev-parse", "HEAD"), "conclusion": None,
                 "status": "in_progress", "name": "gates"}])
            check(False, "a run still going is not a pass")
        except release_check.Bad:
            check(True, "a run still going is not a pass")

        print("\n2. one thing broken at a time: the tool says which step, and refuses")
        sc = clone_scenario(template, base / "dirty")
        write(sc["src"] / "uncommitted.txt", "oops\n")
        code, out = run_tool(sc)
        check(code == 1 and "uncommitted" in step_line(out, 1), "a dirty tree fails step 1",
              step_line(out, 1)[:100])

        sc = clone_scenario(template, base / "moved")
        other = base / "moved-other"
        git(base, "clone", "-q", str(sc["forge"]), "moved-other")
        write(other / "c.txt", "gamma\n")
        git(other, "add", "-A")
        git(other, "commit", "-q", "-m", "someone else merged")
        git(other, "push", "-q", "origin", "main")
        code, out = run_tool(sc)
        check(code == 1 and "fetch" in step_line(out, 1),
              "an unfetched origin/main fails step 1 and says fetch", step_line(out, 1)[:110])

        sc = clone_scenario(template, base / "behind")
        write(sc["src"] / "late.txt", "late\n")
        git(sc["src"], "add", "-A")
        git(sc["src"], "commit", "-q", "-m", "main moves on")
        git(sc["src"], "push", "-q", "origin", "main")
        code, out = run_tool(sc)
        check(code == 1 and "1 commit(s) would not be exported" in step_line(out, 2),
              "main moving past the export branch fails step 2 with the count",
              step_line(out, 2)[:120])

        sc = clone_scenario(template, base / "short-out")
        (sc["out"] / "docs" / "b.txt").unlink()
        git(sc["out"], "add", "-A")
        git(sc["out"], "commit", "-q", "-m", "Tun: initial import")
        code, out = run_tool(sc)
        line = step_line(out, 3)
        check(code == 1 and "only in the branch: docs/b.txt" in line,
              "an export output missing a file fails step 3 and names the file", line[:130])

        sc = clone_scenario(template, base / "leak")
        write(sc["out"] / "internal" / "secret.txt", "never exported\n")
        git(sc["out"], "add", "-A")
        git(sc["out"], "commit", "-q", "-m", "Tun: initial import")
        code, out = run_tool(sc)
        check(code == 1 and "internal" in step_line(out, 3),
              "an internal path left in the output fails step 3", step_line(out, 3)[:120])

        sc = clone_scenario(template, base / "drift")
        write(sc["out"] / "a.txt", "alpha, edited after export\n")
        git(sc["out"], "add", "-A")
        git(sc["out"], "commit", "-q", "-m", "Tun: initial import")
        code, out = run_tool(sc)
        check(code == 1 and "content differs: a.txt" in step_line(out, 3),
              "output content that no longer matches the branch fails step 3", step_line(out, 3)[:120])

        sc = clone_scenario(template, base / "unsynced")
        write(sc["public"] / "new.txt", "came with the export\n")
        git(sc["public"], "add", "-A")
        git(sc["public"], "commit", "-q", "-m", "public edit")
        code, out = run_tool(sc)
        check(code == 1 and "only in the public tree: new.txt" in step_line(out, 4),
              "a public-only file fails step 4 and names it", step_line(out, 4)[:130])

        sc = clone_scenario(template, base / "public-edit")
        write(sc["public"] / "a.txt", "edited on the public side\n")
        git(sc["public"], "add", "-A")
        git(sc["public"], "commit", "-q", "-m", "public edit")
        code, out = run_tool(sc)
        check(code == 1 and "content differs: a.txt" in step_line(out, 4),
              "a public-only edit fails step 4, so the next sync cannot revert it in silence",
              step_line(out, 4)[:120])

        sc = clone_scenario(template, base / "stale-pin")
        write(sc["packager"] / "UPSTREAM_COMMIT", "0" * 40 + "\n")
        code, out = run_tool(sc)
        check(code == 1 and "UPSTREAM_COMMIT is 0000000" in step_line(out, 6),
              "a packager pinned elsewhere fails step 6", step_line(out, 6)[:140])

        sc = clone_scenario(template, base / "bad-pin")
        write(sc["packager"] / "UPSTREAM_COMMIT", '"$(tr -d)\n')
        code, out = run_tool(sc)
        check(code == 1 and "not a 40-character SHA" in step_line(out, 6),
              "a pin that is not a SHA fails step 6 instead of being trusted",
              step_line(out, 6)[:120])

        print("\n3. undecided is its own answer, and --require-all refuses it")
        sc = clone_scenario(template, base / "no-packager")
        shutil.rmtree(sc["packager"])
        code, out = run_tool(sc)
        check(code == 3, "a missing step exits 3, not 0", f"exit {code}")
        check("UNDECIDED" in out, "the verdict says nothing here is releasable", out.strip()[-90:])
        check("SKIP" in step_line(out, 6), "the missing packager is SKIP, not PASS", step_line(out, 6))
        code2, out2 = run_tool(sc, "--require-all")
        check(code2 == 1, "--require-all turns an undecided step into a failure", f"exit {code2}")

        print("\n4. the checklist is honest about what it read")
        code, out = run_tool(clone_scenario(template, base / "json"), "--json")
        try:
            parsed = json.loads(out)
            steps = parsed.get("steps", [])
            check(code == 0 and len(steps) == 6, "the JSON form carries all six steps", str(len(steps)))
            check(all(set(s) == {"step", "status", "detail"} for s in steps),
                  "each step carries a verdict and its evidence")
        except json.JSONDecodeError as exc:
            check(False, "the JSON form carries all six steps", str(exc))
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print()
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} of {CHECKS} checks failed")
        for name in FAILURES:
            print(f"  - {name}")
        return 1
    print(f"PASS: {CHECKS} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
