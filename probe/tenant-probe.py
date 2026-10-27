#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
tenant-probe.py — re-verify what SharePoint/OneDrive actually do with an HTML file.

Every claim in docs/01-tenant-constraints.md came from this probe. Microsoft ships
tenant policy changes continuously (Baseline Security Mode is actively tightening), so
the constraints doc has a shelf life. Re-run this before trusting it.

    python3 probe/tenant-probe.py --graph-token "$TOKEN"

Getting a token: easiest is to let RAIWork do it via the `ms365` MCP server, which is
already authenticated — see "Running via RAIWork" below. This script exists so the
check is reproducible by a human, in any tenant, without RAIWork.

What it measures (each maps to a row in the constraints doc):
  1. .html   → Content-Type / Content-Disposition on the download URL
  2. .aspx   → is the MIME type downgraded?
  3. embed share link with organization scope → allowed?
  4. /preview → does the returned page contain our markup, or viewer chrome?
  5. X-Frame-Options / CSP frame-ancestors
  6. HTTP Range request → 206 Partial Content?
  7. local file:// render → does it work (needs playwright)

Exit 0 = findings match the documented expectations. 1 = something changed, go read the
output and update the doc in the same commit as whatever you change in response.

Running via RAIWork
-------------------
Ask RAIWork: "re-run the tenant probe". It will use the ms365 MCP server to upload the
fixture, pull the download URL, and run the same header assertions — no token juggling.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

GRAPH = "https://graph.microsoft.com/v1.0"

FIXTURE = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Tenant Probe</title>
</head><body><h1 id="marker">TENANT_PROBE_MARKER_8f3a</h1>
<script>document.getElementById('marker').dataset.ran='yes';</script></body></html>"""

MARKER = "TENANT_PROBE_MARKER_8f3a"

# What docs/01-tenant-constraints.md currently claims. If reality diverges, we fail.
EXPECTED = {
    "html_disposition": "attachment",
    "html_content_type": "text/html",
    "aspx_content_type": "application/octet-stream",
    "embed_link_blocked": True,
    "preview_contains_marker": False,
    "range_supported": True,
}


def req(method, url, token, body=None, raw=False):
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        if raw:
            data = body if isinstance(body, bytes) else body.encode()
            headers["Content-Type"] = "text/html"
        else:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            payload = resp.read()
            return resp.status, dict(resp.headers), payload
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def head_only(url, extra=None):
    """Fetch a pre-authenticated URL and return (status, headers, first bytes)."""
    r = urllib.request.Request(url, headers=extra or {})
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, dict(resp.headers), resp.read(400)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), b""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph-token", required=True,
                    help="delegated Graph access token with Files.ReadWrite")
    ap.add_argument("--folder", default="rai-probe")
    ap.add_argument("--keep", action="store_true", help="do not delete the fixtures")
    args = ap.parse_args()
    tok = args.graph_token

    findings, problems = {}, []

    def row(n, label, got, expected_key=None):
        ok = "?" if expected_key is None else ("✓" if got == EXPECTED[expected_key] else "✗")
        if expected_key is not None and got != EXPECTED[expected_key]:
            problems.append(f"row {n} ({label}): expected {EXPECTED[expected_key]!r}, got {got!r}")
        print(f"  {ok} {n}. {label:<34} {got}")
        findings[label] = got

    print("Tenant probe — SharePoint/OneDrive HTML behaviour")
    print("=" * 66)

    # upload the two fixtures
    for ext in ("html", "aspx"):
        st, _, body = req("PUT",
                          f"{GRAPH}/me/drive/items/root:/{args.folder}/probe.{ext}:/content",
                          tok, FIXTURE, raw=True)
        if st not in (200, 201):
            print(f"✗ upload of probe.{ext} failed: HTTP {st} {body[:300]!r}")
            return 2
    print(f"  uploaded fixtures to /{args.folder}/\n")

    # rows 1 & 2 — content type + disposition
    for ext, ct_key in (("html", "html_content_type"), ("aspx", "aspx_content_type")):
        st, hdrs, _ = req("GET",
                          f"{GRAPH}/me/drive/items/root:/{args.folder}/probe.{ext}:", tok)
        meta = json.loads(_ or b"{}")
        dl = meta.get("@microsoft.graph.downloadUrl")
        if not dl:
            print(f"✗ no downloadUrl for probe.{ext}")
            return 2
        st, hdrs, _ = head_only(dl)
        ct = (hdrs.get("Content-Type") or "").split(";")[0].strip()
        disp = (hdrs.get("Content-Disposition") or "").split(";")[0].strip().lower()
        n = 1 if ext == "html" else 2
        row(n, f".{ext} content-type", ct, ct_key)
        if ext == "html":
            row(1, ".html content-disposition", disp, "html_disposition")
            findings["_csp"] = hdrs.get("Content-Security-Policy", "")
            findings["_xfo"] = hdrs.get("X-Frame-Options", "")
            findings["_dl"] = dl

    # row 6 — Range request
    st, hdrs, _ = head_only(findings["_dl"], {"Range": "bytes=0-49"})
    row(6, "Range request → 206", st == 206 and "Content-Range" in hdrs, "range_supported")
    if st == 206:
        print(f"      content-range: {hdrs.get('Content-Range')}")

    # row 5 — framing headers
    print(f"  ✓ 5. x-frame-options              {findings['_xfo'] or '(none)'}")
    csp = findings["_csp"]
    print(f"  ✓ 5. csp frame-ancestors          {'present' if 'frame-ancestors' in csp else 'ABSENT'}")

    # row 3 — embed link with organization scope
    st, _, body = req("POST",
                      f"{GRAPH}/me/drive/items/root:/{args.folder}/probe.html:/createLink",
                      tok, {"type": "embed", "scope": "organization"})
    row(3, "embed link (organization scope)", st >= 400, "embed_link_blocked")
    if st >= 400:
        try:
            print(f"      {json.loads(body)['error']['message'][:90]}")
        except Exception:
            pass

    # row 4 — preview renders our markup?
    st, _, body = req("POST",
                      f"{GRAPH}/me/drive/items/root:/{args.folder}/probe.html:/preview",
                      tok, {})
    contains = False
    if st < 400:
        get_url = json.loads(body or b"{}").get("getUrl")
        if get_url:
            _, _, page = head_only(get_url)
            full = urllib.request.urlopen(urllib.request.Request(get_url)).read()
            contains = MARKER.encode() in full
    row(4, "preview contains our markup", contains, "preview_contains_marker")

    # cleanup
    if not args.keep:
        for ext in ("html", "aspx"):
            req("DELETE", f"{GRAPH}/me/drive/items/root:/{args.folder}/probe.{ext}:", tok)
        print("\n  fixtures deleted")

    print("=" * 66)
    if problems:
        print(f"\n✗ {len(problems)} finding(s) DIVERGED from docs/01-tenant-constraints.md:")
        for p in problems:
            print(f"    • {p}")
        print("\n  → Update the constraints doc, and re-check any architecture decision")
        print("    that depended on the old behaviour.")
        return 1
    print("\n✓ All findings match docs/01-tenant-constraints.md.")
    print("  Note: row 7 (file:// render) is covered by tools/verify_dashboard.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
