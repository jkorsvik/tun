---
name: refresh-artefacts
description: "Rebuild committed example artefacts, re-pin i18n SHA-256 baselines, and refresh the Tún Explorer after editing a template, token file, or builder. Use when template or builder edits make test_examples_are_current, test_i18n, or check_showcase_fresh go red, or before opening a PR that modifies shared templates or tools/."
license: Internal
metadata:
  title: Refresh committed artefacts and Explorer
  version: 1.0.0
  tags: "workflow, templates, builders, i18n, explorer, gates"
  platforms: "darwin, linux, win32"
---

# Refresh committed artefacts and Explorer

**Tier and cost, for the first reply:** none. Local rebuilds on a pinned clock (`SOURCE_DATE_EPOCH=1792836000`); nothing is published until a pull request is reviewed and merged.

When you change a file under `templates/`, `tools/tokens/`, `tools/tun_brand.py`, or `tools/build_*.py`, committed examples and `tests/test_i18n.py` SHA-256 baselines go stale by design. Run this sequence in order so every gate stays byte-exact and nothing slips through.

## 1. Find stale examples

```bash
python3 tests/test_examples_are_current.py
```

Every `stale:` line names an example whose committed `.html` differs from its README rebuild command.

## 2. Rebuild affected examples on the pinned clock

Run each stale example's README build command with the repository's pinned clock so timestamps stay deterministic across machines:

```bash
TZ=UTC SOURCE_DATE_EPOCH=1792836000 python3 tools/build_<kind>.py ... --out examples/<nn>-<slug>/<file>.html
```

Verify every rebuilt example matches:

```bash
python3 tests/test_examples_are_current.py
```

**Done when:** `test_examples_are_current.py` prints `PASS`.

## 3. Audit and re-pin `tests/test_i18n.py`

Run `python3 tests/test_i18n.py`. Only the cases backed by the templates or builders you actually edited should appear under section 3 (`nb build equals the baseline sha256`). If an unrelated builder moved, stop and root-cause it before touching any hash.

When every changed hash is accounted for, dump the fresh hashes from a temp directory and update `BASELINE` in `tests/test_i18n.py` with a dated comment naming the change:

```bash
python3 -c "import subprocess,sys,tempfile; td=tempfile.mkdtemp(); print(subprocess.run([sys.executable,'tests/test_i18n.py','--dump',td],capture_output=True,text=True).stdout)"
```

Re-run `python3 tests/test_i18n.py` and confirm `FAIL: 0`.

## 4. Rebuild the Explorer last

`examples/54-showcase/oversikt.html` embeds every other example byte for byte, so rebuild it only after every other example is final:

```bash
TZ=UTC SOURCE_DATE_EPOCH=1792836000 uv run --extra verify python tools/build_showcase.py \
  --examples examples \
  --title "Tún Explorer" \
  --source "the built examples in this repository" \
  --requested-by "Prosjekteier" \
  --out examples/54-showcase/oversikt.html

python3 tools/check_showcase_fresh.py
```

## 5. Run the gates and inspect a screenshot

```bash
python3 tools/check_all.py --fast
uv run --extra verify python tools/verify_dashboard.py examples/01-hello-dashboard/salg-dashboard.html --engines all
uv run --extra verify python tools/verify_a11y.py examples/01-hello-dashboard/salg-dashboard.html --dark --engines all
uv run --extra verify python tools/check_all.py
```

Remove any generated `*.verify.png` scratch screenshots from the working tree after visually inspecting them, then stage modified files explicitly by path.
