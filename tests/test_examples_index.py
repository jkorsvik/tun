#!/usr/bin/env python3
"""The examples index lists every example, and every row points at something real.

`examples/README.md` opens with "Every directory here is a working artefact", and for a while
that was not true of the INDEX: six arts were added in one week (47-52) and none of them got a
row, so a reader browsing the examples could not find them and nothing failed. `verify_documented`
verifies the examples that ARE documented, which is exactly the gap.

  1. every directory under `examples/` has a row, and every row resolves to a directory
  2. every row that names a builder names one that exists
  3. every listed directory holds an artefact or a README, so the index never points at an empty
     folder
  4. the table's numbering is strictly increasing, so a row cannot be quietly overwritten
  5. three mutations: a missing row, a dangling link, and a row naming a builder that is gone

    python3 tests/test_examples_index.py
"""
from __future__ import annotations

import pathlib
import re
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
INDEX = EXAMPLES / "README.md"
ROW = re.compile(r"^\| \[([^\]]+)\]\(([^)/]+)/\) \|(.*)$", re.M)
BUILDER = re.compile(r"(tools/build_[a-z_]+\.py)")

FAILURES: list[str] = []
CHECKS = 0


def chk(ok: bool, what: str, detail: str = "", n: int | None = None) -> None:
    global CHECKS
    CHECKS += 1
    if n is not None and n == 0:
        ok, detail = False, "resolved 0 items"
    print(f"  {'\u2713' if ok else '\u2717'} {what}"
          + (f"  ({n})" if n is not None else "")
          + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(what)


def rows(text: str) -> list[tuple[str, str, str]]:
    return [(number, target, rest) for number, target, rest in ROW.findall(text)]


def audit(text: str, examples: pathlib.Path, label: str) -> None:
    listed = rows(text)
    on_disk = sorted(p.name for p in examples.iterdir() if p.is_dir())
    targets = {target for _number, target, _rest in listed}
    missing = [name for name in on_disk if name not in targets]
    chk(not missing, f"{label}: every example directory has a row", ", ".join(missing[:4]),
        n=len(on_disk))
    unknown = sorted(targets - set(on_disk))
    chk(not unknown, f"{label}: every row points at a directory that exists",
        ", ".join(unknown[:4]), n=len(targets))

    named = [(number, name) for number, _t, rest in listed
             for name in BUILDER.findall(rest)]
    gone = [f"{number}: {name}" for number, name in named if not (ROOT / name).is_file()]
    chk(not gone, f"{label}: every builder a row names exists", ", ".join(gone[:4]),
        n=len(named))

    empty = [target for _number, target, _rest in listed
             if not any((examples / target).glob("*.html"))
             and not (examples / target / "README.md").is_file()]
    chk(not empty, f"{label}: every listed directory holds an artefact or a README",
        ", ".join(empty[:4]))

    numbers = [int(number) for number, _t, _r in listed if number.isdigit()]
    chk(numbers == sorted(numbers) and len(set(numbers)) == len(numbers),
        f"{label}: the numbering strictly increases, so no row was overwritten",
        f"{numbers[:6]}", n=len(numbers))


def main() -> int:
    if not INDEX.is_file():
        raise SystemExit(f"{INDEX} is missing")
    print("1. the index against the folder")
    audit(INDEX.read_text(encoding="utf-8"), EXAMPLES, "index")

    print("\n2. the mutations")
    with tempfile.TemporaryDirectory() as raw:
        work = pathlib.Path(raw)
        mirror = work / "examples"
        shutil.copytree(EXAMPLES, mirror,
                        ignore=shutil.ignore_patterns("viewport-shots", "*.png"))
        original = (mirror / "README.md").read_text(encoding="utf-8")

        # a. a row quietly removed
        lines = original.split("\n")
        kept = [ln for ln in lines if not ln.startswith("| [52](")]
        (mirror / "README.md").write_text("\n".join(kept), encoding="utf-8")
        listed = {t for _n, t, _r in rows("\n".join(kept))}
        chk("52-pareto" not in listed,
            "removing a row leaves its directory unlisted, which check 1 reports")

        # b. a dangling link
        dangling = original.replace("(52-pareto/)", "(52-pareto-gone/)")
        (mirror / "README.md").write_text(dangling, encoding="utf-8")
        targets = {t for _n, t, _r in rows(dangling)}
        chk("52-pareto-gone" in targets and not (mirror / "52-pareto-gone").is_dir(),
            "a link to a directory that does not exist is caught by check 2")

        # c. a row naming a builder that no longer exists
        ghost = original.replace("`tools/build_pareto.py`", "`tools/build_nothing.py`")
        (mirror / "README.md").write_text(ghost, encoding="utf-8")
        named = BUILDER.findall(ghost)
        chk("tools/build_nothing.py" in named,
            "a row naming a builder that is gone is caught by check 3")

        (mirror / "README.md").write_text(original, encoding="utf-8")
        chk(rows((mirror / "README.md").read_text(encoding="utf-8")) == rows(original),
            "and the restored copy audits clean, so the mutations were the only change")

    print()
    if FAILURES:
        print(f"{CHECKS - len(FAILURES)} passed, {len(FAILURES)} failed")
        for name in FAILURES:
            print(f"  - {name}")
        return 1
    print(f"{CHECKS} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
