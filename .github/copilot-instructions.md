# GitHub Copilot instructions for Tún

Read [`AGENTS.md`](../AGENTS.md) for all repository invariants, verification gates and
conventions. Read [`START-HERE.md`](../START-HERE.md) and [`llms.txt`](../llms.txt) when
helping a user install or use Tún.

## Two modes — notice which one the user wants

1. **Using Tún to build or share an artefact** (user has data, wants a dashboard/report/diagram, or asks to install/introduce Tún):
   - Install skills with `python3 setup.py --tool agents` (`py -3 setup.py --tool agents` on Windows) if not installed yet.
   - Greet new users in their language (Norwegian or English), introduce the `tun-*` verbs (`tun-help`, `tun-new`, `tun-data`, `tun-verify`, `tun-publish`, `tun-process`, `tun-review`, `tun-host`, `tun-powerbi-escape`, `tun-for-communicators`, `tun-feedback`), and follow `skills/<verb>/SKILL.md`.
   - **Folder = security boundary:** never put rows in a file whose whole folder audience should not see them; split the data first.
   - **Never write real user or client data into this repository.** Write user deliverables outside the repo (or under gitignored `work/`).

2. **Contributing to the Tún toolkit itself** (editing `tools/`, `templates/`, `skills/`, `docs/` or `tests/`):
   - Keep `tools/` stdlib-only Python 3.9+ and cross-platform (Windows, macOS, Linux).
   - Never commit directly to `main`; stage explicit paths (`git add <file>`), never `git add -A` or `git add .`.
   - Use British `artefact` and hyphenated `self-contained` in prose (`tests/test_glossary.py`).
   - Run `python3 tools/check_all.py --fast` and browser verification (`uv run --extra verify python tools/check_all.py`) before claiming a change works.
