#!/usr/bin/env python3
"""
check_no_real_data.py — refuse to commit real data or personal data.

Stdlib only. No browser, no install.

    python3 tools/check_no_real_data.py           # scan tracked files
    python3 tools/check_no_real_data.py --list    # print the resolved scope and exit

Why this exists
---------------
Two real cases were worked inside this repository as learning material. One of them was
swept onto main by a single `git add -A`: 142 files, including a survey export with company
names, contact persons, job titles and e-mail addresses for 13 respondents. The branches
have since been rewritten, but one server-held pull-request ref still serves those files,
and nothing we control can delete it. See docs/20-publication-readiness.md.

`.gitignore` alone was not enough, because the directory that leaked was ignored only
*after* it leaked. This is the check that does not depend on remembering.

Two independent rules, because they fail differently:

  1. Shape:    text that looks like personal data anywhere in a tracked file.
  2. Location: a data file tracked outside a place where synthetic data is expected.

Rule 2 is the one that catches a real export with an innocent shape. Rule 1 is the one that
catches a contact address pasted into prose.

Findings are reported redacted. A gate that prints the personal data it found has moved the
problem into the log rather than solved it.

Exit codes
    0  nothing found
    1  at least one finding
    2  the scope could not be resolved, or resolved empty (never reported as clean)
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tree_scan  # noqa: E402

G, R, Y, D, B, Z = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
if not sys.stdout.isatty():
    G = R = Y = D = B = Z = ""

# Binary or generated formats where a text scan means nothing.
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".mov", ".xlsx", ".xls",
}

# ---------------------------------------------------------------------------
# Rule 2: where a tracked data file is allowed to be
# ---------------------------------------------------------------------------
# Every entry needs a reason. "It was already there" is not one: that is exactly how the
# leak happened. If a new entry cannot be justified in one line, the data does not belong
# in the repository.
DATA_SUFFIXES = {".csv", ".tsv", ".json", ".geojson", ".ndjson", ".parquet", ".xlsx", ".xls"}

ALLOWED_DATA: dict[str, str] = {
    "examples/01-hello-dashboard/salgsdata.csv":
        "synthetic sales figures, written by hand for the hello example",
    "examples/15-chart-library-comparison-poc/data/fylker-6.geojson":
        "public county geometry, no personal or commercial content",
    "examples/26-kpi-board/sykefravaer.csv":
        "seeded synthetic sick-leave days, reproducible with the generate_data.py beside it",
    "examples/27-survey-board/survey.csv":
        "invented survey answers, deterministic from the generate_data.py beside it",
    "examples/28-one-dataset-three-artefacts/saksbehandling.csv":
        "invented case-handling hours, seeded from 20261024 in this commit's message",
    "examples/37-printable-onepager/salgsdata.csv":
        "seeded synthetic monthly sales, deterministic from the generate_data.py beside it",
    "examples/29-audience-split/salg-alle.csv":
        "invented sales rows for three made-up teams, deterministic from the generate_data.py beside it",
    "examples/29-audience-split/salg-team-nord.csv":
        "the same rows filtered to one team on disk; written by the same generate_data.py",
    "examples/30-json-to-dashboard/ordrer.json":
        "an invented API response, 27 records, deterministic from the generate_data.py beside it",
    "examples/30-json-to-dashboard/salg.csv":
        "the same 27 records flattened by the flatten.py beside it; no other source",
    "examples/31-survey-crosstab/survey-wide.csv":
        "invented survey answers, 288 respondents, written out as a matrix in the generate_data.py beside it",
    "examples/32-rows-register/avvik.csv":
        "invented deviation cases, 1200 rows, deterministic from the generate_data.py beside it",
    "examples/35-timeline/milepaeler.csv":
        "invented programme milestones, 13 rows, deterministic from the generate_data.py beside it",
    "tests/fixtures/i18n-distribution-en.csv":
        "invented case days with English column names, written by hand for the i18n check",
    "examples/39-scorecard/manedstall.csv":
        "invented monthly figures for seven made-up measures, deterministic from the "
        "generate_data.py beside it (seed 39)",
    "tests/fixtures/i18n-scorecard-en.csv":
        "invented monthly figures with English column names, written by hand for the i18n check",
    "examples/38-distribution/saksbehandlingstid.csv":
        "invented case-handling days, 423 rows, four made-up units, deterministic from the "
        "generate_data.py beside it (seed 38)",
    "examples/43-heatmap/henvendelser.csv":
        "invented enquiries per made-up unit per week, 46 rows over six made-up units and "
        "eight weeks, with two cells deliberately absent, deterministic from the "
        "generate_data.py beside it (seed 43)",
    "examples/44-cohort/kunder.csv":
        "invented accounts and their activity dates, 1087 rows over 496 made-up ids and "
        "nine months, deterministic from the lag_data.py beside it (seed 44)",
    "examples/46-rank-change/produkter.csv":
        "invented revenue for thirteen made-up products over two made-up quarters, 24 rows, "
        "with one product arriving, one leaving and one shared rank, deterministic from the "
        "lag_data.py beside it (no seed: the values are written out)",
    "examples/53-sankey/kanaler.csv":
        "eleven invented channel-to-outcome flows with invented counts, written out literally in "
        "the FLOWS table of the generate_data.py beside it; the balance is exact by construction, "
        "not measured from anything",
    "examples/52-pareto/henvendelser.csv":
        "twenty-two invented enquiry reasons with invented counts, written out literally in the "
        "ROWS table of the generate_data.py beside it; no real case, customer or unit",
    "examples/51-bullet/dekning.csv":
        "fourteen invented units with an invented coverage figure and target, written out "
        "literally in the ROWS table of the generate_data.py beside it; no real unit, target "
        "or decision",
    "examples/50-calendar/hendelser.csv":
        "353 invented days of an invented year from a fixed arithmetic sequence in the "
        "generate_data.py beside it; the twelve missing days and the five zero days are "
        "stated sets in that file, not a measurement",
    "examples/49-gantt/fremdrift.csv":
        "twelve invented tasks of an invented programme, hand-written in the PLAN table of the "
        "generate_data.py beside it; no real project, department or date",
    "examples/48-boxplot/saksbehandlingstid.csv":
        "341 invented case durations across eight invented units, generated by a fixed "
        "arithmetic sequence in the generate_data.py beside it; the slow tail is a stated "
        "share of the rows, not a measurement",
    "examples/47-scatter/enheter.csv":
        "eighteen invented districts with invented answer times and scores, written out "
        "literally in the generate_data.py beside it; the one outlier row is a stated choice "
        "of the example, not a measurement",
    "examples/45-smallmultiples/ko.csv":
        "invented queue length per made-up unit per week, 84 values over nine units and "
        "ten weeks, two unit-weeks absent on purpose, deterministic from the lag_data.py "
        "beside it (seed 45)",
    "examples/42-funnel/soknader.csv":
        "invented application records, 400 made-up case ids over four stages, deterministic "
        "from the generate_data.py beside it (a hash of each id, no seed)",
    "examples/41-composition/bemanning.csv":
        "invented hours per task per quarter for a made-up team, two rows each, deterministic "
        "from the generate_data.py beside it",
    "examples/40-waterfall/omsetning.csv":
        "invented monthly revenue for ten made-up products over three months, two transaction "
        "rows each, deterministic from the generate_data.py beside it",
    "examples/36-review-roundtrip/saksbehandling.csv":
        "invented case-handling cost rows, 96, four made-up units and three case types, "
        "deterministic from the build_example.py beside it",
    "plugin/manifest.json":
        "configuration, not data",
    ".claude-plugin/plugin.json":
        "configuration, not data: Claude Code requires this exact path",
    ".claude-plugin/marketplace.json":
        "configuration, not data: Claude Code requires this exact path",
    "tools/core_generic_baseline.json":
        "gate state: file paths and match counts for the core boundary ratchet, no content",
}


def data_file_is_allowed(rel: str) -> bool:
    if rel in ALLOWED_DATA:
        return True
    # A plugin manifest and a plugin's tenant facts are configuration, not data, and both are
    # named by the contract's layout (docs/22-plugin-contract.md) rather than chosen per
    # plugin. Recognising the shape means a new plugin does not have to be allowlisted to be
    # legal, which is the same reasoning that makes templates/ a scope rule rather than a debt
    # entry. Only those two names, and only at the plugin's root.
    parts = rel.split("/")
    if len(parts) == 3 and parts[0] == "plugins" and parts[2] in ("manifest.json", "tenant-facts.json"):
        return True
    # The same holds for the manifest of a plugin's RAIWork Marketplace bundle, which the
    # Marketplace requires at the bundle root under exactly this name.
    if len(parts) == 5 and parts[0] == "plugins" and parts[2:] == ["raiwork", "bundle", "manifest.json"]:
        return True
    # Nothing else is allowed: being synthetic is not a location. A generator beside the
    # data proves reproducibility, not that the file belongs in git — examples/03 keeps its
    # 207 MB extract out of the repository with .gitignore, which costs it no allowlist
    # entry because the file was never tracked. Add the path here, with a reason, or keep
    # the data out.
    return False


# ---------------------------------------------------------------------------
# Rule 1: shapes that indicate personal data
# ---------------------------------------------------------------------------
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_NO = re.compile(r"\+47[\s-]?(?:\d[\s-]?){8}\b")
DIGITS_9 = re.compile(r"(?<!\d)\d{9}(?!\d)")
DIGITS_11 = re.compile(r"(?<!\d)\d{11}(?!\d)")

# Domains that cannot belong to a person: reserved-for-documentation names (RFC 2606) and
# the obvious local ones. `tun.community` is the project's own domain: an address there is a
# published role address (hei@, no personal mailbox), and it appears in the docs and on the
# landing page on purpose. Listing the domain, not a literal address, so a second role
# address does not need a second exemption; a personal mailbox is not created there.
NON_PERSON_DOMAINS = {
    "example.com", "example.org", "example.net", "example.edu",
    "localhost", "invalid", "test", "domain.com", "eksempel.no.invalid",
    "tun.community",
}


def _orgnr_valid(number: str) -> bool:
    """Norwegian organisation number: nine digits, mod-11 with weights 3,2,7,6,5,4,3,2.

    The checksum is what makes this usable as a gate. A bare nine-digit regex fires on
    coordinates and identifiers: examples/15's geojson contains 884287641, which is not a
    valid organisation number, while Eksempel AS's own public registry number is. That valid number
    is deliberately not written here, because this gate scans its own source.
    """
    if len(number) != 9 or not number.isdigit():
        return False
    weights = (3, 2, 7, 6, 5, 4, 3, 2)
    total = sum(int(d) * w for d, w in zip(number[:8], weights))
    check = 11 - (total % 11)
    if check == 11:
        check = 0
    return check != 10 and check == int(number[8])


def _fnr_valid(number: str) -> bool:
    """Norwegian national identity number: eleven digits, two mod-11 control digits.

    Both control digits plus a plausible day and month are required. Without the checksum
    this pattern fires on timestamps and long integers.
    """
    if len(number) != 11 or not number.isdigit():
        return False
    day, month = int(number[0:2]), int(number[2:4])
    # D-numbers add 40 to the day; H-numbers add 40 to the month.
    if not (1 <= day <= 71 and 1 <= month <= 52):
        return False
    w1 = (3, 7, 6, 1, 8, 9, 4, 5, 2)
    w2 = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    k1 = 11 - (sum(int(d) * w for d, w in zip(number[:9], w1)) % 11)
    if k1 == 11:
        k1 = 0
    k2 = 11 - (sum(int(d) * w for d, w in zip(number[:10], w2)) % 11)
    if k2 == 11:
        k2 = 0
    return k1 < 10 and k2 < 10 and k1 == int(number[9]) and k2 == int(number[10])


def _inside_hash(line: str, start: int, end: int) -> bool:
    """True when the match sits inside a longer hex run: a digest, not data.

    A sha256 pinned in a test is 64 hex characters, and one of them will contain a
    nine-digit run that passes the mod-11 checksum about one time in eleven. The
    pin is not personal data, so the gate must not fire on it — but the exemption
    is narrow on purpose: it needs a hex run of at least 16 characters around the
    match, which no hand-written identifier has.
    """
    hexdigits = set("0123456789abcdefABCDEF")
    left, right = start, end
    while left > 0 and line[left - 1] in hexdigits:
        left -= 1
    while right < len(line) and line[right] in hexdigits:
        right += 1
    return right - left >= 16


def redact(value: str) -> str:
    """Show enough to locate it, not enough to leak it.

    The domain is redacted as well as the local part. In this repository's own leak the
    respondents were companies, so the domain *was* the identifying half: printing
    `g***@somecompany.no` names the company as surely as the full address does. The first
    run of this gate made exactly that mistake and listed twelve real companies into a
    terminal. The public suffix is kept because it is not identifying and helps tell a
    Norwegian address from a foreign one.
    """
    if "@" in value:
        local, _, domain = value.partition("@")
        name, dot, tld = domain.rpartition(".")
        return f"{local[:1]}***@{name[:1]}***{dot}{tld}"
    return f"{value[:2]}***{value[-1:]} ({len(value)} digits)"


def scan_text(rel: str, text: str) -> list[tuple[int, str, str]]:
    """Return [(line number, kind, redacted value)] for one file."""
    findings: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in EMAIL.finditer(line):
            value = match.group(0)
            before = line[:match.start()]
            # Not addresses: URL userinfo and scp-style git remotes.
            #   ssh://git@host/x.git      -> the match is preceded by "//"
            #   eksempel@example.com:org/repo  -> the match is followed by ":"
            if before.endswith("//"):
                continue
            if line[match.end():match.end() + 1] == ":":
                continue
            if value.rpartition("@")[2].lower() in NON_PERSON_DOMAINS:
                continue
            findings.append((lineno, "e-mail address", redact(value)))
        for match in PHONE_NO.finditer(line):
            findings.append((lineno, "Norwegian phone number", redact(match.group(0))))
        for match in DIGITS_9.finditer(line):
            if _inside_hash(line, match.start(), match.end()):
                continue
            if _orgnr_valid(match.group(0)):
                findings.append((lineno, "organisation number", redact(match.group(0))))
        for match in DIGITS_11.finditer(line):
            if _inside_hash(line, match.start(), match.end()):
                continue
            if _fnr_valid(match.group(0)):
                findings.append((lineno, "national identity number", redact(match.group(0))))
    return findings


# ---------------------------------------------------------------------------
# Reusable by example builders (rule 1 inverted: prove the data IS synthetic)
# ---------------------------------------------------------------------------
def assert_synthetic(rows: list[dict], columns: tuple[str, ...],
                     vocabulary: dict[str, str], *, context: str = "data") -> None:
    """Fail unless every row matches a declared synthetic vocabulary.

    Lifted from examples/17's builder, which already refused to write a data file whose
    values fell outside a per-column allowlist. Kept here so every builder shares one
    implementation instead of each example growing its own.

    An allowlist is the right shape for generated data: it states what the values may be,
    so a real value that happens to look ordinary still fails. A denylist cannot do that.
    """
    problems: list[str] = []
    for number, row in enumerate(rows, start=1):
        if sorted(row) != sorted(columns):
            problems.append(f"row {number} has columns {sorted(row)}, "
                            f"expected {sorted(columns)}")
            continue
        for column, pattern in vocabulary.items():
            if not re.fullmatch(pattern, str(row[column])):
                problems.append(f"row {number}: {column} is outside the synthetic "
                                f"vocabulary /{pattern}/")
    if problems:
        raise SystemExit(f"FAIL: {context} is not synthetic:\n  - "
                         + "\n  - ".join(problems[:20]))


# ---------------------------------------------------------------------------
def tracked_text(repo: pathlib.Path = tree_scan.REPO) -> list[str]:
    """Every tracked file worth reading as text. Raises ScopeError on an empty scope."""
    files = tree_scan.tracked_paths(repo)
    keep = [f for f in files if pathlib.Path(f).suffix.lower() not in SKIP_SUFFIXES]
    if not keep:
        raise tree_scan.ScopeError(
            "resolved zero tracked text files — the scope is broken, not clean")
    return keep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="print the scope and exit")
    ap.add_argument("--quiet", action="store_true", help="print only findings")
    args = ap.parse_args()

    try:
        files = tracked_text()
        all_tracked = tree_scan.tracked_paths()
    except tree_scan.ScopeError as exc:
        print(f"{R}✗ scope error{Z} {exc}", file=sys.stderr)
        return 2

    if args.list:
        for rel in files:
            print(rel)
        return 0

    shape_findings: list[tuple[str, int, str, str]] = []
    for rel in files:
        path = tree_scan.REPO / rel
        if not path.exists():
            raise SystemExit(f"tracked file missing from the working tree: {rel}")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"{Y}⚠{Z} could not read {rel}: {exc}", file=sys.stderr)
            continue
        for lineno, kind, shown in scan_text(rel, text):
            shape_findings.append((rel, lineno, kind, shown))

    location_findings = [
        rel for rel in all_tracked
        if pathlib.Path(rel).suffix.lower() in DATA_SUFFIXES
        and not data_file_is_allowed(rel)
    ]

    if not args.quiet:
        print(f"{B}real-data gate{Z}")
        print(f"  scope: {len(files)} tracked text file(s), "
              f"{len(all_tracked)} tracked file(s) total")
        print("─" * 72)
        icon, colour = ("✗", R) if shape_findings else ("✓", G)
        print(f"  {colour}{icon}{Z} personal-data shapes   "
              f"{len(shape_findings)} finding(s)")
        icon, colour = ("✗", R) if location_findings else ("✓", G)
        print(f"  {colour}{icon}{Z} data-file locations    "
              f"{len(location_findings)} unexpected file(s)  "
              f"{D}({len(ALLOWED_DATA)} allowed){Z}")
        print("─" * 72)

    if shape_findings:
        print(f"\n{R}✗ FAIL{Z} — personal-data shapes found (values redacted):")
        for rel, lineno, kind, shown in shape_findings:
            print(f"    {rel}:{lineno}  {kind}: {shown}")
        print("\n  If this is genuinely not personal data, make the pattern narrower or"
              "\n  add the specific exclusion with a reason. Do not widen the gate.")

    if location_findings:
        print(f"\n{R}✗ FAIL{Z} — data file(s) tracked outside an expected location:")
        for rel in location_findings:
            print(f"    {rel}")
        print("\n  Real extracts belong outside git: work/ and dashboards/ are ignored."
              "\n  If this file is synthetic, add it to ALLOWED_DATA in"
              " tools/check_no_real_data.py\n  with a one-line reason, or better, ship the"
              " generator and leave the data untracked\n  (see examples/03).")

    if shape_findings or location_findings:
        return 1
    if not args.quiet:
        print(f"\n{G}✓ PASS{Z} — no personal-data shapes, no unexpected data files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
