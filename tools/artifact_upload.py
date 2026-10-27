#!/usr/bin/env python3
# Copyright (C) 2026 Jon-Mikkel Ryen Korsvik
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
artifact_upload.py — move one artefact's bytes to a presigned upload URL, and prove the store
kept them unchanged. Stdlib only, so it runs the same on Windows and macOS.

Built for hosts that publish a file in three steps, the way Atlassian Artifacts does over its
MCP server (docs/29-atlassian-artifacts.md):

    1. the agent asks the host for an upload slot, passing the file's exact length and checksum
    2. this tool PUTs the exact bytes to the slot's presigned URL
    3. the agent finalises (publishes) the upload with the id the host returned in step 1

The tool does steps 2 and an after-check. It never talks to the host's API itself and knows
no site, account or organisation: the URLs come from the host's own answers at run time.

    python3 tools/artifact_upload.py prepare FILE
        Print the JSON that step 1 needs: {"length", "checksum", "contentType"}.
        checksum is the base64 of the SHA-256 of the bytes (not hex), which is what
        Atlassian's createArtifactsUpload asks for.

    python3 tools/artifact_upload.py put FILE --checksum B64 [--content-type T] < url.txt
        PUT the bytes. The upload URL is read from standard input, never from the command
        line, because it carries a short-lived credential and argv shows up in process lists
        and shell history. Refuses to upload when FILE no longer matches --checksum: the slot
        was reserved for other bytes, and a mismatch would fail at the host, or worse, succeed.

    python3 tools/artifact_upload.py check FILE < download-url.txt
        GET the stored copy and compare it with FILE byte for byte. Prints the response's
        Content-Type and Content-Disposition, because those decide whether a browser runs the
        file or downloads it. A publish call's success is a receipt; this is the artefact.

Neither URL is ever printed. Errors name the host only.

Exit codes: 0 ok, 1 the transfer or the comparison failed, 2 usage or local file problem.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

#: The content types a single-file artefact host is likely to accept. Unknown suffixes must be
#: named with --content-type, rather than guessed: the type is part of the host's metadata, and
#: a wrong one decides how the store serves the file.
CONTENT_TYPES = {
    ".html": "text/html",
    ".htm": "text/html",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".css": "text/css",
    ".js": "text/javascript",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".pdf": "application/pdf",
}

TIMEOUT_S = 120


#: Anything URL-shaped. Every message passes through redact(), so no code path can print a
#: presigned URL by accident: they carry a live credential in their query string.
URLISH = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://\S+")


def redact(msg: str) -> str:
    return URLISH.sub("<url redacted>", msg)


def fail(msg: str, code: int) -> "None":
    print(f"✗ {redact(msg)}", file=sys.stderr)
    raise SystemExit(code)


def read_bytes(path: str) -> bytes:
    if "://" in path:
        fail("FILE looks like a URL; pass the local file, and the URL on standard input", 2)
    p = pathlib.Path(path)
    if not p.is_file():
        fail(f"not a file: {path}", 2)
    data = p.read_bytes()
    if not data:
        fail(f"empty file: {path} (a host rejects a zero-length upload)", 2)
    return data


def b64_sha256(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")


def content_type_for(path: str, override: str | None) -> str:
    if override:
        return override
    ct = CONTENT_TYPES.get(pathlib.Path(path).suffix.lower())
    if not ct:
        fail(f"unknown content type for {pathlib.Path(path).name}; pass --content-type", 2)
    return ct


def url_from_stdin(what: str) -> str:
    if sys.stdin.isatty():
        fail(f"pipe the {what} URL on standard input (it is never taken as an argument)", 2)
    url = sys.stdin.read().strip()
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" and parsed.hostname not in ("127.0.0.1", "localhost"):
        fail(f"the {what} URL must be https (got scheme {parsed.scheme or 'none'!r})", 2)
    if not parsed.hostname:
        fail(f"the {what} URL has no host", 2)
    return url


def host(url: str) -> str:
    return urllib.parse.urlparse(url).hostname or "?"


def cmd_prepare(a: argparse.Namespace) -> int:
    data = read_bytes(a.file)
    print(json.dumps({"length": len(data), "checksum": b64_sha256(data),
                      "contentType": content_type_for(a.file, a.content_type)}))
    return 0


def cmd_put(a: argparse.Namespace) -> int:
    data = read_bytes(a.file)
    actual = b64_sha256(data)
    if actual != a.checksum:
        fail(f"{pathlib.Path(a.file).name} changed since the upload slot was reserved "
             f"(checksum now {actual}); reserve a new slot with `prepare`", 1)
    url = url_from_stdin("upload")
    req = urllib.request.Request(url, data=data, method="PUT",
                                 headers={"Content-Type": content_type_for(a.file, a.content_type),
                                          "Content-Length": str(len(data))})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            status = r.status
    except urllib.error.HTTPError as e:
        fail(f"upload to {host(url)} refused: HTTP {e.code}", 1)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"upload to {host(url)} failed: {getattr(e, 'reason', e)}", 1)
    if not 200 <= status < 300:
        fail(f"upload to {host(url)} answered HTTP {status}", 1)
    print(f"✓ uploaded {len(data)} bytes to {host(url)} (HTTP {status})")
    return 0


def cmd_check(a: argparse.Namespace) -> int:
    data = read_bytes(a.file)
    url = url_from_stdin("download")
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=TIMEOUT_S) as r:
            got, headers, status = r.read(), r.headers, r.status
    except urllib.error.HTTPError as e:
        fail(f"download from {host(url)} refused: HTTP {e.code}", 1)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"download from {host(url)} failed: {getattr(e, 'reason', e)}", 1)
    print(f"  status               HTTP {status}")
    print(f"  content-type         {headers.get('Content-Type', '(none)')}")
    print(f"  content-disposition  {headers.get('Content-Disposition', '(none)')}")
    print(f"  bytes                local {len(data)}, stored {len(got)}")
    if got != data:
        fail("the stored copy differs from the local file", 1)
    print(f"✓ stored copy is byte-identical (sha256 {hashlib.sha256(got).hexdigest()[:16]}…)")
    return 0


class QuietParser(argparse.ArgumentParser):
    """argparse echoes rejected values ("unrecognized arguments: https://…?authToken=…").
    Pasting the upload URL as an argument is the obvious mistake, so the stock message would
    print the credential this tool exists to keep out of logs. Name the problem, not the value."""

    def error(self, message: str) -> "None":
        if "unrecognized arguments" in message:
            message = "unexpected extra argument (URLs go on standard input, never on the command line)"
        self.print_usage(sys.stderr)
        fail(message, 2)


def main(argv: list[str] | None = None) -> int:
    ap = QuietParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare", help="print length, checksum and content type")
    p.add_argument("file"); p.add_argument("--content-type")
    p.set_defaults(fn=cmd_prepare)
    p = sub.add_parser("put", help="PUT the bytes; upload URL on stdin")
    p.add_argument("file"); p.add_argument("--checksum", required=True); p.add_argument("--content-type")
    p.set_defaults(fn=cmd_put)
    p = sub.add_parser("check", help="compare the stored copy; download URL on stdin")
    p.add_argument("file")
    p.set_defaults(fn=cmd_check)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
