#!/usr/bin/env python3
"""Build a standalone scatter: one point per unit, two measures at once.

Every other artefact in this repository answers "how much" or "in what order". None of them
answers "do these two move together", which is the question behind half the requests that
arrive with two columns and no chart in mind.

    python3 tools/build_scatter.py \\
      --data examples/47-scatter/enheter.csv \\
      --label Enhet --x Svartid --y Tilfredshet \\
      --title "Svartid mot tilfredshet" \\
      --source "Syntetisk eksempeldata (enheter.csv)" \\
      --requested-by "Kundeservice" \\
      --out examples/47-scatter/spredning.html

What is built in, rather than left to whoever assembles the file:

  * **one point per unit, and the unit is named.** A scatter without names is a cloud: the
    reader can see that two measures move together and cannot see which unit is the outlier,
    which is the only actionable thing on the page.
  * **a label budget, declared.** Past about two dozen points, direct names collide and a
    legend does not help, because a legend identifies a colour and not a point. Above the
    budget each point carries a number and the names live in the table, and the page says so.
  * **the axes are the data's range, and the page says so.** A scatter forced to zero presses
    the shape of the cloud into a stripe; a scatter cropped silently exaggerates it. The
    extremes are printed at the axis ends, so the reader can see the span.
  * **no fitted line unless it is asked for, and then r is printed with n.** A line drawn
    through a cloud is a summary of that sample. Without the coefficient it is an assertion,
    and with the coefficient but no n it hides how little it rests on.
  * **points that share a place are counted.** Two units with identical values are one dot on
    the page and two rows in the table; the page says how many, so the picture cannot be read
    as "fewer units than there are".
  * **a refusal rather than a misleading picture.** Two points are a line, not a scatter; a
    non-numeric column is not two measures; a repeated name is a data problem the builder will
    not paper over; and past the point budget the answer is to aggregate, not to draw a blob.
  * **there is no script.** A scatter is a snapshot; a filter would be a different artefact.

Stdlib only, like the rest of tools/. Python 3.8+.
"""
from __future__ import annotations

import argparse
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

TEMPLATE = ROOT / "templates" / "scatter.html"
STRINGS = "scatter"
MAX_POINTS = 120              # above this a scatter is a density, and a density is a heatmap
NAME_LIMIT = 24               # above this, names collide: points carry numbers instead
MAX_GROUPS = 5                # --cat-1 .. --cat-5 is what the seam carries
MAX_BYTES = 40 * 1024 * 1024

# The canvas. One unit is one pixel, and the template refuses to scale below that, so the
# 14-unit text is 14 px and the floor holds without measuring.
W, H = 760, 470
PAD_L, PAD_R, PAD_T, PAD_B = 78, 28, 18, 62
PLOT_W = W - PAD_L - PAD_R
PLOT_H = H - PAD_T - PAD_B
DOT_R = 5
TICKS = 4

# Label geometry, used only to decide which side of a point a name goes on. The suite
# measures the rendered boxes in a browser, which is the only place a collision is visible.
CHAR_W = 7.4
LABEL_GAP = 9

SHAPES = ("circle", "square", "triangle", "diamond", "cross")


# -------------------------------------------------------------------------------- numbers
def decimals_of(values: list[float]) -> int:
    """No decimals for whole numbers, at most two otherwise."""
    if all(float(v).is_integer() for v in values):
        return 0
    return 2 if any(round(v, 1) != round(v, 2) for v in values) else 1


def fmt(value: float, lang: str, dec: int) -> str:
    text = f"{value:,.{dec}f}"
    if lang == "nb":
        return text.replace(",", "\u00a0").replace(".", ",")
    return text.replace(",", "\u2009")


def coefficient(value: float, lang: str) -> str:
    """r as the page prints it. A minus sign is a real minus (U+2212), not a hyphen.

    The repository's rule for a change applies to any negative number a reader might check by
    hand: a hyphen reads as punctuation and a minus reads as a sign.
    """
    text = f"{abs(value):.2f}"
    if lang == "nb":
        text = text.replace(".", ",")
    return ("\u2212" if value < 0 else "") + text


# ----------------------------------------------------------------------------------- load
def load(path: pathlib.Path, xcol: str, ycol: str, label_col: str,
         group_col: str) -> tuple[list[dict], int]:
    """One dict per drawn point, and the count of rows that could not be drawn."""
    # coerce first: a CSV holds text, and is_numeric_column answers about real numbers. A
    # column converts only when every non-empty value parses, so an id that looks numeric is
    # left alone.
    rows = tun_core.coerce_numbers(tun_core.read_rows(path))
    if not rows:
        die(f"{path} holds no rows")
    cols = tun_core.columns(rows)
    for name, role in ((xcol, "--x"), (ycol, "--y")):
        if name not in cols:
            die(f"{role} names {name!r}, which is not a column in {path.name}. "
                f"Columns: {', '.join(cols)}")
        if not tun_core.is_numeric_column(rows, name):
            die(f"{role} names {name!r}, and that column is not numeric in every row. A "
                f"scatter is two measures; anything else is a category drawn as a position.")
    if label_col and label_col not in cols:
        die(f"--label names {label_col!r}, which is not a column in {path.name}. "
            f"Columns: {', '.join(cols)}")
    if group_col and group_col not in cols:
        die(f"--group names {group_col!r}, which is not a column in {path.name}")

    points, skipped, seen = [], 0, {}
    for row in rows:
        name = str(row.get(label_col, "")).strip() if label_col else ""
        x, y = tun_core.to_number(row.get(xcol)), tun_core.to_number(row.get(ycol))
        if x is None or y is None or (label_col and not name):
            skipped += 1
            continue
        if not label_col:
            name = f"{len(points) + 1}"
        if name in seen:
            # Two rows with one name is a data problem: the reader would look for one point
            # and there are two, and nothing on the page can say which is meant.
            die(f"the name {name!r} appears twice in {label_col!r}. A scatter draws one point "
                f"per unit, so the names have to identify one row each. Aggregate the file "
                f"first, or pick a column that is unique.")
        seen[name] = True
        points.append({"label": name, "x": float(x), "y": float(y),
                       "group": str(row.get(group_col, "")).strip() if group_col else ""})
    return points, skipped


# ------------------------------------------------------------------------------- geometry
def span(values: list[float]) -> tuple[float, float]:
    """The axis range: floor and ceiling, with air at both ends, never forced to zero.

    Forcing zero is right for a bar and wrong for a scatter: two measures on the same scale
    can both be far from zero, and zero at the bottom presses the whole cloud into a stripe
    that says nothing. The extremes are printed on the page, so the choice is visible.
    """
    low, high = min(values), max(values)
    if low == high:                              # one value: give it a window to sit in
        air = abs(low) * 0.1 or 1.0
        return low - air, high + air
    air = (high - low) * 0.06
    return low - air, high + air


def project(value: float, low: float, high: float, start: float, length: float) -> float:
    return start + (value - low) / (high - low) * length


def ticks(low: float, high: float) -> list[float]:
    """Round tick values inside the range, so the axis reads in round numbers."""
    raw = (high - low) / TICKS
    if raw <= 0:
        return [low]
    power = 10 ** math.floor(math.log10(raw))
    step = min((1, 2, 2.5, 5, 10), key=lambda m: abs(m * power - raw)) * power
    first = math.ceil(low / step) * step
    out, value = [], first
    while value <= high + step / 1000:
        out.append(round(value, 10))
        value += step
    return out


def least_squares(points: list[dict]) -> tuple[float, float, float] | None:
    """(slope, intercept, r) for y on x, or None when x does not vary."""
    n = len(points)
    if n < 3:
        return None
    mx = sum(p["x"] for p in points) / n
    my = sum(p["y"] for p in points) / n
    sxx = sum((p["x"] - mx) ** 2 for p in points)
    if sxx == 0:
        return None
    sxy = sum((p["x"] - mx) * (p["y"] - my) for p in points)
    syy = sum((p["y"] - my) ** 2 for p in points)
    slope = sxy / sxx
    if syy == 0:
        return slope, my - slope * mx, 0.0
    return slope, my - slope * mx, sxy / math.sqrt(sxx * syy)


# ----------------------------------------------------------------------------------- svg
def shape_svg(shape: str, cx: float, cy: float, cls: str) -> str:
    """A point, as one of five shapes. Shape is the second channel beside colour."""
    attrs = f'class="{cls}" data-x="{cx:.2f}" data-y="{cy:.2f}"'
    if shape == "square":
        side = DOT_R * 1.7
        return (f'<rect {attrs} x="{cx - side / 2:.2f}" y="{cy - side / 2:.2f}" '
                f'width="{side:.2f}" height="{side:.2f}"/>')
    if shape == "triangle":
        return (f'<polygon {attrs} points="{cx:.2f},{cy - DOT_R - 1:.2f} '
                f'{cx - DOT_R - 1:.2f},{cy + DOT_R:.2f} {cx + DOT_R + 1:.2f},{cy + DOT_R:.2f}"/>')
    if shape == "diamond":
        r = DOT_R + 1
        return (f'<polygon {attrs} points="{cx:.2f},{cy - r:.2f} {cx + r:.2f},{cy:.2f} '
                f'{cx:.2f},{cy + r:.2f} {cx - r:.2f},{cy:.2f}"/>')
    if shape == "cross":
        a, b = DOT_R, DOT_R * 0.45
        return (f'<path {attrs} d="M{cx - a:.2f},{cy - b:.2f} L{cx + a:.2f},{cy - b:.2f} '
                f'L{cx + a:.2f},{cy + b:.2f} L{cx - a:.2f},{cy + b:.2f} Z '
                f'M{cx - b:.2f},{cy - a:.2f} L{cx + b:.2f},{cy - a:.2f} '
                f'L{cx + b:.2f},{cy + a:.2f} L{cx - b:.2f},{cy + a:.2f} Z"/>')
    return f'<circle {attrs} cx="{cx:.2f}" cy="{cy:.2f}" r="{DOT_R}"/>'


def drawing(points: list[dict], xcol: str, ycol: str, lang: str, t: dict,
            names: bool, trend: bool, groups: list[str]) -> str:
    """The plot, its axes and its labels. Positions are decided here, not by CSS."""
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    xlow, xhigh = span(xs)
    ylow, yhigh = span(ys)
    xdec, ydec = decimals_of(xs), decimals_of(ys)

    def px(value: float) -> float:
        return project(value, xlow, xhigh, PAD_L, PLOT_W)

    def py(value: float) -> float:
        return PAD_T + PLOT_H - project(value, ylow, yhigh, 0, PLOT_H)

    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="sc-t sc-d">',
           f'<title id="sc-t">{html.escape(t["svg_title"])}</title>',
           f'<desc id="sc-d">{html.escape(i18n.fill(t["svg_desc"], n=len(points), x=xcol, y=ycol))}</desc>']

    for value in ticks(xlow, xhigh):
        x = px(value)
        out.append(f'<line class="sc-grid" x1="{x:.2f}" y1="{PAD_T}" x2="{x:.2f}" '
                   f'y2="{PAD_T + PLOT_H}"/>')
        out.append(f'<text class="sc-tick" x="{x:.2f}" y="{PAD_T + PLOT_H + 20}" '
                   f'text-anchor="middle">{html.escape(fmt(value, lang, xdec))}</text>')
    for value in ticks(ylow, yhigh):
        y = py(value)
        out.append(f'<line class="sc-grid" x1="{PAD_L}" y1="{y:.2f}" x2="{PAD_L + PLOT_W}" '
                   f'y2="{y:.2f}"/>')
        out.append(f'<text class="sc-tick" x="{PAD_L - 10}" y="{y + 5:.2f}" '
                   f'text-anchor="end">{html.escape(fmt(value, lang, ydec))}</text>')

    out.append(f'<rect class="sc-box" x="{PAD_L}" y="{PAD_T}" width="{PLOT_W}" '
               f'height="{PLOT_H}"/>')
    out.append(f'<text class="sc-axis-title" x="{PAD_L + PLOT_W / 2:.2f}" y="{H - 16}" '
               f'text-anchor="middle">{html.escape(xcol)}</text>')
    out.append(f'<text class="sc-axis-title" x="18" y="{PAD_T + PLOT_H / 2:.2f}" '
               f'transform="rotate(-90 18 {PAD_T + PLOT_H / 2:.2f})" text-anchor="middle">'
               f'{html.escape(ycol)}</text>')

    if trend:
        fit = least_squares(points)
        if fit:
            slope, intercept, _r = fit
            y_at_low = slope * xlow + intercept
            y_at_high = slope * xhigh + intercept
            # Clip to the plot: a fit line that leaves the box would be drawn over the axis.
            out.append(f'<line class="sc-fit" x1="{px(xlow):.2f}" '
                       f'y1="{max(PAD_T, min(PAD_T + PLOT_H, py(y_at_low))):.2f}" '
                       f'x2="{px(xhigh):.2f}" '
                       f'y2="{max(PAD_T, min(PAD_T + PLOT_H, py(y_at_high))):.2f}"/>')

    # Labels are placed against a box model, not one candidate to the right. One candidate is
    # what puts "Fosen" on top of "Numedal": two units close in both measures get labels that
    # overlap, and the reader cannot tell which name belongs to which point. Four candidates
    # per label, each one rejected if it hits something already placed, and a label with no
    # free candidate becomes its number, which is short enough to fit anywhere. The estimate is
    # deliberately generous (CHAR_W above the measured average); the suite checks the rendered
    # boxes in a browser, which is the only place a collision is really visible.
    placed: list[tuple[float, float, float, float]] = []
    for idx_point, point in enumerate(points, start=1):
        cx, cy = px(point["x"]), py(point["y"])
        placed.append((cx - DOT_R - 2, cy - DOT_R - 2, DOT_R * 2 + 4, DOT_R * 2 + 4))

    def free(box: tuple[float, float, float, float]) -> bool:
        x, y, w, h = box
        if x < PAD_L - 2 or x + w > PAD_L + PLOT_W + 2:
            return False
        if y < PAD_T - 2 or y + h > PAD_T + PLOT_H + 2:
            return False
        return not any(x < bx + bw and bx < x + w and y < by + bh and by < y + h
                       for bx, by, bw, bh in placed)

    degraded = 0
    for index, point in enumerate(points, start=1):
        cx, cy = px(point["x"]), py(point["y"])
        if groups:
            idx = groups.index(point["group"]) if point["group"] in groups else None
            cls = f'sc-dot sc-c{idx + 1}' if idx is not None else "sc-dot sc-c0"
            shape = SHAPES[idx % len(SHAPES)] if idx is not None else "circle"
        else:
            cls, shape = "sc-dot sc-c1", "circle"
        out.append(shape_svg(shape, cx, cy, cls))

        want = point["label"] if names else str(index)
        text, anchor, tx, ty = None, "start", 0.0, 0.0
        for candidate in ("right", "left", "above", "below", "number"):
            body = want if candidate != "number" else str(index)
            width = len(body) * CHAR_W + 2
            if candidate == "right":
                box = (cx + DOT_R + LABEL_GAP, cy - 11, width, 16)
                anchor, tx, ty = "start", cx + DOT_R + LABEL_GAP, cy + 5
            elif candidate == "left":
                box = (cx - DOT_R - LABEL_GAP - width, cy - 11, width, 16)
                anchor, tx, ty = "end", cx - DOT_R - LABEL_GAP, cy + 5
            elif candidate == "above":
                box = (cx - width / 2, cy - DOT_R - 20, width, 16)
                anchor, tx, ty = "middle", cx, cy - DOT_R - 8
            elif candidate == "below":
                box = (cx - width / 2, cy + DOT_R + 5, width, 16)
                anchor, tx, ty = "middle", cx, cy + DOT_R + 18
            else:
                # Nothing free: the number always fits somewhere, and the page says that the
                # names are in the table instead.
                width = len(str(index)) * CHAR_W + 2
                box = (cx + DOT_R + 4, cy - 11, width, 16)
                anchor, tx, ty = "start", cx + DOT_R + 4, cy + 5
                degraded += 1
            if free(box) or candidate == "number":
                text = body
                placed.append(box)
                break
        out.append(f'<text class="sc-name" x="{tx:.2f}" y="{ty:.2f}" '
                   f'text-anchor="{anchor}">{html.escape(text)}</text>')

    out.append("</svg>")
    return "\n".join(out), (xlow, xhigh, ylow, yhigh, xdec, ydec), degraded


# --------------------------------------------------------------------------------- table
def table_html(points: list[dict], xcol: str, ycol: str, lang: str, t: dict,
               groups: list[str]) -> str:
    """Every drawn number, one row per unit, numbered as the point is."""
    xdec, ydec = decimals_of([p["x"] for p in points]), decimals_of([p["y"] for p in points])
    head = [f'<th scope="col">{html.escape(t["col_no"])}</th>',
            f'<th scope="col">{html.escape(t["col_label"])}</th>',
            f'<th scope="col" class="num">{html.escape(i18n.fill(t["col_x"], x=xcol))}</th>',
            f'<th scope="col" class="num">{html.escape(i18n.fill(t["col_y"], y=ycol))}</th>']
    if groups:
        head.append(f'<th scope="col">{html.escape(t["col_group"])}</th>')
    body = []
    for index, point in enumerate(points, start=1):
        cells = [f'<td class="num">{index}</td>',
                 f"<td>{html.escape(point['label'])}</td>",
                 f'<td class="num">{html.escape(fmt(point["x"], lang, xdec))}</td>',
                 f'<td class="num">{html.escape(fmt(point["y"], lang, ydec))}</td>']
        if groups:
            cells.append(f"<td>{html.escape(point['group'] or '—')}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return ("<thead><tr>" + "".join(head) + "</tr></thead>\n<tbody>\n"
            + "\n".join(body) + "\n</tbody>")


# ----------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=pathlib.Path, required=True,
                    help="CSV with one row per unit")
    ap.add_argument("--x-col", default="", help="the column on the horizontal axis")
    ap.add_argument("--y-col", default="", help="the column on the vertical axis")
    ap.add_argument("--label", default="", help="the column naming each unit")
    ap.add_argument("--group", default="",
                    help="the column that puts points in groups (colour and shape)")
    ap.add_argument("--labels", choices=("auto", "on", "off"), default="auto",
                    help="names on the drawing; auto uses them only when they fit")
    ap.add_argument("--trend", action="store_true",
                    help="draw a least-squares line, and print r with n")
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

    if not args.x_col or not args.y_col:
        die("--x-col and --y-col are both required: a scatter needs two measures, and "
            "guessing which column is which would put the wrong variable on the wrong axis.")
    if args.x_col == args.y_col:
        die(f"--x-col and --y-col are both {args.x_col!r}. A measure against itself is a "
            f"straight line, and it would look like a perfect relationship.")

    points, skipped = load(args.data, args.x_col, args.y_col, args.label, args.group)
    if len(points) < 3:
        die(f"{len(points)} unit(s) can be drawn. Two points are a line and one is a dot: "
            f"there is no cloud to read. A scatter needs at least three.")
    if len(points) > MAX_POINTS:
        die(f"{len(points)} units is past the {MAX_POINTS}-point ceiling. Above that the dots "
            f"overlap into a blob and a label identifies nothing; aggregate to one row per "
            f"group first, or use the heatmap, which is built for density.")

    groups = sorted({p["group"] for p in points if p["group"]}) if args.group else []
    if len(groups) > MAX_GROUPS:
        die(f"--group {args.group!r} holds {len(groups)} groups and the seam carries "
            f"{MAX_GROUPS} categorical colours. Merge the smallest groups, or drop --group: "
            f"past five, colour stops identifying and starts decorating.")

    names = {"auto": len(points) <= NAME_LIMIT, "on": True, "off": False}[args.labels]
    if args.labels == "on" and len(points) > NAME_LIMIT:
        die(f"--labels on with {len(points)} points: past {NAME_LIMIT} the names run into "
            f"each other and a name that lands on another point is worse than a number. "
            f"Use --labels auto, or aggregate.")

    drawn, axes, degraded = drawing(points, args.x_col, args.y_col, lang, t, names,
                                    args.trend, groups)
    xlow, xhigh, ylow, yhigh, xdec, ydec = axes
    source = args.source or NOT_STATED
    built = build_stamp.naive()
    extracted = build_stamp.from_mtime(args.data, "%Y-%m-%d %H:%M", aware=False)

    by_y = sorted(points, key=lambda p: p["y"])
    unique_places = len({(round(p["x"], 9), round(p["y"], 9)) for p in points})
    overlapping = len(points) - unique_places

    notes = []
    notes.append(t["axes_note"])
    if degraded:
        notes.append(i18n.fill(t["labels_numbers"], n=len(points)))
    else:
        notes.append({"on": t["labels_names"],
                      "auto": t["labels_names"] if names else
                      i18n.fill(t["labels_numbers"], n=len(points)),
                      "off": t["labels_off"]}[args.labels])
    if args.trend:
        fit = least_squares(points)
        if fit:
            slope, _intercept, r = fit
            notes.append(i18n.fill(t["trend_on"], r=coefficient(r, lang), n=len(points)))
            notes.append(i18n.fill(t["trend_strong"] if abs(r) >= 0.7 else t["trend_weak"],
                                   r=coefficient(r, lang)))
    if skipped:
        notes.append(i18n.fill(t["skipped"], n=skipped))

    summary = i18n.fill(
        t["summary_line"], n=len(points), x=args.x_col, y=args.y_col,
        xlow=fmt(min(p["x"] for p in points), lang, xdec),
        xhigh=fmt(max(p["x"] for p in points), lang, xdec),
        ylow=fmt(by_y[0]["y"], lang, ydec), yhigh=fmt(by_y[-1]["y"], lang, ydec),
        ytop=by_y[-1]["label"], ytopv=fmt(by_y[-1]["y"], lang, ydec),
        ybot=by_y[0]["label"], ybotv=fmt(by_y[0]["y"], lang, ydec))
    if overlapping:
        summary += " " + i18n.fill(t["summary_overlap"], n=overlapping)

    legend = ""
    if groups:
        swatches = "".join(
            f'<li>{shape_svg(SHAPES[i % len(SHAPES)], 9, 9, f"sc-dot sc-c{i + 1}")}'
            f"<span>{html.escape(name)}</span></li>" for i, name in enumerate(groups))
        legend = f'<ul class="legend" aria-label="{html.escape(t["legend_group"])}">{swatches}</ul>'

    feedback = ""
    if args.feedback_to:
        try:
            feedback = feedback_link.block(args.feedback_to, title=args.title, built=built,
                                           source=source, lang=lang)
        except ValueError as exc:
            die(f"--feedback-to: {exc}")

    token_css, _ = tun_tokens.load_token_css(auto_dark=True)
    page = (i18n.apply(TEMPLATE.read_text(encoding="utf-8"), t)
            .replace("{{TOKEN_CSS}}", strip_css_comments(token_css)))
    for token, value in {
        "{{TITLE}}": html.escape(args.title),
        "{{SUBTITLE}}": html.escape(i18n.fill(t["sub_line"], n=len(points),
                                              x=args.x_col, y=args.y_col)),
        "{{SOURCE_DESCRIPTION}}": html.escape(source),
        "{{SOURCE_LINE}}": html.escape(i18n.fill(t["source_line"], name=source,
                                                 rows=len(points) + skipped)),
        "{{EXTRACT_TIMESTAMP}}": html.escape(extracted),
        "{{BUILD_TIMESTAMP}}": html.escape(built),
        "{{REQUESTED_BY}}": html.escape(args.requested_by or NOT_STATED),
        "{{ROWS_INLINED}}": str(len(points)),
        "{{CAPTION}}": html.escape(t["caption"]),
        "{{SUMMARY}}": html.escape(summary),
        "{{DRAWING}}": drawn,
        "{{LEGEND}}": legend,
        "{{TABLE}}": table_html(points, args.x_col, args.y_col, lang, t, groups),
        "{{NOTES}}": "".join(f"<li>{html.escape(n)}</li>" for n in notes),
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

    print(f"units         : {len(points)} ({unique_places} unique place(s) in the plot)")
    print(f"labels        : {'names' if names else 'numbers'} ({len(points)} points)")
    print(f"groups        : {len(groups)}" if groups else "groups        : none")
    print(f"trend         : {'yes' if args.trend and least_squares(points) else 'no'}")
    print(f"wrote         : {args.out} ({len(data) / 1024:.1f} KB)")
    build_size.enforce(args.out)
    print(f"  next: python3 {ROOT / 'tools' / 'verify_a11y.py'} {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
