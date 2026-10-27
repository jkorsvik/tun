#!/usr/bin/env python3
"""Build a standalone calendar heatmap: when in the week, and when in the year.

A heatmap (43) answers "where is it busy" across two categories. This answers it across the
calendar: one cell per day, aligned to weekday columns, so a Monday pattern and a quiet weekend
are visible as shapes rather than as a table.

    python3 tools/build_calendar.py \\
      --data examples/50-calendar/hendelser.csv \\
      --date Dato --value Antall \\
      --title "Hendelser per dag, 2026" \\
      --source "Syntetisk eksempeldata (hendelser.csv)" \\
      --requested-by "Driftsavdelingen" \\
      --out examples/50-calendar/kalender.html

What is built in, rather than left to whoever assembles the file:

  * **the alignment is the claim, so it is stated.** The week starts on Monday, the first
    column is the week that holds the first day, and the weekday labels are printed. A calendar
    whose week starts on the wrong day invents a pattern out of the layout.
  * **a day with no data is hatched, never pale.** A pale cell reads as "a little", which is a
    measurement, and no measurement was taken. Missing days are counted and printed.
  * **zero is a value.** A day that recorded 0 gets the lowest shade and is not confused with a
    day that recorded nothing.
  * **the band edges are printed under the picture**, and the same edges decide the shades.
  * **one value per day.** Two rows for one date is refused by name: a calendar cannot show a
    sum and a value at the same time without saying which it drew.
  * **the shape is only half the answer.** The table adds the seven weekday averages, the ten
    busiest days, and the count of missing days, because a picture of 365 cells is easy to
    squint at and hard to check.
  * **there is no script.** A calendar is a snapshot.

Stdlib only, like the rest of tools/. Python 3.8+.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import math
import pathlib
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

TEMPLATE = ROOT / "templates" / "calendar.html"
STRINGS = "calendar"
BANDS = 5
MAX_DAYS = 400                 # past this the cells are hairlines and the year is the unit
CELL = 15
GAP = 3
GUTTER = 46                    # the weekday labels
PAD_T = 30                     # the month labels
MAX_BYTES = 40 * 1024 * 1024

MONTH_NB = ("januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
            "september", "oktober", "november", "desember")
MONTH_EN = ("January", "February", "March", "April", "May", "June", "July", "August",
            "September", "October", "November", "December")
MONTH_SHORT_NB = ("jan", "feb", "mar", "apr", "mai", "jun", "jul", "aug", "sep", "okt",
                  "nov", "des")
MONTH_SHORT_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                  "Nov", "Dec")
WEEKDAY_NB = ("man", "tir", "ons", "tor", "fre", "lør", "søn")
WEEKDAY_EN = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
# A 1-2-5 ladder, so the printed edges are numbers a reader would have chosen.
LADDER = (1, 2, 5)


def parse_date(value: str, where: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value.strip())
    except ValueError:
        die(f"{where}: {value!r} is not a date. Write it as YYYY-MM-DD (2026-03-14); this "
            f"builder will not guess a dd.mm from an mm.dd.")


def fmt(value: float, lang: str) -> str:
    text = f"{value:,.0f}" if float(value).is_integer() else f"{value:,.1f}"
    if lang == "nb":
        return text.replace(",", "\u00a0").replace(".", ",")
    return text.replace(",", "\u2009")


def iso_date(day: dt.date, lang: str) -> str:
    if lang == "nb":
        return f"{day.day:02d}.{day.month:02d}.{day.year}"
    return f"{day.day} {MONTH_SHORT_EN[day.month - 1]} {day.year}"


# ------------------------------------------------------------------------------- the bands
def ladder_edges(low: float, high: float) -> list[float]:
    """Edges on a 1-2-5 ladder, snapped to a round number, at most BANDS intervals.

    A reader asked to choose five boundaries would choose round ones, so the boundaries are
    round: "0, 20, 40, 60, 80, 100" is a scale somebody can act on, and "0, 18.6, 37.2" is not.
    The smallest step that still fits in BANDS bands wins, so one peak cannot flatten the rest of
    the year into a single shade (it did, on the first build of this page).
    """
    if high <= low:
        return [low, low + 1]
    span = high - low
    for magnitude in (1e-3, 1e-2, 0.1, 1, 10, 100, 1000, 10000, 100000, 1000000):
        for base in LADDER:
            step = base * magnitude
            start = math.floor(low / step) * step
            edges = [round(start, 6)]
            while edges[-1] < high:
                edges.append(round(edges[-1] + step, 6))
                if len(edges) > BANDS + 1:
                    break
            if len(edges) - 1 <= BANDS:
                return edges
    return [low, high]


def band_of(value: float, edges: list[float]) -> int:
    """Which band a value gets. Anything at or above the top edge is folded into the last one,
    which is why the legend prints that band with a minimum and not a range."""
    for index in range(len(edges) - 1):
        if value < edges[index + 1]:
            return index
    return len(edges) - 2


def ink_for(fill: str) -> str:
    """Whichever of the panel inks measures better on this fill, by the WCAG formula."""
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    def luminance(hexa: str) -> float:
        r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
        return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

    def ratio(a: str, b: str) -> float:
        la, lb = sorted((luminance(a), luminance(b)), reverse=True)
        return (la + 0.05) / (lb + 0.05)

    return "#111418" if ratio(fill, "#111418") >= ratio(fill, "#ffffff") else "#ffffff"


def mix(fraction: float, base: tuple[int, int, int], other: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{round(base[i] + (other[i] - base[i]) * fraction):02x}"
                         for i in range(3))


# ----------------------------------------------------------------------------------- load
def load(path: pathlib.Path, date_col: str, value_col: str) -> tuple[dict[dt.date, float], int]:
    if not path.is_file():
        die(f"{path} does not exist")
    # Coerce first: is_numeric_column answers about Python numbers, and a CSV hands back
    # strings, so asking it about the raw rows rejects every numeric column there is.
    rows = tun_core.coerce_numbers(tun_core.read_rows(path))
    if not rows:
        die(f"{path.name} has no rows")
    header = tun_core.columns(rows)
    for name, flag in ((date_col, "--date"), (value_col, "--value")):
        if name not in header:
            die(f"{flag} names {name!r}, which is not a column in {path.name}. "
                f"Columns: {', '.join(header)}")
    if not tun_core.is_numeric_column(rows, value_col):
        die(f"--value names {value_col!r}, and that column is not numeric in every row. A "
            f"calendar shades a number; a category on that axis is a count, so count it first.")

    values: dict[dt.date, float] = {}
    seen: dict[dt.date, int] = {}
    skipped = 0
    for i, row in enumerate(rows, 2):
        raw = str(row.get(date_col) or "").strip()
        if not raw:
            skipped += 1
            continue
        day = parse_date(raw, f"{path.name}:{i}")
        number = tun_core.to_number(row.get(value_col))
        if number is None:
            skipped += 1
            continue
        if day in values:
            seen[day] += 1
            die(f"{path.name}: {iso_date(day, 'nb')} appears {seen[day]} times. A calendar shows "
                f"one value per day, so aggregate the rows first: sum them for a count, mean "
                f"them for a level, and pass the result.")
        values[day] = float(number)
        seen[day] = 1
    if not values:
        die(f"no row in {path.name} has both a date and a number.")
    return values, skipped


# ----------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True)
    ap.add_argument("--date", required=True, help="the column holding YYYY-MM-DD")
    ap.add_argument("--value", required=True, help="the numeric column to shade")
    ap.add_argument("--from", dest="from_date", default="", metavar="YYYY-MM-DD",
                    help="draw from this day, even when no row holds it")
    ap.add_argument("--to", dest="to_date", default="", metavar="YYYY-MM-DD",
                    help="draw to this day, even when no row holds it")
    ap.add_argument("--clamp", type=float, default=None, metavar="N",
                    help="fold every value at or above N into the top band, labelled with a "
                         "minimum; for when one peak would flatten the rest of the year")
    ap.add_argument("--title", required=True)
    ap.add_argument("--source", default="")
    ap.add_argument("--requested-by", default="")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--feedback-to", default="", metavar="ADDRESS_OR_ISSUE_URL",
                    help=feedback_link.FLAG_HELP)
    i18n.add_lang_argument(ap)
    args = ap.parse_args(argv)
    t = i18n.load(STRINGS, args.lang)
    lang = args.lang
    nb = lang == "nb"
    weekday_names = WEEKDAY_NB if nb else WEEKDAY_EN
    month_short = MONTH_SHORT_NB if nb else MONTH_SHORT_EN

    values, skipped = load(args.data, args.date, args.value)
    first = parse_date(args.from_date, "--from") if args.from_date else min(values)
    last = parse_date(args.to_date, "--to") if args.to_date else max(values)
    if last < first:
        die("--to is before --from, so there is no calendar to draw.")
    days = (last - first).days + 1
    if days > MAX_DAYS:
        die(f"that range is {days} days, past the {MAX_DAYS} this page can draw. Pass --from "
            f"and --to for one period, or build one page per year.")
    outside = sum(1 for day in values if not (first <= day <= last))
    present = {day: value for day, value in values.items() if first <= day <= last}
    missing = days - len(present)

    # The grid: one column per week, starting on the Monday of the week that holds the first day.
    grid_start = first - dt.timedelta(days=first.weekday())
    last_col = (last - grid_start).days // 7 + 1
    width = GUTTER + last_col * (CELL + GAP) + 8
    height = PAD_T + 7 * (CELL + GAP) + 30

    low, high = min(present.values()), max(present.values())
    if args.clamp is not None and args.clamp <= low:
        die(f"--clamp {fmt(args.clamp, 'nb')} is not above the lowest value ({fmt(low, 'nb')}), "
            f"so every day would sit in the top band. Give a higher clamp, or drop the flag.")
    top_value = high if args.clamp is None else max(low, min(high, float(args.clamp)))
    edges = ladder_edges(low, top_value)
    clamped = sum(1 for value in present.values() if value >= edges[-1]) if len(edges) > 1 else 0
    base, top = (0x8f, 0xb3, 0xae), (0x2f, 0x5d, 0x9e)      # a pale wash to the brand green
    bands = []
    count = max(1, len(edges) - 1)
    for index in range(count):
        share = index / max(1, count - 1)
        fill = mix(0.25 + 0.75 * share, base, top)
        # In dark the panel is nearly black, so the lightest band has to start further along
        # the mix or it disappears into the page.
        dark = mix(0.45 + 0.55 * share, base, top)
        bands.append({"band": index, "fill": fill, "ink": ink_for(fill),
                      "dark": dark, "dark_ink": ink_for(dark),
                      "low": edges[index],
                      "high": edges[index + 1] if index + 1 < len(edges) else None})

    out = [f'<svg viewBox="0 0 {width} {height}" style="min-width:{width}px" '
           f'role="img" aria-labelledby="cl-t cl-d">',
           f'<title id="cl-t">{html.escape(t["svg_title"])}</title>',
           f'<desc id="cl-d">{html.escape(i18n.fill(t["svg_desc"], n=days, first=iso_date(first, lang), last=iso_date(last, lang), value=args.value))}</desc>']
    for row, name in enumerate(weekday_names):
        y = PAD_T + row * (CELL + GAP) + CELL - 4
        out.append(f'<text class="cl-wd" x="{GUTTER - 8}" y="{y}" text-anchor="end">'
                   f'{html.escape(name)}</text>')
    # Month labels above the first column that starts a month inside the range.
    seen_months: set[tuple[int, int]] = set()
    day = first
    while day <= last:
        if (day.year, day.month) not in seen_months:
            seen_months.add((day.year, day.month))
            column = (day - grid_start).days // 7
            x = GUTTER + column * (CELL + GAP)
            out.append(f'<text class="cl-month" x="{x}" y="{PAD_T - 10}">'
                       f'{html.escape(month_short[day.month - 1])}</text>')
        day += dt.timedelta(days=1)

    for index in range(days):
        day = first + dt.timedelta(days=index)
        column = (day - grid_start).days // 7
        row = day.weekday()
        x = GUTTER + column * (CELL + GAP)
        y = PAD_T + row * (CELL + GAP)
        if day in present:
            value = present[day]
            band = bands[band_of(value, edges)]
            out.append(f'<rect class="cl-cell cal-b{band["band"]}" data-day="{day.isoformat()}" '
                       f'x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2">'
                       f'<title>{html.escape(iso_date(day, lang))}: '
                       f'{html.escape(fmt(value, lang))}</title></rect>')
        else:
            out.append(f'<rect class="cl-cell cl-none" data-day="{day.isoformat()}" '
                       f'x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2">'
                       f'<title>{html.escape(iso_date(day, lang))}: '
                       f'{html.escape(t["cell_missing"])}</title></rect>')
    out.append("</svg>")
    drawing = "\n".join(out)

    def rule(band: dict, indent: str, dark: bool = False) -> str:
        n = band["band"]
        fill = band["dark"] if dark else band["fill"]
        return (f"{indent}.cal-b{n}{{fill:{fill}}}\n"
                f"{indent}.sw.cal-b{n}{{background:{fill}}}")

    light_css = "\n".join(rule(b, "  ") for b in bands)
    dark_css = "\n".join(rule(b, "    ", dark=True) for b in bands)
    ramp_css = f"{light_css}\n  @media (prefers-color-scheme: dark){{\n{dark_css}\n  }}\n"

    legend = []
    for band in bands:
        if band["high"] is None or band is bands[-1]:
            text = "\u2265\u00a0" + fmt(band["low"], lang)
        else:
            text = f'{fmt(band["low"], lang)}\u2013{fmt(band["high"], lang)}'
        legend.append(f'<li><span class="sw cal-b{band["band"]}" aria-hidden="true"></span>'
                      f'<span class="rg">{html.escape(text)}</span></li>')
    legend.append(f'<li><span class="sw sw-none" aria-hidden="true"></span>'
                  f'<span class="rg">{html.escape(t["legend_missing"])}</span></li>')

    busiest = sorted(present.items(), key=lambda item: (-item[1], item[0]))[:10]
    by_weekday: dict[int, list[float]] = {i: [] for i in range(7)}
    for day, value in present.items():
        by_weekday[day.weekday()].append(value)
    weekday_rows = []
    for index, name in enumerate(weekday_names):
        held = by_weekday[index]
        mean = sum(held) / len(held) if held else None
        weekday_rows.append(
            "<tr>"
            f"<td>{html.escape(name)}</td>"
            f'<td class="num">{len(held)}</td>'
            f'<td class="num">{html.escape(fmt(mean, lang)) if mean is not None else "\u2013"}</td>'
            f'<td class="num">{html.escape(fmt(min(held), lang)) if held else "\u2013"}</td>'
            f'<td class="num">{html.escape(fmt(max(held), lang)) if held else "\u2013"}</td>'
            "</tr>")

    busiest_rows = "\n".join(
        "<tr>" + f"<td>{html.escape(iso_date(day, lang))}</td>"
        f"<td>{html.escape(weekday_names[day.weekday()])}</td>"
        f'<td class="num">{html.escape(fmt(value, lang))}</td>' + "</tr>"
        for day, value in busiest)

    busiest_day, busiest_value = busiest[0]
    quietest_day, quietest_value = min(present.items(), key=lambda item: (item[1], item[0]))
    summary = i18n.fill(t["summary_line"], n=days, first=iso_date(first, lang),
                        last=iso_date(last, lang), counted=len(present))
    summary += " " + i18n.fill(t["summary_busiest"], day=iso_date(busiest_day, lang),
                               value=fmt(busiest_value, lang),
                               quiet=iso_date(quietest_day, lang),
                               quietv=fmt(quietest_value, lang))
    if missing:
        summary += " " + i18n.fill(t["summary_missing"], n=missing)
    else:
        summary += " " + t["summary_none_missing"]
    if outside:
        summary += " " + i18n.fill(t["summary_outside"], n=outside)
    if clamped:
        summary += " " + i18n.fill(t["summary_clamped"], n=clamped,
                                   edge=fmt(edges[-1], lang))

    notes = [t["note_align"], t["note_missing"], t["note_zero"], t["note_bands"],
             t["note_one_per_day"]]

    source = args.source or NOT_STATED
    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)

    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=built,
                                           source=source, lang=lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css))
            .replace("{{RAMP_CSS}}", ramp_css))
    for token, value in {
        "{{TITLE}}": html.escape(args.title),
        "{{SUBTITLE}}": html.escape(i18n.fill(t["sub_line"], n=days, days=len(present),
                                              value=args.value)),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(i18n.fill(t["source_line"], name=source,
                                                 rows=len(present) + skipped)),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{ROWS_INLINED}}": str(len(present)),
        "{{CAPTION}}": html.escape(i18n.fill(t["caption"], first=iso_date(first, lang),
                                             last=iso_date(last, lang))),
        "{{SUMMARY}}": html.escape(summary),
        "{{DRAWING}}": drawing,
        "{{LEGEND}}": "\n  ".join(legend),
        "{{NOTES}}": "".join(f"<li>{html.escape(n)}</li>" for n in notes),
        "{{WEEKDAY_ROWS}}": "\n".join(weekday_rows),
        "{{BUSIEST_ROWS}}": busiest_rows,
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

    print(f"days          : {days} ({len(present)} with data, {missing} missing)")
    print(f"bands         : {len(bands)} from {fmt(edges[0], 'nb')} to {fmt(edges[-1], 'nb')}")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
