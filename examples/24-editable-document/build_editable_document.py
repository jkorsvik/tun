#!/usr/bin/env python3
"""
build_editable_document.py — writes editable-document.html from notat.template.html.

The template holds the prose and the edit-mode code. This script inlines the token CSS
(tools/tun_tokens.py: the neutral palette, status colours and the light theme), stamps the
build date into the provenance block, and refuses to write a file that still holds an
unsubstituted {{TOKEN}}.

The token files' comments are stripped before inlining. They cite where each value came
from, which names the organisation and its design system, and core artefacts must not
(tools/check_core_is_generic.py). The provenance block names the palette source instead.

    python3 examples/24-editable-document/build_editable_document.py

Stdlib only. The build date honours SOURCE_DATE_EPOCH, so a rebuild with the same value is
byte-identical; without it the date is today's (a date, not a time, so two builds on the
same day agree).
"""
from __future__ import annotations

import datetime
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
TEMPLATE = HERE / "notat.template.html"
OUT = HERE / "editable-document.html"

sys.path.insert(0, str(REPO / "tools"))
import tun_tokens  # noqa: E402


def build_date() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    when = (datetime.datetime.fromtimestamp(int(epoch), datetime.timezone.utc)
            if epoch else datetime.datetime.now())
    return when.strftime("%Y-%m-%d")


def build() -> pathlib.Path:
    css, source = tun_tokens.load_token_css(("status-semantic.css", "theme-light.css"))
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\n\s*\n+", "\n", css)
    html = TEMPLATE.read_text(encoding="utf-8")
    for key, value in (("TOKEN_CSS", css.strip()),
                       ("TOKEN_SOURCE", tun_tokens.provenance_label(source)),
                       ("BUILT", build_date())):
        token = "{{" + key + "}}"
        if html.count(token) != 1:
            raise SystemExit(f"template must hold {token} exactly once, found {html.count(token)}")
        html = html.replace(token, value)
    left = re.findall(r"\{\{[A-Z0-9_]+\}\}", html)
    if left:
        raise SystemExit(f"unsubstituted placeholders: {sorted(set(left))}")
    OUT.write_text(html, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    out = build()
    print(f"wrote {out.relative_to(REPO)} ({out.stat().st_size / 1024:.1f} KB)")
