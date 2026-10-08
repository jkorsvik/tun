# skills/

Two groups, and the split is the point.

```
skills/                 what this project produces
  tun-help/         you use these to make and ship dashboards
  tun-new/
  tun-data/
  tun-verify/
  tun-publish/
  tun-powerbi-escape/
  tun-process/

skills/dev/             how any project gets built
  hotshot/                these have nothing to do with dashboards
  magnus-review/          and everything to do with the round of work
  writing-for-agents/
```

`python3 setup.py` installs both groups. RAIWork looks one level deep, so they end up flat in
`~/.raiwork/skills/`; the directory split is for the reader, not the loader.

## What an instruction file is

These are not programs. They are plain prose (`SKILL.md`) that the agent reads before it
works. The closest thing you have written before is a documented operating procedure, or a
runbook for the night shift: whoever follows it cannot ring you at three in the morning, so an
ambiguous sentence becomes a stopped job.

That is the whole mechanism, and it is why this is different from ordering a report. If RAIWork
words something badly or does something dumb, **edit the instruction.** It is live the next
time you ask.

Use `writing-for-agents` when you do. The failure mode is always the same: prose that reads
fine to a human who already knows the answer, and underdetermines the action for something that
does not.

---

## skills/ — the six for dashboards

Specific to this project. This repo is their home and they will change as it does.

| Skill | What it does |
|---|---|
| `tun-help` | Router. Describe what you want; it picks the path and says what the choice costs. |
| `tun-new` | Builds a dashboard from a file. Row mode, or cube mode for millions of rows. |
| `tun-data` | New extract, new numbers, existing dashboard. |
| `tun-verify` | Opens it in a real browser, screenshots it, proves it renders. |
| `tun-publish` | Uploads it, confirms who can see it, drafts the announcement. |
| `tun-powerbi-escape` | Moves a report off Power BI, and answers the objections honestly. |
| `tun-process` | Draws a process as swimlanes, with the steps that should improve flagged. |
| `tun-feedback` | Logs what went wrong or right, and files it as an issue if you want. |

---

## skills/dev/ — the three for the work itself

**Deliberately agnostic.** They name no build tool, no test runner, no branch convention and
no forge, because the method is identical whether the thing being built is a dashboard, a
batch job or a payments API. Take them to your next project unchanged; that is the test they
are written to pass.

| Skill | The method, in one line |
|---|---|
| `hotshot` | The full round on one word: understand, implement, prove, get torn apart, cut, submit. |
| `magnus-review` | The reviewer whose job is to falsify your story, not confirm it. |
| `writing-for-agents` | How to write an instruction a machine will actually follow. |

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

The most relevant one in this repo, because the six skills above *are* documents written to a
machine. Same night-shift problem, one layer up.

---

## Vendored, and what that costs

The three in `dev/` also exist at user level (`~/.raiwork/skills/`) and are shared across
projects. The copies here will drift from those. That is an accepted trade: a checkout that
works on a fresh machine with nothing else installed beats a tidier one that does nothing.

If you ever bring a skill in from elsewhere, expect to rewrite it: keep the method, throw
out the stack.

`hotshot` also calls `simplify`, which ships with RAIWork itself and needs no copy here.

## Name collisions

If you already have a skill of the same name at user level, `setup.py` **leaves yours alone**
and tells you:

```
WARN hotshot  (dev)    you already have a skill with this name — left alone
```

It only ever replaces a copy it installed itself, marked with a dotfile it wrote. A project
install must not be able to destroy a global tool.

## Not vendored on purpose

There are general skills for routing across a personal library, for stress-testing a decision
by argument, for naming things consistently, for root-causing a bug and for building a
throwaway to answer a design question. They are good, and they are **not** copied in.

`tun-help` already routes this project, and a second router pointing at skills that are
absent is worse than none. If you build up your own library later, those belong there, at user
level, shared across everything you work on. That is the right home for them.
