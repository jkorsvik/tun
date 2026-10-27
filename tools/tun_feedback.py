#!/usr/bin/env python3
"""
tun_feedback.py — a local feedback log for the Tún skills. Used by `tun-feedback`.

Stdlib only. Nothing is sent anywhere unless `issue --send` is given, and the skill
only gives it after the person said yes to the exact title and body.

    python3 tools/tun_feedback.py append --skill tun-new --kind bug --severity medium \
        --happened "the bar chart was empty" --expected "bars per region" \
        [--artefact dashboards/salg.html] [--title "..."] [--browser "Edge 141"] [--dry-run]
    python3 tools/tun_feedback.py append --skill tun-new --kind idea --happened "a map view"
    python3 tools/tun_feedback.py list [--last 10]
    python3 tools/tun_feedback.py issue [N]            # print the target, title and body
    python3 tools/tun_feedback.py issue [N] --send     # file exactly that, with gh

Issues go to the repository this copy of Tún names, never to whatever git checkout the
person happens to stand in: --repo, else TUN_FEEDBACK_REPO, else a FEEDBACK_REPO file
next to tools/ (a packager writes it, as with VERSION), else the origin remote when
this tree is its own clone. So a packaged copy with no git at all can file too. The
target is usually public, so the issue leaves out the artefact's title and path: those
stay in the local log. If gh is missing or fails, `issue` has already printed a
prefilled new-issue link.

The log is one JSON object per line, append-only:
    ~/.raiwork/tun-feedback/feedback.jsonl     (override with --log or TUN_FEEDBACK_LOG)

A record holds what the person typed plus the operating system, the browser if they
named it, and the Tún version (`git describe` when this tree is its own git checkout,
else a VERSION file next to tools/, else "unknown"). No user name, no host name. A path under the home directory is written as ~/..., so the record does
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
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tree_scan import REPO, clean_env  # noqa: E402

SEVERITIES = ("low", "medium", "high")
KINDS = ("bug", "idea")
REPO_FORM = re.compile(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}/[\w.-]+/[\w.-]+")
DEFAULT_LOG = pathlib.Path.home() / ".raiwork" / "tun-feedback" / "feedback.jsonl"


def log_path(arg: str | None) -> pathlib.Path:
    return pathlib.Path(arg or os.environ.get("TUN_FEEDBACK_LOG") or DEFAULT_LOG).expanduser()


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                             check=True, env=clean_env())
        return out.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def own_checkout() -> bool:
    """True when this tree is the top of its own git checkout, not a copy inside another repo."""
    top = _git("rev-parse", "--show-toplevel")
    return bool(top) and pathlib.Path(top).resolve() == REPO.resolve()


def tun_version() -> str:
    """The Tún version of this tree.

    `git describe` only when this tree is the top of its own checkout: a packaged copy
    inside some other repository (a dotfiles repo in ~, a project) must not report that
    repository's version. Then a VERSION file a packager wrote next to tools/.
    """
    if own_checkout():
        described = _git("describe", "--tags", "--always", "--dirty")
        if described:
            return described
    version = REPO / "VERSION"
    if version.is_file():
        return version.read_text(encoding="utf-8").strip() or "unknown"
    return "unknown"


def _origin() -> str | None:
    """HOST/OWNER/NAME of this clone's origin remote; None for a copy inside another repo."""
    if not own_checkout():
        return None
    m = re.fullmatch(r"(?:https://(?:[^@/]+@)?|ssh://git@|git@)([^/:]+)[/:]([^/]+)/([^/]+?)(?:\.git)?/?",
                     _git("remote", "get-url", "origin") or "")
    return "/".join(m.groups()) if m else None


def target_repo(arg: str | None) -> tuple[str, str]:
    """(HOST/OWNER/NAME, where it came from) that issues are filed on, first found wins."""
    file = REPO / "FEEDBACK_REPO"
    for raw, source in ((arg, "--repo"), (os.environ.get("TUN_FEEDBACK_REPO"), "TUN_FEEDBACK_REPO"),
                        (file.read_text(encoding="utf-8") if file.is_file() else None, "FEEDBACK_REPO"),
                        (_origin(), "origin remote")):
        if not raw or not raw.strip():
            continue
        repo = re.sub(r"^https://|\.git$", "", raw.strip()).strip("/")
        if not REPO_FORM.fullmatch(repo):
            sys.exit(f"error: {repo!r} from {source} is not HOST/OWNER/NAME (for example forge.example/owner/tun)")
        return repo, source
    sys.exit("error: this copy of Tún names no repository for feedback. Give --repo HOST/OWNER/NAME, "
             f"set TUN_FEEDBACK_REPO, or write it to {REPO / 'FEEDBACK_REPO'}. The record stays in the local log.")


def new_issue_url(repo: str, title: str, body: str) -> str:
    """A prefilled new-issue link, for when gh is missing, not logged in, or fails."""
    q = urllib.parse.urlencode({"title": title, "body": body}, quote_via=urllib.parse.quote)
    return f"https://{repo}/issues/new?{q}"


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
        "kind": a.kind,
        "artefact": artefact,
        "happened": a.happened.strip(),
        "expected": (a.expected or "").strip(),
        # Severity is how badly a bug stopped the person. An idea has none unless they gave one.
        "severity": a.severity or ("medium" if a.kind == "bug" else None),
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
    """(title, body) for a forge issue. What `issue` prints is exactly what --send files.

    The artefact's title and path are left out on purpose: the target is public, and a
    title such as an internal product name must not leave the machine by accident.
    """
    kind = r.get("kind", "bug")  # records written before --kind existed were all reports
    first = r["happened"].splitlines()[0] if r["happened"] else "(no description)"
    title = f"{kind}({r['skill']}): {first[:70]}{'…' if len(first) > 70 else ''}"
    about = "a built file (title and path kept in the local log)" if r.get("artefact") else None
    env = r["environment"]
    rows = [("Kind", kind), ("Skill", r["skill"]), ("About", about), ("Severity", r["severity"]),
            ("Time", r["time"]), ("OS", env.get("os")), ("Browser", env.get("browser")),
            ("Tún version", env.get("tun_version"))]
    heads = (("What happened", "What was expected") if kind == "bug"
             else ("The idea", "What it would make possible"))
    body = (f"**{heads[0]}**\n\n{r['happened']}\n\n"
            f"**{heads[1]}**\n\n{r['expected'] or '_not stated_'}\n\n"
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
        print(f"{i:>4}  {r['time'][:16]}  {r.get('kind', 'bug'):<4}  {r['severity'] or '-':<6}  "
              f"{r['skill']:<14}  {r['happened'][:60]}")
    print(f"{len(records)} record(s) in {log_path(a.log)}")
    return 0


def cmd_issue(a: argparse.Namespace) -> int:
    n, rec = pick(read_log(log_path(a.log)), a.n)
    repo, source = target_repo(a.repo)
    title, body = issue_text(rec)
    print(f"record {n}\n\nTARGET\nhttps://{repo}  (from {source}. Anyone who can read this repository "
          f"can read the issue, so check the text for internal names, numbers or customer data "
          f"before you say yes.)\n\n"
          f"TITLE\n{title}\n\nBODY\n{body}\n"
          f"Without gh, open this link and press Submit:\n{new_issue_url(repo, title, body)}")
    if not a.send:
        return 0
    gh = shutil.which("gh")
    if not gh:
        sys.exit("error: gh is not installed. Open the link above to file the same issue by hand.")
    with tempfile.TemporaryDirectory() as td:
        body_file = pathlib.Path(td) / "body.md"
        body_file.write_text(body, encoding="utf-8")
        # An argument list, not a shell string: a title with quotes or backticks stays text.
        # --repo names the host too, and cwd is an empty folder: no checkout, no origin
        # remote and no GH_REPO can change where it lands.
        env = {k: v for k, v in clean_env().items() if k not in ("GH_REPO", "GH_HOST")}
        proc = subprocess.run([gh, "issue", "create", "--repo", repo, "--title", title,
                               "--body-file", str(body_file)], cwd=td, env=env)
    if proc.returncode:
        print("gh could not file it. Open the link above to file the same issue by hand.",
              file=sys.stderr)
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
    p.add_argument("--kind", choices=KINDS, default="bug", help="bug: something went wrong; idea: a suggestion")
    p.add_argument("--severity", choices=SEVERITIES, help="bugs: low, medium (default) or high")
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
    p.add_argument("--repo", help="HOST/OWNER/NAME to file on (else TUN_FEEDBACK_REPO, FEEDBACK_REPO, origin)")
    p.set_defaults(func=cmd_issue)

    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
