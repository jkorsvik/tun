# 0004. One colour seam and zero-script system dark mode

- **Status:** Accepted
- **Date:** 2026-10-25
- **Related docs:** [`docs/10-chart-colour-palettes.md`](../10-chart-colour-palettes.md), [`docs/22-plugin-contract.md`](../22-plugin-contract.md), [`docs/35-visual-identity.md`](../35-visual-identity.md)

## Context

Templates originally carried 9–40 hand-written hex values each. When dark mode was added, several surfaces broke silently (1.00:1 KPI figures, 1.43:1 links, dark-on-dark `<select>` chevrons) because light-only roles were assumed.

## Decision

1. All shipped artefact templates consume one shared token seam in `tools/tokens/` via [`tun_tokens.load_token_css(auto_dark=True)`](../../tools/tun_tokens.py).
2. System dark mode is emitted as `@media screen and (prefers-color-scheme: dark)` scoped to `:root:not([data-theme])` — zero JavaScript required, while preserving explicit user theme choices and white-paper print output.
3. Exceptions (printable one-pager, projected slide decks, and the Explorer chrome) are explicitly enumerated with reasons in [`tests/test_dark_scheme_gate.py`](../../tests/test_dark_scheme_gate.py).
4. Public Tún pages (`tun.community`, Explorer) share the single visual identity defined in [`docs/35-visual-identity.md`](../35-visual-identity.md).

## Consequences

- **Positive:** Brand/palette plugins swap cleanly across all artefacts, and dark-mode contrast defects are caught mechanically before merge.
- **Trade-offs:** Any custom CSS surface (such as data-URI `<select>` chevrons or SVG chart strokes) must explicitly account for dark mode.
- **When to revisit:** If CSS light-dark() achieves universal support across all target offline WebViews and Quick Look engines.

## Enforcement

- [`tools/check_token_contrast.py`](../../tools/check_token_contrast.py) + [`tests/test_token_contrast.py`](../../tests/test_token_contrast.py) measure every declared token pair against WCAG 2.2 AA.
- [`tests/test_token_contract.py`](../../tests/test_token_contract.py) verifies plugin palettes supply all required token slots.
- [`tests/test_dark_scheme_gate.py`](../../tests/test_dark_scheme_gate.py) runs `verify_a11y.py --dark` against every required follower and rejects unaccounted templates.
