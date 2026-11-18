# Microsoft 365 Copilot Chat: help with the brief, build the file locally

**Reader:** user — you want an artefact out of your own data and do not intend to change the toolkit.

**Status: capability read from vendor documentation, not a product test.** No version, edition
or date is recorded below because no Microsoft 365 Copilot session was run for this recipe.
**Last product run: Not run.** Owner: Tún maintainers.

**Capability, as documented**

| Browse | Repository instructions | Create a file to download | Run a command | Open a real local browser |
|---|---|---|---|---|
| Yes — prompted responses are grounded in public web data | No | Depends on edition; no confirmed raw `.html` download | No | No |

The consequence, stated plainly: **Copilot Chat is where you settle what the dashboard must
say. It is not where the Tún file is built.** The file comes from the toolkit on your own
machine, using the same commands every other recipe uses.

## Why the file cannot come from here

Microsoft's pages describe file work as Office work: Copilot in Word, Excel, PowerPoint and
OneNote drafts and edits those documents, and the Microsoft Copilot app converts Word, Excel
or PowerPoint to PDF. No Microsoft page I read describes returning a standalone `.html`
document from chat. Even if a session produced one, it would be the assistant's own markup,
not the builder this project tests. A file without the builder's provenance block is not a
Tún artefact, and [the shared acceptance check](common-contract.md) will reject it.

So the split is: chat for the thinking, toolkit for the file.

## Setup

1. **Get the toolkit.** Follow [Install and use Tún](../../INSTALL.md#get-the-toolkit). You need
   the folder that contains `setup.py`, and Python 3.
2. **Confirm the fixture.** The shared synthetic data is
   [`fixtures/excuses.csv`](fixtures/excuses.csv) — 4 rows, total 10. Use that, not work data.
3. **Open Copilot Chat** from the Microsoft 365 app launcher, signed in
   with your Microsoft 365 account. Without a Copilot subscription there are documented limits
   on adding content and using agents.
4. If you intend to attach the CSV, attach it with **Add and manage sources → Upload images and
   files**. Do not attach a repository. Do not attach anything you could not hand to the whole
   audience of the result.

## Prompt

```text
I have a small synthetic CSV with four rows: Category, Count, Month —
Traffic 3 in 2026-01, Weather 1 in 2026-01, Traffic 2 in 2026-02, Calendar 4 in 2026-02.

I am building a Tún dashboard from it, where Category is the filter, Month is the
time axis and Count is summed.

1. Write the one-sentence subtitle this dashboard should carry, and the source line,
   assuming the data is synthetic example data.
2. Name the two or three questions a reader will ask first, and which of them this
   four-row dataset can and cannot answer.
3. Say which claims the dashboard must not imply at this size, for example a trend
   across two months.

Do not write HTML, and do not write a dashboard app. I build the file locally with
the Tún toolkit.
```

## Expected result

You get prose: a subtitle, a source line, and a short list of what four rows can support.
That is input to the build, not the build.

Then, in the toolkit folder:

```text
py -3 tools/ai_recipe.py build
```

Only the interpreter name differs: `py -3` on Windows PowerShell, `python3` on macOS or
Linux. Both spellings are in [the common contract](common-contract.md).

The output is **`work/ai-recipes/tun-recipe.html`**: 4 rows, total 10, Traffic 5 across two
rows. It is built in bundled mode, so the data, styles and interaction are inside the one
file. It is not a link to an app.

## The Origin Notice

The builder writes the provenance block into the file, including
`Made with   : Tún — tun.community`. That block is the **Origin Notice**: it is what lets you
convey the document under terms of your choice, per
[the artefact exception](../../COPYING.ARTEFACT-EXCEPTION). Do not delete it, and do not
paste a Copilot-written app into the file and label it Tún.

## Verify, then hand off

```text
py -3 tools/ai_recipe.py check
```

**Static PASS** means the file matches this toolkit's reference build exactly, and the Origin
Notice is intact. It does not mean the dashboard ran. For that, use an environment with
Playwright and Chromium, then:

```text
py -3 tools/ai_recipe.py browser
```

**Browser PASS** means Chromium opened the file from `file://` with the network blocked, showed
10, changed to 5 for Traffic, and returned to 10 on Reset. Open the screenshot and look at it.

Hand the `.html` over as a file: attach it, or put it in the folder whose permissions match the
audience. If you use OneDrive or SharePoint, tell the recipient to download it and open it in a
browser — the preview can limit scripts. Do not turn it into a hosted app.

## Limitations and recovery

| Symptom | What it means | What to do |
|---|---|---|
| Copilot returns a Word or Excel file, or a PDF | Documented output formats for Office work | Keep it as a brief; build the HTML locally |
| "Add files" is missing or disabled | Not signed in with a Microsoft 365 account, or a licensing limit | Sign in; if the tenant blocks uploads, paste the four CSV lines as text instead |
| Copilot answers about the wrong columns | It inferred a schema | Restate the four rows in the prompt |
| `check` says "Not the canonical file" | The HTML came from somewhere other than this toolkit | Rebuild with `ai_recipe.py build`; do not hand-edit the file |
| `browser` says provisioning is missing | Playwright or Chromium is absent | Install as the contract describes, or record **browser not verified** |

Never put a secret, a token or restricted rows in the prompt. A filter in the dashboard hides
nothing; split the data before you build separate files for separate audiences.

**Sources read to write this page** (all fetched, all HTTP 200, 2026-11-18):
[Microsoft Copilot overview](https://learn.microsoft.com/en-us/copilot/plan/copilot-overview) ·
[Add content to Microsoft Copilot Chat prompts](https://support.microsoft.com/en-us/microsoft-365-copilot/add-content-to-microsoft-365-copilot-chat-prompts).
Vendor documentation proves a feature exists; it is not a test of this recipe.
