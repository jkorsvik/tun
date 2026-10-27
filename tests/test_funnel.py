#!/usr/bin/env python3
"""The funnel: how many reach each declared stage, and where the cohort leaks.

A funnel is easy to draw and easy to draw wrongly. The stages can be inferred instead of
declared, the drop can be left as a gap in a picture, and scaling both bar dimensions turns a
fall of half the records into a loss of three quarters of the area. This suite checks the
properties that make the page mean what it says:

  1. every count on the page is the number of distinct records that reached that stage, counted
     here from the extract. A duplicate (record, stage) row is counted once, and the page says
     how many were collapsed
  2. the stages are nested: a record at stage n+1 also reached stage n. That is what makes the
     picture a funnel rather than four counts in a column, and it is checked both ways: an
     unnested extract is refused by name, and --allow-skips puts the warning on the page
  3. the width is the only dimension carrying the count: every bar is the same height, and the
     ratio of two widths is the ratio of their counts. A bar area proportional to the count
     would be the classic exaggeration
  4. both conversion rates are printed, of the first stage and of the stage before, and the
     number lost between two stages is the difference rather than a gap
  5. the table carries the same figures as the drawing, so the picture can be checked
  6. the worst step is named from the counts, and this suite decides which pair that is
  7. refusals name what to fix: a stage the file holds but --stages does not name, a stage that
     no record reaches, one stage, the same stage twice, more stages than the page can label,
     a record with no id
  8. no script, and the English build carries none of the page's Norwegian words
  9. four mutations, each tripping exactly the check it should

Stdlib for the arithmetic.

    python3 tests/test_funnel.py
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
BUILDER = ROOT / "tools" / "build_funnel.py"
EXAMPLE = ROOT / "examples" / "42-funnel"
DATA = EXAMPLE / "soknader.csv"
STAGES = ["Mottatt", "Vurdert", "Innstilt", "Utbetalt"]
PIN = "1792836000"          # a fixed clock: one input, one file, on any day

sys.path.insert(0, str(ROOT / "tools"))
import build_funnel as B  # noqa: E402  the layout constants the geometry is checked against

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
    builder = (tools / "build_funnel.py") if tools else BUILDER
    args = [sys.executable, str(builder), "--data", str(data),
            "--id", "Soknadsnr", "--stage", "Status",
            "--stages", ",".join(STAGES), "--title", "S\u00f8knader gjennom behandlingen",
            "--source", "Syntetisk eksempeldata (soknader.csv)",
            "--requested-by", "Saksbehandlingen", "--out", str(out), *extra]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env)


def scratch(root: pathlib.Path, *pairs: tuple[str, str]) -> pathlib.Path:
    """A copy of tools/ and templates/ a mutation can break without touching the repo."""
    tools = root / "tools"
    tools.mkdir(parents=True)
    shutil.copy2(BUILDER, tools / "build_funnel.py")
    for name in ("build_size.py", "build_stamp.py", "feedback_link.py", "i18n.py",
                 "tun_core.py", "tun_tokens.py"):
        shutil.copy2(ROOT / "tools" / name, tools / name)
    # tun_tokens resolves the token files from its own location, so the scratch tree needs them:
    # the template carries {{TOKEN_CSS}} and the builder cannot produce a page without the seam.
    shutil.copytree(ROOT / "tools" / "tokens", tools / "tokens")
    shutil.copytree(ROOT / "templates", root / "templates")
    target = tools / "build_funnel.py"
    text = target.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            raise SystemExit(f"the mutation does not apply: {old[:60]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")
    return tools


def num(text: str) -> float:
    t = re.sub(r"[\s\u00a0\u2009]", "", text).replace("\u2212", "-").replace("%", "")
    return float(t.replace(",", "."))


def reached_ids(path: pathlib.Path) -> dict[str, set[str]]:
    """The distinct records at each stage, straight from the extract."""
    out: dict[str, set[str]] = {stage: set() for stage in STAGES}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            out[row["Status"].strip()].add(row["Soknadsnr"].strip())
    return out


def bars_of(html: str) -> list[dict]:
    return [{"x": float(m.group(1)), "y": float(m.group(2)), "w": float(m.group(3)),
             "h": float(m.group(4))}
            for m in re.finditer(r'<rect class="fn-bar" x="([\d.]+)" y="([\d.]+)" '
                                 r'width="([\d.]+)" height="([\d.]+)"', html)]


def texts_of(html: str, cls: str) -> list[str]:
    return [re.sub(r"<[^>]+>", "", m).strip() for m in
            re.findall(rf'<text class="{cls}"[^>]*>(.*?)</text>', html, re.S)]


def table(html: str) -> list[list[str]]:
    start = html.index('aria-labelledby="tbl-h"')
    block = html[start:html.index("</table>", start)]
    rows = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", block, re.S):
        rows.append([re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
                     for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)])
    return rows


# --------------------------------------------------------------------------------- main
def main() -> int:
    if not DATA.is_file():
        raise SystemExit(f"{DATA} is missing; run examples/42-funnel/generate_data.py")
    ids = reached_ids(DATA)
    counts = [len(ids[stage]) for stage in STAGES]
    records = len({r for s in ids.values() for r in s})

    with tempfile.TemporaryDirectory() as raw:
        work = pathlib.Path(raw)

        print("1. the example builds, and the counts are the distinct records per stage")
        out = work / "fn.html"
        done = run(DATA, out)
        chk(done.returncode == 0, "the builder exits 0", (done.stderr or "")[-500:])
        page = out.read_text(encoding="utf-8")
        chk(f"records       : {records} distinct" in done.stdout,
            "the build prints the distinct record count", done.stdout)
        printed = [int(num(t)) for t in texts_of(page, "fn-count")]
        chk(printed == counts, "every bar carries the count this suite gets from the extract",
            f"{printed} vs {counts}")
        chk(sum(1 for c in counts if c) == len(STAGES), "every declared stage has records")

        print("\n2. the stages are nested, which is what makes it a funnel")
        bad = [f"{b}->{a}" for b, a in zip(STAGES, STAGES[1:]) if ids[a] - ids[b]]
        chk(not bad, "each stage's records are a subset of the stage before", "; ".join(bad))
        chk(counts == sorted(counts, reverse=True),
            "so the counts never grow down the funnel", str(counts))

        print("\n3. the width is the only dimension carrying the count")
        bars = bars_of(page)
        chk(len(bars) == len(STAGES), "one bar per stage", str(len(bars)))
        chk(len({b["h"] for b in bars}) == 1, "every bar has the same height",
            str({b["h"] for b in bars}))
        bad = []
        for bar, n in zip(bars, counts):
            expected = n / counts[0] * B.LONGEST
            if abs(bar["w"] - expected) > 0.6:
                bad.append(f"{n}: {bar['w']} vs {expected:.1f}")
        chk(not bad, "and each width is its own count against the first", "; ".join(bad[:2]))
        chk(all(abs(b["x"] - bars[0]["x"]) < 0.01 for b in bars),
            "every bar starts at the same left edge")

        print("\n4. both conversion rates, and the number lost")
        figs = texts_of(page, "fn-fig")
        firsts = [num(t) for t in figs if "\u00b7" not in t]
        chk(all(abs(f - c / counts[0] * 100) < 0.051 for f, c in zip(firsts, counts)),
            "the share of the first stage is printed for every stage", str(firsts))
        rest = [t for t in figs if "\u00b7" in t]
        chk(len(rest) == len(STAGES) - 1,
            "the stage before is named only where there is one", str(rest))
        bad = []
        for i, text in enumerate(rest, start=1):
            share = num(text.split("\u00b7")[0])
            lost = num(text.split("\u2212")[-1])
            if abs(share - counts[i] / counts[i - 1] * 100) > 0.051:
                bad.append(f"{STAGES[i]}: {share}")
            if abs(lost - (counts[i - 1] - counts[i])) > 0.01:
                bad.append(f"{STAGES[i]} lost: {lost}")
        chk(not bad, "each share and each lost figure is this suite's own subtraction",
            "; ".join(bad[:3]))
        rows = table(page)
        body = [r for r in rows[1:] if r and r[0] in STAGES]
        chk(len(body) == len(STAGES), "the table has one row per stage", str(len(body)))
        chk([int(num(r[1])) for r in body] == counts,
            "the table's counts are the drawing's counts")

        print("\n5. the worst step is named from the counts")
        loss = [(counts[i - 1] - counts[i]) / counts[i - 1] for i in range(1, len(STAGES))]
        worst = STAGES[loss.index(max(loss)) + 1]
        sentence = re.sub(r"<[^>]+>", "", re.search(r'<p class="worst">(.*?)</p>', page,
                                                    re.S).group(1)).strip()
        chk(worst in sentence, "the largest fall names the stage it lands on",
            f"{sentence} (expected {worst})")
        chk(STAGES[loss.index(max(loss))] in sentence, "and the stage it falls from", sentence)
        chk(f"{counts[loss.index(max(loss))] - counts[loss.index(max(loss)) + 1]:,}"
            .replace(",", "\u00a0") in sentence, "and the number of records it costs")

        print("\n6. an extract that is not a funnel is refused, and says which pair")
        unnested = work / "unnested.csv"
        with unnested.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Soknadsnr", "Status"])
            writer.writerows([["A", "Mottatt"], ["A", "Vurdert"], ["A", "Innstilt"],
                              ["B", "Mottatt"], ["B", "Vurdert"],
                              ["C", "Innstilt"], ["C", "Utbetalt"],
                              ["D", "Mottatt"], ["D", "Vurdert"], ["D", "Innstilt"]])
        done = run(unnested, work / "u.html")
        chk(done.returncode != 0 and "not nested" in done.stderr,
            "an unnested extract is refused", (done.stderr or "")[-260:])
        chk("reach 'Innstilt' without reaching 'Vurdert'" in done.stderr,
            "and the refusal names the pair", (done.stderr or "")[-260:])
        allowed = work / "u2.html"
        done = run(unnested, allowed, "--allow-skips")
        chk(done.returncode == 0, "with --allow-skips it builds", (done.stderr or "")[-260:])
        warned = allowed.read_text(encoding="utf-8")
        chk('class="warn"' in warned, "and the page carries the warning block")
        chk("Innstilt uten å ha nådd Vurdert" in warned
            or "reach Innstilt without reaching Vurdert" in warned,
            "with the pair named on the page", warned[warned.index('class="warn"'):][:400])

        print("\n7. refusals name what to fix")
        def refuses(text: str, what: str, data: pathlib.Path = DATA,
                    extra: tuple[str, ...] = (), stages: str = ",".join(STAGES)):
            args = [sys.executable, str(BUILDER), "--data", str(data), "--id", "Soknadsnr",
                    "--stage", "Status", "--stages", stages, "--title", "t",
                    "--out", str(work / f"r{abs(hash(what)) % 9999}.html"), *extra]
            done = subprocess.run(args, capture_output=True, text=True, cwd=ROOT,
                                  env=dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN))
            chk(done.returncode != 0 and text in done.stderr, what,
                (done.stderr or done.stdout)[-220:])

        refuses("does not name", "a stage the file holds but --stages omits",
                stages="Mottatt,Vurdert,Innstilt")
        refuses("needs at least two stages", "a funnel of one stage", stages="Mottatt")
        refuses("names the same stage twice", "a stage named twice",
                stages="Mottatt,Vurdert,Vurdert,Utbetalt")
        refuses("without the names running together", "more stages than the page can label",
                stages=",".join(f"Trinn{i}" for i in range(B.MAX_STAGES + 1)))

        empty_stage = work / "empty-stage.csv"
        with empty_stage.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Soknadsnr", "Status"])
            writer.writerows([["A", "Mottatt"], ["A", "Vurdert"], ["A", "Innstilt"]])
        refuses("A funnel that stops", "a declared stage no record reaches",
                data=empty_stage)

        no_id = work / "no-id.csv"
        with no_id.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Soknadsnr", "Status"])
            writer.writerows([["", "Mottatt"], ["A", "Mottatt"], ["A", "Vurdert"]])
        refuses("cannot be counted at any stage", "a record with no id", data=no_id)

        print("\n8. a duplicate row is counted once, and the page says how many")
        dup = work / "dup.csv"
        with dup.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Soknadsnr", "Status"])
            writer.writerows([["A", "Mottatt"], ["A", "Mottatt"], ["A", "Vurdert"],
                              ["A", "Innstilt"], ["A", "Utbetalt"],
                              ["B", "Mottatt"], ["B", "Vurdert"], ["B", "Innstilt"],
                              ["B", "Utbetalt"]])
        dup_out = work / "dup.html"
        done = run(dup, dup_out)
        chk(done.returncode == 0, "the duplicate build runs", (done.stderr or "")[-260:])
        dup_page = dup_out.read_text(encoding="utf-8")
        chk([int(num(t)) for t in texts_of(dup_page, "fn-count")] == [2, 2, 2, 2],
            "the duplicate row does not inflate the count",
            str(texts_of(dup_page, "fn-count")))
        chk("1 dupliserte rad" in dup_page or "1 duplicate row" in dup_page,
            "and the page prints how many were collapsed")

        print("\n9. no script, and the English build carries none of the page's words")
        chk("<script" not in page.lower(), "the page holds no script element")
        chk(not re.search(r'(src|href)="(https?:)?//', page), "and fetches nothing")
        en_out = work / "en.html"
        done = subprocess.run([sys.executable, str(BUILDER), "--data", str(DATA),
                               "--id", "Soknadsnr", "--stage", "Status",
                               "--stages", ",".join(STAGES), "--title", "Applications",
                               "--source", "Synthetic example data", "--lang", "en",
                               "--out", str(en_out)],
                              capture_output=True, text=True, cwd=ROOT,
                              env=dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH=PIN))
        en = en_out.read_text(encoding="utf-8")
        chk(done.returncode == 0, "the English build runs", (done.stderr or "")[-300:])
        chk('<html lang="en">' in en, "the page declares its language")
        for word in ("Trinn", "Antall", "Selvstendig", "Bygget", "st\u00f8rste fallet"):
            chk(word not in en, f"and not the Norwegian {word!r}")

        print("\n10. the committed example is the builder's own output")
        fresh = work / "fresh.html"
        run(DATA, fresh)
        chk(fresh.read_bytes() == (EXAMPLE / "tratt.html").read_bytes(),
            "a pinned rebuild equals the committed file byte for byte")

        print("\n11. the mutations")
        # 1. the area, not the width, made proportional to the count: the classic exaggeration.
        one = work / "m1"
        one.mkdir()
        tools = scratch(one, ('        width = max(step["n"] / top * longest, 3.0)',
                              '        width = max((step["n"] / top) ** 0.5 * longest, 3.0)'))
        out1 = work / "m1.html"
        done = run(DATA, out1, tools=tools)
        chk(done.returncode == 0, "the area-scaled mutation still builds",
            (done.stderr or "")[-260:])
        mutated = bars_of(out1.read_text(encoding="utf-8"))
        off = any(abs(b["w"] - n / counts[0] * B.LONGEST) > 0.6
                  for b, n in zip(mutated, counts))
        chk(off, "a width that is the square root of the count is caught by the width check")

        # 2. the share of the previous stage computed against the first one.
        two = work / "m2"
        two.mkdir()
        tools = scratch(two, ('            "of_previous": (stage["n"] / previous) if previous else 0.0,',
                              '            "of_previous": (stage["n"] / first) if previous else 0.0,'))
        out2 = work / "m2.html"
        done = run(DATA, out2, tools=tools)
        chk(done.returncode == 0, "the wrong-denominator mutation still builds",
            (done.stderr or "")[-260:])
        rest2 = [t for t in texts_of(out2.read_text(encoding="utf-8"), "fn-fig")
                 if "\u00b7" in t]
        wrong = [num(t.split("\u00b7")[0]) for t in rest2]
        expected = [counts[i] / counts[i - 1] * 100 for i in range(1, len(counts))]
        chk(any(abs(a - b) > 0.051 for a, b in zip(wrong, expected)),
            "a share of the first stage printed as the share of the previous is caught",
            f"{wrong} vs {[round(e, 1) for e in expected]}")

        # 3. the lost figure taken from the first stage instead of the previous one.
        three = work / "m3"
        three.mkdir()
        tools = scratch(three, ('            "lost": (previous - stage["n"]) if i else 0,',
                                '            "lost": (first - stage["n"]) if i else 0,'))
        out3 = work / "m3.html"
        done = run(DATA, out3, tools=tools)
        chk(done.returncode == 0, "the wrong-lost mutation still builds",
            (done.stderr or "")[-260:])
        rest3 = [t for t in texts_of(out3.read_text(encoding="utf-8"), "fn-fig")
                 if "\u00b7" in t]
        lost3 = num(rest3[-1].split("\u2212")[-1])
        chk(abs(lost3 - (counts[-2] - counts[-1])) > 0.01,
            "a lost figure measured from the first stage is caught")

        # 4. and the builder's own guard: the nesting check removed must let the bad file in.
        four = work / "m4"
        four.mkdir()
        tools = scratch(four, ("    if skips and not args.allow_skips:", "    if False:"))
        done = run(unnested, work / "m4.html", tools=tools)
        chk(done.returncode == 0, "with the nesting guard removed the bad file builds",
            (done.stderr or "")[-260:])
        chk(skips_of_mutation(work / "m4.html"),
            "and the page still tells the reader the stages are not nested: with the guard "
            "off, the warning on the page is the only thing left")

    print()
    if FAILURES:
        print(f"{CHECKS - len(FAILURES)} passed, {len(FAILURES)} failed")
        for f in FAILURES:
            print(f"  \u2717 {f}")
        return 1
    print(f"{CHECKS} passed, 0 failed")
    return 0


def skips_of_mutation(path: pathlib.Path) -> bool:
    """True when the page still carries the nesting warning, which it must not after removal."""
    return 'class="warn"' in path.read_text(encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
