# 26. Where a Tún artefact can live, and what works there

**Reader:** user — you want an artefact out of your own data and do not intend to change the toolkit.

> **Status:** a decision guide, written 2026-10-08. It adds no new tenant measurement. Every cell
> cites a row that was measured somewhere else, or says **not measured**.
>
> Short forms: **rN** is row N of [tenant constraints](01-tenant-constraints.md).
> **11§N** is section N of [responsiveness and browser support](11-responsiveness-and-browser-support.md).
> **ops** is a result observed while running a host, not a constraints row. Each ops result
> names its date. Some are written down only outside this repository, and the cell says so.

If a constraints row changes, re-check this table in the same commit ([AGENTS.md](../AGENTS.md)
rule 4).

The artefact is one file. Where it lives decides three things: whether its script runs,
whether its data can change without a rebuild, and who can open it. The file does not
change between hosts. The host does.

## The table

Patterns, from [the generic artefact model](08-generic-artifact-model.md): **standalone**
is one file, **paired** is a shell plus a `data.js` sidecar, **connected** is a page with
read and write access to its folder while open.

| Where it lives | Does JS run | Can the data refresh (standalone / paired / connected) | Auth, and who can see it | Size ceiling | Approvals | What breaks |
|---|---|---|---|---|---|---|
| **E-mail attachment** | Outlook iOS native preview: no, the no-JS layer shows (11§4, measured 2026-09-28). Desktop Outlook and Android: not measured | Standalone only, rebuild and resend. Paired: the sidecar would be a second attachment, not measured. Connected: not measured | None. Anyone holding the file. A sent file cannot be revoked (*Sharing outside* in [01](01-tenant-constraints.md)) | Not measured (open item in [01](01-tenant-constraints.md)) | None. Check the data classification first | Script-dependent pages are inert in the iOS preview. Forwarding is uncontrolled |
| **Teams message, preview card** | Yes, on PC and on the one phone tested (r22b). An unguarded Fullscreen call shows a visible script error (r21) | Standalone (r22b). Paired and connected: not measured | The OneDrive or SharePoint permissions behind the link (r10). Anonymous links are blocked (r11) | Not measured | None | The plain-text link under the same card renders source code on PC and mobile (r22c) |
| **OneDrive file or sharing link** | From the synced folder: yes (r7). Browser open: the file downloads, then runs locally (r1, r7). "Copy link" in an e-mail: PC yes, the one phone tested no (r22a) | Standalone: yes. Paired: yes from the synced folder, swap `data.js` and reload (r14, r15). A browser download fetches one file, so the sidecar does not follow (reasoned from r1, not measured). Connected: synced folder, Chromium, human-only check (r19) | Folder permissions. Organisation links work (r10). Anonymous links are blocked (r11) | Not measured. The project budget applies: warn above 20 MB, fail above 50 MB (`tools/build_dashboard.py`) | None | Mobile e-mail links (r22a). No iframe can render it (r13). No live fetch from the page (r8) |
| **SharePoint document library, inline preview** | Yes (r24, r25). One literal script-tag opener in prose disables every script on the page (r25) | Standalone: yes. Paired and connected: not measured in the preview | Library and folder permissions. The folder is the security boundary ([AGENTS.md](../AGENTS.md) rule 1) | Not measured | None | Fragment navigation and `:target` (r24). Stray script text (r25). `position:sticky` and `position:fixed` (r26). A different surface, the Graph `embed.aspx` viewer, shows its own chrome and not the page (r4) |
| **SharePoint site page** | Documented, not measured: only through an SPFx web part or an Embed web part in HTML-snippet mode. Both are admin-gated. Baseline Security Mode blocks tenant custom script (*What is genuinely closed off* in [01](01-tenant-constraints.md)) | Not measured | Site permissions. Not measured | Not measured | An admin-approved SPFx package. Approvability unknown (open item in [01](01-tenant-constraints.md)) | A library file cannot be framed into a page (r5, r13). Not measured past that |
| **Atlassian Artifacts, viewer or Confluence embed** | Yes, in a sandboxed frame with origin `null`, measured 2026-10-12 ([29](29-atlassian-artifacts.md)). `fetch`, Worker, `import()`, `eval` and storage are blocked by the host's CSP, stricter than `file://`. The frame can get its size without a `resize` event ([29](29-atlassian-artifacts.md), fixed in both chart templates) | Standalone: yes, publish a new version on the same link ([29](29-atlassian-artifacts.md)). Paired: no, `./data.js` cannot resolve. Connected: no | Open to the whole organisation through the link by default (measured, [29](29-atlassian-artifacts.md)). Only the Artifacts UI makes it private. `shareArtifact` adds named people, groups or teams. Who sees an embed of a private artifact without a share: not measured | 51 MB accepted and rendered, so the project budget (50 MB) binds first ([29](29-atlassian-artifacts.md)) | None beyond the product being turned on. The file leaves the Microsoft 365 tenant, so the organisation's classification rules for Atlassian content apply | Paired mode. Anything that fetches, persists or opens a new tab. Fullscreen is disabled |
| **Internal Pages on the enterprise forge** | Not measured. It is a real `https://` origin, so the `file://` blocks (r8, r20) should not apply, but no page has been opened there for this question | Not measured for any pattern | ops, 2026-09-20: the repository Pages API answered `status: built`, `public: false`, source `main` `/docs`, legacy (Jekyll) build. Every request first redirected to the forge sign-in. Recorded in a working session, not in this repository. Re-checked 2026-10-08 through the same API: unchanged, and an unauthenticated request got `307` to the forge sign-in | Not measured on the forge | ops, 2026-09, recorded in a working session: a repository admin switched Pages on for another repository through the API, no ticket | Readers without a forge account cannot open it. Behaviour of the Jekyll build on raw HTML: not measured |
| **Self-hosted static server** (stdlib Go binary, page embedded, `FROM scratch` image, behind a tunnel) | Yes. A site of the same shape runs one inline script per page, allowed by a per-page CSP hash (ops, written down outside this repository). The project's own public page carries no script by design | Standalone: yes, a push rebuilds and redeploys (ops, [AGENTS.md](../AGENTS.md) §8). Paired and connected: not measured | Public. Only for material meant for anyone. Internal data never goes here (11§10, r11) | What the binary embeds. The public page gates itself at 64 KB by choice (ops, [AGENTS.md](../AGENTS.md) §8) | None from the organisation. The host owner runs it | The edge proxy rewrote HTML: it injected a script and stripped comment fences (ops, [AGENTS.md](../AGENTS.md) §8). See *Serving it yourself* |
| **Hosted single-page app with Microsoft Graph** | Yes, a real origin ([23](23-hosted-route-it-brief.md)). Direction, not measured | Live reads through Graph on the reader's behalf, so no sidecar. Direction, not measured ([23](23-hosted-route-it-brief.md)) | Single sign-on. The reader sees only what the reader can already open, delegated `Files.Read` ([23](23-hosted-route-it-brief.md) §1, §3) | Not measured | App registration, an approved host, maybe a risk assessment ([23](23-hosted-route-it-brief.md), the five questions) | An expired registration, or no owner ([23](23-hosted-route-it-brief.md) §5) |

Three readings of the table:

1. **The sharing path decides, not the device.** The same file on the same phone runs from
   a Teams preview card and shows source from the link under it (r22b, r22c).
2. **No host fixes everything.** Every row has a "what breaks" cell. Build for the no-JS
   case anyway (11§3b), because the reader picks the path, not the author.
3. **Only the last three rows serve the artefact from a web origin.** The rows above them
   open it as a file, or not at all. That is why the rules for `file://` (r8, r14, r16, r20)
   apply almost everywhere. Atlassian Artifacts is a special case: a web page serves
   the file, but runs it in a frame with origin `null`, so it belongs with the `file://` rows for
   every rule about what the page itself may reach ([29](29-atlassian-artifacts.md)).

## Which hosts fit each pattern

**Standalone.** Fits the first four rows, Atlassian Artifacts, and the self-hosted server. The
forge is not measured. Best: a OneDrive or SharePoint folder with a link sent
through a Teams preview card (r22b), or the synced folder (r7). For a SharePoint preview,
obey r24 to r26: radio inputs instead of `:target`, no stray script text, a flex shell
instead of sticky or fixed headers. For e-mail, expect the no-JS layer to be what the
reader sees on a phone (11§4).

**Paired.** Fits the OneDrive or SharePoint synced folder, where `data.js` sits beside the
shell (r14, r15). One writer only ([13](13-paired-data-contract.md)). Does not fit Atlassian
Artifacts: `./data.js` does not load there (measured, [29](29-atlassian-artifacts.md)). Does not fit an
e-mail attachment or a browser download, because only one file travels (reasoned, not
measured). Not measured in
the SharePoint preview, on the forge, or on a self-hosted server.

**Connected.** Fits only a synced folder opened in Chromium, and only with a human to grant
the prompt each time (r19). It cannot be tested headlessly. Never the default
([08](08-generic-artifact-model.md)).

**Dense cube.** A standalone file, so it fits wherever standalone fits. It needs
`DecompressionStream`, which works from `file://` ([01](01-tenant-constraints.md), *What
replaced it*). 4 000 000 rows became a 0.81 MB file ([07](07-portable-cube.md)), so size is
not what rules a host out.

**Static site.** A set of self-contained pages behind a real origin: the self-hosted server
for public material, or internal Pages for readers with a forge account (not measured).
Serve each page also as a download (`Content-Disposition: attachment`), so a reader can
save it and check that it still works offline.

**Hosted app.** Only the hosted single-page app row, or SPFx on a site page. Both need an
approval. It is the only route to live tenant data with sign-in. Parquet with DuckDB-WASM
over tenant files needs the same kind of origin ([01](01-tenant-constraints.md), *Why
DuckDB-WASM cannot run from a `file://` page*).

## Serving it yourself

This is the recipe for the self-hosted row. It comes from running the project's public page.

**Headers.** Say in the headers what the page promises, so the browser enforces it if a
later edit forgets:

- `Content-Security-Policy: default-src 'none'` plus the minimum the page needs. For a page
  with inline styles, data-URI images and no script:
  `default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'; frame-ancestors 'none'`.
  `form-action`, `base-uri` and `frame-ancestors` do not fall back to `default-src`, so name
  them. A page with an inline script needs `script-src` with the hash of that script.
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`

**Caching.** Use a content-derived `ETag` and `Cache-Control: no-cache`. Do not send a fixed
`Last-Modified`. A fixed date once kept returning readers on an old page: their browser
sent an old `If-Modified-Since`, the date had not moved, so the server answered `304` and
the new page never arrived. A tag made from the bytes changes whenever the bytes change.

**HTTPS.** Behind a tunnel, the origin speaks plain HTTP and the edge sets
`X-Forwarded-Proto`. When it says `http`, answer `308` to `https://` plus a **fixed**
host. Never build the target from the `Host` header, because a client sets it. No header
means a local preview or a health check: serve the page.

A minimal Go stdlib version. `example.org` stands for the real host:

```go
package main

import (
	"bytes"
	"crypto/sha256"
	_ "embed"
	"encoding/hex"
	"net/http"
	"time"
)

//go:embed page.html
var page []byte

// A fixed host. Never build the redirect from r.Host: a client sets that.
const canonical = "https://example.org"

// The ETag comes from the bytes, so a new page always gets a new tag.
var etag = func() string {
	sum := sha256.Sum256(page)
	return `"` + hex.EncodeToString(sum[:8]) + `"`
}()

func serve(w http.ResponseWriter, r *http.Request) {
	// The edge sets X-Forwarded-Proto. No header means a local preview: serve it.
	if r.Header.Get("X-Forwarded-Proto") == "http" {
		http.Redirect(w, r, canonical+r.URL.RequestURI(), http.StatusPermanentRedirect)
		return
	}
	h := w.Header()
	h.Set("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; "+
		"img-src data:; form-action 'none'; base-uri 'none'; frame-ancestors 'none'")
	h.Set("X-Content-Type-Options", "nosniff")
	h.Set("Referrer-Policy", "no-referrer")
	h.Set("Content-Type", "text/html; charset=utf-8")
	h.Set("Cache-Control", "no-cache")
	h.Set("ETag", etag)
	// Zero modtime: no Last-Modified is sent, and If-Modified-Since is ignored.
	http.ServeContent(w, r, "page.html", time.Time{}, bytes.NewReader(page))
}

func main() {
	http.HandleFunc("GET /{$}", serve)
	srv := &http.Server{Addr: ":8080", ReadHeaderTimeout: 5 * time.Second}
	panic(srv.ListenAndServe())
}
```

When this page was written, the sketch compiled with Go 1.26.1 and passed a six-case test:

- `200`, with the three security headers, `Cache-Control` and no `Last-Modified`
- `304` on the current `ETag`
- `200` on a stale `ETag`
- `200` on an old `If-Modified-Since`
- `308` to the fixed host, with a hostile `Host` header
- `200` over `https`

With a fixed modtime instead of `time.Time{}`, the test failed. The test is not in this
repository.

**The edge can rewrite your HTML.** What the reader gets is not always what you built. In
operation, a CDN edge injected a decoder script into a page that promises no script, and
stripped the comment fences that opt a section out of that rewrite (ops,
[AGENTS.md](../AGENTS.md) §8). On another site, a bot-protection feature injected a script
into HTML it expected a browser to render, and left the download route alone. The e-mail
obfuscation feature still stripped the fences from the download (ops, 2026-10-06,
written down in that site's own server notes, outside this repository). So:

- After every deploy, and after every change to the edge settings, fetch the public URL and
  compare it byte for byte with the source. For example:
  `curl -s https://example.org/ -o delivered.html && cmp delivered.html page.html`.
- When the bytes differ, name the cause: an injected script, stripped fences, or a stale
  deploy. Each one needs a different fix, so one "out of date" message is not enough.
- Never recover the source by fetching the live page. That copy carries the edge's
  rewrites, and deploying it brings the bug back.
