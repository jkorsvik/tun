# Gemini web app: attach the fixture, export a file, then rebuild it canonically

**Reader:** user — you want an artefact out of your own data and do not intend to change the toolkit.

**Status: capability read from vendor documentation, not a product test.** No Gemini plan,
model, version or date is recorded below because no Gemini web or AI Studio session was run for
this recipe. **Last product run: Not run.** Owner: Tún maintainers.

**Capability, as documented**

| Browse | Repository instructions | Create a file to download | Run a command | Open a real local browser |
|---|---|---|---|---|
| Yes, when grounding is available | No, though a code folder or repository can be attached for reading | Yes — Gemini Apps generate files, downloadable or exportable to Drive | No, in chat | No |

Gemini Apps are the most permissive of the hosted recipes on **input**: besides documents,
images and video, Google documents attaching **one code folder, or one GitHub repository, up to
5,000 files and 100 MB**. That is reading material, not execution. Nothing in the documentation
says Gemini runs the repository's Python, and the exported file is Gemini's own output.

So there are two honest exits. Either you use Gemini to draft and export and then discard the
export in favour of the canonical build, or you use it only for the brief. The recipe below does
both, in that order, and is explicit about which artefact is which.

## Setup

1. **Get the toolkit** — [Install and use Tún](../../INSTALL.md#get-the-toolkit). Python 3 and the
   folder holding `setup.py`. You need this regardless of what Gemini returns.
2. **Sign in** to Gemini Apps. For a work or school Google account, attaching from Drive needs the
   Workspace admin to enable apps in Gemini, and History on with Workspace connected.
3. **Attach the fixture** — [`fixtures/excuses.csv`](fixtures/excuses.csv), 4 rows, total 10,
   Traffic 5 — using **Add files → Upload files**. Limits worth knowing: 10 files per prompt,
   100 MB per non-video file.
4. **Optionally attach the code folder** if you want it to read `tools/build_dashboard.py` and
   explain it. Prefer the ZIP of the toolkit over pointing at your live working copy. Do not
   attach a repository whose contents you could not hand to the result's whole audience.

## Prompt

```text
Attached: a synthetic CSV, four rows — Category, Count, Month. Total 10, Traffic 5
across two rows.

I build a Tún dashboard from it locally: Category as filter, Month as time axis, Count
summed. Answer without writing dashboard HTML:

1. Confirm the four rows and the total 10 from the file, showing the arithmetic.
2. Give me the page subtitle and the source line, assuming synthetic example data.
3. Name what this dataset cannot support at two months and three categories.
4. If I attached the toolkit, name the file that builds the dashboard and the flag that
   makes it one self-contained file. Quote the line you read it from.
```

Question 4 is the interesting one: it tests whether the attached folder was actually read, and
the answer is checkable against `tools/build_dashboard.py` on your own disk.

## Expected result

Prose with the arithmetic, a subtitle, an honest list of limits, and — if the folder was read —
`build_dashboard.py` and `--mode bundled`. That last answer is a real cross-check: if it is wrong,
the folder was not read, and you should not trust the rest of the reading either.

**If you want to see a file**, ask for one and expect a *format* file — Docs, Sheets, `.pdf`,
`.docx`, `.xlsx`, `.csv`, LaTeX, TXT, RTF or Markdown are the documented formats. Google states
that for most formats you can download the file directly or export it to Drive. **HTML is not in
that list**, so a request for an HTML dashboard will most likely come back as a code block or an
in-page preview.

**The canonical path** — in the toolkit folder, Windows PowerShell `py -3`, macOS or Linux
`python3`, per [the common contract](common-contract.md):

```text
py -3 tools/ai_recipe.py build
```

Output: **`work/ai-recipes/tun-recipe.html`** — 4 rows, total 10, Traffic 5 — bundled mode, one
file, no app, no CDN.

**If you exported something:** a Gemini-generated `.html`, or a Markdown/PDF rendering of the
analysis, is a different object from the build. Keep it if it is useful as prose. It is not the
deliverable.

## The Origin Notice

The canonical file carries the provenance block, including
`Made with   : Tún — tun.community` — the Origin Notice that lets you convey the document under
terms of your choice ([artefact exception](../../COPYING.ARTEFACT-EXCEPTION)). An exported Gemini
file carries none. Do not add one by hand; provenance on markup no Tún tool produced is a false
claim.

## Verify, then hand off

```text
py -3 tools/ai_recipe.py check
```

**Static PASS** — exact match with this toolkit's reference build, Origin Notice intact. If you
are checking an exported or downloaded candidate, pass its path; a rejected file means it is not
the canonical build, which is expected for a Gemini export.

```text
py -3 tools/ai_recipe.py browser
```

**Browser PASS** — Chromium from `file://`, network blocked, 10 → 5 on Traffic → 10 on Reset, no
errors, no external requests. Requires provisioned Playwright and Chromium.

Hand off the `.html` as a file. In OneDrive or SharePoint, tell the recipient to download and
open it in a browser.

## Limitations and recovery

| Symptom | What it means | What to do |
|---|---|---|
| It will not return HTML | HTML is not a documented output format | Ask for Markdown or a code block, or stop at the brief |
| Attached folder ignored | Import/attachment limits, or the file type was not read | Ask it to quote a line from a specific file; if it cannot, treat the reading as absent |
| Work account cannot attach from Drive | Admin has not enabled apps in Gemini, or History is off | Upload from your device instead, if policy allows |
| Attach or analysis limit reached | Rolling per-period limits | Wait for the reset, or use the local build and skip the chat |
| Exported file fails `check` | Not the canonical build | Expected. Rebuild with `ai_recipe.py build` |
| You attached a folder you should not have | The chat now holds those files | Delete the chat and the attachment; see Google's data-download page for what is retained |

Do not attach a live working copy of a repository that contains anything restricted, and never put
secrets or restricted rows in a prompt. A filter in the dashboard hides nothing; split the data
before building files for separate audiences.

**Sources read to write this page** (all fetched, all HTTP 200, 2026-11-18):
[Attach & analyze files in Gemini Apps](https://support.google.com/gemini/answer/14903178) ·
[Use Gemini Apps](https://support.google.com/gemini/answer/13275745).
Vendor documentation proves a feature exists; it is not a test of this recipe.
