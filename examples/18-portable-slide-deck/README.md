# 18: Portable slide deck

A real single-file presentation adapted after a Slack and iPhone delivery test exposed two
separate problems:

1. Slack's iOS attachment preview showed the HTML source instead of running the page.
2. Once the file opened in an iOS browser, the original hover-only controls were too faint
   and there was no visible fullscreen action.

The presentation is included as a real artefact because a small synthetic sample would not
exercise the dense slide layouts, staggered tiles, counters, section rail, portrait reflow,
and dark/light control contrast together.

The committed copy is the delivered deck with the organisation's name removed from the cover
eyebrow and from three CSS comments, because core must stay generic (see `docs/21`). Only the
author credit remains, inside a declared `attribution:` region. The layout, the data and the
measurements are untouched. The preview images below are regenerated from this copy, in
WebKit, so the pictures cannot disagree with the file: a text gate cannot read pixels.

![Landscape mobile render](preview-landscape.png)
![Portrait mobile render](preview-portrait.png)

## What this proves

`maalebandet.html` is one 38 KB file with no remote dependencies. It opens from `file://`
and needs no server after download. The same file can also be hosted unchanged when a URL is
the easier delivery route.

The shell provides:

- persistent Previous, Next, slide count, and Fullscreen controls;
- 48 px touch targets;
- keyboard, button, and swipe navigation;
- portrait and landscape layouts;
- `100dvh` with a `100vh` fallback;
- safe-area handling for mobile browser chrome;
- standard and WebKit fullscreen paths;
- a visible fallback message when fullscreen is unavailable;
- a useful first slide and platform-neutral warning when JavaScript does not run.

The final point matters for attachment viewers such as Apple Quick Look. A host may refuse to
execute JavaScript even though the exact same bytes work in a browser. The artefact cannot
override that security boundary. It can avoid looking blank and tell the reader what to do.

## Manual finding

Measured on 20 September 2026:

- Slack on macOS opened the attachment as an interactive page.
- Slack on iPhone displayed source text in its attachment preview.
- The iOS "open in browser" handoff offered Yandex on the tested phone.
- Yandex rendered the local file in portrait and landscape.

This is a transport result, not a claim that every iPhone browser or Slack version behaves the
same way. `docs/01-tenant-constraints.md` records it as a manual observation.

## Reproduce

Structural tests need only Python:

```bash
python3 tests/test_portable_slide_deck.py
```

Run Tún's generic checks:

```bash
python3 tools/verify_standalone_core.py examples/18-portable-slide-deck/maalebandet.html
# This deck is a measurement band: its own card labels are 9 px at design size,
# by design, so it declares that floor. Overflow and touch targets are still
# checked at every viewport, and the prose on the slides is 14 px.
python3 tools/verify_viewports.py examples/18-portable-slide-deck/maalebandet.html --text-floor 9
python3 tools/verify_nojs_fallback.py examples/18-portable-slide-deck/maalebandet.html
```

Run the slide-specific Chromium and WebKit matrix:

```bash
uv run --extra verify python tools/verify_slide_deck.py \
  examples/18-portable-slide-deck/maalebandet.html \
  --out /tmp/maalebandet-verification
```

The last command visits all 15 slides at 1600×900, 1366×768, 844×390, and 390×844
in both engines (add `--engines all` for Firefox as well; CI runs all three). It checks controls, navigation, animation endpoints, JavaScript errors,
external requests, and fullscreen or its fallback. It writes one screenshot per slide and
a contact sheet per engine and viewport for human review.

## Reuse

Start from `templates/portable-slide-deck.html`: `python3 tools/build_slide_deck.py --out deck.html`
writes it in Norwegian, and `--lang en` writes it in English. Replace the three sample slides,
keep the shell and controls, then run all four checks above against the built file.

This example belongs in Tún because Tún owns the portable artefact format. The optional
`tun.community` service is one hosting adapter for Tún output. Its testserver deployment lives
in the infrastructure repository; no copy of this template belongs there.
