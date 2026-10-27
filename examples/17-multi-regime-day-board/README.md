# 17 — A day board for an organisation that runs three régimes with three owners

A pupil-transport day overview for **Eksempelskolen** in **Eksempelkommune**, both
fictional, built as a Tier 1 **paired** artefact: `oversikt.html` plus a sibling `data.js`.

The example exists to answer a harder question than "can we draw a table". The
organisation runs **three transport régimes with three different owners**, and an
overview that flattens them into one list is wrong no matter how good it looks. That,
plus the fact that the file is a *view* while the real editor lives elsewhere, is what is
being demonstrated.

It is also the repository's only example whose subject is **not** a tenant of the
platform this repository serves. That turns out to matter, and it is why §5 exists.

## All data is synthetic, and the build proves it

Every `ElevKode` is of the form `ELEV-nn`; every clock time, car id, status and role
label is invented. There is no real pupil, no real initials and no real driving plan
anywhere in this folder.

The mechanism is worth more than the promise. Each column has an **allow-list** in
`VOCABULARY`, and every generated value must match it, so free text — and therefore a
name — cannot enter the data at all. `verify_day_board.py` restates the allow-list
independently against the written file, because a generator that checks only its own
vocabulary proves nothing about what it actually wrote.

An allow-list is the point. A deny-list of forbidden names only ever excludes the names
somebody thought of; an allow-list of `ELEV-\d\d` excludes every identifier there is,
including the ones nobody anticipated.

### Why two hand-typed copies were not enough

The first version of this example stopped there, and the reasoning had a hole that an
adversarial review found. Two independent copies of a vocabulary fail loudly in **one**
direction only:

| Drift | What happens |
|---|---|
| The verifier's copy is **stricter** than the builder's | immediate, obvious failure |
| The verifier's copy is **looser** | nothing notices |

The limit case is `re.compile(r".*")`. Loosen one pattern to that, and the verifier still
reports *"all 57 distinct data values come from the synthetic vocabulary"* — a claim that
is satisfiable without the property holding, which is worse than no check at all, because
it manufactures assurance.

Two guards close it, and neither depends on the patterns being right:

1. **`EXPECTED_VALUES` asserts the exact value set** per closed-vocabulary column: 7
   columns, 44 values. A set cannot be widened by editing a regex, so the guarantee now
   rests here instead. `Dato` and `Planlagt` are deliberately excluded — they are open
   ranges by nature, and pinning them would pin the dataset rather than the contract.
2. **Every pattern is shown a name-shaped canary** (`Ola Nordmann`, `O. Nordmann`, an
   email, an 11-digit number). An allow-list that accepts one of those is not an
   allow-list, whatever else it matches. That is 9 columns × 4 canaries, and it states the
   actual threat rather than a proxy for it.

Verified by mutation, not by argument:

| Mutation | Result |
|---|---|
| Inject `Ola Nordmann` into `data.js` | caught twice — pattern check and set check |
| Loosen a pattern to `.*` | caught by the canary check |
| Both at once (the case that used to pass silently) | caught by canary **and** set check |

## Files

| File | What it is |
|---|---|
| `build_day_board.py` | The generator. Writes both artefacts; nothing in them is hand-written |
| `oversikt.template.html` | The markup, with `{{TOKEN}}` placeholders. Not shipped |
| `oversikt.html` | Generated. This is the artefact |
| `data.js` | Generated. The rows, one JSON object per line so a diff is readable |
| `verify_day_board.py` | The constraint checks `tools/verify_dashboard.py` does not make |
| `preview-*.png` | Frames a human looked at, at 1280, 390 and with JS off |

## The data contract — nine columns, one row per pupil per leg per day

| Column | Values |
|---|---|
| `Dato` | ISO `åååå-mm-dd` in the file, displayed `dd.mm.åååå` (docs/11 §9) |
| `ElevKode` | `ELEV-01` … `ELEV-14`. Synthetic, never initials |
| `Retning` | `Til skole` \| `Fra skole` \| `Fra SFO` |
| `Ordning` | `1-10 drosjesentral` \| `heldagsSFO TT-kort` \| `VGS TT-kort` |
| `Planlagt` | `tt:mm` |
| `Bil` | `OT-nn` / `TT-nn`, or `Ikke bestilt` / `Avventer TT-kort` |
| `Ledsager` | `Ja` \| `Nei` \| `Vurderes` |
| `Status` | `I rute` \| `Venter` \| `Avlyst` |
| `EndretAv` | `Skoleadm.` \| `SFO` \| `Sentralbord` \| `Foresatt` \| `Kommune` |

84 rows: 14 pupils × 2 legs × 3 days, with 8 deliberate deviations from the plan — a
sickness cancellation, a same-day change phoned in to the switchboard, two return legs
the school cannot book because the parents book them, a leg waiting on a TT-kort
renewal, a pupil collected by a parent, and one ledsager under assessment.

`EndretAv` is a **role, not a person**, and it is load-bearing rather than decorative:
it is where the three régimes' different ownership becomes visible in the data itself. A
`Venter` row owned by `Foresatt` and a `Venter` row owned by `Kommune` need entirely
different follow-up. It is also why the artefact can be honest about a leg it cannot fix.

## Build and verify

```bash
python3 examples/17-multi-regime-day-board/build_day_board.py

# Both. The first is the repo gate; the second adds the JS-off and viewport
# checks this example exists to demonstrate. Needs the verify extra:
#   uv sync --extra verify && uv run playwright install chromium
uv run python tools/verify_dashboard.py examples/17-multi-regime-day-board/oversikt.html
uv run python examples/17-multi-regime-day-board/verify_day_board.py

# The chart is one drawing scaled to the card, so below a tablet its axis labels are
# smaller than the 14 px floor; at 1024 px and wider every text clears it, and the
# overflow and touch checks run at every viewport regardless.
uv run --extra verify python tools/verify_viewports.py \
  examples/17-multi-regime-day-board/oversikt.html --text-floor 14 --text-floor-above 1024
```

Last run: repo gate **PASS**, example verifier **91 checks, 0 failures**.

## 1. Why the file has no editor in it

The artefact is a **view**. Nothing in it writes anything back. The three régimes are
maintained in whatever system already owns them, and this file renders a snapshot of the
result.

That is not a limitation that was discovered late; it is the constraint that makes the
artefact shareable at all. A file that edits needs a server, an identity and an audit
trail. A file that shows needs none of those, which is why it can be sent as an
attachment and opened offline by someone with no licence.

Where a row is wrong, the fix is in the owning system and the next `data.js` carries it.
Swap that one file and everyone who opens the overview sees new numbers; the overview
itself does not change.

## 2. Three régimes, three owners

The `Ordninger` view states, per régime, who applies, who books the individual trip, who
pays, who assesses the need for a ledsager, and who maintains the row. They differ in
every column, which is the whole argument: a single flat list would have to pick one
answer for each and would therefore be wrong twice.

The `Rutiner` view holds the same for routines. Where a source says nothing, the cell
says it says nothing, in italics. **Nothing in those tables is filled in by guessing** —
an overview that invents a plausible owner is worse than one with a visible hole,
because the hole gets asked about.

## 3. Colour is never the only signal

Status uses shape first, colour second, text always: green circle `I rute`, yellow
triangle `Venter`, red square `Avlyst eller avvik`. WCAG 2.2 criterion 1.4.1, and
docs/09 counts a colour-only indicator as a defect.

The palette is measured, not recalled. `CONTRAST_GATE` lists the pairs the build refuses
to ship without, and `render_palette_css()` re-measures every one on every build and
fails with the ratio it got. One value in this example was caught that way: `#c9c9c9`
read nicer as a control border and was 1.66:1 on white, against the 3:1 that WCAG 2.2
1.4.11 wants. It is `#8c8c8c` now because the gate refused the build.

## 4. Mobile, and JS off

`preview-390.png` and `preview-nojs-1280.png` are the frames a human looked at. With JS
off, the filters and the chart are gone and the table is still there and still readable,
which is the floor docs/11 asks for.

The verifier measures the JS-off case rather than asserting it: it loads the file with
scripting disabled and checks the table is present and the controls are not.

## 5. Whose brand is this? Nobody's, deliberately

This is the only example in the repository that reads **no token file at all** — not a
plugin's, and not the core one either.

docs/22 describes two cases: core ships a neutral palette in
`tools/tokens/palette-neutral.css`, and a brand plugin may provide its own. Both assume
the artefact belongs to the organisation whose repository this is. **This artefact does
not.** It belongs to a municipality that is not a tenant of this platform.

So loading either palette would dress one organisation's artefact in another
organisation's colours. That is a licensing question wearing a styling question's
clothes, and it is much easier to get wrong by default than on purpose: the earlier
version of this example did exactly that, inheriting a status palette simply because
loading it was the path of least resistance.

Instead there is **one marked slot**, `TENANT PALETTE SLOT`, and it is the only place a
colour is set. Everything before it is greyscale. The verifier proves the shape of that
claim rather than trusting it:

- the slot is opened and closed exactly once;
- it holds exactly nine values;
- there is **no colour literal after it closes**;
- everything before it is greyscale only.

Read the slot as an **unresolved plugin**. The artefact declares what it needs, names the
file that would satisfy it, and records the absence rather than papering over it. No
`kommuneblå` has been invented, because inventing a plausible brand colour is worse than
leaving a visible gap.

### How the leak check avoids going stale

The obvious way to write this check is to list one organisation's hex values inline. The
earlier version did, with nine of them, and it was wrong twice over: it goes stale the
moment a palette is edited, and it only ever tests the one brand somebody typed out.

`palette_values()` reads every palette the repository ships instead — `tools/tokens/*.css`
and `plugins/*/tokens/*.css` — and asserts that none of their non-greyscale values appears
here. That is **39 values across 4 files** on the last run, it covers core and every
plugin, and it will cover a plugin added after this was written.

Greyscale is excluded on purpose: `#ffffff` is nobody's trademark, and this artefact's own
base is greyscale, so including it would guarantee a collision and make the check useless.

Three mutations were run against it, and all three failed the gate as they should:

| Mutation | Result |
|---|---|
| Inject a real plugin brand hex into the artefact | caught, and the failure names the file it came from |
| Add a `<link>` that actually loads a palette | caught by filename |
| Delete the palette files so there is nothing to compare against | caught by the vacuity guard |

The third matters most. Without it, moving the palettes would make this check pass by
finding nothing, which is worse than failing, because it manufactures assurance.

One related subtlety, found by the gate firing on its own author: the filename check runs
**outside comments**. Prose that explains why a file is deliberately *not* loaded has to
be free to name it. Banning the word rather than the load would punish the explanation
and reward silence.

## 6. What this example does not show

- **Deployment.** Not attempted, and it cannot be from here. See below.
- **Row-level access control.** Everyone who can open the file sees all 84 rows. If
  different readers must see different pupils, this pattern is the wrong tool and the
  answer is a real reporting product with a security model.
- **Any real tenant's constraints.** Every row in `docs/01-tenant-constraints.md` was
  measured against the tenant this repository's authors can reach. Eksempelkommune is
  fictional, and a real municipality would be running a different tenant with different
  settings. So **nothing in the quirk log is known to hold for the organisation in this
  example.** Re-measure before promising anything, rather than assuming the constraints
  travel.

## Open items

1. The palette slot holds placeholders. A real rollout replaces those nine values, and
   nothing else in the stylesheet, from the tenant's own design manual.
2. Mobile is reviewed at 390 px from screenshots, not on a physical device.
3. The source for the régime tables is fictional. A real deployment must re-derive those
   six columns from the organisation's own published routines, and keep the "says
   nothing" cells wherever the source is silent.
