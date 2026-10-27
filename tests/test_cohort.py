#!/usr/bin/env python3
"""The cohort grid: one row per cohort, one column per period since it started.

This is the one artefact in the repo whose column axis is not in the file. It is derived,
per row, from each person's own first date, and every way of getting that wrong produces a
page that looks completely normal:

  * the cohort is taken from the last date, or from the first row the file happens to hold,
    so the same extract sorted differently tells a different story. Checked by rebuilding
    from a reversed file and comparing the grid cell for cell
  * the share is divided by everyone in the file instead of by that row's own cohort, so
    every cell is small and the picture says nothing. Checked by re-deriving every percent
  * a cell that cannot exist yet is drawn as 0, which turns "not yet" into "nobody came
    back". Checked by re-deriving which cells are possible, and by a mutation that fills
    them with zeros
  * one person with three visits in a month counts three times. Checked with a fixture that
    holds exactly that
  * the shade and the number disagree. Every band is re-derived from the share the page
    itself prints, and every cell's ink is measured against its own fill at 4.5:1, because
    verify_a11y does not catch white-on-pale table text
  * a cohort too small to speak about is drawn with the same colour as a finding. Cohorts
    under --min-cohort must be named with their sizes instead

Eleven groups, five mutations. Stdlib only for the arithmetic.

    python3 tests/test_cohort.py
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_cohort.py"
EXAMPLE = ROOT / "examples" / "44-cohort"
DATA = EXAMPLE / "kunder.csv"
PIN = "1792836000"          # a fixed clock: one input, one file, on any day

sys.path.insert(0, str(ROOT / "tools"))
import build_cohort as B  # noqa: E402  the ramp and the band edges, checked here

FAILURES: list[str] = []
CHECKS = 0

CELL = re.compile(
    r'<td class="future"></td>'
    r'|<td style="background:(#[0-9a-f]{3}(?:[0-9a-f]{3})?);color:(#[0-9a-f]{3}(?:[0-9a-f]{3})?)">'
    r'([\d,\s\u00a0]+?)<span class="pc">([\d,\s\u00a0]+?)\s?%</span></td>')
ROW = re.compile(r'<tr><th scope="row">(.*?)<span class="sz">(.*?)</span></th>(.*?)</tr>', re.S)


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


# ------------------------------------------------------------------------------- helpers
def run(data: pathlib.Path, out: pathlib.Path, *extra: str,
        tools: pathlib.Path | None = None, lang: str = "nb") -> subprocess.CompletedProcess:
    builder = (tools / "build_cohort.py") if tools else BUILDER
    args = [sys.executable, str(builder), "--data", str(data),
            "--id", "Kunde", "--date", "Dato", "--period", "month",
            "--title", "Hvor mange blir med videre",
            "--source", "Syntetisk eksempeldata (kunder.csv)",
            "--requested-by", "Kundeservice", "--lang", lang, "--out", str(out), *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env)


def scratch(root: pathlib.Path, old: str, new: str) -> pathlib.Path:
    """A copy of tools/ and templates/ a mutation can break without touching the repo."""
    tools = root / "tools"
    tools.mkdir(parents=True)
    for name in ("build_cohort.py", "build_size.py", "build_stamp.py", "feedback_link.py",
                 "i18n.py", "tun_core.py", "tun_tokens.py"):
        shutil.copy2(ROOT / "tools" / name, tools / name)
    # tun_tokens resolves the token files from its own location, so the scratch tree needs them:
    # the template carries {{TOKEN_CSS}} and the builder cannot produce a page without the seam.
    shutil.copytree(ROOT / "tools" / "tokens", tools / "tokens")
    shutil.copytree(ROOT / "templates", root / "templates")
    target = tools / "build_cohort.py"
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"the mutation does not apply once: {text.count(old)} x {old[:70]!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")
    return tools


def number(text: str) -> int:
    return int(re.sub(r"[^\d]", "", text))


def grid_of(html: str) -> list[dict]:
    """[(label, size, [cell or None])] in page order, cells read from the markup."""
    body = html.split("<tbody>")[1].split("</tbody>")[0]
    rows = []
    for label, size, rest in ROW.findall(body):
        cells = []
        tagged = rest.count("<td")
        for fill, ink, count, pct in CELL.findall(rest):
            cells.append(None if not fill and not ink
                         else {"fill": fill, "ink": ink,
                               "count": number(count), "pct": number(pct)})
        if len(cells) != tagged:
            raise SystemExit(f"row {label!r} holds {tagged} cells and this parser understood "
                             f"{len(cells)}: a cell shape it does not know would make every "
                             f"check below quietly pass")
        rows.append({"label": label, "size": number(size), "cells": cells})
    return rows


def own_grid(path: pathlib.Path, min_cohort: int = 5,
             max_periods: int = 12) -> tuple[list[dict], int]:
    """The grid this suite derives from the extract itself, with no help from the builder."""
    text = path.read_text(encoding="utf-8-sig")
    lines = [line for line in text.splitlines() if line.strip()]
    header = lines[0].split(";")
    id_at, date_at = header.index("Kunde"), header.index("Dato")
    seen: dict[str, set[int]] = {}
    for line in lines[1:]:
        parts = line.split(";")
        person = parts[id_at].strip()
        year, month = parts[date_at].strip().split("-")[0:2]
        seen.setdefault(person, set()).add(int(year) * 12 + int(month) - 1)

    groups: dict[int, dict[int, int]] = {}
    for periods in seen.values():
        first = min(periods)
        bucket = groups.setdefault(first, {})
        for offset in sorted(periods):
            k = offset - first
            if 0 <= k < max_periods:
                bucket[k] = bucket.get(k, 0) + 1
    last = max(max(periods) for periods in seen.values())
    rows = [{"index": first, "label": f"{first // 12:04d}-{first % 12 + 1:02d}",
             "size": groups[first][0], "cells": groups[first]} for first in sorted(groups)]
    drawn = [r for r in rows if r["size"] >= min_cohort]
    periods = min(max_periods, last - min(r["index"] for r in drawn) + 1)
    return drawn, periods


def pct_of(count: int, size: int) -> int:
    """Round half up, computed here from the exact fraction rather than the builder's form."""
    return int(Fraction(count * 100, size) + Fraction(1, 2))


def channel(value: int) -> float:
    value /= 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def luminance(colour: str) -> float:
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def csv_of(path: pathlib.Path, lines: list[str]) -> pathlib.Path:
    path.write_text("Kunde;Dato\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------------- main
def main() -> int:
    work = pathlib.Path(tempfile.mkdtemp(prefix="cohort-"))
    try:
        raw = DATA.read_text(encoding="utf-8-sig").splitlines()
        body = [line for line in raw[1:] if line.strip()]
        people: dict[str, set[int]] = {}
        for line in body:
            person, date = line.split(";")
            year, month = date.split("-")[0:2]
            people.setdefault(person, set()).add(int(year) * 12 + int(month) - 1)
        chk(len(people) > 100, "the example holds enough people to have cohorts",
            f"{len(people)}")

        out = work / "main.html"
        done = run(DATA, out)
        chk(done.returncode == 0, "the example builds", (done.stderr or "")[-300:])
        page = out.read_text(encoding="utf-8")
        rows = grid_of(page)
        own, periods = own_grid(DATA)

        print("\n1. every number is this suite's own derivation of the extract")
        chk([r["label"] for r in rows] == [r["label"] for r in own],
            "the drawn cohorts are the cohorts the suite finds",
            f"{[r['label'] for r in rows]} vs {[r['label'] for r in own]}")
        bad = []
        for mine, theirs in zip(rows, own):
            if mine["size"] != theirs["size"]:
                bad.append(f"{mine['label']} size {mine['size']} != {theirs['size']}")
                continue
            for k in range(periods):
                mine_cell = mine["cells"][k]
                want = theirs["cells"].get(k)
                if want is None:
                    continue
                if mine_cell is None or mine_cell["count"] != want:
                    bad.append(f"{mine['label']} +{k} {mine_cell} != {want}")
                elif mine_cell["pct"] != pct_of(want, theirs["size"]):
                    bad.append(f"{mine['label']} +{k} pct {mine_cell['pct']} "
                               f"!= {pct_of(want, theirs['size'])}")
        chk(not bad, "every count and every share matches a re-derivation", bad[:3])

        print("\n2. column +0 is the cohort size, by definition")
        wrong = [r["label"] for r in rows
                 if r["cells"] and (r["cells"][0] is None or r["cells"][0]["count"] != r["size"])]
        chk(not wrong, "every drawn cohort has its own size in +0", wrong[:3])
        chk(all(r["cells"][0] and r["cells"][0]["pct"] == 100 for r in rows),
            "+0 is 100 % on every row")

        print("\n3. a cell that cannot exist yet is hatched, not zero")
        wrong = []
        for mine, theirs in zip(rows, own):
            for k in range(len(mine["cells"])):
                possible = k in theirs["cells"]
                cell = mine["cells"][k]
                if possible and cell is None:
                    wrong.append(f"{mine['label']} +{k} missing")
                if not possible and cell is not None:
                    wrong.append(f"{mine['label']} +{k} drawn as {cell['count']}")
        chk(not wrong, "the drawn cells are exactly the possible ones", wrong[:3])
        chk(page.count('<td class="future"></td>') > 0,
            "and the page hatches the ones it cannot know")
        chk("band_future" not in page and "Ikke mulig" in page,
            "the hatch has its own legend entry")

        print("\n4. one person in one period counts once")
        twice = csv_of(work / "twice.csv", [
            "A;2026-01-05", "A;2026-01-06", "A;2026-01-31", "A;2026-02-02",
            "B;2026-01-09", "B;2026-02-11", "B;2026-02-12", "C;2026-01-10",
            "C;2026-01-11", "C;2026-03-01", "D;2026-01-12", "E;2026-01-13"])
        two_out = work / "twice.html"
        done = run(twice, two_out, "--min-cohort", "1")
        chk(done.returncode == 0, "a file with repeat visits builds", (done.stderr or "")[-200:])
        two = grid_of(two_out.read_text(encoding="utf-8"))
        january = two[0]
        chk(january["size"] == 5, "the January cohort holds five people", str(january["size"]))
        chk(january["cells"][0]["count"] == 5, "+0 counts five, not ten rows",
            str(january["cells"][0]["count"]))
        chk(january["cells"][1]["count"] == 2,
            "and February counts two people, not three visits",
            str(january["cells"][1]["count"]))
        chk(january["cells"][2]["count"] == 1, "March counts the one person who returned",
            str(january["cells"][2]["count"]))

        print("\n5. the cohort is a derivation, not the file's row order")
        flipped = csv_of(work / "flipped.csv", list(reversed(body)))
        flip_out = work / "flipped.html"
        done = run(flipped, flip_out)
        chk(done.returncode == 0, "the reversed file builds", (done.stderr or "")[-200:])
        chk(grid_of(flip_out.read_text(encoding="utf-8")) == rows,
            "a reversed extract gives the same grid, cell for cell")

        print("\n6. the shade carries the share, on stated bands")
        light = []
        for fill in B.RAMP:
            light.append(luminance("#%02x%02x%02x" % fill))
        chk(all(a > b for a, b in zip(light, light[1:])),
            "the ramp gets strictly darker", f"{[round(v, 4) for v in light]}")
        chk(len({B.band_of(share) for share in range(0, 101)}) == 5,
            "all five bands are reachable between 0 and 100 %")
        wrong = []
        for row in rows:
            for k, cell in enumerate(row["cells"]):
                if cell is None:
                    continue
                want = "#%02x%02x%02x" % B.RAMP[B.band_of(cell["pct"])]
                if cell["fill"] != want:
                    wrong.append(f"{row['label']} +{k} {cell['pct']}% {cell['fill']} != {want}")
        chk(not wrong, "each cell's shade is the band its printed share falls in", wrong[:3])

        print("\n7. every figure is readable against its own fill")
        worst = (99.0, "")
        for row in rows:
            for k, cell in enumerate(row["cells"]):
                if cell is None:
                    continue
                ratio = contrast(cell["ink"], cell["fill"])
                if ratio < worst[0]:
                    worst = (ratio, f"{row['label']} +{k} {cell['ink']} on {cell['fill']}")
        chk(worst[0] >= 4.5, "every cell reaches 4.5:1", f"{worst[0]:.2f}:1 {worst[1]}")

        print("\n8. a cohort too small to speak about is named, not drawn")
        big = work / "big.html"
        done = run(DATA, big, "--min-cohort", "60")
        chk(done.returncode == 0, "a high threshold still builds", (done.stderr or "")[-200:])
        big_page = big.read_text(encoding="utf-8")
        kept = grid_of(big_page)
        chk(all(row["size"] >= 60 for row in kept), "every drawn cohort clears the threshold",
            str([r["size"] for r in kept]))
        chk(len(kept) < len(rows), "and the small ones are gone from the grid")
        hidden = [r["label"] for r in rows if r["label"] not in {k["label"] for k in kept}]
        chk(all(label in big_page for label in hidden),
            "the hidden cohorts are still named with their sizes", str(hidden[:3]))

        print("\n9. refusals name what to fix")
        bad_date = csv_of(work / "baddate.csv", ["A;05.01.2026", "B;2026-01-02"])
        done = run(bad_date, work / "x.html", "--min-cohort", "1")
        chk(done.returncode != 0 and "YYYY-MM-DD" in done.stderr,
            "a date it cannot read stops the build", (done.stderr or "")[-160:])
        done = subprocess.run([sys.executable, str(BUILDER), "--data", str(DATA),
                               "--id", "FinnesIkke", "--date", "Dato", "--title", "x",
                               "--out", str(work / "y.html")],
                              capture_output=True, text=True, cwd=ROOT)
        chk(done.returncode != 0 and "FinnesIkke" in done.stderr,
            "an --id that is not a column names the column", (done.stderr or "")[-160:])
        done = run(DATA, work / "z.html", "--min-cohort", "100000")
        chk(done.returncode != 0 and "largest holds" in done.stderr,
            "a threshold above every cohort says how big the largest is",
            (done.stderr or "")[-200:])
        done = run(DATA, work / "w.html", "--max-periods", "999")
        chk(done.returncode != 0 and "--max-periods" in done.stderr,
            "--max-periods outside its range is refused", (done.stderr or "")[-160:])
        week = csv_of(work / "week.csv", ["A;2026-01", "B;2026-01-05"])
        done = run(week, work / "v.html", "--period", "week")
        chk(done.returncode != 0 and "full date" in done.stderr,
            "a week period refuses a month-only date", (done.stderr or "")[-200:])

        print("\n10. no script, and the English page is English")
        chk("<script" not in page.lower(), "the page carries no script")
        en_out = work / "en.html"
        done = run(DATA, en_out, lang="en")
        en = en_out.read_text(encoding="utf-8")
        chk(done.returncode == 0, "the English build runs", (done.stderr or "")[-300:])
        chk('<html lang="en">' in en, "the page declares its language")
        for word in ("Kohort", "personer", "Bygget", "Ikke mulig", "Slik er"):
            chk(word not in en, f"and not the Norwegian {word!r}")

        print("\n11. the committed example is the builder's own output")
        fresh = work / "fresh.html"
        run(DATA, fresh)
        chk(fresh.read_bytes() == (EXAMPLE / "kohort.html").read_bytes(),
            "a pinned rebuild equals the committed file byte for byte")

        print("\n12. the mutations")
        # 1. the cohort taken from the last period instead of the first.
        one = work / "m1"
        one.mkdir()
        tools = scratch(one, "        first = min(periods)", "        first = max(periods)")
        out1 = work / "m1.html"
        done = run(DATA, out1, tools=tools)
        chk(done.returncode == 0, "the last-period mutation still builds",
            (done.stderr or "")[-260:])
        m1 = {r["label"]: r for r in grid_of(out1.read_text(encoding="utf-8"))}
        mine = {r["label"]: r for r in rows}
        chk(m1.get(own[0]["label"], {}).get("cells") != mine[own[0]["label"]]["cells"],
            "and it changes the grid, so check 1 sees it")

        # 2. the share divided by twice the cohort, which every percent check must catch.
        two = work / "m2"
        two.mkdir()
        tools = scratch(two, 'percent_text(share_pct(count, row["size"]), lang)',
                        'percent_text(share_pct(count, row["size"] * 2), lang)')
        out2 = work / "m2.html"
        done = run(DATA, out2, tools=tools)
        chk(done.returncode == 0, "the wrong-denominator mutation still builds",
            (done.stderr or "")[-260:])
        m2 = grid_of(out2.read_text(encoding="utf-8"))
        chk(any(cell and cell["pct"] != pct_of(cell["count"], row["size"])
                for row, m in zip(rows, m2) for cell in m["cells"]),
            "and it prints a share the re-derivation rejects")

        # 3. the impossible cells drawn as zeros, which turns "not yet" into "nobody".
        three = work / "m3"
        three.mkdir()
        tools = scratch(three, """                cells.append('<td class="future"></td>')""",
                        """                cells.append('<td style="background:#eee;color:#000">0"""
                        """<span class="pc">0 %</span></td>')""")
        out3 = work / "m3.html"
        done = run(DATA, out3, tools=tools)
        chk(done.returncode == 0, "the zeroed-future mutation still builds",
            (done.stderr or "")[-260:])
        m3 = out3.read_text(encoding="utf-8")
        chk(page.count('<td class="future"></td>') > 0
            and m3.count('<td class="future"></td>') == 0
            and m3.count("<td") == page.count("<td"),
            "and it fills the hatched cells with zeros, never one cell fewer",
            f"{m3.count('<td class=\"future\"></td>')} hatched, {m3.count('<td')} cells")

        # 4. rows counted instead of people.
        four = work / "m4"
        four.mkdir()
        tools = scratch(four, """            if 0 <= offset < max_periods:
                counts[offset] = counts.get(offset, 0) + 1""",
                        """            if 0 <= offset < max_periods:
                counts[offset] = counts.get(offset, 0) + 1""".replace(
                            "counts.get(offset, 0) + 1", "counts.get(offset, 0) + 2"))
        out4 = work / "m4.html"
        done = run(twice, out4, "--min-cohort", "1", tools=tools)
        chk(done.returncode == 0, "the double-count mutation still builds",
            (done.stderr or "")[-260:])
        m4 = grid_of(out4.read_text(encoding="utf-8"))
        chk(m4[0]["cells"][1]["count"] == 4,
            "and a cohort of five reports four returners instead of two",
            str(m4[0]["cells"][1]["count"]))

        # 5. dark ink on every cell, which the contrast measurement must catch.
        five = work / "m5"
        five.mkdir()
        tools = scratch(five, '    return hexa(INK) if contrast(fill, INK) >= contrast(fill, WHITE) '
                              'else "#ffffff"', "    return hexa(INK)")
        out5 = work / "m5.html"
        done = run(DATA, out5, tools=tools)
        chk(done.returncode == 0, "the dark-ink mutation still builds",
            (done.stderr or "")[-260:])
        m5 = grid_of(out5.read_text(encoding="utf-8"))
        worst5 = min(contrast(cell["ink"], cell["fill"])
                     for row in m5 for cell in row["cells"] if cell)
        chk(worst5 < 4.5, "and it fails the contrast check", f"{worst5:.2f}:1")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failed of {CHECKS} checks:")
        for name in FAILURES:
            print(f"  - {name}")
        return 1
    print(f"{CHECKS} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
