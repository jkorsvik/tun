# 55. When a small server adds value

Tún's standalone artefacts are the right default for sharing a snapshot. They do not share
writes between readers. This example shows the boundary: a small local decision/action log
with persistent create and complete operations, followed by a read-only standalone export of
the same rows.

**Governance cost:** none for local use with the supplied synthetic data. No install, account,
licence, build step, Node runtime or admin approval is needed. Real data, multiple users, or a
non-loopback deployment needs the normal security, privacy and support review and is outside
this example's scope.

## Run it

From the repository root:

```bash
python3 examples/55-functional-app/app.py serve \
  --db work/functional-app/decisions.db \
  --seed
```

Open <http://127.0.0.1:8000>. Stop the server with Ctrl-C. `--seed` adds three synthetic rows
only when the log is empty. The caller selects the SQLite path; restarting with the same path
keeps every decision and completion.

On Windows, `py` can replace `python3`. The application uses only Python's standard library,
including `http.server` and `sqlite3`. HTML, CSS and JavaScript are hand-written. There are no
remote assets, package installs or external services.

To use another loopback port:

```bash
python3 examples/55-functional-app/app.py serve \
  --db work/functional-app/decisions.db \
  --host 127.0.0.1 \
  --port 8765
```

The default bind is `127.0.0.1`. Keep it. This is a local reference app, **not an
internet-hardened service**: it has no authentication, TLS, user permissions, CSRF defence,
rate limiting or audit identity. Do not expose it to a network or put real data in it.

## Export the same data as a standalone file

With the database in place, run:

```bash
python3 examples/55-functional-app/app.py export \
  --db work/functional-app/decisions.db \
  --out work/functional-app/decisions-snapshot.html \
  --requested-by "Team lead"
```

Open `decisions-snapshot.html` directly from disk. It needs no server and no JavaScript. It
contains every row returned by the unfiltered API, visible provenance, a matching provenance
comment, and no create or complete controls. This is the hybrid path: use the app for shared
current state and writes, then export a frozen artefact for distribution and offline reading.

`SOURCE_DATE_EPOCH` pins generated timestamps when a reproducible export is needed. The source
line uses only the database's base name, not its absolute path. Export refuses a missing
database path instead of creating an empty log, and refuses output paths that resolve to the
database itself.

The committed `snapshot.html` is the gallery's static view of this server-backed example.
Rebuild it from three synthetic rows with a pinned clock:

```bash
python3 examples/55-functional-app/build_snapshot.py
```

The live `index.html` stays the app client. The gallery deliberately embeds the standalone
snapshot instead, so opening the card never depends on an API that is not running.

## JSON API

All endpoints are same-origin and return JSON, including errors.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/decisions` | List all decisions; `?status=open` or `?status=completed` filters |
| `POST` | `/api/decisions` | Create from `decision`, `action`, `owner` and optional `due_date` |
| `POST` | `/api/decisions/{id}/complete` | Complete an open decision |

Create requests need `Content-Type: application/json`. Required text is trimmed and bounded;
dates must be real dates in `YYYY-MM-DD` form. Validation returns HTTP 400 with field-specific
messages. Unknown IDs return 404, and completing an already completed row returns 409 rather
than silently changing its history.

Example:

```bash
python3 -c "import json,urllib.request; body=json.dumps({'decision':'Keep one review log','action':'Review it on Friday','owner':'Team coordination','due_date':'2026-11-06'}).encode(); req=urllib.request.Request('http://127.0.0.1:8000/api/decisions',data=body,headers={'Content-Type':'application/json'}); print(urllib.request.urlopen(req).read().decode())"
```

## Verify it

The standard-library suite uses temporary directories and real HTTP connections to a loopback
server. It covers persistence across a restart, validation and conflict responses, API/static
row agreement, escaping, provenance and same-origin-only assets:

```bash
python3 tests/test_functional_app.py
```

The optional browser smoke needs the repository's Playwright verification extra; the app itself
does not. It exercises validation, create and complete in each engine, checks desktop and phone
layouts, opens the export from `file://` with JavaScript disabled, and fails on any external
HTTP request:

```bash
uv run --extra verify python examples/55-functional-app/verify_functional_app.py \
  --engines chromium,webkit \
  --output work/functional-app-smoke
```

The smoke writes live and snapshot screenshots into the selected output directory. Look at
them; HTTP assertions cannot see a broken layout.

## Limits

This is deliberately small. There is no login, multi-user concurrency model, deletion,
reopening, editing, pagination, migration framework or production deployment configuration.
SQLite and the standard-library server are enough to demonstrate the architectural boundary,
not a recommendation to operate a public service.
