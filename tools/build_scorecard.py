#!/usr/bin/env python3
"""Build a standalone scorecard: many measures, one period, with their targets and history.

The monthly management report has the same shape almost everywhere: a short list of
measures, each with this period's figure, the change, the target and a status. Two things
make it useful, and both were missing from this repository until now: a trend small enough to
sit beside the number, and a target to be measured against.

    python3 tools/build_scorecard.py \\
      --data examples/39-scorecard/manedstall.csv \\
      --title "Manedsrapport september 2026" \\
      --source "Syntetisk eksempeldata (manedstall.csv)" \\
      --requested-by "Kvalitetsavdelingen" \\
      --green-at 1.00 --amber-at 0.95 \\
      --out examples/39-scorecard/manedsrapport.html

What is built in, rather than left to whoever assembles the file:

  * **no direction, no verdict.** An increase is good news for revenue and bad news for
    complaints, and this file cannot know which it holds. Direction comes from a column or a
    flag; without one the page prints the figures and says nothing about whether they are
    good. Colour is the last thing a reader should be able to misread.
  * **no bands, no status word.** "Near target" is a policy. `--green-at` and `--amber-at`
    are declared as fractions of the target, and without them there is no status at all.
  * **a missing period is a break, never a straight line.** A series with a hole draws two
    segments, and the change against a period that is not in the data reads as a dash. An
    interpolation would be a figure nobody measured.
  * **the gap is one subtraction, the same way round for every measure**: latest minus
    target. Only the status word knows which direction is good, so the number a reader
    checks by hand is the number on the page.
  * **every figure is also in a table**, period by period, so the page can be checked
    instead of trusted. The suite recomputes each sparkline point from that table.
  * **a measure with no unit is refused by name.** A scorecard whose figures have no unit is
    a page of numbers nobody can act on.
  * **there is no script.** A scorecard is a snapshot with its history behind it; a filter
    would be a different artefact.

Stdlib only, like the rest of tools/. Python 3.8+.
"""
from __future__ import annotations

import argparse
import html
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import build_size  # noqa: E402
import build_stamp  # noqa: E402
import feedback_link  # noqa: E402
import i18n  # noqa: E402
import tun_core  # noqa: E402
import tun_tokens  # noqa: E402
from tun_tokens import strip_css_comments  # noqa: E402
from tun_core import NOT_STATED, die  # noqa: E402

TEMPLATE = ROOT / "templates" / "scorecard.html"
STRINGS = "scorecard"
MAX_KPIS = 24                 # above this a scorecard is a wall, not a page
MAX_PERIODS = 36              # three years of months, which is more than a card can show
SPARK_PERIODS = 12            # the card shows a year; the table shows everything
MAX_BYTES = 40 * 1024 * 1024

# The sparkline canvas. No rendered text at all, so a card can shrink to a phone without
# taking any type under the floor: the labels live in HTML around the drawing.
W = 240
H = 60
PAD = 6

DIRECTIONS = {"opp": "up", "up": "up", "ned": "down", "down": "down", "": ""}
# The three status words, named literally: a key built from a variable is a key the i18n
# gate cannot see, and a table entry nobody can find is one nobody translates.
STATUS_WORDS = {"green": "status_green", "amber": "status_amber", "red": "status_red"}
PERIOD = re.compile(r"^(\d{4})-(\d{2})$")


# -------------------------------------------------------------------------------- periods
def parse_period(text: str, where: str) -> str:
    """YYYY-MM, refused by name otherwise.

    A month is the unit of a scorecard. Accepting a full date as well would mean deciding
    which day of the month a period starts, and two files that disagree about that put the
    same figure in two different columns.
    """
    value = text.strip()
    m = PERIOD.match(value)
    if not m or not 1 <= int(m.group(2)) <= 12:
        die(f"{where}: {text!r} is not a period. Write it as YYYY-MM (2026-09).")
    return value


def shift_year(period: str, years: int = -1) -> str:
    year, month = period.split("-")
    return f"{int(year) + years:04d}-{month}"


def period_label(period: str, lang: str) -> str:
    """The period as a reader writes it: sep 2026 in Norwegian, Sep 2026 in English."""
    year, month = period.split("-")
    names = MONTH_NB if lang == "nb" else MONTH_EN
    return f"{names[int(month) - 1]} {year}"


MONTH_NB = ("jan", "feb", "mar", "apr", "mai", "jun", "jul", "aug", "sep", "okt", "nov", "des")
MONTH_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


# -------------------------------------------------------------------------------- numbers
def decimals_of(values: list[float]) -> int:
    """Per measure: no decimals for whole numbers, at most two otherwise."""
    if all(float(v).is_integer() for v in values):
        return 0
    return 2 if any(round(v, 1) != round(v, 2) for v in values) else 1


def fmt(value: float, lang: str, dec: int) -> str:
    text = f"{value:,.{dec}f}"
    if lang == "nb":
        return text.replace(",", "\u00a0").replace(".", ",")
    return text.replace(",", "\u2009")


def signed(value: float, lang: str, dec: int) -> str:
    """A change, with the sign the reader needs to see. A minus sign is a real minus."""
    if abs(value) < 10 ** (-dec) / 2:
        return fmt(0.0, lang, dec)
    return ("\u2212" if value < 0 else "+") + fmt(abs(value), lang, dec)


def ratio_to_target(latest: float, target: float, direction: str) -> float | None:
    """How far the latest figure is towards its target, as a number around 1.

    1 or more means at or better than the target, whichever direction is good: an increase
    is measured as latest / target, a decrease as target / latest. None when the division
    would be by zero, because an infinite ratio is not a status, it is a missing denominator.
    """
    if direction == "up":
        return None if target == 0 else latest / target
    if direction == "down":
        return None if latest == 0 else target / latest
    return None


def status_of(ratio: float | None, green: float | None, amber: float | None) -> str:
    """green / amber / red / none, from the declared bands and nothing else."""
    if ratio is None or green is None or amber is None:
        return ""
    if ratio >= green:
        return "green"
    if ratio >= amber:
        return "amber"
    return "red"


# ----------------------------------------------------------------------------------- load
def load(path: pathlib.Path, flags: dict, lower: set[str],
         units: dict[str, str]) -> tuple[list[dict], list[str], int]:
    """One entry per measure, with its series over the periods the file holds."""
    rows = tun_core.read_rows(path)
    if not rows:
        die(f"{path.name} has no rows")
    header = tun_core.columns(rows)
    for role in ("kpi", "period", "value", "target", "direction", "unit"):
        name = flags[role]
        if name and name not in header and role not in ("target", "direction", "unit"):
            die(f"--{role}-col {name!r} is not a column in {path.name}. "
                f"Available: {', '.join(header)}")

    series: dict[str, dict] = {}
    order: list[str] = []
    periods: set[str] = set()
    for i, row in enumerate(rows, 2):
        name = str(row.get(flags["kpi"]) or "").strip()
        if not name:
            continue
        period = parse_period(str(row.get(flags["period"]) or ""), f"{path.name}:{i}")
        value = tun_core.to_number(row.get(flags["value"]))
        if value is None:
            die(f"{path.name}:{i}: {flags['value']} is {str(row.get(flags['value']) or '').strip()!r}, "
                f"which is not a number. A row that cannot be read is refused, not skipped.")
        target = tun_core.to_number(row.get(flags["target"])) if flags["target"] in header else None
        raw_direction = ""
        if flags["direction"] in header:
            word = str(row.get(flags["direction"]) or "").strip().lower()
            if word not in DIRECTIONS:
                die(f"{path.name}:{i}: {flags['direction']} is {word!r}. Write opp/ned "
                    f"(or up/down), or leave it empty and pass --lower-is-better.")
            raw_direction = DIRECTIONS[word]
        unit = str(row.get(flags["unit"]) or "").strip() if flags["unit"] in header else ""
        if name not in series:
            series[name] = {"name": name, "unit": "", "direction": "", "targets": {},
                            "values": {}, "order": []}
            order.append(name)
        entry = series[name]
        if period in entry["values"]:
            die(f"{path.name}:{i}: {name} has two figures for {period} "
                f"({entry['values'][period]} and {float(value)}). Summing them would invent a "
                f"third; keep one row per measure per period.")
        entry["values"][period] = float(value)
        entry["targets"][period] = float(target) if target is not None else None
        entry["order"].append(period)
        entry["unit"] = entry["unit"] or unit or units.get(name, "")
        entry["direction"] = entry["direction"] or raw_direction
        periods.add(period)

    if not series:
        die(f"{path.name} has no row with a name in {flags['kpi']!r}")
    if len(order) > MAX_KPIS:
        die(f"{len(order)} measures is more than the {MAX_KPIS} this page can hold. Split the "
            f"report, or build one file per audience.")
    if len(periods) > MAX_PERIODS:
        die(f"{len(periods)} periods is more than the {MAX_PERIODS} this page can show. "
            f"Cut the window: a scorecard is about now, with the history behind it.")

    for name in order:
        if not series[name]["unit"] and name in units:
            series[name]["unit"] = units[name]
    missing_unit = [name for name in order if not series[name]["unit"]]
    if missing_unit:
        die(f"{len(missing_unit)} measure(s) have no unit: {', '.join(missing_unit)}. A figure "
            f"without a unit is not actionable. Add an Enhet column, or pass "
            f"--unit \"{missing_unit[0]}=prosent\".")

    for name in order:
        entry = series[name]
        if name in lower:
            entry["direction"] = "down"
        entry["order"] = sorted(entry["order"])
    return [series[name] for name in order], sorted(periods), len(rows)


def split_units(pairs: list[str]) -> dict[str, str]:
    """--unit "Navn=prosent" as a name -> unit map, refused when it is not of that shape."""
    out: dict[str, str] = {}
    for pair in pairs:
        name, sep, unit = pair.partition("=")
        if not sep or not name.strip() or not unit.strip():
            die(f"--unit {pair!r} is not Name=unit. Example: --unit \"Sykefravaer=prosent\".")
        out[name.strip()] = unit.strip()
    return out


# ------------------------------------------------------------------------------ sparkline
def sparkline(entry: dict, periods: list[str], lang: str, dec: int, t: dict
              ) -> tuple[str, str]:
    """The drawing, and the sentence under it.

    Every point's own value is in a <title> and in the table below, so the picture is a shape
    and the numbers are somewhere a reader can check. The scale is the measure's own, which
    is why the sentence under each card names the lowest and highest value.
    """
    shown = periods[-SPARK_PERIODS:] if len(periods) > SPARK_PERIODS else periods
    present = [(p, entry["values"][p]) for p in shown if p in entry["values"]]
    if not present:
        return "", ""
    values = [v for _, v in present]
    targets = [entry["targets"].get(p) for p, _ in present if entry["targets"].get(p) is not None]
    target = targets[-1] if targets else None
    lo, hi = min(values), max(values)
    if target is not None:
        lo, hi = min(lo, target), max(hi, target)
    if lo == hi:                       # a flat line has no scale, so give it one
        lo, hi = lo - 1.0, hi + 1.0
    step = (W - 2 * PAD) / max(1, len(shown) - 1)

    def x(index: int) -> float:
        return PAD + index * step

    def y(value: float) -> float:
        return H - PAD - (value - lo) / (hi - lo) * (H - 2 * PAD)

    parts = [f'<svg class="spark" viewBox="0 0 {W} {H}" role="img" aria-labelledby="s-{apt(entry["name"])}-t" '
             f'preserveAspectRatio="none">',
             f'<title id="s-{apt(entry["name"])}-t">'
             f'{html.escape(i18n.fill(t["svg_title"], kpi=entry["name"]))}</title>',
             f'<desc>{html.escape(i18n.fill(t["svg_desc"], kpi=entry["name"], values=", ".join(fmt(v, lang, dec) for v in values)))}</desc>']
    if target is not None:
        parts.append(f'<line class="spark-target" x1="{PAD}" y1="{y(target):.1f}" '
                     f'x2="{W - PAD}" y2="{y(target):.1f}"/>')
    # One polyline per run of adjacent periods, so a hole is a break and not a slope.
    run: list[tuple[int, float]] = []
    runs: list[list[tuple[int, float]]] = []
    for index, period in enumerate(shown):
        if period in entry["values"]:
            run.append((index, entry["values"][period]))
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)
    for segment in runs:
        for index, value in segment:
            parts.append(f'<circle class="spark-dot" cx="{x(index):.1f}" cy="{y(value):.1f}" '
                         f'r="2.2"><title>{html.escape(period_label(shown[index], lang))}: '
                         f'{html.escape(fmt(value, lang, dec))}</title></circle>')
        if len(segment) > 1:
            points = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in segment)
            parts.append(f'<polyline class="spark-line" points="{points}"/>')
    parts.append("</svg>")
    sentence = i18n.fill(t["sparkline"], n=len(present),
                         **{"from": period_label(present[0][0], lang),
                            "to": period_label(present[-1][0], lang),
                            "min": fmt(min(values), lang, dec),
                            "max": fmt(max(values), lang, dec)})
    if target is not None:
        sentence += " " + i18n.fill(t["sparkline_target"], target=fmt(target, lang, dec))
    return "".join(parts), sentence


def apt(text: str) -> str:
    """An id fragment for a measure's name: letters and digits, so an id is unique and legal."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "kpi"


# --------------------------------------------------------------------------------- images
def stat_block(entry: dict, lang: str, dec: int, green: float | None, amber: float | None,
               t: dict) -> tuple[str, bool]:
    """The figures under the drawing, and whether the measure carried a verdict."""
    order = entry["order"]
    latest_period = order[-1]
    latest = entry["values"][latest_period]
    previous = order[-2] if len(order) > 1 else ""
    yoy_period = shift_year(latest_period)
    target = entry["targets"].get(latest_period)
    if target is None and entry["targets"]:
        target = next((v for v in reversed(list(entry["targets"].values())) if v is not None), None)

    rows = []
    change = "" if not previous else signed(latest - entry["values"][previous], lang, dec)
    if previous and previous != _month_before(latest_period):
        # A comparison against a period further back than the one before is still a
        # comparison, but the page says which period it is against.
        change += " (" + period_label(previous, lang) + ")"
    rows.append((t["card_change"], change or t["no_prev"]))
    yoy = entry["values"].get(yoy_period)
    rows.append((t["card_yoy"], signed(latest - yoy, lang, dec) if yoy is not None
                 else t["no_yoy"]))
    rows.append((t["card_target"], fmt(target, lang, dec) if target is not None
                 else t["no_target"]))
    gap = ""
    if target is not None:
        gap = signed(latest - target, lang, dec)
    rows.append((t["card_gap"], gap or t["no_target"]))

    ratio = ratio_to_target(latest, target, entry["direction"]) if target is not None else None
    status = status_of(ratio, green, amber)
    if not entry["direction"]:
        verdict = t["no_direction"]
        status = ""
    elif target is None:
        verdict = t["no_target"]
    elif ratio is None:
        verdict = t["no_ratio"]
    elif not status:
        verdict = t["no_status"]
    else:
        verdict = t[STATUS_WORDS[status]]
    rows.append((t["card_status"], verdict))

    cells = "".join(f'<div><dt>{html.escape(k)}</dt>'
                    f'<dd{" class=\"s-" + status + "\"" if k == t["card_status"] and status else ""}>'
                    f'{html.escape(v)}</dd></div>' for k, v in rows)
    return cells, bool(status)


def _month_before(period: str) -> str:
    year, month = period.split("-")
    year, month = int(year), int(month)
    month -= 1
    if month == 0:
        year, month = year - 1, 12
    return f"{year:04d}-{month:02d}"


# ----------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True,
                    help="CSV with one row per measure per period")
    ap.add_argument("--kpi-col", default="KPI", help="the column with the measure's name")
    ap.add_argument("--period-col", default="Periode", help="the column with YYYY-MM")
    ap.add_argument("--value-col", default="Verdi", help="the column with the figure")
    ap.add_argument("--target-col", default="Mal",
                    help="the column with the target (optional; absent means no target)")
    ap.add_argument("--direction-col", default="Retning",
                    help="the column saying which direction is good: opp/ned, up/down")
    ap.add_argument("--unit-col", default="Enhet", help="the column with the unit")
    ap.add_argument("--unit", action="append", default=[], metavar="NAME=UNIT",
                    help="the unit for one measure, when the file has no unit column")
    ap.add_argument("--lower-is-better", default="", metavar="NAME,NAME",
                    help="measures where a smaller figure is better, for a file with no "
                         "direction column")
    ap.add_argument("--green-at", type=float, default=None, metavar="RATIO",
                    help="at or better than this fraction of the target is green "
                         "(1.00 means exactly on target). Without it there is no status")
    ap.add_argument("--amber-at", type=float, default=None, metavar="RATIO",
                    help="at or better than this fraction is amber; below it is red")
    ap.add_argument("--title", required=True)
    ap.add_argument("--source", default="", help="where the rows came from")
    ap.add_argument("--requested-by", default="", help="a role, not a person's name")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--feedback-to", default="", metavar="ADDRESS_OR_ISSUE_URL",
                    help=feedback_link.FLAG_HELP)
    i18n.add_lang_argument(ap)
    args = ap.parse_args(argv)
    t = i18n.load(STRINGS, args.lang)
    lang = args.lang

    if (args.green_at is None) != (args.amber_at is None):
        die("status needs both --green-at and --amber-at, or neither: one band alone cannot "
            "separate green from amber from red.")
    if args.green_at is not None and args.amber_at is not None and args.amber_at > args.green_at:
        die(f"--amber-at ({args.amber_at}) is above --green-at ({args.green_at}). Amber is the "
            f"band between the two, so it has to be the lower number.")

    lower = {name.strip() for name in args.lower_is_better.split(",") if name.strip()}
    units = split_units(args.unit)
    flags = {"kpi": args.kpi_col, "period": args.period_col, "value": args.value_col,
             "target": args.target_col, "direction": args.direction_col, "unit": args.unit_col}
    entries, periods, row_count = load(args.data, flags, lower, units)

    latest_overall = periods[-1]
    cards = []
    statuses = 0
    for entry in entries:
        dec = decimals_of(list(entry["values"].values()) + [v for v in entry["targets"].values() if v is not None])
        svg, sentence = sparkline(entry, periods, lang, dec, t)
        cells, has_status = stat_block(entry, lang, dec, args.green_at, args.amber_at, t)
        statuses += 1 if has_status else 0
        latest_period = entry["order"][-1]
        note = ""
        if latest_period != latest_overall:
            note = (f'<p class="stale">{html.escape(i18n.fill(t["latest_elsewhere"], period=period_label(latest_period, lang)))}</p>')
        cards.append(
            f'<article class="card">\n'
            f'  <h2>{html.escape(entry["name"])}'
            f'<span class="unit">, {html.escape(entry["unit"])}</span></h2>\n'
            f'  <p class="big">{html.escape(fmt(entry["values"][latest_period], lang, dec))}</p>\n'
            f'  <p class="when">{html.escape(t["card_latest"])} '
            f'{html.escape(period_label(latest_period, lang))}</p>\n'
            f'{note}\n'
            f'  {svg}\n'
            f'  <p class="spark-note">{html.escape(sentence)}</p>\n'
            f'  <dl>{cells}</dl>\n'
            f'</article>')

    table = table_html(entries, periods, lang, t)
    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)
    source = i18n.fill(t["source_line"], name=args.source or args.data.name,
                       rows=row_count, kpis=len(entries))
    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=built,
                                           source=source, lang=lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    notes = [t["note_direction"], t["note_scale"], t["note_hole"]]
    if args.green_at is None:
        notes.insert(1, t["note_bands"])

    # The colours come from tools/tokens/: one seam with every other artefact. auto_dark: a
    # reader whose system is dark gets a dark scorecard with no script.
    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css)))
    for token, value in {
        "{{TITLE}}": html.escape(args.title),
        "{{SUBTITLE}}": html.escape(i18n.fill(
            t["sub_line"], n=len(entries), periods=len(periods),
            **{"from": period_label(periods[0], lang),
               "to": period_label(periods[-1], lang)})),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(source),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{ROWS_INLINED}}": str(row_count),
        "{{PERIOD_COUNT}}": str(len(periods)),
        "{{CARDS}}": "\n".join(cards),
        "{{TABLE}}": table,
        "{{NOTES}}": "".join(f"<li>{html.escape(n)}</li>" for n in notes),
        "{{LEGEND}}": (f'<li><span class="ln"></span>{html.escape(t["legend_series"])}</li>'
                       f'<li><span class="ln dash"></span>{html.escape(t["legend_target"])}</li>'),
        "{{FEEDBACK_BLOCK}}": feedback,
    }.items():
        page = page.replace(token, value)
    if "{{" in page:
        left = sorted({piece.split("}}")[0] + "}}" for piece in page.split("{{")[1:]})
        die(f"the template still holds {', '.join(left)} after filling")

    data = page.encode("utf-8")
    if len(data) > MAX_BYTES:
        die(f"the file is {len(data) / 1048576:.1f} MB, over the 40 MB ceiling")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)

    print(f"measures      : {len(entries)}")
    print(f"periods       : {len(periods)} ({periods[0]} to {periods[-1]})")
    print(f"status        : {statuses} of {len(entries)} measure(s) carry one"
          if args.green_at is not None else "status        : none (no --green-at/--amber-at)")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


def table_html(entries: list[dict], periods: list[str], lang: str, t: dict) -> str:
    """Every figure on the page, period by period, so a reader can check the cards.

    The latest period of each series is marked, because the card shows that one and a reader
    should be able to find it without counting columns.
    """
    head = "".join(f'<th scope="col" class="num">{html.escape(period_label(p, lang))}</th>'
                   for p in periods)
    rows = []
    for entry in entries:
        dec = decimals_of(list(entry["values"].values()) + [v for v in entry["targets"].values() if v is not None])
        cells = []
        for period in periods:
            if period in entry["values"]:
                latest = period == entry["order"][-1]
                cells.append(f'<td class="num{" latest" if latest else ""}">'
                             f'{html.escape(fmt(entry["values"][period], lang, dec))}</td>')
            else:
                cells.append(f'<td class="num hole">{html.escape(t["period_missing"])}</td>')
        target = next((v for v in reversed(list(entry["targets"].values())) if v is not None), None)
        # The target sits beside the name rather than at the far end: a wide table scrolls,
        # and a reader recomputing the gap should not have to hunt for the other operand.
        rows.append(f'    <tr><th scope="row">{html.escape(entry["name"])}'
                    f'<span class="unit">, {html.escape(entry["unit"])}</span></th>'
                    f'<td class="num target">'
                    f'{html.escape(fmt(target, lang, dec)) if target is not None else html.escape(t["no_target"])}</td>'
                    f'{"".join(cells)}</tr>')
    return (f'<div class="tablewrap"><table>\n'
            f'  <caption>{html.escape(t["table_caption"])}</caption>\n'
            f'  <thead><tr><th scope="col">{html.escape(t["col_kpi"])}</th>'
            f'<th scope="col" class="num">{html.escape(t["col_target"])}</th>{head}</tr></thead>\n'
            f'  <tbody>\n' + "\n".join(rows) + f'\n  </tbody>\n</table></div>')


if __name__ == "__main__":
    sys.exit(main())
