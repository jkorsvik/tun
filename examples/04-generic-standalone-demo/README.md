# 04. The generic half, with no dashboard in it

`standalone_html_demo1.html` is a document with rows, columns and a table of contents that
knows nothing about dimensions, measures or charts. It exists to prove the split in
[`docs/08`](../../docs/08-generic-artifact-model.md) is real: the generic layer carries
provenance, a self-contained file and a page that works from `file://`, and a dashboard is
one specialisation of that, not the definition of it.

The three sections the page opens with are the argument, in the artefact itself: what this
file is, why three sections and not one, and what it deliberately is not.

## Rebuild it

```bash
python3 examples/04-generic-standalone-demo/build_standalone_demo.py
```

It takes no arguments and writes `standalone_html_demo1.html` beside itself, so the rebuilt
file lands where the committed one is.

## Verify it

```bash
uv run --extra verify python tools/verify_standalone_core.py \
    examples/04-generic-standalone-demo/standalone_html_demo1.html
uv run --extra verify python tools/verify_viewports.py \
    examples/04-generic-standalone-demo/standalone_html_demo1.html
uv run --extra verify python tools/verify_a11y.py \
    examples/04-generic-standalone-demo/standalone_html_demo1.html
```

2026-10-24: its three section buttons measured 35 px tall, under the 44 px touch floor, and
this file was the only record of it. The builder now sets `min-height` on the button itself
rather than relying on the bar's padding, which is the same fix the current templates use.
