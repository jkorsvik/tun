# skills/

Two groups, and the split is the point.

```
skills/                 what this project produces (11 verb skills)
  tun-help/               orient, introduce Tún, and pick the right path
  tun-new/                build any of the 27 shapes (supporting recipes in shapes.md)
  tun-data/
  tun-verify/
  tun-publish/
  tun-host/
  tun-powerbi-escape/
  tun-process/
  tun-review/
  tun-for-communicators/
  tun-feedback/

skills/dev/             how the toolkit itself gets built (6 contributor skills)
  hotshot/                stack-agnostic round: understand, implement, verify, review, PR
  magnus-review/          adversarial correctness + architecture review
  writing-for-agents/     writing instructions an agent actually follows
  template-on-the-seam/   putting a template on the shared colour seam
  adding-an-artefact-kind/ end-to-end checklist for a new builder, template and suite
  refresh-artefacts/      pinned-clock rebuild of examples, test_i18n hashes and Explorer
```

`python3 setup.py --tool <auto|claude|agents|cursor|windsurf>` (`py -3` on Windows; bare
`python3 setup.py` for RAIWork) installs both groups as copies into the folder your AI tool
reads (`~/.agents/skills/`, `~/.claude/skills/`, `~/.cursor/skills/`,
`~/.codeium/windsurf/skills/` or `~/.raiwork/skills/`). Each installed copy carries
`.installed-by-tun` with `repo: <checkout>` so the skills can run `<repo>/tools/...` from
any folder on the machine. The `skills/` vs `skills/dev/` split is for the human reader,
not the loader.

## What an instruction file is

These are not programs. They are plain prose (`SKILL.md`) that the agent reads before it
works. The closest thing you have written before is a documented operating procedure, or a
runbook for the night shift: whoever follows it cannot ring you at three in the morning, so an
ambiguous sentence becomes a stopped job.

That is the whole mechanism, and it is why this is different from ordering a report. If an
agent words something badly or does something dumb, **edit the instruction** and re-run
`setup.py`. It is live the next time you ask.

Use `writing-for-agents` when you do. The failure mode is always the same: prose that reads
fine to a human who already knows the answer, and underdetermines the action for something that
does not.

---

## skills/ — the eleven project skills

Specific to this project. This repo is their home and they will change as it does.

| Skill | What it does |
|---|---|
| `tun-help` | Introduces Tún, lists the verbs, picks the path and states what the choice costs. |
| `tun-new` | Builds an artefact from a file across 27 shapes (`shapes.md` holds the specialised recipes). |
| `tun-data` | New extract, new numbers, existing artefact (including zero-tooling CSV drag-and-drop). |
| `tun-verify` | Opens it in a real browser, checks accessibility and self-containment, proves it renders. |
| `tun-publish` | Uploads it, confirms who can see the folder, drafts the announcement. |
| `tun-host` | Chooses static hosting or a separate backend for a functional app, then verifies the hosted release. |
| `tun-powerbi-escape` | Moves a report off Power BI, and answers the objections honestly. |
| `tun-process` | Draws a process as swimlanes, with the steps that should improve flagged. |
| `tun-review` | A reader who disagrees says which row and hands it back as one text block; `tools/read_review.py` finds the row and shows the file's number beside theirs. |
| `tun-for-communicators` | Explains technical vocabulary with communications analogies (`quick-prompt.md` for plain chat). |
| `tun-feedback` | Logs what went wrong or right locally, and files it as an issue after user approval. |

---

## skills/dev/ — the six for the work itself

**Deliberately agnostic, in three of the six.** `hotshot`, `magnus-review` and
`writing-for-agents` name no build tool, no test runner, no branch convention and no forge,
because the method is identical whether the thing being built is a dashboard, a batch job or a
payments API. Take those three to your next project unchanged; that is the test they are
written to pass. `template-on-the-seam`, `adding-an-artefact-kind` and `refresh-artefacts`
are the three repo-specific skills: they document how THIS repo's artefacts are built and
kept current, and they say so.

| Skill | The method, in one line |
|---|---|
| `hotshot` | The full round on one word: understand, implement, prove, get torn apart, cut, submit. |
| `magnus-review` | The reviewer whose job is to falsify your story, not confirm it. |
| `writing-for-agents` | How to write an instruction a machine will actually follow. |
| `template-on-the-seam` | Putting a template on the shared colour seam, and keeping it there. |
| `adding-an-artefact-kind` | A new kind end to end: builder, seam template, two languages, a suite that can fail, eight registration points. |
| `refresh-artefacts` | Pinned-clock rebuild of committed examples, `test_i18n.py` hashes and the showcase Explorer after a template or builder change. |

### hotshot

The round you have always done. What changed is that it happens on one instruction instead of
eight steps, and the reviewer never gets tired or polite.

It **discovers** rather than assumes: the verification gate comes from whatever this repo
documents (`AGENTS.md` section, `Makefile` target, `package.json` script, or failing all that,
what CI actually runs); the base branch from `origin/HEAD`; the commit style from `git log`;
the forge from what is installed. Hardcoding one project's tooling into a pipeline is how it
silently does the wrong thing in the next one.

Three rules in it are worth reading even if you never invoke it:

- **A passing gate is not a correct result.** A clean build log says the build succeeded, not
  that the output is right. If a human will look at the artefact, open the artefact.
- **Check the gate was capable of failing.** A validator that matched zero files reports
  success. That is worse than failing, because it manufactures assurance.
- **A measurement written down is a claim.** Change the code and the number in the doc goes
  stale, and someone will trust it.

Do not use it to fix one sentence. That is one line, not a round.

### magnus-review

Two lenses: correctness (try to break the author's story; every finding traced to a concrete
line or it does not count) and architecture (data structures over code, wrong coupling, names
that lie). `hotshot` calls it in a loop until it relents. You can also call it alone to stress
a decision.

It is written to be adversarial on purpose. A review that confirms what you already believe
has cost you time and bought nothing.

### writing-for-agents

The most relevant one in this repo, because the project skills above *are* documents written to a
machine. Same night-shift problem, one layer up.

---

## Vendored, and what that costs

The three in `dev/` also exist at user level (`~/.raiwork/skills/`) and are shared across
projects. The copies here will drift from those. That is an accepted trade: a checkout that
works on a fresh machine with nothing else installed beats a tidier one that does nothing.

`hotshot` here is a **rewrite**, not a copy. The original named another codebase's build tools,
branch conventions and container stack. The method transferred; none of those instructions did.
If you ever bring a skill in from elsewhere, expect the same job: keep the method, throw out
the stack.

`hotshot` also calls `simplify`, which ships with RAIWork itself and needs no copy here.

## Name collisions

If you already have a skill of the same name at user level, `setup.py` **leaves yours alone**
and tells you:

```
WARN hotshot  (dev)    you already have a skill with this name — left alone
```

It only ever replaces a copy it installed itself, marked with a dotfile it wrote. A project
install must not be able to destroy a global tool. This was a real bug here, found by it
deleting one.

## Not vendored on purpose

There are general skills for routing across a personal library, for stress-testing a decision
by argument, for naming things consistently, for root-causing a bug and for building a
throwaway to answer a design question. They are good, and they are **not** copied in.

`tun-help` already routes this project, and a second router pointing at skills that are
absent is worse than none. If you build up your own library later, those belong there, at user
level, shared across everything you work on. That is the right home for them.
