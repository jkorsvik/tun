#!/usr/bin/env python3
"""The composition page: what a total is made of, and where the mix and the level disagree.

A share is a ratio, so it can rise while the figure it describes falls. That is the trap this
artefact exists for, and it is also the reason a picture of shares is not enough on its own.
This suite checks the properties that make the page worth trusting, and each one is a way it
could be wrong:

  1. every column of shares adds up to exactly 100,0, printed and recomputed here. Rounding
     each share on its own is what breaks that, and this suite also proves the dataset is one
     where naive rounding would have broken it
  2. every printed share is within one rounding unit of its own exact share. Largest
     remainder rounds down and then hands the last units to the largest remainders, so a share
     can move by up to one unit but never further, and the column still adds up
  3. every category's level is this suite's own sum of the source rows per period, and the
     column of levels adds up to the total printed above it
  4. the drawing's bands are the shares: each band's height on the page is its own share of
     the plot, and the stack starts at the base and ends at the top of the plot
  5. the band colours are distinct, four at most, and the summed rest band is neutral: a
     composition is not a verdict, so no category is painted as bad news
  6. the sentences that name a divergence name exactly the categories where the share and the
     level move apart, and this suite decides that set from the source rows itself
  7. refusals name what to fix: a negative figure, an empty category, an empty period, more
     periods than columns, a value --period does not hold, a top outside the palette
  8. no script, and the English build carries none of the page's Norwegian words
  9. five mutations, each tripping exactly the check it should: the rounding repair switched
     off (the builder's guard stops it), a share printed slightly wrong (the column sum is the
     only check that can see it), a band drawn past its share, a colour slot used twice, and a
     summed band that is one unit short

Stdlib for the arithmetic.

    python3 tests/test_composition.py
"""
from __future__ import annotations

import csv
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_composition.py"
EXAMPLE = ROOT / "examples" / "41-composition"
DATA = EXAMPLE / "bemanning.csv"
PIN = "1792836000"          # a fixed clock: one input, one file, on any day

sys.path.insert(0, str(ROOT / "tools"))
import build_composition as B  # noqa: E402  the layout constants the geometry is checked against

FAILURES: list[str] = []
CHECKS = 0


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    mark = "\u2713" if ok else "\u2717"
    print(f"  {mark} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


# ------------------------------------------------------------------------------- helpers
def run(data: pathlib.Path, out: pathlib.Path, *extra: str,
        tools: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    builder = (tools / "build_composition.py") if tools else BUILDER
    args = [sys.executable, str(builder), "--data", str(data),
            "--measure", "Timer", "--cat", "Oppgave", "--period-col", "Kvartal",
            "--title", "Hva timene gikk til: 2026",
            "--source", "Syntetisk eksempeldata (bemanning.csv)",
            "--requested-by", "Bemanningskontoret", "--out", str(out), *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env)


def scratch(root: pathlib.Path, *pairs: tuple[str, str]) -> pathlib.Path:
    """A copy of tools/ and templates/ a mutation can break without touching the repo."""
    tools = root / "tools"
    tools.mkdir(parents=True)
    shutil.copy2(BUILDER, tools / "build_composition.py")
    for name in ("build_size.py", "build_stamp.py", "feedback_link.py", "i18n.py",
                 "tun_core.py", "tun_tokens.py"):
        shutil.copy2(ROOT / "tools" / name, tools / name)
    # tun_tokens resolves the token files from its own location, so the scratch tree needs them:
    # the template carries {{TOKEN_CSS}} and the builder cannot produce a page without the seam.
    shutil.copytree(ROOT / "tools" / "tokens", tools / "tokens")
    shutil.copytree(ROOT / "templates", root / "templates")
    target = tools / "build_composition.py"
    text = target.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            raise SystemExit(f"the mutation does not apply: {old[:60]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")
    return tools


def num(text: str) -> float:
    """A figure the page printed, back as a number. nb writes NBSP and a comma."""
    t = re.sub(r"[\s\u00a0\u2009]", "", text).replace("\u2212", "-").replace("%", "")
    t = t.replace(",", ".")
    return float(t)


def table(html: str, marker: str) -> list[list[str]]:
    """The rows of the table that carries `marker`, as lists of cell texts, order kept.

    A cell here prints two figures (the share and the level under it), so the cell text is
    returned whole and the caller splits it with `figures`.
    """
    start = html.index(marker)
    block = html[start:html.index("</table>", start)]
    rows = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", block, re.S):
        rows.append([re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
                     for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)])
    return rows


def figures(text: str) -> list[float]:
    return [num(m) for m in re.findall(r"[\d\u00a0\u2009 ]*,\d|\d[\d\u00a0\u2009 ]*", text)
            if m.strip()]


def source_grid(path: pathlib.Path) -> tuple[dict[str, dict[str, float]], list[str]]:
    """Sum the measure per (category, period) from the CSV, and the periods in file order."""
    grid: dict[str, dict[str, float]] = {}
    periods: list[str] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            period, name = row["Kvartal"].strip(), row["Oppgave"].strip()
            if period not in periods:
                periods.append(period)
            grid.setdefault(name, {}).setdefault(period, 0.0)
            grid[name][period] += float(row["Timer"])
    return grid, periods


def bands_of(html: str) -> list[dict]:
    return [{"slot": m.group(1), "x": float(m.group(2)), "y": float(m.group(3)),
             "h": float(m.group(4))}
            for m in re.finditer(r'<rect class="cs-band cs-([^"]+)" x="([\d.]+)" '
                                 r'y="([\d.]+)" width="[\d.]+" height="([\d.]+)"', html)]


def share_texts(html: str) -> list[str]:
    return re.findall(r'<text class="cs-share[^"]*"[^>]*>(.*?)</text>', html, re.S)


# --------------------------------------------------------------------------------- main
def main() -> int:
    if not DATA.is_file():
        raise SystemExit(f"{DATA} is missing; run examples/41-composition/generate_data.py")
    grid, periods = source_grid(DATA)
    totals = {p: sum(per[p] for per in grid.values()) for p in periods}

    with tempfile.TemporaryDirectory() as raw:
        work = pathlib.Path(raw)

        print("1. the example builds, and the page carries every period")
        out = work / "cs.html"
        done = run(DATA, out)
        chk(done.returncode == 0, "the builder exits 0", (done.stderr or "")[-500:])
        page = out.read_text(encoding="utf-8")
        chk(f"periods       : {len(periods)}" in done.stdout,
            "the build prints the period count", done.stdout)
        rows = table(page, 'aria-labelledby="tbl-h"')
        header = rows[0]
        chk(header[1:] == periods, "the table has one column per period, in file order",
            str(header))

        print("\n2. every column of shares adds up, and no share is moved further than rounding")
        body = [r for r in rows[1:] if r and r[0] != "Totalt"]
        total_row = next((r for r in rows if r and r[0] == "Totalt"), [])
        bad = []
        for i, period in enumerate(periods):
            shares = [figures(r[i + 1])[0] for r in body]
            if abs(sum(shares) - 100.0) > 0.0001:
                bad.append(f"{period}: {sum(shares):.1f}")
        chk(not bad, "each column's shares add to exactly 100,0", "; ".join(bad))
        bad = []
        for i, period in enumerate(periods):
            for r in body:
                name = next((n for n in grid if r[0].startswith(n)), None)
                if name is None:
                    continue
                printed = figures(r[i + 1])[0]
                exact = grid[name][period] / totals[period] * 100
                if abs(printed - exact) >= 0.1000001:
                    bad.append(f"{name} {period}: {printed} vs {exact:.3f}")
        chk(not bad, "every share is within one rounding unit of its own exact share",
            "; ".join(bad[:3]))
        # The dataset has to be one where rounding each share on its own would break the
        # column, or the rule this page pays for is not being tested at all.
        naive_breaks = False
        for period in periods:
            naive = [round(grid[n][period] / totals[period] * 100, 1) for n in grid]
            if abs(sum(naive) - 100.0) > 0.0001:
                naive_breaks = True
        chk(naive_breaks, "and naive rounding would have broken at least one column here",
            "the dataset does not exercise the rounding rule")
        chk(total_row and all(abs(figures(c)[0] - 100.0) < 0.0001 for c in total_row[1:]),
            "the total row prints 100,0 % in every column", str(total_row))

        print("\n3. every level is the source sum, and the levels add up to the printed total")
        bad = []
        for i, period in enumerate(periods):
            levels = []
            for r in body:
                name = next((n for n in grid if r[0].startswith(n)), None)
                if name is None:
                    bad.append(f"unknown row {r[0]!r}")
                    continue
                got = figures(r[i + 1])[1]
                levels.append(got)
                if abs(got - grid[name][period]) > 0.01:
                    bad.append(f"{name} {period}: {got} vs {grid[name][period]}")
            if abs(sum(levels) - totals[period]) > 0.01:
                bad.append(f"{period}: levels add to {sum(levels)}, total is {totals[period]}")
        chk(not bad, "each level is the source sum and each column adds to its total",
            "; ".join(bad[:3]))
        chk(len(body) == len(grid), f"the table lists all {len(grid)} categories",
            f"{len(body)} rows")
        printed_totals = re.findall(r'<text class="cs-total"[^>]*>(.*?)</text>', page, re.S)
        chk([num(t) for t in printed_totals] == [totals[p] for p in periods],
            "the total above each column is that period's total", str(printed_totals))

        print("\n4. the bands are the shares, stacked from the base")
        bands = bands_of(page)
        per_column = len(bands) // len(periods)
        chk(len(bands) % len(periods) == 0, "every column has the same number of bands",
            f"{len(bands)} bands over {len(periods)} columns")
        top_of_plot = float(re.search(r'<line class="cs-base"[^>]*y1="([\d.]+)"', page)
                            .group(1))
        bad = []
        for i, period in enumerate(periods):
            column = bands[i * per_column:(i + 1) * per_column]
            heights = sum(b["h"] for b in column)
            if abs(heights - B.PLOT_H) > 0.6:
                bad.append(f"{period}: bands cover {heights:.1f} of {B.PLOT_H}")
            lowest = max(column, key=lambda b: b["y"] + b["h"])
            if abs((lowest["y"] + lowest["h"]) - top_of_plot) > 0.6:
                bad.append(f"{period}: the stack does not end at the base")
            if abs(min(b["y"] for b in column) - (top_of_plot - B.PLOT_H)) > 0.6:
                bad.append(f"{period}: the stack does not reach the top of the plot")
        chk(not bad, "each column's bands fill the plot from base to top", "; ".join(bad[:2]))
        bad = []
        for i, period in enumerate(periods):
            column = bands[i * per_column:(i + 1) * per_column]
            shares = []
            for b in column:
                shares.append(round(b["h"] / B.PLOT_H * 1000))
            if sum(shares) != 1000:
                bad.append(f"{period}: {sum(shares)}")
        chk(not bad, "and their heights are the shares they claim, per mille for per mille",
            "; ".join(bad))
        chk(len(share_texts(page)) > 0, "the bands with room carry their share as text")
        for text in share_texts(page)[:3]:
            chk(num(text) <= 100.0, f"a printed band share is a percentage ({text.strip()})")

        print("\n5. the colours are distinct, few, and none of them is a verdict")
        slots = [b["slot"] for b in bands[:per_column]]
        chk(len(set(slots)) == len(slots), "no two bands in a column share a colour", str(slots))
        drawn_slots = [s for s in slots if s != "rest"]
        chk(len(drawn_slots) <= B.MAX_BANDS, f"at most {B.MAX_BANDS} drawn bands",
            str(drawn_slots))
        chk("rest" in slots, "the summed rest band has its own neutral slot", str(slots))
        # The palette, not the page: the inlined seam declares --bad for other artefacts' status
        # figures, so scanning the page for a red hex would flag the stylesheet. What must hold
        # is that no BAND is painted a verdict colour, in either theme.
        ramp = re.findall(r"--(?:s[1-4]|srest)\s*:\s*([^;}]+)", page)
        chk(len(ramp) >= 5, "the ramp is declared in both themes", str(len(ramp)))
        chk(all("bad" not in v and "negative" not in v and "#dc2a2a" not in v.lower()
                for v in ramp),
            "no band is painted a verdict colour, in either theme", str(ramp))
        chk("s5" not in page, "the palette has four categorical slots, not five")

        print("\n6. the divergence sentences name exactly the categories that diverge")
        moves = re.findall(r"<li>(.*?)</li>", page[page.index('aria-labelledby="moves-h"'):
                                                 page.index('aria-labelledby="tbl-h"')], re.S)
        moves = [re.sub(r"<[^>]+>", "", m).strip() for m in moves]
        first, last = periods[0], periods[-1]
        diverging = set()
        for name, per in grid.items():
            share_before = per[first] / totals[first]
            share_after = per[last] / totals[last]
            if (share_after - share_before) * 100 < 0.5 and \
                    (share_before - share_after) * 100 < 0.5:
                continue
            if (share_after > share_before) != (per[last] > per[first]):
                diverging.add(name)
        named = {n for n in grid if any(m.startswith(n) for m in moves)}
        chk(named == diverging, "the page names the diverging categories, and only those",
            f"page {sorted(named)} vs source {sorted(diverging)}")
        chk(any("Saksbehandling" in m for m in moves),
            "and the example's own divergence is one of them", str(moves[:2]))
        chk(all("{" not in m for m in moves), "no unfilled placeholder in the sentences",
            str([m for m in moves if "{" in m][:2]))
        chk(all(re.search(r"\d", m) for m in moves),
            "every sentence carries the figures it is about")

        print("\n7. refusals name what to fix")
        def refuses(text: str, args: tuple[str, ...], what: str, data: pathlib.Path = DATA):
            done = run(data, work / f"r{abs(hash(text)) % 9999}.html", *args)
            chk(done.returncode != 0 and text in done.stderr, what,
                (done.stderr or done.stdout)[-220:])

        refuses("is not a column in", ("--cat", "Oppgavenavn"), "a column that is not there")
        refuses("--top must be at least 1", ("--top", "0"), "a top of zero")
        refuses(f"more than the {B.MAX_BANDS} slots", ("--top", "9"),
                "a top beyond the palette")
        refuses("is not a value in", ("--period", "2027-Q1"), "a period the file does not hold")

        negative = work / "negative.csv"
        with negative.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Kvartal", "Oppgave", "Timer"])
            writer.writerows([["2026-Q1", "Saksbehandling", "100"],
                              ["2026-Q1", "M\u00f8ter", "-5"]])
        refuses("negative share", (), "a negative figure", negative)

        unnamed = work / "unnamed.csv"
        with unnamed.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Kvartal", "Oppgave", "Timer"])
            writer.writerows([["2026-Q1", "", "100"], ["2026-Q1", "M\u00f8ter", "10"]])
        refuses("belongs to nothing", (), "a figure with no category", unnamed)

        nodate = work / "nodate.csv"
        with nodate.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Kvartal", "Oppgave", "Timer"])
            writer.writerows([["", "Saksbehandling", "100"]])
        refuses("has no period", (), "a figure with no period", nodate)

        many = work / "many.csv"
        with many.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Kvartal", "Oppgave", "Timer"])
            for i in range(B.MAX_PERIODS + 1):
                writer.writerow([f"2026-M{i:02d}", "Saksbehandling", "10"])
        refuses("is more than the", (), f"more than {B.MAX_PERIODS} periods", many)

        empty = work / "empty.csv"
        with empty.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Kvartal", "Oppgave", "Timer"])
            writer.writerows([["2026-Q1", "Saksbehandling", ""]])
        refuses("no row", (), "a file with no figure at all", empty)

        print("\n8. no script, and the English build carries none of the page's words")
        chk("<script" not in page.lower(), "the page holds no script element")
        chk(not re.search(r'(src|href)="(https?:)?//', page), "and fetches nothing")
        en_out = work / "en.html"
        done = subprocess.run([sys.executable, str(BUILDER), "--data", str(DATA),
                               "--measure", "Timer", "--cat", "Oppgave",
                               "--period-col", "Kvartal", "--title", "Where the hours went",
                               "--source", "Synthetic example data", "--lang", "en",
                               "--out", str(en_out)],
                              capture_output=True, text=True, cwd=ROOT,
                              env=dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN))
        en = en_out.read_text(encoding="utf-8")
        chk(done.returncode == 0, "the English build runs", (done.stderr or "")[-300:])
        chk('<html lang="en">' in en, "the page declares its language")
        for word in ("Andel av totalen", "Sammensetningen", "Kategori", "Selvstendig",
                     "Bygget"):
            chk(word not in en, f"and not the Norwegian {word!r}")

        print("\n9. the committed example is the builder's own output")
        fresh = work / "fresh.html"
        run(DATA, fresh)
        chk(fresh.read_bytes() == (EXAMPLE / "sammensetning.html").read_bytes(),
            "a pinned rebuild equals the committed file byte for byte")

        print("\n10. the mutations")
        # 1. naive rounding, with the repair switched off: the builder's own guard is what
        #    must stop it, because the repair is the only thing keeping the column whole.
        one = work / "m1"
        one.mkdir()
        tools = scratch(one, ("    short = round(100 * scale) - sum(floors)",
                              "    short = 0"))
        done = run(DATA, work / "m1.html", tools=tools)
        chk(done.returncode != 0 and "not 100,0" in done.stderr,
            "naive rounding is refused by the builder's own sum guard",
            (done.stderr or "")[-260:])

        # 1b. a share printed slightly wrong: the guard sees whole tenths and cannot notice,
        #     so the suite's column sum is the only check that can.
        one_b = work / "m1b"
        one_b.mkdir()
        tools = scratch(one_b, ('    text = f"{share:.{SHARE_DP}f}"',
                                '    text = f"{share * 0.99:.{SHARE_DP}f}"'))
        out1 = work / "m1b.html"
        done = run(DATA, out1, tools=tools)
        chk(done.returncode == 0, "the misprinted-share mutation still builds",
            (done.stderr or "")[-300:])
        mutated = table(out1.read_text(encoding="utf-8"), 'aria-labelledby="tbl-h"')
        mbody = [r for r in mutated[1:] if r and r[0] != "Totalt"]
        broken = False
        for i, period in enumerate(periods):
            if abs(sum(figures(r[i + 1])[0] for r in mbody) - 100.0) > 0.0001:
                broken = True
        chk(broken, "a column that does not add up is caught by the column-sum check")

        # 2. one band drawn at the wrong height: the picture disagrees with the table.
        two = work / "m2"
        two.mkdir()
        tools = scratch(two, ('            h = units / 1000 * PLOT_H',
                              '            h = units / 900 * PLOT_H'))
        out2 = work / "m2.html"
        done = run(DATA, out2, tools=tools)
        chk(done.returncode == 0, "the stretched-band mutation still builds",
            (done.stderr or "")[-300:])
        mbands = bands_of(out2.read_text(encoding="utf-8"))
        covered = sum(b["h"] for b in mbands[:len(mbands) // len(periods)])
        chk(abs(covered - B.PLOT_H) > 0.6, "a band drawn past its share is caught by the "
            "geometry check", f"covered {covered:.1f}")

        # 3. a colour slot used twice: two categories become one picture.
        three = work / "m3"
        three.mkdir()
        tools = scratch(three, ('        band["slot"] = i + 1 if i < len(drawn) else "rest"',
                                '        band["slot"] = 1'))
        out3 = work / "m3.html"
        done = run(DATA, out3, tools=tools)
        chk(done.returncode == 0, "the one-colour mutation still builds",
            (done.stderr or "")[-300:])
        mslots = [b["slot"] for b in bands_of(out3.read_text(encoding="utf-8"))][:4]
        chk(len(set(mslots)) < len(mslots), "a reused colour is caught by the distinctness "
            "check", str(mslots))

        # 4. and the builder's own guard: a column that does not add to 100,0 must stop.
        four = work / "m4"
        four.mkdir()
        tools = scratch(four, ('            bands[-1]["shares"][when] = 1000 - sum('
                               'b["shares"][when] for b in bands[:-1])',
                               '            bands[-1]["shares"][when] = 999 - sum('
                               'b["shares"][when] for b in bands[:-1])'))
        done = run(DATA, work / "m4.html", tools=tools)
        chk(done.returncode != 0 and "do not add to 100,0" in done.stderr,
            "a column that does not add to 100,0 is refused by the builder",
            (done.stderr or "")[-220:])

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
