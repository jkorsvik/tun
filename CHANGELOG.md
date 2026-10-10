# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Bundled dashboards: one self-contained HTML file with the data inside
  (`tools/build_dashboard.py`, `examples/01-hello-dashboard/`).
- Paired dashboards: a dashboard next to a sibling `data.js`, so replacing the data file
  updates the numbers with no rebuild (`--mode paired`, `examples/02-paired-dashboard/`).
- Cube mode: a pre-aggregated dense cube for millions of rows in one file
  (`tools/build_cube_dashboard.py`, `examples/03-cube-dashboard/`).
- Process diagram builder (`tools/build_process_diagram.py`, `examples/23-process-diagram/`).
- Portable slide deck builder (`tools/build_slide_deck.py`, `examples/18-portable-slide-deck/`).
- `--lang en|nb` on the builders, with the page strings in `templates/i18n/` (`tools/i18n.py`).
- Claude Code plugin (`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`).
- Agent Skills installer for RAIWork, Claude Code and other tools that read the open
  format (`python3 setup.py --tool raiwork|agents|claude`).
- Editable document example (`examples/24-editable-document/`).
- Living picture example (`examples/25-living-idea-picture/`).
- Verification tools that open a built file in a real browser (`tools/verify_dashboard.py`)
  and a pre-commit gate (`tools/hooks/pre-commit`).
