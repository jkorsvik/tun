# 49. Was the plan kept, and by how much did it slip

A timeline (35) shows when things happen. This shows whether the plan held: for every task, one
bar for what was planned and one for what happened, on the same date axis, with the difference
printed as a signed number of days.

The trap is quieter than a chart's. It is that a plan compared against nothing still *looks*
like a plan: a bar drawn from the planned start to today reads as progress, and a task that never
started drawn as a zero-length bar reads as finished on time.

```bash
python3 examples/49-gantt/generate_data.py

python3 tools/build_gantt.py \
  --data examples/49-gantt/fremdrift.csv \
  --task Tiltak --start Planstart --end Planferdig \
  --actual-start Faktisk-start --actual-end Faktisk-ferdig \
  --today 2026-10-26 \
  --title "Fremdrift per tiltak" \
  --source "Syntetisk eksempeldata (fremdrift.csv)" \
  --requested-by "Prosjektkontoret" \
  --out examples/49-gantt/fremdrift.html
```

Then verify it the way a recipient opens it:

```bash
uv run --extra verify python3 tests/test_gantt.py
uv run --extra verify python3 tools/verify_viewports.py examples/49-gantt/fremdrift.html
uv run --extra verify python3 tools/verify_a11y.py examples/49-gantt/fremdrift.html
```

## The rules it carries

* **the difference is a signed number, never a colour.** "Fourteen days late" is the answer; a red
  bar is a mood. Every finished task carries its number beside the bar and in the table, with a
  real minus for early.
* **an unfinished task is a word.** A task with no actual start is "not started"; a task with a
  start and no finish is "running". They are two different words because they are two different
  facts, and neither is drawn as a bar.
* **one scale for both bars.** The comparison is the whole point, so a second axis would let a
  three-day slip look like three weeks. The suite derives pixels-per-day from the plan bars and
  holds the actual bars to the same number.
* **ISO dates only, refused by name.** If the builder also accepted `03.04`, it would have to
  guess whether the source meant March or April, and a plan one month out is worse than one that
  does not build.
* **an end before its start is refused**, for the plan and for the actual bar.
* **the today marker is information, not a verdict**, drawn as a muted dashed rule above its own
  label line so it cannot print through a month tick.
* **the row order is stated**: planned start, ties in source order.

## Refusals

An end before its start (named, with the file and line), a `dd.mm` date, an actual end without an
actual start, only one of the two actual columns, and more than 28 tasks ("the names collide;
keep the milestones and use the timeline for the rest").

## What the suite measures

`tests/test_gantt.py` is 37 checks and three mutations. From the extract itself it re-derives: one
plan bar per task and one actual bar per *started* task, pixels-per-day identical across the plan
bars and then reused to predict every actual bar's position and width, the printed difference as
`actual finish − planned finish` with its sign, all five state words, every cell of the table, and
the committed file rebuilt byte for byte from a pinned clock.

In **Chromium at two widths** it measures that no two task names overlap, that the today marker
does not print through a month label, and that every label is at least 14 px. That check found a
real collision on the first run: the marker cleared the tick row by one pixel.

Three mutations: the difference printed without its sign, an unstarted task given a bar drawn from
its planned start ("assume it started on plan" — the plausible wrong version), and the actual bar
on a 1.25× wider scale. Each trips exactly one check.
