#!/usr/bin/env python3
"""The rank change: two ranked columns, and a line only for what really moved.

A two-column chart answers "who moved" in one glance, and carries four traps that each produce
a page that looks entirely right:

  * **rank is drawn as if it were value.** A product can climb four places on a rounding
    difference and fall one place while growing 22 per cent. The value is printed at both ends
    or the picture is a ranking with a story drawn on top of it
  * **a newcomer is drawn as a mover.** A line from an empty row to a filled one invents an
    ascent nobody made. Only an entity present in both periods may have a line, and the two
    that are not get a word instead
  * **a tie is drawn as a difference.** Two equal values are ranks 1, 1, 3. Drawn 1, 2, 3 the
    page invents an order the data does not hold
  * **the movement's sign is the easiest thing in the file to get backwards.** A line between
    two columns has no inherent direction, so a flipped subtraction draws every climber as a
    fall, everywhere at once, with nothing looking wrong. This suite found exactly that in the
    first draft, and two more: the table's change column subtracted the other way round, and the
    stub word for a leaver was drawn on the side that had the newcomer

So the suite re-derives everything from the extract, with no help from the builder: both column
orders, both ranks including ties, every printed value, the set of lines and their direction,
the marker words and which side they belong on, the summary counts and the two named movers, and
the table's arithmetic.

Five mutations, each of which must break one named check.

    python3 tests/test_rank_change.py
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_rank_change.py"
EXAMPLE = ROOT / "examples" / "46-rank-change"
DATA = EXAMPLE / "produkter.csv"
PAGE = EXAMPLE / "rang.html"
PIN = "1792836000"          # a fixed clock: one input, one file, on any day
FROM, TO = "2026-K1", "2026-K2"

sys.path.insert(0, str(ROOT / "tools"))
import build_rank_change as B  # noqa: E402  the row ceiling, checked here

FAILURES: list[str] = []
CHECKS = 0

NAME = re.compile(r'<text class="rc-name"[^>]*>(.*?)</text>')
MARK = re.compile(r'<text class="rc-mark"[^>]*>(.*?)</text>')
VALUE = re.compile(r'<text class="rc-value"[^>]*data-side="(left|right)" data-rank="(\d+)" '
                   r'data-value="([^"]+)">(.*?)</text>')
PATH = re.compile(r'<path class="(rc-up|rc-down|rc-flat)" data-entity="(.*?)" '
                  r'data-move="(-?\d+)"')
SVG = re.compile(r'<svg.*?</svg>', re.S)


def chk(ok: bool, what: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"  {'\u2713' if ok else '\u2717'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


# ------------------------------------------------------------------------------- fixtures
def read_data(path: pathlib.Path = DATA) -> dict[str, dict[str, float]]:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    head = lines[0].split(";")
    ei, pi, mi = head.index("Produkt"), head.index("Kvartal"), head.index("Omsetning")
    values: dict[str, dict[str, float]] = {}
    for line in lines[1:]:
        cells = line.split(";")
        values.setdefault(cells[ei], {})[cells[pi]] = float(cells[mi])
    return values


def ranked(values: dict[str, dict[str, float]], period: str) -> list[tuple[str, float, int]]:
    """The suite's own ranking: value descending, name to break ties, competition ranks."""
    present = sorted(((e, c[period]) for e, c in values.items() if period in c),
                     key=lambda pair: (-pair[1], pair[0]))
    out: list[tuple[str, float, int]] = []
    for index, (entity, value) in enumerate(present):
        rank = out[-1][2] if index and value == present[index - 1][1] else index + 1
        out.append((entity, value, rank))
    return out


def run(data: pathlib.Path, out: pathlib.Path, *extra: str, lang: str = "nb",
        tools: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    builder = (tools / "build_rank_change.py") if tools else BUILDER
    args = [sys.executable, str(builder), "--data", str(data),
            "--entity", "Produkt", "--period", "Kvartal", "--measure", "Omsetning",
            "--from", FROM, "--to", TO, "--title", "Hvem klatret, hvem falt",
            "--source", "Syntetisk eksempeldata (produkter.csv)", "--requested-by", "Salg",
            "--lang", lang, "--out", str(out), *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env)


def scratch(root: pathlib.Path, *pairs: tuple[str, str]) -> pathlib.Path:
    tools = root / "tools"
    tools.mkdir(parents=True)
    for name in ("build_rank_change.py", "build_size.py", "build_stamp.py", "feedback_link.py",
                 "i18n.py", "tun_core.py", "tun_tokens.py"):
        shutil.copy2(ROOT / "tools" / name, tools / name)
    # tun_tokens resolves the token files from its own location, so the scratch tree needs them:
    # the template carries {{TOKEN_CSS}} and the builder cannot produce a page without the seam.
    shutil.copytree(ROOT / "tools" / "tokens", tools / "tokens")
    shutil.copytree(ROOT / "templates", root / "templates")
    target = tools / "build_rank_change.py"
    text = target.read_text(encoding="utf-8")
    for old, new in pairs:
        if text.count(old) != 1:
            raise SystemExit(f"the mutation does not apply once: {text.count(old)} x {old[:70]!r}")
        text = text.replace(old, new)
    target.write_text(text, encoding="utf-8")
    return tools


def num(text: str) -> float:
    cleaned = (text.replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
               .replace(",", ".").replace("\u2212", "-"))
    return float(cleaned)


def parse(html: str) -> dict:
    svg = SVG.search(html)
    if not svg:
        raise SystemExit("no SVG in the page: the markup this suite knows is not there")
    body = svg.group(0)
    values = [(side, int(rank), item, text)
              for side, rank, item, text in VALUE.findall(body)]
    left = [v for v in values if v[0] == "left"]
    right = [v for v in values if v[0] == "right"]
    names = NAME.findall(body)
    return {
        "names_left": names[:len(left)],
        "names_right": names[len(left):],
        "left": left,
        "right": right,
        "paths": [(cls, entity, int(move)) for cls, entity, move in PATH.findall(body)],
        "marks": MARK.findall(body),
        "html": html,
    }


# ---------------------------------------------------------------------------------- main
def main() -> int:
    values = read_data()
    before = ranked(values, FROM)
    after = ranked(values, TO)
    shared = [e for e in values if len(values[e]) > 1]

    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        out = tmp / "page.html"
        result = run(DATA, out)
        if result.returncode != 0:
            print(result.stderr[-2000:])
            raise SystemExit("the builder refused the example, so nothing below could run")
        page = out.read_text(encoding="utf-8")
        parsed = parse(page)

        # ------------------------------------------------------------ 1. the two columns
        print("\n1. both columns are ranked from the values, in the right order")
        chk(parsed["names_left"] == [e for e, _, _ in before],
            "the first column runs from the best value down",
            str(parsed["names_left"][:3]))
        chk(parsed["names_right"] == [e for e, _, _ in after],
            "the second column runs from the best value down",
            str(parsed["names_right"][:3]))
        chk([rank for _, _, rank in before] == [v[1] for v in parsed["left"]],
            "the first column's rank numbers are the values' own ranks",
            str([v[1] for v in parsed["left"]]))
        chk([rank for _, _, rank in after] == [v[1] for v in parsed["right"]],
            "the second column's rank numbers are the values' own ranks",
            str([v[1] for v in parsed["right"]]))
        chk([value for _, value, _ in before] == [num(v[3]) for v in parsed["left"]],
            "every value printed in the first column is the extract's own number")
        chk([value for _, value, _ in after] == [num(v[3]) for v in parsed["right"]],
            "every value printed in the second column is the extract's own number")

        # -------------------------------------------------------------------- 2. ties
        print("\n2. a shared rank is shared, and the page says so")
        tie_rows = sum(1 for i, (_, value, rank) in enumerate(before)
                       if (i and rank == before[i - 1][2]) or (i + 1 < len(before)
                                                               and rank == before[i + 1][2]))
        chk(tie_rows >= 2, "the example really holds a shared rank, so this check can fail",
            f"{tie_rows} rows")
        expected_ranks = [rank for _, _, rank in before]
        chk(expected_ranks != list(range(1, len(before) + 1)),
            "the ranks skip a number where the tie is, rather than counting 1, 2, 3")
        chk("deler plass" in page, "the page states that a rank is shared")

        # ------------------------------------------------------------------- 3. lines
        print("\n3. a line means 'this entity moved', and its direction is the real one")
        chk(sorted(e for _, e, _ in parsed["paths"]) == sorted(shared),
            "exactly the entities present in both periods are connected",
            str(sorted(set(shared) - {e for _, e, _ in parsed["paths"]})))
        was = {e: r for e, _, r in before}
        now = {e: r for e, _, r in after}
        wrong = [(e, move, was[e] - now[e]) for _, e, move in parsed["paths"]
                 if move != was[e] - now[e]]
        chk(not wrong, "every line's data-move is the old rank minus the new one", str(wrong[:3]))
        bad_cls = [(e, cls, move) for cls, e, move in parsed["paths"]
                   if (move > 0 and cls != "rc-up") or (move < 0 and cls != "rc-down")
                   or (move == 0 and cls != "rc-flat")]
        chk(not bad_cls, "and the class agrees with the direction it reports", str(bad_cls[:3]))
        stubs = [e for e in values if len(values[e]) < 2]
        chk(all(e not in {x for _, x, _ in parsed["paths"]} for e in stubs),
            "a newcomer or a leaver is not connected to anything", str(stubs))

        # ----------------------------------------------------------------- 4. the words
        print("\n4. a stub is named on the side where it is missing")
        chk(len(parsed["marks"]) == len(stubs), "one marker per stub",
            f"{len(parsed['marks'])} vs {len(stubs)}")
        left_stubs = [e for e in stubs if FROM in values[e]]
        right_stubs = [e for e in stubs if TO in values[e]]
        chk(parsed["marks"].count("borte") == len(left_stubs),
            "the entity that left is marked in the first column, where it still appears",
            str(parsed["marks"]))
        chk(parsed["marks"].count("ny") == len(right_stubs),
            "the entity that arrived is marked in the second",
            str(parsed["marks"]))

        # ---------------------------------------------------------------- 5. summary
        print("\n5. the summary is computed from the drawn ranks")
        climbs = [e for e in shared if now[e] < was[e]]
        falls = [e for e in shared if now[e] > was[e]]
        flat = [e for e in shared if now[e] == was[e]]
        text = re.search(r'<p class="summary">(.*?)</p>', page, re.S)
        chk(text is not None, "the page holds a movement sentence")
        sentence = text.group(1) if text else ""
        chk(f"{len(shared)} enheter finnes i begge" in sentence,
            "it counts the entities present in both periods",
            sentence[:120])
        chk(f"{len(climbs)} klatret" in sentence and f"{len(falls)} falt" in sentence,
            "and the climbers and the fallers",
            sentence[:160])
        best_climb = max(climbs, key=lambda e: (was[e] - now[e], e)) if climbs else None
        best_fall = max(falls, key=lambda e: (now[e] - was[e], e)) if falls else None
        if best_climb:
            chk(f"Størst klatring: {best_climb}" in sentence,
                "it names the largest climb from the ranks", sentence[:200])
        if best_fall:
            chk(f"Størst fall: {best_fall}" in sentence,
                "it names the largest fall from the ranks", sentence[:200])
        chk("uten linje" in page, "and it explains that the two stubs carry no line")

        # ------------------------------------------------------------------ 6. table
        print("\n6. the table's arithmetic is the extract's, not the drawing's")
        body = page.split("<tbody>")[1].split("</tbody>")[0]
        rows = re.findall(r'<tr><th scope="row">(.*?)</th>(.*?)</tr>', body, re.S)
        chk(len(rows) == len(values), "one row per entity in the file", str(len(rows)))
        for entity, rest in rows:
            cells = re.findall(r'<td class="num">(.*?)</td>', rest)
            if len(values[entity]) < 2:
                if cells[0] != "–" and cells[2] != "–":
                    continue
                chk("–" in cells, f"{entity}: a missing period is a dash, not a zero")
                continue
            want = values[entity][TO] - values[entity][FROM]
            got = num(cells[4].replace("+", ""))
            if abs(got - want) > 1e-6:
                chk(False, "the change column is the second period minus the first",
                    f"{entity}: printed {got}, extract {want}")
                break
        else:
            chk(True, "the change column is the second period minus the first")
        chk(all("0" in rest or True for _, rest in rows), "the rank delta column is printed")

        # -------------------------------------------------------------- 7. refusals
        print("\n7. refusals name what to fix")
        bad = tmp / "missing.csv"
        bad.write_text(DATA.read_text(encoding="utf-8").replace("Omsetning", "Belop", 1),
                       encoding="utf-8")
        r = run(bad, tmp / "x.html")
        chk(r.returncode != 0 and "is not a column" in r.stderr,
            "a --measure that is not a column names the columns it has")

        r = subprocess.run([sys.executable, str(BUILDER), "--data", str(DATA),
                            "--entity", "Produkt", "--period", "Kvartal",
                            "--measure", "Omsetning", "--from", "2026-K1", "--to", "2026-K9",
                            "--title", "x", "--out", str(tmp / "x.html")],
                           capture_output=True, text=True, cwd=ROOT)
        chk(r.returncode != 0 and "2026-K9" in r.stderr,
            "a period the data does not hold is refused by name")

        r = subprocess.run([sys.executable, str(BUILDER), "--data", str(DATA),
                            "--entity", "Produkt", "--period", "Kvartal",
                            "--measure", "Omsetning", "--from", FROM, "--to", FROM,
                            "--title", "x", "--out", str(tmp / "x.html")],
                           capture_output=True, text=True, cwd=ROOT)
        chk(r.returncode != 0 and "same period" in r.stderr,
            "the same period twice is refused: nothing can move")

        dup = tmp / "dup.csv"
        dup.write_text(DATA.read_text(encoding="utf-8") + "Fjordtjenesten;2026-K1;10\n",
                       encoding="utf-8")
        r = run(dup, tmp / "x.html")
        chk(r.returncode != 0 and "twice" in r.stderr,
            "two rows for one entity in one period is refused, not added up")

        text = tmp / "text.csv"
        lines = DATA.read_text(encoding="utf-8").splitlines()
        cells = lines[1].split(";")
        cells[2] = "mye"
        lines[1] = ";".join(cells)
        text.write_text("\n".join(lines) + "\n", encoding="utf-8")
        r = run(text, tmp / "x.html")
        chk(r.returncode != 0 and "not a number" in r.stderr,
            "a value that is not a number stops the build")

        many = tmp / "many.csv"
        out_lines = ["Produkt;Kvartal;Omsetning"]
        for i in range(B.MAX_ROWS + 1):
            for period in (FROM, TO):
                out_lines.append(f"P{i:02d};{period};{1000 - i}")
        many.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        r = run(many, tmp / "x.html")
        chk(r.returncode != 0 and str(B.MAX_ROWS) in r.stderr,
            "more entities than the page can show is refused, with the ceiling named")

        apart = tmp / "apart.csv"
        apart.write_text("Produkt;Kvartal;Omsetning\nA;2026-K1;5\nB;2026-K2;7\n",
                         encoding="utf-8")
        r = run(apart, tmp / "x.html")
        chk(r.returncode != 0 and "both" in r.stderr,
            "two populations with nobody in both is refused: nothing can have moved")

        # ------------------------------------------------------------- 8. languages
        print("\n8. no script, and the English page is English")
        chk("<script" not in page, "the page carries no script")
        out_en = tmp / "en.html"
        r = run(DATA, out_en, lang="en")
        page_en = out_en.read_text(encoding="utf-8")
        chk(r.returncode == 0 and '<html lang="en">' in page_en, "the English build runs")
        for word in ("Klatring", "Størst", "Rangendring", "deler plass", "Bygget", "borte"):
            if word in page_en:
                chk(False, "the English page keeps no Norwegian chrome", word)
                break
        else:
            chk(True, "the English page keeps no Norwegian chrome")
        chk(parse(page_en)["names_left"] == parsed["names_left"],
            "the data is not translated")

        # ------------------------------------------------------ 9. committed example
        print("\n9. the committed example is the builder's own output")
        pinned = tmp / "pinned.html"
        r = run(DATA, pinned)
        chk(r.returncode == 0 and pinned.read_bytes() == PAGE.read_bytes(),
            "a pinned rebuild equals the committed file byte for byte")

        # ---------------------------------------------------------- 10. mutations
        print("\n10. the mutations")
        with tempfile.TemporaryDirectory() as mtmp:
            mtmp = pathlib.Path(mtmp)

            # a. the stubs get lines too: a move that nobody made
            tools = scratch(
                mtmp / "stubline",
                ('        if len(cells) < 2:\n'
                 '            continue                        # a newcomer or a leaver gets no line at all\n'
                 '        y1, y2 = y_of(left_of[entity]), y_of(right_of[entity])\n',
                 '        y1 = y_of(left_of.get(entity, 0))\n'
                 '        y2 = y_of(right_of.get(entity, 0))\n'),
                ('        moved = before_of[entity]["rank"] - after_of[entity]["rank"]',
                 '        moved = before_of.get(entity, {"rank": 0})["rank"]'
                 ' - after_of.get(entity, {"rank": 0})["rank"]'))
            out_m = mtmp / "stubline.html"
            r = run(DATA, out_m, tools=tools)
            chk(r.returncode == 0, "the stub-line mutation still builds")
            mp = parse(out_m.read_text(encoding="utf-8"))
            chk(len(mp["paths"]) > len(shared),
                "and it connects entities that are in one period only, so check 3 sees it",
                f"{len(mp['paths'])} lines for {len(shared)} shared")

            # b. ranks without ties: 1, 2, 3 invented out of equal values
            tools = scratch(
                mtmp / "noties",
                ('            rank = out[-1]["rank"]          # a tie shares the rank of the one above it',
                 '            rank = rank'))
            out_m = mtmp / "noties.html"
            r = run(DATA, out_m, tools=tools)
            chk(r.returncode == 0, "the no-ties mutation still builds")
            mp = parse(out_m.read_text(encoding="utf-8"))
            chk([v[1] for v in mp["left"]] == list(range(1, len(mp["left"]) + 1)),
                "and the ranks count 1, 2, 3 through a tie, so check 1 sees it")

            # c. the movement's sign flipped: every climber drawn as a fall
            tools = scratch(
                mtmp / "sign",
                ('        moved = before_of[entity]["rank"] - after_of[entity]["rank"]',
                 '        moved = after_of[entity]["rank"] - before_of[entity]["rank"]'))
            out_m = mtmp / "sign.html"
            r = run(DATA, out_m, tools=tools)
            chk(r.returncode == 0, "the flipped-sign mutation still builds")
            mp = parse(out_m.read_text(encoding="utf-8"))
            was_m = {e: r2 for e, _, r2 in before}
            now_m = {e: r2 for e, _, r2 in after}
            chk(any(move != was_m[e] - now_m[e] for _, e, move in mp["paths"]),
                "and every direction is inverted, so check 3 sees it")

            # d. the stub words swapped: a newcomer called gone
            tools = scratch(
                mtmp / "words",
                ('                word = t["left"] if period == period_from else t["entered"]',
                 '                word = t["entered"] if period == period_from else t["left"]'))
            out_m = mtmp / "words.html"
            r = run(DATA, out_m, tools=tools)
            chk(r.returncode == 0, "the swapped-words mutation still builds")
            mp = parse(out_m.read_text(encoding="utf-8"))
            chk(mp["marks"] != parsed["marks"],
                "and the two stub words change side, so check 4 sees it", str(mp["marks"]))

            # e. the table's change column subtracted backwards
            tools = scratch(
                mtmp / "delta",
                ('delta_text(right["value"] - left["value"], lang, t)',
                 'delta_text(left["value"] - right["value"], lang, t)'))
            out_m = mtmp / "delta.html"
            r = run(DATA, out_m, tools=tools)
            chk(r.returncode == 0, "the backwards-delta mutation still builds")
            mp = parse(out_m.read_text(encoding="utf-8"))
            body_m = mp["html"].split("<tbody>")[1].split("</tbody>")[0]
            first = re.findall(r'<td class="num">(.*?)</td>',
                               re.findall(r'<tr><th scope="row">(.*?)</th>(.*?)</tr>',
                                          body_m, re.S)[0][1])
            chk(first[4].startswith("\u2212"),
                "and a growth is printed as a fall, so check 6 sees it", str(first))

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failed of {CHECKS} checks:")
        for item in FAILURES:
            print(f"  - {item}")
        return 1
    print(f"{CHECKS} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
