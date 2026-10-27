#!/usr/bin/env python3
"""Build idea-picture.html: the Tún idea as a moving, explorable picture with no script.

The figure lives in figure.fragment.html. This builder adds what would otherwise be
written twice by hand:

  * every arrow's path data, used both as the arrow's `d` and as the CSS `offset-path`
    its packet travels along (PATHS below, one entry per arrow);
  * the CSS selectors that tie each lens, host and play state to what it lights up,
    generated from LENSES, HOSTS and STEP so a new lens is one list entry.

Writes idea-picture.html (the standalone page) and figure.css (the figure's CSS alone,
for the public site to copy next to the figure). Stdlib only. SOURCE_DATE_EPOCH makes
the build date reproducible.

    python3 examples/25-living-idea-picture/build_idea_picture.py
"""
from __future__ import annotations

import datetime
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = HERE / "idea-picture.template.html"
FRAGMENT = HERE / "figure.fragment.html"
OUT = HERE / "idea-picture.html"
CSS_OUT = HERE / "figure.css"

# One path per arrow: w- = the wide picture, t- = the tall one shown on a phone.
PATHS = {
    "w-author": "M214,366 C236,358 252,350 274,342",
    "w-comm": "M240,182 C268,214 296,232 300,256",
    "w-commback": "M300,256 C296,232 268,214 240,182",
    "w-fb": "M396,164 V222",
    "w-out": "M462,300 H556",
    "w-kill": "M742,250 C790,232 800,226 812,222",
    "w-down": "M666,384 V520",
    "w-read": "M682,526 C752,520 806,502 856,484",
    "w-loop": "M902,450 C958,428 986,384 986,306 L986,70 C986,60 978,52 968,52 "
              "L456,52 C446,52 438,60 438,70 L438,106",
    "t-author": "M76,304 C94,290 106,280 124,266",
    "t-comm": "M130,82 C134,118 142,142 154,166",
    "t-commback": "M154,166 C142,142 134,118 130,82",
    "t-fb": "M318,78 C316,118 292,148 262,170",
    "t-out": "M200,312 V380",
    "t-kill": "M284,488 C292,498 298,506 304,516",
    "t-down": "M120,486 V708",
    "t-read": "M134,714 C206,708 262,698 310,688",
    "t-loop": "M370,652 C390,640 394,620 394,600 L394,60 C394,52 392,48 388,48",
}
# Which arrow's packet belongs to which step of the four-step playback (1-4).
STEP = {"author": 1, "out": 2, "kill": 3, "down": 3, "read": 4, "loop": 4, "fb": 4,
        "comm": 4, "commback": 4}
# Idle motion: seconds of delay per packet, so the picture never pulses all at once.
IDLE_DELAY = {"author": 0, "out": .8, "down": 1.6, "kill": 2.0, "read": 2.4, "loop": 2.8,
              "fb": 3.6, "comm": 1.2, "commback": 2.6}
LENSES = ("author", "reader", "community", "host", "kill")
HOSTS = ("sp", "od", "teams", "conf", "mail", "usb", "sky")
CYCLE = 12  # seconds for one playback of all four steps

BASE_CSS = """\
/* The picture breaks out of a narrow column: it takes 1056 px, or the window less its
   margins, so the wide canvas gets the width its text needs. type:inline-size makes the
   box itself the query container below, instead of the viewport. */
.lv{position:relative;container-type:inline-size;
  margin:1.5rem calc(50% - min(528px, 50vw - 16px));padding:20px;
  background:var(--panel,#fff);border:1px solid var(--line,#dfe3e0);border-radius:.6rem}
.lv-r{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;
  clip:rect(0 0 0 0);white-space:nowrap;opacity:0}
/* The stage is 2 x breakout - 2 x 20px padding - 2 x 1px border, so a 528px breakout
   leaves it 1014 px: wider than the wide canvas. Scaled below its canvas a 14 px label
   reaches the reader at 11.6 px, while a gate reading CSS reports 14 px for both, so
   neither picture may shrink below its own width: the stage scrolls instead, and a
   line of text appears when it does.

   The two min-widths are the guarantee, not the breakpoint below: they make a wrong
   breakpoint degrade to a scroll rather than to clipped type, and they hold in a
   browser that never evaluates a container query. */
.lv-stage{overflow-x:auto}
.lv-stage svg{display:block;width:100%;height:auto}
.lv-stage .lv-wide{min-width:1000px}
.lv-stage .lv-tall{min-width:400px;display:none}
.lv-hint{display:none}
/* Asked of the stage itself, so the answer is true on every platform and at every root
   font size: no viewport arithmetic, no scrollbar gutter to guess at. The hint promises
   that dragging reveals more, so it appears only when the stage is narrower than the
   tall canvas. */
@container (max-width:399px){.lv-hint{display:block;font-size:14px;color:var(--ink-soft);margin:8px 0 0}}
/* Which picture: the stage holds the wide canvas from 1000 px of its own width, which
   the breakout reaches at 1088 px of viewport. Asking the stage keeps those two numbers
   from having to agree. */
@container (max-width:999px){
  .lv-stage .lv-wide{display:none}
  .lv-stage .lv-tall{display:block;max-width:544px;margin:0 auto}}
/* A browser without container queries gets the same two decisions from the viewport, at
   the numbers the box arithmetic gives for a 16 px root: the stage is the viewport minus
   74 px (2 x 16px margin, 2 x 20px padding, 2 x 1px border), so it clears the wide
   canvas from 1074 px and the tall canvas from 474 px. A pixel out is no lie: the
   min-widths still hold. */
@supports not (container-type:inline-size){
  @media (max-width:1088px){
    .lv-stage .lv-wide{display:none}
    .lv-stage .lv-tall{display:block;max-width:544px;margin:0 auto}}
  @media (max-width:474px){.lv-hint{display:block;font-size:14px;color:var(--ink-soft);margin:8px 0 0}}
}
/* The whole drawing, at any width and on paper. Both selectors, because a plain svg rule
   loses on specificity to the min-widths above. */
@media print{.lv-stage{overflow:visible}
  .lv-stage .lv-wide,.lv-stage .lv-tall{min-width:0}}
.lv text{font-family:inherit}
/* SVG text sizes are user units of the viewBox, not page layout: px keeps the picture's
   proportions fixed when the reader's root font size changes. */
.lv .t-h{font-size:15px;font-weight:700;fill:#0d2b21}
.lv .t-core{font-size:34px;font-weight:700;fill:#0d2b21}
.lv .t-file{font-size:17px;font-weight:700;fill:#0d2b21}
.lv .t-b{font-size:14px;fill:#28473c}
.lv .t-js{font-size:14px;font-style:italic;fill:#2f6b4f}
.lv .t-s{font-size:14px;fill:#5d6b65}
.lv .t-s2{font-size:14px;fill:#28473c}
.lv .t-cap{font-size:14px;font-weight:700;letter-spacing:.06em;fill:#28473c}
.lv .t-kill{font-size:14px;font-weight:700;letter-spacing:.06em;fill:#8c3b2e}
.lv .t-k{font-size:14px;fill:#6b3229}
.lv .t-w{font-size:14px;fill:#8c3b2e}
.lv .t-loop{font-size:14px;fill:#5d6b65}
.lv .g{transition:opacity .45s ease}
.lv .pk{fill:#3f8f3f;opacity:0;offset-rotate:0deg;animation:lv-flow 3.2s linear infinite}
.lv .pk.back{fill:#7f9a90}
.lv .pk.warn{fill:#8c3b2e}
.lv .rays,.lv .glow{transform-box:fill-box;transform-origin:center;
  animation:lv-breathe 6s ease-in-out infinite}
.lv .strike{fill:none;stroke:#8c3b2e;stroke-width:1.6;stroke-dasharray:1;stroke-dashoffset:0;
  animation:lv-strike .9s ease-out both}
.lv .k1{animation-delay:1.2s}.lv .k2{animation-delay:1.6s}
.lv .k3{animation-delay:2s}.lv .k4{animation-delay:2.4s}
@keyframes lv-flow{0%{offset-distance:0%;opacity:0}12%,88%{opacity:1}
  100%{offset-distance:100%;opacity:0}}
@keyframes lv-breathe{0%,100%{opacity:.6;transform:scale(.97)}50%{opacity:1;transform:scale(1.03)}}
@keyframes lv-strike{from{stroke-dashoffset:1}}
@keyframes lv-run{0%{offset-distance:0%;opacity:1}23%{offset-distance:100%;opacity:1}
  25%,100%{offset-distance:100%;opacity:0}}
@keyframes lv-step{0%,23%{opacity:1}27%,96%{opacity:.18}100%{opacity:1}}
@keyframes lv-cap{0%,23%{opacity:1}25%,100%{opacity:0}}
@keyframes lv-restrike{0%{stroke-dashoffset:1}6%,100%{stroke-dashoffset:0}}
.lv-cap{position:relative;min-height:1.6em;margin:.75rem 0 0;font-weight:600;color:#0d2b21;
  display:none}
.lv-cap span{position:absolute;left:0;right:0;opacity:0}
#lv-play:checked~.lv-cap{display:block}
.lv-lenses,.lv-hosts{display:flex;flex-wrap:wrap;gap:.5rem;margin:1rem 0 0}
.lv-lenses label,.lv-hosts label{cursor:pointer;padding:.25rem .8rem;border-radius:999px;
  border:.09375rem solid var(--line,#dfe3e0);background:var(--paper,#f7f7f5);
  color:#28473c;font-size:.9rem;line-height:1.5}
.lv-lenses label:hover,.lv-hosts label:hover{border-color:#28473c}
.lv-play{margin-left:auto}
.lv-play .off,#lv-play:checked~.lv-lenses .lv-play .on{display:none}
#lv-play:checked~.lv-lenses .lv-play .off{display:inline}
.lv-play::before{content:"\\25B6\\FE0E  ";color:#3f8f3f}
#lv-play:checked~.lv-lenses .lv-play::before{content:"\\25A0\\FE0E  "}
.lv-panels{margin:1rem 0 0;font-size:.95rem;color:#28473c}
.lv-panels h3{font-size:1rem;margin:0 0 .3rem;color:#0d2b21}
.lv-panels p{margin:0}
.lv-p,.lv-ht{display:none}
.lv-p p+p{margin-top:.6rem}
.lv-hosts{margin:.25rem 0 .6rem}
.lv-hosts label{font-size:.875rem}
.lv-r[name=lv-host]:checked~.lv-panels .lv-ht-none{display:none}
.lv-ideas{margin:1.5rem 0 0;padding-top:1rem;border-top:.0625rem solid var(--line,#dfe3e0)}
.lv-ideas h3{font-size:1rem;margin:0 0 .5rem;color:#0d2b21}
.lv-ideas ul{list-style:none;margin:0;padding:0;display:grid;
  grid-template-columns:repeat(auto-fill,minmax(16rem,1fr));gap:.6rem}
.lv-ideas li{margin:0;padding:.6rem .75rem;border:.0625rem solid var(--line,#dfe3e0);
  border-radius:.5rem;font-size:.9rem;color:#28473c;background:var(--paper,#f7f7f5)}
.lv-ideas b{display:inline-block;font-size:.875rem;letter-spacing:.06em;text-transform:uppercase;
  padding:0 .45rem;border-radius:999px;margin-right:.3rem;vertical-align:.1em}
.lv-ideas .now{background:#0d2b21;color:#fff}
.lv-ideas .soon{background:#e4efe4;color:#0d2b21}
.lv-ideas .dir{border:.0625rem solid #5d6b65;color:#28473c}
.lv-ideas strong{color:#0d2b21}
.lv-ideas li.lead{grid-column:1/-1}
/* Paper: the whole picture lit and still, every lens text and host line as a list. */
@media print{
  .lv *{animation:none!important;transition:none!important}
  .lv .pk,.lv-lenses,.lv-hosts,.lv-ht-none,.lv-cap{display:none!important}
  .lv .g{opacity:1!important}
  .lv-p,.lv-ht{display:block!important;margin:0 0 .5rem}
}
@media (prefers-reduced-motion:reduce){
  .lv *{animation:none!important;transition:none!important}
  .lv .pk{display:none}
  .lv-cap{min-height:0}
  .lv-cap span{position:static;display:block;opacity:1}
}"""


def generated_css() -> str:
    rules: list[str] = []
    # Packets: idle flow along their arrow, and the timed run during playback.
    for name, d in PATHS.items():
        arrow = name.split("-", 1)[1]
        step = STEP[arrow]
        rules.append(f".lv .pk-{name}{{offset-path:path('{d}');"
                     f"animation-delay:{IDLE_DELAY[arrow]}s}}")
        rules.append(f"#lv-play:checked~.lv-stage .pk-{name}{{animation:lv-run {CYCLE}s linear "
                     f"infinite;animation-delay:{phase(step)}s}}")
    # Playback: each group is lit during its own step; s0 (the core) stays lit.
    for step in (1, 2, 3, 4):
        rules.append(f"#lv-play:checked~.lv-stage .s{step}{{animation:lv-step {CYCLE}s linear "
                     f"infinite;animation-delay:{phase(step)}s}}")
        rules.append(f"#lv-play:checked~.lv-cap .c{step}{{animation:lv-cap {CYCLE}s linear "
                     f"infinite;animation-delay:{phase(step)}s}}")
    for k in (1, 2, 3, 4):
        rules.append(f"#lv-play:checked~.lv-stage .k{k}{{animation:lv-restrike {CYCLE}s linear "
                     f"infinite;animation-delay:{phase(3) + .3 * k:.1f}s}}")
    # Lenses: dim everything, then light the lens's own groups, chip and panel.
    # Same specificity as the lighting rules below, which come later and so win.
    rules.append("#lv-all:not(:checked)~.lv-stage .g{opacity:.16}")
    chosen = ("background:#0d2b21;color:#fff;border-color:#0d2b21")
    focus = "outline:.125rem solid #3f8f3f;outline-offset:.125rem"
    for lens in ("all",) + LENSES:
        if lens != "all":
            rules.append(f"#lv-{lens}:checked~.lv-stage .l-{lens}{{opacity:1}}")
        rules.append(f"#lv-{lens}:checked~.lv-lenses [for=lv-{lens}]{{{chosen}}}")
        rules.append(f"#lv-{lens}:focus-visible~.lv-lenses [for=lv-{lens}]{{{focus}}}")
        rules.append(f"#lv-{lens}:checked~.lv-panels .lv-p-{lens}{{display:block}}")
    rules.append(f"#lv-play:checked~.lv-lenses .lv-play{{{chosen}}}")
    rules.append(f"#lv-play:focus-visible~.lv-lenses .lv-play{{{focus}}}")
    rules.append("#lv-play:checked~.lv-lenses .lv-play::before{color:#fff}")
    # Hosts: the chosen host's line, its chip, and its name on the ground, lit.
    for h in HOSTS:
        rules.append(f"#lv-h-{h}:checked~.lv-panels .lv-ht-{h}{{display:block}}")
        rules.append(f"#lv-h-{h}:checked~.lv-panels [for=lv-h-{h}]{{{chosen}}}")
        rules.append(f"#lv-h-{h}:focus-visible~.lv-panels [for=lv-h-{h}]{{{focus}}}")
        rules.append(f"#lv-host:checked~#lv-h-{h}:checked~.lv-stage .h-{h}"
                     "{fill:#0d2b21;font-weight:700;text-decoration:underline}")
    return "\n".join(rules)


def phase(step: int) -> int:
    """Negative delay that puts step N's window at (N-1)/4 of the cycle."""
    return -((CYCLE - (step - 1) * CYCLE // 4) % CYCLE)


def build_date() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return datetime.datetime.fromtimestamp(int(epoch), datetime.timezone.utc).date().isoformat()
    return datetime.date.today().isoformat()


def main() -> int:
    fragment = FRAGMENT.read_text(encoding="utf-8")
    used = set(re.findall(r"\{\{P:([\w-]+)\}\}", fragment))
    unused = {n for n in PATHS if not n.endswith("back")} - used
    unknown = used - set(PATHS)
    if unknown or unused:
        print(f"✗ path names: unknown {sorted(unknown)}, never drawn {sorted(unused)}", file=sys.stderr)
        return 1
    fragment = re.sub(r"\{\{P:([\w-]+)\}\}", lambda m: PATHS[m.group(1)], fragment)
    css = BASE_CSS + "\n" + generated_css()
    page = (TEMPLATE.read_text(encoding="utf-8")
            .replace("{{FIGURE_CSS}}", css)
            .replace("{{FIGURE}}", fragment.rstrip("\n"))
            .replace("{{BUILT}}", build_date()))
    left = re.findall(r"\{\{[A-Z_:]+[\w-]*\}\}", page)
    if left:
        print(f"✗ unsubstituted placeholders: {sorted(set(left))}", file=sys.stderr)
        return 1
    OUT.write_text(page, encoding="utf-8")
    CSS_OUT.write_text(css + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(HERE.parent.parent)} ({len(page.encode()) / 1024:.1f} KB), "
          f"figure {len((css + fragment).encode()) / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
