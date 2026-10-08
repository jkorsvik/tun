#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
feedback_link.py — the optional "Gi tilbakemelding" link inside a built artefact.

Used by tools/build_dashboard.py and tools/build_cube_dashboard.py when they get
`--feedback-to`. Stdlib only. Without that flag neither builder calls this, and the
artefact is byte for byte what it was before this module existed.

The link opens a prefilled message to wherever the builder pointed it: an e-mail
address (a mailto: link) or a forge's "new issue" page (an https URL with the title
and body in the query string). The reader sees the whole message in their own mail
client or browser and decides whether to send it. Nothing is sent from the file.

Two layers, so it works however the file is opened:

  * the static href, written here in Python, needs no JavaScript at all. It carries
    the artefact title, build time and source, and says "JavaScript: nei";
  * the script in templates/_feedback-link.html replaces it, when it can run, with a
    live snapshot: protocol, where it is shown, user agent, viewport, and how many
    script errors a window "error" listener caught. No fetch, no network.
"""
from __future__ import annotations

import html
import json
import pathlib
import re
import urllib.parse

PARTIAL = pathlib.Path(__file__).resolve().parents[1] / "templates" / "_feedback-link.html"

INTRO = ("Hva skjedde?\n\n\n"
         "Hva forventet du?\n\n\n"
         "-- Øyeblikksbilde, lagt inn automatisk. Fjern det du ikke vil sende. --\n")

FLAG_HELP = ("optional: add a 'Gi tilbakemelding' link that opens a prefilled e-mail "
             "(an address or mailto:) or a new issue (an https:// URL)")

EMAIL = re.compile(r"[^@\s<>\"'?&]+@[^@\s<>\"'?&]+\.[^@\s<>\"'?&]+")


def parse_target(target: str) -> tuple[str, list[str], bool]:
    """Return (base, [subject key, body key], crlf) for an address or issue URL.

    Raises ValueError with a message meant for the person running the build.
    """
    t = target.strip()
    address = t[len("mailto:"):] if t.lower().startswith("mailto:") else t
    if EMAIL.fullmatch(address):
        # RFC 6068 wants CRLF line breaks in a mailto body.
        return "mailto:" + address, ["subject", "body"], True
    if t.lower().startswith("https://"):
        url = urllib.parse.urlsplit(t)
        if not url.netloc or re.search(r"\s", t):
            raise ValueError(f"{target!r} is not a usable URL")
        if url.fragment:
            # The prefill goes after the URL, so it would land inside the fragment.
            raise ValueError(f"{target!r} has a #fragment; give the new-issue URL without it")
        # GitLab names its prefill fields differently from GitHub, Gitea and Forgejo.
        if "/-/issues" in url.path:
            return t, ["issue[title]", "issue[description]"], False
        return t, ["title", "body"], False
    raise ValueError(f"{target!r} is neither an e-mail address (or mailto: link) "
                     f"nor an https:// issue URL")


def compose(base: str, keys: list[str], crlf: bool, subject: str, body: str) -> str:
    """The static href. The template script builds the live one the same way."""
    if crlf:
        body = body.replace("\n", "\r\n")
    sep = "&" if "?" in base else "?"
    subject, body = (urllib.parse.quote(s, safe="") for s in (subject, body))
    return f"{base}{sep}{keys[0]}={subject}&{keys[1]}={body}"


def block(target: str, *, title: str, built: str, source: str) -> str:
    """Return the HTML to put in a template's {{FEEDBACK_BLOCK}} slot."""
    base, keys, crlf = parse_target(target)
    subject = f"Tilbakemelding: {title}"
    # The fixed part of the body is written once, here. The script appends its live
    # lines to it; without JavaScript the static href appends one line saying so.
    head = INTRO + "".join(f"{k}: {v}\n" for k, v in
                           (("Artefakt", title), ("Bygget", built), ("Kilde", source)))
    config = {"base": base, "keys": keys, "crlf": crlf, "subject": subject, "head": head}
    # "<" is escaped so no value (a title, say) can end the script element early or
    # put a literal tag into the file (docs/01-tenant-constraints.md row 25).
    config_js = (json.dumps(config, ensure_ascii=False)
                 .replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    static_href = compose(base, keys, crlf, subject, head + "JavaScript: nei")
    # The partial opens with its licence comment. The page it lands in already carries the
    # runtime header, so the comment stays in the source and out of the artefact.
    partial = re.sub(r"\A\s*<!--.*?-->\s*", "", PARTIAL.read_text(encoding="utf-8"), flags=re.S)
    return (partial.strip()
            .replace("{{FEEDBACK_HREF}}", html.escape(static_href, quote=True))
            .replace("{{FEEDBACK_CONFIG}}", config_js))
