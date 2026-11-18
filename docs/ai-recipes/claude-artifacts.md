# Claude.ai `Artifacts`: draft beside the chat, ship the canonical file

**Reader:** user — you want an artefact out of your own data and do not intend to change the toolkit.

**Status: capability read from vendor documentation, not a product test.** No Claude plan,
model, version or date is recorded below because no Claude.ai `Artifacts` session was run for this
recipe. **Last product run: Not run.** Owner: Tún maintainers.

**Capability, as documented**

| Browse | Repository instructions | Create a file to download | Run a command | Open a real local browser |
|---|---|---|---|---|
| Yes, when web search is enabled | No | Yes for template artefacts (Design exports standalone HTML); legacy artefacts can be copied or downloaded | No, in chat | No |

Two things matter here and they are easy to conflate. An `Artifact` is a Claude-hosted
preview. A **Tún file** is a self-contained document built by this repository's builder. They
look similar on screen and they are not the same object: only one has the provenance block, and
only one passes [the shared acceptance check](common-contract.md).

## The boundary, stated once

| | Claude `Artifact` | Tún file |
|---|---|---|
| Who wrote the markup | Claude, per conversation | `tools/build_dashboard.py` at a known revision |
| Where it lives | Claude's workspace, behind a share link | your filesystem, as a document |
| Opens with | Claude, or a published URL | any browser, offline, from a folder |
| Provenance | the conversation | the provenance block and Origin Notice inside the file |
| Survives the vendor changing a plan or a URL | not guaranteed | yes, it is a file |

So an `Artifact` is a good place to **think in public**: to draft the subtitle, argue about which
claims four rows support, sketch a layout. It is a bad place to **end up**, because the result
cannot be handed to a recipient who has no Claude account and no link permission.

## Setup

1. **Get the toolkit** — [Install and use Tún](../../INSTALL.md#get-the-toolkit). Python 3 and the
   folder holding `setup.py`.
2. **Check file creation is on.** Anthropic's page states `Artifacts` need cloud code execution and
   file creation, called **Create and edit files**, enabled in **Settings → Capabilities**
   (Free, Pro, Max, Ultra) or **Organization settings → Capabilities** (Team, Enterprise). Without
   it, an artefact may render as a code block instead of a panel.
3. **Attach the fixture** — [`fixtures/excuses.csv`](fixtures/excuses.csv), 4 rows, total 10,
   Traffic 5 — or paste its four lines. Do not attach a repository, and do not attach anything
   whose audience is narrower than the result's.

## Prompt

```text
Attached is a synthetic CSV, four rows: Category, Count, Month. Total 10; Traffic is 5
across two rows.

I will build a Tún dashboard from it locally — Category as filter, Month as time axis,
Count summed. Please do not write the dashboard HTML.

Instead:
1. Give me the subtitle and the source line for that dashboard, in English, one line each.
2. List two claims this dataset supports and two it must not imply, given only two months
   and three categories.
3. Then, as a layout note only, describe the order the page should present things in
   (header, KPI cards, filter, chart, rows behind the numbers) and why.
```

Deliberately no "make me an artefact". Ask for a **layout note**, and you get design advice
without a second, competing generator in the loop.

## If you do want to see it as an artefact

Ask for a static mock explicitly, and treat it as a sketch:

```text
Now render that layout as a static artefact preview with placeholder numbers. Label it
"layout sketch, not buildable data". Do not claim it is a Tún file.
```

**Expected result, the canonical path:** you still build locally. In the toolkit folder,
Windows PowerShell `py -3`, macOS or Linux `python3`
([the common contract](common-contract.md) has both):

```text
py -3 tools/ai_recipe.py build
```

Output: **`work/ai-recipes/tun-recipe.html`** — 4 rows, total 10, Traffic 5 — bundled mode, one
file, no app, no CDN.

**Expected result, if you export an artefact instead:** a `.html` file you can download, because
Anthropic documents that Design-template artefacts export as standalone HTML (and legacy
artefacts can be copied or downloaded from the artefact panel). That file is **Claude's HTML, not
the canonical build**. `check` will reject it with "Not the canonical file", and that rejection
is correct — it means you are holding a different object, not that something broke.

## The Origin Notice

The canonical file carries the provenance block, including
`Made with   : Tún — tun.community`. It is the Origin Notice that permits conveying the document
under terms of your choice ([artefact exception](../../COPYING.ARTEFACT-EXCEPTION)).

An exported artefact carries no Origin Notice. Do not add one to it by hand: a notice on
markup no Tún tool produced is a false provenance claim, and the exception it points at does not
apply. If you want a file with the notice, build the file.

## Verify, then hand off

```text
py -3 tools/ai_recipe.py check
```

**Static PASS** — exact match with this toolkit's reference build, Origin Notice intact.
**Not** a statement that it rendered.

```text
py -3 tools/ai_recipe.py browser
```

**Browser PASS** — Chromium, `file://`, network blocked, 10 → 5 on Traffic → 10 on Reset, zero
external requests. Requires provisioned Playwright and Chromium.

Hand off the `.html`, not the share link. Anthropic's sharing page is explicit that a recipient
who opens an "anyone with the link" artefact sees the artefact but the parts that use connected
apps or Claude do not work for them — which is the difference between a document and a
hosted page with a dependency. Publish the artefact only if you mean to share a preview.

## Limitations and recovery

| Symptom | What it means | What to do |
|---|---|---|
| `Artifact` shows as a code block | File creation is off, or the plan does not include it | Enable **Create and edit files**; otherwise use the code block as text only |
| You have a share link and no file | That is how artefacts work | Build locally; the link is not a document |
| Exported HTML fails `check` | It is not the canonical build | Expected. Rebuild with `ai_recipe.py build` |
| You cannot reach the artefact later | Plan, workspace or sharing changed | This is why the file is the deliverable |
| Team/Enterprise cannot share externally | Owner-controlled external sharing | Ask the workspace owner; or deliver the `.html` through your own file share |

`Artifacts` start private to you, but a published link is still a link. Do not put restricted rows
in a prompt, an attachment or an artefact. A filter does not protect rows; split the data first.

**Sources read to write this page** (all fetched, all HTTP 200, 2026-11-18):
[What are artefacts and how do I use them?](https://support.claude.com/en/articles/17153992-what-are-artifacts-and-how-do-i-use-them) ·
[Share artefacts](https://support.claude.com/en/articles/9547008-share-artifacts).
Vendor documentation proves a feature exists; it is not a test of this recipe.
