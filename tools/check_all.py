#!/usr/bin/env python3
"""Run every gate in parallel and print one verdict.

ROADMAP C3. The suites are independent, so running them one after another is a choice,
not a requirement: 30 files took most of a minute in sequence and about a sixth of that
in parallel. The pre-commit hook used to have its own hand-written list of eleven of
them, which could drift from `tests/` in silence. It now calls this instead.

    python3 tools/check_all.py                  # everything, this interpreter
    python3 tools/check_all.py --no-browser     # the suites that need no Playwright
    python3 tools/check_all.py --fast           # only what the pre-commit hook runs
    python3 tools/check_all.py -v               # also print each suite's own output
    python3 tools/check_all.py --list           # what would run

A suite is `tests/test_*.py`. A runner that derived a shorter list from anything else
could pass while proving nothing, so the resolved list is printed, an empty one exits 2,
and `--expect N` refuses a count that changed under you.

Exit status: 0 every suite passed, 1 at least one failed, 2 nothing was run.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import pathlib
import subprocess
import re
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
TOOLS = ROOT / "tools"

# The tree gates are not a `tests/test_*.py` file, and they are the ones that must never
# be skipped: they read every tracked file. Named here so the list cannot lose them.
EXTRA = ("tools/check_tree.py",)

# ROADMAP C1: the set the pre-commit hook runs on every commit. It used to be hand-written
# in `tools/hooks/pre-commit`, which could drift from this file in silence; it now lives
# here, next to the full list, so the two cannot disagree about what a suite is. Every
# entry must exist, or the hook refuses to run.
FAST = (
    "tools/check_tree.py",
    "tests/test_row_24_26_checks.py",
    "tests/test_no_real_data_gate.py",
    # The boundary gate scans the whole core tree once per check, so it was 23.7 s of a
    # 28 s hook. The count for a (category, text) pair is memoised on the subject text in
    # `check_core_is_generic.counts`, which takes the suite to 1.7 s. It stays on every
    # commit: scoping it to staged paths would have been the weaker answer (ROADMAP C1).
    "tests/test_core_boundary_gate.py",
    "tests/test_hooks_are_live.py",
    "tests/test_token_contract.py",
    "tests/test_findings_index.py",
    "tests/test_builder_provenance.py",
    "tests/test_cube_reproducible.py",
    "tests/test_no_old_names.py",
    "tests/test_skill_frontmatter.py",
    # Both read the whole tree and finish in about a second: a documented path, a
    # mutation anchor and a skill's tier line are exactly the inputs that drift while
    # a gate keeps printing a colour, so they belong on every commit.
    "tests/test_gate_inputs.py",
    "tests/test_skill_tier_line.py",
    # One word for one thing: reads every tracked file and finishes in under a second, which
    # is exactly the shape of drift a hook should catch before it reaches a commit.
    "tests/test_glossary.py",
    # The shared builder core is what five builders read a table and a number through, so a
    # change to it changes every artefact at once. It runs in about a second.
    "tests/test_shared_core.py",
    # The onboarding document is read by someone with no other context, on a Windows laptop
    # we do not have. Every claim in it that can be checked here is checked here.
    "tests/test_onboarding.py",
    # Docs are filed by reader, and a filing nobody checks becomes a pile again. Pure text,
    # no browser, 0.2 s.
    "tests/test_docs_readers.py",
)


class Absent(Exception):
    """A gate that the list names is not on disk. Never a reason to run a shorter list."""


def browser_need(path: pathlib.Path) -> bool:
    """True when this suite imports Playwright, so it cannot pass without a browser."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return "playwright" in source


def resolve(no_browser: bool, fast: bool = False) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    """The suites to run, and the ones held back."""
    if fast:
        picked = [ROOT / rel for rel in FAST]
        absent = [rel for rel, path in zip(FAST, picked) if not path.is_file()]
        if absent:
            raise Absent(f"always-on gate missing: {', '.join(absent)}")
        return picked, []
    named = [ROOT / rel for rel in EXTRA]
    absent = [rel for rel, path in zip(EXTRA, named) if not path.is_file()]
    if absent:
        # Dropping a missing entry would shrink the run in silence, which is the one
        # failure mode a gate about gates must not have.
        raise Absent(f"named gate missing: {', '.join(absent)}")
    found = sorted(TESTS.glob("test_*.py")) + named
    run, held = [], []
    for path in found:
        if not path.is_file():
            continue
        (held if no_browser and browser_need(path) else run).append(path)
    return run, held


def one(python: str, path: pathlib.Path) -> tuple[pathlib.Path, int, float, str]:
    started = time.monotonic()
    try:
        done = subprocess.run([python, str(path)], cwd=ROOT, capture_output=True,
                              text=True, timeout=1800)
        code, out = done.returncode, (done.stdout or "") + (done.stderr or "")
    except subprocess.TimeoutExpired:
        code, out = 124, "timed out after 1800 s"
    except OSError as exc:                        # interpreter gone between calls
        code, out = 127, str(exc)
    return path, code, time.monotonic() - started, out


def last_lines(text: str, count: int = 12) -> str:
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return "\n".join(lines[-count:])


#: Lines in a suite's output that name a failure rather than narrate a pass.
_FAIL_MARK = re.compile(r"(\u2717|\bFAIL\b|Traceback|Error|error:)")


def failing_excerpt(text: str, limit: int = 40) -> str:
    """What to show for a red suite: the lines that name a failure, then the tail.

    The tail alone was wrong often enough to matter. A suite that prints fifty passing
    checks and then a traceback ends its output with the traceback, but a suite whose last
    act is a summary line ends it with something that says nothing about the cause. The
    marked lines are the ones that name it.
    """
    lines = text.strip().splitlines()
    if len(lines) <= limit:
        return "\n".join(lines)
    marked = [ln for ln in lines if _FAIL_MARK.search(ln)][: limit // 2]
    tail = lines[-(limit - len(marked)):]
    return "\n".join(marked + (["  ..."] if marked else []) + tail)


def keep_log(name: str, text: str) -> pathlib.Path:
    """A red suite's whole output, on disk, so an intermittent failure leaves evidence.

    Suites are run in parallel with their output captured to a pipe. When one fails once in
    twenty runs, whatever this run printed is the only thing that survives, and the next run
    is green. That is how a real intermittent defect was observed, reported once, and left
    unnamed: the output was gone. The log goes under the system temp dir, so it is reachable
    after the run on every platform without a new dependency or a new directory in the repo.
    """
    folder = pathlib.Path(tempfile.gettempdir()) / "tun-check-all"
    folder.mkdir(parents=True, exist_ok=True)
    path = (folder / name.replace("/", "__")).with_suffix(".log")
    path.write_text(text, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-browser", action="store_true",
                    help="hold back the suites that need Playwright")
    ap.add_argument("--fast", action="store_true",
                    help="only the always-on set the pre-commit hook runs")
    ap.add_argument("--python", default=sys.executable,
                    help="interpreter for the suites (default: this one)")
    ap.add_argument("-j", "--jobs", type=int, default=0,
                    help="parallel suites (default: CPU count, at most 8)")
    ap.add_argument("-v", "--verbose", action="store_true", help="print every suite's output")
    ap.add_argument("--list", action="store_true", help="print the resolved suites and stop")
    ap.add_argument("--expect", type=int, default=0,
                    help="refuse to run unless this many suites resolve")
    args = ap.parse_args(argv)

    try:
        run, held = resolve(args.no_browser, fast=args.fast)
    except Absent as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not run:
        print("error: no suites resolved, so this run could not prove anything", file=sys.stderr)
        return 2
    if args.expect and len(run) != args.expect:
        print(f"error: {len(run)} suites resolved, --expect {args.expect}. "
              f"A suite appeared or vanished; look at what changed.", file=sys.stderr)
        return 2

    rel = [p.relative_to(ROOT).as_posix() for p in run]
    if args.list:
        print("\n".join(rel))
        if held:
            print(f"# held back ({len(held)} need Playwright): "
                  + ", ".join(p.relative_to(ROOT).as_posix() for p in held))
        return 0

    jobs = args.jobs or min(8, (len(run) + 1) // 2 or 1)
    started = time.monotonic()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futures = [pool.submit(one, args.python, p) for p in run]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    elapsed = time.monotonic() - started
    results.sort(key=lambda r: rel[run.index(r[0])])

    failures = 0
    for path, code, took, out in results:
        name = path.relative_to(ROOT).as_posix()
        verdict = "ok  " if code == 0 else "FAIL"
        failures += code != 0
        print(f"  {verdict} {name:<46} {took:5.1f} s")
        if code != 0:
            print("\n".join("       " + ln
                            for ln in failing_excerpt(out).splitlines()))
            print(f"       full output: {keep_log(name, out)}")
        elif args.verbose:
            print("\n".join("       " + ln for ln in last_lines(out, 3).splitlines()))

    print()
    print(f"check_all: {len(results) - failures} passed, {failures} failed, "
          f"{len(results)} suites in {elapsed:.1f} s "
          f"({jobs} at a time, {args.python.rsplit('/', 1)[-1]})")
    if held:
        print(f"check_all: {len(held)} suite(s) held back by --no-browser: "
              + ", ".join(p.relative_to(ROOT).as_posix() for p in held))
    print("check_all: PASS" if not failures else "check_all: FAIL")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
