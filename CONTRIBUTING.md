# Contributing

Thanks for looking. Read `AGENTS.md` first. It holds the rules that do not bend, and
`docs/06-way-of-working.md` holds the habits behind them.

By taking part you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). Report security
problems as described in [SECURITY.md](SECURITY.md), not in a public issue.

## Where to start

Open an issue in this repository before a large change.

The skills are prose, not code. If an agent does something the wrong way, the fix is
usually a sentence in `skills/*/SKILL.md`. Knowing how reports are really used is worth
more here than engineering.

## Set up

Nothing to install for the main path. `tools/` is stdlib-only Python and must stay that
way, because the main user is on Windows with no toolchain.

```bash
python3 setup.py --hooks   # once per clone: turns on the pre-commit gate
python3 setup.py --check   # reports what is present and what is missing
```

For the browser checks you need Playwright. Python goes through `uv` and JavaScript
through `bun`; do not use `pip` or `npm`.

```bash
uv run --no-project --no-config --index-url https://pypi.org/simple --with playwright python tools/verify_dashboard.py <file.html>
```

## The verification gate

Before you say a change works, rebuild the example and verify it. The full command is in
the "Verification gate" section of `AGENTS.md`. Shortened:

```bash
python3 tools/build_dashboard.py \
  --data examples/01-hello-dashboard/salgsdata.csv \
  --title "Salg per region og produkt 2026" \
  --dimension Produkt --measure Belop --time Maaned \
  --filters Region,Produkt,Kanal \
  --source "Eksempeldata (syntetisk), salgsdata.csv" \
  --requested-by "Prosjekteier" \
  --out /tmp/demo.html

python3 tools/verify_dashboard.py /tmp/demo.html   # needs Playwright, prints PASS
```

A clean build is not evidence. Open the file and look at the screenshot.

## Tests

Each test is a plain script:

```bash
python3 tests/test_row_24_26_checks.py
python3 tests/test_i18n.py
```

Run them all from a bash shell:

```bash
for f in tests/test_*.py; do python3 "$f" > /dev/null || echo "FAILED $f"; done
```

Some tests also drive a browser. Without Playwright they skip that half or fail, and say
so. Run those through `uv` as shown above, for example:

```bash
uv run --no-project --no-config --index-url https://pypi.org/simple --with playwright python tests/test_feedback_link_browser.py
```

## The pre-commit hook

`python3 setup.py --hooks` points `core.hooksPath` at `tools/hooks`. The hook refuses a
commit made on the integration branch, then runs the tree gates and the gate tests. It
needs only Python. You can run the tree gates by hand at any time:

```bash
python3 tools/check_tree.py
```

There is no CI on this project, so the hook is the whole gate. It only protects a clone
that turned it on.

## Pull requests

- Nothing goes to `main` except through a pull request. Work on a branch.
- Stage files by name. Do not use `git add -A` or `git add .`.
- Never commit real customer or client data, not even briefly (`AGENTS.md`, rule 6).
  `work/<task>/` is gitignored for this reason.
- If you change a tenant constraint, update `docs/01-tenant-constraints.md` in the same
  commit.
