#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún, and part of its Artefact Runtime. Licence: GNU AGPL v3
# or later (see LICENSE), with the Tún Artefact Exception v1.1 (see
# COPYING.ARTEFACT-EXCEPTION): documents generated with this file may be conveyed
# under terms of your choice, provided the Origin Notice is preserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a standalone comparison: two extracts of one measure, matched on a key.

The most common reporting question in a tenant is not "what is the number" but "what moved
since last month". That is answered by hand in Excel, where the arithmetic is invisible and
the answer dies with the spreadsheet. This makes it an artefact: one self-contained file
with every key, its two values, the change, and what is new or gone.

    python3 tools/build_comparison.py \\
      --before examples/33-comparison/forrige.csv \\
      --after  examples/33-comparison/denne.csv \\
      --key Region --value Omsetning \\
      --title "Omsetning per region: september mot oktober" \\
      --before-label September --after-label Oktober \\
      --source "Syntetisk eksempeldata (forrige.csv, denne.csv)" \\
      --requested-by "Innsikt" \\
      --out examples/33-comparison/sammenligning.html

What is built in, rather than left to whoever assembles the file:

  * **a key in only one extract is shown, and named.** It is "new" or "gone", never
    dropped. Dropping it would make the totals reconcile with nothing and hide a real
    event: a region that stopped reporting looks identical to a region with zero sales.
  * **both totals are printed, and the change is printed beside them.** A reader should
    never have to subtract two numbers themselves to find out whether the page agrees with
    the headline.
  * **the no-JS view is the largest movers, drawn by the builder.** A reader whose browser
    will not run the script still sees the answer, and the sentence that says what is
    missing, instead of an empty table.
  * **percentage change is absent, not infinite, when there was nothing to divide by.**
    A key that went from 0 to 5 has a real change and no meaningful percent; the page shows
    a dash rather than a fabricated 100 %.
  * **no cell is interpreted.** Keys are written as text, never as markup, and the payload
    is escaped at the characters that could end a script element.

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

import build_size  # noqa: E402
import review_layer  # noqa: E402
import build_stamp  # noqa: E402
import feedback_link  # noqa: E402
import i18n  # noqa: E402
import tun_core  # noqa: E402
import tun_tokens  # noqa: E402
from tun_tokens import strip_css_comments  # noqa: E402
from tun_core import NOT_STATED, as_script_json, die  # noqa: E402

TEMPLATE = ROOT / "templates" / "compare-dashboard.html"
STRINGS = "compare-dashboard"
NOJS_ROWS = 12           # how many rows the no-JS view carries
MAX_BYTES = 40 * 1024 * 1024
FLAT_EPSILON = 0.005     # below half a hundredth, "unchanged" is the honest word


def load(path: pathlib.Path, key: str, value: str) -> tuple[dict[str, float], int]:
    """Sum the value column per key. Returns ({key: total}, rows read).

    Summed rather than the first row per key: the input is usually a transaction extract,
    where a key appears many times, and taking one row per key would answer a different
    question than the reader asked. A key whose value cells are all unparsable keeps a
    total of zero, because a value that is not a number cannot add to a number.
    """
    if not path.is_file():
        die(f"{path} does not exist")
    reader = tun_core.read_rows(path)
    if not reader:
        die(f"{path.name} has no rows")
    header = tun_core.columns(reader)
    for wanted in (key, value):
        if wanted not in header:
            die(f"{wanted!r} is not a column in {path.name}. Available: {', '.join(header)}")
    totals: dict[str, float] = {}
    for row in reader:
        name = str(row.get(key) or "").strip()
        if not name:
            continue                       # a row with no key cannot be compared to anything
        number = tun_core.to_number(row.get(value))
        totals[name] = totals.get(name, 0.0) + (float(number) if number is not None else 0.0)
    return totals, len(reader)


def compare(before: dict[str, float], after: dict[str, float]) -> list[dict]:
    """One row per key in either extract, with the change and how to describe it."""
    rows = []
    for name in sorted(set(before) | set(after)):
        b = before.get(name)
        a = after.get(name)
        if b is None:
            state, delta, pct = "added", a, None
        elif a is None:
            state, delta, pct = "gone", -b, None
        else:
            delta = a - b
            if abs(delta) < FLAT_EPSILON:
                state = "flat"
            else:
                state = "up" if delta > 0 else "down"
            # A percentage needs something to divide by. Zero is not a small denominator,
            # it is the absence of one, so there is no percent rather than an infinite one.
            pct = (delta / b) if b not in (0, None) else None
        rows.append({"k": name, "b": b, "a": a, "d": delta,
                     "pct": pct, "s": state})
    return rows


def fmt(value: float | None, t: dict) -> str:
    if value is None:
        return "\u2013"
    text = f"{abs(value):,.1f}".rstrip("0").rstrip(".")
    if t["dec"] == ",":
        text = text.replace(",", "\u00a0").replace(".", ",")
    else:
        text = text.replace(",", "\u2009")
    return ("\u2212" if value < 0 else "") + text


def signed(value: float | None, t: dict) -> str:
    if value is None:
        return "\u2013"
    if abs(value) < FLAT_EPSILON:
        return fmt(0.0, t)
    return ("+" if value > 0 else "") + fmt(value, t)


def pct_text(value: float | None) -> str:
    if value is None:
        return "\u2013"
    return f"{value * 100:+.1f} %".replace(".", ",")


def static_rows(rows: list[dict], t: dict) -> str:
    """The no-JS view: the largest movers, in the same shape the script draws."""
    ranked = sorted(rows, key=lambda r: abs(r["d"] or 0), reverse=True)[:NOJS_ROWS]
    if not ranked:
        return f'      <tr><td colspan="6">{html.escape(t["table_caption"])}</td></tr>'
    top = max((abs(r["d"] or 0) for r in ranked), default=0) or 1
    out = []
    for r in ranked:
        tag = ""
        if r["s"] in ("added", "gone"):
            tag = f' <span class="tag">{html.escape(t[r["s"]])}</span>'
        share = int(round((abs(r["d"] or 0) / top) * 100))
        mark = f' data-status="{r["s"]}"' if r["s"] else ""
        mark += f' data-key="{html.escape(str(r["k"]))}"'
        out.append(
            f'      <tr{mark}>'
            f'<td>{html.escape(str(r["k"]))}{tag}</td>'
            f'<td class="num">{fmt(r["b"], t)}</td>'
            f'<td class="num">{fmt(r["a"], t)}</td>'
            f'<td class="num delta {r["s"]}"><span class="sign">{signed(r["d"], t)}</span></td>'
            f'<td class="num">{pct_text(r["pct"])}</td>'
            f'<td class="barcol"><span class="trk {r["s"]}" aria-hidden="true">'
            f'<i style="width:{share}%"></i></span></td>'
            f'</tr>')
    return "\n".join(out)


def total(rows: list[dict], field: str) -> float:
    return sum((r[field] or 0) for r in rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--before", type=pathlib.Path, required=True,
                    help="the earlier extract (CSV)")
    ap.add_argument("--after", type=pathlib.Path, required=True,
                    help="the later extract (CSV)")
    ap.add_argument("--key", required=True, help="the column that identifies a row")
    ap.add_argument("--value", required=True, help="the column to compare, summed per key")
    ap.add_argument("--title", required=True)
    ap.add_argument("--before-label", default="", help="what 'before' means, e.g. September")
    ap.add_argument("--after-label", default="", help="what 'after' means, e.g. Oktober")
    ap.add_argument("--source", default="", help="where the rows came from")
    ap.add_argument("--requested-by", default="", help="a role, not a person's name")
    ap.add_argument("--meaning", choices=("none", "up", "down"), default="none",
                    help="which direction is good news, so colour may encode a verdict: "
                         "'up' or 'down'. default none, where the sign carries direction and "
                         "colour stays neutral, because an increase is not good or bad by "
                         "itself: more revenue and more overtime are the same arithmetic")
    ap.add_argument("--lang", choices=("nb", "en"), default="nb")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--feedback-to", default="", metavar="ADDRESS_OR_ISSUE_URL",
                    help=feedback_link.FLAG_HELP)
    ap.add_argument("--annotate", action="store_true", help=review_layer.FLAG_HELP)
    args = ap.parse_args(argv)

    before, before_rows = load(args.before, args.key, args.value)
    after, after_rows = load(args.after, args.key, args.value)
    rows = compare(before, after)

    t = i18n.load(STRINGS, args.lang)
    total_before, total_after = total(rows, "b"), total(rows, "a")
    delta_total = total_after - total_before
    added = sum(1 for r in rows if r["s"] == "added")
    gone = sum(1 for r in rows if r["s"] == "gone")
    moved = sum(1 for r in rows if r["s"] in ("up", "down"))
    delta_class = "flat" if abs(delta_total) < FLAT_EPSILON else ("up" if delta_total > 0 else "down")

    before_label = args.before_label or t["kpi_before"]
    after_label = args.after_label or t["kpi_after"]
    source = args.source or NOT_STATED
    requester = args.requested_by or NOT_STATED
    stamp = build_stamp.naive()
    extract = build_stamp.from_mtime(args.after, "%Y-%m-%d %H:%M", aware=False)

    payload = {
        "meta": {"locale": t["num_locale"], "lang": args.lang},
        "rows": rows,
    }
    js_strings = {"added": t["added"], "gone": t["gone"]}

    if args.feedback_to:
        page_feedback = feedback_link.block(args.feedback_to, title=args.title, built=stamp,
                                           source=source, lang=args.lang)
    else:
        page_feedback = ""
    # The tokens are inlined here rather than written into the template, so this page shares
    # one seam with every other artefact. auto_dark: a reader whose system is dark gets a
    # dark comparison with no script, and the status colours come from the theme rather than
    # from a hex chosen for white.
    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
    substitutions = {
        "{{TOKEN_CSS}}": strip_css_comments(token_css),
        "{{TITLE}}": html.escape(args.title),
        "{{SUBTITLE}}": html.escape(
            f"{before_label} \u2192 {after_label} \u00b7 {args.key} \u00b7 "
            f"{len(rows)} {t['kpi_rows'].lower()}"),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(source),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extract),
        "{{BUILD_TIMESTAMP}}": html.escape(stamp),
        "{{REQUESTED_BY}}": html.escape(requester),
        "{{ROWS_INLINED}}": str(len(rows)),
        "{{ROWS_BEFORE}}": str(before_rows),
        "{{ROWS_AFTER}}": str(after_rows),
        "{{KEY_LABEL}}": html.escape(args.key),
        "{{BEFORE_LABEL}}": html.escape(before_label),
        "{{AFTER_LABEL}}": html.escape(after_label),
        "{{KPI_BEFORE}}": fmt(total_before, t),
        "{{KPI_AFTER}}": fmt(total_after, t),
        "{{KPI_DELTA}}": signed(delta_total, t),
        "{{KPI_DELTA_CLASS}}": delta_class,
        "{{KPI_ROWS}}": str(len(rows)),
        "{{KPI_ADDED}}": str(added),
        "{{KPI_GONE}}": str(gone),
        "{{KPI_PCT}}": pct_text((delta_total / total_before) if total_before else None),
        "{{STATIC_ROWS}}": static_rows(rows, t),
        "{{T_JSON}}": as_script_json(js_strings),
        "{{COMPARISON_DATA}}": as_script_json(payload),
        "{{MEANING}}": args.meaning,
        "{{FEEDBACK_BLOCK}}": page_feedback,
    }
    for token, value in substitutions.items():
        page = page.replace(token, value)

    if args.annotate:
        # The comparison is the artefact where a reader most often disagrees with a row
        # rather than a number: a key that appeared, or one that vanished. The comment
        # belongs to the key, and the row's own mark says which side is empty, so the
        # report explains an absent figure instead of calling the row wrong.
        head_html, body_html = review_layer.layer(
            title=args.title, file=args.out.name, built=stamp, rows=len(rows), source=source,
            keys=["key"], measure="delta", table="tbl", status_attr="data-status",
            key_attr="data-key",
            measures=["before", "after", "delta"],
            examples=[([html.unescape(str(r["k"]))], signed(r["d"], t)) for r in rows[:3]],
            lang=args.lang)
        page = review_layer.insert(page, head_html, body_html)

    left = re.findall(r"\{\{[A-Z0-9_:]+\}\}", page)
    if left:
        die(f"the template still holds {', '.join(sorted(set(left)))} after filling")

    data = page.encode("utf-8")
    if len(data) > MAX_BYTES:
        die(f"the file is {len(data) / 1048576:.1f} MB, over the 40 MB ceiling. "
            f"Compare fewer keys, or aggregate before building.")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    build_size.enforce(args.out)
    print(f"built {args.out}  ({len(data) / 1048576:.2f} MB  {len(rows)} keys, "
          f"{moved} moved, {added} new, {gone} gone)")
    print(f"  next: python3 {ROOT / 'tools' / 'verify_dashboard.py'} {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
