# 0006. Servers, live APIs and shared writes stay outside the toolkit core

- **Status:** Accepted
- **Date:** 2026-11-01
- **Related docs:** [`docs/08-generic-artifact-model.md`](../08-generic-artifact-model.md), [`docs/23-hosted-route-it-brief.md`](../23-hosted-route-it-brief.md), [`docs/36-hosting-and-functional-apps.md`](../36-hosting-and-functional-apps.md)

## Context

Some teams ask for live databases, multi-user form writes, server-enforced sign-in, or scheduled background jobs. Folding a web server, database layer, or auth framework into Tún's core would break its zero-dependency, file-first premise and impose permanent security/operations overhead on every simple report.

## Decision

1. No server, backend framework, database, or job runner enters the Tún toolkit core.
2. Read-only snapshots and static interactive views remain Tier 1 self-contained files (which may also be deployed on static HTTPS hosts).
3. When shared writes, server-enforced authorisation, or live APIs are genuinely needed, build a separate small application outside the toolkit core, routed through [`skills/tun-host/SKILL.md`](../../skills/tun-host/SKILL.md), and pair it with a static snapshot export (demonstrated in [`examples/56-functional-app/`](../../examples/56-functional-app/)).

## Consequences

- **Positive:** Tier 1 stays dependency-free and low-governance, while teams with genuine server needs get an honest exit and a hybrid snapshot-export pattern.
- **Trade-offs:** Tún does not provide turnkey multi-user state or turnkey hosting adapters.
- **When to revisit:** If a narrow, zero-dependency publish adapter contract is measured and proven across multiple hosts (noted as direction in [`docs/index.md`](../index.md)).

## Enforcement

- [`tests/test_skill_routes.py`](../../tests/test_skill_routes.py) asserts that `tun-help` and `tun-publish` route hosted/backend requests to `tun-host` and that `docs/36-hosting-and-functional-apps.md` preserves the no-server-in-core boundary.
- [`tests/test_functional_app.py`](../../tests/test_functional_app.py) verifies the reference hybrid app and its script-free snapshot export.
