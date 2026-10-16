# 23: A process diagram, Tún drawing its own workflow

`tun-workflow.html` is a swimlane process diagram of how a Tún dashboard comes to exist:
the request, modelling the data, approval for the audience, the build, `tun-verify`,
publishing, and the feedback that sends it round again. Two steps are flagged as places
to improve.

It is built by `tools/build_process_diagram.py` from `tun-workflow.process.txt`. Nobody
writes the HTML by hand. `tests/test_process_diagram.py` rebuilds it and fails if the
committed file differs from what the builder makes (apart from the build time).

![The flow tab in Chromium](preview.png)

## What it shows about the format

- Three lanes (who does it), eleven numbered steps, thirteen connections, in Tún's own
  palette (`palette: plugins/tun/tokens/palette.css` in the spec).
- Three decisions. Each outcome sits in a pill beside its arrow: `ja`, `nei`,
  `nei, del opp`.
- Three dashed loops back: a refused approval goes back to describing the request, a
  failed verify goes back to the build, and "something must change" goes back to
  modelling. Each leaves its box on the right and climbs its lane's own gutter.
- One crossing in the whole drawing, pinned as a ceiling in the test. Before loops got
  their own gutters there were six.
- Two improvement points: a tinted box with a numbered badge, and a card with the
  problem and the proposal.
- Every step has a card. Each says what happens, and most also give input, output and
  tool, as far as the skills say them. Two have a duration, and those two were measured (`tools/build_dashboard.py` and `tools/verify_dashboard.py`
  on examples/01, 776 rows). The skills state no durations, so the other steps have
  none.

## Two layers

With JavaScript off, five sections show one after the other: the flow, the step cards,
the roles with their hand-offs, the improvement points, and a text version. That is also
what print shows.

With JavaScript on, the same sections become tabs («Flyt», «Steg», «Roller»,
«Forbedringspunkter», «Tekstversjon»). Click a step, or give it Enter, to open its card
beside the drawing. Hover or focus a step to light its connections. A role chip keeps
one lane. «Vis i flyten» on a card jumps to the step. Zoom and fit-to-width sit above
the drawing. No URL fragment, no network, works from `file://`.

## Any window width

The drawing fills its frame. On a wide screen it grows up to 1.5 times its natural size,
and it never shrinks below the size where its smallest text is 12 px (the builder draws no text smaller than
14 units, so the floor is 12/14 of natural size). This is plain CSS, so it holds with
JavaScript off too. Below the floor the frame scrolls. With JavaScript on, it then stops
at the window height, so both scrollbars are in reach, and the lane names stay over the
top of the frame while it scrolls. The page has no width cap, so the frame spans the
window; the text keeps a readable line length. A step's detail panel opens over the drawing beside the
step, so it never narrows the drawing. On a phone the page starts on «Steg».

The file carries the flow twice: lanes as columns with the flow running down, and lanes
as rows with the flow running right. «Auto» shows, of the two that fit the window without
panning, the one that needs the least scrolling down. A wide, short screen gets rows and
a tall or narrow one gets columns, and it changes as the window does. «Loddrett» and
«Vannrett» choose one. Both drawings number the steps the same, so «Steg» and
«Tekstversjon» keep the plan's order. Without JavaScript, and on paper, it is columns.
Rows start at a size that fits the window's height too, so every lane is in view as the
page opens; where that would take text under 12 px, «Auto» keeps the columns. A rows box
is as wide as a 3440x1440 window allows at 12 px, and each lane only as tall as its own
labels need. A label breaks at a space or after a "/" or "-" it already has, never inside
a word; a word longer than a line makes the boxes wider.

`fem-roller.process.txt` is a second, synthetic spec in the shape that showed the need:
five roles, seventeen steps, loops back and two-way decisions. Its drawing pans at
1084 px, fits at 1440 px and grows past 1:1 from about 1620 px. The verifier sweeps
both files across eight windows, up to 3440x1440 and 3840x1080, where fem-roller shows
as rows.

## Rebuild

```bash
python3 tools/build_process_diagram.py \
  examples/23-process-diagram/tun-workflow.process.txt \
  --out examples/23-process-diagram/tun-workflow.html
python3 tools/build_process_diagram.py \
  examples/23-process-diagram/fem-roller.process.txt \
  --out examples/23-process-diagram/fem-roller.html
```

`source:`, `requested-by:` and `palette:` live in the spec, so a rebuild cannot lose them.

## Verify

```bash
uv run --extra verify python tools/verify_process_diagram.py \
  examples/23-process-diagram/tun-workflow.html \
  --spec examples/23-process-diagram/tun-workflow.process.txt --max-crossings 1
```

```bash
uv run --extra verify python tools/verify_process_diagram.py \
  examples/23-process-diagram/fem-roller.html \
  --spec examples/23-process-diagram/fem-roller.process.txt --max-crossings 3
```

It opens the file from `file://` in Chromium, Firefox and WebKit. It checks the drawing
against the spec, and drives the page like a reader: tabs by keyboard, every panel's
content, detail panel, highlight, role filter, zoom, «Vis i flyten», print, and no text
under 12 px. It does it again in seven windows from 375x812 to 3440x1440: no sideways
page scroll, a frame that spans the window, the drawing at the width it gives (up to
1.5x), no text under 12 px,
every lane in view where it fits, and panning with the lane names in view where it does
not. Then it opens the file with JavaScript off. It writes
`<file>.<engine>.verify.png`, and `<file>.<engine>.<w>x<h>.verify.png` per window, beside
the file (gitignored). Look at them.

`--mutation-check` breaks copies of the file in thirty ways, in a temp directory,
one per behaviour, and requires each break to be caught by the check aimed at it. Run it
on `fem-roller.html`: the three-lane file fits at every laptop width, so a broken pan
cannot show on it.

Firefox inside a sandboxed agent session may fail to start its own content sandbox
(`sandbox_init() failed`). Setting `MOZ_DISABLE_CONTENT_SANDBOX=1` for that run fixes it.
A normal desktop session does not need it.

## Files

- `tun-workflow.process.txt`: the spec, the only file a person edits
- `tun-workflow.html`: the built diagram
- `fem-roller.process.txt`, `fem-roller.html`: the synthetic five-lane spec and its diagram
- `preview.png`: the Chromium screenshot from the verifier
