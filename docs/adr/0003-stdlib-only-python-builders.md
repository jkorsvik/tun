# 0003. Stdlib-only cross-platform Python builders

- **Status:** Accepted
- **Date:** 2026-10-24
- **Related docs:** [`docs/04-onboarding.md`](../04-onboarding.md), [`docs/05-toolchain.md`](../05-toolchain.md), [`docs/12-maintainability-conventions.md`](../12-maintainability-conventions.md)

## Context

The primary user works on Windows without a developer toolchain, virtualenv workflow, Node runtime, or admin rights to install packages. Earlier builders also grew separate CSV/number parsers that drifted silently (one parsed en-US `1,234.56` as `1.23456`, a 1000× error).

## Decision

1. Every builder in `tools/` uses **Python 3.9+ standard library only** — no `pip` install, no bundler, no shell scripts, and no symlink assumptions.
2. Shared table reading, locale-safe number parsing, `</script>`-safe JSON encoding, and exit-2 refusals live in one module: [`tools/tun_core.py`](../../tools/tun_core.py).
3. Shared clock pinning (`SOURCE_DATE_EPOCH`) lives in [`tools/build_stamp.py`](../../tools/build_stamp.py) and shared Tier 1 size limits live in [`tools/build_size.py`](../../tools/build_size.py).
4. External dependencies (Playwright for browser verification) are isolated to the optional `verify` extra managed with `uv`, never required to build an artefact.

## Consequences

- **Positive:** Cloning the repo plus `python3` (or `py -3` on Windows) is sufficient to build every artefact shape offline and reproducibly.
- **Trade-offs:** Complex data formats (`.xlsx`, `.parquet`) are converted to CSV/JSON upstream (`tun-data` skill) rather than parsed inside Tier 1 builders.
- **When to revisit:** Only if Python drops a required stdlib module or the target audience universally has a managed build environment.

## Enforcement

- [`tests/test_shared_core.py`](../../tests/test_shared_core.py) proves builders use `tun_core` and prevents duplicate local number parsers.
- [`tests/test_source_date_epoch.py`](../../tests/test_source_date_epoch.py) proves pinned builds are byte-identical across timezones.
- [`tests/test_onboarding.py`](../../tests/test_onboarding.py) verifies documented Windows and Unix commands use real flags and zero extra packages.
