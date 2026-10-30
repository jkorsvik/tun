#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Local decision/action log with a JSON API and a static snapshot exporter.

The application uses only the Python standard library. It is a reference for the
point where shared, persistent writes justify a small server. It is deliberately
not an internet-hardened service: keep the default loopback bind.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import html
import json
import os
import pathlib
import re
import sqlite3
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).resolve().parent
MAX_BODY = 32 * 1024
TEXT_LIMITS = {"decision": 180, "action": 240, "owner": 80}
LABELS = {"decision": "Decision", "action": "Next action", "owner": "Owner"}
SEED_ROWS = (
    ("Use one decision log for the weekly review",
     "Bring the two open actions to Friday's review", "Team coordination", "2026-11-06"),
    ("Publish a read-only snapshot after each monthly review",
     "Export the log and share the standalone HTML file", "Reporting", "2026-11-30"),
    ("Keep the reference data synthetic",
     "Use team names instead of people's names", "Platform example", None),
)


def now_iso() -> str:
    """UTC seconds, with SOURCE_DATE_EPOCH available for reproducible exports."""
    pinned = os.environ.get("SOURCE_DATE_EPOCH")
    moment = (dt.datetime.fromtimestamp(int(pinned), dt.timezone.utc) if pinned
              else dt.datetime.now(dt.timezone.utc))
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str, fields: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.fields = status, code, message, fields or {}


class ValidationProblem(APIError):
    def __init__(self, fields: dict[str, str]):
        super().__init__(400, "validation_error", "Correct the fields below.", fields)


class Store:
    """One SQLite file; a short connection per operation keeps threaded requests isolated."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = pathlib.Path(path).expanduser().absolute()

    @contextlib.contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision TEXT NOT NULL,
                    action TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    due_date TEXT,
                    status TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'completed')),
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
            """)

    def seed(self) -> int:
        """Add three synthetic rows only to an empty log; never overwrite caller data."""
        with self.connection() as conn:
            if conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]:
                return 0
            stamp = now_iso()
            conn.executemany("""
                INSERT INTO decisions
                    (decision, action, owner, due_date, status, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [(*row, "completed" if i == 2 else "open", stamp,
                   stamp if i == 2 else None) for i, row in enumerate(SEED_ROWS)])
            return len(SEED_ROWS)

    def list(self, status: str = "all") -> list[dict]:
        if status not in ("all", "open", "completed"):
            raise APIError(400, "invalid_status", "Status must be all, open or completed.")
        where = "" if status == "all" else "WHERE status = ?"
        args = () if status == "all" else (status,)
        with self.connection() as conn:
            rows = conn.execute(f"""
                SELECT id, decision, action, owner, due_date, status, created_at, completed_at
                FROM decisions {where}
                ORDER BY CASE status WHEN 'open' THEN 0 ELSE 1 END,
                         due_date IS NULL, due_date, id
            """, args).fetchall()
        return [dict(row) for row in rows]

    def create(self, payload: object) -> dict:
        clean = validate_decision(payload)
        with self.connection() as conn:
            cursor = conn.execute("""
                INSERT INTO decisions (decision, action, owner, due_date, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (*[clean[name] for name in ("decision", "action", "owner", "due_date")],
                  now_iso()))
            row = conn.execute("SELECT * FROM decisions WHERE id = ?",
                               (cursor.lastrowid,)).fetchone()
        return dict(row)

    def complete(self, decision_id: int) -> dict:
        with self.connection() as conn:
            row = conn.execute("SELECT id FROM decisions WHERE id = ?",
                               (decision_id,)).fetchone()
            if row is None:
                raise APIError(404, "not_found", f"Decision {decision_id} does not exist.")
            # The row-count guard is the status check. Two threaded requests cannot both
            # complete the same row and receive 200.
            changed = conn.execute("""
                UPDATE decisions SET status = 'completed', completed_at = ?
                WHERE id = ? AND status = 'open'
            """, (now_iso(), decision_id))
            if changed.rowcount != 1:
                raise APIError(409, "already_completed",
                               f"Decision {decision_id} is already completed.")
            row = conn.execute("SELECT * FROM decisions WHERE id = ?",
                               (decision_id,)).fetchone()
        return dict(row)


def validate_decision(payload: object) -> dict[str, str | None]:
    if not isinstance(payload, dict):
        raise ValidationProblem({"body": "Expected a JSON object."})
    unknown = sorted(set(payload) - {"decision", "action", "owner", "due_date"})
    if unknown:
        raise ValidationProblem({"body": "Unknown field(s): " + ", ".join(unknown) + "."})
    errors: dict[str, str] = {}
    clean: dict[str, str | None] = {}
    for name, limit in TEXT_LIMITS.items():
        value = payload.get(name)
        if value is None:
            errors[name] = f"{LABELS[name]} is required."
            continue
        if not isinstance(value, str):
            errors[name] = f"{LABELS[name]} must be text."
            continue
        if not value.strip():
            errors[name] = f"{LABELS[name]} is required."
            continue
        value = value.strip()
        if len(value) > limit:
            errors[name] = f"{LABELS[name]} must be {limit} characters or fewer."
        else:
            clean[name] = value
    due = payload.get("due_date")
    if due in (None, ""):
        clean["due_date"] = None
    elif not isinstance(due, str):
        errors["due_date"] = "Due date must use YYYY-MM-DD."
    else:
        try:
            parsed = dt.datetime.strptime(due, "%Y-%m-%d").date()
            if parsed.isoformat() != due:
                raise ValueError("not canonical")
            clean["due_date"] = due
        except ValueError:
            errors["due_date"] = "Due date must be a real date in YYYY-MM-DD format."
    if errors:
        raise ValidationProblem(errors)
    return clean


def comment_text(value: object) -> str:
    # Keep user-supplied provenance inside the comment and make the no-script
    # property true even for markup-shaped input.
    safe = html.escape(str(value)).replace("--", "- -")
    return safe.replace("\r", " ").replace("\n", " ")


def snapshot_html(store: Store, requested_by: str) -> str:
    rows = store.list()
    extracted = now_iso()
    built = now_iso()
    source = f"Local SQLite decision log ({store.path.name})"
    open_count = sum(row["status"] == "open" for row in rows)
    cards = []
    for row in rows:
        status = "Open" if row["status"] == "open" else "Completed"
        values = {
            "action": row["action"], "owner": row["owner"],
            "due": row["due_date"] or "No due date",
            "created": row["created_at"], "completed": row["completed_at"] or "Not completed",
        }
        cards.append(f"""<article class="decision snapshot-decision" data-decision-id="{row['id']}" data-status="{row['status']}">
  <div class="decision-heading"><h2>{html.escape(row['decision'])}</h2>
    <span class="status status-{row['status']}">{status}</span></div>
  <dl class="details">
    <div><dt>Next action</dt><dd class="field-action">{html.escape(values['action'])}</dd></div>
    <div><dt>Owner</dt><dd class="field-owner">{html.escape(values['owner'])}</dd></div>
    <div><dt>Due</dt><dd class="field-due">{html.escape(values['due'])}</dd></div>
    <div><dt>Created</dt><dd class="field-created">{html.escape(values['created'])}</dd></div>
    <div><dt>Completed</dt><dd class="field-completed">{html.escape(values['completed'])}</dd></div>
  </dl>
</article>""")
    if not cards:
        cards.append('<p class="empty">The log has no decisions.</p>')
    provenance = (f"Source data: {source}; Extracted: {extracted}; Built: {built}; "
                  f"Requested by: {requested_by}; Rows: {len(rows)}")
    css = (HERE / "app.css").read_text(encoding="utf-8")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<link rel="icon" href="data:,">
<title>Decision log — read-only snapshot</title>
<!--
PROVENANCE (do not delete — this is how output gets traced back)
  Source data : {comment_text(source)}
  Extracted   : {extracted}
  Built       : {built}
  Requested by: {comment_text(requested_by)}
  Rows        : {len(rows)} decisions ({open_count} open, {len(rows) - open_count} completed)
This is a read-only, self-contained snapshot. It has no script and makes no network requests.
-->
<style>
{css}
.snapshot-banner{{margin:0 0 1rem}}
.snapshot-meta{{margin:0 0 1rem;color:var(--muted)}}
.snapshot-decision{{margin-bottom:1rem}}
</style>
</head>
<body>
<header><div class="inner"><p class="eyebrow">Tún hybrid example</p><h1>Decision log</h1>
<p>Read-only snapshot of the same SQLite rows served by the local app.</p></div></header>
<main>
<section class="notice snapshot-banner"><strong>Read-only snapshot.</strong>
Use the local app to create or complete a decision. This file is for sharing and offline reading.</section>
<p class="snapshot-meta">{len(rows)} decisions · {open_count} open · {len(rows) - open_count} completed</p>
<section aria-label="Decisions">{''.join(cards)}</section>
</main>
<footer><strong>Provenance</strong><br>{html.escape(provenance)}<br>
No server, script, font download or network connection is needed to read this file.</footer>
</body>
</html>
"""


def export_snapshot(store: Store, out: str | os.PathLike[str], requested_by: str) -> pathlib.Path:
    if not store.path.is_file():
        raise FileNotFoundError(f"SQLite database does not exist: {store.path}")
    store.initialize()
    destination = pathlib.Path(out).expanduser().absolute()
    same_path = destination.resolve(strict=False) == store.path.resolve(strict=False)
    same_file = destination.exists() and store.path.exists() and os.path.samefile(destination, store.path)
    if same_path or same_file:
        raise ValueError("The snapshot path must not overwrite the SQLite database.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(snapshot_html(store, requested_by))
    return destination


class AppServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, store: Store, quiet: bool = False):
        self.store, self.quiet = store, quiet
        super().__init__(address, Handler)


def local_hostnames(bound: str, port: int) -> set[str]:
    allowed = {f"{bound}:{port}", f"localhost:{port}"}
    if bound == "::1":
        allowed.update({f"[::1]:{port}", f"127.0.0.1:{port}"})
    if port == 80:  # Browsers omit the default HTTP port in Host.
        allowed.update({bound, "localhost"})
        if bound == "::1":
            allowed.update({"[::1]", "127.0.0.1"})
    return allowed


class Handler(BaseHTTPRequestHandler):
    server_version = "FunctionalApp/1.0"
    sys_version = ""

    def log_message(self, fmt, *args):
        if not self.server.quiet:
            super().log_message(fmt, *args)

    def send_bytes(self, status: int, body: bytes, content_type: str,
                   csp: str = "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", csp)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        self.close_connection = True

    def send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_bytes(status, body, "application/json; charset=utf-8")

    def send_error_json(self, error: APIError) -> None:
        detail = {"code": error.code, "message": error.message}
        if error.fields:
            detail["fields"] = error.fields
        self.send_json(error.status, {"error": detail})

    def require_local_host(self) -> None:
        """Keep DNS-rebinding callers away from the loopback-only reference server."""
        bound = self.server.server_address[0]
        if bound not in ("127.0.0.1", "localhost", "::1"):
            return  # A non-loopback bind is already outside this example's security boundary.
        port = self.server.server_address[1]
        if self.headers.get("Host", "").lower() not in local_hostnames(bound, port):
            raise APIError(403, "invalid_host", "Use the local address printed by the app.")

    def require_json(self) -> None:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise APIError(415, "unsupported_media_type", "Send JSON with Content-Type: application/json.")

    def read_json(self) -> object:
        self.require_json()
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise APIError(400, "invalid_length", "Content-Length must be an integer.")
        if length <= 0 or length > MAX_BODY:
            raise APIError(400, "invalid_length", f"JSON body must be 1 to {MAX_BODY} bytes.")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise APIError(400, "invalid_json", "The request body is not valid UTF-8 JSON.")

    def do_GET(self) -> None:
        try:
            self.require_local_host()
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path == "/api/decisions":
                query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
                status = query.get("status", ["all"])
                if len(status) != 1:
                    raise APIError(400, "invalid_status", "Pass status once: all, open or completed.")
                rows = self.server.store.list(status[0])
                self.send_json(200, {"decisions": rows, "count": len(rows)})
                return
            files = {"/": ("index.html", "text/html; charset=utf-8"),
                     "/app.css": ("app.css", "text/css; charset=utf-8"),
                     "/app.js": ("app.js", "text/javascript; charset=utf-8")}
            if parsed.path in files and not parsed.query:
                name, content_type = files[parsed.path]
                self.send_bytes(200, (HERE / name).read_bytes(), content_type)
                return
            if parsed.path == "/favicon.ico":
                self.send_bytes(204, b"", "image/x-icon")
                return
            raise APIError(404, "not_found", "That resource does not exist.")
        except APIError as error:
            self.send_error_json(error)
        except sqlite3.Error:
            self.send_error_json(APIError(500, "database_error", "The local database operation failed."))
        except OSError:
            self.send_error_json(APIError(500, "asset_error", "A local application asset could not be read."))

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_POST(self) -> None:
        try:
            self.require_local_host()
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/decisions":
                row = self.server.store.create(self.read_json())
                self.send_json(201, {"decision": row})
                return
            match = re.fullmatch(r"/api/decisions/([1-9]\d*)/complete", path)
            if match:
                self.require_json()
                row = self.server.store.complete(int(match.group(1)))
                self.send_json(200, {"decision": row})
                return
            raise APIError(404, "not_found", "That API endpoint does not exist.")
        except APIError as error:
            self.send_error_json(error)
        except sqlite3.Error:
            self.send_error_json(APIError(500, "database_error", "The local database operation failed."))


def make_server(store: Store, host: str = "127.0.0.1", port: int = 8000,
                quiet: bool = False) -> AppServer:
    store.initialize()
    return AppServer((host, port), store, quiet)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="serve the local app and JSON API")
    serve.add_argument("--db", required=True, help="caller-selected local SQLite file")
    serve.add_argument("--host", default="127.0.0.1", help="bind address (default: loopback only)")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--seed", action="store_true", help="seed an empty log with synthetic rows")
    export = commands.add_parser("export", help="write a read-only standalone HTML snapshot")
    export.add_argument("--db", required=True, help="local SQLite file to read")
    export.add_argument("--out", required=True, help="HTML file to write")
    export.add_argument("--requested-by", default="Local app operator")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    store = Store(args.db)
    if args.command == "export":
        try:
            out = export_snapshot(store, args.out, args.requested_by)
        except (FileNotFoundError, ValueError, sqlite3.Error) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        print(f"Wrote {out} ({len(store.list())} decisions)")
        return 0
    store.initialize()
    if args.seed:
        print(f"Seeded {store.seed()} synthetic decision(s)")
    server = make_server(store, args.host, args.port)
    host, port = server.server_address[:2]
    display_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    print(f"Serving http://{display_host}:{port} with SQLite file {store.path}")
    print("Local reference only: no authentication, TLS or internet hardening. Ctrl-C stops it.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
