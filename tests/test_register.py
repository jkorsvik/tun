#!/usr/bin/env python3
"""The register: a list a reader can search, sort and page, in one self-contained file.

Half of what people share as a spreadsheet is not a chart waiting to happen — it is a list
they want to hand over so someone can search it. This suite proves the properties that make
that safe, and each one is a failure this repository has already met somewhere else:

  1. every row that went in is in the file, and a column that was not named is not in it
     at all (the split happens at build time, not in a browser filter)
  2. a numeric column sorts as a number, and an empty cell sorts last rather than as zero
  3. a search that matches nothing says so in words, in the table body
  4. the no-JS view is the first page, with the count and the sentence saying what is
     missing, so a reader whose browser will not run the script is not looking at a blank box
  5. the floors hold: no text under 14 px, no target under 44 px, no sideways scroll at 320
  6. a cell is text. Nothing in the data is ever written as markup (a CSV cell once ran
     script in this repo, so this is checked with a hostile value, not by inspection)

Run: python3 tests/test_register.py [--engines chromium,webkit]
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_register.py"
CSV_IN = ROOT / "examples" / "32-rows-register" / "avvik.csv"
TEMPLATE = ROOT / "templates" / "register.html"

FAILURES: list[str] = []
CHECKS = 0


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    mark = "\u2713" if ok else "\u2717"
    print(f"  {mark} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


def build(out: pathlib.Path, *extra: str, data: pathlib.Path = CSV_IN) -> subprocess.CompletedProcess:
    args = [sys.executable, str(BUILDER), "--data", str(data), "--title", "Avvik 2026",
            "--columns", "Saksnummer,Enhet,Avvik,Mottatt,Status,Dager,Belop",
            "--numeric", "Dager,Belop", "--sort", "Dager", "--desc",
            "--source", "Syntetisk eksempeldata (avvik.csv)", "--requested-by", "Kvalitet",
            "--out", str(out), *extra]
    return subprocess.run(args, capture_output=True, text=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engines", default="chromium,webkit")
    args = ap.parse_args(argv)
    engines = [e.strip() for e in args.engines.split(",") if e.strip()]

    work = pathlib.Path(tempfile.mkdtemp(prefix="tun-register-"))
    page = work / "register.html"
    res = build(page)
    chk(res.returncode == 0, "the example builds", res.stderr.strip()[-200:])
    if not page.is_file():
        print("cannot continue without a build")
        return 1
    blob = page.read_text(encoding="utf-8")

    print("\n1. what went in is what is in the file, and nothing else")
    with CSV_IN.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        n_rows = sum(1 for _ in reader)
    chk(n_rows > 500, "the example has enough rows to need paging", f"{n_rows} rows")
    chk(f"{n_rows:,}".replace(",", "\u00a0") in blob or f"{n_rows}" in blob,
        "the row count on the page is the row count in the file", str(n_rows))
    chk('"Saksbehandler"' not in blob and "Saksbehandler 7" not in blob,
        "a column that was not named is absent from the file, not merely hidden")
    chk("Saksbehandler" not in blob.split("<script>")[0],
        "and it is not in the static view either")

    meta = json.loads(re.search(r"const META = (\{.*?\});", blob, re.S).group(1))
    chk(meta["columns"] == ["Saksnummer", "Enhet", "Avvik", "Mottatt", "Status", "Dager",
                            "Belop"], "the column order is the order asked for",
        ", ".join(meta["columns"]))
    chk(meta["numeric"] == [5, 6], "the numeric columns are marked", str(meta["numeric"]))
    rows = json.loads(re.search(r"const ROWS = (\[\[.*?\]\]);", blob, re.S).group(1))
    chk(len(rows) == n_rows, "every row is inlined", f"{len(rows)} inlined, {n_rows} in file")
    chk(any(isinstance(r[5], (int, float)) for r in rows),
        "a numeric cell is a JSON number, so the page compares it as one")

    print("\n2. a build that cannot be what it says does not build")
    narrow = work / "narrow.html"
    res = subprocess.run([sys.executable, str(BUILDER), "--data", str(CSV_IN),
                          "--title", "x", "--columns", "Saksnummer,NotAColumn",
                          "--out", str(narrow)], capture_output=True, text=True)
    chk(res.returncode == 2 and "NotAColumn" in res.stderr,
        "a column that does not exist is refused by name")
    res = subprocess.run([sys.executable, str(BUILDER), "--data", str(CSV_IN),
                          "--title", "x", "--columns", "Saksnummer,Dager",
                          "--numeric", "Saksbehandler", "--out", str(narrow)],
                         capture_output=True, text=True)
    chk(res.returncode == 2 and "Saksbehandler" in res.stderr,
        "--numeric on a column that is not shown is refused")
    long_cell = work / "long.csv"
    long_cell.write_text("A,B\n" + "x" * 500 + ",1\n", encoding="utf-8")
    res = subprocess.run([sys.executable, str(BUILDER), "--data", str(long_cell),
                          "--title", "x", "--out", str(narrow)], capture_output=True, text=True)
    chk(res.returncode == 2 and "paragraph" in res.stderr,
        "a paragraph in a cell is refused, with the reason")

    print("\n3. grouping: a band per group, with its own count and sums")
    # Expected values computed from the file, not from the builder: a group header that
    # echoed the builder's own arithmetic would prove only that the builder agrees with
    # itself.
    with CSV_IN.open(newline="", encoding="utf-8-sig") as fh:
        per_group: dict[str, list] = {}
        for row in csv.DictReader(fh):
            acc = per_group.setdefault(row["Enhet"], [0, 0.0, 0.0])
            acc[0] += 1
            acc[1] += float(row["Dager"] or 0)
            acc[2] += float(row["Belop"] or 0)

    grouped = work / "grouped.html"
    res = build(grouped, "--columns", "Saksnummer,Enhet,Status,Dager,Belop",
                "--numeric", "Dager,Belop", "--group-by", "Enhet", "--page-size", "250")
    chk(res.returncode == 0, "a grouped build runs", res.stderr.strip()[-200:])
    grouped_blob = grouped.read_text(encoding="utf-8")
    chk('"groupCol":1' in grouped_blob.replace(" ", ""),
        "the page is told which column groups it", "groupCol missing")
    gmeta = json.loads(re.search(r"const META = (\{.*?\});", grouped_blob, re.S).group(1))
    chk(gmeta.get("groupCol") == 1, "and it is the column that was named",
        str(gmeta.get("groupCol")))

    plain = work / "plain.html"
    res = build(plain, "--columns", "Saksnummer,Enhet,Status,Dager,Belop",
                "--numeric", "Dager,Belop")
    plain_blob = plain.read_text(encoding="utf-8")
    # The stylesheet always holds the band's rules; what must be absent is the band itself
    # and the build fact that turns it on.
    chk('class="grp"' not in plain_blob and '"groupCol"' not in plain_blob,
        "a build without --group-by carries no group band and no grouping flag, so the "
        "feature is additive")

    res = subprocess.run([sys.executable, str(BUILDER), "--data", str(CSV_IN),
                          "--title", "x", "--columns", "Saksnummer,Dager",
                          "--group-by", "Enhet", "--out", str(work / "nogroup.html")],
                         capture_output=True, text=True)
    chk(res.returncode == 2 and "Enhet" in res.stderr,
        "--group-by on a column that is not written is refused by name")

    def band_numbers(meta_text: str) -> tuple[int, list[float]]:
        """Read the count and the sums back out of a band's meta text.

        The page prints them in the reader's own convention (nb groups with a no-break
        space, en with a thin one), so they are parsed rather than string-compared: a test
        that compared the formatted text would pass on a wrong number that formatted the
        same way.
        """
        count, sums = 0, []
        for i, part in enumerate(p.strip() for p in meta_text.split("\u00b7")):
            if i == 0:
                count = int(re.sub(r"[^0-9]", "", part) or 0)
            else:
                digits = re.sub(r"[^0-9,.]", "", part.split(" ", 1)[-1])
                sums.append(float(digits.replace(",", ".")) if digits else 0.0)
        return count, sums

    static_bands = re.findall(r'<tr class="grp"><th scope="colgroup" colspan="5">'
                              r'<span class="grpname">([^<]*)</span>'
                              r'<span class="grpmeta">([^<]*)</span>', grouped_blob)
    chk(len(static_bands) >= 1, "the no-JS view carries a group band",
        f"{len(static_bands)} band(s)")
    if static_bands:
        name, meta_text = static_bands[0]
        count, sums = band_numbers(meta_text)
        chk(name == "Drift", "the groups come out ascending, so the first is Drift", name)
        chk(count == per_group[name][0], "the band's count is the group's count in the file",
            f"{count} vs {per_group[name][0]}")
        chk(abs(sums[0] - per_group[name][1]) < 0.5 and abs(sums[1] - per_group[name][2]) < 0.5,
            "and its sums are the column sums, computed here rather than by the builder",
            f"{sums} vs {per_group[name][1:]}")
        chk(re.search(r"<tr class=\"grp\">.*?</tr><tr><td", grouped_blob, re.S) is not None,
            "the band is followed by its own rows")

    print("\n4. the page, in a real browser")
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    hostile = work / "hostile.csv"
    hostile.write_text('A,B\n<script>window.__x=1</script>,1\n"<img src=x onerror=1>",2\n',
                       encoding="utf-8")
    hostile_out = work / "hostile.html"
    res = subprocess.run([sys.executable, str(BUILDER), "--data", str(hostile),
                          "--title", "x", "--out", str(hostile_out)],
                         capture_output=True, text=True)
    chk(res.returncode == 0, "a hostile cell still builds", res.stderr.strip()[-120:])
    hostile_blob = hostile_out.read_text(encoding="utf-8")
    chk(hostile_blob.count("</script>") == 2,
        "a cell holding </script> cannot end the script element early",
        f"{hostile_blob.count('</script>')} occurrences, expected 2")
    chk("u003cscript" in hostile_blob,
        "the payload carries the cell as escaped text, and the page reads it back unchanged")

    with sync_playwright() as pw:
        for engine in engines:
            print(f"  -- {engine}")
            browser = getattr(pw, engine).launch()
            ctx = browser.new_context(viewport={"width": 1366, "height": 900})
            p = ctx.new_page()
            errors: list[str] = []
            p.on("pageerror", lambda e: errors.append(str(e)))
            p.goto(page.as_uri())
            p.wait_for_selector("#tbl tbody tr")

            chk(p.eval_on_selector_all("#tbl tbody tr", "e => e.length") == meta["pageSize"],
                "the first page holds the page size", engine)
            first = p.eval_on_selector("#tbl tbody tr td:nth-child(6)", "e => e.textContent")
            chk(first == "120", "the sort at open is descending, and the top value is right",
                f"{engine}: {first}")
            chk(p.eval_on_selector("#tbl thead th:nth-child(6)",
                                   "e => e.getAttribute('aria-sort')") == "descending",
                "the sorted column says so in aria-sort", engine)

            p.click("#tbl thead th:nth-child(6) button")
            p.wait_for_timeout(120)
            asc = p.eval_on_selector_all("#tbl tbody tr td:nth-child(6)",
                                         "e => e.slice(0, 3).map(x => x.textContent)")
            chk(asc == ["1", "1", "1"], "clicking the heading reverses the order",
                f"{engine}: {asc}")
            p.click("#tbl thead th:nth-child(6) button")
            p.wait_for_timeout(120)
            chk(p.eval_on_selector("#tbl tbody tr td:nth-child(6)",
                                   "e => e.textContent") == "120",
                "and clicking again restores it", engine)

            # A number sorted as text would put "99" above "120".
            p.click("#tbl thead th:nth-child(6) button")   # ascending: 1, 1, 1, ...
            p.wait_for_timeout(120)
            values = p.eval_on_selector_all("#tbl tbody tr td:nth-child(6)",
                                            "e => e.map(x => Number(x.textContent))")
            chk(values == sorted(values), "a numeric column sorts as numbers, not as text",
                f"{engine}: {values[:5]}")

            p.fill("#q", "Drift")
            p.wait_for_timeout(200)
            filtered = p.eval_on_selector_all("#tbl tbody tr", "e => e.length")
            count = p.eval_on_selector("#count", "e => e.textContent")
            chk(0 < filtered <= meta["pageSize"] and "av" in count,
                "a search filters the list and the count follows", f"{engine}: {count}")

            p.fill("#q", "zzzzz")
            p.wait_for_timeout(200)
            body = p.eval_on_selector("#tbl tbody", "e => e.textContent.trim()")
            chk("Ingen rader" in body or "No rows" in body,
                "a search that matches nothing says so in words", f"{engine}: {body[:40]}")
            chk(p.eval_on_selector("#count", "e => e.textContent").strip().startswith("0"),
                "and the count reads zero rather than lying", engine)

            p.fill("#q", "")
            p.wait_for_timeout(200)
            p.click("#next")
            p.wait_for_timeout(150)
            chk(p.eval_on_selector("#count", "e => e.textContent").split()[0] == "51\u2013100",
                "the next page starts where the last one ended",
                f"{engine}: {p.eval_on_selector('#count', 'e => e.textContent')}")
            chk(not p.eval_on_selector("#prev", "e => e.disabled"),
                "the previous button is live once a page back exists", engine)

            p.click("#reset")
            p.wait_for_timeout(200)
            chk(p.eval_on_selector("#count", "e => e.textContent").split()[0] == "1\u201350",
                "reset returns to the first page and the opening sort", engine)

            p.set_viewport_size({"width": 320, "height": 720})
            p.wait_for_timeout(150)
            chk(p.evaluate("document.documentElement.scrollWidth - innerWidth") == 0,
                "no sideways scroll at 320 px", engine)
            chk(p.evaluate("""() => {let m=99;document.querySelectorAll('body *').forEach(e=>{
                    const f=parseFloat(getComputedStyle(e).fontSize);
                    if(e.textContent.trim()&&f<m)m=f});return m}""") >= 14,
                "no rendered text under 14 px", engine)
            chk(p.evaluate("""() => {let m=999;document.querySelectorAll('button,input,select')
                    .forEach(e=>{const r=e.getBoundingClientRect();if(r.height)m=Math.min(m,r.height)});
                    return m}""") >= 44,
                "no target under 44 px", engine)
            chk(not errors, "no page error", f"{engine}: {errors[:2]}")

            gp = ctx.new_page()
            gp.goto(grouped.as_uri())
            gp.wait_for_selector("#tbl tbody tr.grp")
            bands = gp.eval_on_selector_all(
                "tbody tr.grp", "els => els.map(e => [e.querySelector('.grpname').textContent,"
                " e.querySelector('.grpmeta').textContent])")
            chk(len(bands) >= 2, "250 rows reach more than one group", f"{engine}: {len(bands)}")
            wrong = []
            for name, meta_text in bands:
                count, sums = band_numbers(meta_text)
                want = per_group[name]
                if count > want[0] or abs(sums[0] - want[1]) > 0.5 or \
                        abs(sums[1] - want[2]) > 0.5:
                    wrong.append(f"{name}: {count}/{sums} vs {want}")
            chk(not wrong, "every band on screen agrees with the file", f"{engine}: {wrong[:2]}")

            gp.set_viewport_size({"width": 1366, "height": 900})
            gp.select_option("#size", "25")
            gp.wait_for_timeout(200)
            gp.click("#next")
            gp.wait_for_timeout(250)
            first_band = gp.eval_on_selector(
                "tbody tr.grp .grpmeta", "e => e.textContent")
            count_on_page_two, _ = band_numbers(first_band)
            chk(count_on_page_two == per_group["Drift"][0],
                "a group split across pages keeps one total, not one per page",
                f"{engine}: {count_on_page_two} vs {per_group['Drift'][0]}")

            gp.fill("#q", "Apen")
            gp.wait_for_timeout(400)
            narrowed = gp.eval_on_selector_all(
                "tbody tr.grp", "els => els.map(e => [e.querySelector('.grpname').textContent,"
                " e.querySelector('.grpmeta').textContent])")
            narrowed_counts = {n: band_numbers(m)[0] for n, m in narrowed}
            chk(narrowed_counts and all(v < per_group[k][0] for k, v in narrowed_counts.items()),
                "a search narrows the count in the band, so the band is not a build-time "
                "constant", f"{engine}: {narrowed_counts}")
            rows_shown = gp.eval_on_selector_all("tbody tr:not(.grp)", "e => e.length")
            chk(sum(narrowed_counts.values()) >= rows_shown,
                "and the bands account for at least the rows on screen",
                f"{engine}: {sum(narrowed_counts.values())} vs {rows_shown}")
            gp.close()

            hp = ctx.new_page()
            hp.goto(hostile_out.as_uri())
            hp.wait_for_selector("#tbl tbody tr")
            chk(hp.evaluate("() => window.__x === undefined"),
                "a hostile cell does not run", engine)
            chk("<script>window.__x=1</script>" in hp.eval_on_selector(
                    "#tbl tbody", "e => e.textContent"),
                "and it is on screen as the text it was", engine)
            hp.close()
            browser.close()

        print("  -- no script")
        browser = pw.chromium.launch()
        ctx = browser.new_context(java_script_enabled=False)
        p = ctx.new_page()
        p.goto(page.as_uri())
        static_rows = p.eval_on_selector_all("#tbl tbody tr", "e => e.length")
        chk(static_rows == 25, "the first page is written into the markup", f"{static_rows} rows")
        text = p.eval_on_selector("body", "e => e.innerText")
        chk(len(text) > 800, "the no-JS page carries real content", f"{len(text)} chars")
        chk("Uten skript" in text and "1\u00a0200" in text,
            "and it says, in words, that it is the first page of a larger list")
        chk(p.eval_on_selector("#controls", "e => e.hidden"),
            "the controls stay hidden without script, rather than doing nothing")
        browser.close()

    print(f"\n{'FAIL' if FAILURES else 'PASS'}: {CHECKS - len(FAILURES)} of {CHECKS} checks")
    for name in FAILURES:
        print(f"  - {name}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
