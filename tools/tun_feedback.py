#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
tun_feedback.py — a local feedback log for the Tún skills. Used by `tun-feedback`.

Stdlib only. Nothing is sent anywhere unless `issue --send` is given, and the skill
only gives it after the person said yes to the exact title and body.

    python3 tools/tun_feedback.py append --skill tun-new --severity medium \
        --happened "the bar chart was empty" --expected "bars per region" \
        [--artefact dashboards/salg.html] [--title "..."] [--browser "Edge 141"] [--dry-run]
    python3 tools/tun_feedback.py list [--last 10]
    python3 tools/tun_feedback.py issue [N]            # print the issue title and body
    python3 tools/tun_feedback.py issue [N] --send     # file it with gh, in this checkout

The log is one JSON object per line, append-only:
    ~/.raiwork/tun-feedback/feedback.jsonl     (override with --log or TUN_FEEDBACK_LOG)

A record holds what the person typed plus the operating system, the browser if they
named it, and the Tún version (`git describe` of this checkout). No user name, no
host name. A path under the home directory is written as ~/..., so the record does
not carry the account name either.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tree_scan import REPO, clean_env  # noqa: E402

SEVERITIES = ("low", "medium", "high")
DEFAULT_LOG = pathlib.Path.home() / ".raiwork" / "tun-feedback" / "feedback.jsonl"


def log_path(arg: str | None) -> pathlib.Path:
    return pathlib.Path(arg or os.environ.get("TUN_FEEDBACK_LOG") or DEFAULT_LOG).expanduser()


def tun_version() -> str:
    """`git describe` of the checkout this script lives in, or "unknown" (a zip, no git)."""
    try:
        out = subprocess.run(["git", "-C", str(REPO), "describe", "--tags", "--always", "--dirty"],
                             capture_output=True, text=True, check=True, env=clean_env())
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def tidy_path(raw: str) -> str:
    """Absolute path with the home directory shown as ~, so no account name is stored."""
    p = pathlib.Path(raw).expanduser().resolve()
    try:
        return "~/" + p.relative_to(pathlib.Path.home().resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def read_title(raw: str) -> str | None:
    """The artefact's own <title>, if the file is there to read."""
    p = pathlib.Path(raw).expanduser()
    if not p.is_file():
        return None
    m = re.search(r"<title>(.*?)</title>", p.read_text(encoding="utf-8", errors="replace")[:65536],
                  re.IGNORECASE | re.DOTALL)
    return html.unescape(m.group(1)).strip() if m else None


def make_record(a: argparse.Namespace) -> dict:
    artefact = None
    if a.artefact:
        artefact = {"path": tidy_path(a.artefact), "title": a.title or read_title(a.artefact)}
    elif a.title:
        artefact = {"path": None, "title": a.title}
    return {
        "time": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "skill": a.skill,
        "artefact": artefact,
        "happened": a.happened.strip(),
        "expected": (a.expected or "").strip(),
        "severity": a.severity,
        "environment": {
            "os": f"{platform.system()} {platform.release()}".strip(),
            "browser": a.browser or None,
            "tun_version": tun_version(),
        },
    }


def read_log(path: pathlib.Path) -> list[dict]:
    if not path.is_file():
        return []
    records = []
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            sys.exit(f"error: line {no} of {path} is not valid JSON ({exc.msg}). "
                     f"Fix or delete that line; the other records are intact.")
    return records


def pick(records: list[dict], n: int | None) -> tuple[int, dict]:
    """(N, record N), counting from 1 as `list` does; the last record when N is None."""
    if not records:
        sys.exit("error: the feedback log is empty")
    n = n or len(records)
    if not 1 <= n <= len(records):
        sys.exit(f"error: no record {n}; the log holds 1..{len(records)}")
    return n, records[n - 1]


def _cell(v) -> str:
    """One markdown table cell: empty reads as "not stated", and | or a newline cannot break the row."""
    return str(v if v not in (None, "") else "not stated").replace("|", "\\|").replace("\n", " ")


def issue_text(r: dict) -> tuple[str, str]:
    """(title, body) for a forge issue. What `issue` prints is exactly what --send files."""
    first = r["happened"].splitlines()[0] if r["happened"] else "(no description)"
    title = f"feedback({r['skill']}): {first[:70]}{'…' if len(first) > 70 else ''}"
    art = r.get("artefact") or {}
    artefact = " ".join(x for x in (art.get("title") or "", f"`{art['path']}`" if art.get("path") else "") if x)
    env = r["environment"]
    rows = [("Skill", r["skill"]), ("Artefact", artefact), ("Severity", r["severity"]),
            ("Time", r["time"]), ("OS", env.get("os")), ("Browser", env.get("browser")),
            ("Tún version", env.get("tun_version"))]
    body = (f"**What happened**\n\n{r['happened']}\n\n"
            f"**What was expected**\n\n{r['expected'] or '_not stated_'}\n\n"
            "| | |\n|---|---|\n" + "".join(f"| {k} | {_cell(v)} |\n" for k, v in rows) +
            "\n_Recorded with the tun-feedback skill. The reporter saw this text before it was filed._\n")
    return title, body


def cmd_append(a: argparse.Namespace) -> int:
    if not a.happened.strip():
        sys.exit("error: --happened is empty; record what the person said happened")
    rec = make_record(a)
    print(json.dumps(rec, ensure_ascii=False, indent=2))
    if a.dry_run:
        print("\n(dry run: not written)")
        return 0
    path = log_path(a.log)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"\nappended to {path} (record {len(read_log(path))})")
    return 0


def cmd_list(a: argparse.Namespace) -> int:
    records = read_log(log_path(a.log))
    start = max(0, len(records) - a.last) if a.last else 0
    for i, r in enumerate(records[start:], start + 1):
        print(f"{i:>4}  {r['time'][:16]}  {r['severity']:<6}  {r['skill']:<14}  {r['happened'][:60]}")
    print(f"{len(records)} record(s) in {log_path(a.log)}")
    return 0


def cmd_issue(a: argparse.Namespace) -> int:
    n, rec = pick(read_log(log_path(a.log)), a.n)
    title, body = issue_text(rec)
    print(f"record {n}\n\nTITLE\n{title}\n\nBODY\n{body}")
    if not a.send:
        return 0
    gh = shutil.which("gh")
    if not gh:
        sys.exit("error: gh is not installed. Open a new issue on the forge by hand and paste "
                 "the title and body above.")
    with tempfile.TemporaryDirectory() as td:
        body_file = pathlib.Path(td) / "body.md"
        body_file.write_text(body, encoding="utf-8")
        # An argument list, not a shell string: a title with quotes or backticks stays text.
        # cwd is this checkout, so gh files on the forge its origin remote points at.
        proc = subprocess.run([gh, "issue", "create", "--title", title, "--body-file", str(body_file)],
                              cwd=REPO, env=clean_env())
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--log", help="log file (default ~/.raiwork/tun-feedback/feedback.jsonl)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("append", parents=[common], help="record one item (prints it first)")
    p.add_argument("--skill", required=True, help="the tun-* skill it is about, or 'artefact'")
    p.add_argument("--happened", required=True, help="what happened, in the person's words")
    p.add_argument("--expected", default="", help="what they expected instead")
    p.add_argument("--severity", choices=SEVERITIES, default="medium")
    p.add_argument("--artefact", help="path to the built file it is about, if any")
    p.add_argument("--title", help="artefact title (read from the file when omitted)")
    p.add_argument("--browser", help="browser and version, only if the person named it")
    p.add_argument("--dry-run", action="store_true", help="print the record, write nothing")
    p.set_defaults(func=cmd_append)

    p = sub.add_parser("list", parents=[common], help="show the log")
    p.add_argument("--last", type=int, default=0)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("issue", parents=[common], help="print record N (default: last) as an issue title and body")
    p.add_argument("n", nargs="?", type=int)
    p.add_argument("--send", action="store_true", help="file it with gh; only after an explicit yes")
    p.set_defaults(func=cmd_issue)

    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
