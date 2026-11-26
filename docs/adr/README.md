# Architecture Decision Records (ADRs)

Short, durable records of the architectural decisions that shape Tún and the automated gates that enforce them.

Deep empirical write-ups live in the numbered documents under [`docs/`](../index.md). An ADR is the one-page summary you read *before* changing a boundary, adding a tier, or questioning why a constraint exists.

## Index

| ADR | Decision | Status | Primary gate |
|---|---|---|---|
| [0001](0001-folder-is-the-security-boundary.md) | The folder is the security boundary, never a browser filter | Accepted | `tests/test_audience_split.py` |
| [0002](0002-download-is-the-delivery-mechanism.md) | The download is the delivery mechanism (self-contained HTML, no remote assets) | Accepted | `tools/verify_standalone_core.py`, `tests/test_nojs_fallback.py`, `tests/test_row_24_26_checks.py` |
| [0003](0003-stdlib-only-python-builders.md) | Stdlib-only cross-platform Python builders with a single shared core | Accepted | `tests/test_shared_core.py`, `tests/test_onboarding.py` |
| [0004](0004-shared-colour-seam-and-auto-dark.md) | One token seam and zero-script system dark mode with a measured contrast ratchet | Accepted | `tools/check_token_contrast.py`, `tests/test_token_contract.py`, `tests/test_dark_scheme_gate.py` |
| [0005](0005-agpl-with-artefact-exception.md) | AGPL-3.0-or-later for the toolkit with the Tún Artefact Exception v1.1 for outputs | Accepted | `tests/test_licence_headers.py`, `tests/test_origin_notice.py` |
| [0006](0006-hosted-boundary-outside-toolkit-core.md) | Servers, live APIs and shared writes live outside the toolkit core | Accepted | `tests/test_skill_routes.py`, `tests/test_functional_app.py` |

## When to write a new ADR

Write an ADR in the same pull request whenever a change:

- alters a non-negotiable rule in [`AGENTS.md`](../../AGENTS.md),
- introduces or changes a shared core contract (`tools/tun_core.py`, `tools/tun_tokens.py`, `tools/tun_brand.py`, paired `data.js`),
- adds a delivery tier, runtime dependency, or licence boundary, or
- supersedes an existing ADR (mark the old record `Superseded by NNNN` rather than deleting it).

Copy [`0000-template.md`](0000-template.md) to `NNNN-short-kebab-title.md`, add a row to the table above, and run `python3 tests/test_adrs.py`.
