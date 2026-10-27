---
name: tun-publish
description: Publish a built standalone dashboard to SharePoint, OneDrive or Atlassian Artifacts, confirm who can see it, produce a shareable link or a Confluence embed, and draft the announcement. Use when someone wants to share, publish, distribute, or send out a dashboard, asks where to put it so colleagues can open it, or wants it in Artifacts or on a Confluence page.
---

# Publish a dashboard to SharePoint, OneDrive or Atlassian Artifacts

**Tier and cost, for the first reply:** Tier 1, no licence, no workspace, no admin. The only
real decision is who can open the folder, and that belongs to the folder's owner rather than
to IT.

## Before you publish

**The dashboard must have passed `tun-verify`.** If you have not seen a PASS
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

Three options, and the choice matters:

**A team SharePoint library** (usually right)
- permissions already reflect the intended audience
- the file is in a place people already look
- it syncs to members' laptops automatically

**Personal OneDrive** (for drafts and one-to-one sharing)
- fine for "let me show you this"
- wrong for anything recurring — it dies when the person changes role

**Atlassian Artifacts** (when the readers work in Confluence or Jira)
- one persistent link that opens in the browser, no download; new versions keep the link
- embeds live in a Confluence page
- internal, non-sensitive material only, and no paired mode. Go to *Destination C* below,
  which replaces Steps 3 and 4

If the site has a synced local path, the simplest reliable publish is a file copy. The
sync client then uploads it — often better than a Graph upload, because it puts the file
exactly where the user already navigates.

**Find the synced folder — the location differs per OS.** `python3 setup.py` prints it (`py -3 setup.py` on Windows), or:

- **Windows:** `%OneDriveCommercial%`, or `C:\Users\<user>\Eksempel AS Bank ASA\<site>`
- **macOS:** `~/Library/CloudStorage/OneDrive-SharedLibraries-Eksempel ASBankASA/<site>`

Then copy the file there with whatever the platform uses (`copy` / `cp`, or just drag it
in Explorer/Finder — this step does not need a terminal at all).

Otherwise upload via Microsoft Graph (the `ms365` MCP server):
- `upload-file-content` with `driveItem-id: "root:/<folder>/<name>.html:"`
- get the drive with `list-drives` (personal OneDrive is the one whose `webUrl` ends
  in `/Documents`) or `search-sharepoint-sites` → `list-drives` for a team site

## Destination C — Atlassian Artifacts

Measured behaviour, limits and the reasons behind each step: `docs/29-atlassian-artifacts.md`.

Say these three in your first reply, before any upload:

- **Classification.** The file leaves the Microsoft 365 tenant for Atlassian Cloud, so the
  organisation's rules for Atlassian content apply. If an installed plugin states the
  ceiling (`plugins/*/tenant-facts.json`, key `atlassian.artifacts`), quote it. Otherwise
  ask what the organisation allows there. Material above that ceiling goes to a SharePoint
  library instead.
- **Mode.** Bundled and cube files work. A paired dashboard cannot load its `data.js`
  there: rebuild it with `--mode bundled` first.
- **Audience.** A new artifact is readable by everyone in the organisation who has the
  link (`OPEN`, measured). Only a person in the Artifacts UI can make it private. So
  publish here only what the whole organisation may see, or the user sets it private
  before the link goes anywhere. One artifact per audience, like one folder per audience.

Then:

1. `getAccessibleAtlassianResources`, and keep the `cloudId` of the site whose `products`
   include `artifacts`. Several sites: ask which.
2. `python3 tools/artifact_upload.py prepare <file>` prints `length`, `checksum`,
   `contentType`.
3. `executeWrite` with `createArtifactsUpload` and `{cloudId, length, checksum}`.
4. Pipe the returned `url` into `python3 tools/artifact_upload.py put <file> --checksum
   <checksum>` on standard input. The URL carries a credential: keep it out of command
   arguments, messages and files.
5. `executeWrite` with `publishArtifact` and `{cloudId, name, description, contentId,
   contentType}`. `description` is indexed for search: say what the dashboard shows and
   for whom. **Republishing an existing artifact:** add its `id` (the path segment after
   `/artifacts/` in its link), so the link stays and a new version appears.
6. Pipe the returned `downloadUrl` into `python3 tools/artifact_upload.py check <file>`.
7. Open the returned `url` in a signed-in browser and look at the dashboard there. This
   checks the host; `tun-verify` already checked the file.
8. **Access.** Tell the user, in these words: *"Anyone in the organisation with this link
   can open it now."* If the audience is narrower, the user sets the artifact to private
   in the Artifacts UI (the MCP cannot) before the link is sent or embedded. Then ask who
   should open it, resolve each person, group or team to an identity ARI
   (`lookupJiraAccountId`, `searchTeams`), show the list, and call `shareArtifact` once the
   user approves it. Read `access` in its answer: it must match what the user chose.
9. **Confluence page (optional).** `publishArtifact` returned `confluenceEmbedHtmlFragment`.
   Put it unchanged into the page body in HTML format, after the user has seen the whole
   page body. It renders live and interactive. An `OPEN` artifact renders for every
   organisation member who can open the page. What a page reader sees of a private
   artifact without a share is not measured yet, so say that.

Done when: step 6 printed `✓ stored copy is byte-identical`, you looked at the dashboard
through the link, the user approved the share list, and the access level matches the
audience the user chose. Report the link, the artifact id, the access level,
the named shares, and where it is embedded. Continue with Step 5.

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

⚠️ `type: "embed"` and `scope: "anonymous"` **do not work** in the Eksempel AS tenant —
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
- the numbers are a **snapshot** — ask for `tun-data` to refresh
- if they republish, the **link stays the same** (same path = new version, and
  SharePoint keeps the version history; in Artifacts, publish with the same `id`)

## Notes

- Overwriting the same path is the right way to update — the link keeps working and
  SharePoint retains previous versions.
- Do not rename files with dates in them (`report-2026-09.html`) unless the user wants
  a genuine archive; a stable filename keeps every existing link and bookmark alive.
- If the file carries a sensitivity label, uploading may behave differently. This is
  an untested assumption — see the open questions in `docs/01-tenant-constraints.md`.

To let readers report problems from inside the file, rebuild with `--feedback-to`, and use `tun-feedback` for anything the publishing step itself got wrong.
