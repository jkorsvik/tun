#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
test_review_roundtrip.py — the artefact that comes back.

The round trip has three moving parts, and each can be broken without the others
noticing, so all three are checked here:

  1. the layer the builder appends (tools/review_layer.py, templates/_annotate.html):
     a reader can comment on a row, and the block they copy carries the build identity,
     the key column names and the row's own values;
  2. the block format (tools/read_review.py): quoting from a mail client, a wrapped
     comment, a greeting, a signature, an unknown field — read, not dropped;
  3. the resolution: the row still exists, exactly once, and says what the reader saw.
     A row the file no longer holds, and a value that moved, are findings, not errors.

The browser half opens the file from file:// in Chromium and drives it the way a reader
would: click the button, click a row, type, add, copy. A missing Playwright is a FAIL,
not a skip (tests/test_verify_gate_browser.py: a gate that reports success having never
opened the file is worse than one that reports nothing).

Every negative case here is a working case with one thing wrong, so a check that cannot
fail would be caught by its own counterpart.

    zsh -lc 'uv run --extra verify python tests/test_review_roundtrip.py'
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
import read_review  # noqa: E402

DATA = ROOT / "examples" / "01-hello-dashboard" / "salgsdata.csv"
AVVIK = ROOT / "examples" / "32-rows-register" / "avvik.csv"
REGISTER = [str(TOOLS / "build_register.py"), "--data", str(AVVIK),
            "--title", "Avvik per enhet",
            "--columns", "Enhet,Status,Dager,Belop", "--numeric", "Dager,Belop",
            "--group-by", "Enhet", "--sort", "Dager", "--desc",
            "--source", "Syntetisk eksempeldata (avvik.csv)", "--requested-by", "Kvalitet"]
BUILD = [str(TOOLS / "build_dashboard.py"), "--data", str(DATA),
         "--title", "Salg per region og produkt 2026",
         "--dimension", "Produkt", "--measure", "Belop", "--time", "Maaned",
         "--filters", "Region,Produkt,Kanal",
         "--source", "Eksempeldata (syntetisk) — salgsdata.csv",
         "--requested-by", "Prosjekteier"]

PASS = FAIL = 0


def chk(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def build(out: pathlib.Path, *extra: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, SOURCE_DATE_EPOCH="1761300000")
    return subprocess.run([sys.executable, *BUILD, "--out", str(out), *extra],
                          capture_output=True, text=True, env=env)


def build_register(out: pathlib.Path, *extra: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, SOURCE_DATE_EPOCH="1792836000")
    return subprocess.run([sys.executable, *REGISTER, "--out", str(out), *extra],
                          capture_output=True, text=True, env=env)


def payload(**over) -> str:
    """A block as a reader would hand it back, with any field overwritten."""
    lines = {"artefact": "Salg per region og produkt 2026", "file": "annotert.html",
             "built": over.get("built", "2026-10-24 09:00 UTC"), "rows": "776",
             "source": "Eksempeldata (syntetisk) — salgsdata.csv",
             "keys": "Maaned, Region, Produkt, Kanal", "measure": "Belop"}
    out = ["TUN-REVIEW 1"] + [f"{k}: {v}" for k, v in lines.items()]
    for row, value, comment in over.get("blocks", [
            ("2026-01 | Oslo | Boliglån | Nettbank", "4 664 226", "Dobbelt av det vi solgte.")]):
        out += ["--", f"row: {row}", f"value: {value}", f"comment: {comment}"]
    return "\n".join(out) + "\n"


def main() -> int:
    print("review round trip")
    print("─" * 62)
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        plain, note = tmp / "plain.html", tmp / "annotert.html"
        r0, r1 = build(plain), build(note, "--annotate")
        chk("both builds succeed", r0.returncode == r1.returncode == 0,
            (r0.stderr + r1.stderr)[-300:])
        if r0.returncode or r1.returncode:
            print(f"PASS: {PASS}  FAIL: {FAIL}")
            return 1

        page = note.read_text(encoding="utf-8")

        # ---- 1. the layer the builder appends
        chk("without --annotate there is no block", "TUN-REVIEW 1" not in plain.read_text(encoding="utf-8"))
        chk("without --annotate there is no layer", 'id="annotate-toggle"' not in plain.read_text(encoding="utf-8"))
        chk("with --annotate the sheet names the format", "TUN-REVIEW 1" in page)
        chk("the sheet names the key columns", "keys: Maaned, Region, Produkt, Kanal" in page,
            page[page.find("keys:"):][:60])
        chk("the style went into the head, not the body",
            page.index(".annotate-bar{display:none}") < page.index("</head>"))
        chk("the markup went before </body>", page.index('id="annotate-toggle"') < page.index("</body>"))
        chk("the sheet shows a real row of this file, filled in",
            "row: 2026-01 | Oslo | Boliglån | Nettbank" in page)
        first = note.read_bytes()
        build(note, "--annotate")
        chk("two annotated builds of the same file are byte-identical",
            note.read_bytes() == first)

        # ---- 2. the format, including what a mail client does to it
        ident, blocks, warns = read_review.parse_payload(payload())
        chk("a plain block parses", (len(blocks), ident.get("keys")) ==
            (1, "Maaned, Region, Produkt, Kanal"), f"{len(blocks)} blocks, {warns}")
        quoted = "\n".join("> " + ln if ln else ln for ln in payload().splitlines())
        chk("a quoted block parses the same",
            read_review.parse_payload("Her er det jeg fant:\n\n" + quoted)[1] == blocks)
        wrapped = payload(blocks=[("2026-01 | Oslo | Boliglån | Nettbank", "4 664 226",
                                  "Dette tallet ser dobbelt ut.\nVi hadde to selgere.")])
        chk("a wrapped comment is joined back", read_review.parse_payload(wrapped)[1][0]["comment"] ==
            "Dette tallet ser dobbelt ut. Vi hadde to selgere.")
        greet = "Hei!\n\n" + payload() + "\nMvh Enhetsleder Nord\n"
        ident2, blocks2, warns2 = read_review.parse_payload(greet)
        chk("a greeting and a signature are ignored, not glued on",
            blocks2[0]["comment"] == "Dobbelt av det vi solgte." and
            any("Enhetsleder" in w for w in warns2), str(warns2))
        try:
            read_review.parse_payload("Bare en e-post uten blokk")
            chk("a payload with no block raises", False)
        except ValueError as exc:
            chk("a payload with no block raises", "TUN-REVIEW 1" in str(exc), str(exc))
        chk("a block with no comments is noted",
            any("no comments" in w for w in read_review.parse_payload(payload(blocks=[]))[2]))

        # ---- 3. resolving against the artefact
        def rep(text: str) -> tuple[str, int]:
            return read_review.report(note, text)

        body, code = rep(payload(built=""))
        chk("an identical build resolves the row", code == 0 and "| same |" in body, body[-300:])
        chk("the row's value is shown", "4 664 226" in body)
        body, _ = rep(payload(blocks=[("2026-01 | Oslo | Boliglån | Nettbank", "1", "Feil.")]))
        chk("a figure that differs is shown beside the file's own",
            "**block says 1**" in body and
            "figures in the block that differ from the file: **1**" in body,
            body[body.find("| 1 |"):][:200])
        body, _ = rep(payload(blocks=[("2026-01 | Oslo | BSU | Nettbank", "1", "Mangler.")]))
        chk("a row the file no longer holds is a finding, not a crash",
            "**not found**" in body and "rows the file no longer holds: **1**" in body,
            body[body.find("| 1 |"):][:200])
        body, _ = rep(payload(blocks=[("2026-01 | Oslo | Boliglån", "1", "For faa verdier.")]))
        chk("a row line with too few values says so", "value(s)" in body,
            body[body.find("| 1 |"):][:200])
        body, _ = rep(payload(built="2020-01-01 00:00 UTC"))
        chk("a block from another build is flagged loudly",
            "not the same build the reader looked at" in body and "2020-01-01" in body)
        body, _ = rep(payload(blocks=[("2026-01 | Oslo | Boliglån | Nettbank | nei",
                                       "1", "Ukjent kolonne.")])
                      .replace("keys: Maaned, Region, Produkt, Kanal",
                               "keys: Maaned, Region, Produkt, Kanal, FinnesIkke"))
        chk("a column this file does not have says so", "has no column" in body,
            body[body.find("| 1 |"):][:220])
        body, code = rep("ingenting")
        chk("nothing to read exits 2", code == 2 and "Could not read" in body, body[:120])
        chk("an empty-value comment is still placed",
            "| same |" in rep(payload(blocks=[("2026-01 | Oslo | Boliglån | Nettbank", "", "Uten tall.")]))[0])

        # paired mode: the numbers live in data.js, and the block still resolves.
        pair = tmp / "parr" / "p.html"
        pair.parent.mkdir()
        build(pair, "--annotate", "--mode", "paired")
        chk("paired mode writes data.js", (pair.parent / "data.js").exists())
        chk("paired mode resolves through the sidecar", "| same |" in rep(
            payload(blocks=[("2026-01 | Oslo | Boliglån | Nettbank", "4 664 226", "Ok.")]))[0])

        # ---- the register carries the layer too, and there it has no measure
        reg_plain, reg = tmp / "reg-plain.html", tmp / "avvik.html"
        rp, rn = build_register(reg_plain), build_register(reg, "--annotate")
        chk("register: both builds succeed", rp.returncode == rn.returncode == 0,
            (rp.stderr + rn.stderr)[-300:])
        regpage = reg.read_text(encoding="utf-8")
        chk("register: without --annotate there is no layer",
            'id="annotate-toggle"' not in reg_plain.read_text(encoding="utf-8"))
        chk("register: the sheet names the text columns as the row's name",
            "keys: Enhet, Status" in regpage, regpage[regpage.find("keys:"):][:60])
        chk("register: there is no measure to name", '"measure": ""' in regpage,
            regpage[regpage.find('"measure"'):][:40])
        chk("register: the layer knows how this template labels a cell",
            '"cellAttr": "data-label"' in regpage)
        reg_first = reg.read_bytes()
        build_register(reg, "--annotate")
        chk("register: two builds of the same file are byte-identical",
            reg.read_bytes() == reg_first)
        reg_art = read_review.artefact(reg)
        chk("register: the reader reads the register's own data shape",
            len(reg_art["data"]) > 100 and "Enhet" in reg_art["data"][0],
            str(list(reg_art["data"][0])[:4]) if reg_art["data"] else "no rows")

        # ---- 4. the browser half
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            chk("playwright importable", False,
                "run with: uv run --extra verify python tests/test_review_roundtrip.py")
            print("─" * 62)
            print(f"PASS: {PASS}  FAIL: {FAIL}")
            return 1

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            pg = ctx.new_page()
            errors: list[str] = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto(note.as_uri())
            pg.wait_for_timeout(700)

            chk("the toggle is visible", pg.locator("#annotate-toggle").is_visible())
            chk("nothing to copy before a comment", not pg.locator("#annotate-out").is_visible())
            chk("the count starts at zero",
                pg.locator("#annotate-count").inner_text().strip() == "Ingen kommentarer",
                pg.locator("#annotate-count").inner_text())

            pg.locator("#annotate-toggle").click()
            chk("turning it on says what to do", pg.locator("#annotate-hint").is_visible())
            chk("and marks the page", pg.evaluate("document.body.classList.contains('annotate-on')") is True)

            row = pg.locator("#tbl tbody tr").first
            cells = [row.locator("td").nth(i).inner_text().strip() for i in range(4)]
            measure = row.locator("td").nth(5).inner_text().strip()
            row.click()
            chk("clicking a row opens the form", pg.locator("#annotate-form").is_visible())
            target = pg.locator("#annotate-target").inner_text()
            chk("the form names the row that was clicked",
                all(c in target for c in cells) and measure in target, f"{target} vs {cells}+{measure}")

            pg.locator("#annotate-add").click()
            pg.wait_for_timeout(100)
            chk("an empty comment is refused",
                not pg.locator("#annotate-out").is_visible() and
                pg.locator("#annotate-count").inner_text().strip() == "Ingen kommentarer",
                pg.locator("#annotate-count").inner_text())

            said = "Dette tallet ser dobbelt ut — vi hadde to selgere."
            pg.locator("#annotate-text").fill(said)
            pg.locator("#annotate-add").click()
            pg.wait_for_timeout(150)
            chk("adding a comment shows the block", pg.locator("#annotate-out").is_visible())
            got = pg.locator("#annotate-payload").input_value()
            chk("the block starts with the format line", got.splitlines()[0] == "TUN-REVIEW 1", got[:40])
            chk("the block carries the build it was written against",
                any(ln.startswith("built: ") and len(ln) > 12 for ln in got.splitlines()))
            chk("the block names the key columns",
                "keys: Maaned, Region, Produkt, Kanal" in got, got[:400])
            chk("the block carries the row's own values",
                "row: " + " | ".join(cells) in got, got[got.find("row:"):][:120])
            chk("the block carries the value the reader saw", f"value: {measure}" in got)
            chk("the block carries the comment", f"comment: {said}" in got)
            chk("the count followed", pg.locator("#annotate-count").inner_text().strip() == "1 kommentar",
                pg.locator("#annotate-count").inner_text())

            # The whole point: what the browser produced is what read_review reads back.
            body, code = rep(got)
            chk("the browser's own block resolves in the file it came from",
                code == 0 and "| same |" in body and said in body, body[-400:])
            chk("no row was missing", "rows the file no longer holds: **0**" in body)

            chk("the commented row is marked, so scrolling back finds it",
                pg.locator("#tbl tbody tr.annotate-done").count() == 1 and
                pg.locator("#tbl tbody tr.annotate-done").first.get_attribute("title") ==
                "Denne raden har en kommentar.",
                str(pg.locator("#tbl tbody tr.annotate-done").count()))
            pg.locator("#tbl thead th button").first.click()
            pg.wait_for_timeout(250)
            chk("the marker survives the table being re-sorted",
                pg.locator("#tbl tbody tr.annotate-done").count() == 1,
                str(pg.locator("#tbl tbody tr.annotate-done").count()))

            pg.locator("#annotate-toggle").click()
            chk("turning it off stops the marking",
                pg.evaluate("document.body.classList.contains('annotate-on')") is False)
            chk("but the block stays available",
                pg.locator("#annotate-out").is_visible() and
                pg.locator("#annotate-payload").input_value().startswith("TUN-REVIEW 1"))
            pg.locator("#annotate-list button").first.click()
            pg.wait_for_timeout(100)
            chk("a comment can be removed again", not pg.locator("#annotate-out").is_visible())
            chk("no script errors", not errors, str(errors[:2]))
            ctx.close()

            ctx = browser.new_context(java_script_enabled=False)
            pg = ctx.new_page()
            pg.goto(note.as_uri())
            chk("JS off: the sheet is the page", pg.locator("#annotate-sheet").is_visible())
            chk("JS off: there is no dead button", not pg.locator("#annotate-toggle").is_visible())
            sheet = pg.locator("#annotate-sheet").inner_text()
            chk("JS off: the sheet carries the identity and a worked example",
                "TUN-REVIEW 1" in sheet and "row: 2026-01 | Oslo" in sheet, sheet[:200])
            chk("JS off: it says how to use it", "Kopier linjen" in sheet)
            ctx.close()

            # The register: one table, but a grouped one, so the layer has to tell a
            # record from a band and from the empty-search row.
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            pg = ctx.new_page()
            errors2: list[str] = []
            pg.on("pageerror", lambda e: errors2.append(str(e)))
            pg.goto(reg.as_uri())
            pg.wait_for_timeout(700)
            pg.locator("#annotate-toggle").click()
            chk("register: the bands are drawn", pg.locator("#tbl tbody tr.grp").count() >= 1)
            pg.locator("#tbl tbody tr.grp").first.click()
            pg.wait_for_timeout(150)
            chk("register: a group band is not a record, so it does not open a form",
                not pg.locator("#annotate-form").is_visible())

            first = pg.locator("#tbl tbody tr:not(.grp)").first
            cells = [first.locator("td").nth(i).inner_text().strip() for i in range(2)]
            first.click()
            pg.wait_for_timeout(150)
            chk("register: a record opens the form", pg.locator("#annotate-form").is_visible())
            pg.locator("#annotate-text").fill("Status er feil: denne er lukket.")
            pg.locator("#annotate-add").click()
            pg.wait_for_timeout(200)
            got = pg.locator("#annotate-payload").input_value()
            chk("register: the block names the row by its text columns",
                "row: " + " | ".join(cells) in got, got[got.find("row:"):][:120])
            chk("register: there is no figure line to disagree about",
                "value:" not in got, got[got.find("--"):][:120])

            body, code = rep_reg = read_review.report(reg, got)
            chk("register: the block resolves in the register it came from",
                code == 0 and "| same" in body and "rows the file no longer holds: **0**" in body,
                body[-300:])
            chk("register: the report shows the row's own numbers",
                "Dager=" in body and "Belop=" in body, body[body.find("| 1 |"):][:200])
            chk("register: the figures the reader copied narrow a shared name",
                "narrowed by the figures" in body, body[body.find("| 1 |"):][:200])

            pg.locator("#q").fill("zzzz-ingenting")
            pg.wait_for_timeout(400)
            pg.locator("#tbl tbody tr").first.click()
            pg.wait_for_timeout(150)
            chk("register: the empty-search row is not a record either",
                not pg.locator("#annotate-form").is_visible())
            chk("register: no script errors", not errors2, str(errors2[:2]))
            ctx.close()
            browser.close()

    print("─" * 62)
    print(f"PASS: {PASS}  FAIL: {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
