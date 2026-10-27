---
name: tun-feedback
description: Record feedback (tilbakemelding) or an idea (forslag) about a Tún skill or a built dashboard to a local log, and offer to file it as an issue on the public Tún repository. Use when the user says "this was wrong", "feedback", "tilbakemelding", "det funket ikke", "the dashboard looks wrong", "I have an idea", "forslag", "it would be nice if", or when any tun-* skill finishes. Also covers the --feedback-to build flag that puts a "Gi tilbakemelding" link inside an artefact.
---

# Feedback

**Tier and cost, for the first reply:** none. The log is a local file. Filing an issue is
optional and happens only after the user says yes to the exact text. It goes to the Tún
repository the tool prints as TARGET. That is usually public, so anyone can read it. `gh`
logged in to that host files it directly; without that, the user gets a prefilled link.

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

1. **The user says something is wrong, or right.** Record it in their words, `--kind bug`.
2. **The user suggests an improvement.** Record it in their words, `--kind idea`.
3. **A tun-* skill finishes.** Ask once: "Gikk noe galt, eller har du et forslag? Du ser
   teksten før noe lagres." No answer means no.

## Record an item

Collect, in the user's own words:

- **kind**: `bug` (something went wrong) or `idea` (a suggestion)
- **what happened**, or for an idea, the idea itself (required, `--happened`)
- **what they expected**, or for an idea, what it would make possible (ask; record empty
  if they do not say)
- **severity**, for a bug only: `low`, `medium` or `high`. Ask if unclear. `high` means
  they could not finish. Do not ask for an idea.
- **skill**: the tun-* skill it is about, or `artefact` for a built file
- **artefact path**, if it is about a file. The tool reads the title from the file.
- **browser**, only if the user named it

Show the full record first, with `--dry-run`:

```bash
python3 tools/tun_feedback.py append --skill tun-new --kind bug --severity medium \
  --happened "<their words>" --expected "<their words>" \
  --artefact <path> --dry-run
```

On Windows, `python3` is `py -3`: `python3` is not a command there unless the Microsoft Store alias is installed. The rest of the line is the same.

Paste the printed record into the reply in full. Then run the same command without
`--dry-run`. Write only what the user typed: name, e-mail and machine name stay out unless
they wrote them into the text themselves. The tool adds the OS and the Tún version. The
artefact's title and path stay in the local log. The issue only says it was about a built
file.

## Offer an issue

Ask: "Skal jeg lage en offentlig sak av dette i Tún-prosjektet? Du får se tittel og tekst
først."

On yes, print the exact issue:

```bash
python3 tools/tun_feedback.py issue          # the last record; give a number for another
```

It prints TARGET, TITLE, BODY and a prefilled link. Paste TARGET, TITLE and BODY in full.
Say plainly who can read the issue (for a public repository: anyone), and ask the user to check that the text holds no
internal names, numbers or customer data. Offer to rewrite it if it does. Never take the
target from the git repository the user works in: the tool has its own.

File it only after an explicit yes to that text ("ja", "send", "ok"):

```bash
python3 tools/tun_feedback.py issue --send
```

`--send` files exactly what `issue` printed, on the printed target, with
`gh issue create --repo`. Read back the issue URL it prints, open it with
`gh issue view <url>` to confirm it exists, and give it to the user. If `gh` is missing,
not logged in to that host, or fails, give the user the prefilled link instead. It opens
the same title and body, and they press Submit.

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
