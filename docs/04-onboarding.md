# Onboarding: from a spreadsheet to a shared dashboard

**Reader:** user — you want an artefact out of your own data and do not intend to change the toolkit.

[START-HERE.md](../START-HERE.md) is the shortest route. This guide adds Windows details,
verification, publishing and the data boundary.

Two routes, and you can stop after the first:

- **Part 1** builds a real dashboard from the command line in about five minutes, with no
  AI tool installed.
- **Part 2** installs the Agent Skills so a coding assistant can do the same job from a sentence.

**Done looks like this:**

- [ ] Python runs and reports 3.9 or newer
- [ ] you have opened the example dashboard from `file://` in a browser
- [ ] you have compared one number with the CSV and looked at the verification screenshot
- [ ] you know who may read every row in the file you share

---

## Windows: the four things that are different

Everything else is identical on Windows and macOS.

| On Windows | What to know |
|---|---|
| `python3` is `py -3` | Use `py -3` wherever this guide shows `python3`. `setup.py` prints the spelling your machine has. |
| Skills are **copied**, not symlinked | Symlinks need Developer Mode. `setup.py` copies the files instead. Re-run it after updating a skill, and it tells you when a copy is stale. |
| OneDrive lives elsewhere | `%OneDriveCommercial%`, not the macOS `~/Library/CloudStorage/...` path. |
| Paths use `\` | Forward slashes also work in the Python commands. Nothing here needs a shell script. |

---

## Part 1: five minutes, no AI tool

### Step 1. Check Python

macOS:

```bash
python3 --version
```

Windows, in PowerShell:

```powershell
py -3 --version
```

If that fails, install Python from [python.org](https://www.python.org/downloads/) and tick
"Add python.exe to PATH", or run `winget install Python.Python.3.12`. Anything 3.9 or newer
is fine. The builders use only the Python standard library.

### Step 2. Get this repository

```bash
git clone https://github.com/jkorsvik/tun.git
cd tun
```

No git yet? Use `winget install Git.Git` on Windows or `xcode-select --install` on macOS.

### Step 3. Build the example

```bash
python3 tools/build_dashboard.py \
  --data examples/01-hello-dashboard/salgsdata.csv \
  --title "Salg per region og produkt 2026" \
  --dimension Produkt --measure Belop --time Maaned \
  --filters Region,Produkt,Kanal \
  --source "Eksempeldata (syntetisk) - salgsdata.csv" \
  --requested-by "Prosjekteier" \
  --out /tmp/salg.html
```

Open `/tmp/salg.html` in your browser. On Windows, `start` it from the directory you chose
for `--out`. The deliverable is one file. No server starts, and no package installation is
needed for the build.

**Look at it.** A clean build log does not show overlapping labels or a number that is wrong
by a factor of a thousand.

### Step 4. Prove it renders

Install [uv](https://docs.astral.sh/uv/) and Chromium once, then run the verifier:

```bash
uv sync --extra verify && uv run playwright install chromium
uv run python tools/verify_dashboard.py /tmp/salg.html
```

Expected: `✓ PASS`, plus a screenshot path. Open the screenshot. The verifier refuses to
report success when it cannot open a real browser.

Use your own CSV as `--data` next. Column names come from your file. If one is wrong, the
builder lists the columns it found. Refusals start with `error:` and exit 2, so a calling
script can distinguish a refused input from a crash.

---

## Part 2: the same job, by asking

The skills are open [Agent Skills](https://agentskills.io/specification): editable Markdown
recipes that tell an assistant how to build and check the file. Clone the repository, then
run the command for your tool:

| Tool | Install |
|---|---|
| Claude Code | `python3 setup.py --tool claude` |
| Codex, Gemini CLI, GitHub Copilot, VS Code, OpenCode | `python3 setup.py --tool agents` |
| RAIWork | `python3 setup.py` |

On Windows, use `py -3 setup.py --tool claude` or `py -3 setup.py --tool agents`.

Check the installation afterwards:

```bash
python3 setup.py --check
```

Then open your assistant with this repository as its working folder and ask:

> Build me a dashboard from `examples/01-hello-dashboard/salgsdata.csv`, with amounts by
> product, the trend over months and region as a filter.

The skills tell the assistant to use the tested builders and verification tools. You can
read and change the recipes in `skills/` without a build step.

### ChatGPT, Grok and other chat bots

Use the [copyable starter prompt](../START-HERE.md#3-chatgpt-grok-or-another-chat-bot).
The bot writes its own HTML and JavaScript, not the tested Tún builders. This is useful for
a first try. Use Part 1 or Part 2 for the full toolkit and verification.

### What to ask for

| You want to... | Say something like... |
|---|---|
| start something new | "make me a dashboard from this file" |
| the list, not a chart | "give me a searchable list of the open cases" |
| a process diagram | "draw how a request flows between these three teams" |
| know if this is the right approach | "can this replace our Power BI report?" |
| update stale numbers | "refresh the sales dashboard with the new export" |
| check before sending | "is this dashboard safe to share?" |
| share it | "publish this to the team folder" |

---

## Part 3: publish it

Put the file in a synced OneDrive or SharePoint folder and share it the way you share a
document. You can also attach it in Teams or email, publish it as a static web page, or use
the Atlassian Artifacts route in `docs/29-atlassian-artifacts.md`.

A coding assistant with the publishing tools can do this for you. It must confirm the folder,
tell you who can see it and show you any announcement before sending.

### The one quirk to explain to readers

SharePoint downloads an HTML file instead of rendering it in the page. That is a Microsoft
security rule. The download is the delivery mechanism, not a failure.

Tell the reader: "Click the link, then open the downloaded file in your browser. It also
works offline."

---

## The one rule that actually matters

> **If different people who open the dashboard must see different rows of data, this
> approach cannot be used.**

The data lives inside the file. Anyone who can open the file can read all of it. A browser
filter hides nothing. Split the data before building: same dashboard shell, one file per
audience, each in a folder only that audience can open.

Use paired mode when the numbers need refreshing without a rebuild. A trusted `data.js`
sits beside `dash.html`; replace it and readers see the new numbers on the next load.
That is an update on reload, not real-time delivery.

---

## Where things are

| Path | What it is |
|---|---|
| [START-HERE.md](../START-HERE.md) | the shortest first-run route |
| `docs/00-vision.md` | why this exists, and the Power BI boundary |
| `docs/01-tenant-constraints.md` | what SharePoint actually does, measured |
| `docs/02-architecture.md` | the delivery tiers and their approval costs |
| `docs/03-skill-tree.md` | the skills and how they fit together |
| `docs/05-toolchain.md` | every tool needed and why |
| `docs/30-glossary.md` | the vocabulary, for anyone who is not a developer |
| `skills/` | the editable recipes |
| `examples/` | working artefacts with synthetic sample data |
| `CONTRIBUTING.md` | how to report, improve and contribute |

## When it does not work

| Message | Cause | Fix |
|---|---|---|
| `error: <file>: no such file` | the `--data` path is wrong, or relative to another folder | pass an absolute path, or `cd` to the repository first |
| `error: --dimension 'X' not found. Available: A, B, C` | the column name does not match, including case and `æøå` | use one of the printed names |
| `error: --measure 'X' is not numeric` | that column is text | pick a numeric column or convert it first |
| `error: input contained zero rows` | the file has a header and no rows | check that it opens as a table |
| `verify` stops because it has no browser | Chromium is not installed | run the two installation commands above |
| a dashboard is over the size limit | too many rows to carry in one file | pre-aggregate to the grain the dashboard shows |
| the link downloads instead of opening | `Content-Disposition: attachment`, by design | tell the reader to open the downloaded file |

Any part of this being unclear is a documentation bug. Report it in an issue rather than
working around it alone.
