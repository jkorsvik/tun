# 22 — The plugin contract

Status: contract proposal, derived from the one real case.

| capability | state |
|---|---|
| `tokens` | **implemented** in `tools/tun_tokens.py`: discovery, single-provider rule, slot validation, load order. Asserted by `tests/test_token_contract.py` (38 assertions). |
| `assets` | partial: the plugin holds its own artwork, but no code resolves an asset by name |
| `templates` | **specified, not built** |
| `verifiers` | **specified, not built** |
| `tenant_facts` | **specified, not built** |

Everything marked "not built" is a description of an intended shape, not a guarantee. An
earlier version of this document stated the slot validation as fact while no code performed
it, which is worse than omitting it: a contract is read as a guarantee, so the failure it
claimed to prevent stayed possible and nobody looked for it.

`docs/21-plugin-architecture.md` names the three tiers and argues why the Eksempel AS
material is a plugin rather than contamination. This document says what a plugin actually is.

## The rule the contract exists to serve

> Core must build, verify and ship a correct artefact with **no plugin installed**, and must
> never name an organisation.

Everything below follows from that. A capability that cannot be absent is not a plugin
capability; it is core.

## Derived from the real case, not invented

The Eksempel plugin is the only real consumer, so the contract is exactly what extracting it
requires. The token layering in this repository already pointed at the answer:

| File | Kind | Verdict |
|---|---|---|
| `plugins/eksempel/tokens/palette.css` (formerly under `tools/tokens/`) | raw palette, `--eksempel-*` | brand-specific, leaves core |
| `tools/tokens/theme-light.css`, `theme-dark.css` | semantic roles: `--ink`, `--bg`, `--brand` | core, but they referenced the raw palette |
| `tools/tokens/status-semantic.css` | `--status-*` | already brand-free, stays |

Measured: the theme files reference **eight** of the nineteen raw palette values. Eight is
therefore the size of the seam, not nineteen.

**Core defines semantic roles. A plugin supplies the palette those roles map onto.**

## Layout and manifest

```
plugins/<id>/
  manifest.json
  tokens/palette.css
  assets/<name>.svg
  templates/<name>.html      (optional override)
  verifiers/<name>.py        (optional)
  tenant-facts.json          (optional)
```

```json
{
  "schema": "tun.plugin/v1",
  "id": "eksempel",
  "title": "Eksempel AS brand",
  "version": "0.1.0",
  "requires_tun": ">=0.1",
  "private": true,
  "license": "Internal",
  "provides": ["tokens", "assets"]
}
```

`private: true` means never publish, and is the machine-readable form of the third tier. It is
advisory to humans and load-bearing for tooling: a packaging step refuses to include a private
plugin.

## Discovery and load order

Discovery is `plugins/*/manifest.json`, sorted by `id` for determinism. Any number of
installed plugins may declare `"provides": ["tokens"]` at once — coexistence is fine,
and `tests/test_token_contract.py` runs with two (`eksempel`, `tun`) in this tree. The rule
is about the *automatic* pick: exactly one plugin may be resolved by `prefer_plugin=True`
with no explicit palette named, and more than one candidate there is an error rather than
a silent last-wins, because a last-wins palette is impossible to debug from a built
artefact. `TUN_PALETTE` sidesteps the question entirely by naming one file, so it works
unambiguously no matter how many plugins provide tokens. A manifest that is not readable
JSON is also an error, not a skip: a silently skipped plugin is installed as far as the
user is concerned and absent as far as the build is concerned.

**An installed plugin does not win by default**, which reads backwards for a plugin system
and is deliberate. This repository *contains* the brand plugin, so installed-wins would
make every core example rebuild branded, writing brand values back into core files and
regressing the boundary ratchet on the next commit: the build would undo the extraction.
Core artefacts therefore pin the neutral palette, and anything wanting the brand asks for
it (`prefer_plugin=True`, or `TUN_PALETTE`). `TUN_PALETTE` is validated like any other
palette, so a typo fails the build instead of quietly falling back to neutral and producing
a plausible artefact in the wrong colours.

Token load order, which matters because later files reference earlier ones:

1. the palette: the plugin's `tokens/palette.css`, or core's `tools/tokens/palette-neutral.css`
   when no plugin provides one
2. `tools/tokens/status-semantic.css`
3. `tools/tokens/theme-light.css`, then `theme-dark.css`

Everything is inlined at build time. Nothing is fetched by the shipped artefact, ever; that is
design principle 1 in `docs/00-vision.md` and it is not negotiable by a plugin.

## The five capabilities

### 1. `tokens`

A CSS file defining the eight required palette slots. Validated by
`tun_tokens.validate_palette()`: a palette omitting one fails the build rather than producing
an artefact with an unresolved `var()`, which CSS renders as *nothing* — an invisible or
wrong colour that would pass every other gate in this repository.

The eight are a measured seam, not a design: they are exactly the palette values core's
theme files consume, out of the nineteen the brand defines. `tests/test_token_contract.py`
asserts that this list, the two shipped palettes, and the `var(--palette-*)` references in
`theme-light.css` and `theme-dark.css` all agree, so the seam cannot drift from the code.

```
--palette-ink              body text
--palette-surface          page background
--palette-primary          primary data colour, links, focus
--palette-primary-dark     header background
--palette-primary-darkest  darkest surface
--palette-accent           secondary series, decorative only
--palette-accent-light     highlight on dark
--palette-on-dark          text on a dark surface
```

### 2. `assets`

Files inlined at build time and referenced by name. Core holds no copy. This is what lets logo
artwork live entirely inside a private plugin, which is the specific thing that currently makes
two examples unpublishable.

### 3. `templates`

Override or extend a core template by name. A plugin-branded topbar becomes a plugin concern;
core keeps the topbar *pattern* with a neutral wordmark, because the pattern is the reusable
part and the mark is not.

### 4. `verifiers`

Additional check modules, discovered and run by `tools/check_tree.py` alongside the core gates.
An organisation can then assert its own rules, for example that its logo never appears on a
disallowed background. Plugin verifiers may add failures; they may not remove core ones.

### 5. `tenant_facts`

`docs/01-tenant-constraints.md` mixes two kinds of statement: how Microsoft 365 behaves, which
is core knowledge, and how one tenant is configured, which is not. Tenant facts are structured
data supplied by a plugin, so the distinction stops depending on how a row was worded.

## The two questions `docs/21` left open

**May a plugin add skills? Yes.** The sketch labels core "skills" and ".MD"; if skills were
core-only, a plugin could not extend the thing the product actually is.

**Are substrate adapters plugins or core? Core.** In the sketch the sun's rays fall across GCP,
SharePoint, Cloudflare, Vercel, Firebase, OneDrive, AWS and Azure equally. Substrate
independence is a promise core makes, so the adapters that keep that promise cannot be optional
extras. A plugin may add a *new* substrate; it may not change how an existing one behaves.

## Invariants a gate can check

1. Core does not reference any specific plugin by id.
2. A plugin does not modify files under core paths.
3. With `plugins/` empty, every build succeeds and every gate passes.
4. Core contains no organisation name, design-system name, internal host or person name.

Invariant 4 is the hardest to satisfy in a toolkit grown inside one organisation, so it
ships as an exact-set debt list that may only shrink, in the manner `tools/tree_scan.py`
already uses for row 25. A ratchet converts a large rewrite into reviewable increments; a
big-bang edit of the same scope is unreviewable and would be merged without being read.
