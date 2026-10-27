# Onboarding — from a spreadsheet to a shared dashboard

**Reader:** user — you want an artefact out of your own data and do not intend to change the toolkit.

**Who this is for:** anyone with a work laptop, Windows or macOS. No prior setup, no
developer toolchain, no admin approval. If you can open Excel and a browser, you can do
this.

Two routes, and you can stop after the first:

- **Part 1** builds a real dashboard from the command line in about five minutes, with no
  AI tool installed. Nothing about this project needs one — the dashboard is a file.
- **Part 2** adds the assistant, so the same job becomes one sentence.

**Done looks like this:**

- [ ] Python runs on your machine and says 3.9 or newer
- [ ] `python3 setup.py` (Windows: `py -3 setup.py`) prints `Everything the dashboard
      skills need is in place.`
- [ ] you have opened a dashboard built from your own data, from `file://`, in a browser
- [ ] it is in a SharePoint or OneDrive folder, and a colleague has opened it

---

## Windows: the four things that are different

Everything else in this document is identical on both systems. These are the only
differences, and every one of them is handled by the tools here rather than by you:

| On Windows | What to know |
|---|---|
| `python3` is `py -3` | `python3` is not a command on Windows unless the Microsoft Store alias is installed. Use `py -3` wherever this document shows `python3`. `setup.py` prints the spelling your machine has. |
| Skills are **copied**, not symlinked | Symlinks need Developer Mode. Without it `setup.py` copies the skill files, which works the same — but then re-run `setup.py` after someone updates a skill. It tells you when they are stale. |
| OneDrive lives elsewhere | `%OneDriveCommercial%` (usually `C:\Users\<you>\Eksempel AS Bank ASA\...`), not the macOS `~/Library/CloudStorage/...` path. `setup.py` finds it and prints it. |
| Paths use `\` | Every path in this document also works with `/` on Windows. Nothing here needs a shell script, and there are none in this repository. |

---

## Part 1 — five minutes, no AI tool

### Step 1. Python

macOS ships a usable Python 3; check it:

```bash
python3 --version
```

Windows, in PowerShell:

```powershell
py -3 --version
```

If that fails, install Python from [python.org](https://www.python.org/downloads/) and tick
"Add python.exe to PATH" in the installer, or run `winget install Python.Python.3.12`.
Anything 3.9 or newer is fine — the builders are stdlib only, so there is nothing to
install afterwards.

### Step 2. Get this repository

```bash
git clone https://example.com/tun.git \
  ~/dev/work/github_repos/tun
cd ~/dev/work/github_repos/tun
```

No git yet? `winget install Git.Git` on Windows, `xcode-select --install` on macOS.

### Step 3. Check the machine and install the skills

One command does both: it copies the skills into your AI tool if you have one, then checks
every tool, then builds and verifies a test dashboard to prove the chain works.

```bash
python3 setup.py
```

Windows: `py -3 setup.py`. If either fails, the last block is a list of exact commands to
fix it; `docs/05-toolchain.md` explains why each tool is there.

Two of those lines matter:

- `OK ms365 authenticated` — the connection to SharePoint and OneDrive. Without it you can
  still build, but you cannot publish from the assistant.
- `OK build produced a dashboard` followed by `OK verify it renders and is interactive` —
  the whole pipeline works on your machine, including a headless browser.

### Step 4. Build the example, then look at it

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

Then open `/tmp/salg.html` in your browser — double-click it, or `start` it on Windows
(`start %TEMP%\salg.html`). That is the deliverable: one file, no server, no licence, and
it keeps working on a plane.

**Look at it, do not trust the build log.** A dashboard that printed no error can still
have overlapping labels or a number that is wrong by a factor of a thousand. Verifying is
the next step and it is not optional.

### Step 5. Prove it renders

```bash
python3 tools/verify_dashboard.py /tmp/salg.html
```

Expected: `✓ PASS`, plus a screenshot path. Open the screenshot. If the verify tool complains
it has no browser, it prints the two commands to install one; it refuses to report success
without one, on purpose.

From here, everything else is the same three verbs: **build**, **verify**, **share** with
your own file as `--data`. Column names come from your file; if one is wrong the builder
lists the ones it found:

```
error: --dimension 'Nope' not found. Available: Maaned, Region, Produkt, Kanal, Antall, Belop
```

Every refusal is one line, starts with `error:`, and exits 2, so a script you wrap around it
can tell "refused" from "crashed".

---

## Part 2 — the same job, by asking

Install the assistant once, and the rest of this document becomes a conversation.

**macOS** — the team's installer:

```bash
git clone eksempel@example.com:vedlikeholderen-Ryen-vedlikeholderen/dotfiles.git ~/dev/personal/dotfiles
cd ~/dev/personal/dotfiles && ./install.sh
```

Pick the **Developer** profile — the lowest one that includes the assistant ("Minimal"
skips it). Safe to re-run.

**Windows** — the assistant installs on Windows, but the team's `install.sh` is macOS-only,
so the Windows route is the app itself plus this repository's skills:

1. install the assistant from the internal distribution point your team uses
2. `py -3 setup.py --tool raiwork` in this repository, which puts the skills where it reads
   them
3. `py -3 setup.py --check` to confirm

What is verified: the skills install path, `setup.py` on both systems, and every build and
verify command above. What is **not** verified: the assistant's Windows installer, which is
a separate artefact this repository does not carry. If it fights you, that is a bug worth
reporting, not something you are doing wrong.

Then open the assistant, point it at this repository as its working folder, and type:

> Build me a dashboard from `examples/01-hello-dashboard/salgsdata.csv` — the amounts by
> product, the trend over the months, filterable by region.

It asks the one question that changes the answer (do different people need to see different
rows? say no here), reads the file, tells you which columns it found, builds the file, opens
it in a real browser, and shows you the picture.

### What to ask for

You do not need to know skill names. Say what you want:

| You want to… | Say something like… |
|---|---|
| start something new | *"make me a dashboard from this file"* |
| the list, not a chart | *"give me a searchable list of the open cases"* |
| a process diagram | *"draw how a request flows between these three teams"* |
| know if this is the right approach | *"can this replace our Power BI report?"* |
| update stale numbers | *"refresh the sales dashboard with the new export"* |
| check before sending | *"is this dashboard safe to share?"* |
| share it | *"publish this to the team folder"* |

Not sure? *"what can you do with dashboards?"* routes you and states what each option costs
in approvals.

---

## Part 3 — publish it

> Put it in \<your team's SharePoint folder\> and give me a link I can share.

The assistant confirms which folder, tells you **who will be able to see it**, uploads it,
and drafts the message. It will not send anything without you saying so.

If you publish by hand instead: put the file in a synced OneDrive or SharePoint folder and
share the file the way you share a document. Same result.

### The one quirk to explain to readers

When someone clicks the link, SharePoint **downloads** the file instead of rendering it in
the page. That is a Microsoft security rule, it applies to every `.html` file in every
document library, and we route around it rather than defeat it. So describe it that way:

> "Klikk lenken, filen åpnes i nettleseren. Den fungerer også offline etterpå."

Same number of clicks as opening a PDF, and it is the reason the dashboard keeps working on
a train.

---

## The one rule that actually matters

> **If different people who open the dashboard must see different rows of data, this
> approach cannot be used.**

The data lives inside the file. Anyone who can open the file can read all of it, including
rows they should not see. A filter in the browser hides nothing — the rows are still in the
file — so there is no safe workaround, and the skills refuse rather than pretend.

The fix is a split, not a filter: same dashboard shell, one data file per audience, each in
a folder only that audience can open. The split happens **before** anything is written.
Everything else — where everyone sees the same numbers — is fair game, and that is most
reporting.

On freshness: use **paired mode** and the dashboard is a small file next to a `data.js`.
Replace the data file and everyone sees new numbers the next time they open it, with no
rebuild and no republish.

`docs/00-vision.md` has the honest comparison, including where Power BI is the right answer.

---

## Where things are

| Path | What it is |
|---|---|
| `docs/00-vision.md` | why this exists, and the honest Power BI boundary |
| `docs/01-tenant-constraints.md` | **what SharePoint actually does** — measured, not guessed |
| `docs/02-architecture.md` | the three delivery tiers and what each costs in approvals |
| `docs/03-skill-tree.md` | the skills, how they fit, what is built and what is planned |
| `docs/05-toolchain.md` | every tool needed and why |
| `docs/09-usability-and-navigation-principles.md` | what a reader must be able to do |
| `docs/30-glossary.md` | the vocabulary, for anyone who is not a developer |
| `skills/` | the skills — plain English, editable without a build step |
| `examples/` | working artefacts with sample data |
| `ROADMAP.md` | what is next, and what is blocked on a question |

Read `docs/01-tenant-constraints.md` at some point. It is the document that turns "I think
this works" into "I know exactly what works and why".

---

## When it does not work

Every message below came from a real run. The first line is what you see.

| Message | Cause | Fix |
|---|---|---|
| `error: <file>: no such file` | the `--data` path is wrong, or relative to another folder | pass an absolute path, or `cd` to the repository first |
| `error: --dimension 'X' not found. Available: A, B, C` | the column name does not match the file, including case and `æøå` | use one of the names this line prints |
| `error: --measure 'X' is not numeric` | that column is text; a chart of it would be empty | pick a numeric column, or convert it first |
| `error: input contained zero rows` | the file has a header and nothing else, or the delimiter was not detected | check the file opens as a table in a text editor |
| `verify` stops because it has no browser | the headless browser is not installed | run the two commands it prints |
| a dashboard is over the size limit | too many rows to carry in one file | pre-aggregate to the grain the dashboard shows, then rebuild |
| the link downloads instead of opening | `Content-Disposition: attachment`, by design | nothing to fix; describe it to readers as a download that opens |

The last one is not a bug and there is no workaround. It is the security control the whole
architecture is built around.

---

## Your first real contribution

The skills are **plain English files**, not code. If something is done in a way you do not
like — the wrong chart, the wrong wording, a question you would always ask and it does not —
open the relevant `skills/*/SKILL.md` and change the instruction. Then re-run `setup.py`.
That is the whole mechanism, and no build step stands between the edit and the behaviour.

The highest-value thing to add early is `docs/use-cases.md`: the real reports in your area
that could move to this, **and the ones that cannot, with the reason.** The refusal list is
the more valuable half — it draws the boundary and stops the same argument every quarter.

Any part of this being unclear is a bug in the guide, not in you.
