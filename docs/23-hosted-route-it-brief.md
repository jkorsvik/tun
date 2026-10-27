# 23. The hosted route, and the questions only IT can answer

**Reader:** user — you want an artefact out of your own data and do not intend to change the toolkit.

> **Status: DIRECTION, not measured, not approved.** Written up from an internal brief
> drafted in September 2026 to open the conversation with IT architecture and security.
> Nothing on this page has been built or probed. Whether the brief was ever sent is not
> recorded here.

Every other page in this repository is about an artefact that is a **file**: standalone,
paired or connected (see [the generic artefact model](08-generic-artifact-model.md)). This
page is about the one route that is **not** a file pattern at all: a small web application,
hosted on a real `https://` origin, that signs the reader in and reads their OneDrive or
SharePoint files through Microsoft Graph on their behalf.

It matters because it is the only route that removes the ceilings the file patterns share.
It needs no sidecar next to the shell, no permission prompt per open, and no `file://`
origin `null` (so the `Worker`, `fetch` and `import()` blocks in
[tenant constraints](01-tenant-constraints.md) do not apply). The cost is that it is an
application, and an application needs an owner, an approval and a host.

## Do not confuse it with "connected"

The word "connected" is already taken in this repository, and the two things behave very
differently:

| | **connected** (a file pattern) | **hosted** (this page) |
|---|---|---|
| What runs | the shared `.html` file itself, opened locally | a web app on an approved host |
| How it reaches data | `showDirectoryPicker`, File System Access API | Microsoft Graph, delegated OAuth |
| Who grants access | the reader, with a prompt, every time | the tenant, once, through an app registration |
| Browser support | Chromium only | any modern browser |
| Needs IT | no | yes, for registration and hosting |
| Testable headlessly | no (constraints row 19) | yes, like any web app |

## What the application would need

### 1. An app registration in Entra ID

- Type **single-page application**, with **delegated** Microsoft Graph permissions only.
  Never application permissions: those give the app access regardless of who is signed in,
  which is far broader than the job needs.
- Minimum scope **`Files.Read`**, reading only files the signed-in user can already read.
  Not `Files.Read.All`, and no write scope unless a real need appears.
- Redirect URIs registered exactly, pointing at the real hosted address from point 2.

### 2. A host

A file somebody double-clicks cannot do this. It must sit on a real `https://` address:

- **Option A:** an approved internal web host or app platform, for example Azure Static Web
  Apps or App Service inside the organisation's own Azure tenant.
- **Option B:** a SharePoint page built with SPFx, the supported way to run custom code in
  SharePoint, as opposed to dropping an `.html` file into a library, which is already
  measured as blocked ([tenant constraints](01-tenant-constraints.md) rows 1 to 5). This is
  the same SPFx question that blocks Tier 2 in [the architecture](02-architecture.md).

### 3. Sign-in and authorisation

- Single sign-on with the reader's existing work account. No new usernames or passwords.
- Every read happens on the reader's behalf with the reader's existing rights. The app can
  never see a file the reader could not open themselves.
- No secrets in the page. Only the standard OAuth flow through MSAL.js, Microsoft's own
  library.

### 4. Data classification

- The classification of the data shown decides whether this route is suitable at all, and
  whether extra controls (conditional access, IP restrictions, logging) are needed.
- The app stores nothing outside Microsoft 365. It is a view, not a data store.

### 5. Operation and ownership

- Somebody owns the app registration and the host over time: renewals, and changes Microsoft
  makes to permissions or libraries.
- Somebody decides what happens when it breaks, for example an expired registration.

### 6. What it deliberately does not do

- No writing back to OneDrive or SharePoint. Read only.
- No user database and no passwords of its own.
- No data stored or cached beyond the reader's browser session.

## The five questions

Take the brief to IT architecture and security as a **request for guidance, not a finished
solution**. These five answers decide whether this is a light approval or a project:

1. Who has the mandate to create and approve an app registration, and what is the approval
   path for an internal app with delegated read access to user data?
2. Which hosting platform is already approved for small internal tools built by business
   teams rather than by IT? Is there an established low-threshold route, or does everything
   go through the ordinary development process?
3. Is delegated SSO through MSAL.js compatible with the current authentication requirements
   for internal tools, or must specific settings (MFA, conditional access) be configured on
   the registration?
4. Given what the data contains, does this kind of solution need a formal risk assessment or
   a DPIA before it may be used?
5. Can the business team operate it, or does it need formal IT ownership as a run service?

## Where this sits in the plan

The hosted route is the most likely answer to two open items at once: the in-page embedding
of Tier 2 (if option B), and the real HTTP origin that Tier 3 requires. It changes nothing
for Tier 1. The file patterns stay the default, because they need none of the above.
