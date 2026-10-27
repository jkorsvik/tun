---
name: tun-review
description: Close the loop on a built Tún artefact, so a reader who disagrees with a number can say which row and hand it back. Use when someone says "the numbers look wrong", "tallet stemmer ikke", "I got comments back on the dashboard", "here is feedback on the file", "hvordan får jeg tilbakemelding", "can a reader comment on this", or after sending out a dashboard and the recipient replies with a screenshot. Also covers the --annotate build flag and tools/read_review.py, which turns one pasted text block into a report.
---

# Review

**Tier and cost, for the first reply:** none. Nothing is uploaded, nothing leaves the
machine. The reader copies one block of text into whatever they already use to talk to you,
and a script on your side reads it. No server, no account, no licence.

There are two directions, and the skill does whichever the situation asks for.

| Situation | Direction |
|---|---|
| Someone replies "dette tallet er feil", with or without a screenshot | **read** a block (Path B), and offer `--annotate` so the next round is precise |
| You are about to send a file out and expect questions | **build** it with `--annotate` (Path A) |
| You have a `TUN-REVIEW 1` block in a mail, a chat or an issue | **read** it (Path B) |

## Where the tools are

In the Tún checkout. The installed copy of this skill has a `.installed-by-tun` file whose
`source:` line names `<checkout>/skills/tun-review`; the checkout is two levels up. Run
every command below from the checkout.

- `tools/build_dashboard.py --annotate` adds the layer to the rows dashboard.
- `tools/read_review.py` reads a block back and writes the report.
- `docs/31-review-roundtrip.md` is the reasoning, including what the layer does not do.

The commands below are written `python3`. On Windows the interpreter is `py -3`, and
nothing else changes: `py -3 tools/read_review.py saksbehandling.html svar.txt`.

## Path A: build it so a reader can comment

Add `--annotate` to the same build command the file was made with:

```bash
python3 tools/build_dashboard.py \
  --data saksbehandling.csv --title "Saksbehandling: kostnad per sak" \
  --dimension Sakstype --measure Kostnad --time Maaned --filters Enhet,Sakstype,Kanal \
  --source "Saksbehandling 2026" --requested-by "Enhetsleder" \
  --annotate \
  --out saksbehandling.html
```

Then verify it like any other artefact (`tun-verify`). The layer is off unless the flag is
passed, so a file built without it keeps its old bytes exactly.

Tell the reader one sentence, because the button is at the foot of the page: *"Nederst i
filen er det en knapp, **Kommenter**. Trykk på den, klikk raden du vil si noe om, og kopier
blokken du får inn i svaret til meg."*

## Path B: read what came back

Save the reply as a text file, or pipe it straight from the clipboard, and point the tool at
the artefact the reader had:

```bash
pbpaste | python3 tools/read_review.py saksbehandling.html -
python3 tools/read_review.py saksbehandling.html svar.txt --out svar.md
```

It reads the data out of the artefact itself, so the source file and the connection are not
needed. For each comment it reports one of:

| Outcome | What it means |
|---|---|
| `same` | the row exists and the file holds the figure the reader saw |
| `**block says X**` | the row exists; the reader's figure differs from the file's. Show both and ask which is right. Never overwrite either number yourself. |
| `**not found**` | no row in this file has those cells. The reader may have an older file, or typed a cell wrong. Ask for the file they opened before redrawing anything. |
| headed with **not the same build** | the block names a different build stamp. Place the comments against the build they name before acting. |

Present the result in the user's language. The report file is English because it is a tool
output, not a document for the reader.

## What it will not do

- **It cannot decide who is right.** The file holds one figure, the reader holds another.
  Only a person knows whether the invoice or the extract is wrong. Report both.
- **It does not edit the data.** If the file should change, that is `tun-data`, with the
  corrected source. A comment is not a correction.
- **It stores nothing.** No comment is kept anywhere by this skill. If the team wants a
  trail, the block belongs in the issue tracker, and that is the user's call.
- **The rows dashboard, the register and the comparison have the layer.** The cube,
  timeline and slide-deck builders do not: offer this for the three that do, and say plainly
  that the others would need the reader to describe the row in words.
- **On a comparison, a key can be missing from one side.** `--annotate` on
  `build_comparison.py` carries `status: gone` or `status: added` in the block, so the report
  says why a figure is empty instead of calling the row wrong. A comment there is about the
  key: the row is in the file, marked, and the other side's number does not exist.
- **A register comment is about a record, not a figure.** There the block carries `cells:`
  with the record's own numbers, and the report prints them beside the comment. Do not
  reduce it to one number to make it look like a dashboard.
