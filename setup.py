#!/usr/bin/env python3
"""
setup.py — install the Tún skills and check this machine. Cross-platform.

Replaces the old setup-skills.sh + doctor.sh, which were bash-only and full of
macOS assumptions. Works on Windows, macOS and Linux. Stdlib only.

    python3 setup.py           # check tools, run a smoke test; skills for RAIWork if installed
    python3 setup.py --check   # check only, change nothing (reports stale copies)
    python3 setup.py --link    # symlink instead of copy, for editing the skills
    python3 setup.py --hooks   # install the pre-commit gate, then exit
    python3 setup.py --tool claude                 # skills for Claude Code (repeatable: agents)

On Windows every one of these is `py -3 setup.py ...`: `python3` is not a command there
unless the Microsoft Store alias is installed, so this script prints the spelling the
machine it runs on actually has.

Read-only apart from installing the skills into ~/.raiwork/skills when RAIWork is
installed, and into the folders --tool names. The skills are in the open Agent Skills format, so other tools read the same
folders (docs/28): ~/.agents/skills is read by Codex, Gemini CLI, GitHub Copilot, VS Code
and OpenCode; ~/.claude/skills by Claude Code, VS Code and OpenCode. VS Code and OpenCode read
both, so installing both shows them each skill twice; pick the one your tool reads.

Skills are copied, not symlinked. A symlink makes ~/.raiwork/skills/<name>/SKILL.md the
same file as a tracked file in this checkout, so editing a skill silently edits the repo
on whatever branch is checked out, and switching branches rewrites the installed skills
underneath a running session. A copy can go stale instead — which --check detects.
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent
HOME = Path.home()
RAIWORK = HOME / ".raiwork"
SKILLS_DIR = RAIWORK / "skills"
# --tool name -> the folder that tool reads. Same files everywhere; see the docstring.
TOOLS = {"raiwork": SKILLS_DIR,
         "agents": HOME / ".agents" / "skills",
         "claude": HOME / ".claude" / "skills"}
IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
# How a person on this machine starts Python. `python3` does not exist on Windows unless the
# Microsoft Store alias is installed, and telling someone to run a command they do not have
# is the same as telling them nothing. Every hint this script prints uses this.
PY_CMD = "py -3" if IS_WIN else "python3"

fixes: list[str] = []
blocking = 0

# Windows terminals handle ANSI fine on modern builds; degrade gracefully anyway.
if IS_WIN:
    os.system("")  # enables VT100 processing on Windows 10+
G, Y, R, B, D, Z = "\033[32m", "\033[33m", "\033[31m", "\033[1m", "\033[2m", "\033[0m"


def section(t): print(f"\n{B}{t}{Z}")
def ok(a, b=""):   print(f"  {G}OK{Z}   {a:<30} {b}")
def warn(a, b=""): print(f"  {Y}WARN{Z} {a:<30} {b}")
def bad(a, b=""):  print(f"  {R}FAIL{Z} {a:<30} {b}")
def fix(c): fixes.append(c)


# ---------------------------------------------------------------- skills
# Skills are COPIED into ~/.raiwork/skills, not symlinked.
#
# Symlinking looks strictly better — one source of truth, edits are live, nothing goes
# stale — and it was what this script did until it bit us. The problem is that the link
# makes ~/.raiwork/skills/<name>/SKILL.md the same file as a tracked file in this
# checkout, so:
#
#   * "editing a skill" silently edits the repo working tree, on whatever branch happens
#     to be checked out, and the change turns up in the next unrelated commit or PR;
#   * switching branches rewrites the installed skills underneath a running session, and
#     a branch that does not contain a skill makes it vanish mid-task;
#   * git checkout / stash / reset can revert a skill edit nobody remembers making.
#
# A copy trades those failures for one much smaller one: it can go stale. That is worth
# it, because staleness is detectable and the others are not — `--check` compares the
# copy against the repo and tells you to re-run. Authors who do want live editing can
# ask for the old behaviour with --link, and are told what they are getting.

MARKER = ".installed-by-tun"
# Markers written by earlier versions of this script. The marker is written inside every
# skill directory this script installs, and its presence is the only thing that separates
# "our copy, safe to replace" from "a skill the user wrote, leave alone". So a renamed
# marker must keep recognising every old one: drop a name from this tuple and each install
# carrying it turns into "you already have a skill with this name", silently never
# refreshed and never cleaned up. A run replaces an old marker with MARKER.
#: Markers earlier versions wrote. Composed from fragments because the exported tree must not
#: carry the former repository name as text, and this tuple is the one place that needs it.
LEGACY_MARKERS = (".installed-by-" + "onedrive" + "-native-dashboards",)
ALL_MARKERS = (MARKER, *LEGACY_MARKERS)

SKIP_NAMES = {*ALL_MARKERS, "__pycache__", ".DS_Store"}


def _is_ours(dst: Path) -> bool:
    """A real directory carrying any marker this script has ever written."""
    return (dst.is_dir() and not dst.is_symlink()
            and any((dst / m).is_file() for m in ALL_MARKERS))


def _files(root: Path) -> dict[str, bytes]:
    """Relative path -> content, for comparing an installed copy with its source."""
    out: dict[str, bytes] = {}
    for p in sorted(root.rglob("*")):
        if p.is_dir() or any(part in SKIP_NAMES for part in p.relative_to(root).parts):
            continue
        out[str(p.relative_to(root)).replace(os.sep, "/")] = p.read_bytes()
    return out


def _drift(src: Path, dst: Path) -> int:
    """How many files differ between the source skill and the installed copy."""
    a, b = _files(src), _files(dst)
    return len(set(a) ^ set(b)) + sum(1 for k in set(a) & set(b) if a[k] != b[k])


def _install_copy(src: Path, dst: Path) -> None:
    if dst.is_symlink():
        dst.unlink()
    elif dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*SKIP_NAMES))
    # Never write the marker through a link. If dst were still a symlink at this point,
    # the write would land inside the source repository — which is exactly the coupling
    # this function exists to remove, and it is silent when it happens.
    if dst.is_symlink() or dst.resolve() == src.resolve():
        raise OSError(f"refusing to write the install marker through a link: {dst}")
    (dst / MARKER).write_text(
        f"Installed by {PY_CMD} setup.py. Safe to delete.\n"
        f"source: {src}\n"
        "Edit the skill in that repo and re-run setup.py; edits made here are overwritten.\n"
    )


def _cleanup_renamed(sources: list[tuple[str, Path]], check_only: bool,
                     skills_dir: Path = SKILLS_DIR) -> None:
    """Remove an install left behind by a skill that has since been renamed or deleted in
    this repo (e.g. dashboard-new -> tun-new).

    Only ever touches a directory that carries a marker (MARKER or a legacy one) — the
    mark _install_copy() itself writes. That is what tells "our old copy, safe to remove"
    apart from a skill the user wrote under a name that happens to collide, or a foreign
    symlink another tool owns;
    neither of those carries our marker, so neither is touched here.
    """
    if not skills_dir.is_dir():
        return
    current_names = {src.name for _, src in sources}
    for dst in sorted(skills_dir.iterdir()):
        if dst.name in current_names or not _is_ours(dst):
            continue
        label = f"{dst.name}  (stale)"
        if check_only:
            warn(label, "installed by a skill no longer in this repo — renamed or removed")
            fix(f"{_rerun(skills_dir)}   # removes the stale {_show(skills_dir)}/{dst.name}")
        else:
            shutil.rmtree(dst)
            ok(label, "removed — no longer a skill in this repo")


def _rerun(skills_dir: Path) -> str:
    """The command that repairs skills_dir. RAIWork's folder is the default; any other
    tool's folder needs its --tool, or the advice would install nothing."""
    tool = next((k for k, v in TOOLS.items() if v == skills_dir and k != "raiwork"), None)
    return PY_CMD + " setup.py" + (f" --tool {tool}" if tool else "")


def _show(path: Path) -> str:
    """~/... for messages, so a fix line can be pasted on any machine."""
    try:
        return "~/" + path.relative_to(HOME).as_posix()
    except ValueError:
        return str(path)


def install_skills(check_only: bool, use_symlinks: bool = False,
                   skills_dir: Path = SKILLS_DIR) -> None:
    section(f"Skills  {D}({_show(skills_dir)}){Z}")
    global blocking
    if skills_dir == SKILLS_DIR and not RAIWORK.exists():
        bad("~/.raiwork", "RAIWork not installed?")
        fix("Install RAIWork - see docs/04-onboarding.md")
        blocking += 1
        return
    if not check_only:
        skills_dir.mkdir(parents=True, exist_ok=True)

    # Two groups, flattened into ~/.raiwork/skills/ because RAIWork looks one level deep.
    # The directory split exists for the reader, not the loader: skills/ is what this
    # project produces, skills/dev/ is how any project gets built. See skills/README.md.
    sources = []
    for p in sorted((REPO / "skills").iterdir()):
        if p.is_dir() and p.name != "dev":
            sources.append(("project", p))
    dev_dir = REPO / "skills" / "dev"
    if dev_dir.is_dir():
        for p in sorted(dev_dir.iterdir()):
            if p.is_dir():
                sources.append(("dev", p))

    _cleanup_renamed(sources, check_only, skills_dir)

    for group, src in sources:
        label = src.name if group == "project" else f"{src.name}  (dev)"
        dst = skills_dir / src.name

        # Whose is it? Answer this before touching anything.
        ours_link = dst.is_symlink() and Path(os.readlink(dst)).resolve() == src.resolve()
        foreign_link = dst.is_symlink() and not ours_link
        ours_copy = _is_ours(dst)
        user_own = dst.is_dir() and not dst.is_symlink() and not ours_copy
        old_marker = ours_copy and not (dst / MARKER).is_file()

        if check_only:
            if foreign_link:
                ok(label, f"provided by {os.readlink(dst)}")
            elif ours_link:
                # Cannot tell an opted-in --link from an install made before copying was
                # the default, so state the fact rather than guessing the intent.
                ok(label, "symlinked into this repo — edits here change the repo")
            elif ours_copy:
                n = _drift(src, dst)
                if n:
                    warn(label, f"stale — {n} file(s) differ from this repo")
                    fix(_rerun(skills_dir))
                elif old_marker:
                    warn(label, "up to date, but carries the old install marker")
                    fix(f"{_rerun(skills_dir)}   # replaces the old marker")
                else:
                    ok(label, "installed, up to date")
            elif user_own:
                warn(label, "your own skill with this name — not managed here")
            else:
                bad(label, "not installed")
                fix(_rerun(skills_dir))
            continue

        if foreign_link:
            # Someone else — usually the dotfiles repo — owns this name, and their link is
            # canonical. Taking it over would move authority for a global tool into this
            # project checkout. The skill is installed and usable; that is the right outcome,
            # so no fix is suggested.
            ok(label, f"provided by {os.readlink(dst)}")
            continue

        if user_own:
            warn(label, "you already have a skill with this name — left alone")
            fix(f"rename or remove {_show(skills_dir)}/{src.name} "
                f"if you want this repo's version instead")
            continue

        if use_symlinks:
            try:
                if ours_link:
                    ok(label, "already linked"); continue
                if dst.exists() or dst.is_symlink():
                    _remove(dst)
                os.symlink(src, dst, target_is_directory=True)
                ok(label, "linked (edits here change the repo)")
            except OSError as e:
                bad(label, f"could not link: {e}")
                blocking += 1
            continue

        try:
            if ours_copy and not old_marker and _drift(src, dst) == 0:
                ok(label, "already installed"); continue
            was_link = ours_link
            _install_copy(src, dst)
            ok(label, "migrated from symlink to copy" if was_link else
                      "upgraded from the old install marker" if old_marker else "installed")
        except OSError as e:
            bad(label, f"could not install: {e}")
            blocking += 1

    if not check_only and not use_symlinks:
        print(f"  {D}note: these are copies. Edit the skill in this repo, then re-run"
              f"\n        this script. `--check` reports copies that have gone stale.{Z}")


def _remove(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


# ---------------------------------------------------------------- tools
def which(name: str) -> str | None:
    return shutil.which(name)


# Playwright is an optional extra (pyproject.toml, `verify`), so it usually lives in the
# repo's uv environment, not in whatever python3 runs this script. Asking only this
# interpreter reported "FAIL playwright" on machines where `uv run` verifies fine.
VERIFY_FIX = "uv sync --extra verify && uv run playwright install chromium"
_BROWSER_PROBE = ("from playwright.sync_api import sync_playwright\n"
                  "with sync_playwright() as p:\n"
                  "    p.chromium.launch().close()\n")
VERIFY_PY: list[str] | None = None  # set by check_tools(): a Python that can render


SMOKE_TIMEOUT = 300  # seconds per smoke step: a hook must be able to fail, not hang


def run_bounded(cmd: list[str], seconds: int = SMOKE_TIMEOUT) -> subprocess.CompletedProcess:
    """subprocess.run with a ceiling. A hook that waits forever is worse than one that fails.

    subprocess.run raises on timeout and every caller here wants a return code, so a
    timeout becomes 124 with the reason on stderr, the way a shell reports it.
    """
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=seconds)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", f"timed out after {seconds} s")


def _probe(cmd: list[str]) -> bool:
    try:
        return subprocess.run(cmd + ["-c", _BROWSER_PROBE], capture_output=True,
                              timeout=120).returncode == 0
    except Exception:
        return False


def browser_python() -> tuple[list[str] | None, str]:
    """A Python command that can launch Chromium through Playwright, and where it is.

    This interpreter first, then the repo's uv environment. `uv run --no-sync` never
    installs anything, but it does create an empty .venv when none exists, so uv is only
    asked when an environment is already there: --check must change nothing.
    """
    if _probe([sys.executable]):
        return [sys.executable], "this Python"
    uv = which("uv")
    if uv and ((REPO / ".venv").is_dir() or os.environ.get("UV_PROJECT_ENVIRONMENT")):
        cmd = [uv, "run", "--no-sync", "--project", str(REPO), "--extra", "verify", "python"]
        if _probe(cmd):
            return cmd, "the uv environment"
    return None, ""


def check_tools() -> None:
    section("Required tools")
    global blocking

    py = sys.version_info
    ok(PY_CMD, f"{py.major}.{py.minor}.{py.micro}")

    if which("git"):
        ok("git")
    else:
        bad("git", "NOT FOUND"); fix("Install git"); blocking += 1

    if which("uv"):
        ok("uv")
    else:
        warn("uv", "NOT FOUND - needed to install anything (never use pip)")
        fix("winget install astral-sh.uv" if IS_WIN else
            ("brew install uv" if IS_MAC else "curl -LsSf https://astral.sh/uv/install.sh | sh"))

    global VERIFY_PY
    VERIFY_PY, where = browser_python()
    if VERIFY_PY:
        ok("playwright + chromium", f"render verification available ({where})")
    else:
        # An optional extra, so a WARN with the command, not a FAIL. The verify tools
        # themselves still refuse to pass a file they could not open in a browser.
        warn("playwright + chromium", "not here or in the uv env - no render verification")
        fix(VERIFY_FIX)


def check_repo() -> None:
    section("Repo tooling")
    global blocking
    for rel in ("tools/build_dashboard.py", "tools/build_cube_dashboard.py",
                "tools/verify_dashboard.py", "tools/check_tree.py", "tools/tree_scan.py",
                "tools/check_no_real_data.py", "tools/scan_history.py",
                "tools/check_core_is_generic.py", "tools/core_generic_baseline.json",
                "templates/single-file-dashboard.html", "templates/cube-dashboard.html",
                "probe/tenant-probe.py"):
        if (REPO / rel).exists():
            ok(rel)
        else:
            bad(rel, "MISSING"); blocking += 1


# ---------------------------------------------------------------- git hooks
# This host has no CI (the public repository runs .github/workflows/gates.yml). GHE
# Actions runners are org-disabled (docs/08), and the probe that
# proved it — a probe run, job `probe`, labels ["ubuntu-latest"] — died in three seconds
# with zero steps because no runner picked it up. So the pre-commit hook is the only
# automatic gate available, which makes "is it installed" a question worth reporting.
#
# Installed by pointing core.hooksPath at the tracked tools/hooks directory, rather than
# copying into .git/hooks. The hook is then version-controlled and updates with a pull,
# and there is no second copy to go stale — the same drift problem install_skills() has to
# work around for skills, avoided here because a hook has no reason to be edited per
# machine.
HOOKS_REL = "tools/hooks"


def _hooks_path() -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(REPO), "config", "--get", "core.hooksPath"],
                             capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    return out.stdout.strip() or None


def install_hooks(check_only: bool) -> None:
    section("Git hooks")
    global blocking
    hook = REPO / HOOKS_REL / "pre-commit"
    if not hook.exists():
        bad("tools/hooks/pre-commit", "MISSING"); blocking += 1
        return
    if not os.access(hook, os.X_OK):
        if check_only:
            warn("pre-commit", "not executable"); fix("chmod +x tools/hooks/pre-commit")
        else:
            hook.chmod(hook.stat().st_mode | 0o111)
            ok("pre-commit", "made executable")

    current = _hooks_path()
    if current == HOOKS_REL:
        ok("core.hooksPath", HOOKS_REL)
        return
    if check_only:
        warn("core.hooksPath", f"{current or 'unset'} — gates do not run on commit")
        fix(f"{PY_CMD} setup.py --hooks")
        return
    if current:
        # Someone else owns the hooks path. Overwriting it silently could disable their
        # hooks, so report and let a human decide.
        warn("core.hooksPath", f"already set to {current} — leaving it alone")
        fix(f"point it at {HOOKS_REL} by hand, or merge the two hook sets")
        return
    try:
        subprocess.run(["git", "-C", str(REPO), "config", "core.hooksPath", HOOKS_REL],
                       check=True, capture_output=True, timeout=10)
    except Exception as exc:
        bad("core.hooksPath", f"could not set: {exc}"); blocking += 1
        return
    ok("core.hooksPath", f"set to {HOOKS_REL}")


# ---------------------------------------------------------------- raiwork / mcp
def raiwork_cli() -> str | None:
    if c := which("raiwork"):
        return c
    candidates = [
        Path("/Applications/raiwork.app/Contents/MacOS/raiwork"),
        HOME / "AppData/Local/Programs/raiwork/raiwork.exe",
        HOME / "AppData/Local/raiwork/raiwork.exe",
        Path("C:/Program Files/raiwork/raiwork.exe"),
    ]
    return next((str(p) for p in candidates if p.exists()), None)


def check_mcp() -> None:
    section("MCP servers")
    global blocking
    if not RAIWORK.exists():
        warn("RAIWork", "not installed - skipping its MCP checks")
        return
    cli = raiwork_cli()
    if not cli:
        warn("raiwork CLI", "not found - skipping MCP checks")
        return
    try:
        # Two seconds, not sixty: this is a report, not a gate, and a CLI that cannot
        # list its servers in two seconds is unavailable for the purpose. The suite in
        # tests/test_skill_links.py runs this script about nine times, so a minute each
        # was minutes of the pre-commit spent waiting on a command whose answer is a WARN.
        out = subprocess.run([cli, "mcp", "list"], capture_output=True, text=True,
                             timeout=2).stdout
    except Exception as e:
        warn("raiwork mcp list", f"could not run: {e}")
        return
    line = next((l for l in out.splitlines() if l.startswith("ms365")), "")
    if not line:
        bad("ms365", "not configured - REQUIRED to publish")
        fix("Add ms365 in RAIWork settings, then: raiwork mcp auth ms365")
        blocking += 1
    elif "authenticated" in line or "refresh ready" in line:
        ok("ms365", "authenticated - SharePoint/OneDrive reachable")
    else:
        warn("ms365", "configured but not authenticated")
        fix("raiwork mcp auth ms365")


# ---------------------------------------------------------------- onedrive
def check_onedrive() -> None:
    section("OneDrive sync folder (for publishing)")
    roots: list[Path] = []
    if IS_MAC:
        cs = HOME / "Library/CloudStorage"
        if cs.exists():
            roots = [p for p in cs.iterdir() if "OneDrive" in p.name or "SharePoint" in p.name]
    else:
        # Windows/Linux: OneDrive Business syncs to ~/<Tenant Name> or ~/OneDrive - <Tenant>
        env = [os.environ.get("OneDriveCommercial"), os.environ.get("OneDrive")]
        roots = [Path(e) for e in env if e and Path(e).exists()]
        roots += [p for p in HOME.iterdir()
                  if p.is_dir() and ("OneDrive" in p.name or "Eksempel AS" in p.name)] if HOME.exists() else []
    roots = sorted(set(roots))
    if roots:
        for r in roots[:4]:
            ok("synced library", str(r))
    else:
        warn("OneDrive sync", "no synced library found - publish via Graph upload instead")


# ---------------------------------------------------------------- smoke
def smoke() -> None:
    section("End-to-end smoke test")
    if blocking:
        warn("skipped", "fix the failures above first")
        return
    data = REPO / "examples/01-hello-dashboard/salgsdata.csv"
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "smoke.html"
        build = run_bounded(
            [sys.executable, str(REPO / "tools/build_dashboard.py"),
             "--data", str(data), "--title", "Setup smoke test",
             "--dimension", "Produkt", "--measure", "Belop", "--time", "Maaned",
             "--filters", "Region", "--out", str(out)])
        if build.returncode != 0:
            bad("build", (build.stderr or build.stdout).strip().splitlines()[-1:] or "failed")
            return
        ok("build", "produced a dashboard")
        if not VERIFY_PY:
            warn("verify", "skipped - no Playwright to render with")
            fix(VERIFY_FIX)
            return
        ver = run_bounded(
            [*VERIFY_PY, str(REPO / "tools/verify_dashboard.py"), str(out)])
        if ver.returncode == 0:
            ok("verify", "it renders and is interactive")
        else:
            bad("verify", "built but failed verification")
            fix(f"{PY_CMD} tools/verify_dashboard.py <a built dashboard>   # see detail")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="check only, change nothing")
    ap.add_argument("--hooks", action="store_true",
                    help="install the git pre-commit hook (sets core.hooksPath to "
                         "tools/hooks) and exit. CI runs only on the public repository, "
                         "so in this clone the hook is the only automatic gate (docs/06).")
    ap.add_argument("--link", action="store_true",
                    help="symlink the skills instead of copying them — for editing the "
                         "skills themselves. Edits then change this repo's working tree.")
    ap.add_argument("--tool", action="append", choices=list(TOOLS), default=[],
                    help="install into the folder this tool reads (repeatable; RAIWork is "
                         "included when ~/.raiwork exists): "
                         "agents = ~/.agents/skills (Codex, Gemini CLI, Copilot, VS Code, OpenCode), "
                         "claude = ~/.claude/skills (Claude Code, VS Code, OpenCode)")
    args = ap.parse_args()

    print(f"{B}Tún setup + check{Z}  {D}({platform.system()}, {REPO}){Z}")
    if args.hooks:
        install_hooks(check_only=False)
        print()
        for f in dict.fromkeys(fixes):
            print(f"  - {f}")
        return 1 if blocking else 0

    check_tools()
    check_repo()
    install_hooks(args.check)
    # RAIWork gets the skills when it is installed, as before. Anyone else names
    # their tool; with neither, say how instead of failing on a tool they never had.
    tools = (["raiwork"] if RAIWORK.exists() else []) + args.tool
    if not tools:
        section("Skills")
        warn("no AI tool chosen", "skills not installed")
        fix(f"Install the skills for your AI tool: {PY_CMD} setup.py --tool claude "
            "(Claude Code) or --tool agents (Codex, Gemini CLI, Copilot, VS Code, OpenCode)")
    for tool in dict.fromkeys(tools):
        install_skills(args.check, use_symlinks=args.link, skills_dir=TOOLS[tool])
    check_mcp()
    check_onedrive()
    smoke()

    print("\n" + "-" * 60)
    if not fixes:
        print(f"{G}Everything the Tún skills need is in place.{Z}\n")
        print("  Open your AI tool in this repo and try:\n")
        print('    "Build me a dashboard from examples/01-hello-dashboard/salgsdata.csv')
        print('     showing amounts by product and the trend over months,')
        print('     filterable by region."\n')
    else:
        print(f"{B}To fix:{Z}")
        for f in dict.fromkeys(fixes):
            print(f"  - {f}")
        print(f"\n{D}Detail: docs/05-toolchain.md{Z}\n")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
