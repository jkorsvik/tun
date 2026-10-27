#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""test_source_date_epoch.py — a pinned build is byte-identical, and a normal build is not pinned.

Every artefact stamps when it was built and when its data was extracted. Those stamps come
from the clock and from the data file's mtime, which means one data set gives different bytes
on every rebuild: every rebuild of a committed example is a diff, and a real change is
indistinguishable from a clock tick.

`SOURCE_DATE_EPOCH` fixes that, in every builder. This test proves four things per builder:
the epoch is honoured, twice with the same epoch is byte-identical, a different epoch gives
different bytes, and no epoch still stamps today rather than freezing. Then it proves the
same epoch gives the same bytes in two timezones, and it mutates one builder back to the
clock to prove the test would notice.

Stdlib only, runs the real builders as subprocesses into temp dirs.

    python3 tests/test_source_date_epoch.py
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_stamp  # noqa: E402

EPOCH_A = 1700000000   # 2023-11-14 22:13 UTC
EPOCH_B = 1600000000   # 2020-09-13 12:26 UTC


def stamp(epoch: int, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """The expected stamp, derived here rather than from the module under test."""
    return dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc).strftime(fmt)


RECIPES = {
    "dashboard": (
        ["tools/build_dashboard.py",
         "--data", "examples/01-hello-dashboard/salgsdata.csv",
         "--title", "T", "--dimension", "Produkt", "--measure", "Belop",
         "--time", "Maaned", "--filters", "Region", "--source", "S",
         "--requested-by", "R"],
        "%Y-%m-%d %H:%M",            # its stamps read "2023-11-14 22:13 UTC"
    ),
    "cube": (
        ["tools/build_cube_dashboard.py",
         "--data", "examples/01-hello-dashboard/salgsdata.csv",
         "--dims", "Produkt,Region", "--measures", "Belop:sum", "--title", "T",
         "--source", "S", "--requested-by", "R"],
        "%Y-%m-%d %H:%M",
    ),
    "survey": (
        ["tools/build_survey_dashboard.py",
         "--data", "examples/27-survey-board/survey.csv", "--title", "S"],
        "%Y-%m-%d %H:%M",
    ),
    "process": (
        ["tools/build_process_diagram.py", "examples/23-process-diagram/fem-roller.process.txt"],
        "%Y-%m-%d %H:%M",
    ),
}

passed = failed = 0


def chk(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS {label}")
    else:
        failed += 1
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def build(name: str, out: pathlib.Path, cwd: pathlib.Path = ROOT,
          epoch: int | None = None, tz: str | None = None) -> bytes:
    cmd, _ = RECIPES[name]
    env = dict(os.environ)
    env.pop("SOURCE_DATE_EPOCH", None)
    if epoch is not None:
        env["SOURCE_DATE_EPOCH"] = str(epoch)
    if tz is not None:
        env["TZ"] = tz
    full = [sys.executable] + [str(cwd / cmd[0])] + cmd[1:] + ["--out", str(out)]
    r = subprocess.run(full, cwd=cwd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{name}: builder failed: {(r.stderr or r.stdout).strip()[:300]}")
    return out.read_bytes()


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="tun-sde-"))
    try:
        # --- the module itself -------------------------------------------------------
        os.environ.pop(build_stamp.VAR, None)
        chk("no epoch: epoch() is None", build_stamp.epoch() is None)
        os.environ[build_stamp.VAR] = str(EPOCH_A)
        chk("epoch is read as an int", build_stamp.epoch() == EPOCH_A)
        os.environ[build_stamp.VAR] = f"  {EPOCH_A}  "
        chk("surrounding whitespace is tolerated", build_stamp.epoch() == EPOCH_A)
        chk("pinned local() is the UTC instant",
            build_stamp.local("%Y-%m-%d %H:%M") == stamp(EPOCH_A))
        chk("pinned naive() is the UTC instant",
            build_stamp.naive() == stamp(EPOCH_A))

        mtime_file = tmp / "m.csv"
        mtime_file.write_text("a,b\n1,2\n", encoding="utf-8")
        os.utime(mtime_file, (EPOCH_B + 3600, EPOCH_B + 3600))
        chk("pinned from_mtime() ignores the file's mtime",
            build_stamp.from_mtime(mtime_file, "%Y-%m-%d %H:%M") == stamp(EPOCH_A))
        os.environ.pop(build_stamp.VAR, None)
        # Unpinned it is the mtime in local time, which is what the builders printed before.
        local_mtime = dt.datetime.fromtimestamp(EPOCH_B + 3600).strftime("%Y-%m-%d %H:%M")
        chk("unpinned from_mtime() reads the file's mtime, as before",
            build_stamp.from_mtime(mtime_file, "%Y-%m-%d %H:%M") == local_mtime)

        for bad in ("abc", "12.5", "2026-10-24", "-1"):
            os.environ[build_stamp.VAR] = bad
            try:
                build_stamp.epoch()
            except SystemExit as e:
                msg = str(e.code)
                chk(f"rejects {bad!r} with a message naming the variable",
                    e.code != 0 and build_stamp.VAR in msg)
            else:
                chk(f"rejects {bad!r}", False, "accepted it")
        os.environ.pop(build_stamp.VAR, None)

        # --- every builder honours it ------------------------------------------------
        today = dt.datetime.now().strftime("%Y-%m-%d")
        for name in RECIPES:
            a1 = build(name, tmp / f"{name}-a1.html", epoch=EPOCH_A)
            a2 = build(name, tmp / f"{name}-a2.html", epoch=EPOCH_A)
            b1 = build(name, tmp / f"{name}-b1.html", epoch=EPOCH_B)
            free = build(name, tmp / f"{name}-free.html")
            chk(f"{name}: the same epoch twice is byte-identical", a1 == a2,
                f"{len(a1)} vs {len(a2)} bytes")
            chk(f"{name}: the pinned stamp is in the file",
                stamp(EPOCH_A).encode() in a1)
            chk(f"{name}: a different epoch gives different bytes", a1 != b1)
            chk(f"{name}: the second stamp is in the second file and not the first",
                stamp(EPOCH_B).encode() in b1 and stamp(EPOCH_B).encode() not in a1)
            chk(f"{name}: with no epoch it still stamps today, not a frozen date",
                today.encode() in free and stamp(EPOCH_A).encode() not in free)

        # --- the point of the convention: the timezone does not matter ---------------
        oslo = build("dashboard", tmp / "tz-oslo.html", epoch=EPOCH_A, tz="Europe/Oslo")
        akl = build("dashboard", tmp / "tz-akl.html", epoch=EPOCH_A, tz="Pacific/Auckland")
        chk("dashboard: two timezones, one pinned epoch, identical bytes", oslo == akl)

        # --- mutation control: put the clock back and require the checks above to notice
        mut = tmp / "mutant"
        shutil.copytree(ROOT / "tools", mut / "tools")
        shutil.copytree(ROOT / "templates", mut / "templates")
        shutil.copytree(ROOT / "examples" / "01-hello-dashboard",
                        mut / "examples" / "01-hello-dashboard")
        target = mut / "tools" / "build_dashboard.py"
        src = target.read_text(encoding="utf-8")
        old = "    now = build_stamp.local()"
        if src.count(old) != 1:
            chk("mutation applies exactly once", False, f"found {src.count(old)} sites")
        else:
            target.write_text(src.replace(
                old, '    now = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")'),
                encoding="utf-8")
            # The mutant still runs: it ignores the epoch rather than crashing.
            survive = build("dashboard", tmp / "mut1.html", cwd=mut, epoch=EPOCH_A)
            # A healthy dashboard stamps the pinned instant twice: built, and extracted.
            healthy = (tmp / "dashboard-a1.html").read_bytes().count(stamp(EPOCH_A).encode())
            mutant = survive.count(stamp(EPOCH_A).encode())
            chk("mutant: the builder still runs with the clock restored", len(survive) > 1000)
            chk("mutant: one of the two pinned stamps is gone, so 'the pinned stamp is in "
                "the file' would fail", mutant < healthy, f"{mutant} of {healthy} stamps")
            chk("mutant: the clock is stamped instead, so 'still stamps today' would fail",
                today.encode() in survive and stamp(EPOCH_A).encode() in survive)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("─" * 66)
    print(f"{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
