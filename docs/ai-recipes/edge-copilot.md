# Copilot in Microsoft Edge: read the project, then build locally

**Reader:** user — you want an artefact out of your own data and do not intend to change the toolkit.

**Status: capability read from vendor documentation, not a product test.** No Edge or Copilot
version, edition or date is recorded below because no Edge Copilot session was run for this
recipe. **Last product run: Not run.** Owner: Tún maintainers.

**Capability, as documented**

| Browse | Repository instructions | Create a file to download | Run a command | Open a real local browser |
|---|---|---|---|---|
| Yes — page, tab and PDF context | No | No documented file output | No | Yes, manually: it is a browser |

Edge Copilot is the only recipe here whose honest strength is **reading**. It can look at
`tun.community`, at a GitHub file page, at a CSV you have open, and at a PDF — and answer
questions grounded in what is on screen. It is not documented to hand back a file, and it
cannot run the builder. So it plays two real roles: understanding the project before you start,
and opening the finished file in the browser you already have.

## What it can and cannot do here

Documented: Copilot in Edge summarises open tabs, videos and PDFs, and answers from the
current page, page title, open tabs and browsing history. "Browse with Copilot" can click,
type and navigate tabs, and can work in an already-open document when explicitly asked.

Not documented anywhere I read: returning a downloadable `.html` file, or executing a command
in a terminal. Treat "make me a dashboard file" as a request it will answer with prose or an
in-page attempt, not with an artefact.

That is not a dead end. It changes the order of work: **read first in Edge, build second in the
toolkit, look third in Edge.**

## Setup

1. **Get the toolkit** — [Install and use Tún](../../INSTALL.md#get-the-toolkit). Python 3, and the
   folder holding `setup.py`.
2. **Open Edge** and the Copilot pane. Being signed in changes what is available; so does
   whether your organisation allows Copilot to read page context.
3. **Open the pages you want it to read**, for example:
   - `https://tun.community`
   - the repository's `START-HERE.md` and the folder view of `tools/`
   - the shared fixture, [`fixtures/excuses.csv`](fixtures/excuses.csv) — 4 rows, total 10.
4. **Check what context it is using.** Edge's own page says Copilot may use the current page,
   page title, open tabs and browsing history, and that a tenant or you can turn that off. If
   page reading is off, this recipe's main value is gone; use the local build only.

## Prompt

Open the repository page and the fixture, then paste:

```text
Using the Tún pages and the CSV open in my tabs:

1. In two sentences, what does Tún produce, and what does it deliberately not need?
2. The CSV has four rows — Category, Count, Month — total 10, Traffic 5 across two rows.
   Name the header, filter, measure and time axis the Tún builder would take for it.
3. Which of these commands belong in a terminal on my machine, and which would need a
   hosted service: build, check, browser?
4. Stop there. Do not write HTML and do not create a dashboard file.
```

Question 3 is the useful one: it makes the assistant state, in its own words, that the build is
local. If it claims it can produce the file, that is the failure mode this recipe exists to
prevent, and the answer is the local command below.

## Expected result

Prose: what Tún is, `Category` as dimension and filter, `Count` as measure, `Month` as time;
and an admission that all three commands are local. No file.

Then, in the toolkit folder — Windows PowerShell `py -3`, macOS or Linux `python3`, as
[the common contract](common-contract.md) spells out:

```text
py -3 tools/ai_recipe.py build
```

That writes **`work/ai-recipes/tun-recipe.html`** — 4 rows, total 10, Traffic 5 — as one
self-contained file in bundled mode.

## The Origin Notice

The builder writes the provenance block, including `Made with   : Tún — tun.community`. It is
the Origin Notice that lets you convey the document under terms of your choice
([artefact exception](../../COPYING.ARTEFACT-EXCEPTION)). Nothing Edge Copilot writes goes into
that file, so nothing here can damage or forge it — provided you do not let an assistant
rewrite the file after the build.

## Verify, then hand off

Two different verifications, and they are not the same claim:

```text
py -3 tools/ai_recipe.py check
```

**Static PASS** — the file matches this toolkit's reference build exactly and the Origin Notice
is intact. It says nothing about rendering.

```text
py -3 tools/ai_recipe.py browser
```

**Browser PASS** — scripted Chromium opened it from `file://` with the network blocked, showed
10, filtered to 5 for Traffic, and returned to 10 on Reset. This needs provisioned Playwright
and Chromium.

**Opening the file in Edge yourself is a third thing and it is worth doing**: it is a real
browser, the one your recipient may use, and it is not the automated gate. It proves the file
opens and that one number matches the CSV. It does not prove the filter still works, because
you would be checking by eye. Record it as a manual check.

Hand off the `.html` as a file. In OneDrive or SharePoint, tell the recipient to download and
open it in a browser; the preview can limit scripts.

## Limitations and recovery

| Symptom | What it means | What to do |
|---|---|---|
| Copilot answers from the wrong tab | Context comes from open tabs and history | Close unrelated tabs, or turn off context clues and paste the text instead |
| It offers HTML in a code block, in-page | Its own markup, not the builder's | Copy nothing into the artefact; run the local build |
| It cannot see the repository at all | Tenant policy or signed-out state | Download the toolkit and read `START-HERE.md` locally |
| "Browse with Copilot" acts on the page | It can click and type on sites | Do not point it at a page where an action would change or send anything |
| `check` says "Not the canonical file" | The file was edited or came from elsewhere | Rebuild with `ai_recipe.py build` |

Do not let a browsing assistant sign in, submit a form, or send mail on your behalf as part of
this recipe. Keep restricted data out of tabs that Copilot can read — browsing context is
exactly what this tool consumes.

**Sources read to write this page** (all fetched, all HTTP 200, 2026-11-18):
[Getting started with Copilot in Microsoft Edge](https://support.microsoft.com/en-us/edge/copilot/getting-started-with-copilot-in-microsoft-edge) ·
[Browse with Copilot in Microsoft Edge](https://support.microsoft.com/en-us/edge/copilot/browse-with-copilot).
Vendor documentation proves a feature exists; it is not a test of this recipe.
