# 0002. The download is the delivery mechanism

- **Status:** Accepted
- **Date:** 2026-10-10
- **Related docs:** [`docs/01-tenant-constraints.md`](../01-tenant-constraints.md), [`docs/11-responsiveness-and-browser-support.md`](../11-responsiveness-and-browser-support.md)

## Context

Live measurements against SharePoint and OneDrive showed that every uploaded `.html` file is served with `Content-Disposition: attachment`, `.aspx` renames downgrade to `application/octet-stream`, anonymous share links are blocked tenant-wide, and iOS/macOS Quick Look disables JavaScript in attachment previews.

## Decision

Do not fight or defeat `Content-Disposition: attachment` (it is a tenant XSS control). Treat SharePoint/OneDrive as a permissioned document store and design every Tier 1 artefact as a single self-contained HTML file that:

- opens directly from `file://` with zero network requests (no CDN scripts, external fonts, or remote images),
- inlines its CSS, JavaScript, favicon, and data (or loads a single sibling `./data.js` in paired mode),
- uses [`tun_core.as_script_json()`](../../tools/tun_core.py) for all script-embedded JSON so untrusted cell text cannot break out of `<script>` or trigger SharePoint row-25 script stripping, and
- renders high-value static facts when scripting is blocked (the `html:not(.js)` canary pattern).

## Consequences

- **Positive:** Zero admin approval, zero viewer licences, offline reading, and predictable rendering across Windows, macOS, and mobile browsers.
- **Trade-offs:** Files are point-in-time snapshots (warn >20 MB, fail >50 MB), and recipients open a downloaded/synced file rather than an inline SharePoint web page.
- **When to revisit:** If [`probe/tenant-probe.py`](../../probe/tenant-probe.py) measures a change in tenant hosting headers, update [`docs/01-tenant-constraints.md`](../01-tenant-constraints.md) first and re-evaluate Tier 2/3 options.

## Enforcement

- [`tools/verify_standalone_core.py`](../../tools/verify_standalone_core.py) rejects external `http(s)` subresources, leftover placeholders, stray `<script` text, and files over 50 MB.
- [`tests/test_nojs_fallback.py`](../../tests/test_nojs_fallback.py) verifies readable content with `java_script_enabled=False`.
- [`tests/test_row_24_26_checks.py`](../../tests/test_row_24_26_checks.py) enforces SharePoint rows 24–26 statically across tracked files.
- [`tests/test_builder_escaping.py`](../../tests/test_builder_escaping.py) verifies `</script>` breakout protection in Chromium.
