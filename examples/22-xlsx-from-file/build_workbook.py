#!/usr/bin/env python3
"""
build_workbook.py — writes demo-workbook.xlsx, stdlib only.

No openpyxl, no third-party library of any kind: a real .xlsx is just a ZIP archive
(`zipfile`, deflate-compressed — the same raw-deflate byte stream the browser-side
`DecompressionStream('deflate-raw')` in xlsx-from-file.html has to unpack) holding a
handful of XML parts. This script writes those parts as plain strings and zips them up,
which is the whole point: the only thing that can read this file afterwards, other than
Excel itself, is a parser that actually implements the ZIP + SpreadsheetML format — not a
wrapper around someone else's library.

Produces three sheets, on purpose exercising every cell shape the HTML parser has to
handle:
  - shared strings      (every text cell is an index into xl/sharedStrings.xml, not an
                          inline value)
  - plain numbers        (no `t` attribute on the <c> element)
  - a real Excel date    (a number serial + a style pointing at a date number format,
                          not a pre-formatted string — the honest representation)
  - an explicit empty cell (`<c r="D4"/>`, present in the row, no `<v>` child — "known to
                          be blank" is a different fact than "column skipped entirely")
  - Norwegian letters æøå (a sheet name, customer names, free-text comments)

All data is invented. No real names, organisation numbers or company data.

    python3 examples/22-xlsx-from-file/build_workbook.py
"""
from __future__ import annotations

import datetime
import pathlib
import zipfile
from xml.sax.saxutils import escape, quoteattr

HERE = pathlib.Path(__file__).parent
OUT = HERE / "demo-workbook.xlsx"

# Excel's "1900 date system" epoch. Day 1 is 1900-01-01, but Excel treats 1900 as a leap
# year (it wasn't) — a 1900s bug every spreadsheet tool still reproduces for compatibility.
# Using 1899-12-30 as day zero reproduces that bug and gives the correct serial for any
# date safely after it, which every date in this workbook is.
EXCEL_EPOCH = datetime.date(1899, 12, 30)


def excel_serial(d: datetime.date) -> int:
    return (d - EXCEL_EPOCH).days


# ---------------------------------------------------------------------------
# Synthetic content — three sheets, invented data only
# ---------------------------------------------------------------------------
# Column kinds: "s" shared string, "n" number, "d" date (datetime.date), None empty cell.
SHEETS = [
    {
        "name": "Produkter",
        "headers": ["ProduktID", "Produktnavn", "Pris", "Lagerbeholdning", "SistOppdatert"],
        "rows": [
            [1, "Kaffekopp blå", 149.9, 120, datetime.date(2024, 3, 15)],
            [2, "Notatblokk A5", 39.5, 300, datetime.date(2024, 2, 1)],
            # Lagerbeholdning deliberately missing for this row: an explicit empty cell,
            # not a zero and not a column that was never written.
            [3, "Penn sort", 12.0, None, datetime.date(2024, 1, 10)],
            [4, "Veske for bærbar PC", 899.0, 45, datetime.date(2024, 3, 1)],
            [5, "Kaffekopp rød", 149.9, 80, datetime.date(2024, 3, 15)],
        ],
    },
    {
        "name": "Ordrer",
        "headers": ["OrdreID", "Kunde", "Beløp", "Bestillingsdato"],
        "rows": [
            [1001, "Ola Nordmann", 299.8, datetime.date(2024, 3, 16)],
            [1002, "Kari Hansen", 39.5, datetime.date(2024, 3, 17)],
            [1003, "Åse Lund", 899.0, datetime.date(2024, 3, 18)],
            [1004, "Per Øverland", 161.9, datetime.date(2024, 3, 19)],
        ],
    },
    {
        # Norwegian letters in the sheet name itself, not only in cell content.
        "name": "Kommentarer æøå",
        "headers": ["Rad", "Kommentar"],
        "rows": [
            [1, "Alt i orden, ingen avvik å rapportere."],
            [2, "Husk å sjekke lagerbeholdning for penn sort – ukjent per nå."],
            [3, "Dette arket tester norske bokstaver: æ Æ ø Ø å Å."],
        ],
    },
]

DATE_STYLE_INDEX = 1  # see styles.xml below: cellXfs[1] applies numFmtId 164 (a date)
CUSTOM_DATE_NUMFMT_ID = 164
CUSTOM_DATE_FORMAT_CODE = "yyyy\\-mm\\-dd"

CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
SS_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def col_letter(idx: int) -> str:
    """0-based column index -> spreadsheet column letters (0 -> A, 25 -> Z, 26 -> AA)."""
    letters = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def build_shared_strings() -> tuple[list[str], dict[str, int]]:
    """Collect every text cell across every sheet (headers + string rows) into one
    de-duplicated table — this is what makes it a *shared* strings table rather than
    inline text, and the thing xlsx-from-file.html has to resolve indices against."""
    strings: list[str] = []
    index: dict[str, int] = {}

    def intern(value: str) -> int:
        if value not in index:
            index[value] = len(strings)
            strings.append(value)
        return index[value]

    for sheet in SHEETS:
        for header in sheet["headers"]:
            intern(header)
        for row in sheet["rows"]:
            for value in row:
                if isinstance(value, str):
                    intern(value)
    return strings, index


def cell_xml(ref: str, value, shared_index: dict[str, int]) -> str:
    if value is None:
        # Explicit empty cell: present in the row, no value, no type.
        return f'<c r="{ref}"/>'
    if isinstance(value, str):
        idx = shared_index[value]
        return f'<c r="{ref}" t="s"><v>{idx}</v></c>'
    if isinstance(value, datetime.date):
        serial = excel_serial(value)
        return f'<c r="{ref}" s="{DATE_STYLE_INDEX}"><v>{serial}</v></c>'
    # Plain number (int or float), no `t` attribute — the SpreadsheetML default.
    return f'<c r="{ref}"><v>{value}</v></c>'


def sheet_xml(sheet: dict, shared_index: dict[str, int]) -> str:
    rows_xml = []
    all_rows = [sheet["headers"]] + sheet["rows"]
    for r, row in enumerate(all_rows, start=1):
        cells = []
        for c, value in enumerate(row):
            ref = f"{col_letter(c)}{r}"
            # Header row cells are always strings; data rows use cell_xml's type sniffing.
            if r == 1:
                cells.append(cell_xml(ref, value, shared_index))
            else:
                cells.append(cell_xml(ref, value, shared_index))
        rows_xml.append(f'<row r="{r}">' + "".join(cells) + "</row>")
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{SS_NS}"><sheetData>' + "".join(rows_xml) + "</sheetData></worksheet>"
    )


def shared_strings_xml(strings: list[str]) -> str:
    items = "".join(f"<si><t xml:space=\"preserve\">{escape(s)}</t></si>" for s in strings)
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="{SS_NS}" count="{len(strings)}" uniqueCount="{len(strings)}">{items}</sst>'
    )


def workbook_xml() -> str:
    sheets = "".join(
        f'<sheet name={quoteattr(s["name"])} sheetId="{i + 1}" r:id="rId{i + 1}"/>'
        for i, s in enumerate(SHEETS)
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{SS_NS}" xmlns:r="{R_NS}"><sheets>{sheets}</sheets></workbook>'
    )


def workbook_rels_xml() -> str:
    rels = "".join(
        f'<Relationship Id="rId{i + 1}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{i + 1}.xml"/>'
        for i in range(len(SHEETS))
    )
    n = len(SHEETS)
    rels += (
        f'<Relationship Id="rId{n + 1}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
        f'Target="sharedStrings.xml"/>'
        f'<Relationship Id="rId{n + 2}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        f'Target="styles.xml"/>'
    )
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{REL_NS}">{rels}</Relationships>'


def root_rels_xml() -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{REL_NS}">'
        f'<Relationship Id="rId1" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        f'Target="xl/workbook.xml"/>'
        f'</Relationships>'
    )


def content_types_xml() -> str:
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(len(SHEETS))
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Types xmlns="{CT_NS}">'
        f'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        f'<Default Extension="xml" ContentType="application/xml"/>'
        f'<Override PartName="/xl/workbook.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f'{overrides}'
        f'<Override PartName="/xl/sharedStrings.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        f'<Override PartName="/xl/styles.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f'</Types>'
    )


def styles_xml() -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<styleSheet xmlns="{SS_NS}">'
        f'<numFmts count="1">'
        f'<numFmt numFmtId="{CUSTOM_DATE_NUMFMT_ID}" formatCode="{CUSTOM_DATE_FORMAT_CODE}"/>'
        f'</numFmts>'
        f'<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        f'<fills count="2"><fill><patternFill patternType="none"/></fill>'
        f'<fill><patternFill patternType="gray125"/></fill></fills>'
        f'<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        f'<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        f'<cellXfs count="2">'
        f'<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        f'<xf numFmtId="{CUSTOM_DATE_NUMFMT_ID}" fontId="0" fillId="0" borderId="0" xfId="0" '
        f'applyNumberFormat="1"/>'
        f'</cellXfs>'
        f'</styleSheet>'
    )


def build() -> pathlib.Path:
    strings, shared_index = build_shared_strings()

    parts: dict[str, str] = {
        "[Content_Types].xml": content_types_xml(),
        "_rels/.rels": root_rels_xml(),
        "xl/workbook.xml": workbook_xml(),
        "xl/_rels/workbook.xml.rels": workbook_rels_xml(),
        "xl/sharedStrings.xml": shared_strings_xml(strings),
        "xl/styles.xml": styles_xml(),
    }
    for i, sheet in enumerate(SHEETS, start=1):
        parts[f"xl/worksheets/sheet{i}.xml"] = sheet_xml(sheet, shared_index)

    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in parts.items():
            zf.writestr(name, content.encode("utf-8"))

    return OUT


if __name__ == "__main__":
    out = build()
    size = out.stat().st_size
    print(f"wrote {out} ({size} bytes), {len(SHEETS)} sheets:")
    for s in SHEETS:
        print(f"  - {s['name']!r}: {len(s['rows'])} data row(s) + 1 header")
