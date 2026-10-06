# `plugins/eksempel` — the example third-party plugin

This is the third tier from `docs/21-plugin-architecture.md`: organisation-specific, not part
of core.

**Eksempel AS is a fictional organisation.** Its palette, wordmark and icons were invented for
this plugin, so the tier can be demonstrated with a real-looking brand and no real
organisation's identity. A real organisation copies this layout, puts in its own brand, and
keeps `private: true`.

Brand material is a legitimate thing to have; it simply is not core's, and the tier model is
where it belongs.

## What is in here, and why it cannot be in core

| Path | Why |
|---|---|
| `tokens/palette.css` | brand colours. For a real brand these come from its brandbook |
| `examples/logo-poc/` | the wordmark `<path>` data. For a real brand this is trademark artwork |
| `examples/branded-topbar/` | the same artwork, baked into its built HTML |

`private: true` in `manifest.json` is the machine-readable form of "never publish". A packaging
step must refuse to include a plugin carrying it. It is set here to demonstrate the flag.

## What stayed in core, deliberately

The *patterns* are the reusable contribution and they are not brand-specific:

- `examples/07-topbar-pattern-demo` keeps the topbar pattern with a neutral wordmark. The
  pattern is reusable; the mark is not.
- `tools/tokens/theme-light.css` and `theme-dark.css` keep the semantic roles (`--ink`, `--bg`,
  `--brand`). They used to reference the brand palette directly, which is what put brand names
  inside core; they now reference neutral slots.
- `tools/tokens/palette-neutral.css` is core's default palette, so a build with `plugins/`
  empty still produces a coherent artefact instead of one full of unresolved `var()`.

## The seam, measured

Core's theme files need **eight** of the nineteen brand values. Eight is therefore the
size of the contract, and `tokens/palette.css` ends with the block that maps the brand onto
those eight slots.

## Using it

```
# core default, no plugin:
python3 examples/05-theme-toggle-demo/build_theme_toggle_demo.py

# with this plugin's palette:
TUN_PALETTE=plugins/eksempel/tokens/palette.css \
  python3 examples/05-theme-toggle-demo/build_theme_toggle_demo.py
```

`TUN_PALETTE` is the current, deliberately minimal mechanism. `docs/22-plugin-contract.md`
specifies proper discovery through `plugins/*/manifest.json`; that is not built yet, and this
environment variable is honest about being a stopgap rather than pretending to be the contract.

## What is still wrong here

Being honest about the state rather than implying completion:

- Several core examples (`01`, `02`, `03`, `04`, `06`, `10`, `13`) still hardcode brand hex
  values in their built output. They are pattern demos that happen to be brand-coloured. They
  are tracked as debt by the core-is-generic gate and the list may only shrink.
