#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Functional-app tests: real loopback HTTP, SQLite persistence and static export.

Stdlib only. Every database and snapshot lives in a temporary directory.

    python3 tests/test_functional_app.py
"""
from __future__ import annotations

import contextlib
import http.client
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from html.parser import HTMLParser
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "55-functional-app"
sys.path.insert(0, str(EXAMPLE))
import app as functional_app  # noqa: E402


class SnapshotParser(HTMLParser):
    """Read the exported cards back instead of trusting the exporter's row count."""

    FIELDS = {
        "field-action": "action", "field-owner": "owner", "field-due": "due_date",
        "field-created": "created_at", "field-completed": "completed_at",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[dict] = []
        self.current: dict | None = None
        self.capture: str | None = None
        self.controls = {"script": 0, "form": 0, "button": 0}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in self.controls:
            self.controls[tag] += 1
        if tag == "article" and "snapshot-decision" in attributes.get("class", "").split():
            self.current = {"id": int(attributes["data-decision-id"]),
                            "status": attributes["data-status"]}
        elif self.current is not None and tag == "h2":
            self.capture = "decision"
        elif self.current is not None and tag == "dd":
            classes = attributes.get("class", "").split()
            self.capture = next((self.FIELDS[name] for name in classes if name in self.FIELDS), None)

    def handle_data(self, data):
        if self.current is not None and self.capture:
            self.current[self.capture] = self.current.get(self.capture, "") + data

    def handle_endtag(self, tag):
        if tag in ("h2", "dd"):
            self.capture = None
        elif tag == "article" and self.current is not None:
            self.rows.append(self.current)
            self.current = None


class ResourceParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls: list[str] = []
        self.csp = ""

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        for name in ("src", "href", "poster", "data"):
            if attributes.get(name):
                self.urls.append(attributes[name])
        if tag == "meta" and attributes.get("http-equiv", "").lower() == "content-security-policy":
            self.csp = attributes.get("content", "")


class LocalClient:
    def __init__(self, server):
        self.host, self.port = server.server_address[:2]
        self.base = f"http://{self.host}:{self.port}"

    def request(self, method: str, path: str, payload=None, *, raw: bytes | None = None,
                content_type: str = "application/json", host: str | None = None):
        body = raw if raw is not None else (json.dumps(payload).encode("utf-8")
                                             if payload is not None else None)
        headers = {"Content-Type": content_type} if body is not None else {}
        if host is not None:
            headers["Host"] = host
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read()
        response_headers = dict(response.getheaders())
        status = response.status
        connection.close()
        if response_headers.get("Content-Type", "").startswith("application/json"):
            return status, response_headers, json.loads(data)
        return status, response_headers, data


@contextlib.contextmanager
def running_server(store):
    server = functional_app.make_server(store, port=0, quiet=True)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        yield LocalClient(server)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def valid_payload(**changes):
    payload = {"decision": "Use the shared decision log",
               "action": "Review the open actions on Friday",
               "owner": "Team coordination", "due_date": "2027-01-15"}
    payload.update(changes)
    return payload


class FunctionalAppTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = pathlib.Path(self.temporary.name)
        self.store = functional_app.Store(self.folder / "decisions.db")
        self.store.initialize()

    def tearDown(self):
        self.temporary.cleanup()

    def test_default_bind_is_loopback_and_seed_is_synthetic_and_idempotent(self):
        args = functional_app.parser().parse_args(["serve", "--db", str(self.store.path)])
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8000)
        self.assertIn("127.0.0.1", functional_app.local_hostnames("127.0.0.1", 80))
        self.assertIn("localhost", functional_app.local_hostnames("127.0.0.1", 80))
        self.assertIn("[::1]", functional_app.local_hostnames("::1", 80))
        self.assertEqual(self.store.seed(), 3)
        self.assertEqual(self.store.seed(), 0)
        rows = self.store.list()
        self.assertEqual(len(rows), 3)
        self.assertEqual([row["status"] for row in rows].count("completed"), 1)
        self.assertIn("synthetic", rows[-1]["decision"].lower())

    def test_validation_errors_are_specific_and_do_not_write_rows(self):
        with running_server(self.store) as client:
            status, _headers, body = client.request("POST", "/api/decisions", {})
            self.assertEqual(status, 400)
            self.assertEqual(body["error"]["code"], "validation_error")
            self.assertEqual(body["error"]["fields"], {
                "decision": "Decision is required.", "action": "Next action is required.",
                "owner": "Owner is required."})

            status, _headers, body = client.request(
                "POST", "/api/decisions", valid_payload(due_date="2027-02-30"))
            self.assertEqual(status, 400)
            self.assertIn("real date", body["error"]["fields"]["due_date"])

            status, _headers, body = client.request(
                "POST", "/api/decisions", valid_payload(decision="x" * 181, owner=12))
            self.assertEqual(status, 400)
            self.assertIn("180 characters", body["error"]["fields"]["decision"])
            self.assertEqual(body["error"]["fields"]["owner"], "Owner must be text.")

            status, _headers, body = client.request(
                "POST", "/api/decisions", valid_payload(extra="not accepted"))
            self.assertEqual(status, 400)
            self.assertIn("extra", body["error"]["fields"]["body"])

            status, _headers, body = client.request(
                "POST", "/api/decisions", raw=b"{not json")
            self.assertEqual((status, body["error"]["code"]), (400, "invalid_json"))
            status, _headers, body = client.request(
                "POST", "/api/decisions", valid_payload(), content_type="text/plain")
            self.assertEqual((status, body["error"]["code"]), (415, "unsupported_media_type"))
            status, _headers, body = client.request(
                "POST", "/api/decisions", raw=b" " * (functional_app.MAX_BODY + 1))
            self.assertEqual((status, body["error"]["code"]), (400, "invalid_length"))

            status, _headers, body = client.request("GET", "/api/decisions")
            self.assertEqual((status, body["count"]), (200, 0))

    def test_create_list_filter_and_complete_over_real_http(self):
        with running_server(self.store) as client:
            status, _headers, body = client.request("POST", "/api/decisions", valid_payload())
            self.assertEqual(status, 201)
            created = body["decision"]
            self.assertEqual(created["status"], "open")
            self.assertIsNone(created["completed_at"])
            self.assertTrue(created["created_at"].endswith("Z"))

            status, _headers, body = client.request("GET", "/api/decisions?status=open")
            self.assertEqual((status, body["count"]), (200, 1))
            self.assertEqual(body["decisions"][0], created)
            status, _headers, body = client.request("GET", "/api/decisions?status=completed")
            self.assertEqual(body["count"], 0)
            status, _headers, body = client.request("GET", "/api/decisions?status=unknown")
            self.assertEqual((status, body["error"]["code"]), (400, "invalid_status"))
            status, _headers, body = client.request("GET", "/api/decisions?status=")
            self.assertEqual((status, body["error"]["code"]), (400, "invalid_status"))

            path = f"/api/decisions/{created['id']}/complete"
            status, _headers, body = client.request("POST", path, {})
            self.assertEqual(status, 200)
            self.assertEqual(body["decision"]["status"], "completed")
            self.assertIsNotNone(body["decision"]["completed_at"])
            status, _headers, body = client.request("POST", path, {})
            self.assertEqual((status, body["error"]["code"]), (409, "already_completed"))
            status, _headers, body = client.request("POST", "/api/decisions/999/complete", {})
            self.assertEqual((status, body["error"]["code"]), (404, "not_found"))

    def test_loopback_host_and_json_content_type_are_request_boundaries(self):
        row = self.store.create(valid_payload())
        path = f"/api/decisions/{row['id']}/complete"
        with running_server(self.store) as client:
            status, _headers, body = client.request("POST", path)
            self.assertEqual((status, body["error"]["code"]), (415, "unsupported_media_type"))
            status, _headers, body = client.request(
                "POST", path, raw=b"status=completed",
                content_type="application/x-www-form-urlencoded")
            self.assertEqual((status, body["error"]["code"]), (415, "unsupported_media_type"))

            status, _headers, body = client.request("GET", "/api/decisions", host="evil.example")
            self.assertEqual((status, body["error"]["code"]), (403, "invalid_host"))
            status, _headers, body = client.request(
                "POST", "/api/decisions", valid_payload(), host="evil.example")
            self.assertEqual((status, body["error"]["code"]), (403, "invalid_host"))

            status, _headers, body = client.request("GET", "/api/decisions?status=open")
            self.assertEqual((status, body["count"]), (200, 1))
            status, _headers, body = client.request("POST", path, {})
            self.assertEqual((status, body["decision"]["status"]), (200, "completed"))

    def test_two_concurrent_completions_have_one_winner(self):
        row = self.store.create(valid_payload())
        path = f"/api/decisions/{row['id']}/complete"
        with running_server(self.store) as client:
            barrier = threading.Barrier(3)
            outcomes: list[int] = []

            def complete():
                barrier.wait()
                status, _headers, _body = client.request("POST", path, {})
                outcomes.append(status)

            threads = [threading.Thread(target=complete) for _ in range(2)]
            for thread in threads:
                thread.start()
            barrier.wait()
            for thread in threads:
                thread.join(timeout=5)
            self.assertEqual(sorted(outcomes), [200, 409])

    def test_sqlite_rows_and_completion_survive_server_restarts(self):
        with running_server(self.store) as client:
            _status, _headers, body = client.request("POST", "/api/decisions", valid_payload())
            decision_id = body["decision"]["id"]
        self.assertTrue(self.store.path.is_file())

        with running_server(self.store) as client:
            _status, _headers, body = client.request("GET", "/api/decisions")
            self.assertEqual(body["decisions"][0]["decision"], "Use the shared decision log")
            client.request("POST", f"/api/decisions/{decision_id}/complete", {})

        restarted = functional_app.Store(self.store.path)
        with running_server(restarted) as client:
            _status, _headers, body = client.request("GET", "/api/decisions?status=completed")
            self.assertEqual(body["count"], 1)
            self.assertEqual(body["decisions"][0]["id"], decision_id)
            self.assertEqual(body["decisions"][0]["status"], "completed")

    def test_export_refuses_a_missing_database_and_every_database_alias(self):
        missing = functional_app.Store(self.folder / "missing.db")
        missing_out = self.folder / "missing.html"
        done = subprocess.run([
            sys.executable, str(EXAMPLE / "app.py"), "export",
            "--db", str(missing.path), "--out", str(missing_out),
        ], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("does not exist", done.stderr)
        self.assertFalse(missing.path.exists())
        self.assertFalse(missing_out.exists())

        corrupt = self.folder / "corrupt.db"
        corrupt.write_bytes(b"not a sqlite database")
        done = subprocess.run([
            sys.executable, str(EXAMPLE / "app.py"), "export",
            "--db", str(corrupt), "--out", str(missing_out),
        ], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertNotIn("Traceback", done.stderr)
        self.assertIn("error:", done.stderr)

        self.store.seed()
        original = self.store.path.read_bytes()
        with self.assertRaises(ValueError):
            functional_app.export_snapshot(self.store, self.store.path, "Test")
        self.assertEqual(self.store.path.read_bytes(), original)

        alias = self.folder / "database-alias.html"
        try:
            alias.symlink_to(self.store.path)
        except OSError:
            pass  # Windows without Developer Mode: the same-file check above still runs.
        else:
            with self.assertRaises(ValueError):
                functional_app.export_snapshot(self.store, alias, "Test")
            self.assertEqual(self.store.path.read_bytes(), original)

    def test_committed_snapshot_equals_its_reproducible_build(self):
        out = self.folder / "gallery-snapshot.html"
        env = dict(os.environ)
        env.pop("SOURCE_DATE_EPOCH", None)
        done = subprocess.run([
            sys.executable, str(EXAMPLE / "build_snapshot.py"), "--out", str(out),
        ], cwd=ROOT, capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        committed = (EXAMPLE / "snapshot.html").read_bytes()
        if os.environ.get("TUN_REQUIRE_HEADERS") == "1":
            # export.sh prepends one publishing comment after the reproducible build. Remove
            # that comment only; every artefact byte before and after it must still match.
            header = re.match(br"(<!DOCTYPE html>\n)<!--\n  Copyright.*?-->\n", committed, re.S)
            self.assertIsNotNone(header, "published snapshot has no licence header")
            committed = header.group(1) + committed[header.end():]
        self.assertEqual(out.read_bytes(), committed)

    def test_export_matches_every_api_field_and_carries_provenance(self):
        with mock.patch.dict(os.environ, {"SOURCE_DATE_EPOCH": "1792836000"}):
            self.store.seed()
            self.store.create(valid_payload(
                decision='<img src="x" onerror="alert(1)"> & decide',
                action="A&B <b>bold</b>", owner="Synthetic <team>", due_date=None))
            self.store.complete(1)
            with running_server(self.store) as client:
                status, _headers, body = client.request("GET", "/api/decisions")
                self.assertEqual(status, 200)
                api_rows = body["decisions"]

            out = self.folder / "snapshot.html"
            done = subprocess.run([
                sys.executable, str(EXAMPLE / "app.py"), "export",
                "--db", str(self.store.path), "--out", str(out),
                "--requested-by", "Test suite",
            ], cwd=ROOT, capture_output=True, text=True,
               env=dict(os.environ, SOURCE_DATE_EPOCH="1792836000"))
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("4 decisions", done.stdout)
            text = out.read_text(encoding="utf-8")
            parsed = SnapshotParser()
            parsed.feed(text)

            expected = [{**row, "due_date": row["due_date"] or "No due date",
                         "completed_at": row["completed_at"] or "Not completed"}
                        for row in api_rows]
            self.assertEqual(parsed.rows, expected)
            self.assertEqual(parsed.controls, {"script": 0, "form": 0, "button": 0})
            self.assertNotIn('<img src="x"', text)
            self.assertIn("&lt;img src=", text)
            self.assertIn("A&amp;B &lt;b&gt;bold&lt;/b&gt;", text)
            self.assertIn("Source data : Local SQLite decision log (decisions.db)", text)
            self.assertIn("Requested by: Test suite", text)
            self.assertIn("Rows        : 4 decisions (2 open, 2 completed)", text)
            self.assertIn(f"Built       : {functional_app.now_iso()}", text)
            self.assertNotIn(str(self.folder), text)

    def test_assets_and_snapshot_declare_no_external_network_capability(self):
        with running_server(self.store) as client:
            resources = {}
            for path in ("/", "/app.css", "/app.js"):
                status, headers, body = client.request("GET", path)
                self.assertEqual(status, 200)
                self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
                self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                resources[path] = body.decode("utf-8")

        index = ResourceParser()
        index.feed(resources["/"])
        self.assertTrue(index.urls)
        self.assertTrue(all(url.startswith(("/", "data:")) for url in index.urls), index.urls)
        self.assertNotIn("@import", resources["/app.css"])
        self.assertNotIn("url(", resources["/app.css"])
        self.assertNotRegex(resources["/app.js"], r"https?://")
        self.assertNotRegex(resources["/app.js"], r"[\"']//[^\"']+[\"']")

        self.store.create(valid_payload())
        out = functional_app.export_snapshot(
            self.store, self.folder / "offline.html", "Test <script>alert(2)</script>")
        snapshot = out.read_text(encoding="utf-8")
        static = ResourceParser()
        static.feed(snapshot)
        self.assertIn("default-src 'none'", static.csp)
        self.assertTrue(all(url.startswith("data:") for url in static.urls), static.urls)
        self.assertNotIn("<script", snapshot.lower())
        self.assertNotRegex(snapshot, r"(?:src|href)=[\"']https?://")


if __name__ == "__main__":
    unittest.main(verbosity=2)
