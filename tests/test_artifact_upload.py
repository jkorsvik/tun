#!/usr/bin/env python3
"""Tests for tools/artifact_upload.py.

Stdlib only, no network beyond 127.0.0.1, no browser. A local HTTP server stands in for the
host's presigned upload and download URLs, records what it received, and can be told to
refuse, to corrupt the stored copy, or to serve a header.

  A. prepare — length and base64 SHA-256 agree with an independent computation
  B. put     — the exact bytes and content type arrive; a refusal fails; a file that changed
               after `prepare` is never uploaded; the URL is taken from stdin only
  C. check   — identical bytes pass; one flipped byte fails; headers are reported
  D. secrecy — the credential-bearing query string never appears in any output
  E. control — the suite notices when the checksum guard is removed (mutation)

Every case runs the real script as a subprocess.

    python3 tests/test_artifact_upload.py
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "artifact_upload.py"
SECRET = "authToken=SECRET-DO-NOT-PRINT-7f3a"

PASS = FAIL = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


class Store:
    """What the fake host received, and how it should behave next."""
    def __init__(self) -> None:
        self.body = b""
        self.ctype = ""
        self.puts = 0
        self.refuse = False
        self.corrupt = False
        self.disposition = ""


def make_server(store: Store) -> http.server.ThreadingHTTPServer:
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep test output readable
            pass

        def do_PUT(self):
            store.puts += 1
            n = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(n)
            if store.refuse:
                self.send_response(403); self.end_headers(); return
            store.body, store.ctype = body, self.headers.get("Content-Type", "")
            self.send_response(201); self.end_headers()

        def do_GET(self):
            body = store.body
            if store.corrupt and body:
                body = bytes([body[0] ^ 1]) + body[1:]
            self.send_response(200)
            self.send_header("Content-Type", store.ctype or "application/octet-stream")
            if store.disposition:
                self.send_header("Content-Disposition", store.disposition)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def run(tool: pathlib.Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(tool), *args], input=stdin,
                          capture_output=True, text=True, timeout=60)


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="tun-upload-test-"))
    try:
        art = tmp / "artefact.html"
        art.write_bytes("<!doctype html><p>Tún æøå 1 500,50</p>\n".encode("utf-8"))
        data = art.read_bytes()
        want = base64.b64encode(hashlib.sha256(data).digest()).decode()

        store = Store()
        srv = make_server(store)
        url = f"http://127.0.0.1:{srv.server_address[1]}/upload/x?{SECRET}"
        outputs: list[str] = []

        print("A. prepare")
        r = run(TOOL, "prepare", str(art)); outputs += [r.stdout, r.stderr]
        try:
            got = json.loads(r.stdout)
        except json.JSONDecodeError:
            got = {}
        check("prints JSON and exits 0", r.returncode == 0 and bool(got), r.stderr)
        check("length is the byte count, not the character count",
              got.get("length") == len(data) and len(data) != len(data.decode()), str(got))
        check("checksum is base64 SHA-256 of the bytes", got.get("checksum") == want, str(got))
        check("content type from .html", got.get("contentType") == "text/html", str(got))
        odd = tmp / "x.unknownext"; odd.write_bytes(b"x")
        r = run(TOOL, "prepare", str(odd)); outputs += [r.stdout, r.stderr]
        check("unknown suffix is refused, not guessed", r.returncode == 2, r.stderr)
        empty = tmp / "e.html"; empty.write_bytes(b"")
        r = run(TOOL, "prepare", str(empty)); outputs += [r.stdout, r.stderr]
        check("empty file is refused", r.returncode == 2, r.stderr)

        print("B. put")
        r = run(TOOL, "put", str(art), "--checksum", want, stdin=url); outputs += [r.stdout, r.stderr]
        check("upload exits 0", r.returncode == 0, r.stderr)
        check("server received the exact bytes", store.body == data)
        check("server received the content type", store.ctype == "text/html", store.ctype)
        before = store.puts
        art2 = tmp / "changed.html"; art2.write_bytes(data + b"<!-- edited -->")
        r = run(TOOL, "put", str(art2), "--checksum", want, stdin=url); outputs += [r.stdout, r.stderr]
        check("a file changed after prepare exits 1", r.returncode == 1, r.stderr)
        check("... and is never sent", store.puts == before, f"puts {before} -> {store.puts}")
        store.refuse = True
        r = run(TOOL, "put", str(art), "--checksum", want, stdin=url); outputs += [r.stdout, r.stderr]
        check("a refused upload (403) exits 1", r.returncode == 1, r.stderr)
        store.refuse = False
        r = run(TOOL, "put", str(art), "--checksum", want, url); outputs += [r.stdout, r.stderr]
        check("the URL is not accepted as an argument", r.returncode == 2, r.stderr)
        r = run(TOOL, url); outputs += [r.stdout, r.stderr]
        check("a URL in place of the subcommand is refused", r.returncode == 2, r.stderr)
        r = run(TOOL, "put", url, "--checksum", want, stdin=url); outputs += [r.stdout, r.stderr]
        check("a URL in place of FILE is refused", r.returncode == 2, r.stderr)
        r = run(TOOL, "put", str(art), "--checksum", want, stdin="http://example.com/u?x=1")
        outputs += [r.stdout, r.stderr]
        check("a non-https remote URL is refused", r.returncode == 2, r.stderr)

        print("C. check")
        store.body, store.ctype, store.disposition = data, "text/html", ""
        r = run(TOOL, "check", str(art), stdin=url); outputs += [r.stdout, r.stderr]
        check("identical stored copy exits 0", r.returncode == 0, r.stderr)
        check("reports the content type", "text/html" in r.stdout, r.stdout)
        check("reports a missing Content-Disposition as (none)", "(none)" in r.stdout, r.stdout)
        store.disposition = "attachment"
        r = run(TOOL, "check", str(art), stdin=url); outputs += [r.stdout, r.stderr]
        check("reports Content-Disposition: attachment", "attachment" in r.stdout, r.stdout)
        store.corrupt = True
        r = run(TOOL, "check", str(art), stdin=url); outputs += [r.stdout, r.stderr]
        check("one flipped byte exits 1", r.returncode == 1, r.stdout + r.stderr)
        store.corrupt = False

        print("D. secrecy")
        leaked = [o for o in outputs if "SECRET-DO-NOT-PRINT" in o or "/upload/x" in o]
        check(f"no output carries the URL path or its token ({len(outputs)} streams read)",
              not leaked and len(outputs) >= 20, leaked[0][:120] if leaked else "")

        print("E. mutation control")
        mutant = tmp / "artifact_upload_mutant.py"
        src = TOOL.read_text(encoding="utf-8")
        guard = "    if actual != a.checksum:\n"
        check("the checksum guard is where the control expects it", src.count(guard) == 1)
        mutant.write_text(src.replace(guard, "    if False:\n"), encoding="utf-8")
        before = store.puts
        r = run(mutant, "put", str(art2), "--checksum", want, stdin=url)
        check("without the guard, the changed file IS sent (so section B can see the guard)",
              store.puts == before + 1 and r.returncode == 0, f"rc {r.returncode}")

        srv.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"PASS: {PASS}  FAIL: {FAIL}")
    return 0 if FAIL == 0 and PASS > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
