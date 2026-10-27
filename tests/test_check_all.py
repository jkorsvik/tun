#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""`tools/check_all.py` runs every gate in parallel and still tells the truth.

ROADMAP C1 and C3. A runner is a gate about gates, so the ways it can lie are the ways
it gets tested here:

  1. it resolves every suite that exists — nothing drops out of the list in silence;
  2. an empty list exits 2 instead of reporting a green run of nothing;
  3. `--expect` refuses a count that changed;
  4. a failing suite makes the verdict FAIL and the exit status 1, and its own output
     is printed, because a bare "FAIL" teaches nobody anything;
  5. a passing set exits 0 and says PASS;
  6. it really runs them at the same time: four suites that each sleep a second finish
     in well under four;
  7. `--no-browser` holds back exactly the suites that import Playwright, and says how
     many it held back rather than quietly shrinking the run.

    python3 tests/test_check_all.py
"""
from __future__ import annotations

import contextlib
import io
import pathlib
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_all  # noqa: E402

checks = failed = 0
PY = sys.executable


def check(ok: bool, what: str, detail: str = "") -> None:
    global checks, failed
    checks += 1
    if ok:
        print(f"  ok   {what}")
        return
    failed += 1
    print(f"  FAIL {what}" + (f"\n       {detail}" if detail else ""))


def run(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            code = check_all.main(argv)
        except SystemExit as exc:                 # argparse only
            code = exc.code if isinstance(exc.code, int) else 2
    return code, buf.getvalue()


def use(files: dict[str, str], extra: tuple[str, ...] = ("tools/check_tree.py",)) -> tuple:
    """Point the runner at a throwaway tree, and return what to put back."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="checkall-"))
    (tmp / "tools").mkdir()
    (tmp / "tests").mkdir()
    for name, body in files.items():
        (tmp / "tests" / name).write_text(body, encoding="utf-8")
    (tmp / "tools" / "check_tree.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    previous = (check_all.ROOT, check_all.TESTS, check_all.EXTRA)
    check_all.ROOT, check_all.TESTS, check_all.EXTRA = tmp, tmp / "tests", extra
    return previous


def restore(previous: tuple) -> None:
    check_all.ROOT, check_all.TESTS, check_all.EXTRA = previous


PASS = "print('all good'); raise SystemExit(0)\n"
FAIL = "print('boom: the thing was wrong'); raise SystemExit(1)\n"
SLEEP = "import time; time.sleep(1.0); print('slept')\n"

def main() -> int:
    # 1. Every suite that exists is resolved. This is the check that stops a renamed
    #    file from leaving the run quietly smaller than the directory.
    real, held = check_all.resolve(no_browser=False)
    on_disk = sorted(p for p in (ROOT / "tests").glob("test_*.py"))
    names = {p.resolve() for p in real}
    missing = [p.name for p in on_disk if p.resolve() not in names]
    check(not missing, f"all {len(on_disk)} suite(s) in tests/ resolve", str(missing))
    check((ROOT / "tools" / "check_tree.py").resolve() in names,
          "the tree gates are in the run, they are not a tests/ file")
    check(len(real) >= 25, "the resolved list is not a skeleton", f"{len(real)} suites")

    # 2. An empty list is not a pass.
    previous = use({}, extra=())
    code, out = run(["--python", PY])
    check(code == 2, "nothing resolved exits 2, not 0", out.strip()[-120:])
    restore(previous)

    # 3. Two suites, one of them broken.
    use({"test_good.py": PASS, "test_bad.py": FAIL})
    code, out = run(["--python", PY])
    check(code == 1, "one failing suite exits 1", out.strip().splitlines()[-1] if out else "")
    check("PASS" not in out.splitlines()[-1], "the verdict is not PASS when a suite failed")
    check("boom: the thing was wrong" in out, "the failing suite's own output is printed")
    check("test_bad.py" in out, "the failing suite is named")

    # 4. A count that changed is refused. A passing tree this time: the verdict below is
    #    about the count, and a failing fixture would report FAIL for the wrong reason.
    use({"test_one.py": PASS, "test_two.py": PASS})
    code, out = run(["--python", PY, "--expect", "9"])
    check(code == 2, "--expect refuses a different count", out.strip()[-120:])
    # two fixture suites plus tools/check_tree.py
    code, out = run(["--python", PY, "--expect", "3"])
    check(code == 0, "--expect accepts the count it was given", out.strip()[-120:])
    check("check_all: PASS" in out, "a green run says PASS")

    # 5. Parallel, measured, not assumed.
    use({f"test_slow{i}.py": SLEEP for i in range(4)})
    started = time.monotonic()
    code, out = run(["--python", PY, "-j", "4"])
    took = time.monotonic() - started
    check(code == 0, "four sleeping suites pass", out.strip()[-120:])
    check(took < 3.0, "they ran at the same time, not one after another",
          f"{took:.1f} s for 4 x 1.0 s")

    # 6. --list prints one per line, and names what it held back.
    restore(previous)
    use({"test_good.py": PASS, "test_browser.py": "import playwright\n" + PASS})
    code, out = run(["--list", "--no-browser"])
    check(code == 0, "--list exits 0")
    check("tests/test_good.py" in out, "--list names the browser-free suite")
    check("test_browser.py" in out and "held back" in out,
          "--list says which suites it held back, and why")
    check("tools/check_tree.py" in out, "--list includes the tree gates")

    # 7. --no-browser really holds back the Playwright suites, in the real tree.
    restore(previous)
    real_all, _ = check_all.resolve(no_browser=False)
    real_nb, held_nb = check_all.resolve(no_browser=True)
    playwright = [p for p in real_all if check_all.browser_need(p)]
    check(len(held_nb) == len(playwright) and held_nb,
          "every suite that imports Playwright is the one held back",
          f"held {len(held_nb)}, import it {len(playwright)}")
    check(len(real_nb) + len(held_nb) == len(real_all),
          "held back plus run equals the whole list",
          f"{len(real_nb)} + {len(held_nb)} != {len(real_all)}")

    # 8. The pre-commit set (ROADMAP C1) is named in one place, is a subset of the full
    #    list, and has no hole in it: a missing entry must stop the hook, not shrink it.
    fast, _ = check_all.resolve(no_browser=True, fast=True)
    fast_names = {p.relative_to(ROOT).as_posix() for p in fast}
    check(fast_names == set(check_all.FAST), "the hook runs exactly the named always-on set",
          f"{sorted(fast_names)}")
    check(fast_names <= {p.relative_to(ROOT).as_posix() for p in real_all},
          "every always-on gate is also in the full list, so the two cannot disagree")
    code, out = run(["--fast", "--list"])
    listed = [ln for ln in out.strip().splitlines() if ln.strip()]
    check(code == 0 and len(listed) == len(check_all.FAST),
          f"--fast lists all {len(check_all.FAST)} gates", out.strip()[-160:])
    previous = use({}, extra=())
    check_all.EXTRA = ()
    saved = check_all.FAST
    check_all.FAST = ("tests/test_not_here.py",)
    code, out = run(["--fast", "--list"])
    check(code == 2 and "missing" in out, "a hole in the always-on set stops the run",
          out.strip()[-140:])
    check_all.FAST = saved
    restore(previous)

    # 9. A red suite leaves evidence. A suite that fails once in twenty runs printed its one
    #    useful line in the middle of forty others, the run reported the tail, the next run was
    #    green, and the defect was never named. The output is kept on disk and its path printed.
    restore(previous)
    NOISY = (
        "import sys\n"
        "for i in range(40): print('  ok   check', i)\n"
        "print('  FAIL the real cause is here')\n"
        "print('Traceback (most recent call last):')\n"
        "for i in range(40): print('  note', i)\n"
        "sys.exit(1)\n"
    )
    use({"test_noisy.py": NOISY})
    code, out = run(["--python", PY])
    check(code == 1, "the noisy fixture fails", out.strip()[-120:])
    check("full output:" in out, "a red suite prints where its full output went")
    kept = [ln.split("full output:", 1)[1].strip() for ln in out.splitlines()
            if "full output:" in ln]
    check(len(kept) == 1 and pathlib.Path(kept[0]).exists(),
          "and that path exists", str(kept))
    if kept and pathlib.Path(kept[0]).exists():
        body = pathlib.Path(kept[0]).read_text(encoding="utf-8")
        check("the real cause is here" in body,
              "the log holds the whole output, not the printed excerpt")
        check("the real cause is here" in out,
              "and the excerpt surfaces the marked line, not just the tail")
        check(all(f"note {i}" in body for i in range(40)),
              "nothing was truncated on the way to disk")
    # control: the excerpt is what shows a marked line that the tail would miss
    middle = "\n".join(["  ok   check"] * 30 + ["  FAIL the middle one"] + ["  note"] * 30)
    check("the middle one" in check_all.failing_excerpt(middle),
          "the excerpt keeps a failure that is 30 lines from the end")
    check("the middle one" not in check_all.last_lines(middle),
          "while the old tail-only excerpt would have lost it, which is the defect")
    restore(previous)

    print()
    print(f"{checks - failed}/{checks} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
