# 05. Three navigation decisions, on a throwaway page

A KPI page that exists to answer one question: where does "dark mode" live? Three answers,
in the page, on top of the same three numbers. A theme toggle in the header, a persisted
choice, and `aria-pressed` telling a screen reader which state it is in.

It is a demo, not a template. The decisions it argues about are written down in
[`docs/09`](../../docs/09-usability-and-navigation-principles.md); the artefact is how they were settled,
and the real templates carry the conclusion.

## Rebuild it

```bash
python3 examples/05-theme-toggle-demo/build_theme_toggle_demo.py
```

No arguments: it writes `theme-toggle-demo.html` beside itself. `preview.png` beside it is
the saved look of the page, refreshed by hand, not by the builder.

## Verify it

```bash
uv run --extra verify python tools/verify_standalone_core.py examples/05-theme-toggle-demo/theme-toggle-demo.html
uv run --extra verify python tools/verify_viewports.py examples/05-theme-toggle-demo/theme-toggle-demo.html
uv run --extra verify python tools/verify_a11y.py examples/05-theme-toggle-demo/theme-toggle-demo.html
```

The theme toggle is the one thing no static check covers: press it, then read the small grey
text on the dark surface. Contrast is where a palette switch breaks, and it breaks quietly.

2026-10-24: this page sat outside the documented loop until its README existed, and by then
its KPI label had drifted to 12 px and two buttons to 35 px, both under the floor. The
builder sets `.875rem` and `min-height:2.75rem` now, and `preview.png` was refreshed after
the fix.
