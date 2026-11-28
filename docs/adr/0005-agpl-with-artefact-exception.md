# 0005. AGPL-3.0-or-later with the Tún Artefact Exception v1.1

- **Status:** Accepted
- **Date:** 2026-10-10
- **Related docs:** [`docs/17-licensing.md`](../17-licensing.md), [`LICENSE`](../../LICENSE), [`COPYING.ARTEFACT-EXCEPTION`](../../COPYING.ARTEFACT-EXCEPTION), [`TRADEMARK.md`](../../TRADEMARK.md)

## Context

Tún copies its own HTML, CSS, and JavaScript runtime into every generated artefact. Under plain AGPL-3.0, every generated report or dashboard could be argued to be a covered work, blocking commercial and internal sharing. At the same time, hosted forks modifying the toolkit itself should contribute improvements back.

## Decision

1. License the Tún toolkit and Artefact Runtime under **GNU AGPL v3 or later**.
2. Grant the **Tún Artefact Exception v1.1** (an AGPLv3 section 7 additional permission) so users may convey generated artefacts and their embedded data under any terms, commercial or private, provided two narrow conditions hold:
   - the generated artefact is not itself a competing document generator, and
   - the provenance **Origin Notice** remains in the file source (visible branding is optional and removable via `--no-tun-hint`).
3. License documentation and examples under CC BY-SA 4.0, and keep the `Tún` name and mark governed separately by [`TRADEMARK.md`](../../TRADEMARK.md).

## Consequences

- **Positive:** Users can freely share generated reports with clients or employers without copyleft obligations on outputs, while hosted toolkit forks remain open.
- **Trade-offs:** Third-party code vendored into the runtime must be licence-compatible (e.g., MPL-2.0 `axe-core` is intentionally not vendored without an explicit owner decision).
- **When to revisit:** Only by formal decision of the copyright holders before a major licence version change.

## Enforcement

- [`tests/test_licence_headers.py`](../../tests/test_licence_headers.py) checks SPDX and copyright headers across source files.
- [`tests/test_origin_notice.py`](../../tests/test_origin_notice.py) ensures every builder emits the Origin Notice in generated artefacts.
