#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The comparison: two extracts of one measure, and the change between them.

"What moved since last month" is answered by hand in Excel, where the arithmetic is
invisible and the answer dies with the spreadsheet. This suite proves the properties that
make the built file a trustworthy answer, and each one is a way the answer could be wrong:

  1. a key that appears many times is summed, not read once: a transaction extract has one
     row per transaction, and taking the first per key answers a different question
  2. the change is the arithmetic this suite does independently, key for key, against the
     page's own numbers. A wrong delta that looks plausible is the failure mode here
  3. a key in only one extract is named "new" or "gone", never dropped. A region that
     stopped reporting must not look like a region with zero sales
  4. a percentage needs a denominator: a key that went from 0 to 5 has a real change and no
     meaningful percent, so the page shows a dash rather than a fabricated 100 %
  5. the no-JS view is the largest movers, drawn by the builder, with the sentence that
     says what is missing. A reader whose browser will not run the script is not looking at
     a blank box
  6. a key is text. A key holding `</script>` cannot end the script element (a CSV cell
     once ran script in this repository), so this is checked with a hostile value
  7. the English build is English, and no Norwegian string survives it

Run: python3 tests/test_comparison_dashboard.py [--engines chromium,webkit]
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_token_contrast as cc  # noqa: E402
import tun_tokens  # noqa: E402


def seam_light(slot: str) -> str:
    """The colour a light-theme slot resolves to, from the token files themselves."""
    css, _ = tun_tokens.load_token_css(auto_dark=True)
    lit = cc.resolve(cc.theme_vars(css, "light"), slot)
    r, g, b = cc.to_rgb(lit)
    return f"rgb({r}, {g}, {b})"
BUILDER = ROOT / "tools" / "build_comparison.py"
EX = ROOT / "examples" / "33-comparison"
sys.path.insert(0, str(EX))
import generate_data  # noqa: E402  the example's own generator, so the fixtures are its data

FAILURES: list[str] = []
CHECKS = 0


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


def fixtures(tmp: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """Write the two extracts the example generates, so this suite reads nothing untracked."""
    before, after = tmp / "forrige.csv", tmp / "denne.csv"
    generate_data.write(before, generate_data.BEFORE)
    generate_data.write(after, generate_data.AFTER)
    return before, after


def build(out: pathlib.Path, before: pathlib.Path, after: pathlib.Path,
          *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BUILDER), "--before", str(before), "--after", str(after),
         "--key", "Region", "--value", "Omsetning",
         "--title", "Omsetning per region", "--before-label", "September",
         "--after-label", "Oktober", "--source", "Syntetisk eksempeldata",
         "--requested-by", "Innsikt", "--out", str(out), *extra],
        capture_output=True, text=True)


def read_totals(path: pathlib.Path) -> dict[str, float]:
    """Sum the value column per key, independently of the builder."""
    totals: dict[str, float] = {}
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            key = (row.get("Region") or "").strip()
            if not key:
                continue
            totals[key] = totals.get(key, 0.0) + float(row["Omsetning"])
    return totals


def payload(page: str) -> dict:
    m = re.search(r"<script>window\.COMPARISON_DATA = (.*?);</script>", page, re.S)
    assert m, "the data payload is missing"
    return json.loads(m.group(1))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--engines", default="chromium",
                    help="comma-separated subset of chromium,firefox,webkit")
    args = ap.parse_args(argv)
    engines = [e.strip() for e in args.engines.split(",") if e.strip()]

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        BEFORE, AFTER = fixtures(tmp)
        nb = tmp / "nb.html"
        done = build(nb, BEFORE, AFTER)
        chk(done.returncode == 0, "the builder runs", (done.stderr or done.stdout)[-300:])
        page = nb.read_text(encoding="utf-8")
        data = payload(page)

        before, after = read_totals(BEFORE), read_totals(AFTER)
        keys = set(before) | set(after)

        print("\nkeys, sums and the change")
        chk(len(data["rows"]) == len(keys), "every key in either extract is a row",
            f'{len(data["rows"])} rows, {len(keys)} keys')
        chk(len(before) == 6 and len(after) == 6, "the fixture has six keys on each side",
            f"{len(before)} / {len(after)}")
        # The fixture has a repeated key on purpose, so "summed, not read once" is provable.
        with BEFORE.open(newline="", encoding="utf-8-sig") as fh:
            rows_before = list(csv.DictReader(fh))
        chk(len(rows_before) == 11, "the before extract has more rows than keys",
            f"{len(rows_before)} rows, {len(before)} keys")

        wrong = []
        for row in data["rows"]:
            k = row["k"]
            b, a = before.get(k), after.get(k)
            if b is not None and a is not None:
                if abs(row["d"] - (a - b)) > 1e-9:
                    wrong.append(f"{k}: delta {row['d']} != {a - b}")
            elif b is None:
                if row["s"] != "added" or abs(row["d"] - a) > 1e-9:
                    wrong.append(f"{k}: should be added by {a}")
            else:
                if row["s"] != "gone" or abs(row["d"] + b) > 1e-9:
                    wrong.append(f"{k}: should be gone by {-b}")
        chk(wrong == [], "every delta is the arithmetic, key for key", "; ".join(wrong[:3]))

        tot_b = sum(before.get(r["k"], 0) for r in data["rows"])
        tot_a = sum(after.get(r["k"], 0) for r in data["rows"])
        chk(round(tot_a - tot_b, 1) == round(sum((r["d"] or 0) for r in data["rows"]), 1),
            "the rows' deltas add up to the change in the totals")

        print("\nnew and gone are named, never dropped")
        states = {r["k"]: r["s"] for r in data["rows"]}
        chk(states.get("Sørvest") == "added", "a key only in the later extract is 'added'",
            states.get("Sørvest"))
        chk(states.get("Nordvest") == "gone", "a key only in the earlier extract is 'gone'",
            states.get("Nordvest"))
        chk("Sørvest" in page and "Nordvest" in page, "and both are in the markup a reader sees")

        print("\na percentage needs a denominator")
        zero_before = tmp / "zero-before.csv"
        zero_after = tmp / "zero-after.csv"
        zero_before.write_text("Region,Omsetning\nNord,0\nSør,100\n", encoding="utf-8")
        zero_after.write_text("Region,Omsetning\nNord,5\nSør,50\n", encoding="utf-8")
        z = tmp / "zero.html"
        done = build(z, zero_before, zero_after)
        zdata = payload(z.read_text(encoding="utf-8"))
        by = {r["k"]: r for r in zdata["rows"]}
        chk(by["Nord"]["d"] == 5 and by["Nord"]["pct"] is None,
            "0 to 5 has a change and no percent", str(by["Nord"]))
        chk(by["Sør"]["pct"] is not None and round(by["Sør"]["pct"], 4) == -0.5,
            "100 to 50 is minus fifty percent", str(by["Sør"]))

        print("\na key is text, never markup")
        hostile_before = tmp / "h-before.csv"
        hostile_after = tmp / "h-after.csv"
        hostile_before.write_text('Region,Omsetning\n"</script><b>x</b>",10\n', encoding="utf-8")
        hostile_after.write_text('Region,Omsetning\n"</script><b>x</b>",12\n', encoding="utf-8")
        h = tmp / "hostile.html"
        done = build(h, hostile_before, hostile_after)
        chk(done.returncode == 0, "a hostile key builds", (done.stderr or "")[-200:])
        hpage = h.read_text(encoding="utf-8")
        chk("</script><b>" not in hpage, "the hostile key cannot end the script element")
        chk("\\u003c/script\\u003e" in hpage, "it is escaped at the characters that could")
        chk("<b>x</b>" not in hpage or "&lt;b&gt;" in hpage,
            "and it is not written as markup in the table either")

        print("\nthe English build is English")
        en = tmp / "en.html"
        done = build(en, BEFORE, AFTER, "--lang", "en")
        chk(done.returncode == 0, "the English build runs", (done.stderr or "")[-200:])
        epage = en.read_text(encoding="utf-8")
        for word in ("Before", "After", "Change", "Search the keys"):
            chk(word in epage, f"the English page says {word!r}")
        for word in ("Endring", "Nullstill", "Søk i nøklene"):
            chk(word not in epage, f"and not {word!r}")

        print("\ncolour carries a verdict only when it is told which way is good")
        chk('data-meaning="none"' in page, "the default build states no verdict")
        # The tokens are in the stylesheet either way; what must not happen is a colour
        # that reads as a verdict being applied. The browser pass below measures that.
        good = tmp / "good.html"
        done = build(good, BEFORE, AFTER, "--meaning", "up")
        gpage = good.read_text(encoding="utf-8")
        chk(done.returncode == 0 and 'data-meaning="up"' in gpage,
            "a build told which way is good says so", (done.stderr or "")[-160:])
        chk("#dc2a2a" in gpage and "#007b5e" in gpage,
            "and uses the approved status tokens, not a colour recalled from memory")

        print(f"\nthe page in a real browser ({', '.join(engines)})")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("  ERROR: playwright is not installed, so nothing was rendered.")
            print("         uv sync --extra verify && uv run playwright install chromium")
            return 2
        url = nb.resolve().as_uri()
        with sync_playwright() as p:
            for engine in engines:
                browser = getattr(p, engine).launch()
                try:
                    # No script: the pre-drawn view must carry the answer.
                    ctx = browser.new_context(java_script_enabled=False,
                                              viewport={"width": 1366, "height": 900})
                    plain = ctx.new_page()
                    plain.goto(url)
                    rows = plain.locator("tbody tr").count()
                    chk(rows > 0, f"{engine}: the no-JS view lists the largest movers", str(rows))
                    chk("Sørvest" in plain.inner_text("tbody"),
                        f"{engine}: the no-JS view names the new key")
                    chk(plain.locator("#nojs").is_visible(),
                        f"{engine}: and says that search and sorting need the script")
                    ctx.close()

                    # With script: the same rows, filtered and sorted by the page itself.
                    ctx = browser.new_context(viewport={"width": 1366, "height": 900})
                    page_obj = ctx.new_page()
                    errors: list[str] = []
                    page_obj.on("pageerror", lambda e: errors.append(str(e)))
                    page_obj.goto(url)
                    page_obj.wait_for_timeout(300)
                    chk(errors == [], f"{engine}: no script errors", "; ".join(errors[:2]))
                    shown = page_obj.locator("tbody tr").count()
                    chk(shown == len(keys), f"{engine}: one row per key once the script runs",
                        f"{shown} shown, {len(keys)} keys")

                    page_obj.select_option("#show", "changed")
                    page_obj.wait_for_timeout(150)
                    changed = page_obj.locator("tbody tr").count()
                    expect = len([r for r in data["rows"] if r["s"] in ("up", "down")])
                    chk(changed == expect, f"{engine}: 'only the ones that moved' shows {expect}",
                        str(changed))

                    page_obj.select_option("#show", "all")
                    page_obj.select_option("#sort", "key")
                    page_obj.wait_for_timeout(150)
                    first = page_obj.locator("tbody tr td").first.inner_text().strip()
                    chk(first == sorted(keys, key=lambda s: s)[0] or first.startswith(
                        sorted(keys)[0]), f"{engine}: sorting by key puts a key first",
                        first)

                    page_obj.fill("#q", "Øst")
                    page_obj.wait_for_timeout(200)
                    chk(page_obj.locator("tbody tr").count() == 1,
                        f"{engine}: the search narrows to the one key that matches",
                        str(page_obj.locator("tbody tr").count()))

                    # The numbers on screen are the numbers in the payload.
                    page_obj.fill("#q", "")
                    page_obj.wait_for_timeout(150)
                    body = page_obj.inner_text("tbody")
                    chk("Sørvest" in body and "Nordvest" in body,
                        f"{engine}: both named keys survive the round trip")

                    # Default build, with every row back in view: both directions are the
                    # same colour, so the sign and the words carry the movement and the page
                    # asserts nothing about whether a change is good news.
                    up0 = page_obj.eval_on_selector(
                        "tbody tr td.delta.up", "n => getComputedStyle(n).color")
                    down0 = page_obj.eval_on_selector(
                        "tbody tr td.delta.down", "n => getComputedStyle(n).color")
                    chk(up0 == down0, f"{engine}: with no verdict flag, both directions are "
                        "the same colour", f"{up0} vs {down0}")
                    ctx.close()

                    # The verdict colours are the approved ones, measured, not assumed.
                    ctx = browser.new_context(viewport={"width": 1366, "height": 900})
                    judged = ctx.new_page()
                    judged.goto(good.resolve().as_uri())
                    judged.wait_for_timeout(300)
                    up = judged.eval_on_selector(
                        "tbody tr td.delta.up", "n => getComputedStyle(n).color")
                    down = judged.eval_on_selector(
                        "tbody tr td.delta.down", "n => getComputedStyle(n).color")
                    # Read the expected values out of the seam rather than recalling a hex:
                    # an increase is the theme's --ok (Success Green), and a decrease is
                    # --bad-ink, which is Fire Red one step darker. --bad itself is 4.49:1 on
                    # --panel, under AA by a hundredth, so the seam keeps a text variant and
                    # this figure is text. A hex written here would drift from both.
                    chk(up == seam_light("--ok"),
                        f"{engine}: an increase is the theme's --ok (Success Green)", up)
                    chk(down == seam_light("--bad-ink"),
                        f"{engine}: a decrease is the theme's --bad-ink, Fire Red one step "
                        "darker because these figures are text", down)
                    chk(seam_light("--bad-ink") != seam_light("--bad"),
                        f"{engine}: --bad-ink is not --bad (the reason it exists)", down)
                    ctx.close()
                finally:
                    browser.close()

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
