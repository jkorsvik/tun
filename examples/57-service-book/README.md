# 57. A plan you edit, then hand over

A duty roster is not a report. It is a plan that changes while people are standing
in it: someone swaps a shift, a rotation gives way to fixed posts at noon, a day is
added. A dashboard cannot hold that, because it is read-only by design, and a
spreadsheet that holds it cannot be handed to a phone on a locked-down network.

This example is the middle path. One self-contained HTML file that you **edit in the
browser** and then **download again** as a new standalone copy. The downloaded file
carries your edits, opens from `file://`, needs no server, and can be mailed or put
in a synced folder. Open it a week later and everything is still there.

**Governance cost:** none. No install, no account, no build step, no Node, no admin
approval. It is a file.

## The two ideas worth stealing

Most of this file is ordinary DOM work. Two decisions are the reason it stays
correct as it grows, and they are what a reader should take away.

### 1. The plan is data, the page is a projection of it

Nothing but the tab bar and the pane shells exists in the markup. `state.panes` is a
list of records, and each record's `type` decides which builder draws it:

```js
{ id: 'rullering', title: 'Rullering', heading: 'Gjeldende vaktliste',
  type: 'rullering', badge: true }
```

Adding a section is adding a record. There is no `switch` over pane ids anywhere in
the file, no branch that says "if this is the roster tab". The Layout panel (button
**Faner**) adds, renames, reorders and removes panes; a pane of type `tekst` brings
its own list into existence. The same holds for days: `state.days` is a list, and the
roster is drawn by looping over **the days**, not over the watches.

That last choice is small and load-bearing. Loop over the watches and a day with no
watches simply vanishes, so the reader cannot tell "nothing planned yet" from "this
day was deleted". Loop over the days and an empty day renders and says so:

> Ingen vakter på denne dagen ennå. Bruk «+ vakt» og sett datoen.

### 2. A change of plan is expressed by marking a record, never by deleting one

At noon on the last day the rotation stops and fixed posts take over. The obvious
implementation is to delete the later watches. That destroys the answer to the
question a service book exists to answer: *what was the plan, and why did it change?*

So the later watches stay in `state.watches`. Two functions carry the idea:

```js
superseded(watch)    // does this watch start at or after the cut?
effectiveEnd(watch)  // a watch straddling the cut is shown as ending AT the cut
```

A superseded watch renders struck through, with a visible `erstattet av …` tag, and
the checks raise a **warning** that names it — because the roles are still attached
to it and someone has to decide what they do now. The plan ends where the next thing
starts; the history is not quietly rewritten.

The cut itself, `handover.rotationEnds`, is an editable field, so the plan can move
without editing code. The same section lists what the source did **not** decide, so
the open questions travel with the file instead of living in someone's head.

## The rest of what it does

* **Eight pane types** — `naa`, `rullering`, `posts`, `folk`, `vo`, `instruks`,
  `sjekk`, `beskjed`, `tekst`. One builder function each; a new **type** is one branch, one entry in
  `PANE_TYPES`, and its own markup ids.
  A new **pane of an existing type** is just a record — but only fully for `tekst`, which
  carries its own list. The other types write fixed DOM ids (`#watches`, `#posts`,
  `#people`), so two of the same type on one page would collide. The example ships one of
  each for that reason; the layout panel lets you add more `tekst` panes freely, rename
  and reorder anything, and remove anything except `naa` and `rullering`.
* **Every list adds and removes its own points.** The add button binds its own
  handler at creation. This is not a detail: wiring add buttons through a global
  `getElementById` pass makes them silently dead every time the pane is rebuilt, and
  the page looks fine.
* **Save is the delivery mechanism.** `download()` clones `state` into the
  `<script id="appstate">` block and downloads a copy of the document. Reopening it
  restores panes, days, edits and the cut.
* **Text is text.** User strings go in through `textContent` and are escaped at `<`
  and `>` in the payload, so a list item reading `</script>` cannot end the script
  element. The suite pushes exactly that string and checks the round trip.
* **A check names its record.** "Something may be wrong" is worse than nothing; every
  warning says which watch or which role.
* **The clock is Oslo, not the reader's.** A plan read on a phone in another timezone
  shows the wall clock the author wrote.
* **The file is the source of truth, and the only one.** `boot()` reads the state embedded
  in the copy it was opened from. There is no browser store, so two copies of a plan cannot
  silently disagree. Edits made but never saved with **Lagre fil** are lost on reload,
  which is deliberate. A file whose payload will not parse says so **in the page** and
  stops, rather than showing a blank plan.

## Rebuild

```bash
python3 examples/57-service-book/generate_data.py
python3 examples/57-service-book/build_service_book.py
```

`generate_data.py` is seeded and writes `service-book.json`, so the committed state
can be regenerated and compared. The scenario is invented: a three-day information
desk at a fictional venue, staffed by **roles** (`Desk A`, `Post 1`) rather than
names, because a role label cannot accidentally resemble a real person.
`SOURCE_DATE_EPOCH` pins the build stamp when a reproducible file is needed.

## Verify

```bash
uv run --extra verify python3 examples/57-service-book/verify_service_book.py --engines all
uv run --extra verify python3 tools/verify_a11y.py examples/57-service-book/service-book.html
uv run --extra verify python3 tools/verify_viewports.py examples/57-service-book/service-book.html
```

The suite is **46 checks per engine**, in Chromium, Firefox and WebKit (138 in total).
It opens the file from `file://` and checks: a tab and a section per pane; the handover
logic (watches at or after the cut are marked **and kept**, and the row says what
replaced them); `effectiveEnd` on a watch that really straddles the cut, on one wholly
after it and one wholly before it; that each day heading carries **its own** label and
note; that a day with no watches renders and says so; that adding and removing a point
changes both the list and the DOM; that hostile text survives as exact text and injects
nothing; adding a pane; renaming a pane and then proving **every tab still responds**;
adding a day; then **saving and reopening** and finding the new pane, the new day, every
watch, every superseded mark, an **edited list point**, the **pane rename** and the
**moved cut** still there. Both the first page and the reopened one fail the run on any
console error or any external request.

Four mutations were run against it to prove it can fail, each restored afterwards:

| Mutation | What goes red |
|---|---|
| `superseded()` always returns `false` | `superseded watches marked` |
| the add-point handler is detached | `add a point`, `remove a point` |
| `importFile` reads `match[1]` instead of `match[2]` | `"Åpne fil" loads the payload it is given` |
| the superseded warning is deleted from the checks | `the checks pane warns about every superseded watch` |
| the load-error path re-parses the broken payload instead of showing an error | `a corrupt payload shows an error pane` |

A fifth, putting a wrong day note back into the data, reddens that day's
`carries its own text` check. It is not in the script because it edits the committed JSON,
not the built page.

The rendered page is also swept at six viewports:

```bash
uv run --extra verify python3 tools/verify_viewports.py examples/57-service-book/service-book.html
```

That sweep found four defects the first version shipped, and it is worth knowing they
existed because a measurement passing is not a layout being right:

* card labels and the tab badge rendered at 12–13 px, under the 14 px floor;
* eighteen controls were below the 44 px touch minimum, because the rule was keyed only on
  `pointer:coarse` while the sweep measures by viewport width;
* the tab bar did not wrap, so labels ran together as one word
  ("Rullering 18Poster 5Folk 14") on a phone.

All three are fixed in the stylesheet, and the sweep now passes at all six sizes. Look at
`viewport-shots/` as well: the sweep proves measurements, not layout.

Two limits worth stating. `verify_service_book.py` **fails** rather than skips when
Playwright is missing, because a gate that reports success having never opened the file
is worse than one that reports nothing. And the browser suite is the only thing that
proves the interactions: the stdlib tests and `check_tree.py` prove shape, not behaviour.

## What it does not do

No server, so two people editing the same file do not merge: each downloads their own
copy, which is why the file states its own provenance and why the tool is for a plan
one person hands over, not for a shared live document. No accounts, no permissions —
the boundary is the folder you put the file in, not a filter inside it. No codes or
phone numbers: anything sensitive stays out of the document by design, and the footer
says so. No column chooser and no chart: a plan is read in the order it was written.
