#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build the front page of a folder: one card per built file, read from its own provenance.

A folder of built artefacts has no order and no introduction. Whoever is handed it sees a
list of file names and picks one, or asks which one they were supposed to open. This writes
the missing front page: what each file answers, where its numbers came from, when it was
built, and for whom - each fact lifted out of the built file's own provenance block.

    python3 tools/build_index.py \\
      --dir dashboards \\
      --title "Oversikt: dashboards for innsikt" \\
      --requested-by "Innsikt" \\
      --out dashboards/index.html

What is built in, rather than left to whoever assembles the page:

  * **a file that cannot account for itself is listed, in its own section.** A missing or
    unreadable provenance block means this page has nothing to say about what the file
    contains, so it says exactly that. Dropping it would hide a file that someone will
    eventually open.
  * **no fact on the page is invented.** Every field is read from the file, and a field that
    is absent reads "not stated" rather than being filled in from the file name.
  * **there is no script.** A page whose whole job is a list of links does not need one, so
    nothing on it can be broken by a host that refuses to run scripts.
  * **links are relative.** The folder keeps working wherever it is copied or synced to.

Stdlib only, like the rest of tools/. Python 3.8+.
"""
from __future__ import annotations

import argparse
import html
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import build_stamp  # noqa: E402
import i18n  # noqa: E402
import tun_core  # noqa: E402
import tun_tokens  # noqa: E402
from tun_tokens import strip_css_comments  # noqa: E402
from tun_core import NOT_STATED, die  # noqa: E402

TEMPLATE = ROOT / "templates" / "index.html"
STRINGS = "index"
MAX_BYTES = 40 * 1024 * 1024

# The provenance block is a comment the builders write, with one field per line, aligned by
# the builders that write it. Read by label rather than by position: a builder that adds a
# line must not shift every field on this page.
FIELDS = {
    "source": re.compile(r"^\s*Source data\s*:\s*(.+?)\s*$", re.M),
    "built": re.compile(r"^\s*Built\s*:\s*(.+?)\s*$", re.M),
    "requested": re.compile(r"^\s*Requested by\s*:\s*(.+?)\s*$", re.M),
}
PROVENANCE_MARK = "PROVENANCE"
TITLE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")


def read_card(path: pathlib.Path, t: dict) -> dict | None:
    """What this file says about itself, or None when it says nothing.

    Reads the first 8 KB only: a provenance block is at the top of every template by
    construction, and an artefact can be 40 MB.
    """
    with path.open("rb") as fh:
        head = fh.read(8192).decode("utf-8", "replace")
    if PROVENANCE_MARK not in head:
        return None
    fields = {}
    for name, pattern in FIELDS.items():
        m = pattern.search(head)
        fields[name] = m.group(1).strip() if m else ""
    title_match = TITLE.search(head) or H1.search(head)
    title = ""
    if title_match:
        title = html.unescape(TAG.sub("", title_match.group(1))).strip()
    if not title:
        title = path.stem
    # "Nothing to say" is not the same as "says nothing about the source": a block that is
    # present but carries no source is still a card, with the gap visible.
    return {
        "file": path.name,
        "title": title,
        "source": fields["source"] or t["unknown"],
        "built": fields["built"] or t["unknown"],
        "requested": fields["requested"] or t["unknown"],
        "size": path.stat().st_size,
        "state": "built",
    }


def size_text(n: int) -> str:
    if n >= 1048576:
        return f"{n / 1048576:.1f} MB"
    return f"{max(1, round(n / 1024))} kB"


def card_html(card: dict, t: dict) -> str:
    cls = "card" if card["state"] == "built" else "card bare"
    facts = [("field_source", card["source"]), ("field_built", card["built"]),
             ("field_requested", card["requested"]), ("field_size", size_text(card["size"]))]
    rows = "".join(f"<dt>{html.escape(t[k])}</dt><dd>{html.escape(str(v))}</dd>"
                   for k, v in facts)
    return (f'    <li class="{cls}">\n'
            f'      <h3><a href="{html.escape(card["file"], quote=True)}">'
            f'{html.escape(card["title"])}</a></h3>\n'
            f'      <dl class="facts">{rows}</dl>\n'
            f'    </li>')


def bare_html(card: dict) -> str:
    return (f'    <li class="card bare">\n'
            f'      <h3><a href="{html.escape(card["file"], quote=True)}">'
            f'{html.escape(card["file"])}</a></h3>\n'
            f'    </li>')


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", type=pathlib.Path, default=pathlib.Path("."),
                    help="the folder to index (default: the current one)")
    ap.add_argument("--title", default="", help="the page heading (default: the folder name)")
    ap.add_argument("--include", default="", metavar="GLOB",
                    help="extra files to consider, e.g. '*.htm'. .html is always included.")
    ap.add_argument("--requested-by", default="", help="a role, not a person's name")
    ap.add_argument("--lang", choices=("nb", "en"), default="nb")
    ap.add_argument("--out", type=pathlib.Path, default=None,
                    help="where to write the page (default: <dir>/index.html)")
    args = ap.parse_args(argv)

    folder = args.dir
    if not folder.is_dir():
        die(f"{folder} is not a folder")
    out = args.out or (folder / "index.html")
    t = i18n.load(STRINGS, args.lang)

    patterns = ["*.html"] + ([args.include] if args.include else [])
    files: list[pathlib.Path] = []
    for pattern in patterns:
        for p in sorted(folder.glob(pattern)):
            if p.is_file() and p.resolve() != out.resolve() and p not in files:
                if p.name.endswith(".fragment.html"):
                    continue          # a fragment is not a document; it has no provenance
                files.append(p)
    files.sort(key=lambda p: p.name.lower())

    cards, bare = [], []
    for p in files:
        card = read_card(p, t)
        (cards if card else bare).append(card or {"file": p.name, "state": "bare",
                                                  "size": p.stat().st_size})

    if cards:
        if len(cards) == 1:
            sub = i18n.fill(t["sub_line_one"], folder=html.escape(folder.name))
        else:
            sub = i18n.fill(t["sub_line"], folder=html.escape(folder.name), count=len(cards))
    else:
        sub = i18n.fill(t["sub_line_none"], folder=html.escape(folder.name))

    body_cards = "\n".join(card_html(c, t) for c in cards) or (
        f'    <li class="empty">{html.escape(t["empty"])}</li>')
    bare_section = ""
    if bare:
        bare_section = (f'  <h2 id="bare">{html.escape(t["head_bare"])}</h2>\n'
                        f'  <p class="note">{html.escape(t["note_bare"])}</p>\n'
                        f'  <ul class="list">\n'
                        + "\n".join(bare_html(c) for c in bare) + "\n  </ul>")

    stamp = build_stamp.naive()
    # The tokens are inlined here rather than written into the template, so this page shares
    # one seam with every other artefact. auto_dark: a reader whose operating system asks for
    # dark gets a dark page with no script, which matters more here than anywhere, since this
    # page deliberately carries no script at all.
    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
    for token, value in {
        "{{TOKEN_CSS}}": strip_css_comments(token_css),
        "{{TITLE}}": html.escape(args.title or folder.name),
        "{{SUBTITLE}}": html.escape(sub),
        # The folder's NAME, never its absolute path: the page travels to other machines,
        # and a path baked into it both leaks where it was built and makes two builds of
        # the same folder differ (tests/test_i18n.py pins the bytes).
        "{{FOLDER}}": html.escape(folder.resolve().name),
        "{{BUILD_TIMESTAMP}}": html.escape(stamp),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{COUNT_ARTEFACTS}}": str(len(cards)),
        "{{COUNT_BARE}}": str(len(bare)),
        "{{CARDS}}": body_cards,
        "{{BARE_SECTION}}": bare_section,
    }.items():
        page = page.replace(token, value)
    left = re.findall(r"\{\{[A-Z0-9_:]+\}\}", page)
    if left:
        die(f"the template still holds {', '.join(sorted(set(left)))} after filling")
    if "<script" in page.lower():
        die("the index page must contain no script: nothing on it needs one")

    data = page.encode("utf-8")
    if len(data) > MAX_BYTES:
        die(f"the page is {len(data) / 1048576:.1f} MB, over the 40 MB ceiling")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(f"built {out}  ({len(cards)} file(s) with a provenance block, "
          f"{len(bare)} without)")
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
