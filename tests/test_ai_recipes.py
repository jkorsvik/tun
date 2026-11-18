#!/usr/bin/env python3
# Copyright (C) 2026 The Tún authors (see AUTHORS.md)
# This file is part of Tún. Licence: GNU AGPL v3 or later, see LICENSE.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Exercise the install and recipe commands from a source ZIP and an empty home."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "docs/ai-recipes"
DOCS = set("microsoft-365-copilot edge-copilot github-copilot-vscode github-copilot-coding-agent claude-code claude-artifacts chatgpt codex gemini-cli gemini-web cursor windsurf cline-roo jetbrains visual-studio raiwork".split())


class Recipes(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="tun recipe ")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.home = root / "Temporary home"
        self.home.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "TUN_"))}
        self.env.update(HOME=str(self.home), USERPROFILE=str(self.home), PYTHONUTF8="1",
                        PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_NOSYSTEM="1", PATH="")
        self.src = root / "Tún toolkit with spaces"
        bundle = root / "source.zip"
        files = [ROOT / "setup.py", *RECIPE.joinpath("fixtures").glob("*")]
        for folder in ("skills", "tools", "templates", "plugins"):
            files.extend(p for p in (ROOT / folder).rglob("*") if p.is_file()
                         and "__pycache__" not in p.parts)
        with zipfile.ZipFile(bundle, "w") as z:
            for f in files:
                z.write(f, f.relative_to(ROOT).as_posix())
        with zipfile.ZipFile(bundle) as z:
            z.extractall(self.src)

    def run_cli(self, *args, code=0):
        p = subprocess.run([sys.executable, *args], cwd=self.src, env=self.env,
                           capture_output=True, text=True, encoding="utf-8", timeout=45)
        self.assertEqual(p.returncode, code, p.stdout + p.stderr)
        return p.stdout + p.stderr

    def test_install_in_zip_does_not_touch_raiwork_or_replace_user_skills(self):
        (self.home / ".raiwork").mkdir()
        target = self.home / ".claude/skills"
        self.run_cli("setup.py", "--install", "--tool", "claude", "--check", code=1)
        self.assertFalse(target.exists())
        self.run_cli("setup.py", "--install", "--tool", "claude")
        names = {p.parent.name for p in (self.src / "skills").glob("tun-*/SKILL.md")}
        self.assertGreaterEqual(len(names), 9)
        self.assertEqual({p.name for p in target.iterdir()}, names)
        self.assertFalse((self.home / ".raiwork/skills").exists())
        self.assertFalse((self.src / ".git").exists())
        skill = target / "tun-new/SKILL.md"
        before = skill.stat().st_mtime_ns
        self.run_cli("setup.py", "--install", "--tool", "claude")
        self.run_cli("setup.py", "--install", "--tool", "claude", "--check")
        self.assertEqual(skill.stat().st_mtime_ns, before)
        skill.write_text("My own notes", encoding="utf-8")
        self.assertIn("existing skill differs", self.run_cli("setup.py", "--install", "--tool", "claude", code=1))
        self.assertEqual(skill.read_text(encoding="utf-8"), "My own notes")
        self.run_cli("setup.py", "--install", "--tool", "agents")
        self.assertTrue((self.home / ".agents/skills/tun-new/SKILL.md").is_file())
        self.run_cli("setup.py", "--install", "--tool", "raiwork", code=2)

    def test_build_check_and_mutations_in_zip(self):
        self.assertIn("Built", self.run_cli("tools/ai_recipe.py", "build"))
        out = self.src / "work/ai-recipes/tun-recipe.html"
        original = out.read_bytes()
        self.assertFalse(out.with_name("data.js").exists())
        self.assertIn("Static PASS: 4 rows, total 10", self.run_cli("tools/ai_recipe.py", "check"))
        self.assertIn("Static PASS", self.run_cli("tools/ai_recipe.py", "check",
                                                "docs/ai-recipes/fixtures/tun-recipe.html"))
        self.run_cli("tools/ai_recipe.py", "build")
        self.assertEqual(out.read_bytes(), original)
        for needle, replacement in [
            (b'"Count":3', b'"Count":8'),
            (b"Excuses by category", b"Wrong title"),
            ("Made with   : Tún".encode(), b"Made with   : other"),
            (b"T\xc3\xban AI recipe contract: 1;", b"T\xc3\xban AI recipe contract: 0;"),
            (b"</head>", b'<script src="https://example.invalid/test.js"></script></head>'),
        ]:
            with self.subTest(needle=needle):
                self.assertIn(needle, original)
                altered = self.src / "changed.html"
                altered.write_bytes(original.replace(needle, replacement, 1))
                self.assertIn("Not the canonical file", self.run_cli("tools/ai_recipe.py", "check", str(altered), code=1))
        self.assertEqual(out.read_bytes(), original)


class Index(unittest.TestCase):
    def test_marketplace_command_installs_skills(self):
        commands = []
        for doc in (ROOT / "INSTALL.md", RECIPE / "raiwork.md"):
            lines = [line.split() for line in doc.read_text(encoding="utf-8").splitlines()
                     if line.startswith("raicode manage marketplace install plugin/tun@")]
            self.assertEqual(len(lines), 1, doc.name)
            commands.append(lines[0])
        self.assertEqual(*commands)
        self.assertIn("--accept=skills", commands[0])

    def test_every_platform_is_listed_and_has_recipe_evidence(self):
        index = (RECIPE / "README.md").read_text(encoding="utf-8")
        self.assertEqual({p.stem for p in RECIPE.glob("*.md")} - {"README", "common-contract"}, DOCS)
        for name in sorted(DOCS):
            with self.subTest(platform=name):
                self.assertIn(f"({name}.md)", index)
                text = (RECIPE / f"{name}.md").read_text(encoding="utf-8")
                for item in ("fixtures/excuses.csv", "common-contract.md", "tun-recipe.html",
                             "ai_recipe.py", "Origin Notice", "maintainers"):
                    self.assertIn(item, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
