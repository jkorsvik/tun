#!/usr/bin/env python3
"""Build the whole example: one dataset, three answers, and the page you land on.

The point is the last file. Each of the three artefacts beside it answers a different
question well, and a reader handed the folder still has no way to know which one to open.
`index.html` is that answer, and it is read out of each file's own provenance block rather
than maintained by hand.

Run: python3 examples/34-folder-index/build_example.py
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parents[1]
TOOLS = ROOT / "tools"

# Team, Sak, Mottatt, Status, Dager, Maaned, Belop. Twelve rows, invented, small on purpose.
ROWS = [
    ("Nord", "SAK-1001", "2026-09-03", "Lukket", 6, "2026-09", 41200),
    ("Nord", "SAK-1002", "2026-09-11", "Lukket", 11, "2026-09", 18750),
    ("Nord", "SAK-1003", "2026-10-02", "Apen", 4, "2026-10", 22400),
    ("Vest", "SAK-1004", "2026-09-05", "Lukket", 19, "2026-09", 63800),
    ("Vest", "SAK-1005", "2026-10-06", "Apen", 9, "2026-10", 30150),
    ("Vest", "SAK-1006", "2026-10-14", "Apen", 2, "2026-10", 9800),
    ("Midt", "SAK-1007", "2026-09-08", "Lukket", 24, "2026-09", 54300),
    ("Midt", "SAK-1008", "2026-10-01", "Lukket", 7, "2026-10", 27900),
    ("Ost", "SAK-1009", "2026-09-15", "Lukket", 31, "2026-09", 88400),
    ("Ost", "SAK-1010", "2026-10-03", "Apen", 5, "2026-10", 46100),
    ("Ost", "SAK-1011", "2026-10-09", "Apen", 12, "2026-10", 15600),
    ("Ost", "SAK-1012", "2026-10-20", "Apen", 1, "2026-10", 7300),
]
HEADER = "Team,Sak,Mottatt,Status,Dager,Maaned,Belop"


def write_csv(path: pathlib.Path, rows) -> None:
    lines = [HEADER] + [",".join(str(c) for c in row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(*args: str) -> None:
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit(f"builder failed: {' '.join(args)}\n{r.stderr[-1500:]}")
    print("  " + r.stdout.strip().splitlines()[0])


def main() -> int:
    data = HERE / "saker.csv"
    write_csv(data, ROWS)
    write_csv(HERE / "saker-september.csv", [r for r in ROWS if r[5] == "2026-09"])
    write_csv(HERE / "saker-oktober.csv", [r for r in ROWS if r[5] == "2026-10"])
    print(f"wrote {data.name} ({len(ROWS)} rows) and the two monthly extracts")

    common = ["--source", "Syntetisk eksempeldata (saker.csv)", "--requested-by", "Innsikt"]
    run(str(TOOLS / "build_dashboard.py"), "--data", str(data),
        "--title", "Saker per team og maned", "--dimension", "Team", "--measure", "Belop",
        "--time", "Maaned", "--filters", "Team,Status", *common,
        "--out", str(HERE / "saker-dashboard.html"))
    run(str(TOOLS / "build_register.py"), "--data", str(data),
        "--title", "Sakene selv", "--columns", "Sak,Team,Mottatt,Status,Dager",
        "--numeric", "Dager", "--sort", "Dager", "--desc", *common,
        "--out", str(HERE / "saker-register.html"))
    run(str(TOOLS / "build_comparison.py"),
        "--before", str(HERE / "saker-september.csv"),
        "--after", str(HERE / "saker-oktober.csv"),
        "--key", "Team", "--value", "Belop", "--title", "Belop per team: september mot oktober",
        "--before-label", "September", "--after-label", "Oktober", "--meaning", "up",
        *common, "--out", str(HERE / "saker-sammenligning.html"))
    run(str(TOOLS / "build_index.py"), "--dir", str(HERE),
        "--title", "Saker: tre svar og en inngang", "--requested-by", "Innsikt",
        "--out", str(HERE / "index.html"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
