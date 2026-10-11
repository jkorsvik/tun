# Way of Working

Short on purpose. These are the habits that keep this project simple, portable and
trustworthy — plus the two power tools worth knowing.

## The rules

1. **Verify, don't assume.** If it's checkable, check it. Read the live API response, not
   the doc describing it. Every constraint in this repo was measured; twice the
   documentation was wrong in a way that would have changed the design.

2. **Look at the artefact.** A clean build is not evidence. Open the dashboard, look at
   the screenshot, check one number against the source. A dashboard that renders
   beautifully and shows wrong numbers is worse than one that fails loudly.

3. **Show before sending.** Anything going to a human — an email, a Teams post, a link
   announcement, an issue comment — gets shown in full and approved *before* it's sent.
   No exceptions.

4. **Small, reversible steps.** Local and reversible (edit a file, run a test) — just do
   it. Destructive or outward-visible (delete, force push, notify someone) — ask first.

5. **Test locally, then publish.** Build and verify on your own machine before anything
   reaches a shared folder. The published copy is the one colleagues trust.

6. **Say when you don't know.** "Unverified" is a complete and useful answer. Guessing
   confidently is the expensive failure.

7. **Be concise.** State the answer, then the reasoning. Don't repeat a reminder that's
   already landed.

   The one exception is jargon, when the person on the other side is not a developer. Then:

   - explain a git or GitHub term with a short analogy **the first time** it comes up in a
     conversation (branch, commit, pull request, merge, fork, clone), and let them say
     "skip the explanation" once they know it;
   - flag a term that assumes experience (rebase, "CI fails", squash) and give its meaning
     **before** asking for a yes or a no, so the person knows what they are agreeing to;
   - keep the explanations in one glossary in the repository, so they are written once
     (not written yet; see the roadmap).

   Concise means no filler. It does not mean assuming a vocabulary the reader never had.

8. **Nothing reaches `main` except through a pull request.** No direct commits on `main`,
   no `git push origin HEAD:main`, no "it's just a typo fix". A pull request is how a
   change becomes reviewable; a direct push skips the only review this repo has.

   This is a rule because the failure is silent. A `git add` on the wrong branch, or in a
   shared clone, can sweep unrelated files onto `main`, and nobody notices until after the
   merge.

   Enforced locally by two hooks, both enabled by `python3 setup.py --hooks`:

   | hook | refuses |
   |---|---|
   | `tools/hooks/pre-commit` | a commit made while on `main` |
   | `tools/hooks/pre-push` | any push whose destination is `refs/heads/main`, including `HEAD:main`, `--force`, and deletion |

   Both discover the integration branch from `origin/HEAD` rather than hardcoding `main`,
   so they keep working after a rename or in a fork.

   Two honest limits. `--no-verify` bypasses both, and a hook only protects a clone that
   ran `setup.py --hooks`; a fresh clone has no protection at all until it does.
   **Branch protection on the forge is the real control**, because it applies to every
   clone and to the web UI. Check whether `main` is protected on your forge; if it is not,
   the hooks are the only thing there is.

## Tooling preferences

- **Python → `uv`. JS → `bun`. Never `pip`, never `npm`.** Not a preference — a rule.
- **Public registries (PyPI, npm) are the default package source.** No internal mirror
  is assumed.
- The Tier 1 path needs neither tool — `tools/` is stdlib-only on purpose. A
  prerequisite is a failure on the main path.

## Two gates: the pre-commit hook before the commit, CI on every pull request

`.github/workflows/gates.yml` runs every gate on GitHub-hosted runners for each pull
request, including every documented example check in Chromium, Firefox and WebKit. Its
job carries `if: github.server_url == 'https://github.com'`, so on a host without hosted
runners it shows as skipped, never as green, and never waits for a runner. A workflow that
never executes but reports success would be worse than none, because it looks like a gate.
Where runners may be disabled, probe that rather than assume it: a run that no runner
picks up produces zero steps and no logs, and it still shows up in the run list.

CI sees a mistake only after the push. The hook stops it before the commit:

```
python3 setup.py --hooks     # once per clone — sets core.hooksPath to tools/hooks
python3 tools/check_tree.py  # the same gates, by hand, any time
```

`tools/hooks/pre-commit` runs the text-level gates over every tracked `.html`, the
real-and-personal-data gate over every tracked text file, plus the gate unit tests, plus —
only when their inputs are staged — the verify-tool and skill-installer suites.
`core.hooksPath` keeps the hooks tracked in the repo, so a pull updates them and there is no
copy in `.git/hooks` to go stale.

Two of these are about data rather than layout. Real cases stay local and never enter
git; only method, scripts, templates and tests on synthetic data belong here.

```
python3 tools/check_no_real_data.py   # redacted detail for the data gate
python3 tools/scan_history.py         # the pre-publication scan: PII, internal refs, secrets
```

Two consequences worth saying out loud:

- **The hook protects only clones that installed it.** A green commit is evidence about
  that machine, not about the repo. `python3 setup.py --check` reports whether it is on.
- **`--no-verify` has nothing behind it.** On a repo with CI, bypassing a hook means the
  server still checks. Here it means nothing checks.

If a gate ever needs to run server-side, the route is an in-network runner, not a public
hosted runner such as `ubuntu-latest`.

## `hotshot` — the full pipeline in one word

For a real change to the tooling — the template, `tools/`, `setup.py` — say **hotshot**:

> "Use hotshot to add a stacked bar chart option to the template."

Saying it by name is explicit permission to run the whole loop without stopping to ask at
each step:

```
implement → verify → adversarial review (fix, re-review until clean)
          → simplify → commit → push to a new branch → open a PR
```

You get a PR to look at, not a pile of questions. It stays on its own branch — never
straight onto `main` — so nothing lands until you've read it.

**When not to bother:** editing prose in `skills/*/SKILL.md`. That's a one-line change to
an instruction; it doesn't need a pipeline. Just change it.

## The three general skills in `skills/dev/`

Not about dashboards. About how the work gets done, which is the same regardless of what is
being built. `python3 setup.py` installs them; `skills/README.md` covers them properly.

| Skill | Use it when |
|---|---|
| **`writing-for-agents`** | Editing a `SKILL.md` or `AGENTS.md`. **The most relevant one here**, because the skills in this repo *are* agent-facing documents, and writing them well is the core contribution. |
| **`hotshot`** | A real change to the tools, template or docs. One word instead of eight steps: understand, implement, verify, get reviewed adversarially, simplify, branch, PR. Not for a one-line wording fix. |
| **`magnus-review`** | You want a change or a decision attacked rather than approved. `hotshot` calls it in a loop; you can call it alone. |

They are written to be **stack-agnostic** and are worth taking to your next project unchanged.
`hotshot` discovers this repo's verification gate from the `## Verification gate` section of
`AGENTS.md` rather than hardcoding it, which is why it keeps working when the gate changes.

Other general-purpose skills exist for routing, arguing a decision, naming things, root-causing
and prototyping. They are deliberately **not** vendored here; `skills/README.md` says why, and
where they do belong.

## How feedback flows

Two paths, one per audience. Neither sends anything without the sender seeing it first.

**A reader of a built file.** A dashboard built with `--feedback-to <address-or-issue-url>`
has a "Gi tilbakemelding" link. It opens a prefilled e-mail, or a prefilled new issue, with a
snapshot attached: artefact title, build time, source, protocol, where it is shown, browser,
window size, whether JavaScript ran, and how many script errors were caught. It works from
`file://` with no network, and with JavaScript off it still opens, with the static fields
only. The reader edits and sends it from their own mail client or browser. The person or
team behind the address reads it, which is normally whoever asked for the dashboard. There
is no default target: a file without the flag has no link.

**Someone using the skills.** `tun-feedback` writes one JSON line per item to
`~/.raiwork/tun-feedback/feedback.jsonl` on their own machine, after showing the record. That
log is private; nobody else reads it. If they want, the skill turns an item into an issue on
this project's forge, shows the exact title and body, and files it with `gh` only after a
yes. The project maintainers read and triage those issues like any other.

## What "good" looks like

One file. Opens for anyone who can open the folder. Numbers traceable to a source. No
licence, no workspace, no build step, no admin ticket. If a change makes any of those less
true, it's the wrong change.
