#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""test_i18n.py: every builder speaks `--lang en|nb`, and `nb` is exactly what it was.

What is checked, and what each check counts (a check that looks at zero items fails):

  1. tables      every strings table has the same keys in nb and en; every {{T:key}} in a
                 template exists; every key is used; no en value holds a character that
                 would break the HTML, JavaScript string or comment it is pasted into.
  2. builds      every builder builds with --lang en and with --lang nb.
  3. nb frozen   the nb build of each case has the sha256 of the build made before the
                 tables existed (clock frozen, so one input gives one file).
  4. en clean    the en build of an English fixture has <html lang="en">, none of the
                 letters æøåÆØÅ, and none of the nb strings from its tables.
  5. mutations   a damaged copy of the tables must be noticed: a deleted en key stops the
                 build, and an nb string or an æ pasted into en is flagged by check 4.
                 Without these, checks 1 and 4 could be satisfied by deleting them.

Stdlib only. Runs the real builders as subprocesses.

    python3 tests/test_i18n.py                    # run the checks
    python3 tests/test_i18n.py --dump DIR [--tools DIR]
                                                  # write the nb builds, print their sha256
                                                  # (--tools: an older copy of tools/, with the
                                                  # declared nb changes applied to its output)
    python3 tests/test_i18n.py --dump-adv [--tools DIR]
                                                  # the same for the section 6 probes
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import i18n  # noqa: E402

CSV = ROOT / "examples" / "01-hello-dashboard" / "salgsdata.csv"
SPEC = ROOT / "examples" / "23-process-diagram" / "tun-workflow.process.txt"
FX_CSV = ROOT / "tests" / "fixtures" / "i18n-sales-en.txt"
FX_SPEC = ROOT / "tests" / "fixtures" / "i18n-process-en.process.txt"
TEMPLATES = ROOT / "templates"

# Runs a builder with the clock frozen, so one input gives one output on any day. Passed
# with -c, so no file lands in the repo. The builders stamp "now" into the provenance block.
SHIM = r"""
import datetime as _dt, runpy, sys
_FIXED = _dt.datetime(2026, 1, 2, 3, 4, 5)
class _Frozen(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return _FIXED.replace(tzinfo=tz) if tz else _FIXED
_dt.datetime = _Frozen
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""

DASH = "build_dashboard.py"
CUBE = "build_cube_dashboard.py"
PROC = "build_process_diagram.py"
DECK = "build_slide_deck.py"      # no input data: the starter deck, so the case has no source

# name -> (builder, input file, arguments, files written, strings tables the page uses).
# {out} is the temp dir, {in} the input as copied there (name kept, mtime fixed).
SALES = ["--title", "Salg per region og produkt 2026", "--dimension", "Produkt",
         "--measure", "Belop", "--time", "Maaned", "--requested-by", "Prosjekteier"]
FX_SALES = ["--title", "Sales by region and product 2026", "--dimension", "Product",
            "--measure", "Amount", "--time", "Month", "--requested-by", "The sales team",
            "--source", "Made-up example data"]
DASH_T = ["single-file-dashboard"]
CUBE_T = ["cube-dashboard"]
FB = ["_feedback-link"]
CASES = {
    # the repo's own examples, Norwegian data: the nb output must not move
    "dash-bundled": (DASH, CSV, SALES + ["--filters", "Region,Produkt,Kanal",
                                         "--out", "{out}/dash-bundled.html"],
                     ["dash-bundled.html"], DASH_T),
    "dash-paired": (DASH, CSV, SALES + ["--filters", "Region,Produkt,Kanal", "--mode", "paired",
                                        "--out", "{out}/paired/dash.html"],
                    ["paired/dash.html", "paired/data.js"], DASH_T),
    "dash-feedback": (DASH, CSV, ["--title", "Salg per region og produkt 2026",
                                  "--dimension", "Produkt", "--measure", "Belop",
                                  "--time", "Maaned", "--requested-by", "Prosjekteier",
                                  "--feedback-to", "hei@example.org",
                                  "--out", "{out}/dash-feedback.html"],
                      ["dash-feedback.html"], DASH_T + FB),
    "cube": (CUBE, CSV, ["--dims", "Region,Produkt,Kanal", "--time", "Maaned",
                         "--measures", "Belop:sum:kr,Antall:sum", "--title", "Transaksjonsoversikt",
                         "--requested-by", "Analyseteamet", "--out", "{out}/cube.html"],
             ["cube.html"], CUBE_T),
    "cube-feedback": (CUBE, CSV, ["--dims", "Region,Produkt", "--time", "Maaned",
                                  "--measures", "Belop:sum,Antall:sum",
                                  "--title", "Transaksjonsoversikt", "--requested-by", "Analyseteamet",
                                  "--feedback-to", "https://example.org/org/repo/issues/new",
                                  "--out", "{out}/cube-feedback.html"],
                      ["cube-feedback.html"], CUBE_T + FB),
    "process": (PROC, SPEC, ["{in}", "--out", "{out}/process.html"], ["process.html"],
                ["process-diagram"]),
    # English fixtures: the en output is judged on these, and nb is frozen on them too
    "fx-dash": (DASH, FX_CSV, FX_SALES + ["--filters", "Region,Product,Channel",
                                          "--feedback-to", "hei@example.org",
                                          "--out", "{out}/fx-dash.html"],
                ["fx-dash.html"], DASH_T + FB),
    "fx-dash-paired": (DASH, FX_CSV, FX_SALES + ["--mode", "paired", "--out", "{out}/fxp/dash.html"],
                       ["fxp/dash.html", "fxp/data.js"], DASH_T),
    "fx-dash-notime": (DASH, FX_CSV, ["--title", "Sales", "--dimension", "Product",
                                      "--measure", "Amount", "--out", "{out}/fx-dash-notime.html"],
                       ["fx-dash-notime.html"], DASH_T),
    "fx-cube": (CUBE, FX_CSV, ["--dims", "Region,Product,Channel", "--time", "Month",
                               "--measures", "Amount:sum:kr,Count:sum", "--title", "Sales",
                               "--requested-by", "The sales team",
                               "--feedback-to", "https://example.org/org/repo/issues/new",
                               "--out", "{out}/fx-cube.html"],
                ["fx-cube.html"], CUBE_T + FB),
    "fx-process": (PROC, FX_SPEC, ["{in}", "--out", "{out}/fx-process.html"], ["fx-process.html"],
                   ["process-diagram"]),
    "fx-deck": (DECK, None, ["--out", "{out}/fx-deck.html"], ["fx-deck.html"],
                ["portable-slide-deck"]),
}

# sha256 of the nb build of each file, made with the export branch's own builders and
# templates (licence headers, neutral palette) as they were on a9cca83, before any strings
# table existed, plus the one deliberate change below. Rebuilt on every run, so a change to
# nb output anywhere (a template, a builder, a table) shows up here as a changed hash.
# The pins were taken from the old builders and proved equal to the builds with the tables:
# `--dump DIR --tools OLD_TOOLS` writes the old output, `--dump DIR` the current nb output.
# The deck had no starter builder: its baseline is the sha256 of templates/portable-slide-deck.html
# on that commit with its placeholders filled the way the builder fills them (title "Portable
# presentasjon", source "none (starter deck)", requested by "not stated", clock frozen).
# The one deliberate change to nb output since then: the dashboard footer and its build
# comment no longer name the tool that ran the builder (decision D7, 2026-10-09). The six
# dashboard hashes below include it. The second deliberate change is accessibility (G08,
# 2026-10-10, found by axe 4.14): --muted in tools/tokens/theme-light.css went from #737373
# (4.46:1 on --panel, under WCAG AA) to #666666 (5.4:1), which also reaches the process
# diagrams; the table wrapper became a focusable named region; and the KPI and chart grids
# stopped forcing a minimum wider than a 375px phone. Applying these pairs to the old
# builders' output must give the current nb output; that is how the pins were proved
# (old builders: the export branch at 1856e1f), and the pairs stay here so the next re-pin
# can be proved the same way.
DELIBERATE_NB_CHANGES = [
    (b"Selvstendig dashboard bygget av RAIWork", "Selvstendig dashboard laget med T\u00fan".encode()),
    (b"Tallene er bygget inn i denne filen. Be RAIWork om <code>tun-data</code> for \\u00e5 oppdatere.",
     b"Tallene er bygget inn i denne filen. Oppdater dem med <code>tun-data</code>."),
    (b"Built by    : RAIWork skill `tun-new`", "Built by    : T\u00fan skill `tun-new`".encode()),
    (b"--muted:      #737373;               /* neutral grey: labels, axis text (4.7:1 on white) */",
     b"--muted:      #666666;               /* neutral grey: labels, axis text (5.7:1 on white, 5.4:1 on --panel) */"),
    (b"--muted:      #737373;\n", b"--muted:      #666666;\n"),   # the process builder drops comments
    (b"repeat(auto-fit,minmax(12rem,1fr));", b"repeat(auto-fit,minmax(min(17rem,100%),1fr));"),
    (b".kpi{background:var(--panel);", b".kpi{min-width:0;background:var(--panel);"),
    (b"repeat(auto-fit,minmax(26rem,1fr));gap", b"repeat(auto-fit,minmax(min(26rem,100%),1fr));gap"),
    (b'<h2>Detaljer <span id="rowcount"', b'<h2 id="details-title">Detaljer <span id="rowcount"'),
    (b'<div class="table-wrap"><table id="tbl">',
     b'<div class="table-wrap" role="region" aria-labelledby="details-title" tabindex="0"><table id="tbl">'),
]

BASELINE = {
    "fx-deck/fx-deck.html": "e78abdddeda4a42de1d9dce5d639f272ce001f193c8e087463ed26f224ffea91",
    "dash-bundled/dash-bundled.html": "fc33e12275a40c844026c6209c279734372b19e84c67d648b69a41ea088880d5",
    "dash-paired/paired/dash.html": "b582d62b0a66238ab406909a046ca27f997a940c0e12b9442b57a12ca305906c",
    "dash-paired/paired/data.js": "57971987b2a191b18dc9d3980ccaad1419cb3a8d92145a9aef497bfaa72a678c",
    "dash-feedback/dash-feedback.html": "cf7965ea1a8271882705efd2265247bc169545d7a554811e1f7e9d7873db2f55",
    "cube/cube.html": "6d6dced8ab5a854522d2b9126e21d91e9af35c20329f0bde7d8abb9cfdfcb0b3",
    "cube-feedback/cube-feedback.html": "d54f023996cc2cfa9303706fc31823173b66f0f2a8b9845584faa69ddfa18a30",
    "process/process.html": "c6fc57835960134684cc4d92d14a4cf289c8872aa62c23c629384ea92d5d0a31",
    "fx-dash/fx-dash.html": "c58595bbbae4198fc729077e0aea3b49dc889bb0785141958839934bd3092a05",
    "fx-dash-paired/fxp/dash.html": "4f06ae7ca8c3cdba88965a2155566391b17d149ff92633940bfe5d04bb4f5fdd",
    "fx-dash-paired/fxp/data.js": "360bafa7d429d90f75a86aa7bc2f73f80db69634e8451dbf996c9001721f85bb",
    "fx-dash-notime/fx-dash-notime.html": "5e25e24b5a5e6469370cf60f08f49b280c2d57df41f2a43398a7e8a015cc06dd",
    "fx-cube/fx-cube.html": "354fd6cadd571edc3f0b1117e55168df96d31a2b6e701d2e68060c580a56137a",
    "fx-process/fx-process.html": "bbdd3a69642463217a0f03fa86449de091e9f7e84cf86dff2773999a6d429421",
}

FORBIDDEN_IN_EN = ("'", '"', "\\", "`", "${")   # would break the string or comment it lands in
NORWEGIAN_LETTERS = re.compile("[æøåÆØÅ]")

passed = failed = 0


def chk(label: str, ok: bool, detail: str = "", n: int | None = None) -> bool:
    """One check. `n` is how many items it looked at; zero items is a failure."""
    global passed, failed
    if n is not None and n == 0:
        ok, detail = False, "checked 0 items"
    if ok:
        passed += 1
        print(f"  PASS {label}" + (f" ({n} checked)" if n is not None else ""))
    else:
        failed += 1
        print(f"  FAIL {label}" + (f": {detail}" if detail else ""))
    return ok


def build_case(name: str, out: pathlib.Path, lang: str | None, tools: pathlib.Path | None = None,
               extra_env: dict | None = None, check: bool = True):
    """Build one case into `out`. Returns ({relative file: bytes}, CompletedProcess)."""
    builder, source, args, files, _tables = CASES[name]
    out.mkdir(parents=True, exist_ok=True)
    data = out / "_in" / (source.name if source else "none")
    if source:
        data.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, data)
        os.utime(data, (1767323045, 1767323045))
    argv = [a.replace("{out}", str(out)).replace("{in}", str(data)) for a in args]
    if builder in (DASH, CUBE):
        argv = ["--data", str(data), *argv]
    if lang:
        argv += ["--lang", lang]
    env = dict(os.environ, TZ="UTC", SOURCE_DATE_EPOCH="1767323045", **(extra_env or {}))
    r = subprocess.run([sys.executable, "-c", SHIM, str((tools or ROOT / "tools") / builder), *argv],
                       capture_output=True, text=True, cwd=ROOT, env=env)
    if r.returncode != 0:
        if check:
            raise SystemExit(f"{name} ({lang}): builder failed\n{r.stderr[-1500:]}")
        return {}, r
    return {f: (out / f).read_bytes() for f in files}, r


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


# ------------------------------------------------------------------------ table checks
def table_names() -> list[str]:
    return sorted(p.stem for p in i18n.DIR.glob("*.strings"))


def table_problems(directory: pathlib.Path) -> list[str]:
    """Key sets that differ between nb and en, in every table of a directory."""
    problems = []
    for p in sorted(directory.glob("*.strings")):
        tables = i18n.parse(p.read_text(encoding="utf-8"), p.name)
        for lang in i18n.LANGS:
            if lang not in tables:
                problems.append(f"{p.name}: no [{lang}] section")
        if all(lang in tables for lang in i18n.LANGS):
            for key in sorted(set(tables["nb"]) ^ set(tables["en"])):
                have = "nb" if key in tables["nb"] else "en"
                problems.append(f"{p.name}: {key} only in {have}")
    return problems


ALSO_ENGLISH = {"over"}    # an nb word that is an English word too ("{measure} over {time}")
IDENTIFIERS = re.compile(r'\b(?:id|for|aria-controls|aria-labelledby)="[^"]*"')


def en_problems(html: str, tables: list[str]) -> tuple[list[str], int]:
    """What is wrong with an en page: Norwegian letters, or an nb string. Also the number
    of nb fragments looked for, so the caller can refuse a check that looked for nothing.

    The reference is always the committed tables, never the ones a page was built from, so
    a table that was damaged cannot vouch for itself. Element ids (tab-steg, panel-roller)
    are identifiers that no one reads, and the verifiers and old links use them, so they
    stay as they were and are not scanned."""
    problems = []
    html = IDENTIFIERS.sub("", html)
    for m in NORWEGIAN_LETTERS.finditer(html):
        line = html.count("\n", 0, m.start()) + 1
        problems.append(f"letter {m.group()!r} on line {line}")
        break
    looked = 0
    for name in tables:
        t = i18n.load_all(name)
        for key, nb_value in t["nb"].items():
            en_value = t["en"][key]
            for frag in re.split(r"\{[a-z]+\}", nb_value):
                frag = frag.strip()
                if len(frag) < 3 or frag in en_value or frag in ALSO_ENGLISH:
                    continue          # too short to mean anything, or the same word in en
                looked += 1
                if re.search(r"(?<![\w])" + re.escape(frag) + r"(?![\w])", html):
                    problems.append(f"nb text from {name}.{key}: {frag!r}")
    return problems, looked


def declared_changes(blob: bytes) -> bytes:
    """What an old builder's output becomes once the declared nb changes are applied."""
    for before, after in DELIBERATE_NB_CHANGES:
        blob = blob.replace(before, after)
    return blob


def main() -> int:
    tools_dir = None
    if "--tools" in sys.argv:
        tools_dir = pathlib.Path(sys.argv[sys.argv.index("--tools") + 1])
    if "--dump" in sys.argv:
        dest = pathlib.Path(sys.argv[sys.argv.index("--dump") + 1])
        dest.mkdir(parents=True, exist_ok=True)
        for case in CASES:
            if tools_dir and CASES[case][0] == DECK:
                continue      # older tools had no deck builder
            built, _ = build_case(case, pathlib.Path(tempfile.mkdtemp()), None if tools_dir else "nb",
                                  tools_dir)
            for rel, blob in built.items():
                if tools_dir:
                    blob = declared_changes(blob)
                (dest / f"{case}--{rel.replace('/', '__')}").write_bytes(blob)
                print(f'    "{case}/{rel}": "{sha(blob)}",')
        return 0
    if "--dump-adv" in sys.argv:
        work = pathlib.Path(tempfile.mkdtemp(prefix="tun-i18n-adv-"))
        for name in register_probes(work):
            built, _ = build_case(name, work / "pin" / name, None if tools_dir else "nb", tools_dir)
            for rel, blob in built.items():
                if tools_dir:
                    blob = declared_changes(blob)
                print(f'    "{name}/{rel}": "{sha(blob)}",')
        return 0

    work = pathlib.Path(tempfile.mkdtemp(prefix="tun-i18n-"))
    try:
        return run(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


# sha256 of the nb build of each section 6 probe file, taken from the builders before any
# strings table existed (a9cca83) with the declared nb changes applied to their output
# (`--dump-adv --tools OLD_TOOLS`), and proved equal to the current builders' nb output.
# Pinned rather than rebuilt from git: a flattened export has no history to build from.
ADV_BASELINE = {
    "slot-dash/slot-dash.html": "939106d0d4a76abb90eca28ddec91ec321473cd92d28b64af5c8d9d9b50033ae",
    "slot-cube/slot-cube.html": "3ed2300d33491df0d2050c42f7246b90ce3876718aba91ff66c5d4e2180d8e8a",
    "tok-dash/tok-dash.html": "cdbee34cd89632c76bfa776cb55521cf703f72cf01451aa7bf5fb4dda8eaef3e",
    "tok-cube/tok-cube.html": "eaa34ce4e1adc7124ee9f2fd56a95c6f433fbad42bec641a52d6b3fee8274d73",
    "tok-process/tok-process.html": "ef37a38809985e10775e901d4c3bd7ea5b252adc50f2a0d0f27d1e4d0413befc",
}


def register_probes(work: pathlib.Path) -> dict:
    """Write the probe inputs under `work` and add the probes to CASES. Data that looks like
    a format slot or a template token: it must come out untouched, exactly as the builders
    before the tables wrote it (chained .replace() rescanned it). Returns name -> probe."""
    adv = work / "adv"
    adv.mkdir(exist_ok=True)
    # a measure column called {dimension}; the old builder printed "{dimension} per Product"
    slot_csv = adv / "slot.csv"
    slot_csv.write_text("Month,Product,{dimension}\n2026-01,Loans,10\n2026-02,Cards,20\n", encoding="utf-8")
    # a source file called source-{rows}.csv; the old cube builder kept the name as it was
    name_csv = adv / "source-{rows}.csv"
    name_csv.write_text("Month,Product,Amount\n2026-01,Loans,10\n2026-02,Cards,20\n", encoding="utf-8")
    # titles, column names, values and a requester that hold tokens and slots of every table
    evil = "{{T:reset}} {n} {measure} {dimension} {time} {name} {rows} {cells} {dims} {steps} {lanes}"
    tok_csv = adv / "tokens.csv"
    tok_csv.write_text(f'Month,Product,Amount\n2026-01,"{evil}",10\n2026-02,Cards,20\n', encoding="utf-8")
    spec = adv / "tokens.process.txt"
    short = "{{T:reset}} {n} {steps} {lanes}"       # a lane name is at most 40 characters
    spec.write_text(
        f"title: {evil}\nsource: {evil}\nrequested-by: {evil}\ndescription: {evil}\n\n"
        f"lane {short}\n  start a: {evil}\n    beskrivelse: {evil}\n  step b: Two\n"
        f"    improve: {evil}\n  end c: Three\n\nflow\n  a -> b -> c\n", encoding="utf-8")
    probes = {
        "slot-dash": (DASH, slot_csv, ["--title", "t", "--dimension", "Product", "--measure", "{dimension}",
                                       "--time", "Month", "--out", "{out}/slot-dash.html"],
                      ["slot-dash.html"], DASH_T,
                      {"nb": ["{dimension} per Product"], "en": ["{dimension} by Product"]}),
        "slot-cube": (CUBE, name_csv, ["--dims", "Product", "--time", "Month", "--measures", "Amount:sum",
                                       "--title", "t", "--feedback-to", "hei@example.org",
                                       "--out", "{out}/slot-cube.html"],
                      ["slot-cube.html"], CUBE_T + FB, ["source-{rows}.csv"]),
        "tok-dash": (DASH, tok_csv, ["--title", evil, "--dimension", "Product", "--measure", "Amount",
                                     "--time", "Month", "--requested-by", evil, "--source", evil,
                                     "--feedback-to", "hei@example.org", "--out", "{out}/tok-dash.html"],
                     ["tok-dash.html"], DASH_T + FB, [evil, "{{T:reset}}"]),
        "tok-cube": (CUBE, tok_csv, ["--dims", "Product", "--time", "Month", "--measures", "Amount:sum",
                                     "--title", evil, "--requested-by", evil,
                                     "--feedback-to", "hei@example.org", "--out", "{out}/tok-cube.html"],
                     ["tok-cube.html"], CUBE_T + FB, [evil]),
        "tok-process": (PROC, spec, ["{in}", "--out", "{out}/tok-process.html"], ["tok-process.html"],
                        ["process-diagram"], ["&#123;&#123;T:reset&#125;&#125;", "&#123;n&#125;"]),   # braces are escaped
    }
    for name, (builder, src, args, files, tables, _literals) in probes.items():
        CASES[name] = (builder, src, args, files, tables)
    return probes


def adversarial(work: pathlib.Path) -> None:
    """Data that looks like a format slot or a template token must come out untouched."""
    print("6. data that looks like a slot or a token")
    probes = register_probes(work)

    def lits_for(literals, lang):
        """A probe's expected strings: one list for both languages, or a list per language."""
        return literals[lang] if isinstance(literals, dict) else literals

    drifted, unpinned, seen = [], [], set()
    for name, (_b, _s, _a, _f, _t, literals) in probes.items():
        got_nb, _ = build_case(name, work / "adv-nb" / name, "nb")
        got_en, _ = build_case(name, work / "adv-en" / name, "en")
        for rel, blob in got_nb.items():
            key = f"{name}/{rel}"
            seen.add(key)
            if key not in ADV_BASELINE:
                unpinned.append(key)
            elif ADV_BASELINE[key] != sha(blob):
                drifted.append(key)
        if name.startswith("slot-"):      # the string the old builder wrote is still there, in both
            page = lambda built: "".join(b.decode("utf-8") for b in built.values())  # noqa: E731
            for lang, built in (("nb", got_nb), ("en", got_en)):
                for lit in lits_for(literals, lang):
                    if lit not in page(built):
                        drifted.append(f"{name} {lang}: {lit!r} was rewritten")
    chk("every probe file has a pinned hash", not unpinned, ", ".join(unpinned), n=len(seen))
    chk("every pinned hash belongs to a probe file (none is stale)",
        set(ADV_BASELINE) == seen, str(sorted(set(ADV_BASELINE) ^ seen)), n=len(ADV_BASELINE))
    chk("nb build equals the pinned old output byte for byte (slots and tokens as data)",
        not drifted, ", ".join(drifted), n=len(seen))
    for name, (_b, _s, _a, _f, _t, literals) in probes.items():
        page = "".join(b.decode("utf-8") for b in build_case(name, work / "adv-en" / name, "en")[0].values())
        en_lits = lits_for(literals, "en")
        missing = [lit for lit in en_lits if lit not in page]
        chk(f"{name}: en keeps {len(en_lits)} data string(s) as written", not missing, str(missing),
            n=len(en_lits))
    cube_page = build_case("slot-cube", work / "adv-en" / "slot-cube", "en")[0]["slot-cube.html"].decode("utf-8")
    chk("slot-cube: the file name was not filled in (no source-48.csv)", "source-48.csv" not in cube_page, n=1)
    for name in probes:
        del CASES[name]


def run(work: pathlib.Path) -> int:
    # 1 ---- tables
    print("1. tables")
    names = table_names()
    chk("there are strings tables", bool(names), n=len(names))
    problems = table_problems(i18n.DIR)
    nkeys = sum(len(i18n.load(n, "nb")) for n in names)
    chk("every key exists in both nb and en", not problems, "; ".join(problems), n=nkeys)

    used_bad, tokens = [], 0
    html_sources = sorted(TEMPLATES.glob("*.html"))
    for p in html_sources:
        keys = i18n.keys_used(p.read_text(encoding="utf-8"))
        table = i18n.path_for(p.stem)
        if not keys:
            continue
        if not table.exists():
            used_bad.append(f"{p.name}: has tokens, no table")
            continue
        have = set(i18n.load(p.stem, "nb"))
        tokens += len(keys)
        used_bad += [f"{p.name}: {{{{T:{k}}}}} not in the table" for k in sorted(keys - have)]
    chk("every {{T:key}} in a template exists in its table", not used_bad, "; ".join(used_bad), n=tokens)

    unused, total = [], 0
    code = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "tools").glob("*.py"))
    for n in names:
        tpl = TEMPLATES / f"{n}.html"
        text = (tpl.read_text(encoding="utf-8") if tpl.exists() else "") + code
        for key in i18n.load(n, "nb"):
            total += 1
            base = re.sub(r"_(one|other)$", "", key)     # n_steps_one is read as "n_steps"
            if f"{{{{T:{key}}}}}" not in text and f'"{key}"' not in text \
                    and f"'{key}'" not in text and f'"{base}"' not in text \
                    and f"'{base}'" not in text:
                unused.append(f"{n}.{key}")
    chk("every key is used by a template or a builder", not unused, ", ".join(unused), n=total)

    bad_chars = []
    for n in names:
        for key, v in i18n.load(n, "en").items():
            if any(c in v for c in FORBIDDEN_IN_EN):
                bad_chars.append(f"{n}.{key}")
    chk("no en value holds a quote, backslash, backtick or ${", not bad_chars, ", ".join(bad_chars), n=nkeys)

    # 2 ---- builds
    print("2. builds")
    nb, en = {}, {}
    for case in CASES:
        nb[case], _ = build_case(case, work / "nb" / case, "nb")
        en[case], _ = build_case(case, work / "en" / case, "en")
    chk("every builder builds with --lang nb", all(nb.values()), n=len(nb))
    chk("every builder builds with --lang en", all(en.values()), n=len(en))
    default, _ = build_case("dash-bundled", work / "default", None)
    chk("no --lang means nb", default == nb["dash-bundled"], n=len(default))

    # 3 ---- nb frozen
    print("3. nb output is what it was")
    drift, nfiles = [], 0
    for case, files in nb.items():
        for rel, blob in files.items():
            nfiles += 1
            want = BASELINE.get(f"{case}/{rel}")
            if want != sha(blob):
                drift.append(f"{case}/{rel}" + (" (no baseline)" if want is None else ""))
    chk("nb build equals the baseline sha256", not drift, ", ".join(drift), n=nfiles)

    # 4 ---- en clean
    print("4. en output has no Norwegian")
    bad, pages, looked_total = [], 0, 0
    for case, files in en.items():
        if not case.startswith("fx-"):
            continue
        tables = CASES[case][4]
        for rel, blob in files.items():
            pages += 1
            text = blob.decode("utf-8")
            problems, looked = en_problems(text, tables)
            looked_total += looked
            if rel.endswith(".html") and '<html lang="en">' not in text:
                problems.append("no <html lang=\"en\">")
            bad += [f"{case}/{rel}: {p}" for p in problems]
    chk("en pages: lang=en, no æøåÆØÅ, no nb strings", not bad, "; ".join(bad[:6]), n=pages)
    chk("... and the nb fragments were really looked for", looked_total > 0, n=looked_total)
    differ = sum(1 for c in en if c.startswith("fx-") for f in en[c] if en[c][f] != nb[c][f])
    chk("en differs from nb in every fx page", differ == sum(len(en[c]) for c in en if c.startswith("fx-"))
        - sum(1 for c in en if c.startswith("fx-") for f in en[c] if f.endswith("data.js")),
        f"{differ} differ", n=differ)

    # 5 ---- mutations
    print("5. a damaged table is noticed")
    broken = work / "broken"
    shutil.copytree(i18n.DIR, broken)
    victim = broken / "single-file-dashboard.strings"
    text = victim.read_text(encoding="utf-8")
    en_part = text.split("[en]", 1)[1]
    gone = en_part.replace("\nreset = Reset\n", "\n", 1)
    chk("mutation setup: the en key to delete is there", gone != en_part, n=1)
    victim.write_text(text.split("[en]", 1)[0] + "[en]" + gone, encoding="utf-8")
    seen = table_problems(broken)
    chk("a deleted en key is reported by the table check",
        len(seen) == 1 and "reset only in nb" in seen[0], "; ".join(seen), n=len(seen))
    _, r = build_case("fx-dash", work / "mut-build", "en", extra_env={"TUN_I18N_DIR": str(broken)},
                      check=False)
    chk("a deleted en key stops the en build", r.returncode != 0 and "reset" in r.stderr,
        f"exit {r.returncode}: {r.stderr[-200:]}", n=1)

    shutil.copyfile(i18n.DIR / "single-file-dashboard.strings", victim)
    leaked = victim.read_text(encoding="utf-8").replace("reset = Reset\n", "reset = Nullstill\n", 1)
    victim.write_text(leaked, encoding="utf-8")
    built, _ = build_case("fx-dash", work / "mut-nb", "en", extra_env={"TUN_I18N_DIR": str(broken)})
    problems, _ = en_problems(built["fx-dash.html"].decode("utf-8"), DASH_T + FB)
    chk("an nb string pasted into en is flagged", len(problems) == 1 and "reset" in problems[0],
        "; ".join(problems), n=len(problems))

    shutil.copyfile(i18n.DIR / "single-file-dashboard.strings", victim)
    leaked = victim.read_text(encoding="utf-8").replace("reset = Reset\n", "reset = Reset p\u00e5\n", 1)
    victim.write_text(leaked, encoding="utf-8")
    built, _ = build_case("fx-dash", work / "mut-letter", "en", extra_env={"TUN_I18N_DIR": str(broken)})
    problems, _ = en_problems(built["fx-dash.html"].decode("utf-8"), DASH_T + FB)
    chk("an \u00e5 pasted into en is flagged", len(problems) == 1 and "letter" in problems[0],
        "; ".join(problems), n=len(problems))

    shutil.copyfile(i18n.DIR / "single-file-dashboard.strings", victim)
    changed = victim.read_text(encoding="utf-8").replace("reset = Nullstill\n", "reset = Nullstill!\n", 1)
    victim.write_text(changed, encoding="utf-8")
    built, _ = build_case("fx-dash", work / "mut-frozen", "nb", extra_env={"TUN_I18N_DIR": str(broken)})
    chk("a changed nb string breaks the frozen hash",
        sha(built["fx-dash.html"]) != BASELINE["fx-dash/fx-dash.html"], n=len(built))

    adversarial(work)

    print("-" * 62)
    print(f"PASS: {passed}  FAIL: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
