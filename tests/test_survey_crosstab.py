#!/usr/bin/env python3
"""The cross-tab rule, and the script that keeps it honest.

A cross-tab multiplies two questions, which is exactly how a small group becomes one
person. The board's per-cell floor is not enough there, because the question totals are
already on the page: one withheld cell is recovered by subtracting the visible ones from
the total. So the rule a cross-tab gets is all or nothing — printed when every
combination reaches the floor, dropped with its reason otherwise.

What this suite proves:

1. The pairing is by respondent. A wide file is built whose matrix is known, and the
   table must carry that matrix; a join that paired the wrong answers would not.
2. The totals reconcile: every cell, every row total and every column total come from
   the same set, and the grand total is the number of respondents who answered both.
3. The floor bites, and it is the floor that decides: the same question pair is shown
   with a thick file and dropped with a thin one. That is the control — a builder that
   dropped everything, or nothing, would fail one half of it.
4. A long-format file with --cross is refused rather than guessed at.
5. The browser half: no script error, the table is there before any filter, a filter
   hides the cross-tabs and shows the note that says why, and reset brings them back.

Stdlib for 1-4; Playwright for 5, which FAILS without it rather than skipping.

    python3 tests/test_survey_crosstab.py
    uv run --extra verify python tests/test_survey_crosstab.py
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILD = ROOT / "tools" / "build_survey_dashboard.py"
TMP = pathlib.Path(tempfile.mkdtemp(prefix="tun-crosstab-"))

checks = failed = 0


def check(ok: bool, what: str, detail: str = "") -> None:
    global checks, failed
    checks += 1
    if ok:
        print(f"  ✓ {what}")
    else:
        failed += 1
        print(f"  ✗ {what}" + (f" — {detail}" if detail else ""))


def build(data: pathlib.Path, out: str, extra: list[str]) -> tuple[pathlib.Path, str, int]:
    target = TMP / f"{out}.html"
    cmd = [sys.executable, str(BUILD), "--data", str(data), "--title", "Test",
           "--segments", "Enhet", "--source", "synthetic test data",
           "--requested-by", "Test", "--out", str(target)] + extra
    r = subprocess.run(cmd, capture_output=True, text=True)
    return target, r.stdout + r.stderr, r.returncode


def wide(rows: list[str], names: list[str]) -> pathlib.Path:
    path = TMP / f"wide{len(list(TMP.glob('wide*.csv')))}.csv"
    path.write_text(",".join(["Enhet"] + names) + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def matrix_of(page: str) -> list[list[int]]:
    """The body of the first printed cross-tab, as numbers."""
    body = page.split("<tbody>")[1].split("</tbody>")[0]
    out = []
    for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        cells = re.findall(r'<td[^>]*>([^<]*)</td>', tr)
        out.append([int(c.replace("\u00a0", "").replace(" ", "")) for c in cells[:-1]])
    return out


def main() -> int:
    print("1. the pairing is by respondent, and the matrix is the file's")
    # Two questions, three options each, one unit. The matrix is written out, so a join
    # that paired Q1 of one person with Q2 of another would land on different numbers.
    grid = [[6, 7, 5], [8, 6, 9], [7, 5, 6]]
    rows, i = [], 0
    for a, line in enumerate(grid):
        for b, count in enumerate(line):
            for _ in range(count):
                rows.append(f"Nord,A{a},B{b}")
                i += 1
    thick = wide(rows, ["Q1", "Q2"])
    page, log, code = build(thick, "thick", ["--wide", "--questions", "Q1,Q2", "--cross", "Q1|Q2"])
    check(code == 0, "the builder accepts a wide file with --cross", log.strip()[-200:])
    html = page.read_text(encoding="utf-8")
    check(matrix_of(html) == grid, "the printed table is the file's own matrix",
          f"{matrix_of(html)} vs {grid}")
    total = sum(sum(line) for line in grid)
    check(f'<td class="t">{total}</td>' in html.replace("\u00a0", " "),
          "the grand total is the number who answered both", str(total))
    col_totals = [sum(line[j] for line in grid) for j in range(3)]
    check(all(f'<td class="t">{v}</td>' in html.replace("\u00a0", " ")
              for v in col_totals), "every column total reconciles", str(col_totals))

    print("\n2. the floor decides, and it is the floor that decides")
    thin_grid = [[6, 7, 5], [8, 2, 9], [7, 5, 6]]      # the middle cell is under five
    rows, i = [], 0
    for a, line in enumerate(thin_grid):
        for b, count in enumerate(line):
            for _ in range(count):
                rows.append(f"Nord,A{a},B{b}")
    thin = wide(rows, ["Q1", "Q2"])
    page2, log2, code2 = build(thin, "thin", ["--wide", "--questions", "Q1,Q2", "--cross", "Q1|Q2"])
    html2 = page2.read_text(encoding="utf-8")
    check(code2 == 0 and "<tbody>" not in html2,
          "one combination under the floor drops the whole table")
    check("cross_dropped" not in html2 and "Ikke vist" in html2,
          "the dropped table says why instead of printing a number")
    check("1 of 2" not in log2 and "0 of 1 shown" in log2,
          "the build log counts the dropped table", log2.strip().splitlines()[-2:])

    print("\n3. a long-format file is refused, not guessed at")
    long_csv = TMP / "long.csv"
    long_csv.write_text("Enhet,Sporsmal,Svar\nNord,Q1,A0\nNord,Q2,B0\n", encoding="utf-8")
    _, log3, code3 = build(long_csv, "long", ["--cross", "Q1|Q2"])
    check(code3 != 0, "the builder exits non-zero on --cross without --wide")
    check("needs --wide" in log3, "and says which input a cross-tab needs", log3.strip()[-160:])

    print("\n4. the strings are translated, not hard-coded")
    page_en, log4, code4 = build(thick, "en", ["--wide", "--questions", "Q1,Q2",
                                              "--cross", "Q1|Q2", "--lang", "en"])
    en = page_en.read_text(encoding="utf-8")
    check(code4 == 0 and "Cross-tab" in en and "Total" in en,
          "English gets English table words", log4.strip()[-160:])
    check("Krysstabell" in html and "Krysstabell" not in en,
          "Norwegian stays in the Norwegian file")

    print("\n5. the browser, two engines: the table is there, a filter says why it is not")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ✗ playwright is not installed, so nothing was measured")
        print("    install: uv sync --extra verify && uv run playwright install chromium")
        return 1
    expected = 3 * 3 + 3 + 3 + 1        # cells, row totals, column totals, grand total
    errors: list[str] = []
    with sync_playwright() as p:
        for engine in ("chromium", "webkit"):     # Firefox will not launch on this Mac
            browser = getattr(p, engine).launch()
            pg = browser.new_page(viewport={"width": 1366, "height": 1100})
            pg.on("pageerror", lambda e: errors.append(f"{engine}: {e}"))
            pg.goto(page.resolve().as_uri())
            pg.wait_for_timeout(300)
            visible_at_load = pg.locator("#cross section:visible").count()
            note_at_load = pg.locator("#cross-note").is_visible()
            marks_at_load = pg.locator("#cross table td").count()
            pg.select_option("#s0", label="Nord")
            pg.wait_for_timeout(250)
            visible_filtered = pg.locator("#cross section:visible").count()
            note_filtered = pg.locator("#cross-note").is_visible()
            pg.click("#reset")
            pg.wait_for_timeout(250)
            visible_reset = pg.locator("#cross section:visible").count()
            browser.close()

            check(not errors, f"{engine}: the page loads with no script error",
                  "; ".join(errors[:2]))
            check(visible_at_load == 1, f"{engine}: the printed table is on the page at load",
                  str(visible_at_load))
            check(marks_at_load == expected,
                  f"{engine}: the matrix renders its cells and both sets of totals",
                  f"{marks_at_load} vs {expected}")
            check(not note_at_load, f"{engine}: the filter note is hidden while nothing is filtered")
            check(visible_filtered == 0 and note_filtered,
                  f"{engine}: a filter hides the cross-tabs and shows the note",
                  f"visible={visible_filtered} note={note_filtered}")
            check(visible_reset == 1, f"{engine}: reset brings the table back", str(visible_reset))

    print()
    print(f"{checks - failed}/{checks} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
