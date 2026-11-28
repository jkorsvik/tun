# Contributing

Thanks for looking. You can help without being a framework developer:

- **Bring a real task.** [Open an issue](https://github.com/jkorsvik/tun/issues) about a report
  that takes too long, a reader who got stuck, or a result you did not understand.
- **Improve a recipe.** The skills in `skills/*/SKILL.md` are editable Markdown. Clearer
  wording and better questions are product changes.
- **Add an example or a check.** A small synthetic dataset, a useful artefact or a failing
  test is a good first pull request.

For your first change, clone the repository, create a branch, make one focused edit and run
`python3 tools/check_all.py --fast` (`py -3` on Windows). Open a draft pull request if you
want early feedback.

Before changing code, read [`AGENTS.md`](AGENTS.md) and [`docs/adr/README.md`](docs/adr/README.md).
They hold the rules that do not bend and the recorded architecture decisions;
[`docs/06-way-of-working.md`](docs/06-way-of-working.md) holds the habits behind them.

By taking part you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). Report security
problems as described in [SECURITY.md](SECURITY.md), not in a public issue.

## Where to start

Open an issue in this repository before a large change.

The skills are prose, not code. If an agent does something the wrong way, the fix is
usually a sentence in `skills/*/SKILL.md` (read [`skills/dev/writing-for-agents/SKILL.md`](skills/dev/writing-for-agents/SKILL.md)
when editing one). Adding a new artefact shape follows the eight-point checklist in
[`skills/dev/adding-an-artefact-kind/SKILL.md`](skills/dev/adding-an-artefact-kind/SKILL.md).

## Set up

Nothing to install for the main path. `tools/` is stdlib-only Python and must stay that
way, because the primary user is on Windows with no toolchain.

```bash
python3 setup.py --hooks        # once per clone: turns on the pre-commit gate
python3 setup.py --check        # reports what is present and what is missing
python3 setup.py --tool auto    # installs Tún + dev skills for your AI tool
```

For the browser checks you need Playwright. Python goes through `uv` and JavaScript
through `bun`; do not use `pip` or `npm`.

```bash
uv sync --extra verify && uv run playwright install chromium firefox webkit
```

## The verification gate

Before you say a change works, rebuild the example and verify it. The full command is in
the "Verification gate" section of [`AGENTS.md`](AGENTS.md). Shortened:

```bash
python3 tools/build_dashboard.py \
  --data examples/01-hello-dashboard/salgsdata.csv \
  --title "Salg per region og produkt 2026" \
  --dimension Produkt --measure Belop --time Maaned \
  --filters Region,Produkt,Kanal \
  --source "Eksempeldata (syntetisk), salgsdata.csv" \
  --requested-by "Prosjekteier" \
  --out work/demo.html

uv run --extra verify python tools/verify_dashboard.py work/demo.html --engines all
```

A clean build is not evidence. Open the file and look at the screenshot.

If you changed a template, shared token or builder, follow
[`skills/dev/refresh-artefacts/SKILL.md`](skills/dev/refresh-artefacts/SKILL.md) to rebuild
affected committed examples on the pinned clock (`TZ=UTC SOURCE_DATE_EPOCH=1792836000`),
re-pin `tests/test_i18n.py` if intended, and rebuild `examples/54-showcase/oversikt.html`.

## Tests

Run a single suite directly, or run the whole gate runner in parallel:

```bash
python3 tools/check_all.py --fast                       # pre-commit static gates (~2 s)
python3 tools/check_all.py --no-browser                 # all non-Playwright suites
uv run --extra verify python tools/check_all.py -j 4    # full suite including browsers
```

For non-trivial tooling changes, the [`hotshot`](skills/dev/hotshot/SKILL.md) dev skill
drives the full implement → verify → adversarial review (`magnus-review`) → PR round.

## The pre-commit hook

`python3 setup.py --hooks` points `core.hooksPath` at `tools/hooks`. The hook refuses a
commit made on `main`, then runs `python3 tools/check_all.py --fast`. You can run the tree
gates by hand at any time:

```bash
python3 tools/check_tree.py
```

The public repository runs every gate on each pull request
(`.github/workflows/gates.yml`).

## Pull requests

- Nothing goes to `main` except through a pull request. Work on a branch.
- Stage files by name. Do not use `git add -A` or `git add .`.
- Never commit real customer or client data, not even briefly ([`AGENTS.md`](AGENTS.md), rule 6).
  `work/<task>/` is gitignored for this reason.
- Use British `artefact` and hyphenated `self-contained` in prose (`tests/test_glossary.py`).
- If you change a tenant constraint, update [`docs/01-tenant-constraints.md`](docs/01-tenant-constraints.md)
  in the same commit. If you add or revise an architectural boundary, record an ADR in
  [`docs/adr/`](docs/adr/README.md).
