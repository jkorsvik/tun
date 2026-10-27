# 19 — the Tún pitch, as a Tún artefact

`tun-pitch.html` is the one-page pitch: the system diagram, the four-step process, and the
measured answer to the question that always comes back — *"how do I actually share an HTML
file with one colleague?"*

Open it. It is 15 KB, one file, and it works offline.

## Why it is built the way it is

The pitch makes a claim about portability, so it has to be the thing it describes. This file
therefore has **no code that runs at all**: pure HTML, CSS and inline SVG. That is not a
limitation for a pitch, it is the argument. The worst outcome in a hostile preview surface is
that it looks plainer, never that it is dead.

Consequences worth knowing if you edit it:

- the diagram is hand-written SVG, so it scales to any width and prints
- no `:target` navigation and no pinned header, because both are measured-broken in the
  tenant's inline preview (`docs/01-tenant-constraints.md` rows 24 and 26)
- the literal characters that trip row 25 appear nowhere, not even in prose

## The sharing table is the load-bearing part

Everything in that table is a **manual test on a real device**, from
`docs/01-tenant-constraints.md` rows 21, 22 and 27. The finding that matters is
counter-intuitive and is the answer to the objection:

> **The sharing path decides, not the device.** The same file, on the same phone, works
> through a link in a chat message and shows raw source through the plain link rendered
> underneath it.

So the answer to "must it be hosted somewhere with access control?" is **no**. The access
control already exists: it is the permissions on the folder or the link. What fails is the
*preview surface*, and a preview surface is not a browser.

Keep that table honest. It is small: one phone, one chat version, one client. If you extend
it, extend the rows in `docs/01` first and copy from there, never the other way round.

## What it must keep saying

The hard limit stays on the page: **a file cannot hold a secret.** If two readers must see
different numbers, this is the wrong tool and Power BI is the right one. A pitch that hides
its own limit is a pitch that gets found out in the room.

## Verifying a change

```sh
python3 tools/verify_standalone_core.py examples/19-tun-pitch/tun-pitch.html

# The illustration is one scaled picture: its labels are drawn in the picture's own
# units, so the floor it can hold depends on the width. From 1366 px up every label
# is at least 11 px; narrower than that the picture scales with the window, and the
# overflow and touch checks still run at every viewport.
python3 tools/verify_viewports.py examples/19-tun-pitch/tun-pitch.html \
    --text-floor 11 --text-floor-above 1366
```

Nine checks, including self-containment and the provenance block. Then **look at the
screenshot it writes** — the diagram is a visual artefact, and a clean gate says nothing
about whether two labels overlap.
