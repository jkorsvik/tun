#!/usr/bin/env python3
"""The waterfall: the steps that add up to a change, and the arithmetic behind the picture.

A bridge is the one report shape whose claim can be added up by hand, and the one that lies
most easily: a step dropped from the drawing, a level read off the wrong row, a contribution
cut at the top-N instead of summed. This suite checks the properties that make the picture
worth trusting, and each one is a way the page could be wrong:

  1. opening plus every step equals closing, recomputed here from the source rows. The page
     prints the same three figures, so a reader can check the claim without this suite
  2. every contributor's change is that contributor's own two figures subtracted, summed per
     contributor rather than read off one row, because the input is a transaction extract
  3. the table lists every contributor in the source, including the ones the drawing sums
     into one bar, and that bar's height is their exact net rather than an average
  4. the level chain adds up: each step starts where the previous one ended, and the last one
     ends at the closing figure
  5. the drawing's own geometry is the chain: each bar's top and height are that step's two
     levels on the axis the page prints, so the picture cannot disagree with the table
  6. a total is drawn as a level, not as a bar from the axis bottom, and the axis is stated
     with the numbers it starts and ends at
  7. direction is geometry and a sign; colour claims a verdict only when the caller declared
     which direction is good
  8. refusals name what to fix: a column that is not there, three periods with no --from, two
     periods that are the same, a figure that is not a number, a contributor with no name
  9. no two labels under the drawing collide, measured in a browser, because a collision is
     the one defect a static check cannot see
 10. the page holds no script, and the English build carries no Norwegian
 11. three mutations of the builder each trip exactly the check they should, and none of them
     is caught by the builder's own guard, so the checks above are the ones doing the work

Stdlib for the arithmetic; chromium for the label collisions.

    python3 tests/test_waterfall.py
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
BUILDER = ROOT / "tools" / "build_waterfall.py"
TEMPLATE = ROOT / "templates" / "waterfall.html"
EXAMPLE = ROOT / "examples" / "40-waterfall"
DATA = EXAMPLE / "omsetning.csv"
PIN = "1792836000"          # a fixed clock: one input, one file, on any day

sys.path.insert(0, str(ROOT / "tools"))
import build_waterfall as B  # noqa: E402  the layout constants the geometry is checked against

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
    builder = (tools / "build_waterfall.py") if tools else BUILDER
    args = [sys.executable, str(builder), "--data", str(data),
            "--measure", "Omsetning", "--dim", "Produkt", "--period-col", "M\u00e5ned",
            "--from", "September", "--to", "Oktober",
            "--title", "Omsetning per produkt: september mot oktober",
            "--source", "Syntetisk eksempeldata (omsetning.csv)",
            "--requested-by", "Innsikt", "--out", str(out), *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env)


def scratch(root: pathlib.Path, *pairs: tuple[str, str]) -> pathlib.Path:
    """A copy of tools/ and templates/ a mutation can break without touching the repo."""
    tools = root / "tools"
    tools.mkdir(parents=True)
    shutil.copy2(BUILDER, tools / "build_waterfall.py")
    for name in ("build_size.py", "build_stamp.py", "feedback_link.py", "i18n.py",
                 "tun_core.py", "tun_tokens.py"):
        shutil.copy2(ROOT / "tools" / name, tools / name)
    # tun_tokens resolves the token files from its own location, so the scratch tree needs them:
    # the template carries {{TOKEN_CSS}} and the builder cannot produce a page without the seam.
    shutil.copytree(ROOT / "tools" / "tokens", tools / "tokens")
    shutil.copytree(ROOT / "templates", root / "templates")
    target = tools / "build_waterfall.py"
    text = target.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            raise SystemExit(f"the mutation does not apply: {old[:60]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")
    return tools


def num(text: str) -> float:
    """A figure the page printed, back as a number. nb writes NBSP and a comma."""
    t = (text.replace("\u00a0", "").replace("\u2009", "")
         .replace("\u2212", "-").replace("+", "").replace(",", ".").strip())
    return float(t)


FIG = re.compile(r"[\u2212+\-]?\d[\d\u00a0\u2009 ]*(?:,\d+)?")


def figures(text: str) -> list[float]:
    """Every figure in a sentence of the page's prose, in order."""
    return [num(m) for m in FIG.findall(text) if m.strip()]


def cells(page: str, marker: str, stop: str = "</table>") -> list[list[str]]:
    """The rows of the table that carries `marker`, as lists of cell texts."""
    start = page.index(marker)
    block = page[start:page.index(stop, start)]
    rows = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", block, re.S):
        rows.append([re.sub(r"<[^>]+>", "", c).strip()
                     for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)])
    return rows


def source_totals(path: pathlib.Path) -> tuple[dict[tuple[str, str], float], set[str]]:
    """Sum the measure per (product, month) straight from the CSV, plus the product set."""
    sums: dict[tuple[str, str], float] = {}
    names: set[str] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            name, month = row["Produkt"].strip(), row["M\u00e5ned"].strip()
            names.add(name)
            key = (name, month)
            sums[key] = sums.get(key, 0.0) + float(row["Omsetning"])
    return sums, names


def page_parts(page: str) -> dict:
    """Everything the checks read out of one built page, in one place."""
    return {
        "identity": re.search(r'class="identity"><strong>(.*?)</strong>', page, re.S).group(1),
        "axis": re.search(r'class="wf-axis"[^>]*>(.*?)</text>', page, re.S).group(1),
        "bars": [{"cls": m.group(1), "y": m.group(2), "h": m.group(3)}
                 for m in re.finditer(
                     r'<rect class="wf-step([^"]*)" x="[\d.]+" y="([\d.]+)" '
                     r'width="[\d.]+" height="([\d.]+)">', page)],
        "levels": re.findall(r'<line class="wf-level" x1="[\d.]+" y1="([\d.]+)"', page),
        "numbers": re.findall(r'<text class="wf-num"[^>]*>(.*?)</text>', page, re.S),
        "names": re.findall(r'<text class="wf-name"[^>]*>(.*?)</text>', page, re.S),
        "base": float(re.search(r'<line class="wf-base" x1="[\d.]+" y1="([\d.]+)"',
                                page).group(1)),
    }


def y_of(level: float, low: float, high: float, base: float) -> float:
    """Where a level sits on the drawing, from the page's own axis and base line."""
    return base - (level - low) / (high - low) * B.PLOT_H


# --------------------------------------------------------------------------------- main
def main() -> int:
    if not DATA.is_file():
        raise SystemExit(f"{DATA} is missing; run examples/40-waterfall/generate_data.py")
    sums, names = source_totals(DATA)
    opening = sum(v for (n, m), v in sums.items() if m == "September")
    closing = sum(v for (n, m), v in sums.items() if m == "Oktober")
    deltas = {n: (sums.get((n, "Oktober"), 0.0) - sums.get((n, "September"), 0.0))
              for n in names}

    with tempfile.TemporaryDirectory() as raw:
        work = pathlib.Path(raw)

        print("1. the example builds, and says what it built")
        out = work / "bro.html"
        done = run(DATA, out)
        chk(done.returncode == 0, "the builder exits 0", (done.stderr or "")[-400:])
        chk(out.is_file(), "the file exists")
        page = out.read_text(encoding="utf-8")
        chk(f"opening       : {opening:,.0f}".replace(",", "\u00a0").replace(".", ",")
            in done.stdout, "the build prints the opening figure", done.stdout)
        chk("not in bridge : 16 row(s)" in done.stdout,
            "the build names the rows outside the two periods", done.stdout)

        print("\n2. the bridge closes, and the page prints the three figures")
        parts = page_parts(page)
        identity = figures(parts["identity"])[:3]
        chk(len(identity) == 3, "the identity line carries three figures", parts["identity"])
        chk(abs(identity[0] - opening) < 0.01, "its opening is the source's September total",
            f"{identity[0]} vs {opening}")
        chk(abs(identity[2] - closing) < 0.01, "its closing is the source's October total",
            f"{identity[2]} vs {closing}")
        chk(abs(identity[0] + identity[1] - identity[2]) < 0.01,
            "opening plus the change equals closing, on the page itself", parts["identity"])
        chk(abs(sum(deltas.values()) - (closing - opening)) < 0.01,
            "and this suite's own sums agree", f"{sum(deltas.values())}")
        chk("+" in parts["identity"], "a rise carries a plus in the identity line")

        print("\n3. every contributor, summed per contributor rather than read off one row")
        table = cells(page, 'aria-labelledby="tbl-h"')
        body = [r for r in table[1:] if r and r[0] != "Totalt"]
        listed = {r[0].split("\n")[0].strip() for r in body}
        chk(len(body) == len(names), f"the table lists all {len(names)} contributors",
            f"{len(body)}")
        chk(all(any(n == name.split(" ")[0] or name.startswith(n) for n in names)
                for name in listed), "every row names a contributor from the source")
        bad = []
        for row in body:
            name = next((n for n in names if row[0].startswith(n)), None)
            if name is None:
                bad.append(f"unknown row {row[0]!r}")
                continue
            frm = None if row[1] in ("\u2013", "-") else num(row[1])
            to = None if row[4] in ("\u2013", "-") else num(row[4])
            change = num(row[2])
            if abs(change - deltas[name]) > 0.01:
                bad.append(f"{name}: page says {change}, source says {deltas[name]}")
            if frm is not None and to is not None and abs((to - frm) - change) > 0.01:
                bad.append(f"{name}: {to} - {frm} is not {change}")
        chk(not bad, "each row's change is its own two figures subtracted", "; ".join(bad[:2]))
        chk(any("ny" in r[0] for r in body), "a contributor that only exists in October is tagged")
        chk(any("borte" in r[0] for r in body),
            "a contributor that only exists in September is tagged")
        total_row = next((r for r in table if r and r[0] == "Totalt"), None)
        chk(total_row is not None, "the table has a total row")
        if total_row:
            chk(abs(num(total_row[2]) - (closing - opening)) < 0.01,
                "the total row's change is the change in the identity line", str(total_row))

        print("\n4. the level chain adds up")
        chain = cells(page, 'aria-labelledby="chain-h"')[1:]
        chk(len(chain) >= 4, "the chain table has the opening, the steps and the closing",
            str(len(chain)))
        bad = []
        for i in range(len(chain) - 1):
            after = num(chain[i][3])
            before_next = num(chain[i + 1][1])
            if abs(after - before_next) > 0.01:
                bad.append(f"{chain[i][0]}: ends at {after}, next starts at {before_next}")
        chk(not bad, "each step starts where the previous one ended", "; ".join(bad[:2]))
        bad = []
        for row in chain[1:-1]:
            if abs(num(row[1]) + num(row[2]) - num(row[3])) > 0.01:
                bad.append(f"{row[0]}: {row[1]} + {row[2]} is not {row[3]}")
        chk(not bad, "each step's own three figures add up", "; ".join(bad[:2]))
        chk(abs(num(chain[0][3]) - opening) < 0.01, "the chain opens at the opening figure")
        chk(abs(num(chain[-1][3]) - closing) < 0.01, "the chain closes at the closing figure")

        print("\n5. the drawing is that chain, on the axis the page prints")
        axis_nums = figures(parts["axis"])[:2] + figures(parts["axis"])[-1:]
        chk(len(axis_nums) == 3, "the axis note carries low, high and the opening",
            parts["axis"])
        low, high = axis_nums[0], axis_nums[1]
        chk(low < opening < high, "the axis contains the opening figure")
        steps = chain[1:-1]
        chk(len(parts["bars"]) == len(steps),
            "one bar per step in the chain", f"{len(parts['bars'])} vs {len(steps)}")
        bad = []
        for bar, row in zip(parts["bars"], steps):
            before, after = num(row[1]), num(row[3])
            top = y_of(max(before, after), low, high, parts["base"])
            height = abs(y_of(after, low, high, parts["base"])
                         - y_of(before, low, high, parts["base"]))
            if abs(float(bar["y"]) - top) > 0.6:
                bad.append(f"{row[0]}: bar top {bar['y']} vs {top:.1f}")
            if abs(float(bar["h"]) - height) > 0.6:
                bad.append(f"{row[0]}: bar height {bar['h']} vs {height:.1f}")
        chk(not bad, "every bar's top and height are that step's two levels",
            "; ".join(bad[:2]))

        print("\n6. a total is a level, not a bar from the axis bottom")
        chk(len(parts["levels"]) == 2, "the opening and the closing are drawn as levels",
            str(len(parts["levels"])))
        for line, value, label in zip(parts["levels"], (opening, closing),
                                      ("opening", "closing")):
            expected = y_of(value, low, high, parts["base"])
            chk(abs(float(line) - expected) < 0.6,
                f"the {label} level sits at its own figure", f"{line} vs {expected:.1f}")
        chk("ikke fra null" in parts["axis"] or "not from zero" in parts["axis"],
            "the page says the axis does not start at zero")

        print("\n7. direction is geometry and a sign; colour claims nothing on its own")
        bad = [b["cls"] for b in parts["bars"] if b["cls"].strip()]
        chk(not bad, "without --meaning every step uses the neutral class", str(bad[:2]))
        chk(all(parts["numbers"][i + 1].startswith(("+", "\u2212"))
                for i in range(len(steps)) if abs(num(chain[i + 1][2])) > 0.005),
            "every step's number carries its sign", str(parts["numbers"]))
        up = work / "up.html"
        done = run(DATA, up, "--meaning", "up")
        chk(done.returncode == 0, "a build with --meaning up runs", (done.stderr or "")[-200:])
        marked = page_parts(up.read_text(encoding="utf-8"))["bars"]
        good = [b["cls"].strip() for b in marked]
        chk(sum(1 for c in good if c == "wf-good") >= 3,
            "a rising step is marked as good when up is good", str(good))
        chk(all(c == ("wf-good" if num(row[2]) > 0 else "wf-bad")
                for c, row in zip(good, steps)),
            "and every step's colour follows its own direction", str(good))

        print("\n8. the top-N drawing never changes the arithmetic")
        narrow = work / "narrow.html"
        done = run(DATA, narrow, "--top", "3")
        chk(done.returncode == 0, "a build with --top 3 runs", (done.stderr or "")[-300:])
        narrow_page = narrow.read_text(encoding="utf-8")
        narrow_chain = cells(narrow_page, 'aria-labelledby="chain-h"')[1:]
        chk(len(narrow_chain) == 3 + 2 + 1,
            "three steps, one summed bar, and the two totals", str(len(narrow_chain)))
        chk(abs(num(narrow_chain[-1][3]) - closing) < 0.01,
            "the narrower drawing still closes on the closing figure")
        other = narrow_chain[-2]
        rest = sorted((d for n, d in deltas.items()
                       if n not in {r[0] for r in narrow_chain[1:4]}
                       and abs(d) > 0.005), key=abs, reverse=True)
        chk(abs(num(other[2]) - sum(rest)) < 0.01,
            "the summed bar is the exact net of the steps it replaces",
            f"{num(other[2])} vs {sum(rest)}")
        chk(f"({len(rest)} trinn)" in other[0],
            "and it says how many steps it holds", other[0])
        chk(len(cells(narrow_page, 'aria-labelledby="tbl-h"')) - 2 == len(names),
            "the table still lists every contributor")

        print("\n9. refusals name what to fix")
        done = run(DATA, work / "r1.html", "--dim", "Produktnavn")
        chk(done.returncode != 0 and "is not a column in" in done.stderr,
            "a column that is not there is named", done.stderr[-200:])
        done = run(DATA, work / "r2.html", "--top", "0")
        chk(done.returncode != 0 and "--top must be at least 1" in done.stderr,
            "a top of zero is refused", done.stderr[-200:])
        done = run(DATA, work / "r3.html", "--from", "September", "--to", "September")
        chk(done.returncode != 0 and "same period" in done.stderr,
            "two identical periods are refused", done.stderr[-200:])
        done = run(DATA, work / "r4.html", "--from", "Desember")
        chk(done.returncode != 0 and "is not a value in" in done.stderr,
            "a period the file does not hold is refused", done.stderr[-200:])
        done = run(DATA, work / "r5.html", "--from", "September", "--to", "")
        chk(done.returncode != 0 and "both --from and --to" in done.stderr,
            "half a period pair is refused", done.stderr[-200:])
        two = work / "two.csv"
        with two.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["M\u00e5ned", "Produkt", "Omsetning"])
            writer.writerows([["Januar", "Boligl\u00e5n", "10"],
                              ["Februar", "Boligl\u00e5n", "12"],
                              ["Mars", "Boligl\u00e5n", "14"]])
        done = subprocess.run([sys.executable, str(BUILDER), "--data", str(two),
                               "--measure", "Omsetning", "--dim", "Produkt",
                               "--period-col", "M\u00e5ned", "--title", "t",
                               "--out", str(work / "r6.html")],
                              capture_output=True, text=True, cwd=ROOT,
                              env=dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN))
        chk(done.returncode != 0 and "holds 3 periods" in done.stderr,
            "three periods with no --from is refused by count", done.stderr[-200:])
        notnum = work / "notnum.csv"
        with notnum.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["M\u00e5ned", "Produkt", "Omsetning"])
            writer.writerows([["September", "Boligl\u00e5n", "10"],
                              ["Oktober", "Boligl\u00e5n", "elleve"]])
        done = subprocess.run([sys.executable, str(BUILDER), "--data", str(notnum),
                               "--measure", "Omsetning", "--dim", "Produkt",
                               "--period-col", "M\u00e5ned", "--title", "t",
                               "--out", str(work / "r7.html")],
                              capture_output=True, text=True, cwd=ROOT,
                              env=dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN))
        chk(done.returncode != 0 and "which is not a number" in done.stderr,
            "a figure that is not a number is refused by line", done.stderr[-200:])
        unnamed = work / "unnamed.csv"
        with unnamed.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["M\u00e5ned", "Produkt", "Omsetning"])
            writer.writerows([["September", "", "10"], ["Oktober", "Boligl\u00e5n", "12"]])
        done = subprocess.run([sys.executable, str(BUILDER), "--data", str(unnamed),
                               "--measure", "Omsetning", "--dim", "Produkt",
                               "--period-col", "M\u00e5ned", "--title", "t",
                               "--out", str(work / "r8.html")],
                              capture_output=True, text=True, cwd=ROOT,
                              env=dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN))
        chk(done.returncode != 0 and "no contributor" in done.stderr,
            "a figure with no contributor is refused", done.stderr[-200:])

        print("\n10. no script, and the English build carries no Norwegian")
        chk("<script" not in page.lower(), "the page holds no script element")
        chk(not re.search(r'(src|href)="(https?:)?//', page),
            "and fetches nothing from anywhere")
        en_out = work / "en.html"
        done = subprocess.run([sys.executable, str(BUILDER), "--data", str(DATA),
                               "--measure", "Omsetning", "--dim", "Produkt",
                               "--period-col", "M\u00e5ned", "--from", "September",
                               "--to", "Oktober", "--title", "Revenue per product",
                               "--source", "Synthetic example data", "--lang", "en",
                               "--out", str(en_out)],
                              capture_output=True, text=True, cwd=ROOT,
                              env=dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN))
        en = en_out.read_text(encoding="utf-8")
        chk(done.returncode == 0, "the English build runs", (done.stderr or "")[-300:])
        chk('<html lang="en">' in en, "the page declares its language")
        # Not a letters check: the data in this example is Norwegian by design (product names
        # such as "Boliglån"), so the test is that none of the page's own words are.
        for word in ("Lukking", "Aksen", "Trinn", "endring", "Selvstendig", "Bygget"):
            chk(word not in en, f"and not the Norwegian {word!r}")

        print("\n11. the committed example is the builder's own output")
        fresh = work / "fresh.html"
        run(DATA, fresh)
        chk(fresh.read_bytes() == (EXAMPLE / "bro.html").read_bytes(),
            "a pinned rebuild equals the committed file byte for byte")

        print("\n12. no two labels collide, measured in a browser")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            chk(False, "playwright is installed (this suite measures text, so it needs a "
                       "browser)", "uv sync --extra verify && uv run playwright install chromium")
        else:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                for width, height in ((1366, 900), (390, 844)):
                    pg = browser.new_page(viewport={"width": width, "height": height})
                    pg.goto(out.resolve().as_uri())
                    pg.wait_for_timeout(150)
                    boxes = pg.evaluate("""() => [...document.querySelectorAll('.wf-name, .wf-num')]
                        .map(n => { const b = n.getBoundingClientRect();
                                    return {t: n.textContent, x: b.x, y: b.y, w: b.width,
                                             h: b.height, size: parseFloat(getComputedStyle(n).fontSize)}; })""")
                    small = [b for b in boxes if b["size"] < 14]
                    chk(not small, f"{width}px: every label is at least 14 px",
                        str(small[:2]))
                    hits = []
                    for i, a in enumerate(boxes):
                        for b in boxes[i + 1:]:
                            if abs(a["y"] - b["y"]) < 4 and a["x"] < b["x"] + b["w"] \
                                    and b["x"] < a["x"] + a["w"]:
                                hits.append(f"{a['t']!r} over {b['t']!r}")
                    chk(not hits, f"{width}px: no two labels in one band overlap",
                        "; ".join(hits[:3]))
                    pg.close()
                browser.close()

        print("\n13. the mutation controls")
        # 1. a printed number that is not the step's own change. The chain still closes, so
        #    the builder's guard cannot see it; only the check that reads the figure can.
        one = work / "m1"
        one.mkdir()
        tools = scratch(one, ('"printed": signed(s["delta"], lang, 0),',
                              '"printed": signed(s["delta"] * 2, lang, 0),'))
        out1 = work / "m1.html"
        done = run(DATA, out1, tools=tools)
        chk(done.returncode == 0, "the doubled-number mutation still builds",
            (done.stderr or "")[-200:])
        numbers = page_parts(out1.read_text(encoding="utf-8"))["numbers"]
        chain = cells(out1.read_text(encoding="utf-8"), 'aria-labelledby="chain-h"')[1:]
        agree = all(abs(num(n) - num(row[2])) < 0.01
                    for n, row in zip(numbers[1:-1], chain[1:-1]))
        chk(not agree, "a bar carrying twice its own change is caught by the number check")

        # 2. a wrap budget so wide that names run into each other. The static checks are
        #    silent and only the browser measurement sees it, so the fixture carries names
        #    long enough to collide: the example's own are comfortably short.
        two_dir = work / "m2"
        two_dir.mkdir()
        tools = scratch(two_dir, ("        lines = wrap(c[\"name\"], chars)",
                                  "        lines = wrap(c[\"name\"], 400)"))
        longnames = work / "longnames.csv"
        with longnames.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["M\u00e5ned", "Produkt", "Omsetning"])
            for i, amount in enumerate((420, 370, 310, 260, 165, 155, 116, 80, 30, 5)):
                writer.writerow(["September", f"Produktnummer {i} med langt navn",
                                 f"{amount * 10}"])
                writer.writerow(["Oktober", f"Produktnummer {i} med langt navn",
                                 f"{amount * 10 + 7}"])
        out2 = work / "m2.html"
        done = run(longnames, out2, "--top", "7", tools=tools)
        chk(done.returncode == 0, "the wide-name mutation still builds",
            (done.stderr or "")[-200:])
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            chk(False, "playwright is installed for the collision mutation")
        else:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                pg = browser.new_page(viewport={"width": 1366, "height": 900})
                pg.goto(out2.resolve().as_uri())
                boxes = pg.evaluate("""() => [...document.querySelectorAll('.wf-name')]
                    .map(n => { const b = n.getBoundingClientRect();
                                return {t: n.textContent, x: b.x, y: b.y, w: b.width}; })""")
                hits = [f"{a['t']} over {b['t']}" for i, a in enumerate(boxes)
                        for b in boxes[i + 1:]
                        if abs(a["y"] - b["y"]) < 4 and a["x"] < b["x"] + b["w"]
                        and b["x"] < a["x"] + a["w"]]
                chk(bool(hits), "names that run together are caught by the collision check",
                    "no collision, so the check would not have caught the real one")
                pg.close()
                browser.close()

        # 3. colour claiming a verdict when none was declared.
        three = work / "m3"
        three.mkdir()
        tools = scratch(three, ('    if meaning == "none":\n        return "step"',
                                '    if meaning == "none":\n        return "good"'))
        out3 = work / "m3.html"
        done = run(DATA, out3, tools=tools)
        chk(done.returncode == 0, "the colour mutation still builds",
            (done.stderr or "")[-200:])
        classes = [b["cls"].strip() for b in page_parts(out3.read_text(encoding="utf-8"))["bars"]]
        chk(any(classes), "a verdict colour without a declared direction is caught",
            str(classes[:3]))

        # 4. and the builder's own guard: a step left out of the chain must stop the build.
        four = work / "m4"
        four.mkdir()
        tools = scratch(four, ("    if rest:\n        net = sum(s[\"delta\"] for s in rest)",
                               "    if False:\n        net = sum(s[\"delta\"] for s in rest)"))
        done = run(DATA, work / "m4.html", tools=tools)
        chk(done.returncode != 0 and "but the closing figure is" in done.stderr,
            "a bridge whose drawn steps miss the closing figure is refused by the builder",
            done.stderr[-200:])

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
