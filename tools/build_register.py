#!/usr/bin/env python3
"""Build a standalone register: a searchable, sortable, paged list in one HTML file.

Sometimes the question is not "show me a chart", it is "give me the list". A register is
that list, and it is the artefact people otherwise build by hand in Excel and then send as
an attachment that only one person can filter.

    python3 tools/build_register.py \\
      --data examples/32-rows-register/avvik.csv \\
      --title "Avvik 2026" \\
      --columns Enhet,Avvik,Mottatt,Status,Dager \\
      --numeric Dager \\
      --sort Dager \\
      --source "Syntetisk eksempeldata (avvik.csv)" \\
      --requested-by "Kvalitet" \\
      --out examples/32-rows-register/register.html

What is built in, rather than left to whoever assembles the file:

  * **every row the builder received is in the file.** No filter is applied at build time
    and none is hidden: a reader with the file can search all of it. When two audiences
    must see different rows, split the data and build two files (AGENTS.md rule 1 — the
    boundary is the folder, not a filter inside the file).
  * **the first page is written into the markup.** A reader whose browser will not run the
    script still sees the list, the count, and the sentence that says what is missing.
  * **a numeric column is marked as numeric.** The page then sorts it as a number and
    right-aligns it. Sorting "9" after "10" is a silent wrong answer, and a page that
    looks sorted is harder to distrust than a page that looks broken.
  * **no cell is interpreted.** Every value is written as text, never as markup, and a
    formula-looking value stays literal text. A CSV cell is data.

Stdlib only, like the rest of tools/. Python 3.8+.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import build_size  # noqa: E402
import build_stamp  # noqa: E402
import feedback_link  # noqa: E402
import review_layer  # noqa: E402
import i18n  # noqa: E402
import tun_core  # noqa: E402
import tun_tokens  # noqa: E402
from tun_core import NOT_STATED, as_script_json, die  # noqa: E402
from tun_tokens import strip_css_comments  # noqa: E402

TEMPLATE = ROOT / "templates" / "register.html"
STRINGS = "register"
MAX_CELL = 400               # a longer cell is a paragraph, not a table entry
MAX_BYTES = 40 * 1024 * 1024  # above the Tier 1 warn budget, so refuse before writing
PAGE_SIZES = (25, 50, 100, 250)
PAGE_SIZE_DEFAULT = 50
NOJS_ROWS = 25               # the first page written into the markup

# die, NOT_STATED and the numeric parse are tun_core's, so five builders refuse alike.


def load(path: pathlib.Path, columns: list[str], numeric: list[str]) -> tuple[list[str], list[list[str]]]:
    """Read the file, keep the named columns in the given order, and nothing else.

    Columns not named are dropped *before* anything is stored, so a column that should not
    be in front of this audience cannot be in the file at all — the split happens here, not
    in a browser filter.
    """
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            die(f"{path.name} is empty")
        header = [h.strip() for h in header]
        if columns:
            missing = [c for c in columns if c not in header]
            if missing:
                die(f"column(s) {', '.join(missing)} not in {path.name}. "
                    f"Available: {', '.join(header)}")
            keep = [header.index(c) for c in columns]
            names = columns
        else:
            keep = list(range(len(header)))
            names = header
        for col in numeric:
            if col not in names:
                die(f"--numeric {col!r} is not one of the columns written "
                    f"({', '.join(names)})")

        rows: list[list[str]] = []
        for line_no, raw in enumerate(reader, 2):
            if not any(cell.strip() for cell in raw):
                continue           # a blank line is not a row
            cells = []
            for index in keep:
                value = raw[index].strip() if index < len(raw) else ""
                if len(value) > MAX_CELL:
                    die(f"{path.name}:{line_no} has a {len(value)}-character cell. A register "
                        f"holds values, not paragraphs; keep the long text out of this file.")
                cells.append(value)
            rows.append(cells)
    return names, rows


def number_cells(rows: list[list[str]], numeric_cols: list[int]) -> None:
    """Mark a numeric column per row, so the page sorts it as a number.

    The column flag alone is not enough: a column that is numeric for most rows and holds
    "n/a" for one is still sorted as a number, and the empty or unparsable cell must sort
    last rather than as zero. The page handles both; this only records which is which by
    leaving a non-numeric cell as the string it is.
    """
    for row in rows:
        for col in numeric_cols:
            value = row[col]
            if value == "":
                continue
            try:
                float(value.replace("\u00a0", "").replace(" ", "").replace(",", "."))
            except ValueError:
                continue


def numeric_cell(value: str) -> float | str:
    """A cell the page can compare arithmetically, or the text as given.

    The parse itself is tun_core's, which reads both `1 234,56` and `1,234.56` as one
    thousand two hundred and thirty four and a half. This adds the register's own contract
    on top: a cell that is not a number stays the text it was, so the page shows it and
    sorts it as a string rather than turning it into zero. Named apart from the core's
    `to_number` on purpose: a local function of that name is what the shared-core suite
    reads as a builder that grew its own parser again.
    """
    if value == "":
        return ""
    number = tun_core.to_number(value)
    return value if number is None else float(number)


def group_html(name: str, meta: str, ncols: int) -> str:
    """A band that names the group and says what it holds.

    `scope="colgroup"` is what tells a screen reader the rows below belong to this header;
    a styled <td> would look the same and mean nothing. The band is not a row of data, so
    it carries no data-label attribute: the card layout on a phone must not print a column
    name beside it.
    """
    return (f'<tr class="grp"><th scope="colgroup" colspan="{ncols}">'
            f'<span class="grpname">{name}</span>'
            f'<span class="grpmeta">{meta}</span></th></tr>')


def group_key(value):
    """Group ascending, with numbers as numbers and text case-insensitively.

    The kind flag comes before the value so two keys are only compared on the third element
    when they are the same kind: a group column of years must not sort 2026 after 999 the
    way text does. An empty group value sorts last rather than as a name.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, 0, value)
    text = str(value)
    return (1 if text == "" else 0, 1, text.lower())


def head_html(names: list[str], numeric: set[int], sort_col: int, t: dict) -> str:
    cells = []
    for i, name in enumerate(names):
        cls = ' class="num"' if i in numeric else ""
        on = i == sort_col
        sort = ("descending" if t["_dir"] < 0 else "ascending") if on else "none"
        cells.append(f'<th scope="col"{cls} aria-sort="{sort}">'
                     f'<button type="button">{html.escape(name)}'
                     f'<span class="caret" aria-hidden="true">'
                     f'{("\u25be" if t["_dir"] < 0 else "\u25b4") if on else ""}</span>'
                     f'</button></th>')
    return "".join(cells)


def row_html(row: list[str], numeric: set[int], names: list[str]) -> str:
    cells = []
    for i, value in enumerate(row):
        cls = ' class="num"' if i in numeric else ""
        # data-label is the column name, so a phone can print it above the value when the
        # heading row is hidden. Without it the card layout is a list of unlabelled numbers.
        cells.append(f'<td{cls} data-label="{html.escape(names[i])}">'
                     f"{html.escape(str(value))}</td>")
    return "<tr>" + "".join(cells) + "</tr>"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True, help="CSV, one row per row")
    ap.add_argument("--title", required=True)
    ap.add_argument("--columns", default="",
                    help="comma-separated columns to show, in page order. Anything not named "
                         "is dropped before the file is written. Default: all of them.")
    ap.add_argument("--numeric", default="",
                    help="comma-separated columns to right-align and sort as numbers")
    ap.add_argument("--group-by", default="", metavar="COLUMN",
                    help="group the rows by this column. Each group gets a header stating "
                         "how many rows it holds and what its numeric columns sum to, "
                         "counted over the rows in the current view rather than only the "
                         "page on screen, so a group split across pages does not appear to "
                         "hold two different totals. The column must also be one of "
                         "--columns")
    ap.add_argument("--sort", default="", help="column to sort by at open (default: first)")
    ap.add_argument("--desc", action="store_true", help="sort descending at open")
    ap.add_argument("--page-size", type=int, default=PAGE_SIZE_DEFAULT,
                    help=f"rows per page at open (default {PAGE_SIZE_DEFAULT})")
    ap.add_argument("--source", default="", help="where the rows came from")
    ap.add_argument("--requested-by", default="", help="a role, not a person's name")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--feedback-to", default="", metavar="ADDRESS_OR_ISSUE_URL",
                    help=feedback_link.FLAG_HELP)
    ap.add_argument("--annotate", action="store_true", help=review_layer.FLAG_HELP)
    i18n.add_lang_argument(ap)
    args = ap.parse_args(argv)
    t = i18n.load(STRINGS, args.lang)

    if not args.data.is_file():
        die(f"{args.data} not found")
    if not TEMPLATE.is_file():
        die(f"template missing: {TEMPLATE}")
    if args.page_size not in PAGE_SIZES:
        die(f"--page-size must be one of {', '.join(map(str, PAGE_SIZES))}")

    columns = [c.strip() for c in args.columns.split(",") if c.strip()]
    numeric_names = [c.strip() for c in args.numeric.split(",") if c.strip()]
    names, rows = load(args.data, columns, numeric_names)
    if not rows:
        die(f"{args.data.name} has no rows")
    numeric = {names.index(c) for c in numeric_names}

    if args.sort:
        if args.sort not in names:
            die(f"--sort {args.sort!r} is not one of the columns written ({', '.join(names)}). "
                f"Name it in --columns too.")
        sort_col = names.index(args.sort)
    else:
        sort_col = 0
    group_col = None
    if args.group_by:
        if args.group_by not in names:
            die(f"--group-by {args.group_by!r} is not one of the columns written "
                f"({', '.join(names)}). Name it in --columns too.")
        group_col = names.index(args.group_by)
    sort_dir = -1 if args.desc else 1
    number_cells(rows, sorted(numeric))

    # The rows as the page holds them: typed numbers where the build said the column is
    # numeric, text everywhere else. A reader never sees markup, so nothing can run.
    packed = []
    for row in rows:
        out = list(row)
        for col in numeric:
            out[col] = numeric_cell(row[col])
        packed.append(out)

    rows_sorted = sorted(range(len(packed)),
                         key=lambda i: (packed[i][sort_col] == "",
                                        packed[i][sort_col] if sort_col in numeric
                                        else str(packed[i][sort_col]).lower()))
    if sort_dir < 0:
        rows_sorted.reverse()
    # Grouping is a second, stable pass: the groups come out ascending and the reader's own
    # sort survives inside each one. Reversing this pass instead would reverse the groups
    # too, which is not what "--desc" asks for.
    if group_col is not None:
        rows_sorted.sort(key=lambda i: group_key(packed[i][group_col]))

    # What each group holds, counted over every row the file received rather than over the
    # page on screen: a group split across two pages must not report two different totals.
    group_counts: dict = {}
    group_sums: dict = {}
    if group_col is not None:
        for row in packed:
            key = row[group_col]
            group_counts[key] = group_counts.get(key, 0) + 1
            acc = group_sums.setdefault(key, [0] * len(names))
            for col in numeric:
                value = row[col]
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    acc[col] += value

    # The static view prints the value as written ("1 200", not 1200.0): the page's script
    # may render a number, but a table cell a reader prints should read like the source.
    first = [rows[i] for i in rows_sorted[:NOJS_ROWS]]

    t_head = dict(t)
    t_head["_dir"] = sort_dir
    meta = {"columns": names, "numeric": sorted(numeric), "pageSize": args.page_size,
            "pageSizes": list(PAGE_SIZES), "sortCol": sort_col, "sortDir": sort_dir,
            "rows": len(packed)}
    strings = {k: t[k] for k in ("rows_shown", "rows_empty", "sort_label", "sort_asc",
                                 "sort_desc")}
    strings.setdefault("locale", t.get("num_locale", "nb-NO"))
    # Added only when grouping is on, so a build without it stays byte for byte what it was:
    # the frozen nb output in tests/test_i18n.py is the proof that this feature is additive.
    if group_col is not None:
        meta["groupCol"] = group_col
        strings["groupRows"] = t["group_rows"]
        strings["groupRowsOne"] = t["group_rows_one"]

    def num(value: int) -> str:
        """A count in the reader's own convention. nb groups with a space, never a comma."""
        text = f"{value:,}"
        return text.replace(",", "\u00a0") if t["dec"] == "," else text

    def sum_text(value: float) -> str:
        """A group sum in the reader's own convention, with at most one decimal.

        A sum of whole numbers prints as a whole number; a sum of one-decimal values keeps
        the decimal and the reader's comma. It is the same rule the comparison page uses, so
        two artefacts from this repo do not format the same figure two ways.
        """
        text = f"{abs(value):,.1f}".rstrip("0").rstrip(".")
        if t["dec"] == ",":
            text = text.replace(",", "\u00a0").replace(".", ",")
        else:
            text = text.replace(",", "\u2009")
        return ("\u2212" if value < 0 else "") + text

    def static_rows() -> str:
        """The no-JS view: the first page, with a group band wherever the group changes."""
        out: list[str] = []
        last: object = object()
        for shown, index in enumerate(rows_sorted):
            if shown >= NOJS_ROWS:
                break
            row = rows[index]
            if group_col is not None:
                key = packed[index][group_col]
                if key != last:
                    count = group_counts[key]
                    parts = [html.escape(str(key)),
                             i18n.fill(t["group_rows"] if count != 1 else t["group_rows_one"],
                                       n=num(count))]
                    parts += [f"{html.escape(names[col])} {sum_text(group_sums[key][col])}"
                              for col in sorted(numeric)]
                    out.append(group_html(parts[0], " · ".join(parts[1:]), len(names)))
                    last = key
            out.append(row_html(row, numeric, names))
        return "".join(out)

    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)
    source = i18n.fill(t["source_line"], name=args.source or args.data.name,
                       rows=num(len(packed)), cols=len(names))
    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=built,
                                           source=source, lang=args.lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    nojs_note = i18n.fill(t["nojs_body"], shown=num(len(first)), total=num(len(packed)))
    # The tokens are inlined here rather than written into the template, so this page shares
    # one seam with every other artefact. auto_dark: the register is read on whatever machine
    # the reader has, and a reader whose system is dark gets a dark list with no script.
    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css))
            .replace("{{TITLE}}", html.escape(args.title))
            .replace("{{SOURCE_DESCRIPTION}}", html.escape(source))
            .replace("{{EXTRACT_TIMESTAMP}}", extracted)
            .replace("{{BUILD_TIMESTAMP}}", built)
            .replace("{{REQUESTED_BY}}", args.requested_by or NOT_STATED)
            .replace("{{ROWS_INLINED}}", num(len(packed)))
            .replace("{{COLUMNS_INLINED}}", num(len(names)))
            .replace("{{PAGE_SIZE_OPTIONS}}",
                     "".join(f'<option value="{n}"'
                             f'{" selected" if n == args.page_size else ""}>{n}</option>'
                             for n in PAGE_SIZES))
            .replace("{{NOJS_NOTE}}", html.escape(nojs_note))
            .replace("{{NOJS_HEAD}}", head_html(names, numeric, sort_col, t_head))
            .replace("{{NOJS_ROWS}}", static_rows())
            .replace("{{SORT_OPTIONS}}",
                     "".join(f'<option value="{i}"'
                             f'{" selected" if i == sort_col else ""}>{html.escape(n)}</option>'
                             for i, n in enumerate(names)))
            .replace("{{REGISTER_META}}", as_script_json(meta))
            .replace("{{REGISTER_ROWS}}", as_script_json(packed))
            .replace("{{REGISTER_STRINGS}}", as_script_json(strings))
            .replace("{{FEEDBACK_BLOCK}}", feedback))
    if "{{" in page.split("<script>")[0]:
        die("a template placeholder was left unfilled; the file would ship a visible {{...}}")

    if args.annotate:
        # The review round trip (docs/31). A register is the artefact most likely to come
        # back with "this row is wrong", so it carries the layer too. A row is named by its
        # text columns: the numeric ones are what a rebuild changes, and a name that moves
        # with a figure would make the row the reader pointed at unfindable. There is no
        # single measure under discussion in a list, so the block carries the name only
        # and read_review.py shows the row's own numbers beside it.
        keys = [n for i, n in enumerate(names) if i not in numeric] or [names[0]]
        try:
            layer_head, layer_body = review_layer.layer(
                title=args.title, file=args.out.name, built=built, rows=len(packed),
                source=source, keys=keys, measure="",
                examples=[([str(packed[i][names.index(k)]) for k in keys], "")
                          for i in rows_sorted[:review_layer.MAX_EXAMPLES]],
                table="tbl", cell_attr="data-label",
                measures=[n for i, n in enumerate(names) if i in numeric],
                lang=args.lang)
            page = review_layer.insert(page, layer_head, layer_body)
        except (ValueError, KeyError) as exc:
            die(f"--annotate: {exc}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    size = args.out.stat().st_size
    if size > MAX_BYTES:
        die(f"{args.out} is {size / 1024 / 1024:.1f} MB, above the {MAX_BYTES // 1024 // 1024} MB "
            f"this builder will write. Pre-aggregate, or split the register by audience.")

    print(f"rows          : {num(len(packed))}")
    print(f"columns       : {', '.join(names)}" + (f"  (numeric: {', '.join(numeric_names)})"
                                                   if numeric_names else ""))
    print(f"sort at open  : {names[sort_col]} {'descending' if sort_dir < 0 else 'ascending'}")
    if group_col is not None:
        print(f"grouped by    : {names[group_col]} ({len(group_counts)} group(s))")
    print(f"first page    : {len(first)} rows written into the markup (no-JS view)")
    print(f"wrote         : {args.out} ({size / 1024:.1f} KB)")
    build_size.enforce(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
