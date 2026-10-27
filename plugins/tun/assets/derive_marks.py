#!/usr/bin/env python3
"""
derive_marks.py: write mark.svg and logo-mono.svg from logo.svg.

Stdlib only.

    python3 plugins/tun/assets/derive_marks.py           # rewrite the two derived files
    python3 plugins/tun/assets/derive_marks.py --check   # exit 1 if either is stale

logo.svg is the source. It is the logo from the public site, copied verbatim. The two
other files are derived from it, and a derived file that is stored must be re-derived by
a check, or the first hand edit makes it disagree with its source in silence.
tests/test_token_contract.py runs --check.

Every edit is an exact string replacement that must match exactly once. If logo.svg
changes shape, this fails loudly instead of writing a half-derived mark.

mark.svg, the square mark for favicons:
  * the frame keeps its height (148) and becomes a square: width 288 -> 148
  * the viewBox becomes 160 x 160, the same margin as the logo
  * only the middle letter, "u", is kept, at the same size and baseline
  * the text centre moves from x=150 to x=80, and the check moves with it (dx = -70),
    so the check sits over the "u" as it does in the logo

logo-mono.svg: the logo with both colours replaced by currentColor. Inlined in a page,
it takes the colour of the surrounding text. Opened on its own, it renders black.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "logo.svg"

LOGO_CENTRE, MARK_CENTRE = 150, 80
DX = MARK_CENTRE - LOGO_CENTRE

INK, ACCENT = "#0d2b21", "#3f8f3f"


def _body(text: str) -> str:
    """The logo without its leading comment, starting at <svg."""
    start = text.find("<svg")
    if start == -1:
        raise SystemExit(f"{SOURCE.name}: no <svg element")
    return text[start:]


def _replace_once(text: str, old: str, new: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{SOURCE.name}: expected {old!r} exactly once, found {n}. "
                         f"The logo changed shape; update derive_marks.py to match.")
    return text.replace(old, new)


def _header(what: str) -> str:
    return (f"<!-- {what}\n"
            f"     Generated from logo.svg by derive_marks.py. Do not edit by hand.\n"
            f"     Tún and this mark are unregistered trademarks: see TRADEMARK.md. -->\n")


def derive_mark(logo: str) -> str:
    out = _body(logo)
    for old, new in (
        ('viewBox="0 0 300 160"', 'viewBox="0 0 160 160"'),
        ('width="288"', 'width="148"'),
        (f'x="{LOGO_CENTRE}"', f'x="{MARK_CENTRE}"'),
        (">Tun</text>", ">u</text>"),
        ('d="M139 48 ', f'd="M{139 + DX} 48 '),
    ):
        out = _replace_once(out, old, new)
    return _header("The Tún square mark, for favicons and small sizes.") + out


def derive_mono(logo: str) -> str:
    out = _body(logo)
    for colour in (INK, ACCENT):
        if colour not in out:
            raise SystemExit(f"{SOURCE.name}: colour {colour} not found")
        out = out.replace(colour, "currentColor")
    if "#" in out:
        raise SystemExit(f"{SOURCE.name}: a colour is left after the mono replacement")
    return _header("The Tún logo in one colour (currentColor).") + out


TARGETS = {"mark.svg": derive_mark, "logo-mono.svg": derive_mono}


def main(argv: list[str]) -> int:
    check = "--check" in argv
    logo = SOURCE.read_text(encoding="utf-8")
    stale = []
    for name, derive in TARGETS.items():
        path = HERE / name
        want = derive(logo)
        if check:
            have = path.read_text(encoding="utf-8") if path.is_file() else None
            if have != want:
                stale.append(name)
        else:
            # open(), not write_text(newline=...): that argument needs Python 3.10.
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(want)
            print(f"wrote {path.relative_to(HERE.parents[2])}")
    if check:
        if stale:
            print(f"stale: {', '.join(stale)}. Run python3 {pathlib.Path(__file__).name}")
            return 1
        print(f"ok: {', '.join(TARGETS)} match {SOURCE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
