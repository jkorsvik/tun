---
name: tun-host
description: "Choose and publish a hosting route for a functional app: a read-only snapshot, a static interactive app, or an app with shared writes, sign-in, persistence or scheduled jobs. Use when someone asks to host a Tún artefact or app on GitHub Pages, Cloudflare static assets, Azure Static Web Apps or an ordinary static file server, asks whether it needs a backend, or proposes a static front end with a JSON API."
---

# Host a functional app

**Tier and cost, for the first reply:** Tier 1 remains the default: no server and no
admin. A static host adds a host owner plus access and approval checks. Shared writes,
sign-in, persistence or jobs make a separate application that needs security, data and
run ownership. The approval path and platform behaviour are unverified until checked
live.

Say that cost before choosing a platform. Do not promise an approval-free host.

This skill routes and publishes. It does not change the Tier 1 builders or templates, and
it does not add a server to the toolkit core. A production functional app lives in its own
workspace or repository, with its own owner and tests. Reference examples may live under
`examples/`; they do not change the core boundary. `tun-publish` remains the route for an
ordinary self-contained file. [Architecture and host checks](../../docs/35-hosting-and-functional-apps.md).

## Step 1: Choose by behaviour, not by product name

Ask only what is not already answered:

1. Does every reader get the same data?
2. After deployment, must anything change without a rebuild? Is the change local to one
   browser, or shared between people?
3. Does the app need sign-in, durable server state, live server data, or scheduled work?
4. Who is the audience, and who owns the host and the app after release?

Then route:

| Requirement | Route |
|---|---|
| A read-only snapshot; all needed data is known at build time | **Tier 1.** Use `tun-new`, `tun-verify`, then `tun-publish`. A web host is optional, not an upgrade |
| A real web origin, several static assets or client-side routes, but no trusted server work | **Static interactive app.** Follow Step 3 |
| Shared writes, sign-in enforced by the app, durable shared state, live server data, or scheduled jobs | **Backend application.** Follow Step 4 |
| A static front end that calls a JSON API | **Hybrid.** Follow Steps 4 and 5 |

The [generic artefact model](../../docs/08-generic-artifact-model.md) keeps the word
**connected** for local folder access with a per-open consent prompt. Do not use it for a
hosted app. If that local file pattern is enough, use it instead of adding a backend. For
delegated Microsoft Graph reads, follow [the existing hosted route](../../docs/23-hosted-route-it-brief.md)
and its five IT questions rather than inventing new scopes.

Local filters, calculations and drafts do not need a backend. Browser storage is not
shared or durable application storage.

If audiences need different shared static data, split it before writing. Build one
artefact or deployment per audience and protect each with its own folder, site or host
access boundary. A browser filter or hidden route protects nothing. If a shared backend
must return different records to different users, treat that as server-side
authorisation design, not as a static app. The toolkit adds no row-level security layer.

## Step 2: Name the release boundary before any upload

Before an outward-visible action, get the user's approval and record:

- the app owner and the person approving this release
- audience, data classification and intended access boundary
- source and release provenance
- host, environment and approval path
- what will be verified after deployment

This skill adds no platform measurement or approval. Treat product
capabilities, prices, lead times and approval requirements as unverified until the owner
or a live probe confirms them.

Every value shipped to a browser is readable by its audience. Keep credentials, private
keys, connection strings and signing secrets out of HTML, JavaScript, static environment
variables, source maps and build logs. Put required secrets only in the server's approved
secret store.

## Step 3: Publish a static interactive app

1. **Keep the artefact unchanged.** If the deliverable is already a self-contained Tier 1
   file, deploy those exact bytes. Run `tun-verify` from `file://` first. Do not rewrite
   it to make it look hosted.
2. **Build the static output.** For a multi-file app, use its own production build. The
   publish directory must contain `index.html` and every referenced asset. Use relative
   asset URLs when the app can live below a path prefix.
3. **Choose an existing approved host.** Prefer one the owner already operates:
   GitHub Pages, Cloudflare static assets, Azure Static Web Apps, or an ordinary static
   file server. Use the host table in the architecture doc for the checks specific to
   each. Repository permissions are not proof of who can open the deployed URL.
4. **Configure the request routes.** Serve assets with the right content type. Add an SPA
   fallback only for client-side page routes that need it. Never return `index.html` for
   a missing asset or an API request. Configure HTTPS, access control, caching and
   security headers where the host provides them.
5. **Deploy only the reviewed output.** Record the release identifier and source revision.
   Do not fetch the live page and use that rewritten copy as the next source.

Done when the hosted URL serves the reviewed release, the access boundary is proven, and
the browser checks in Step 6 pass.

## Step 4: Add the smallest backend that does the trusted work

Keep this application outside the toolkit core. Prefer an existing approved application
platform and datastore over new infrastructure. For a local synthetic demonstration of
persistent writes followed by a standalone export, see
[example 55](../../examples/55-functional-app/). It is a reference, not a production host.

1. Start with one small service and one datastore. Use server-rendered pages when that
   avoids an unnecessary separate front end. Add a separate JSON API only when the app
   needs one.
2. Use the organisation's approved identity flow. Authenticate on the server. Authorise
   every read and write on the server. Hiding a button or a route is not authorisation.
3. Validate every request. Use parameterised database access. Return errors that do not
   expose secrets, personal data or internal stack details.
4. Define the schema, migrations, backup and restore ownership. For writes, define
   concurrency behaviour and the audit record the use case needs.
5. For scheduled or background work, name the scheduler and owner. Make retries safe,
   normally with idempotent jobs and a visible failure state.
6. Add health checks, useful logs and an operation owner. Keep secrets and unnecessary
   personal data out of logs.

Done when denied requests fail on the server, data survives the required restart or
redeployment, job retry behaviour is proven, and an owner accepts the running service.

## Step 5: Use a hybrid only when the split earns its keep

A static front end plus a JSON API is useful when the front end and API need independent
release cycles, different scaling, or more than one client. Otherwise use the smaller
server-rendered route in Step 4.

1. Prefer one origin: static routes serve the front end and `/api/` serves JSON. This
   avoids making cross-origin credentials a default requirement.
2. Define the API contract: request and response shapes, errors, pagination, concurrency,
   and the provenance fields for the data. Return JSON errors from API routes, never the
   SPA fallback page.
3. If separate origins are necessary, use an explicit CORS allowlist. Configure cookies
   and CSRF protection for cookie-based authentication. Use the organisation's approved
   token flow for bearer authentication. Never place a long-lived credential in the
   static bundle.
4. Make the front end show loading, empty, error and stale-data states. A failed API must
   not leave an old number looking current.

Done when the browser and API agree on the contract, failure states are visible, and the
hosted routes return the intended content types.

## Step 6: Verify before publishing

A local build is not the release. Verify the actual hosted surface.

**Every route**

- Confirm the audience and access control with an unauthorised reader as well as an
  authorised one where those roles exist.
- Check the release provenance: source, extract or data time, build or release time,
  requester or owner, and row count when meaningful.
- Inspect the delivered HTML, JavaScript, JSON and source maps for secrets and data that
  the audience must not receive.
- Open the release in a real browser and look at it. Check a number or a state change
  against the source.
- Read the deployed URL back. Confirm that it serves the reviewed release, not a stale or
  edge-rewritten surprise.

**Tier 1 snapshot**

Run `tun-verify` from `file://` and review its screenshot. If the same file is also hosted,
repeat the smoke test through its web URL.

**Static interactive app**

Test the production output over HTTP before deployment. On the hosted URL, test the main
flow, assets, deep links, refresh, 404 behaviour and any SPA fallback. Check the target
browsers and viewports. Treat all unrun engines and devices as unverified.

**Backend or hybrid**

Exercise the real API with authorised and unauthorised requests. Test validation,
server-side authorisation, persistence across restart, migration or rollback, write
conflicts, job retries, and backup restoration at the level the use case requires. Check
that logs and error responses carry no secrets. Verify the front end against the deployed
API, not only a mock.

Publish only after the user approves the outward action. Report the URL, host, release,
owner, verified audience, provenance, checks run, and anything still unverified. Draft
announcements in full for approval; do not send them without an explicit go-ahead.
