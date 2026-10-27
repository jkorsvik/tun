# 20. The idea, written for a communications reader

One long page, not a deck: what Tún is, in the vocabulary of someone who writes for a living
rather than someone who ships data. The three questions a communications adviser actually
asks — who sees this, where does it live, what happens when someone disagrees with a number
— get an answer each, in their words.

It is **hand-written**, with no builder. That is deliberate and it is also the cost: this
file is the only place its structure exists, so a change here is a rewrite, not a rebuild.
Two of its sections were the seed of `skills/tun-for-communicators/`, which is where the
vocabulary now lives.

## Verify it

```bash
uv run --extra verify python tools/verify_standalone_core.py \
    examples/20-tun-for-kommunikasjon/tun-for-kommunikasjon.html
uv run --extra verify python tools/verify_viewports.py \
    examples/20-tun-for-kommunikasjon/tun-for-kommunikasjon.html
uv run --extra verify python tools/verify_a11y.py \
    examples/20-tun-for-kommunikasjon/tun-for-kommunikasjon.html
```

Nothing dynamic: no script, one file, so what a browser renders is what the file says.

2026-10-24: four labels in the prose were under the 14 px floor (the eyebrow, the gold step
label, the NOW/THEN banners, and the footer), which on a page of 17 px body text reads as
fine print rather than as words. They are at the floor now.
