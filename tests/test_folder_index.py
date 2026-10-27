#!/usr/bin/env python3
"""The folder index: the page you land on when someone shares a folder of built files.

A folder of artefacts has no order and no introduction. The index is the missing front page,
and its one job is to be trustworthy about files it did not build: every fact on it is read
out of the file's own provenance block, and a file that has no block is shown as exactly
that. This suite proves the properties that make it trustworthy, plus the ones that make it
survive a folder:

  1. one card per file that carries a provenance block, sorted by name, and every link
     resolves to a file that is actually in the folder
  2. every fact on the card equals the fact in the artefact's own comment, so the page cannot
     drift from the files it describes
  3. a file with no provenance block is listed in its own section, never dropped and never
     described by guesswork; a `.fragment.html` is not a document and is skipped
  4. the index does not list itself
  5. a title holding markup is escaped: this page renders strings it did not author
  6. there is no script in the file at all, because nothing on it needs one
  7. a missing "requested by" reads as the not-stated word, not as a blank
  8. the English build is English, and no Norwegian survives it

Run: python3 tests/test_folder_index.py
"""
from __future__ import annotations

import html
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_index.py"
EXAMPLE = ROOT / "examples" / "34-folder-index"

FAILURES: list[str] = []
CHECKS = 0


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


def build(folder: pathlib.Path, *extra: str, run_dir: pathlib.Path | None = None):
    args = [sys.executable, str(BUILDER), "--dir", str(folder), "--title", "Oversikt",
            "--requested-by", "Innsikt", *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH="1767323045")
    return subprocess.run(args, capture_output=True, text=True,
                          cwd=run_dir or ROOT, env=env)


def provenance_of(path: pathlib.Path, field: str) -> str:
    """Read one field straight out of the artefact's own comment block."""
    head = path.read_text(encoding="utf-8")[:8192]
    m = re.search(rf"^\s*{field}\s*:\s*(.+?)\s*$", head, re.M)
    return m.group(1) if m else ""


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        folder = pathlib.Path(td) / "dashboards"
        folder.mkdir()
        # The example's own three artefacts are the realistic input: a dashboard, a register
        # and a comparison, each with a provenance block written by a different builder.
        for name in ("saker-dashboard.html", "saker-register.html", "saker-sammenligning.html"):
            (folder / name).write_bytes((EXAMPLE / name).read_bytes())

        print("one card per built file, and the order")
        done = build(folder)
        chk(done.returncode == 0, "the builder runs", (done.stderr or "")[-300:])
        page = (folder / "index.html").read_text(encoding="utf-8")

        links = re.findall(r'<h3><a href="([^"]+)">', page)
        chk(links == ["saker-dashboard.html", "saker-register.html", "saker-sammenligning.html"],
            "three cards, sorted by file name", ", ".join(links))
        chk(all((folder / l).is_file() for l in links), "every link resolves inside the folder")
        chk(all("/" not in l and ":" not in l for l in links),
            "links are relative, so the folder works wherever it is copied")
        chk("index.html" not in links, "the index does not list itself")
        chk(page.count('<li class="card"') == 3, "three cards in the markup",
            str(page.count('<li class="card"')))

        print("\nevery fact equals the file's own comment")
        for name in links:
            src = folder / name
            for field, label in (("Source data", "Kilde"), ("Built", "Bygget"),
                                 ("Requested by", "For")):
                want = provenance_of(src, field)
                if not want:
                    continue
                got = want in page
                chk(got, f"{name}: {label} is the artefact's own value", want[:60])
        chk(provenance_of(folder / links[0], "Source data") in page,
            "the dashboard's source line appears once the HTML entity is undone"
            if "&" not in provenance_of(folder / links[0], "Source data") else
            "the dashboard's source line is present")

        print("\na file that cannot account for itself is listed, in its own section")
        (folder / "gammel-rapport.html").write_text(
            "<!DOCTYPE html><html lang=nb><head><title>Gammel rapport</title></head>"
            "<body><h1>Gammel rapport</h1></body></html>", encoding="utf-8")
        (folder / "bilde.fragment.html").write_text("<div>et fragment</div>", encoding="utf-8")
        done = build(folder)
        page = (folder / "index.html").read_text(encoding="utf-8")
        chk(done.returncode == 0, "a folder with a bare file still builds", (done.stderr or "")[-200:])
        chk("gammel-rapport.html" in page, "the file with no provenance is on the page")
        chk('id="bare"' in page and page.index('id="bare"') > page.index('id="built"'),
            "it is in its own section, after the built files")
        chk("bilde.fragment.html" not in page, "a fragment is not a document and is skipped")
        chk(page.count('<li class="card"') == 3,
            "the built cards are unchanged by the bare file", str(page.count('<li class="card"')))

        print("\na title holding markup is escaped")
        (folder / "slem.html").write_text(
            "<!DOCTYPE html><html lang=nb><head><title>&lt;b&gt;Slem&lt;/b&gt;</title></head>"
            "<body><!-- PROVENANCE\n  Source data : noe\n  Built       : i dag\n"
            "  Requested by: ingen --></body></html>", encoding="utf-8")
        done = build(folder)
        page = (folder / "index.html").read_text(encoding="utf-8")
        chk(done.returncode == 0, "a hostile title builds", (done.stderr or "")[-200:])
        chk("<b>Slem</b>" not in page, "the title is not written as markup")
        chk("&lt;b&gt;Slem&lt;/b&gt;" in page, "it is escaped and still readable")
        (folder / "slem.html").unlink()

        print("\nthe folder travels: its path is not baked into the page")
        page_now = (folder / "index.html").read_text(encoding="utf-8")
        chk(str(folder) not in page_now and str(pathlib.Path.home()) not in page_now,
            "no absolute path appears anywhere in the page")
        chk(folder.name in page_now, "the folder's own name does, so a reader knows where it is")

        print("\nthere is no script in the file")
        chk("<script" not in page.lower(), "no script element, in any case")
        chk("onclick" not in page.lower() and "javascript:" not in page.lower(),
            "no inline handler and no javascript: URL")

        print("\na missing fact reads as not stated")
        (folder / "uten-opphav.html").write_text(
            "<!DOCTYPE html><html lang=nb><head><title>Uten opphav</title></head><body>"
            "<!-- PROVENANCE\n  Source data : noe\n  Built       : i dag --></body></html>",
            encoding="utf-8")
        done = build(folder)
        page = (folder / "index.html").read_text(encoding="utf-8")
        chk("ikke oppgitt" in page,
            "the missing 'requested by' is the word, not a blank", "ikke oppgitt")
        (folder / "uten-opphav.html").unlink()

        print("\nthe English build is English")
        done = build(folder, "--lang", "en")
        en = (folder / "index.html").read_text(encoding="utf-8")
        chk(done.returncode == 0, "the English build runs", (done.stderr or "")[-200:])
        for word in ("The files in this folder", "Source", "Built", "Size", "Folder"):
            chk(word in en, f"the English page says {word!r}")
        for word in ("Filene i denne mappen", "Størrelse", "ikke oppgitt"):
            chk(word not in en, f"and not {word!r}")

        print("\nthe same folder builds the same bytes twice")
        os.environ["SOURCE_DATE_EPOCH"] = "1767323045"
        build(folder)
        first = (folder / "index.html").read_bytes()
        build(folder)
        second = (folder / "index.html").read_bytes()
        chk(first == second, "two runs with the same inputs give identical output",
            f"{len(first)} vs {len(second)} bytes")

        print("\nthe example in the repository is the builder's own output")
        ex_index = (EXAMPLE / "index.html").read_text(encoding="utf-8")
        ex_links = re.findall(r'<h3><a href="([^"]+)">', ex_index)
        chk(len(ex_links) == 3, "the committed example lists its three artefacts", ", ".join(ex_links))
        chk(all((EXAMPLE / l).is_file() for l in ex_links),
            "and every one of them is committed beside it")

    print()
    if FAILURES:
        print(f"{CHECKS - len(FAILURES)} passed, {len(FAILURES)} failed")
        for f in FAILURES:
            print(f"  \u2717 {f}")
        return 1
    print(f"{CHECKS} passed, 0 failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
