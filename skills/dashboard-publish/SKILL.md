---
name: dashboard-publish
description: Publish a built standalone dashboard to SharePoint or OneDrive, confirm who can see it, produce a shareable link, and draft the announcement. Use when someone wants to share, publish, distribute, or send out a dashboard, or asks where to put it so colleagues can open it.
license: AGPL-3.0-or-later
---

# Publish a dashboard to SharePoint / OneDrive

## Before you publish

**The dashboard must have passed `dashboard-verify`.** If you have not seen a PASS
and looked at the screenshot in this session, run it now. Publishing an unverified
dashboard means someone opens a broken file — and the whole value proposition here is
that the artefact works on someone else's machine.

## Step 1 — Understand what you are about to do

Be explicit with the user, because this is the step where the security model becomes
real:

> "Whoever can open this SharePoint folder will be able to read **all** the data in
> this file — the numbers are inside it, not fetched from anywhere. So the folder's
> permissions *are* the dashboard's permissions. Which folder should it go in?"

Do not pick the folder yourself. Ask. Getting this wrong is the main way this project
could cause harm.

## Step 2 — Choose the destination

Two options, and the choice matters:

**A team SharePoint library** (usually right)
- permissions already reflect the intended audience
- the file is in a place people already look
- it syncs to members' laptops automatically

**Personal OneDrive** (for drafts and one-to-one sharing)
- fine for "let me show you this"
- wrong for anything recurring — it dies when the person changes role

If the site has a synced local path, the simplest reliable publish is a file copy. The
sync client then uploads it — often better than a Graph upload, because it puts the file
exactly where the user already navigates.

**Find the synced folder — the location differs per OS.** `python3 setup.py` prints it, or:

- **Windows:** `%OneDriveCommercial%`, or `C:\Users\<user>\Eksempel AS\<site>`
- **macOS:** `~/Library/CloudStorage/OneDrive-SharedLibraries-EksempelAS/<site>`

Then copy the file there with whatever the platform uses (`copy` / `cp`, or just drag it
in Explorer/Finder — this step does not need a terminal at all).

Otherwise upload via Microsoft Graph (the `ms365` MCP server):
- `upload-file-content` with `driveItem-id: "root:/<folder>/<name>.html:"`
- get the drive with `list-drives` (personal OneDrive is the one whose `webUrl` ends
  in `/Documents`) or `search-sharepoint-sites` → `list-drives` for a team site

## Step 3 — Confirm who can actually see it

Do not assume. Check:
- `list-drive-item-permissions` on the uploaded file, or
- read the parent folder's permissions

Report back plainly: *"This is in the Team X library, so the 14 members of Team X can
open it. Nobody else."*

If the answer is broader than the user expected, **say so before sharing the link**.

## Step 4 — Produce the link

Use `create-drive-item-share-link` with:
- `type: "view"` — viewers should not edit the artefact
- `scope: "organization"` — an internal link

⚠️ `type: "embed"` and `scope: "anonymous"` **do not work** in the organisation's tenant —
anonymous sharing is blocked (verified; `docs/01-tenant-constraints.md` row 3). Do not
try to route around it.

Set the user's expectation about what the link does:

> "Clicking the link downloads the file and it opens in the browser — that's how
> SharePoint serves HTML, and it's why the dashboard works offline afterwards. People
> with the folder synced can also just double-click it in Explorer/Finder."

This is important. If someone expects the link to open a live web page and instead
gets a download, they will think it is broken. Frame the download as the feature it is.

## Step 5 — Draft the announcement (do not send it)

Write the message — Teams post or email — and **show it to the user for approval
before anything is sent.** Never send on someone's behalf without an explicit go-ahead.

Keep it short and lead with what the reader gets:

```
<Title> — interaktivt dashboard

Ligger her: <link>
Du kan filtrere på <filters> og sortere tabellen.

Tallene er per <extract date>. Ingen Power BI-lisens nødvendig —
klikk lenken, filen åpnes i nettleseren.
```

## Step 6 — Close the loop

Remind them once:
- the numbers are a **snapshot** — ask for `dashboard-data` to refresh
- if they republish, the **link stays the same** (same path = new version, and
  SharePoint keeps the version history)

## Notes

- Overwriting the same path is the right way to update — the link keeps working and
  SharePoint retains previous versions.
- Do not rename files with dates in them (`report-2026-09.html`) unless the user wants
  a genuine archive; a stable filename keeps every existing link and bookmark alive.
- If the file carries a sensitivity label, uploading may behave differently. This is
  an untested assumption — see the open questions in `docs/01-tenant-constraints.md`.
