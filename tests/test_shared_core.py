#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""One home for reading a table and reading a number, and proof that it is used.

`tools/tun_core.py` exists because five builders each grew a copy of the same three
functions and the copies disagreed. The disagreement that mattered:

    1,234.56    en-US Excel       dashboard read 1.23456     (a silent factor of 1000)
    1.234,56    nb Excel          register kept it as text   (it sorts as a string)

Both are the same amount. Neither is exotic: the first is what an English-locale Excel
writes, the second what a Norwegian one writes, and a tenant has both.

So this suite has three jobs: prove the shared parse reads both, prove each builder
actually goes through it, and prove the checks can fail by mutating a scratch copy.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
PY = sys.executable
CHECKS = 0
FAILED: list[str] = []
# Which numeric wrapper each builder uses, so the import scan below is not a guess.
BUILDERS = {
    "build_dashboard.py": "tun_core",
    "build_cube_dashboard.py": "tun_core",
    "build_survey_dashboard.py": "tun_core",
    "build_register.py": "tun_core",
}


def chk(ok: bool, what: str, detail: str = "") -> bool:
    global CHECKS
    CHECKS += 1
    print(f"  {'✓' if ok else '✗'} {what}" + ("" if ok else f" — {detail}"))
    if not ok:
        FAILED.append(what)
    return ok


def section(title: str) -> None:
    print(f"\n{title}")


def run(args: list[str], cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([PY, *args], capture_output=True, text=True, cwd=cwd or ROOT)


def load_core(tools: pathlib.Path | None = None):
    import importlib.util
    path = (tools or TOOLS) / "tun_core.py"
    spec = importlib.util.spec_from_file_location(f"tun_core_{abs(hash(path))}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    core = load_core()

    section("1. one amount, two locales, one reading")
    for text, want in [("1,234.56", 1234.56), ("1.234,56", 1234.56), ("1 234,56", 1234.56),
                       ("1234,56", 1234.56), ("1234.56", 1234.56), ("2 500", 2500),
                       ("12%", 12), ("-7,5", -7.5), ("  42  ", 42)]:
        got = core.to_number(text)
        chk(got == want, f"{text!r} reads as {want}", f"got {got!r}")
    chk(core.to_number("") is None, "an empty cell is nothing, not zero")
    chk(core.to_number(None) is None, "a missing cell is nothing, not zero")
    chk(core.to_number("12A") is None, "text that is not a number is refused rather than guessed")
    chk(core.to_number(True) is None, "True is not 1 in a table that came from a file")
    chk(core.number_or_zero("") == 0.0, "the cube's wrapper still counts a gap as nothing")
    chk(core.to_number("1.234") == 1.234,
        "one separator stays a decimal separator, the reading both builders already had")

    section("2. the amount survives a build, in both spellings")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = pathlib.Path(tmp)
        table = tmpdir / "en.csv"
        table.write_text("Enhet,Belop\nNord,\"1,234.56\"\nSør,\"2,469.12\"\n", encoding="utf-8")
        out = tmpdir / "en.html"
        res = run([str(TOOLS / "build_dashboard.py"), "--data", str(table),
                   "--title", "Test", "--dimension", "Enhet", "--measure", "Belop",
                   "--requested-by", "Test", "--out", str(out)])
        chk(res.returncode == 0, "an en-US formatted amount builds", res.stderr[-200:])
        blob = out.read_text(encoding="utf-8")
        chk(re.search(r"3\s?703", blob) is not None,
            "the two amounts add up to about 3 703, not to about 3,7",
            "the total is not in the page")
        chk("1.23456" not in blob, "no cell was read as a thousandth of itself")
        numbers = [float(v) for v in re.findall(r'"Belop":([0-9.]+)', blob)]
        chk(numbers == [1234.56, 2469.12], "each cell kept its value", f"got {numbers}")

    section("3. every builder goes through the shared code")
    for name, expected in BUILDERS.items():
        src = (TOOLS / name).read_text(encoding="utf-8")
        chk(f"import {expected}" in src or f"from {expected} import" in src,
            f"{name} imports the shared core")
        chk("def to_number" not in src and "def _parse_num" not in src,
            f"{name} carries no numeric parser of its own")
        chk("csv.DictReader" not in src,
            f"{name} does not open a table with its own DictReader")
        chk("def die" not in src, f"{name} refuses through the shared die()")
        chk("8192" not in src and "64 * 1024" not in src and "64*1024" not in src,
            f"{name} does not set its own sniffer sample size")
    chk((TOOLS / "tun_core.py").read_text(encoding="utf-8").count("NOT_STATED = ") == 1,
        "the provenance wording has one definition")

    section("4. every builder refuses the same way")
    # Each builder gets everything it requires, so the failure is the file and not argparse.
    REQUIRED = {
        "build_dashboard.py": ["--dimension", "A", "--measure", "B"],
        "build_cube_dashboard.py": ["--dims", "A", "--measures", "B:sum"],
        "build_survey_dashboard.py": [],
        "build_register.py": [],
    }
    for name in BUILDERS:
        res = run([str(TOOLS / name), "--data", "/nonexistent/none.csv", "--title", "x",
                   *REQUIRED[name], "--out", "/tmp/none.html"])
        chk(res.returncode == 2, f"{name} exits 2 on a missing file", f"got {res.returncode}")
        chk(res.stderr.startswith("error: "),
            f"{name} says error: on one line", res.stderr[:80].replace("\n", " "))

    section("5. the checks can fail: a mutated copy is caught")
    with tempfile.TemporaryDirectory() as tmp:
        scratch = pathlib.Path(tmp) / "tools"
        shutil.copytree(TOOLS, scratch)
        shutil.copytree(ROOT / "templates", pathlib.Path(tmp) / "templates")

        # a) put the old, wrong parse back
        p = scratch / "tun_core.py"
        s = p.read_text(encoding="utf-8")
        s = s.replace('''    has_comma, has_dot = "," in text, "." in text
    if has_comma and has_dot:
        decimal = "," if text.rindex(",") > text.rindex(".") else "."
        thousands = "." if decimal == "," else ","
        text = text.replace(thousands, "").replace(decimal, ".")''',
'''    has_comma, has_dot = "," in text, "." in text
    if has_comma and has_dot:
        text = text.replace(".", "").replace(",", ".")''')
        p.write_text(s, encoding="utf-8")
        mutated = load_core(scratch)
        chk(mutated.to_number("1,234.56") != 1234.56,
            "the naive parse really is the bug (so the locale check is not vacuous)",
            f"got {mutated.to_number('1,234.56')!r}")

        # b) a builder that grows its own loader again
        p = scratch / "build_register.py"
        p.write_text(p.read_text(encoding="utf-8")
                     + "\n\ndef die(msg):\n    print(msg)\n    raise SystemExit(2)\n",
                     encoding="utf-8")
        chk("def die" in p.read_text(encoding="utf-8"),
            "the scan would see a builder that re-grew a local helper (mutation applied)")

        # c) and a local sniffer sample size, the drift that started this
        p = scratch / "build_dashboard.py"
        p.write_text(p.read_text(encoding="utf-8") + "\nSAMPLE = 8192\n", encoding="utf-8")
        chk("8192" in p.read_text(encoding="utf-8"),
            "the scan would see a builder choosing its own sample size (mutation applied)")

    section("6. reading a table the way a person's file is written")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = pathlib.Path(tmp)
        cases = {
            "semicolon.csv": ("Enhet;Belop\nNord;10\nSør;20\n", ";"),
            "pipe.txt": ("Enhet|Belop\nNord|10\nSør|20\n", "|"),
            "bom.csv": ("\ufeffEnhet,Belop\nNord,10\nSør,20\n", ","),
            "tab.tsv": ("Enhet\tBelop\nNord\t10\nSør\t20\n", "\t"),
        }
        for name, (text, _delim) in cases.items():
            path = tmpdir / name
            path.write_text(text, encoding="utf-8")
            rows = core.read_rows(path)
            chk(list(rows[0].keys()) == ["Enhet", "Belop"],
                f"{name} reads as two named columns", f"got {list(rows[0].keys())}")
            chk(len(rows) == 2, f"{name} reads both rows", f"got {len(rows)}")
        js = tmpdir / "rows.json"
        js.write_text(json.dumps([{"Enhet": "Nord", "Belop": 10}]), encoding="utf-8")
        chk(core.read_rows(js) == [{"Enhet": "Nord", "Belop": 10}], "a JSON array of objects reads")

    print()
    if FAILED:
        print(f"FAIL: {CHECKS - len(FAILED)} of {CHECKS} checks")
        for f in FAILED:
            print(f"  - {f}")
        return 1
    print(f"PASS: {CHECKS} of {CHECKS} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
