#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The KPI cards and the bar labels of tools/build_dashboard.py, on data shaped like a query.

Two problems, found by building a dashboard from a Snowflake result (one case each):

  K1  the four KPI cards were fixed: the total, the row count, the distinct count and the
      mean per row. For a rate (a value per person) the mean per row means nothing, and
      the row count is a technical number. The caller now picks the cards (--kpis) or
      names the kind of measure (--measure-kind rate drops the cards that mislead), and
      the cards get labels a reader understands, in nb and in en. With neither flag the
      cards and their code are what they always were.
  L1  a bar label longer than 16 characters was cut short with "…" and drawn at an angle.
      A chart with a long label now lays its bars out sideways, so each name has the
      width of the card. A name that is still too long for a phone ends in "…" and
      carries its full text as a tooltip.

Every case runs the real builder as a subprocess on a synthetic fixture in a temp dir,
and opens the built file from a file:// URL. L1 runs in Chromium, Firefox and WebKit.
Without Playwright the page half is reported as SKIP with the command to run.

    python3 tests/test_dashboard_kpis_and_labels.py
    uv run --extra verify python tests/test_dashboard_kpis_and_labels.py   # with the browser half
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_dashboard.py"
WITH_BROWSER = "uv run --extra verify python tests/test_dashboard_kpis_and_labels.py"
ENGINES = ("chromium", "firefox", "webkit")

PASS = FAIL = SKIP = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def skip(label: str, why: str = "playwright not installed") -> None:
    global SKIP
    SKIP += 1
    print(f"  SKIP {label} — {why}. Run: {WITH_BROWSER}")


def build(data: pathlib.Path, out: pathlib.Path, *extra: str, dimension: str = "Kategori",
          measure: str = "Kroner per person") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BUILDER), "--data", str(data), "--title", "t",
         "--dimension", dimension, "--measure", measure, "--out", str(out),
         "--source", "fixture", "--requested-by", "test", *extra],
        capture_output=True, text=True, cwd=ROOT, timeout=120)


def open_page(browser, path: pathlib.Path, width: int = 1280, height: int = 900):
    page = browser.new_page(viewport={"width": width, "height": height})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(path.resolve().as_uri())
    page.wait_for_selector("#kpis .kpi")
    return page, errors


def cards(page) -> list[tuple[str, str]]:
    """(label, value) per KPI card, as written: textContent, not the upper-cased rendering."""
    return [tuple(c) for c in page.evaluate("""() => [...document.querySelectorAll('#kpis .kpi')]
        .map(k => [k.querySelector('.label').textContent, k.querySelector('.value').textContent])""")]


def fmt(page, n: float) -> str:
    """The page's own number format, so the comparison does not depend on the locale."""
    return page.evaluate("n => META.numberFormat.format(n)", n)


# ── K1: the KPI cards ────────────────────────────────────────────────────────
QUARTERS = ("2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4")
KINDS = ("Mat", "Reise", "Bolig")


def rate_rows() -> list[dict]:
    """3 categories x 4 quarters of a per-person rate. Worked by hand: the sum is
    Mat 100+200+300+400 = 1000, Reise 10+20+30+40 = 100, Bolig 1+2+3+4 = 10, so 1110 in
    all, 277.5 per quarter, and 92.5 per row. Only the last one is meaningless."""
    base = {"Mat": 100, "Reise": 10, "Bolig": 1}
    return [{"Kategori": k, "Kvartal": q, "Kroner per person": base[k] * (i + 1)}
            for k in KINDS for i, q in enumerate(QUARTERS)]


# The cards block as the builder wrote it before --kpis existed, nb. Copied from the
# template at 748ca6f with its {{T:...}} tokens filled from the nb table. A build with
# neither new flag must still carry it, character for character.
LEGACY_CARDS_NB = """  const cards = [
    { label: `Total ${META.measure}`, value: fmt(total) },
    { label: "Antall rader", value: fmt(rows.length) },
    { label: `Unike ${META.dimension}`, value: fmt(dims) },
    { label: "Gjennomsnitt", value: fmt(avg) }
  ];
"""


def case_k1(tmp: pathlib.Path, browsers: dict) -> None:
    print("\nK1: the caller picks the KPI cards, and their labels read well")
    data = tmp / "k1.json"
    data.write_text(json.dumps(rate_rows(), ensure_ascii=False), encoding="utf-8")
    time = ("--time", "Kvartal", "--filters", "Kategori")

    legacy = tmp / "k1-legacy.html"
    r = build(data, legacy, *time)
    check("K1: builds with neither new flag", r.returncode == 0, (r.stdout + r.stderr)[-200:])
    html = legacy.read_text(encoding="utf-8") if legacy.exists() else ""
    check("K1: and its cards code is what it always was", LEGACY_CARDS_NB in html,
          "the legacy cards block is missing")

    rate_nb, rate_en = tmp / "k1-rate-nb.html", tmp / "k1-rate-en.html"
    r = build(data, rate_nb, *time, "--measure-kind", "rate")
    check("K1: builds with --measure-kind rate", r.returncode == 0, (r.stdout + r.stderr)[-200:])
    r = build(data, rate_en, *time, "--measure-kind", "rate", "--lang", "en")
    check("K1: builds with --measure-kind rate --lang en", r.returncode == 0,
          (r.stdout + r.stderr)[-200:])
    amount = tmp / "k1-amount.html"
    r = build(data, amount, "--measure-kind", "amount")
    check("K1: builds with --measure-kind amount and no --time", r.returncode == 0,
          (r.stdout + r.stderr)[-200:])
    picked = tmp / "k1-picked.html"
    r = build(data, picked, *time, "--kpis", "total,distinct")
    check("K1: builds with --kpis total,distinct", r.returncode == 0, (r.stdout + r.stderr)[-200:])
    # A label holds a column name and lands in innerHTML: it must show as text.
    odd = tmp / "k1-odd.json"
    odd.write_text(json.dumps([{"Kategori": "Mat", "Kr <b>per</b> person": 5}]), encoding="utf-8")
    escaped = tmp / "k1-odd.html"
    r = build(odd, escaped, "--kpis", "total", measure="Kr <b>per</b> person")
    check("K1: builds with markup in the measure name", r.returncode == 0, (r.stdout + r.stderr)[-200:])

    # The flags refuse what would mislead or cannot be computed, and say why.
    r = build(data, tmp / "k1-x.html", *time, "--measure-kind", "rate", "--kpis", "total,mean")
    check("K1: a mean per row is refused for a rate",
          r.returncode != 0 and "error: --kpis mean is the mean per row, which misleads for "
          "--measure-kind rate" in r.stderr, r.stderr[-200:])
    r = build(data, tmp / "k1-x.html", "--kpis", "per_period")
    check("K1: per_period without --time is refused",
          r.returncode != 0 and "error: --kpis per_period needs --time" in r.stderr, r.stderr[-200:])
    r = build(data, tmp / "k1-x.html", *time, "--kpis", ",")
    check("K1: --kpis with no card in it is refused",
          r.returncode != 0 and "error: --kpis names no card" in r.stderr, r.stderr[-200:])
    r = build(data, tmp / "k1-x.html", *time, "--kpis", "total,median")
    check("K1: an unknown card is refused, and the choices are named",
          r.returncode != 0 and "error: --kpis: unknown card 'median'. Choose from: total, distinct, "
          "per_period, mean, rows" in r.stderr, r.stderr[-200:])

    browser = browsers.get("chromium")
    if browser is None:
        skip("K1: the page shows the chosen cards with their labels and values")
        return
    if not all(p.exists() for p in (legacy, rate_nb, rate_en, amount, picked, escaped)):
        check("K1: page checks need the built files", False, "a build failed above")
        return

    page, errors = open_page(browser, legacy)
    got = cards(page)
    want = [("Total Kroner per person", fmt(page, 1110)), ("Antall rader", fmt(page, 12)),
            ("Unike Kategori", fmt(page, 3)), ("Gjennomsnitt", fmt(page, 92.5))]
    check("K1: with neither flag, the four cards are unchanged", got == want, f"{got}")
    check("K1: no page errors (legacy)", not errors, str(errors)[:200])
    page.close()

    page, errors = open_page(browser, rate_nb)
    got = cards(page)
    want = [("Sum Kroner per person", fmt(page, 1110)), ("Snitt per Kvartal", fmt(page, 277.5)),
            ("Kategori (antall)", fmt(page, 3))]
    check("K1: a rate shows the sum, the mean per quarter and the count, nb", got == want, f"{got}")
    # The cards follow the filter: Mat alone is 1000 in all, 250 per quarter, 1 category.
    page.select_option("#f_Kategori", "Mat")
    got = cards(page)
    want = [("Sum Kroner per person", fmt(page, 1000)), ("Snitt per Kvartal", fmt(page, 250)),
            ("Kategori (antall)", fmt(page, 1))]
    check("K1: and the cards follow the filter", got == want, f"{got}")
    check("K1: no page errors (rate nb)", not errors, str(errors)[:200])
    page.close()

    page, errors = open_page(browser, rate_en)
    got = cards(page)
    want = [("Total Kroner per person", fmt(page, 1110)), ("Average per Kvartal", fmt(page, 277.5)),
            ("Kategori (count)", fmt(page, 3))]
    check("K1: a rate shows the same three cards in English", got == want, f"{got}")
    check("K1: no page errors (rate en)", not errors, str(errors)[:200])
    page.close()

    page, errors = open_page(browser, amount)
    got = cards(page)
    want = [("Sum Kroner per person", fmt(page, 1110)), ("Kategori (antall)", fmt(page, 3)),
            ("Snitt per rad", fmt(page, 92.5))]
    check("K1: an amount with no --time shows the sum, the count and the mean per row",
          got == want, f"{got}")
    check("K1: no page errors (amount)", not errors, str(errors)[:200])
    page.close()

    page, errors = open_page(browser, picked)
    got = cards(page)
    want = [("Sum Kroner per person", fmt(page, 1110)), ("Kategori (antall)", fmt(page, 3))]
    check("K1: --kpis total,distinct shows exactly those two, in that order", got == want, f"{got}")
    check("K1: no page errors (picked)", not errors, str(errors)[:200])
    page.close()

    page, errors = open_page(browser, escaped)
    got = cards(page)
    check("K1: markup in a column name shows as text in the label",
          got == [("Sum Kr <b>per</b> person", fmt(page, 5))], f"{got}")
    check("K1: no page errors (markup)", not errors, str(errors)[:200])
    page.close()


# ── L1: the bar labels ───────────────────────────────────────────────────────
# Made-up names, longest first, each longer than the 16 characters the old code kept.
LONG = ("Første kategori med et langt navn", "Andre kategori, også ganske lang",
        "Tredje kategori med langt navn", "Fjerde og femte samlet", "Sjette kategori i lista",
        "Syvende kategori her", "Åttende kategori", "Niende og siste")
SHORT = ("Alfa", "Beta", "Gamma", "Delta")

LABELS_JS = """() => {
  const card = document.getElementById('chart1').closest('.card').getBoundingClientRect();
  return [...document.querySelectorAll('#chart1 text')].map(t => {
    const b = t.getBoundingClientRect(), title = t.querySelector('title');
    return { text: [...t.childNodes].filter(n => n.nodeType === 3).map(n => n.data).join(''),
             title: title ? title.textContent : null,
             transform: t.getAttribute('transform') || '',
             box: [b.left, b.top, b.right, b.bottom],
             inCard: b.left >= card.left - 1 && b.right <= card.right + 1
                     && b.top >= card.top - 1 && b.bottom <= card.bottom + 1 };
  });
}"""


def overlaps(a: list[float], b: list[float]) -> bool:
    return a[0] < b[2] - 0.5 and b[0] < a[2] - 0.5 and a[1] < b[3] - 0.5 and b[1] < a[3] - 0.5


def category_labels(page, names) -> list[dict]:
    """The chart texts that name a category: the full name, or a cut one that has a title."""
    out = []
    for t in page.evaluate(LABELS_JS):
        name = t["title"] if t["title"] is not None else t["text"]
        if name in names:
            out.append(dict(t, name=name))
    return out


def label_rows(names) -> list[dict]:
    """One value per name and quarter, larger for the earlier names, so the bar order is
    the order of `names`."""
    n = len(names)
    return [{"Kategori": k, "Kvartal": q, "Kroner per person": (n - i) * 100 + j}
            for i, k in enumerate(names) for j, q in enumerate(QUARTERS)]


def case_l1(tmp: pathlib.Path, browsers: dict) -> None:
    print("\nL1: a long bar label is shown in full, level, and clear of the others")
    built = {}
    for name, names in (("long", LONG), ("short", SHORT)):
        data = tmp / f"l1-{name}.json"
        data.write_text(json.dumps(label_rows(names), ensure_ascii=False), encoding="utf-8")
        out = tmp / f"l1-{name}.html"
        r = build(data, out, "--time", "Kvartal")
        check(f"L1: builds ({name} labels)", r.returncode == 0, (r.stdout + r.stderr)[-200:])
        built[name] = out

    for engine in ENGINES:
        browser = browsers.get(engine)
        if browser is None:
            skip(f"L1 [{engine}]: the bar labels", f"{engine} not available")
            continue
        if not all(p.exists() for p in built.values()):
            check(f"L1 [{engine}]: page checks need the built files", False, "a build failed above")
            return

        page, errors = open_page(browser, built["long"])
        labels = category_labels(page, LONG)
        texts = [t["text"] for t in labels]
        check(f"L1 [{engine}]: every long name is shown in full on a wide screen",
              sorted(texts) == sorted(LONG), f"{texts}")
        check(f"L1 [{engine}]: no label is drawn at an angle",
              labels and not any("rotate" in t["transform"] for t in labels),
              str([t["transform"] for t in labels if t["transform"]])[:200])
        tops = [t["name"] for t in sorted(labels, key=lambda t: t["box"][1])]
        check(f"L1 [{engine}]: the labels run top to bottom, largest first", tops == list(LONG),
              f"{tops}")
        clash = [(a["name"], b["name"]) for i, a in enumerate(labels) for b in labels[i + 1:]
                 if overlaps(a["box"], b["box"])]
        full = len(labels) == len(LONG)
        check(f"L1 [{engine}]: no two labels overlap", full and not clash, f"{clash[:3]}")
        out = [t["name"] for t in labels if not t["inCard"]]
        check(f"L1 [{engine}]: every label stays inside its card", full and not out, f"{out}")
        check(f"L1 [{engine}]: no page errors (wide)", not errors, str(errors)[:200])
        page.close()

        # A phone is too narrow for the longest names. Each label is the full name, or a
        # start of it ending in "…" with the full name as its tooltip.
        page, errors = open_page(browser, built["long"], width=375, height=800)
        labels = category_labels(page, LONG)
        bad = [t for t in labels if t["text"] != t["name"]
               and not (t["text"].endswith("…") and t["name"].startswith(t["text"][:-1]))]
        check(f"L1 [{engine}]: on a phone each name is in full, or cut with its full tooltip",
              len(labels) == len(LONG) and not bad, f"{len(labels)} labels, bad: {bad[:2]}")
        clash = [(a["name"], b["name"]) for i, a in enumerate(labels) for b in labels[i + 1:]
                 if overlaps(a["box"], b["box"])]
        out = [t["name"] for t in labels if not t["inCard"]]
        check(f"L1 [{engine}]: on a phone no labels overlap, and all stay in the card",
              len(labels) == len(LONG) and not clash and not out, f"clash={clash[:3]} out={out}")
        # The value axis is the other texts. On a phone there is room for fewer of them.
        ticks = [t for t in page.evaluate(LABELS_JS) if t["text"] not in LONG and t["title"] is None]
        clash = [(a["text"], b["text"]) for i, a in enumerate(ticks) for b in ticks[i + 1:]
                 if overlaps(a["box"], b["box"])]
        check(f"L1 [{engine}]: on a phone the value axis numbers do not overlap",
              len(ticks) >= 2 and not clash, f"{len(ticks)} ticks, clash={clash[:3]}")
        # The name column is capped, so the bars keep room: the largest is a third of the chart.
        widest, chart = page.evaluate("""() => [Math.max(...[...document.querySelectorAll(
            '#chart1 rect.bar')].map(r => r.getBoundingClientRect().width)),
            document.getElementById('chart1').getBoundingClientRect().width]""")
        check(f"L1 [{engine}]: on a phone the largest bar has a third of the chart or more",
              widest >= chart / 3, f"bar {widest:.0f} of {chart:.0f} px")
        check(f"L1 [{engine}]: no page errors (phone)", not errors, str(errors)[:200])
        page.close()

        # Names that fit under a bar keep the chart they always had.
        page, errors = open_page(browser, built["short"])
        labels = category_labels(page, SHORT)
        xs = page.evaluate("() => [...document.querySelectorAll('#chart1 rect.bar')]"
                           ".map(r => +r.getAttribute('x'))")
        check(f"L1 [{engine}]: short names keep the upright bars, one beside the other",
              len(set(xs)) == len(SHORT) and sorted(t["text"] for t in labels) == sorted(SHORT),
              f"x={xs} labels={[t['text'] for t in labels]}")
        check(f"L1 [{engine}]: no page errors (short)", not errors, str(errors)[:200])
        page.close()


CASES = (case_k1, case_l1)


def main() -> int:
    print("builder: KPI cards and bar labels")
    print("─" * 62)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        if sync_playwright is None:
            for case in CASES:
                case(tmp, {})
        else:
            with sync_playwright() as p:
                browsers = {}
                try:
                    for name in ENGINES:
                        try:
                            browsers[name] = getattr(p, name).launch()
                        except Exception as exc:          # an engine that is not installed
                            print(f"  note: {name} did not start: {str(exc).splitlines()[0]}")
                    for case in CASES:
                        case(tmp, browsers)
                finally:
                    for b in browsers.values():
                        b.close()

    print("─" * 62)
    tail = f"  SKIP: {SKIP} (run: {WITH_BROWSER})" if SKIP else ""
    print(f"PASS: {PASS}  FAIL: {FAIL}{tail}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
