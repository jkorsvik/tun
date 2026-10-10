# Security policy

## What is in scope

- The toolkit: `setup.py` and the builders and verifiers in `tools/`.
- The gates: `tools/check_tree.py`, `tools/check_no_real_data.py`, `tools/scan_history.py` and the hooks in `tools/hooks`.
- The templates in `templates/` and the skills in `skills/`.

Generated artefacts are plain files with no server behind them. A flaw in how a template builds them is in scope, because every artefact copies that markup. A flaw in a file someone built with it and shared is the author's file, so report the template cause rather than the file.

Two things count as security problems here even if they look like design:

- A build that writes a row into a file whose audience should not see it (rule 1 in `AGENTS.md`).
- Anything that defeats `Content-Disposition: attachment` (rule 2 in `AGENTS.md`).

## How to report

Use GitHub private vulnerability reporting: open this repository's **Security** tab and choose
**Report a vulnerability**.

Please do not open a public issue for a vulnerability. Describe what you saw, the file or command involved, and how to reproduce it. Do not attach real customer or client data.

## What to expect

Reports are read on a best effort basis. This is a small project, so there is no promised response time. You will hear back through the same advisory thread.
