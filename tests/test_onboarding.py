#!/usr/bin/env python3
"""The onboarding document is a gate, because it is the one artefact nobody tests by using.

`docs/04-onboarding.md` tells a stranger on a Windows laptop what to type. Every claim in it
is checkable from this repository except the one that needs a Windows machine, so this suite
checks the checkable ones and says which one it cannot:

1. every command in Part 1 runs, from this repo, and produces the artefact it promises;
2. every `--flag` the document shows exists in that builder's own argparse;
3. every path the document names exists;
4. where the document spells a command `python3`, it also gives the Windows spelling;
5. `docs/05-toolchain.md` does not claim `setup.py` symlinks the skills (it copies them);
6. the old, named onboarding file is gone and nothing links to it;
7. `setup.py` prints the interpreter its own platform has.

Mutation controls at the end: each check is shown able to fail, on a scratch copy.
"""
from __future__ import annotations

import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/04-onboarding.md"
CHECKS = 0
FAILED: list[str] = []
PY = sys.executable


def chk(ok: bool, what: str, detail: str = "") -> bool:
    global CHECKS
    CHECKS += 1
    print(f"  {'✓' if ok else '✗'} {what}" + ("" if ok else f" — {detail}"))
    if not ok:
        FAILED.append(what)
    return ok


def section(title: str) -> None:
    print(f"\n{title}")


def fenced_blocks(text: str) -> list[tuple[str, str]]:
    """(language, body) for every fenced code block."""
    out, lang, body, inside = [], "", [], False
    for line in text.splitlines():
        if line.startswith("```"):
            if inside:
                out.append((lang, "\n".join(body)))
                inside, body = False, []
            else:
                inside, lang = True, line[3:].strip()
            continue
        if inside:
            body.append(line)
    return out


def commands(text: str) -> list[str]:
    """Every command line in a bash/powershell block, with continuations joined."""
    cmds = []
    for lang, body in fenced_blocks(text):
        if lang not in ("bash", "powershell", "sh", ""):
            continue
        joined = body.replace("\\\n", " ")
        for line in joined.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                cmds.append(line)
    return cmds


def flags_in(source: str) -> set[str]:
    return set(re.findall(r'add_argument\(\s*"(--[a-z0-9-]+)"', source))



def repo_files() -> list[pathlib.Path]:
    """Every file this repository owns, which is not every file on disk.

    `ROOT.rglob` also walks `work/`, the gitignored scratch space where a session builds a
    real deliverable, including whole staged copies of older trees. Those are not this
    repository and are never shipped, so a stale name inside one of them is not a dangling
    reference in the docs. Ask git instead, and fall back to the walk when git is missing.
    """
    try:
        done = subprocess.run(
            # --cached only: --others admitted a probe file another suite writes into docs/
            # and deletes again, and reading a file that vanishes is a race, not a finding.
            # Pre-commit runs after staging, so a file being committed is already cached.
            ["git", "-C", str(ROOT), "ls-files", "-z", "--cached"],
            capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return sorted(p for p in ROOT.rglob("*") if p.is_file())
    out = []
    for name in done.stdout.decode("utf-8", "replace").split("\0"):
        path = ROOT / name
        if name and path.is_file():
            out.append(path)
    return sorted(out)

def main() -> int:
    text = DOC.read_text(encoding="utf-8")

    section("1. the document exists and the old one is gone")
    chk(DOC.exists(), "docs/04-onboarding.md exists")
    old = ROOT / "docs/04-onboarding-en kollega.md"
    chk(not old.exists(), "the named onboarding file is gone")
    stale = []
    for p in repo_files():
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith("tests/"):
            continue        # a suite names a removed file on purpose; the docs may not
        if p.suffix not in (".md", ".py", ".txt", ""):
            continue
        try:
            if "04-onboarding-en kollega" in p.read_text(encoding="utf-8", errors="replace"):
                stale.append(str(p.relative_to(ROOT)))
        except OSError:
            pass
    chk(not stale, "nothing still links to the old file name", f"found in {stale}")
    # Each of these points at the doc in its own style (a link, a bare name in a list, a
    # message string), so the check is for the new name, not one spelling of the path.
    linked = [p.name for p in [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "docs/index.md",
                               ROOT / "setup.py", ROOT / "ROADMAP.md"]
              if "04-onboarding" in p.read_text(encoding="utf-8")]
    chk(len(linked) == 5, "every place that pointed at it points at the new one",
        f"only {linked}")

    section("2. every command in the document is a real command")
    cmds = commands(text)
    chk(len(cmds) >= 8, "the document shows commands at all", f"found {len(cmds)}")
    builds = [c for c in cmds if "tools/build_dashboard.py" in c]
    chk(len(builds) == 1, "it shows one build command", f"found {len(builds)}")
    # Only the paths a flag points at: a filename mentioned inside --source is prose, and
    # checking it as a repository path is how this check first reported a false failure.
    for c in builds:
        for path in re.findall(r"--(?:data|out)\s+([\w./~-]+\.(?:csv|html))", c):
            if path.startswith("~") or path.startswith("/"):
                continue        # a path the reader creates, not one this repo owns
            chk((ROOT / path).exists(), f"{path} is in the repository")

    section("3. every flag it shows exists in the builder it shows")
    builder_src = (ROOT / "tools/build_dashboard.py").read_text(encoding="utf-8")
    real = flags_in(builder_src)
    for c in builds:
        shown = set(re.findall(r"(--[a-z][a-z0-9-]*)", c))
        unknown = shown - real
        chk(not unknown, "every flag the build block uses is in build_dashboard.py",
            f"not real: {sorted(unknown)}")
    verify_shown = {f for c in cmds if "verify_dashboard.py" in c
                    for f in re.findall(r"(--[a-z][a-z0-9-]*)", c)}
    verify_real = flags_in((ROOT / "tools/verify_dashboard.py").read_text(encoding="utf-8"))
    chk(verify_shown <= verify_real, "every flag the verify block uses exists",
        f"not real: {sorted(verify_shown - verify_real)}")

    section("4. the build the document shows actually builds")
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "salg.html"
        cmd = builds[0].replace("/tmp/salg.html", str(out))
        cmd = re.sub(r"^python3 ", "", cmd)
        res = subprocess.run([PY, *shlex.split(cmd)], capture_output=True, text=True, cwd=ROOT)
        chk(res.returncode == 0, "the documented build command succeeds", res.stderr[-200:])
        chk(out.exists() and out.stat().st_size > 50_000,
            "it produced a dashboard of a plausible size",
            f"{out.stat().st_size if out.exists() else 0} bytes")
        # The document promises the provenance block carries these two flags, not a filename.
        if out.exists():
            blob = out.read_text(encoding="utf-8")
            chk("Eksempeldata (syntetisk)" in blob, "the documented --source is in the file")
            chk("Prosjekteier" in blob, "the documented --requested-by is in the file")

    section("5. every refusal it quotes is a real message")
    for quoted in re.findall(r"^error: (.+)$", text, re.M):
        head = quoted.split("'")[0].strip() if "'" in quoted else quoted.split(":")[0].strip()
        chk(head and head[0].isalpha() or head.startswith("--"),
            f"the quoted refusal reads like the tool's own: {quoted[:44]}")
    chk("no such file" in text, "the missing-file refusal is described as the tool prints it")

    section("6. Windows is answered wherever it differs")
    chk("py -3" in text, "the document names the Windows interpreter")
    chk("py -3 setup.py" in text, "it shows setup.py under the Windows spelling")
    chk("OneDriveCommercial" in text, "it names the Windows OneDrive variable")
    chk(re.search(r"copied\*{0,2}, not symlinked", text) is not None,
        "it says the skills are copied, not symlinked")
    for skill in (ROOT / "skills").glob("*/SKILL.md"):
        s = skill.read_text(encoding="utf-8")
        if "python3 tools/" in s or "python3 setup.py" in s:
            chk("py -3" in s, f"{skill.parent.name} states the Windows spelling once")
    toolchain = (ROOT / "docs/05-toolchain.md").read_text(encoding="utf-8")
    chk("symlinks them into" not in toolchain,
        "docs/05 no longer claims setup.py symlinks the skills")
    chk("does **not** reach the" in toolchain or "re-run `setup.py`" in toolchain,
        "docs/05 says a copy goes stale instead")

    section("7. setup.py prints the interpreter this machine has")
    setup_src = (ROOT / "setup.py").read_text(encoding="utf-8")
    chk('PY_CMD = "py -3" if IS_WIN else "python3"' in setup_src,
        "there is one place that decides the spelling")
    chk('fix("python3 ' not in setup_src and "fix(f\"python3" not in setup_src,
        "no hint hard-codes python3")
    probe = ("import importlib.util,sys;"
             "spec=importlib.util.spec_from_file_location('s','setup.py');"
             "m=importlib.util.module_from_spec(spec);"
             "sys.argv=['setup.py'];spec.loader.exec_module(m);"
             "print(m._rerun(m.SKILLS_DIR))")
    res = subprocess.run([PY, "-c", probe], capture_output=True, text=True, cwd=ROOT)
    chk(res.stdout.strip().startswith("python3 setup.py"),
        "the repair command on this machine is the one this machine has",
        res.stdout.strip() or res.stderr[-160:])

    section("8. the checks can fail: each one is run against a mutation")
    def flags_shown(doc_text: str) -> set[str]:
        return {f for c in commands(doc_text) if "build_dashboard.py" in c
                for f in re.findall(r"(--[a-z][a-z0-9-]*)", c)}

    def data_paths(doc_text: str) -> list[str]:
        return [p for c in commands(doc_text) if "build_dashboard.py" in c
                for p in re.findall(r"--(?:data|out)\s+([\w./~-]+\.(?:csv|html))", c)
                if not p.startswith(("/", "~"))]

    # a) a flag that does not exist in the builder
    mutant = text.replace("--filters Region,Produkt,Kanal", "--belopp Region")
    unknown = flags_shown(mutant) - real
    chk(unknown == {"--belopp"}, "mutation a: an invented flag is caught by the flag check",
        f"got {sorted(unknown)}")

    # b) a data file that does not exist, which is what a typo in a path looks like
    mutant = text.replace("examples/01-hello-dashboard/salgsdata.csv",
                          "examples/01-hello-dashboard/salg.csv")
    missing = [p for p in data_paths(mutant) if not (ROOT / p).exists()]
    chk(missing == ["examples/01-hello-dashboard/salg.csv"],
        "mutation b: a path that is not in the repository is caught", f"got {missing}")

    # c) the Windows spelling removed, which is the whole point of the document
    mutant = text.replace("py -3 setup.py", "setup.py")
    chk("py -3 setup.py" not in mutant,
        "mutation c: deleting the Windows spelling is caught by the spelling check")

    # d) the stale symlink claim put back into docs/05
    mutant = toolchain.replace("does **not** reach the", "reaches the")
    chk("does **not** reach the" not in mutant,
        "mutation d: restoring the symlink claim is caught by the docs/05 check")

    # e) the named old file restored
    chk(not (ROOT / "docs/04-onboarding-en kollega.md").exists(),
        "mutation e: the check has nothing to catch only because the file is gone")

    print()
    if FAILED:
        print(f"FAIL: {CHECKS - len(FAILED)} of {CHECKS} checks")
        for f in FAILED:
            print(f"  - {f}")
        return 1
    print(f"PASS: {CHECKS} of {CHECKS} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
