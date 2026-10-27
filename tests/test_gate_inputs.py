#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""A gate is only as good as its inputs, and its inputs drift silently.

Three gates in this repository broke the same way: a README documented a command for a
file that had been renamed, verify_viewports' select and table assertions fired on an
artefact whose CSS had moved, and the idea picture's mutation control mutated a rule the
artefact no longer carried, so it reported "caught" while checking nothing. In each case
the gate still ran and still printed a colour. What had changed was the thing it pointed
at.

This test points at those things directly, in a second, with no browser:

1. every verify command a README documents resolves: the tool exists, and so does every
   `.html` file it names;
2. every `examples/...` path a suite resolves is tracked by git. This is ROADMAP C6: a
   suite built from `examples/33-comparison/forrige.csv`, which `.gitignore` excludes, so
   it passed in a checkout where someone had generated the file and failed on a fresh
   worktree. `check_all` looked like a race; the tree decided the answer;
3. every mutation anchor in every example verifier that uses (needle, replacement) tuples
   occurs exactly once in the artefact that verifier names, read by `ast` rather than by
   importing the module (importing pulls in Playwright);
4. mutation controls: an anchor is broken in a copy of the text, and a gitignored read is
   written to a probe file, and the same checks must notice. A run that checks nothing
   cannot pass.

Stdlib only, and it prints how many of each it resolved. A gate that derives its own
input list can pass vacuously; the counts are the evidence that it did not.
"""
import ast
import pathlib
import shlex
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES = ("AGENTS.md", "examples/*/README.md")

passed = failed = 0


def chk(label: str, ok: bool, detail: str = "", n: int | None = None) -> bool:
    global passed, failed
    if n is not None and n == 0:
        ok, detail = False, "resolved 0 items"
    if ok:
        passed += 1
        print(f"  PASS {label}" + (f" ({n})" if n is not None else ""))
    else:
        failed += 1
        print(f"  FAIL {label}" + (f": {detail}" if detail else ""))
    return ok


def fenced_lines(text: str) -> list[str]:
    """The lines inside ``` fences, with backslash continuations joined."""
    out: list[str] = []
    inside = False
    pending = ""
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            inside = not inside
            continue
        if not inside:
            continue
        pending += line.rstrip("\\").rstrip()
        if line.rstrip().endswith("\\"):
            pending += " "
            continue
        out.append(pending)
        pending = ""
    return out


def documented_commands() -> list[tuple[pathlib.Path, list[str]]]:
    found = []
    for pattern in SOURCES:
        for doc in sorted(ROOT.glob(pattern)):
            for line in fenced_lines(doc.read_text(encoding="utf-8")):
                try:
                    words = shlex.split(line, comments=True)
                except ValueError:
                    continue
                # a command, not a mention: the verify tool is the first word, or it
                # follows the interpreter. The layout block in AGENTS.md lists the same
                # filenames as prose, and those are not commands a reader runs.
                for i, w in enumerate(words):
                    if not (w.endswith(".py") and "verify_" in w):
                        continue
                    if i == 0 or words[i - 1] in {"python", "python3", "py"}:
                        found.append((doc, words))
                    break
    return found


# ---------------------------------------------------------------------------
# 1. the files a documented command names
# ---------------------------------------------------------------------------

def check_documented_paths() -> int:
    print("\n1. every documented verify command names files that exist")
    cmds = documented_commands()
    chk("documented verify commands were found at all", bool(cmds), n=len(cmds))
    missing = []
    for doc, words in cmds:
        # a README may write its command from the repo root (AGENTS.md, most examples) or
        # from its own directory; both are honest, so a path counts if either resolves.
        bases = (doc.parent, ROOT) if doc.parent != ROOT else (ROOT,)
        for w in words:
            if not (w.endswith(".py") or w.endswith(".html")):
                continue
            if not any((b / w).resolve().exists() for b in bases):
                missing.append(f"{doc.relative_to(ROOT)}: {w}")
    chk("every tool and artefact a README documents exists", not missing,
        "; ".join(missing[:4]), n=len(cmds))
    return len(cmds)


# ---------------------------------------------------------------------------
# 2. a suite may not read a file git does not carry
# ---------------------------------------------------------------------------

def _path_parts(node: ast.expr, names: dict[str, tuple[str, ...]]) -> tuple[str, ...] | None:
    """A path expression as literal parts, or None when it cannot be resolved by reading."""
    # The root, whatever shape it is written in: `Path(__file__).parent.parent`,
    # `.resolve().parents[1]`, a module-level constant. `ast.unparse` is what makes the
    # several spellings one case instead of one branch each.
    text = ast.unparse(node)
    if "__file__" in text:
        return ("",)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _path_parts(node.left, names)
        right = _path_parts(node.right, names)
        if left is None or right is None:
            return None
        return left + right
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return (node.value,)
    if isinstance(node, ast.Name):
        return names.get(node.id)
    return names.get(text)


def _module_paths(tree: ast.Module) -> dict[str, tuple[str, ...]]:
    """Module-level names bound to a path, resolved in one pass (source order)."""
    names: dict[str, tuple[str, ...]] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target = stmt.targets[0]
            if isinstance(target, ast.Name):
                got = _path_parts(stmt.value, names)
                if got is not None:
                    names[target.id] = got
    return names


TRACKED: list[str] | None = None


def _tracked() -> list[str]:
    global TRACKED
    if TRACKED is None:
        import subprocess
        done = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True)
        TRACKED = [ln for ln in (done.stdout or "").splitlines() if ln.strip()]
    return TRACKED


def example_reads(scripts: list[pathlib.Path]) -> tuple[list[str], int, int]:
    """Every `examples/...` path a suite resolves, and the ones git does not carry.

    The C6 failure in one sentence: `tests/test_review_comparison.py` built from
    `examples/33-comparison/forrige.csv`, which `.gitignore` excludes. It ran green in a
    checkout where someone had run `generate_data.py` and failed on a fresh worktree, so
    `check_all` looked like a race. A suite may read a file git carries, or write its own
    fixture into a temporary directory; nothing in between.
    """
    tracked = set(_tracked())
    untracked: list[str] = []
    resolved = skipped = 0
    for script in scripts:
        tree = ast.parse(script.read_text(encoding="utf-8"))
        names = _module_paths(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
                continue
            got = _path_parts(node, names)
            if not got or not any(part == "examples" for part in got):
                continue
            rel = "/".join(part for part in got if part).strip("/")
            if not rel.startswith("examples/"):
                continue
            if not pathlib.PurePosixPath(rel).suffix:
                skipped += 1     # a directory, not a file a suite could read as data
                continue
            resolved += 1
            if rel not in tracked:
                untracked.append(f"{script.name} -> {rel}")
    return sorted(set(untracked)), resolved, skipped


#: A path a suite names on purpose although no such file exists: a mutation control has to
#: point at something absent for the defect it plants to be a defect. Each entry states why,
#: and the ratchet below refuses an entry nothing names any more, so the list can only
#: shrink. It is not an exemption from the rule, only from the rule's subject.
DELIBERATE_ABSENT = {
    "examples/99-not-there/ny.html":
        "tests/test_gate_coverage.py invents it to check that a new artefact nothing "
        "verifies is reported, and that a debt entry pointing at nothing is reported",
}


def check_example_reads() -> None:
    print("\n2. no suite reads an example path git does not carry")
    scripts = sorted((ROOT / "tests").glob("test_*.py"))
    chk("the suites were found", bool(scripts), n=len(scripts))
    untracked, resolved, skipped = example_reads(scripts)
    print(f"       {resolved} example path(s) resolved, {skipped} directory reference(s) skipped")
    named = {rel for entry in untracked for rel in [entry.split(" -> ", 1)[1]]}
    unexplained = [e for e in untracked if e.split(" -> ", 1)[1] not in DELIBERATE_ABSENT]
    print(f"       {len(DELIBERATE_ABSENT)} deliberate absence(s) on the list")
    chk("every example path a suite resolves is tracked, or a declared absence",
        not unexplained, "; ".join(unexplained[:4]), n=resolved)
    stale = [rel for rel in DELIBERATE_ABSENT if rel not in named]
    chk("no declared absence has gone stale", not stale,
        "; ".join(stale), n=len(DELIBERATE_ABSENT))
    # the control: the pre-fix form, resolved through the same reader, must be reported
    probe = ROOT / "tests" / "_probe_untracked.py"
    probe.write_text(
        'import pathlib\n'
        'ROOT = pathlib.Path(__file__).resolve().parents[1]\n'
        'EXAMPLE = ROOT / "examples" / "33-comparison"\n'
        'DATA = str(EXAMPLE / "forrige.csv")\n', encoding="utf-8")
    try:
        caught, _, _ = example_reads([probe])
    finally:
        probe.unlink()
    chk("the reader notices a gitignored example read (mutation control)",
        any("forrige.csv" in c for c in caught), str(caught), n=1)


# ---------------------------------------------------------------------------
# 3. the anchors a mutation control points at
# ---------------------------------------------------------------------------

def module_string_assign(tree: ast.Module, name: str) -> ast.expr | None:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node.value
    return None


def artefacts_and_anchors(script: pathlib.Path) -> tuple[list[str], list[tuple[str, str]], bool]:
    """(artefact filenames, [(label, needle)], has_function_mutants) from the source text."""
    tree = ast.parse(script.read_text(encoding="utf-8"))

    html = module_string_assign(tree, "HTML")
    artefacts: list[str] = []
    if isinstance(html, ast.BinOp) and isinstance(html.right, ast.Constant) \
            and isinstance(html.right.value, str):
        artefacts.append(html.right.value)

    anchors: list[tuple[str, str]] = []
    has_fn = False
    mut = module_string_assign(tree, "MUTATIONS")
    if isinstance(mut, ast.Dict):
        for key, value in zip(mut.keys, mut.values):
            if not isinstance(key, ast.Constant) or not isinstance(value, ast.Tuple):
                continue
            elts = value.elts
            if len(elts) >= 2 and all(isinstance(e, ast.Constant) and isinstance(e.value, str)
                                     for e in elts[:2]):
                anchors.append((key.value, elts[0].value))
    elif isinstance(mut, (ast.Tuple, ast.List)):
        has_fn = True
    return artefacts, anchors, has_fn


def broken_anchors(root: pathlib.Path, scripts: list[pathlib.Path]) -> tuple[list[str], int, int]:
    """Anchors that are absent or ambiguous in the artefact their verifier names."""
    broken: list[str] = []
    anchors_seen = files_seen = 0
    for script in scripts:
        artefacts, anchors, _ = artefacts_and_anchors(script)
        here = script.parent
        for rel in artefacts:
            target = here / rel
            if not target.is_file():
                broken.append(f"{script.name}: artefact {rel} is missing")
                continue
            files_seen += 1
            text = target.read_text(encoding="utf-8")
            for label, needle in anchors:
                anchors_seen += 1
                count = text.count(needle)
                if count != 1:
                    broken.append(f"{script.name}: anchor '{label}' occurs {count} time(s)")
    return broken, anchors_seen, files_seen


def mutation_scripts() -> list[pathlib.Path]:
    scripts = []
    for script in sorted(ROOT.glob("examples/*/verify_*.py")) + sorted(ROOT.glob("tools/verify_*.py")):
        try:
            _, anchors, has_fn = artefacts_and_anchors(script)
        except SyntaxError:
            continue
        if anchors or has_fn:
            scripts.append(script)
    return scripts


def check_anchors() -> int:
    print("\n3. every mutation anchor still occurs exactly once in its artefact")
    scripts = mutation_scripts()
    chk("verifiers with a mutation control were found", bool(scripts), n=len(scripts))
    broken, anchors_seen, files_seen = broken_anchors(ROOT, scripts)
    print(f"       {len(scripts)} verifier(s), {files_seen} artefact(s), {anchors_seen} anchor(s)")
    chk("every anchor occurs exactly once in the file it names", not broken,
        "; ".join(broken[:4]), n=anchors_seen)
    return anchors_seen


# ---------------------------------------------------------------------------
# 3. the control: break one anchor in a copy and require the check to notice
# ---------------------------------------------------------------------------

def check_control(scripts: list[pathlib.Path]) -> None:
    print("\n4. the mutation control: a broken anchor is noticed")
    with_anchors = [s for s in scripts if artefacts_and_anchors(s)[1]]
    if not with_anchors:
        chk("a (needle, replacement) verifier exists to test the control against", False)
        return
    script = with_anchors[0]
    artefacts, anchors, _ = artefacts_and_anchors(script)
    label, needle = anchors[0]
    target = script.parent / artefacts[0]
    text = target.read_text(encoding="utf-8")
    chk("the chosen anchor is unique before the mutation", text.count(needle) == 1, needle[:40])

    # the two drifts that actually happened here: a rule renamed away (count 0) and a
    # rule copied so the anchor stops being unique (count 2). Appending to a needle would
    # leave it present once, which is why it is not a mutation worth testing.
    deleted = text.replace(needle, "", 1)
    chk("a deleted anchor is reported (count 0)",
        deleted.count(needle) == 0 and deleted != text,
        f"{script.name}: '{label}' still counts {deleted.count(needle)}", n=1)
    doubled = text.replace(needle, needle + needle, 1)
    chk("a duplicated anchor is reported (count 2)",
        doubled.count(needle) == 2 and doubled != text,
        f"{script.name}: '{label}' counts {doubled.count(needle)}", n=1)
    chk("the untouched text still holds the anchor exactly once",
        text.count(needle) == 1, label)


def main() -> int:
    n_docs = check_documented_paths()
    check_example_reads()
    check_anchors()
    check_control(mutation_scripts())
    print("\n" + "-" * 60)
    print(f"PASS: {passed}  FAIL: {failed}   (documents {n_docs})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
