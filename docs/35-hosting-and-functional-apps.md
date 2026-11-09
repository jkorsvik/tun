# 35. Hosting and functional apps

**Reader:** user - you want to choose a host or decide whether an app needs a backend, not change the toolkit.

> **Status: DIRECTION, not measured for this toolkit.** This page adds no platform measurement and
> names no approved host. Product behaviour, access control, approval paths and
> operating cost must be checked with the platform owner and on the live environment.
> Measured artefact hosting remains in [26](26-hosting.md), the Microsoft Graph direction
> in [23](23-hosted-route-it-brief.md), and Atlassian Artifacts measurements in
> [29](29-atlassian-artifacts.md).

A host answers where bytes are served. An application architecture answers where trusted
work happens. Choose those separately. Do not start with a vendor list.

The [generic artefact model](08-generic-artifact-model.md) remains the authority for file
shapes. **Standalone**, **paired** and **connected** keep their existing meanings. Its
"Outside the tree: the hosted route" exception names a web app on a real `https://`
origin. [The hosted route](23-hosted-route-it-brief.md) remains the governance brief for
delegated Microsoft Graph access, including the five questions for IT. This page uses the
same outside-the-tree boundary for other functional apps. It does not redefine
**connected** or add another file pattern.

Tier 1 stays unchanged: a self-contained file, its existing builders, and the existing
`tun-verify` gate. Static hosting may deliver that same file, but it does not require a
new builder or a server in the toolkit core. Multi-file apps and backend apps are
separate applications with their own source, owner and tests.

## The decision boundary

| What the reader needs | Shape | Where the data and trusted work live | Governance consequence |
|---|---|---|---|
| Open, filter and calculate over a fixed extract | **Read-only snapshot** | In the self-contained artefact | Tier 1. No server. Use `tun-publish` |
| Open a web URL, use several static assets or client-side routes, with no shared server state | **Static interactive app** | Static files plus browser computation | A host owner, an access decision and any host approval |
| Share writes, enforce sign-in, keep durable shared state, read live server data, or run scheduled jobs | **Backend application** | A server and usually a datastore | Application, security, data and run ownership |
| Use a rich static client against those server capabilities | **Static front end plus JSON API** | Static client, server API and datastore | The backend cost plus an API contract and release coordination |

Escalate only for **trusted server** work. Visual complexity alone does not change the route. A static app
can have charts, forms, filters, local drafts and client-side routing. A backend becomes
necessary when another person must see a write, when the server must decide what a user
may do, or when state and jobs must outlive a browser.

A static app may read static JSON produced at build time. That is still a snapshot. An
app that calls a remote API is no longer static-only, even if its front end is hosted as
static files.

Hosting a Tier 1 artefact does not move it outside the file tree. A multi-file static app
or backend app uses the hosted exception. Neither changes the existing delivery tiers.

## Pattern 1: static files on a real web origin

```text
reviewed static output -> static host -> HTTPS -> browser
```

Use this when every reader in the intended audience can receive the same files.
There is no trusted application code at request time. Access control, if any, belongs to
the host or to the identity-aware proxy in front of it, and must cover every asset.

### Choose from four dependable host shapes

These are routing checks, not claims that a product is available or approved.

| Host | Choose it when | Confirm before deployment |
|---|---|---|
| **GitHub Pages** | An owner already has an approved repository-based static publishing route | Repository and organisation approval; source branch or workflow; publish directory; custom domain and HTTPS; who can open the deployed URL. Repository read permission alone does not prove site access |
| **Cloudflare static assets** | An owner already operates the account, zone and deployment route | Asset upload or build route; account and zone ownership; whether an access policy protects HTML, JavaScript, JSON and downloads; cache invalidation; edge rewrites and injected content |
| **Azure Static Web Apps** | An owner already has an approved Azure application route | Subscription and resource owner; environment and deployment approval; data classification; custom domain; the actual sign-in configuration. Treat any integrated authentication or API feature as unverified until exercised |
| **Ordinary static file server** | An existing HTTPS server can own the document root | Document root and release mechanism; TLS; content types; access control; security headers; caching; process and platform ownership; backup and restore of the published content |

Prefer an existing approved host over a new account or new infrastructure. If none is
available, the approval question comes before implementation of the release route.

### Route requests deliberately

1. Publish one reviewed output directory with `index.html` and all referenced assets.
2. Use relative asset URLs when deployment below a path prefix is possible.
3. Return the correct content type for every asset.
4. Add a single-page-app fallback only for page routes owned by the client router. A
   missing `.js`, `.json` or API request must produce an error, not `index.html` with a
   success status.
5. Configure caching so a new release is reachable. A common split is revalidation for
   HTML and long-lived caching only for content-hashed assets. Measure the chosen host
   rather than assuming its defaults.
6. Set the security headers the application can support. At minimum, review content
   security policy, `X-Content-Type-Options`, referrer policy and framing policy against
   the app's actual needs.
7. Deploy the source-controlled release, then read the hosted bytes back. A CDN or edge
   feature can change what the reader receives. Do not recover source from the live page.

## Pattern 2: the smallest backend that does the trusted work

```text
browser -> application service -> datastore
                         \-> scheduler or background worker
```

Start with one service and one datastore on an existing approved platform. A
server-rendered app is often smaller than a separate static client and API. Choose that
shape unless independent clients, releases or scaling make the split useful.

[Example 55](../examples/55-functional-app/) is a local, synthetic reference for this
boundary. It uses SQLite for persistent writes and exports the same rows as a script-free
standalone snapshot. It is not an internet-hardened deployment or a new toolkit tier.

The server owns the following jobs:

- **Authentication:** establish who the caller is through the organisation's approved
  identity flow.
- **Authorisation:** permit or deny every read and write on the server. Client-side route
  guards and hidden buttons are usability features only.
- **Validation and storage:** validate input, use parameterised data access, define
  migrations, and state backup and restore ownership.
- **Writes:** define concurrency, conflict and audit behaviour before the first shared
  write.
- **Jobs:** name the scheduler, make retries safe, expose failure, and assign an owner.
  Idempotent job design is the default.
- **Operations:** provide health checks, useful logs, error handling, release and rollback
  procedures, and a named run owner.

A read-only API is still a backend when it provides live server data or decides what the
caller may read. Removing writes does not remove authentication, authorisation or run
ownership.

## Pattern 3: static front end plus JSON API

```text
same origin, preferred
  /        -> reviewed static front end
  /api/    -> JSON API -> datastore and jobs
```

Use this hybrid when the split has a concrete benefit: independent release cycles,
independent scaling, or more than one client. Use the smaller backend pattern when none
of those benefits applies.

Prefer one origin. It reduces cross-origin credential and CORS cases. If separate origins
are necessary, use an explicit origin allowlist and test the actual deployed pair.
Cookie-based authentication needs deliberate cookie and CSRF settings. Bearer
authentication needs the organisation's approved token flow. No approach permits a
long-lived credential in the static bundle.

Write the API contract before wiring the client:

- request and response schemas, including null and empty behaviour
- errors, pagination and concurrency
- authentication and authorisation expectations per operation
- source and data-time provenance for reads
- release compatibility and rollback expectations

The API returns JSON errors with useful status codes. It never relies on the SPA
fallback. The client shows loading, empty, error and stale-data states, so a failed
request cannot make an old number look current.

## Security and access control

These rules apply to every hosted shape.

1. **The folder boundary remains for shared static data.** Split data before writing.
   Give each audience its own artefact, folder, site or deployment and its own access
   boundary. One shared file with a browser filter exposes every row in that file.
2. **No hidden row-level security.** A static route guard, hidden column, obscured URL or
   minified bundle is not a security control. A separate backend that returns different
   records to different users must enforce that decision on the server and return only
   the permitted records. The toolkit itself does not implement an RLS layer.
3. **Nothing secret goes to the browser.** Treat HTML, JavaScript, static JSON, static
   environment variables, source maps and client logs as reader-visible. Keep server
   secrets in an approved secret store and out of source and build logs.
4. **Authentication is not authorisation.** A valid sign-in does not grant every action.
   Check permission on the server or at a proven host boundary for every protected
   resource, including direct asset and API URLs.
5. **Verify the deny case.** Test an unauthenticated caller and an authenticated caller
   without permission where those roles exist. A successful admin request proves only
   the allow case.
6. **Classify before publishing.** The owner names the audience and data classification.
   A public static host is only for data approved for that public audience. Do not infer
   approval from the fact that upload is technically possible.

## Provenance

A hosted release must remain traceable.

- Keep the existing provenance block in a Tier 1 artefact unchanged: source data, extract
  time, build time, requester and row count.
- For a multi-file static app, show the equivalent source provenance in the app and record
  the source revision, build identifier and release identifier with the deployment.
- For live data, return or display the source identity and the data's own timestamp or
  version. The front-end build time does not say when the data was current.
- For writes, keep the actor, time and change history required by the use case. Do not
  confuse deployment provenance with a business audit trail.
- Show only provenance that the audience may know. Internal connection strings and secret
  source locations never become public provenance.

## Verification and release gate

A successful build proves only that a build ran. Publish the exact thing that passed the
checks relevant to its shape.

| Shape | Required evidence before release |
|---|---|
| Read-only snapshot | `tun-verify` passes from `file://`; a human reviews the screenshot; source numbers are spot-checked. If hosted, repeat the smoke test through the URL |
| Static interactive app | Production output tested over HTTP; main flow checked in a real browser; assets, deep links, refresh and 404 behaviour checked; target browsers and viewports named; hosted release read back |
| Backend application | Automated checks plus real-environment allow and deny requests; server-side authorisation; validation; persistence across restart; migration or rollback; write conflicts; job retry behaviour; logs and errors checked for secrets; backup restoration at the required level |
| Hybrid | All relevant static and backend checks; real client against the real API; contract and content types; loading, empty, error and stale states; cross-origin behaviour if applicable |

For every route, inspect the delivered client files for secrets and unauthorised data.
Confirm the audience at the actual URL. Record checks not run as **unverified**, including
browser engines and devices. After deployment, compare the release identifier and
provenance with what was approved.

The release owner approves the outward-visible deployment. The final report names the
URL, host, release, owner, audience, provenance, evidence and remaining unverified items.
An announcement is a separate outward action and needs its own approval.

## Deliberate limits and open product choices

- No server, backend framework, database or job runner enters the toolkit core.
- No Tier 1 builder or template changes to support these routes.
- No default host, identity provider configuration, secret store or runtime is chosen
  here. Those depend on approved platform and organisational standards.
- No product capability or approval time is claimed without a live check.
- Whether a future functional-app template belongs in a separate repository or plugin is
  a product decision. It is not a reason to expand the self-contained file core.
