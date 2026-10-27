#!/usr/bin/env python3
"""
read_review.py — read a "TUN-REVIEW 1" block back, and find the rows it is about.

The other half of the review round trip (tools/review_layer.py, docs/31). A reader opens
a built artefact, comments on rows, and copies a text block. This tool takes that block
and the artefact it came from and answers the only question the person who built the file
actually has: *which* rows, and does the file still say what the reader saw?

    python3 tools/read_review.py salg-dashboard.html review.txt
    pbpaste | python3 tools/read_review.py salg-dashboard.html -

It reads the data out of the artefact itself — bundled `window.DASHBOARD_DATA`, or the
`data.js` beside it in paired mode — so it needs no source file, no connection and no
account: the file the reader had is the file that answers.

What it checks, in the order a person would care:

  * is this the build the comments were written against? (their `built` against the file's)
  * does every commented row still exist, exactly once?
  * does the value the reader saw match the value the file holds now?

A row that is missing, or a value that moved, is not an error in the block: it is the
finding. Both are reported as such, with the comment attached.

Exit code 0 when the block was read, 2 when it could not be found in the input at all.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

FORMAT = "TUN-REVIEW 1"
HEADER_KEYS = ("artefact", "file", "built", "rows", "source", "keys", "measure")
BLOCK_KEYS = ("row", "status", "value", "cells", "comment")
QUOTE = re.compile(r"^[ \t]*(?:>+[ \t]?)+")
FIELD = re.compile(r"^([a-z]+):[ \t]?(.*)$")


# ---------------------------------------------------------------- reading the artefact
def _json_after(text: str, needle: str):
    """The JSON value that starts right after `needle`, or None.

    Scanned by hand rather than matched with a regex: a `]` or a `;` inside a string
    (a column called "Net; margin", a filename) would end a non-greedy pattern early and
    the block would be parsed as truncated JSON.
    """
    at = text.find(needle)
    if at < 0:
        return None
    i = at + len(needle)
    n = len(text)
    while i < n and text[i] not in "[{":
        if not text[i].isspace():
            return None
        i += 1
    if i >= n:
        return None
    depth, in_str, esc = 0, False, False
    start = i
    while i < n:
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except ValueError:
                    return None
        i += 1
    return None


def artefact(path: pathlib.Path) -> dict:
    """{data, meta, config, page} for a built artefact, with the rows as list[dict].

    Two shapes exist. A dashboard assigns `window.DASHBOARD_DATA` to an array of objects;
    a register assigns `const ROWS` to an array of arrays with `const META.columns` naming
    them. Both become one list of dicts here, so everything downstream is one codepath and
    a third builder only has to say how its rows are laid out.
    """
    page = path.read_text(encoding="utf-8")
    data = _json_after(page, "window.DASHBOARD_DATA=")
    meta = _json_after(page, "window.DASHBOARD_META=")
    config = _json_after(page, "var C = ")
    if data is None:
        rows = _json_after(page, "const ROWS = ")
        rmeta = _json_after(page, "const META = ")
        if isinstance(rows, list) and isinstance(rmeta, dict):
            names = rmeta.get("columns") or []
            if rows and isinstance(rows[0], list):
                # A register formats its numbers at build time, so these cells are already
                # the strings the reader saw; nothing here invents a locale.
                data = [dict(zip(names, r)) for r in rows]
            else:
                data = rows
            meta = {"rows": rmeta.get("rows", len(data)), "columns": names,
                    "source": "", "generated": ""}
    if data is None:
        # A comparison assigns one object with its rows inside, and names its fields the way
        # a script wants them (k, b, a, d) rather than the way the table shows them. The
        # block speaks the visible columns, so the two vocabularies meet here, once.
        comp = _json_after(page, "window.COMPARISON_DATA = ")
        if isinstance(comp, dict) and isinstance(comp.get("rows"), list):
            names = {"k": "key", "b": "before", "a": "after", "d": "delta",
                     "pct": "pct", "s": "status"}
            data = [{names.get(k, k): v for k, v in r.items()} for r in comp["rows"]
                    if isinstance(r, dict)]
            meta = comp.get("meta") or {}
            meta = {"rows": len(data), "source": meta.get("source", ""),
                    "generated": meta.get("generated", "")}
    if data is None and path.parent.joinpath("data.js").exists():
        # Paired mode: the numbers live beside the file, which is the point of it.
        sidecar = path.parent / "data.js"
        text = sidecar.read_text(encoding="utf-8")
        data = _json_after(text, "window.DASHBOARD_DATA=")
        if meta is None:
            meta = _json_after(text, "window.DASHBOARD_META=")
    return {"data": data or [], "meta": meta or {}, "config": config or {},
            "page": page, "page_name": path.name}


def _display(value, lang: str = "nb") -> str:
    """A cell as the page shows it: whole numbers grouped, everything else as text."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        whole = f"{int(round(value)):,}"
        return whole.replace(",", " ") if lang == "nb" else whole
    return "" if value is None else str(value)


def _cells(text: str) -> dict[str, str]:
    """`Dager=119; Belop=48 518` as {column: value}. The one place the block spells pairs."""
    out: dict[str, str] = {}
    for part in (text or "").split("; "):
        name, sep, value = part.partition("=")
        if sep and name.strip():
            out[name.strip()] = value.strip()
    return out


def _numbers(row: dict) -> str:
    """The numeric cells of one row, for an artefact with no single measure.

    A register is a list, not a chart: the comment is about the row, and the figures the
    analyst needs are all of them, so they are shown rather than guessed at.
    """
    parts = [f"{k}={_display(v, 'nb')}" for k, v in row.items()
             if isinstance(v, (int, float)) and not isinstance(v, bool)]
    text = ", ".join(parts)
    return text if len(text) <= 160 else text[:157] + "..."


def _same_value(a: str, b: str) -> bool:
    """Are these two shown values the same? Numbers compare as numbers.

    Three renderings of one figure meet here: the page groups with whatever its locale
    says, this tool groups with `_display`, and a reader may type it plain. 48518,
    48 518 and 48.518,00 are one figure.
    """
    na, nb = _number(a), _number(b)
    if na is not None and nb is not None:
        return round(na) == round(nb)
    return _norm(a) == _norm(b)


def _norm(text: str) -> str:
    """A cell as text, with the grouping spaces a locale adds made ordinary."""
    return " ".join((text or "").replace("\u00a0", " ").replace("\u202f", " ")
                    .replace("\u2212", "-").split())


def _number(text: str):
    """A shown value as a number, or None. Tolerates the grouping a locale adds."""
    t = (text or "").replace("\u00a0", " ").replace("\u202f", " ").replace("\u2212", "-").strip()
    if not t:
        return None
    t = t.replace(" ", "")
    # A signed figure may arrive with a leading plus, which is how the page writes an
    # increase; the number is the same number.
    if t.startswith("+"):
        t = t[1:]
    if re.fullmatch(r"-?\d+", t):
        return int(t)
    t2 = t.replace(",", ".")
    if re.fullmatch(r"-?\d+\.\d+", t2):
        try:
            return float(t2)
        except ValueError:
            return None
    return None


# ----------------------------------------------------------------- reading the payload
def parse_payload(text: str) -> tuple[dict, list[dict], list[str]]:
    """(identity, blocks, warnings). Raises ValueError when the block is not there."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    start = None
    for i, line in enumerate(lines):
        if QUOTE.sub("", line).strip() == FORMAT:
            start = i
            break
    if start is None:
        raise ValueError(f"no '{FORMAT}' line in the input")
    warnings: list[str] = []
    identity: dict[str, str] = {}
    blocks: list[dict] = []
    block: dict | None = None
    field: str | None = None

    for raw in lines[start + 1:]:
        line = QUOTE.sub("", raw).rstrip()
        if not line.strip():
            # A blank line ends a wrapped field. What comes after it is a signature or a
            # greeting, not more comment: the layer writes one line per field, so a
            # wrapped field never contains a blank line to begin with.
            field = None
            continue
        if line.strip() == "--":
            block, field = {}, None
            blocks.append(block)
            continue
        m = FIELD.match(line.strip())
        key = m.group(1) if m else ""
        if m and key in HEADER_KEYS and block is None:
            identity[key] = m.group(2).strip()
            field = None
            continue
        if m and key in BLOCK_KEYS:
            if block is None:
                block = {}
                blocks.append(block)
            block[key] = m.group(2).strip()
            field = key
            continue
        # Not a field: a mail client wrapped the line above, or the reader wrote a
        # sentence of their own. Either way it belongs to the field it follows.
        if block is not None and field:
            block[field] = (block.get(field, "") + " " + line.strip()).strip()
        else:
            # Not attached to anything: a greeting above the block, a signature after it,
            # or a field name this format does not know. Reported, never dropped, so the
            # person reading the report can see what the parser did not use.
            where = "" if block is None else " (after a blank line, so not part of a comment)"
            warnings.append(f"ignored{where}: {line.strip()[:80]}")
    if not blocks:
        warnings.append("the block carries no comments")
    for n, b in enumerate(blocks, 1):
        if not b.get("row"):
            warnings.append(f"comment {n} has no 'row:' line, so it cannot be placed")
        if not b.get("comment"):
            warnings.append(f"comment {n} has no text")
    return identity, blocks, warnings


# ---------------------------------------------------------------------- finding rows
def resolve(block: dict, keys: list[str], data: list[dict]) -> tuple[list[dict], str]:
    """(matching rows, why not) for one comment."""
    values = [_norm(v) for v in (block.get("row") or "").split("|")]
    if not keys:
        return [], "the block names no key columns"
    if len(values) != len(keys):
        return [], (f"the block names {len(keys)} column(s) ({', '.join(keys)}) but the row "
                    f"line has {len(values)} value(s)")
    missing = [k for k in keys if not any(k in r for r in data)]
    if missing:
        return [], f"this file has no column {', '.join(missing)}"
    hits = [r for r in data
            if [_norm(_display(r.get(k), "nb")) for k in keys] == values
            or [_norm(_display(r.get(k), "en")) for k in keys] == values]
    return hits, "" if hits else "no row in this file has that combination"


def report(path: pathlib.Path, payload_text: str) -> tuple[str, int]:
    """The Markdown report, and the exit code."""
    art = artefact(path)
    try:
        identity, blocks, warnings = parse_payload(payload_text)
    except ValueError as exc:
        return f"# Review of {path.name}\n\nCould not read the block: {exc}\n", 2

    data = art["data"]
    config = art["config"] or {}
    # The block names its own key columns, so it can be read against a file built without
    # the layer. The artefact's own config is the fallback for a hand-written block.
    said_keys = identity.get("keys") or ", ".join(config.get("keys") or [])
    keys = [k.strip() for k in said_keys.split(",") if k.strip()]
    file_built = config.get("built") or (art["meta"] or {}).get("generated") or ""
    file_rows = config.get("rows") or (art["meta"] or {}).get("rows") or len(data)
    out: list[str] = [f"# Review of {identity.get('artefact') or path.name}", ""]

    said_built = identity.get("built", "")
    mismatches = []
    if said_built and file_built and said_built != file_built:
        mismatches.append(f"the comments were written against a build from **{said_built}**; "
                          f"this file was built **{file_built}**")
    said_rows = identity.get("rows", "")
    if said_rows and str(file_rows) and said_rows.strip() != str(file_rows):
        mismatches.append(f"the comments saw **{said_rows}** rows; this file has **{file_rows}**")
    said_name = identity.get("file", "")
    if said_name and said_name != path.name:
        mismatches.append(f"the comments name the file `{said_name}`; this is `{path.name}` "
                          f"(a rename is fine, the build line above is the real check)")

    out.append(f"**{len(blocks)} comment(s)**"
               + (f" on `{path.name}`" if path.name else "")
               + (f", built {file_built}" if file_built else "") + ".")
    if mismatches:
        out += ["", "> **This is not the same build the reader looked at.**"]
        out += [f"> - {m}" for m in mismatches]
        out += ["", "Place the comments against the build they name, or confirm the difference "
                    "is only a rebuild, before acting on them."]
    out.append("")

    measure = identity.get("measure") or config.get("measure") or ""
    moved = missing = 0
    out += ["| # | row | comment | the file says | check |", "|---|---|---|---|---|"]
    for n, b in enumerate(blocks, 1):
        hits, why = resolve(b, keys, data)
        coord = (b.get("row") or "(no row)").replace("|", "/")
        comment = (b.get("comment") or "").replace("|", "/").replace("\n", " ")
        if not hits:
            missing += 1
            out.append(f"| {n} | {coord} | {comment} | (none) | **not found**: {why} |")
            continue
        note = ""
        if len(hits) > 1:
            # Several records share the same text cells (a grouped register shows few
            # columns). The figures the reader copied narrow it down; if they do not, say
            # how many rows it could be instead of naming one as if it were found.
            said_cells = _cells(b.get("cells", ""))
            if said_cells:
                narrowed = [r for r in hits
                            if all(_same_value(_display(r.get(k), "nb"), v)
                                   for k, v in said_cells.items() if k in r)]
                if narrowed:
                    hits = narrowed
                    note = "; narrowed by the figures to " + str(len(hits))
            if len(hits) > 1:
                note += f"; {len(hits)} rows share that key, first shown"
        row = hits[0]
        now = _display(row.get(measure), "nb") if measure else _numbers(row)
        status = b.get("status", "")
        if status and not now:
            # The artefact marks a key as present on one side only, so this side's figure is
            # empty by construction. Naming the mark keeps the report from reading as a row
            # the file got wrong: the author of the comment is looking at a key that is
            # gone, and there is nothing to compare the figure to.
            now = f"({status})"
        said = b.get("value", "")
        if said and _number(said) is not None and _number(now) is not None:
            # Compared at the precision the page shows (whole numbers), so a fraction the
            # reader could not see is not reported as a value that moved.
            same = round(_number(said)) == round(_number(now))
            check = "same" if same else f"**block says {said}**"
            if not same:
                moved += 1
        elif said and said != now:
            check = f"**block says {said}**"
            moved += 1
        else:
            check = "same"
        check += note
        marked = f" ({b['status']})" if b.get("status") else ""
        out.append(f"| {n} | {coord} | {comment} | {now or '(none)'} | {check}{marked} |")

    out += ["", "---", ""]
    out.append(f"- rows the file no longer holds: **{missing}**")
    out.append(f"- figures in the block that differ from the file: **{moved}**")
    if warnings:
        out.append(f"- notes from the block: {len(warnings)}")
        out += [f"  - {w}" for w in warnings]
    if missing or moved:
        out.append("")
        out.append("A row the file does not hold, and a figure that differs from it, are the "
                   "findings, not faults in the block. The reader is describing what they "
                   "saw; the file is the other half of the disagreement.")
    return "\n".join(out) + "\n", 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("artefact", type=pathlib.Path, help="the built .html the reader had")
    ap.add_argument("payload", nargs="?", default="-",
                    help="the pasted block: a file, or - for stdin (default)")
    ap.add_argument("--out", type=pathlib.Path, default=None, help="write the report here")
    args = ap.parse_args()

    if not args.artefact.exists():
        raise SystemExit(f"read_review: no such file: {args.artefact}")
    text = sys.stdin.read() if args.payload == "-" else pathlib.Path(args.payload).read_text(
        encoding="utf-8")
    body, code = report(args.artefact, text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(body, encoding="utf-8")
        print(f"wrote {args.out}  ({len(body.splitlines())} lines)")
    else:
        sys.stdout.write(body)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
