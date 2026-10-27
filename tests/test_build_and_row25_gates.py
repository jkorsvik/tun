#!/usr/bin/env python3
"""Mutation tests for the two gates added alongside them — prove they can fail.

Both gates here exist because a check that *looked* present was not actually
running. A test that only asserts "a clean artefact passes" cannot tell a firing
gate from a deleted one, so each case below breaks exactly one thing and asserts
the gate notices — and notices *alone*, so a neighbouring failure cannot cover
for a gate that has quietly stopped working.

  1. the builders reject any surviving {{TOKEN}}, not just their own keys
     (tools/build_dashboard.py, tools/build_cube_dashboard.py)
  2. the publish gate rejects a literal "<script" written as prose
     (tools/verify_dashboard.py, docs/01-tenant-constraints.md row 25)

Stdlib only, no network: every case mutates a copy of the real template in a
temp dir and runs the real scripts as subprocesses.

The publish gates also open the file in a browser. Without Playwright they say
"BLOCKED — playwright not installed" and fail, as they must. This test then
reports the browser half as SKIP with the command to run, and still asserts every
static check: a missing optional dependency is not a failure here, but it never
hides one either.

    python3 tests/test_build_and_row25_gates.py
    uv run --extra verify python tests/test_build_and_row25_gates.py   # with the browser half
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
TEMPLATE = ROOT / "templates" / "single-file-dashboard.html"
CSV = ROOT / "examples" / "01-hello-dashboard" / "salgsdata.csv"

PASS = FAIL = SKIP = 0

# The line both verify tools print when they cannot open a browser.
BLOCKED = "BLOCKED — playwright not installed"
WITH_BROWSER = "uv run --extra verify python tests/test_build_and_row25_gates.py"


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def skip(label: str) -> None:
    global SKIP
    SKIP += 1
    print(f"  SKIP {label} — playwright not installed. Run: {WITH_BROWSER}")


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True,
                          cwd=ROOT, timeout=120)


def build(template: pathlib.Path, out: pathlib.Path) -> subprocess.CompletedProcess:
    """Build a dashboard from an arbitrary template copy, via a patched tool copy."""
    tool = out.parent / "build_dashboard.py"
    src = (TOOLS / "build_dashboard.py").read_text(encoding="utf-8")
    # Point the copy at our mutated template and at the real tools/ for its import.
    # Assert each rewrite landed: if the real file is refactored so a target string no
    # longer matches, this test would otherwise keep passing against a stale or
    # unredirected copy — a green suite that has stopped testing anything.
    rewrites = [
        ('TEMPLATE = pathlib.Path(__file__).resolve().parents[1] / "templates" / "single-file-dashboard.html"',
         f'TEMPLATE = pathlib.Path({str(template)!r})'),
        ('sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))',
         f'sys.path.insert(0, {str(TOOLS)!r})'),
    ]
    for old, new in rewrites:
        if src.count(old) != 1:
            raise AssertionError(
                f"tools/build_dashboard.py no longer contains exactly one:\n  {old}\n"
                "This test redirects that line; update the test with the tool.")
        src = src.replace(old, new)
    tool.write_text(src, encoding="utf-8")
    return run([str(tool), "--data", str(CSV), "--title", "t",
                "--dimension", "Produkt", "--measure", "Belop", "--time", "Maaned",
                "--out", str(out)])


def failure_lines(stdout: str) -> list[str]:
    """The gate's own ✗ bullets, excluding its closing summary line."""
    return [ln.strip() for ln in stdout.splitlines()
            if "✗" in ln and "blocking issue" not in ln]


def verdict(returncode: int, stdout: str) -> tuple[str, list[str]]:
    """("pass" | "blocked" | "fail", the ✗ bullets other than the missing browser).

    "blocked" means the ONLY failure was the missing browser, so every static check
    passed. Anything else that fired, or a non-zero exit with no bullet at all (a
    crash), is "fail".
    """
    bullets = failure_lines(stdout)
    real = [b for b in bullets if BLOCKED not in b]
    if returncode == 0:
        return "pass", real
    if not real and len(bullets) > len(real):
        return "blocked", real
    return "fail", real


def main() -> int:
    print("mutation tests: build placeholder scan + row-25 stray-script gate")
    print("─" * 62)

    if not CSV.exists():
        print(f"FAIL: fixture data missing: {CSV}")
        return 1

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        original = TEMPLATE.read_text(encoding="utf-8")

        # ── baseline ───────────────────────────────────────────────────────
        # Without this, every case below could "pass" because the pipeline is
        # broken for an unrelated reason.
        clean = tmp / "clean.html"
        clean_tpl = tmp / "clean-template.html"
        clean_tpl.write_text(original, encoding="utf-8")
        r = build(clean_tpl, clean)
        check("baseline: unmutated template builds", r.returncode == 0, r.stderr.strip()[:120])

        r = run([str(TOOLS / "verify_standalone_core.py"), str(clean)])
        v, real = verdict(r.returncode, r.stdout)
        if v == "blocked":
            check("baseline: unmutated artefact passes the static generic checks", True)
            skip("baseline: browser half of the generic checks")
        else:
            check("baseline: unmutated artefact passes the generic checks",
                  v == "pass", r.stdout.strip()[-160:])

        # ── M1: a token the builder does not know about ────────────────────
        # The old check iterated its own substitution keys, so this was invisible
        # to the builder and only surfaced later, in the publish gate.
        m1_tpl = tmp / "m1-template.html"
        m1_tpl.write_text(original.replace("<title>", "<title>{{UNKNOWN_TOKEN}}", 1),
                          encoding="utf-8")
        r = build(m1_tpl, tmp / "m1.html")
        check("M1: builder rejects a {{TOKEN}} outside its own key list",
              r.returncode != 0 and "UNKNOWN_TOKEN" in (r.stdout + r.stderr),
              f"exit={r.returncode}")

        # ── M2: the row-25 literal, reintroduced as prose ───────────────────
        marker = "A script element with a src attribute works"
        if marker not in original:
            check("M2: fixture marker present in template", False,
                  f"{marker!r} not found — update this test with the template")
        else:
            m2_tpl = tmp / "m2-template.html"
            m2_tpl.write_text(original.replace(marker, "A <script src> works", 1),
                              encoding="utf-8")
            m2_out = tmp / "m2.html"
            r = build(m2_tpl, m2_out)
            check("M2: the trap does not stop the build (only the gate catches it)",
                  r.returncode == 0, f"exit={r.returncode}")

            r = run([str(TOOLS / "verify_dashboard.py"), str(m2_out)])
            v, bullets = verdict(r.returncode, r.stdout)
            # Without a browser the gate fails anyway, so "it failed" proves nothing;
            # it must fail on something other than the missing browser.
            check("M2: publish gate rejects it", v == "fail", f"exit={r.returncode}, {v}")
            check("M2: it is the stray-script check that fired",
                  any("no-stray-script" in b for b in bullets), str(bullets)[:160])
            # Fires alone: otherwise a future regression in this check would stay
            # hidden behind whichever neighbouring check happens to fail too.
            check("M2: and it fired alone", len(bullets) == 1, f"{len(bullets)} failures: {bullets}")
            if BLOCKED in r.stdout:
                skip("M2: alone among the browser checks too")

        # ── M3: the gate must not fire on a clean file ─────────────────────
        r = run([str(TOOLS / "verify_dashboard.py"), str(clean)])
        check("M3: no false positive on the unmutated artefact",
              r.returncode == 0 or not any("no-stray-script" in b for b in failure_lines(r.stdout)),
              r.stdout.strip()[-200:])

        # ── M3b: the SKIP path cannot swallow a real failure ───────────────
        # verdict() is what turns a missing browser into SKIP. Pin it on gate output
        # shaped like the real thing, so a looser version cannot hide a failure.
        blocked = f"  ✗ render             {BLOCKED}, browser checks could not run"
        stray = '  ✗ no-stray-script    found "<script" 3 time(s)'
        check("M3b: only the missing browser -> blocked (SKIP)",
              verdict(1, blocked)[0] == "blocked")
        check("M3b: missing browser plus a real failure -> fail",
              verdict(1, blocked + "\n" + stray) == ("fail", [stray.strip()]))
        check("M3b: non-zero exit with no bullet at all (a crash) -> fail",
              verdict(1, "Traceback (most recent call last):")[0] == "fail")
        check("M3b: exit 0 -> pass", verdict(0, "")[0] == "pass")

        # ── M4: the check is wired into the gate at all ────────────────────
        # Cheap structural guard: the import can be dropped in a refactor and
        # every case above would still pass if the checks happened to be clean.
        gate = (TOOLS / "verify_dashboard.py").read_text(encoding="utf-8")
        check("M4: verify_dashboard.py imports check_no_stray_script_text",
              "check_no_stray_script_text" in gate)
        check("M4: and calls it",
              len(re.findall(r"check_no_stray_script_text\s*\(", gate)) >= 1)

        # ── M5: the template is unchanged by this test run ─────────────────
        check("M5: real template untouched",
              TEMPLATE.read_text(encoding="utf-8") == original)

        # ── M6: one substitution convention in the cube template ───────────
        # The generic scan can only see {{TOKEN}}. templates/cube-dashboard.html used
        # to mix that with __TOKEN__ for its title/meta/data — lexically identical to
        # the runtime globals the page really does define (window.__READY__ and
        # friends, cube-dashboard.html:262-278), so no scan can tell a stale
        # placeholder from working code. Extending the regex to cover __TOKEN__ would
        # therefore fail every correct build. The fix is the convention, not the
        # regex: these two assertions stop both halves from regressing.
        cube_tpl = (ROOT / "templates" / "cube-dashboard.html").read_text(encoding="utf-8")
        cube_build = (TOOLS / "build_cube_dashboard.py").read_text(encoding="utf-8")
        substituted = set(re.findall(r'\.replace\("(\{\{[A-Z0-9_]+\}\})"', cube_build))
        unknown = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", cube_tpl)) - substituted)
        check("M6: every {{TOKEN}} in the cube template is substituted by its builder",
              not unknown, f"unsubstituted: {unknown}")
        check("M6: and the cube builder no longer relies on the unscannable __TOKEN__ form",
              '.replace("__' not in cube_build)

    print("─" * 62)
    tail = f"  SKIP: {SKIP} (browser half; run: {WITH_BROWSER})" if SKIP else ""
    print(f"PASS: {PASS}  FAIL: {FAIL}{tail}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
