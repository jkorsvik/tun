#!/usr/bin/env python3
"""Tests for the feedback paths: the skill's local log and the artefact's link.

Stdlib only, no network, no browser. The browser half (live href, JavaScript off,
error count, verify_dashboard on both builds) is tests/test_feedback_link_browser.py.

  A. tools/tun_feedback.py — append, list, issue, issue --send (through a spy `gh`),
     and a packaged copy with no checkout of its own
  B. tools/feedback_link.py and the --feedback-to flag on both builders

Every case runs the real scripts as subprocesses against a temp log and temp output.

    python3 tests/test_tun_feedback.py
"""
from __future__ import annotations

import getpass
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
CSV = ROOT / "examples" / "01-hello-dashboard" / "salgsdata.csv"
EXAMPLE = ROOT / "examples" / "01-hello-dashboard" / "salg-dashboard.html"
sys.path.insert(0, str(TOOLS))
import feedback_link  # noqa: E402
import verify_standalone_core as core  # noqa: E402

PASS = FAIL = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}{(' — ' + detail) if detail else ''}")


def run(args: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=ROOT,
                          timeout=120, env=env)


def static_href(html: str) -> str:
    m = re.search(r'<a id="tun-feedback" href="([^"]*)"', html)
    return m.group(1).replace("&amp;", "&") if m else ""


def spy_gh(bin_dir: pathlib.Path, record: pathlib.Path) -> None:
    """A `gh` that records its argv and the body file, then succeeds. Spy-shim, no network."""
    script = bin_dir / "gh_spy.py"
    script.write_text(
        "import json, os, sys\n"
        "a = sys.argv[1:]\n"
        "body = open(a[a.index('--body-file') + 1], encoding='utf-8').read()\n"
        f"open({str(record)!r}, 'w', encoding='utf-8').write(json.dumps({{'argv': a, 'body': body, "
        "'cwd': os.getcwd(), 'gh_env': {k: v for k, v in os.environ.items() if k.startswith('GH_')}}))\n"
        "sys.exit(int(os.environ.get('GH_SPY_RC', '0')))\n",
        encoding="utf-8")
    sh = bin_dir / "gh"
    sh.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
    sh.chmod(0o755)
    (bin_dir / "gh.bat").write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")


def printed(stdout: str) -> tuple[str, str, str, str]:
    """(target, title, body, fallback link) exactly as `issue` printed them."""
    target = stdout.split("TARGET\n", 1)[-1].split("\n", 1)[0]
    title = stdout.split("TITLE\n", 1)[-1].split("\n", 1)[0]
    body, _, rest = stdout.split("BODY\n", 1)[-1].partition("\nWithout gh, open this link")
    link = rest.split(":\n", 1)[-1].split("\n", 1)[0]
    return target, title, body, link


def part_a(tmp: pathlib.Path) -> None:
    print("A. tools/tun_feedback.py")
    home = tmp / "home"
    log = home / ".raiwork" / "tun-feedback" / "feedback.jsonl"
    # A fake home, so "a path under home is stored as ~/..." is tested wherever the
    # checkout lives. HOME on POSIX, USERPROFILE on Windows.
    # TUN_FEEDBACK_REPO pins the target, so this checkout's own origin never decides a result.
    env = {**os.environ, "TUN_FEEDBACK_LOG": str(log), "HOME": str(home), "USERPROFILE": str(home),
           "TUN_FEEDBACK_REPO": "forge.example/acme/tun"}
    artefact = home / "dash" / "salg.html"
    artefact.parent.mkdir(parents=True)
    shutil.copy(EXAMPLE, artefact)
    helper = str(TOOLS / "tun_feedback.py")

    r = run([helper, "append", "--skill", "tun-new", "--happened", "x", "--dry-run"], env)
    check("dry run prints the record", r.returncode == 0 and '"happened": "x"' in r.stdout, r.stderr)
    check("dry run writes nothing", not log.exists())

    r = run([helper, "append", "--skill", "tun-verify", "--severity", "high",
             "--happened", "Grafen var tom | helt", "--expected", "Søyler per region",
             "--artefact", str(artefact), "--browser", "Edge | 141"], env)
    check("append exits 0", r.returncode == 0, r.stderr.strip())
    check("append shows the full record before saying where it went",
          r.stdout.index('"happened"') < r.stdout.index("appended to"), r.stdout[-200:])
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    check("append writes exactly one line", len(lines) == 1, str(len(lines)))
    rec = json.loads(lines[0]) if lines else {}
    check("record has exactly the documented fields",
          sorted(rec) == ["artefact", "environment", "expected", "happened", "kind", "severity", "skill", "time"],
          str(sorted(rec)))
    check("environment has exactly os, browser, tun_version",
          sorted(rec.get("environment", {})) == ["browser", "os", "tun_version"])
    check("title read from the artefact itself",
          (rec.get("artefact") or {}).get("title") == "Salg per region og produkt 2026", str(rec.get("artefact")))
    check("Tún version comes from git describe", bool(rec.get("environment", {}).get("tun_version"))
          and rec["environment"]["tun_version"] != "unknown", str(rec.get("environment")))
    user = getpass.getuser()
    check("no account name in the stored line", user not in lines[0], f"{user!r} found")
    check("a path under home is stored as ~/...",
          (rec.get("artefact") or {}).get("path") == "~/dash/salg.html", str(rec.get("artefact")))

    r = run([helper, "append", "--skill", "tun-new", "--happened", "  "], env)
    check("an empty --happened is refused", r.returncode != 0 and "empty" in r.stderr, r.stderr)
    r = run([helper, "append", "--skill", "tun-new", "--happened", "x", "--severity", "urgent"], env)
    check("an unknown severity is refused", r.returncode != 0)

    run([helper, "append", "--skill", "tun-publish", "--happened", "andre"], env)
    r = run([helper, "list"], env)
    check("list shows both records", "2 record(s)" in r.stdout and "andre" in r.stdout, r.stdout)

    check("a report defaults to kind bug", rec.get("kind") == "bug", str(rec.get("kind")))
    r = run([helper, "issue", "1"], env)
    target, title, body, link = printed(r.stdout)
    check("issue names the target, its source and who can read it, before the text",
          target.startswith("https://forge.example/acme/tun  (from TUN_FEEDBACK_REPO")
          and "Anyone who can read" in target
          and r.stdout.index("TARGET") < r.stdout.index("TITLE"), target)
    check("issue title names the kind, the skill and the complaint",
          title == "bug(tun-verify): Grafen var tom | helt", title)
    check("issue body carries happened and expected",
          "Grafen var tom | helt" in body and "Søyler per region" in body)
    check("a | in a table cell is escaped", "| Browser | Edge \\| 141 |" in body, body[-300:])
    check("the public issue leaves out the artefact's title and path",
          "Salg per region" not in r.stdout and "salg.html" not in r.stdout and "built file" in body,
          body[-400:])
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query)
    check("the fallback link is a prefilled new issue on the same target",
          link.startswith("https://forge.example/acme/tun/issues/new?")
          and q.get("title") == [title] and q.get("body") == [body], link[:90])
    other = tmp / "other.jsonl"
    r = run([helper, "append", "--skill", "tun-new", "--happened", "x", "--log", str(other)], env)
    check("--log works after the subcommand", r.returncode == 0 and other.is_file(), r.stderr[-160:])
    other.write_text(other.read_text(encoding="utf-8") + "{not json\n", encoding="utf-8")
    r = run([helper, "list", "--log", str(other)], env)
    check("a corrupt line is named, not a traceback",
          r.returncode != 0 and "line 2" in r.stderr and "Traceback" not in r.stderr, r.stderr[-200:])
    r = run([helper, "issue", "9"], env)
    check("an out-of-range record is refused", r.returncode != 0 and "1..2" in r.stderr, r.stderr)
    r = run([helper, "issue"], env)
    check("issue defaults to the last record", "bug(tun-publish): andre" in r.stdout)

    r = run([helper, "append", "--skill", "tun-new", "--kind", "idea", "--happened", "Et kart",
             "--expected", "se fylkene", "--log", str(tmp / "idea.jsonl")], env)
    idea = json.loads((tmp / "idea.jsonl").read_text(encoding="utf-8")) if r.returncode == 0 else {}
    check("an idea is recorded as kind idea, with no made-up severity",
          idea.get("kind") == "idea" and idea.get("severity") is None, str(idea)[:160])
    r = run([helper, "issue", "--log", str(tmp / "idea.jsonl")], env)
    _, t, b, _ = printed(r.stdout)
    check("an idea is filed as an idea", t == "idea(tun-new): Et kart" and "**The idea**" in b
          and "| Severity | not stated |" in b, t + " / " + b[:80])
    r = run([helper, "append", "--skill", "tun-new", "--kind", "rant", "--happened", "x"], env)
    check("an unknown kind is refused", r.returncode != 0)
    r = run([helper, "issue", "1", "--repo", "forge.example/acme/other"], env)
    check("--repo beats TUN_FEEDBACK_REPO", printed(r.stdout)[0].startswith("https://forge.example/acme/other "))
    r = run([helper, "issue", "1"], {**env, "TUN_FEEDBACK_REPO": "forge.example/acme/tun2"})
    check("TUN_FEEDBACK_REPO moves the target", printed(r.stdout)[0].startswith("https://forge.example/acme/tun2 "))
    r = run([helper, "issue", "1", "--repo", "acme/tun"], env)
    check("a target without a host is refused", r.returncode != 0 and "HOST/OWNER/NAME" in r.stderr, r.stderr)

    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    spy = tmp / "gh-call.json"
    spy_gh(bin_dir, spy)
    # GH_REPO and GH_HOST would redirect gh; --send must not let them.
    env_gh = {**env, "PATH": str(bin_dir) + os.pathsep + env.get("PATH", ""),
              "GH_REPO": "evil/elsewhere", "GH_HOST": "evil.example"}
    r = run([helper, "issue", "1"], env_gh)
    check("issue without --send never calls gh", r.returncode == 0 and not spy.exists())
    r = run([helper, "issue", "1", "--send"], env_gh)
    call = json.loads(spy.read_text(encoding="utf-8")) if spy.exists() else {}
    check("--send calls gh issue create", call.get("argv", [])[:2] == ["issue", "create"], r.stderr)
    argv = call.get("argv", [])
    check("--send files the exact title it printed",
          "--title" in argv and argv[argv.index("--title") + 1] == title)
    check("--send files the exact body it printed", call.get("body", "").strip() == body.strip())
    check("--send names the target with --repo, host included",
          "--repo" in argv and argv[argv.index("--repo") + 1] == "forge.example/acme/tun", str(argv))
    check("--send runs outside any checkout, with GH_REPO and GH_HOST removed",
          not (pathlib.Path(call.get("cwd", ROOT)) / ".git").exists()
          and pathlib.Path(call.get("cwd", ROOT)).resolve() != ROOT.resolve()
          and not call.get("gh_env"), str({k: call.get(k) for k in ("cwd", "gh_env")}))
    r = run([helper, "issue", "1", "--send"], {**env_gh, "GH_SPY_RC": "1"})
    check("a failing gh is reported, pointing at the link", r.returncode == 1 and "link above" in r.stderr,
          r.stderr[-160:])
    empty_bin = tmp / "nobin"
    empty_bin.mkdir()
    r = run([helper, "issue", "1", "--send"], {**env, "PATH": str(empty_bin)})
    check("no gh: refused, pointing at the link", r.returncode != 0 and "link above" in r.stderr, r.stderr[-160:])

    # A packaged copy (the RAIWork plugin) has no checkout of its own. Put one inside an
    # unrelated git repository, as a dotfiles repo in ~ would be, and check that it
    # neither reports that repository's version nor needs a checkout to file.
    outer = tmp / "outer"
    pkg = outer / "plugins" / "engine"
    shutil.copytree(TOOLS, pkg / "tools", ignore=shutil.ignore_patterns("__pycache__"))
    # Without the GIT_* scrub, inside the pre-commit hook GIT_DIR and GIT_INDEX_FILE point
    # at this repository, and `git -C outer commit` commits here (it did, once).
    genv = {**{k: v for k, v in env.items() if not k.startswith("GIT_") and k != "TUN_FEEDBACK_REPO"},
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    for g in (["init", "-q"], ["-c", "user.email=t@example.org", "-c", "user.name=t", "commit", "-q",
                               "--allow-empty", "-m", "outer"], ["tag", "outer-v9"],
              ["remote", "add", "origin", "https://forge.example/evil/outer.git"]):
        subprocess.run(["git", "-C", str(outer), *g], check=True, env=genv, capture_output=True)
    copied = str(pkg / "tools" / "tun_feedback.py")
    plog = tmp / "pkg.jsonl"
    r = run([copied, "append", "--skill", "tun-new", "--happened", "x", "--log", str(plog)], genv)
    v = json.loads(plog.read_text(encoding="utf-8"))["environment"]["tun_version"] if plog.exists() else None
    check("a packaged copy inside another repo does not take that repo's version", v == "unknown", str(v))
    (pkg / "VERSION").write_text("plugin 9.9.9 @ abc1234\n", encoding="utf-8")
    r = run([copied, "append", "--skill", "tun-new", "--happened", "y", "--log", str(plog)], genv)
    v = json.loads(plog.read_text(encoding="utf-8").splitlines()[-1])["environment"]["tun_version"]
    check("a packaged copy reports the VERSION its packager wrote", v == "plugin 9.9.9 @ abc1234", v)
    spy.unlink()
    r = run([copied, "issue", "--send", "--log", str(plog)], {**genv, "PATH": env_gh["PATH"]})
    check("a copy that names no target refuses, and never borrows the outer repo's origin",
          r.returncode != 0 and "names no repository" in r.stderr and not spy.exists()
          and "evil" not in r.stdout + r.stderr, (r.stdout + r.stderr)[-200:])
    (pkg / "FEEDBACK_REPO").write_text("forge.example/acme/packaged\n", encoding="utf-8")
    r = run([copied, "issue", "--send", "--log", str(plog)], {**genv, "PATH": env_gh["PATH"]})
    call = json.loads(spy.read_text(encoding="utf-8")) if spy.exists() else {}
    check("a packaged copy files on the FEEDBACK_REPO its packager wrote, no checkout needed",
          r.returncode == 0 and "forge.example/acme/packaged" in call.get("argv", [])
          and "(from FEEDBACK_REPO." in r.stdout, r.stderr[-160:])
    r = run([copied, "issue", "--log", str(plog)], {**genv, "TUN_FEEDBACK_REPO": "forge.example/acme/env"})
    check("TUN_FEEDBACK_REPO beats FEEDBACK_REPO", printed(r.stdout)[0].startswith("https://forge.example/acme/env "))

    # A clone of its own files on its own origin, in each URL form git hands out.
    clone = tmp / "clone"
    shutil.copytree(TOOLS, clone / "tools", ignore=shutil.ignore_patterns("__pycache__"))
    subprocess.run(["git", "-C", str(clone), "init", "-q"], check=True, env=genv, capture_output=True)
    # example.org: a git URL's user@host reads as an e-mail address, and the export scan
    # allows only the reserved example domains there.
    for url in ("git@example.org:acme/clone.git", "https://user@example.org/acme/clone.git",
                "ssh://git@example.org/acme/clone"):
        subprocess.run(["git", "-C", str(clone), "remote", "remove", "origin"], env=genv, capture_output=True)
        subprocess.run(["git", "-C", str(clone), "remote", "add", "origin", url], check=True, env=genv)
        r = run([str(clone / "tools" / "tun_feedback.py"), "issue", "--log", str(plog)], genv)
        check(f"a clone files on its own origin ({url.split(':')[0]})",
              printed(r.stdout)[0].startswith("https://example.org/acme/clone  (from origin remote"),
              (r.stdout + r.stderr)[:160])


def build_rows(out: pathlib.Path, *extra: str, tool: pathlib.Path = TOOLS) -> subprocess.CompletedProcess:
    return run([str(tool / "build_dashboard.py"), "--data", str(CSV), "--title", "Salg test",
                "--dimension", "Produkt", "--measure", "Belop", "--time", "Maaned",
                "--filters", "Region", "--source", "syntetisk", "--out", str(out), *extra])


def build_cube(out: pathlib.Path, *extra: str, tool: pathlib.Path = TOOLS) -> subprocess.CompletedProcess:
    return run([str(tool / "build_cube_dashboard.py"), "--data", str(CSV),
                "--dims", "Region,Produkt,Kanal", "--time", "Maaned", "--measures", "Belop:sum:kr",
                "--title", "Kube test", "--out", str(out), *extra])


def tree_gates(html: str) -> list[str]:
    """The tree-wide row checks, by name, that this HTML fails."""
    checks = {"row 25": core.check_no_stray_script_text, "row 24": core.check_no_target_driven_visibility,
              "row 26": core.check_no_scroll_persistent_positioning,
              "self-contained": core.check_self_contained, "placeholders": core.check_no_leftover_placeholders}
    return [name for name, fn in checks.items() if not fn(html)[0]]


def part_b(tmp: pathlib.Path) -> None:
    print("B. --feedback-to on both builders")
    for name, build in (("rows", build_rows), ("cube", build_cube)):
        plain, fb = tmp / f"{name}-plain.html", tmp / f"{name}-fb.html"
        r1 = build(plain)
        target = ("rapport@example.org" if name == "rows"
                  else "https://forge.example/acme/tun/issues/new")
        r2 = build(fb, "--feedback-to", target)
        check(f"{name}: both builds exit 0", r1.returncode == r2.returncode == 0,
              (r1.stderr + r2.stderr).strip()[-200:])
        p, f = plain.read_text(encoding="utf-8"), fb.read_text(encoding="utf-8")
        check(f"{name}: no flag, no link and no listener",
              "tun-feedback" not in p and "tilbakemelding" not in p.lower()
              and "unhandledrejection" not in p)
        check(f"{name}: flag gives exactly one link", f.count('id="tun-feedback"') == 1)
        check(f"{name}: the flagged build passes the tree row gates", tree_gates(f) == [], str(tree_gates(f)))
        href = static_href(f)
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
        subject_key = "subject" if name == "rows" else "title"
        title = "Salg test" if name == "rows" else "Kube test"
        check(f"{name}: static href points at the target",
              href.startswith("mailto:rapport@example.org?" if name == "rows" else target + "?"), href[:60])
        check(f"{name}: static subject names the artefact",
              q.get(subject_key) == [f"Tilbakemelding: {title}"], str(q.get(subject_key)))
        check(f"{name}: mailto body uses CRLF (RFC 6068), issue body LF",
              ("%0D%0A" in href) == (name == "rows") and "%0A" in href, href[-60:])
        body = (q.get("body") or [""])[0]
        check(f"{name}: static body says JavaScript did not run and names the artefact",
              "JavaScript: nei" in body and f"Artefakt: {title}" in body and "Bygget: " in body
              and "Kilde: " in body, body[-200:])

    # Without the flag the slot must add nothing: a build from a copy of the tree whose
    # templates have no slot at all is the same file, apart from the build timestamps.
    copy = tmp / "noslot"
    for d in ("tools", "templates"):
        shutil.copytree(ROOT / d, copy / d, ignore=shutil.ignore_patterns("__pycache__"))
    stamp = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?: [A-Z]{2,5})?"
                       # the cube payload too: gzip writes the build second into its header
                       r'|(?<=<script id="cube" type="application/gzip;base64">)[^<]*')
    for name, build, tpl in (("rows", build_rows, "single-file-dashboard.html"),
                             ("cube", build_cube, "cube-dashboard.html")):
        t = copy / "templates" / tpl
        src = t.read_text(encoding="utf-8")
        check(f"{name}: the template has exactly one slot", src.count("{{FEEDBACK_BLOCK}}") == 1)
        # Inline after a closing tag, so an empty slot leaves no blank line behind.
        check(f"{name}: and it sits inline", bool(re.search(r"</[a-z]+>\{\{FEEDBACK_BLOCK\}\}\n", src)))
        t.write_text(src.replace("{{FEEDBACK_BLOCK}}", ""), encoding="utf-8")
        r = build(tmp / f"{name}-noslot.html", tool=copy / "tools")
        same = r.returncode == 0 and (
            stamp.sub("T", (tmp / f"{name}-noslot.html").read_text(encoding="utf-8"))
            == stamp.sub("T", (tmp / f"{name}-plain.html").read_text(encoding="utf-8")))
        check(f"{name}: without the flag the slot adds nothing", same, r.stderr[-200:])

    for bad in ("ftp://x.example/issues", "https://x.example/o/r/issues/new#top", "not-an-address", "mailto:a@example.org?cc=c@example.org", "http://x.example/i"):
        r = build_rows(tmp / "bad.html", "--feedback-to", bad)
        check(f"refused: {bad}", r.returncode != 0 and "--feedback-to" in r.stderr, r.stderr[-160:])

    hostile = 'Salg </script><script>alert(1)</script> "x" \u2028'
    blk = feedback_link.block("a@example.org", title=hostile, built="b", source="s")
    check("a hostile title cannot add a script element to the block",
          core.check_no_stray_script_text(blk)[0] and blk.count("</script>") == 1,
          core.check_no_stray_script_text(blk)[1])
    blk = feedback_link.block("https://forge.example/g/p/-/issues/new", title="t", built="b", source="s")
    check("GitLab-style issue URL gets its own prefill keys",
          "issue%5Btitle%5D=" in blk or "issue[title]=" in blk)
    blk = feedback_link.block("https://forge.example/o/r/issues/new?labels=feedback", title="t", built="b", source="s")
    check("an issue URL that already has a query keeps it", "?labels=feedback&amp;title=" in blk)


def main() -> int:
    print("feedback: local log helper and artefact link")
    print("─" * 62)
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        part_a(tmp)
        part_b(tmp)
    print("─" * 62)
    print(f"PASS: {PASS}  FAIL: {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
