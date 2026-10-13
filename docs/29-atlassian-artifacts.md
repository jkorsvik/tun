# 29. Atlassian Artifacts as a host

> **Status:** measured 2026-10-12 on one Atlassian Cloud site, with Artifacts in beta, in desktop
> Chrome on macOS, signed in as the artifact's owner. Every statement below was measured unless
> it says **not measured** or **reasoned**. Artifacts is a beta product: re-run the probe
> (*Re-running the probe*, at the end) before you rely on a row that is older than a few weeks.

Atlassian Artifacts is a vendor-hosted library for files that an AI agent or a person produces:
HTML, Markdown, CSV and similar. Each artifact has one persistent link. A new version replaces the
content behind the same link. An artifact can be shared with named people, groups or teams, and
embedded in a Confluence page or a Jira work item.

For Tún it is a new row in [where an artefact can live](26-hosting.md). It is the first host in
that table that serves the file from a web page *and* needs no approval, because an organisation
that already uses Atlassian Cloud turns it on as a product setting.

## Publishing over the Atlassian MCP server (measured)

Three steps. The operation names are what the live server answered through its `discover`
operation. On 2026-10-12 Atlassian's public pages that list the server's tools did not list any
artifact operation, so read the live server, not the page.

| Step | Operation (through `executeWrite`) | Inputs | Gives back |
|---|---|---|---|
| 1. reserve | `createArtifactsUpload` | `cloudId`, `length` (exact bytes), `checksum` (base64 of SHA-256, not hex) | a presigned `url`, and `completionPayload.contentId` |
| 2. transfer | HTTP `PUT` of the exact bytes to that `url` | `Content-Type` header | `201` |
| 3. publish | `publishArtifact` | `cloudId`, `name`, `description` (1 to 1000 characters, indexed for search), `contentId`, `contentType`, and `id` to publish a **new version** of an existing artifact | `id`, `url` (the share link), `downloadUrl`, `confluenceEmbedHtmlFragment` |

`tools/artifact_upload.py` does steps 2 and an after-check, in stdlib Python so it runs on Windows
too. `prepare` prints the step 1 inputs. `put` refuses to upload a file that changed after
`prepare`. `check` downloads the stored copy and compares it byte for byte. Both URLs carry a
short-lived credential, so the tool reads them from standard input and never prints them.

Sharing is two more operations: `shareArtifact` and `revokeArtifactShare`, both taking identity
ARIs of the form `ari:cloud:identity::user|group|team/<id>`.

Pitfalls seen while measuring:

- The publish answer grants no named shares, but the artifact is **not** private. Measured
  2026-10-13: all four artifacts published with `publishArtifact` had access `OPEN`, which the
  host's own answer describes as "anyone in the organisation with the link can view this
  artifact". Whether that is the product default or a site setting is not measured. An earlier
  version of this page said "private by default". That was read from a tool description, not
  measured, and it was wrong.
- To read the level, look at the `access` field in a `revokeArtifactShare` answer. Revoking an
  audience that holds no share changes nothing and still returns it.
- The **access level** ("anyone with the link", "the whole organisation") cannot be set over the
  MCP server. Only named shares can. `revokeArtifactShare` says so in its own description: an
  artifact readable by link or by the organisation stays readable after every share is revoked.
- No delete operation and no version-list operation turned up in `discover`. Operation names that
  look plausible (`createArtifact`, `listArtifactVersions`, `deleteArtifact`) do not exist. Use
  only names that `discover` returned.
- Passing `responseFields` to `publishArtifact` returned an empty object. Do not filter its answer.

## What the store keeps (measured)

| Question | Answer |
|---|---|
| Bytes after a round trip | identical (SHA-256 compared) for a 119 KB dashboard and a 6.7 KB probe |
| `Content-Type` of the stored copy | `text/html`, as sent |
| `Content-Disposition` | none. Contrast SharePoint, which forces `attachment` ([01](01-tenant-constraints.md) row 1). There is no download-forcing control here to route around |
| Other headers | `x-content-type-options: nosniff`, `cache-control: max-age=2592000, must-revalidate` |
| A new version on the same `id` | same link, the viewer shows "Edited … ago" and the new content (measured for versions 2 to 5 of one artifact) |
| Size | a 51 MB HTML file was accepted, published and rendered. That is above Tún's own fail budget of 50 MB (`tools/build_dashboard.py`), so the project budget binds first. The host's own ceiling is not measured |

## What runs, in the viewer and in a Confluence embed (measured)

`probe/host-capability-probe.html` runs every check below inside the host and prints the results
on screen, CSP violations first. The `file://` column is the control: the same probe in headless
Chromium opened from disk, where every check passes.

| Capability | `file://` (control) | Artifacts viewer | Confluence page embed | What it means for Tún |
|---|---|---|---|---|
| Inline `<script>` runs | yes | **yes** | **yes** | The templates run |
| Origin | `file://` | `null`, an `about:` document | same | Same family as `file://`: no origin to fetch from |
| Framed | no | yes, two levels deep, sandbox `allow-scripts allow-same-origin allow-forms allow-modals allow-pointer-lock allow-downloads` | same sandbox | No `allow-popups`, no `allow-top-navigation` |
| `eval`, `new Function` | yes | **blocked** (`script-src`) | **blocked** | Templates use neither |
| `fetch` to the network, `data:` or `blob:` | yes | **blocked** (`connect-src`) | **blocked** | Templates fetch nothing |
| Worker from a `Blob` | yes ([01](01-tenant-constraints.md) row 20) | **blocked** (`worker-src`) | **blocked** | Stricter than `file://`. Templates use no Worker |
| `import()` of a `blob:` module, `<script src="blob:…">` | yes | **blocked** (`script-src-elem`) | **blocked** | |
| `<script src="./data.js">` | yes when the sibling exists ([01](01-tenant-constraints.md) row 14) | **fails** | **fails** | **Paired mode does not work here.** One artifact is one file, and an `about:` document has no folder |
| `localStorage`, `sessionStorage`, `indexedDB` | yes | **blocked** (`SecurityError`) | **blocked** | Nothing may persist between visits |
| `<img src="data:…">` | yes | not tested with a valid image | **loads** | |
| `DecompressionStream("gzip")` | yes | **yes** | **yes** | **The dense cube works** ([07](07-portable-cube.md)); it decodes with `atob` + `DecompressionStream` + `Response` and never calls `fetch` |
| `document.fullscreenEnabled` | true | **false** | **false** | The slide deck's fullscreen button is refused; the template already catches that and shows a message |
| Inline `on…=""` handler attributes | yes | yes | yes | |
| `a.download` attribute | supported | supported, not clicked | not clicked | Whether "Lagre datafil" really saves a file here is **not measured** |
| Viewport when the script starts | real size | real size in one load, **0 x 0** in two others | **0 x 0** | See next section |
| `resize` events after the frame gets its size | n/a | 0 | **0** | See next section |

CSP directives reported by `securitypolicyviolation`, identical in the viewer and in the embed:
`script-src` (eval), `connect-src` (an `https:` URL, `data:`, `blob:`), `worker-src` (`blob:`),
`script-src-elem` (`blob:`). No `img-src` violation.

### A frame that gets its size without a `resize` event

Inside a Confluence embed the artefact's script ran while the frame was 0 x 0. Three and a half
seconds later the frame was 1582 x 1249, and not one `resize` event had fired. Both chart templates
measured their cards at boot, fell back to a fixed width when they read 0, and redrew only on
`resize`. So they kept drawing for the fallback width: 640 px of drawing scaled into a 472 px card
in the single-file template, 560 into 481 in the cube.

Fixed in both templates: each one also watches its chart containers with a `ResizeObserver`.
`tests/test_chart_width_after_hidden_load.py` reproduces the host locally. It loads each example
in a hidden `<iframe>`, so the artefact boots at 0 x 0, swallows every `resize` event the way the
host does, then shows the frame and requires each chart's drawing width to equal its rendered
width. A control run lets `resize` fire. A mutant run disables the `ResizeObserver` and must fail.

Any hand-written page that sizes itself once at load has the same problem in this host. Measure
again when the element changes size, not when the window says so.

## Embedding in Confluence (measured)

`publishArtifact` returns `confluenceEmbedHtmlFragment`, a `native-embed:artifacts` macro in the
Confluence HTML body format. Four ways of putting an artifact into a page were tested on one
private page:

| Form | How it is written | Result |
|---|---|---|
| Native artifact embed | the returned `confluenceEmbedHtmlFragment`, unchanged | **Live and interactive.** Confluence stored it intact and added its own `macroId` |
| Embed card | `<a href="<share url>" data-card-appearance="embed"></a>` | **Live**, with the artifact's title as a link above it, and its own scroll bar |
| Inline smart link | `data-card-appearance="inline"` | A pill with the artifact's title |
| Block card | `data-card-appearance="block"` | Title, "Updated … ago", and an "Open preview modal" button |

Embeds load when they scroll into view, not with the page.

Interactivity inside an embed was proven for scripts and event handlers (the probe's own
asynchronous checks ran and wrote their rows). Driving a real slider or filter from outside was
not possible: the content is two cross-origin frames deep. A human check (drag one control) is
part of `tun-verify`'s screenshot review anyway.

**Who sees an embed.** A second account, an organisation member given read access to the private
page and no share on the artifacts, saw the native embed and the embed card live (2026-10-13).
The artifacts were `OPEN`, so this proves only that an organisation member sees an `OPEN`
artifact through an embed. Whether a page reader without a share sees a **private** artifact in
an embed is still not measured. Until it is, treat the artifact's own access level as the
boundary, and read `OPEN` as "the whole organisation".

## Access, classification, governance

- **The boundary is the artifact's sharing**, the way a folder is the boundary on SharePoint
  ([AGENTS.md](../AGENTS.md) rule 1). Split the data before writing, and publish one artifact per
  audience. A filter inside one shared artifact hides nothing.
- **Open to the organisation by default (measured, see above).** From the moment it is
  published, any organisation member with the link can read the artifact, and its description is
  indexed for search. Only a person in the Artifacts UI can make it private. `shareArtifact` adds
  named people, groups or teams; it narrows nothing. So publish here only what the whole
  organisation may see, or have the publisher set it private before the link is sent or embedded.
- **Shared artifacts become findable** in Atlassian search and the Teamwork Graph (Atlassian's
  product documentation; not measured here).
- **The file leaves the document store.** Artifacts is part of the Atlassian Cloud estate, not of
  the Microsoft 365 tenant this project otherwise lives in. The organisation's classification rules
  for Atlassian content apply. An installed plugin can state that ceiling as a tenant fact
  (`atlassian.artifacts` in `plugins/<id>/tenant-facts.json`, see
  [the plugin contract](22-plugin-contract.md)); without one, ask before publishing anything that
  is not plainly internal and non-sensitive.

## Consequences for each pattern

| Pattern ([08](08-generic-artifact-model.md)) | Fits? |
|---|---|
| **Standalone, bundled** | Yes. The best fit: one file, one link, versions in place |
| **Dense cube** | Yes. 51 MB was accepted, so the cube's size is never what rules it out |
| **Paired** | No. Refresh means publishing a new version of the whole file (`tun-data`) |
| **Connected** | No. Storage is blocked and the page cannot reach its folder. File System Access itself: not measured |
| **Slide deck** | Yes, without fullscreen |
| **Process diagram** | Not measured. It uses no feature the probe found blocked |

## Not measured

- What a page reader without a share sees when the artifact is private (above).
- Whether `OPEN` is the product default or a site setting, and whether an `OPEN` artifact shows
  up in search for people who never had the link.
- The host's own size ceiling (only that 51 MB is accepted).
- Firefox, Safari, mobile, and the Jira work item embed.
- Whether a Blob download ("Lagre datafil") saves a file.
- Search and Teamwork Graph behaviour, version history in the UI, and deletion.

## Re-running the probe

1. `python3 tools/artifact_upload.py prepare probe/host-capability-probe.html`
2. `createArtifactsUpload` with the printed `length` and `checksum`.
3. Pipe the returned upload URL into
   `python3 tools/artifact_upload.py put probe/host-capability-probe.html --checksum <checksum>`.
4. `publishArtifact`, with `id` set to an existing probe artifact to add a version.
5. Open the share link, and a page that embeds it, in a signed-in browser. Wait five seconds and
   read the two tables. Compare with the table above, and update this page in the same commit if a
   row changed ([AGENTS.md](../AGENTS.md) rule 4).
