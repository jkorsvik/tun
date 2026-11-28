# ChatGPT: analyse in chat, build the file in the toolkit

**Reader:** user — you want an artefact out of your own data and do not intend to change the toolkit.

**Status: capability read from vendor documentation, not a product test.** No ChatGPT plan,
model, version or date is recorded below because no ChatGPT session was run for this recipe.
**Last product run: Not run.** Owner: Tún maintainers.

**Capability, as documented**

| Browse | Repository instructions | Create a file to download | Run a command | Open a real local browser |
|---|---|---|---|---|
| Yes, with web search enabled | No | Yes — created files are saved and downloadable | Python inside its own sandbox, not your machine | No |

ChatGPT is the one recipe here that documents **both** halves: it runs Python in a stateful
Jupyter sandbox and it saves created files that you can download. That is genuinely useful, and
it still does not produce a Tún file, for one reason: the sandbox has no repository. OpenAI's own
page states the analysis environment cannot make external web requests or API calls, so it cannot
clone the toolkit, install nothing, and run the builder. Code it writes is its own.

The division of labour is therefore: **ChatGPT to explore the data, the toolkit to build the
artefact.**

## Setup

1. **Get the toolkit** — [Install and use Tún](../../INSTALL.md#get-the-toolkit). Python 3, and the
   folder containing `setup.py`.
2. **Start a chat** with data analysis / file creation enabled. Without **Code Interpreter &
   Data Analysis** in the session or the GPT, downloads are documented to fail.
3. **Attach the fixture** — [`fixtures/excuses.csv`](fixtures/excuses.csv), 4 rows, total 10,
   Traffic 5 — or paste its four lines. OpenAI's guidance is the same as ours: structured data,
   clear column names, one record per row.
4. **Do not attach a repository, a ZIP of the repository, or work data.** The fixture is enough
   to prove the recipe, and the sandbox cannot use a repo anyway.

## Prompt

```text
Attached: a synthetic CSV, four rows — Category, Count, Month. Total 10, Traffic 5
across two rows.

Two parts, in this order.

Part 1 — analysis only, no dashboard code:
- Confirm the row count and total from the file yourself, and say what you computed.
- State what a two-month, three-category dataset can support, and what it cannot
  (for example: it cannot show a trend, a share of a market, or a season).
- Write the subtitle and source line for a one-page dashboard about it.

Part 2 — a reusable snippet, not a dashboard:
- Write a short Python function that reads the CSV and prints the four facts above,
  so I can paste it into my own notes. No plotting, no HTML.
```

Part 2 is deliberately small. Asking for a dashboard produces a second, untested generator; asking
for four lines of arithmetic gets you a cross-check you can run next to the builder.

## Expected result

Part 1: a computed confirmation — 4 rows, total 10, Traffic 5 — and an honest list of what the
data cannot show. Part 2: a snippet.

If you asked for a file, and the session creates one, you can download it from the file card in
the reply or from **Library**, and OpenAI documents that files you create are saved there. **That
file is not the canonical artefact.** Whether ChatGPT returns HTML depends on the session and on
Code Interpreter being on; when it does, it is ChatGPT's markup.

The canonical path, in the toolkit folder — Windows PowerShell `py -3`, macOS or Linux `python3`,
per [the common contract](common-contract.md):

```text
py -3 tools/ai_recipe.py build
```

Output: **`work/ai-recipes/tun-recipe.html`** — 4 rows, total 10, Traffic 5 — bundled, one file,
no app, no CDN.

## The Origin Notice

The builder writes the provenance block, including `Made with   : Tún — tun.community`. That is
the Origin Notice ([artefact exception](../../COPYING.ARTEFACT-EXCEPTION)), and it is what makes
the document yours to convey. A downloaded ChatGPT file has no such block; do not add one by
hand. Provenance on markup no Tún tool produced is a false claim.

## Verify, then hand off

```text
py -3 tools/ai_recipe.py check
```

**Static PASS** — byte-identical to this toolkit's reference build, Origin Notice intact. It is a
content check, not a rendering check. If you are checking a downloaded copy, pass its path:
`py -3 tools/ai_recipe.py check "$HOME/Downloads/tun-recipe.html"`.

```text
py -3 tools/ai_recipe.py browser
```

**Browser PASS** — Chromium from `file://` with the network blocked: 10 → 5 on Traffic → 10 on
Reset, no errors, no external requests. Needs provisioned Playwright and Chromium.

ChatGPT's own preview of an HTML file, if it shows one, is **not** this check. It renders inside
the vendor's sandbox with the vendor's rules.

Hand off the `.html` as a file. In OneDrive or SharePoint, say "download then open in a browser".

## Limitations and recovery

| Symptom | What it means | What to do |
|---|---|---|
| "Files created cannot be downloaded" | Code Interpreter & Data Analysis is off, or the file step failed | Enable it; retry with a smaller output; or skip download and build locally |
| It cannot reach the repository or GitHub | Documented: the analysis sandbox makes no external requests | Download the toolkit yourself; do not try to work around the sandbox |
| Numbers differ from 10 | It misread the schema | Ask it to print the parsed rows, and compare with the CSV by eye |
| Downloaded HTML fails `check` | It is not the canonical build | Expected. Rebuild with `ai_recipe.py build` |
| It wrote a dashboard app you like | Plausible-looking, untested | Keep the idea; take the numbers and layout, then build |

Files in Temporary Chat are documented as not saved to your account or Library, and files in a
locked chat are reachable only from that chat. Download what you intend to keep. Never put a
secret, a token or restricted rows in a prompt or attachment — a filter does not protect rows.

**Sources read to write this page** (all fetched, all HTTP 200, 2026-11-18):
[Data analysis with ChatGPT](https://help.openai.com/en/articles/8437071-data-analysis-with-chatgpt) ·
[Using Library to manage files in ChatGPT](https://help.openai.com/en/articles/20001052-using-library-to-manage-files-in-chatgpt) ·
[Troubleshooting GPTs](https://help.openai.com/en/articles/11325361-troubleshooting-gpts).
Vendor documentation proves a feature exists; it is not a test of this recipe.
