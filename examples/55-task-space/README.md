# 55. A task space: one declared workflow in three dimensions

A spatial, rotatable view of a declared sequence. Select a step to read its purpose. This example
exists to show when raw WebGL adds a useful way to explore a relationship without adding a library,
a server or a rendering dependency. It is a view, not a process engine or a simulation.

The input is a small CSV: step id, title, description and X/Y/Z. Row order is the sequence.
Coordinates place the drawing; they do not measure value, duration or progress. The same rows also
produce a static SVG and the complete table, so WebGL is never the only way to read the facts.

```bash
python3 examples/55-task-space/generate_data.py

python3 tools/build_task_space.py \
  --data examples/55-task-space/trinn.csv \
  --step Step --label Title --description Description --x X --y Y --z Z \
  --title "Fra spørsmål til leser" \
  --source "Syntetisk arbeidsflyt (trinn.csv)" \
  --requested-by "Prosjekteier" \
  --lang nb \
  --out examples/55-task-space/arbeidsflyt.html
```

For English, use `--lang en`, an English `--title` and `--source`, and an output outside this pinned
example. A column named `Title` or `Description` can be replaced by `Title_nb` / `Title_en` and
`Description_nb` / `Description_en`, as in this CSV.

Then verify it:

```bash
uv run --extra verify python3 tests/test_task_space.py
uv run --extra verify python3 tools/verify_viewports.py examples/55-task-space/arbeidsflyt.html
uv run --extra verify python3 tools/verify_a11y.py examples/55-task-space/arbeidsflyt.html
uv run --extra verify python3 tools/verify_a11y.py examples/55-task-space/arbeidsflyt.html --dark
```

## The rules it carries

- **the row order is the sequence.** The 3D distance between two points never claims chronology.
- **coordinates are display choices, not measurements.** They do not represent value or progress.
- **no automatic movement.** Drag to rotate; select a step with mouse, touch or keyboard.
- **one source, three views.** Raw WebGL, a static SVG and the full table come from the same rows.
- **no runtime dependency.** No library, framework, font, texture, network request or build tool is
  needed by the reader.

## Refusals

Fewer than two or more than twelve steps, duplicate step ids, duplicate coordinates, missing text,
non-numeric coordinates, and any coordinate outside the declared `[-3, 3]` display volume. For
branches, decisions, ownership or a larger process, use the process diagram instead.
