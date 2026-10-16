---
name: tun-process
description: "Draw a process as a swimlane diagram in one self-contained HTML file: who does what, in which order, where it branches, and where it goes wrong. Use when someone wants a process diagram, flowchart, swimlane or workflow drawn, wants to map how work really flows between people or teams, or wants to show where a process should improve."
---

# Draw a process diagram

You are producing a **Tier 1 portable artefact**: one `.html` file, no server, no network.
It opens from SharePoint, OneDrive, an attachment or a USB stick. See
`docs/08-generic-artifact-model.md`, section "Process diagrams".

The file has two layers. The floor is a static drawing plus plain HTML: with JavaScript
off, five sections show one after the other (the flow, a card per step, the roles, the
improvement points, a text version). On top, a small script turns them into five tabs
(«Flyt», «Steg», «Roller», «Forbedringspunkter», «Tekstversjon»), opens a detail panel
when a step is clicked, highlights a step's connections, filters by role, and zooms.

Say this up front, in one line:

> "This will be one file with the process drawn as lanes, a card for every step, and the
> improvement points listed. No licence, no approvals, nothing to install."

## Step 1: Who will see it

Ask: **"Who is this for, and is anything in the process sensitive?"**

A process diagram holds no data rows, but it can still name people, systems or weak
spots. The rule from rule 1 applies: everything in the file is readable by everyone who
can open the folder. Use **roles** in lane names ("Saksbehandler", "Kreditt"), never
people's names. If two audiences may see different detail, build two files and put each
in its own folder.

Done when you know the audience and the lanes will hold roles only.

## Step 2: The interview

Ask in this order, one question at a time, in the user's words. Repeat back what you
heard as a short list before moving on.

1. **Who takes part?** Each role, team or system becomes a **lane**. Three to six is
   typical. More than eight is two diagrams.
2. **Where does it start, and what counts as finished?** One `start`, one or more `end`.
3. **What happens, in order?** Walk it from the start. For each step: who does it (which
   lane) and what they do, as a verb phrase ("Registrerer saken"). Keep a label under
   about 60 characters.
4. **Where does it branch?** Every yes/no or either/or point is a `decision`. Ask what
   each answer is called and where each leads. Loops back are normal: "nei" goes back to
   an earlier step.
5. **Where does it go wrong?** Ask: "Where does it stall, get redone, or depend on one
   person?" Each answer becomes an `improve:` line on that step, with the reason in one
   sentence. Then ask what exactly goes wrong (`problem:`) and what should change
   (`forslag:`). These are the point of the diagram for most readers.
6. **What does each step need and give?** For each step, as far as the user knows: what
   happens (`beskrivelse:`), what it needs (`input:`), what it hands on (`output:`), the
   tool (`verktøy:`), and how long it typically takes (`varighet:`). These fill the step
   cards. Write only what the user says or what you measured. Leave a field out rather
   than guess, and never invent a duration.

Done when every step has a lane, every decision has a labelled outcome for each answer,
every step leads somewhere, and the user has confirmed the list.

## Step 3: Write the spec

Write a `.process.txt` file. The full format is at the top of
`tools/build_process_diagram.py`. A small one:

```
title: Slik behandles en søknad
source: Intervju med saksbehandlerne, mars
requested-by: Seksjonsleder

lane Kunde
  start send: Sender søknad
  end svar: Får svar
lane Saksbehandler
  step reg: Registrerer saken
    beskrivelse: Legger søknaden inn i saksbehandlingssystemet
    input: Søknad med vedlegg
    output: Et saksnummer
    verktøy: Saksbehandlingssystemet
  decision ok: Komplett?
  step vedtak: Skriver vedtak
    improve: Fem varianter av vedtaksmalen sier det samme
      problem: Saksbehandlerne velger mal på følelse, og svarene blir ulike
      forslag: Slå malene sammen til én

flow
  send -> reg -> ok
  ok -> vedtak [ja]
  ok -> reg [nei]
  vedtak -> svar
```

- `title:`, `source:` and `requested-by:` are required. They go into the provenance block
  and the footer. `source:` says where the process came from: an interview, a procedure
  document, a workshop.
- `<kind> <id>: <label>` with kind `start`, `step`, `decision` or `end`. The id is short,
  letters, digits, `-` and `_`.
- `improve: <why>` goes on the line under a step or decision. `problem:` and `forslag:`
  go under it.
- Optional step fields, any subset, under the step: `beskrivelse:`, `input:`, `output:`,
  `verktøy:` (or `verktoy:`), `varighet:`. At most 300 characters each.
- Optional header `palette:` picks a token palette, for example
  `palette: plugins/tun/tokens/palette.css` for Tún's own colours. Without it the file
  uses core's neutral palette.
- After `flow`, one connection per line. `a -> b -> c` is a chain. `[label]` names a
  decision's answer and goes on a single arrow.

Write it in the user's working folder, for example `work/<task>/` (gitignored), never in
`examples/` unless it is a synthetic example for this repo.

Done when `python3 tools/build_process_diagram.py <spec> --check` prints `ok`.

## Step 4: Build

```bash
python3 tools/build_process_diagram.py <spec>.process.txt --out <folder>/<slug>.html
```

The builder lays the drawing out itself: lanes as columns, the flow running downwards,
lines at right angles with rounded bends, each on its own track. A connection back to an
earlier step is a dashed loop that leaves the box's right side and climbs its lane's own
gutter, so it stays out of the middle. The router picks routes with the fewest crossings,
then the shortest. The build summary prints the crossing count. Same spec, same file.

If it stops with an error, the message names the line and the rule. Fix the spec, not
the HTML. Two layout errors have a fix in the spec: outcome labels "too long to sit side
by side" (shorten them) and "could not route every connection" (reorder the `flow`
lines, or split a step with many connections).

## Step 5: Verify (mandatory)

```bash
uv run --extra verify python tools/verify_process_diagram.py <slug>.html --spec <spec>.process.txt
```

It must print `✓ PASS`. In Chromium, Firefox and WebKit it checks the drawing against the
spec (steps, connections, loops, numbers, flags, no overlap, no clipping, no line through
a box or along another, every branch label on a clear pill, no text under 12 px). It also
drives the page like a reader: the tabs by keyboard, every panel with its content, a
click and Enter on a step open the right detail, «Vis i flyten» lands on the right step,
highlight, role filter and zoom work, and print shows every panel. In seven windows
(375 px to a 3440 px ultrawide) it checks that the drawing fits where it can, pans with the lane names
in view where it cannot, and never shows text under 12 px. Then it opens the file with
JavaScript off and checks that all five sections are there. Add
`--max-crossings <n>` with the count from the build summary to make it a ceiling.

Then **look at `<slug>.chromium.verify.png`** and show it inline. Check that the order
reads the way the user described it, and that the flagged steps are the right ones. A
diagram can pass every check and still be the wrong process.

Done when the verifier prints `✓ PASS` and you have looked at the screenshot.

## Step 6: Hand over

Tell them:

1. **Where the file is**, and that it is one file.
2. **How to change it**: edit the `.process.txt` and rebuild. Never edit the HTML.
3. **How to share it**: `tun-publish`, or drop it in a SharePoint or OneDrive folder.

## Limits, said plainly

- It is a swimlane flowchart, not BPMN. No timers, messages, pools, parallel gateways or
  sub-processes. A step that waits is a step called "Venter på ...".
- One step per lane per layer. A long chain makes a tall drawing. It scrolls on screen,
  and on paper it shrinks to one page: an 11-layer flow prints at about 5 pt. The cards
  and the text version follow at a readable size, each section on a new page.
- Many lanes make it wide. The drawing shrinks to fit the window, but only down to the
  size where its smallest text is 12 px. On a wide screen it grows, up to 1.5 times, and on
  a wide, short screen it turns: lanes become rows and the flow runs left to right. The
  reader can choose with «Loddrett» and «Vannrett». Print is always columns.
- Labels break between words, and after a "/" or "-" they already have. A single word
  longer than a line makes every box wider, so keep file names and codes short in labels. Five lanes fit a 1440 px window. On a smaller
  laptop the frame scrolls sideways, with the lane names kept in view. «Tilpass til
  bredden» shows the whole width at a smaller size. On a phone the page opens on «Steg».
- Loops back leave a box's right side. They enter the target's right side, or its left
  side when the target's lane is the next one to the right. A loop never leaves a left
  side, so a loop to a lane further left takes the long way over the top.
- Steps sit in a fixed column per lane, so the router can only reorder the lines along a
  box, not the boxes in a layer. Some crossings are structural: a loop that climbs past
  hand-offs between two lanes must cross them.
- Text wraps by an estimated character width. The verifier measures the real rendering,
  which is why step 5 is not optional.
- Chrome and labels are Norwegian, like the other templates.
