#!/usr/bin/env python3
"""
review_layer.py — the optional review round trip inside a built artefact.

Used by tools/build_dashboard.py when it gets `--annotate`. Stdlib only. Without that
flag the builder never calls this and the artefact is byte for byte what it was before
this module existed.

The problem it answers: every other Tún artefact is one-way. Someone opens the file,
disagrees with a number, and the only way back is a screenshot and a sentence in an
e-mail that names neither the row nor the build. This layer makes the file ask, and the
answer is a text block the reader copies into whatever they already use to talk to the
person who built it. No server, no upload, no account:

    reader clicks a row   ->  a comment
    comment              ->  a "TUN-REVIEW 1" block on their clipboard
    block pasted anywhere -> tools/read_review.py finds the rows again

The block is line-based `key: value`, not JSON, for two reasons: a person can write one
by hand when JavaScript is off (the static sheet in the partial shows them how, filled in
with their own first rows), and a mail client that wraps a line does not destroy it —
read_review.py joins a wrapped comment back together.

The keys of that block are the same in both languages on purpose. It is a data format,
not prose: tools/read_review.py parses one vocabulary. The words on screen come from
templates/i18n/_annotate.strings.
"""
from __future__ import annotations

import html
import json
import pathlib

import i18n

PARTIAL = pathlib.Path(__file__).resolve().parents[1] / "templates" / "_annotate.html"
STYLE_MARK = "<!--TUN-ANNOTATE-STYLE-->"
BODY_MARK = "<!--TUN-ANNOTATE-BODY-->"

FLAG_HELP = ("optional: let the reader comment on rows inside the file and hand the "
             "comments back as a text block (see tools/read_review.py)")

FORMAT = "TUN-REVIEW 1"
MAX_EXAMPLES = 3


def header_lines(*, title: str, file: str, built: str, rows: int, source: str,
                 keys: list[str], measure: str) -> list[str]:
    """The identity lines every block carries, in the one vocabulary read_review parses."""
    return [FORMAT,
            f"artefact: {title}",
            f"file: {file}",
            f"built: {built}",
            f"rows: {rows}",
            f"source: {source}",
            f"keys: {', '.join(keys)}",
            f"measure: {measure}"]


def _example(values: list[str], measure_text: str, comment: str) -> str:
    block = ["row: " + " | ".join(values)]
    if measure_text:
        block.append("value: " + measure_text)
    block.append("comment: " + comment)
    return "\n".join(block)


def layer(*, title: str, file: str, built: str, rows: int, source: str,
          keys: list[str], measure: str, examples: list[tuple[list[str], str]],
          table: str = "tbl", cell_attr: str = "", measures: list[str] | None = None,
          status_attr: str = "", key_attr: str = "",
          lang: str = i18n.DEFAULT_LANG) -> tuple[str, str]:
    """Return (head_html, body_html) — the style goes in <head>, the rest before </body>.

    `examples` is up to three (key values, measure as displayed) pairs from the real rows,
    so the sheet a reader fills in by hand shows their own data, not a generic sample.

    `table` is the id of the table whose rows a reader can comment on, and `cell_attr` is
    how this template names a column on a cell: the register writes `data-label` on every
    td, the rows dashboard writes `data-col` on the th. One attribute name in the config
    instead of two codepaths in the script.

    `measure` may be empty, for an artefact with no single number under discussion: the
    block then carries the row's name only, and tools/read_review.py shows the row's
    numeric cells instead of comparing one figure.
    """
    text = PARTIAL.read_text(encoding="utf-8")
    if STYLE_MARK not in text or BODY_MARK not in text:
        raise ValueError(f"{PARTIAL.name}: missing {STYLE_MARK} or {BODY_MARK}")
    head, body = text.split(BODY_MARK)
    head = head.replace(STYLE_MARK, "")

    t = i18n.load("_annotate", lang)
    tables = i18n.load_all("_annotate")
    for other in i18n.LANGS:
        if set(tables[other]) != set(t):
            raise ValueError(f"templates/i18n/_annotate.strings: {other} keys differ")

    identity = header_lines(title=title, file=file, built=built, rows=rows, source=source,
                            keys=keys, measure=measure)
    shown = [_example(v, m, t["your_comment"]) for v, m in examples[:MAX_EXAMPLES]] or [
        _example([t["your_row"]] * max(1, len(keys)), "", t["your_comment"])]
    head_html = i18n.apply(head, t).strip()
    body_html = (i18n.apply(body, t).strip()
                 .replace("{{ANNOTATE_HEADER}}", html.escape("\n".join(identity) + "\n"))
                 .replace("{{ANNOTATE_EXAMPLES}}", html.escape("\n--\n".join(shown))))

    config = {
        "title": title, "file": file, "built": built, "rows": rows, "source": source,
        "keys": keys, "measure": measure, "table": table, "cellAttr": cell_attr,
        "measures": measures or [], "statusAttr": status_attr, "keyAttr": key_attr,
        # Only the strings the script itself writes; the rest are already in the markup.
        "t": {k: t[k] for k in ("btn_on", "btn_off", "hint", "count_none", "count_one",
                               "count_other", "row", "add", "cancel", "ask", "added",
                               "remove", "copied", "copy_manual", "annotated")},
    }
    # "<" is escaped so no value (a title, say) can end the script element early or put a
    # literal tag into the file (docs/01-tenant-constraints.md row 25).
    config_js = (json.dumps(config, ensure_ascii=False)
                 .replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    body_html = body_html.replace("{{ANNOTATE_CONFIG}}", config_js)
    left = [m for m in ("{{ANNOTATE_CONFIG}}", "{{ANNOTATE_HEADER}}", "{{ANNOTATE_EXAMPLES}}")
            if m in body_html or m in head_html]
    if left:
        raise ValueError(f"review layer placeholders not substituted: {left}")
    return head_html, body_html


def insert(page: str, head_html: str, body_html: str) -> str:
    """Put the style at the end of <head> and the markup at the end of <body>."""
    for tag in ("</head>", "</body>"):
        if tag not in page:
            raise ValueError(f"the artefact has no {tag}; the review layer needs one")
    page = page.replace("</head>", head_html + "\n</head>", 1)
    return page.replace("</body>", body_html + "\n</body>", 1)
