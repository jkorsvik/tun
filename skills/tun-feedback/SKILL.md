---
name: tun-feedback
description: Record feedback (tilbakemelding) about a Tún skill or a built dashboard to a local log, and offer to file it as an issue on the project's forge. Use when the user says "this was wrong", "feedback", "tilbakemelding", "det funket ikke", "the dashboard looks wrong", or when any tun-* skill finishes. Also covers the --feedback-to build flag that puts a "Gi tilbakemelding" link inside an artefact.
---

# Feedback

**Tier and cost, for the first reply:** none. The log is a local file. Filing an issue is
optional, needs `gh`, and happens only after the user says yes to the exact text.

Two paths, one per audience:

| Who | Path |
|---|---|
| Someone using the skills | this skill: local log, then an issue if they want one |
| Someone reading a built file | the "Gi tilbakemelding" link, if it was built with `--feedback-to` |

## Where the tool is

`tools/tun_feedback.py` in the Tún checkout. The installed copy of this skill has a
`.installed-by-tun` file whose `source:` line names
`<checkout>/skills/tun-feedback`; the checkout is two levels up. Run every command below
from the checkout.

## When it runs

1. **The user says something is wrong, or right.** Record it in their words.
2. **A tun-* skill finishes.** Ask once: "Vil du gi en tilbakemelding på dette? Du ser
   teksten før noe lagres." No answer means no.

## Record an item

Collect, in the user's own words:

- **what happened** (required)
- **what they expected** (ask; record empty if they do not say)
- **severity**: `low`, `medium` or `high`. Ask if unclear. `high` means they could not
  finish.
- **skill**: the tun-* skill it is about, or `artefact` for a built file
- **artefact path**, if it is about a file. The tool reads the title from the file.
- **browser**, only if the user named it

Show the full record first, with `--dry-run`:

```bash
python3 tools/tun_feedback.py append --skill tun-new --severity medium \
  --happened "<their words>" --expected "<their words>" \
  --artefact <path> --dry-run
```

Paste the printed record into the reply in full. Then run the same command without
`--dry-run`. Write only what the user typed: name, e-mail and machine name stay out unless
they wrote them into the text themselves. The tool adds the OS, and the Tún version from
`git describe`.

## Offer an issue

Ask: "Skal jeg lage en sak av dette i prosjektet? Du får se tittel og tekst først."

On yes, print the exact issue:

```bash
python3 tools/tun_feedback.py issue          # the last record; give a number for another
git remote get-url origin                    # where it will be filed
```

Paste the TITLE and BODY in full and say which forge and repository will get it. File it
only after an explicit yes to that text ("ja", "send", "ok"):

```bash
python3 tools/tun_feedback.py issue --send
```

`--send` files exactly what `issue` printed, with `gh issue create` in the checkout, so `gh`
picks the forge from the `origin` remote. Read back the issue URL it prints and give it to
the user. If `gh` is missing or not logged in, give them the title and body to paste into a
new issue by hand.

## Feedback from inside a file

`tools/build_dashboard.py` and `tools/build_cube_dashboard.py` take
`--feedback-to <address-or-issue-url>`:

- an e-mail address or `mailto:` link opens a prefilled e-mail
- an `https://` "new issue" URL opens a prefilled issue (GitHub, Gitea and Forgejo style
  `title`/`body`; GitLab when the path holds `/-/issues`)

The link holds a snapshot: artefact title, build time and source, protocol (`file` or
`https`), where it is shown (local file, SharePoint, OneDrive, framed), user agent,
viewport, whether JavaScript ran, and how many script errors were caught. With JavaScript
off it still works, with the static fields only. The reader sees the whole message in their
mail client or browser before anything is sent.

Ask the requester which address or issue page should get reader feedback. There is no
default, and every reader of the file can see the target. Without the flag, the built file
is unchanged.
