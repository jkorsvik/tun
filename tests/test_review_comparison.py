#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_review_comparison.py — the layer on the artefact where a row, not a number, is disputed.

A comparison is the second artefact this layer covers, and it asks a question the register
did not: a key that has no figure on one side. `Nordvest` is in September and not in
October. Is a comment about it a comment about a row that vanished, or a complaint about a
wrong number?

It is a comment about the key, and the artefact already knows: the row is in the file, marked
`gone`, with an empty "after". So the block carries `status: gone` beside the key, and
`tools/read_review.py` reports the row as it finds it rather than calling it wrong.

Three defects had to be fixed for that to be true, and each has a check here that would fail
without the fix:

  * a key cell that carries a tag reads "Nordvest borte" as its text, so the comment was
    filed against a name the file does not hold (`data-key` now carries the identity);
  * the page writes a real minus sign and a leading plus, so every comparison figure arrived
    at the parser as text and every row read as a changed value;
  * the comparison's rows use short field names (`k, b, a, d`), which the block does not
    speak, so nothing resolved at all.

A missing Playwright is a FAIL, not a skip.

This suite writes its own two extracts with the example's generator, into its own temporary
directory. It used to read `examples/33-comparison/forrige.csv` and `denne.csv` in place,
which are **gitignored**: they exist only in a checkout where someone has run
`generate_data.py`. So the suite passed where that had happened and failed on a fresh
worktree or a clean CI clone, with a `FileNotFoundError` for the built file rather than a
sentence saying why. That is the whole of ROADMAP C6: `check_all` looked intermittent
because which tree it ran in decided the answer, not what the commit contained.

    zsh -lc 'uv run --extra verify python tests/test_review_comparison.py'
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT / "examples" / "33-comparison"))
import read_review  # noqa: E402
import generate_data  # noqa: E402  the example's own generator, so nothing untracked is read


def command(before: pathlib.Path, after: pathlib.Path, out: pathlib.Path,
            *extra: str) -> list[str]:
    return [sys.executable, str(TOOLS / "build_comparison.py"),
            "--before", str(before), "--after", str(after),
            "--key", "Region", "--value", "Omsetning",
            "--title", "Omsetning per region: september mot oktober",
            "--before-label", "September", "--after-label", "Oktober", "--meaning", "up",
            "--source", "Syntetisk eksempeldata (forrige.csv, denne.csv)",
            "--requested-by", "Innsikt", "--out", str(out), *extra]


def fixtures(directory: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """Write the two extracts here, so this suite reads nothing gitignored."""
    before, after = directory / "forrige.csv", directory / "denne.csv"
    generate_data.write(before, generate_data.BEFORE)
    generate_data.write(after, generate_data.AFTER)
    return before, after

PASS = FAIL = 0


def chk(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}" + (f" — {detail}" if detail else ""))


def comment(page, selector: str, said: str) -> None:
    page.locator(selector).first.click()
    page.fill("#annotate-text", said)
    page.click("#annotate-add")


def main() -> int:
    print("the builder")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = pathlib.Path(tmp)
        before, after = fixtures(tmpdir)
        plain = tmpdir / "plain.html"
        run_plain = subprocess.run(command(before, after, plain), capture_output=True,
                                   text=True, cwd=ROOT)
        chk("the plain build works", run_plain.returncode == 0,
            (run_plain.stderr or run_plain.stdout or "")[-300:])
        if not plain.is_file():
            # No artefact, no point in the rest: say so in one line rather than raising a
            # FileNotFoundError five frames down, which reads like a defect in the suite.
            print("-" * 62)
            print(f"PASS: {PASS}  FAIL: {FAIL}")
            return 1
        chk("the layer is off by default", "TUN-REVIEW 1" not in plain.read_text(encoding="utf-8"))

        annotated = tmpdir / "annotert.html"
        run = subprocess.run(command(before, after, annotated, "--annotate"),
                             capture_output=True, text=True, cwd=ROOT)
        chk("the annotated build works", run.returncode == 0, (run.stderr or "")[-300:])
        if not annotated.is_file():
            print("-" * 62)
            print(f"PASS: {PASS}  FAIL: {FAIL}")
            return 1
        page_text = annotated.read_text(encoding="utf-8")
        chk("the layer is in it", "TUN-REVIEW 1" in page_text)
        chk("the table can be found", 'id="tbl"' in page_text)
        chk("the columns are named for the layer", 'data-col="delta"' in page_text)
        chk("a row carries its own identity", 'data-key="Nordvest"' in page_text)

        print("the reader's half")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            chk("playwright is installed", False,
                "install: uv sync --extra verify && uv run playwright install chromium")
            return 1

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1366, "height": 900})
                page.goto(annotated.resolve().as_uri())
                page.wait_for_timeout(300)
                page.click("#annotate-toggle")
                chk("the artefact marks the row that vanished",
                    page.locator('tr[data-status="gone"]').count() == 1)
                comment(page, 'tr[data-status="gone"]', "Denne regionen forsvant fra oktober.")
                comment(page, 'tr[data-status="added"]', "Ny region i oktober. Er den reell?")
                block = page.input_value("#annotate-payload")
            finally:
                browser.close()

        chk("the block names the key, not the tag beside it", "row: Nordvest\n" in block,
            block[:200])
        chk("the tag word is not part of the key", "Nordvest borte" not in block)
        chk("a gone row says so", "status: gone" in block)
        chk("an added row says so", "status: added" in block)

        print("the file's half")
        block_file = tmpdir / "block.txt"
        block_file.write_text(block, encoding="utf-8")
        out = subprocess.run([sys.executable, str(TOOLS / "read_review.py"),
                              str(annotated), str(block_file)], capture_output=True, text=True)
        chk("the report is produced", out.returncode == 0, (out.stderr or "")[-300:])
        chk("both comments resolve", "not found" not in out.stdout, out.stdout[-400:])
        chk("a vanished row is marked, not called wrong", "same (gone)" in out.stdout,
            out.stdout[-400:])
        chk("a new row is marked", "(added)" in out.stdout)
        chk("no row is called missing", "rows the file no longer holds: **0**" in out.stdout)
        chk("no figure is called different", "differ from the file: **0**" in out.stdout)

        print("the checks can fail")
        # 1. take the identity away: the layer falls back to the cell text, which holds the
        #    tag, and the report stops finding the row. The attribute is set by the script
        #    that draws the rows, so the mutation is the config the layer reads, not the
        #    markup it would overwrite anyway.
        no_key = tmpdir / "utan-nokkel.html"
        no_key.write_text(page_text.replace('"keyAttr": "data-key"', '"keyAttr": ""'),
                          encoding="utf-8")
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1366, "height": 900})
                page.goto(no_key.resolve().as_uri())
                page.wait_for_timeout(300)
                page.click("#annotate-toggle")
                comment(page, 'tr[data-status="gone"]', "Denne regionen forsvant fra oktober.")
                bare = page.input_value("#annotate-payload")
            finally:
                browser.close()
        chk("without the row's own key, the tag leaks into it", "Nordvest borte" in bare,
            bare[:200])
        bare_file = tmpdir / "bare.txt"
        bare_file.write_text(bare, encoding="utf-8")
        miss = subprocess.run([sys.executable, str(TOOLS / "read_review.py"),
                               str(annotated), str(bare_file)], capture_output=True, text=True)
        chk("and the report can no longer find the row", "not found" in miss.stdout,
            miss.stdout[-300:])

        # 2. a figure that moved must still be reported as a moved figure.
        moved = tmpdir / "flyttet.txt"
        # A lambda, not a template: `\s` in a replacement string is a bad escape.
        changed = re.sub(r"value: \u221288\s000", lambda m: "value: \u221299\u00a0000", block)
        chk("the mutation applied (the value it edits is in the block)", changed != block,
            block[:200])
        moved.write_text(changed, encoding="utf-8")
        moved_out = subprocess.run([sys.executable, str(TOOLS / "read_review.py"),
                                    str(annotated), str(moved)], capture_output=True, text=True)
        chk("a figure that differs is still caught", "**block says" in moved_out.stdout,
            moved_out.stdout[-300:])
        chk("and it counts as one", "differ from the file: **1**" in moved_out.stdout)

        # 3. the status line is what makes an empty figure legible; without it the report
        #    has no word for why the number is absent.
        no_status = tmpdir / "utan-status.txt"
        no_status.write_text(re.sub(r"^status: gone\n", "", block, flags=re.M), encoding="utf-8")
        bare_out = subprocess.run([sys.executable, str(TOOLS / "read_review.py"),
                                   str(annotated), str(no_status)], capture_output=True, text=True)
        chk("without the status line the mark is gone", "(gone)" not in bare_out.stdout,
            bare_out.stdout[-300:])

    print("-" * 62)
    print(f"PASS: {PASS}  FAIL: {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
