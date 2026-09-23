import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from setup_workspace import setup
from package_plugin import package


class WorkspaceSetupTests(unittest.TestCase):
    def test_both_hosts_copy_complete_skill_without_dependencies(self):
        with tempfile.TemporaryDirectory(prefix="decksmith workspace ") as raw:
            result = setup(raw, "both")
            for location in result["skills"]:
                skill = Path(location)
                for filename in ("SKILL.md", "package-lock.json", "scripts/doctor.py"):
                    self.assertTrue((skill / filename).is_file())
                self.assertTrue((skill / "scripts/vendor").is_dir())
                self.assertFalse((skill / "node_modules").exists())

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as raw:
            self.assertTrue(setup(raw, "both", dry_run=True)["dry_run"])
            self.assertEqual(list(Path(raw).iterdir()), [])

    def test_conflict_preflight_preserves_all_targets(self):
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            existing = workspace / ".claude/skills/decksmith"
            existing.mkdir(parents=True)
            sentinel = existing / "keep.txt"
            sentinel.write_text("user content")
            with self.assertRaisesRegex(ValueError, "overwrite"):
                setup(workspace, "both")
            self.assertEqual(sentinel.read_text(), "user content")
            self.assertFalse((workspace / ".agents").exists())

    def test_nonexistent_workspace_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaisesRegex(ValueError, "existing workspace"):
                setup(Path(raw) / "missing", "codex")

    def test_external_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            workspace = base / "workspace"
            external = base / "external"
            workspace.mkdir()
            external.mkdir()
            (workspace / ".agents").symlink_to(external, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "outside"):
                setup(workspace, "codex")
            self.assertEqual(list(external.iterdir()), [])

    def test_broken_target_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            parent = workspace / ".agents/skills"
            parent.mkdir(parents=True)
            (parent / "decksmith").symlink_to(workspace / "missing")
            with self.assertRaisesRegex(ValueError, "overwrite"):
                setup(workspace, "codex")
            self.assertTrue((parent / "decksmith").is_symlink())

    def test_distributions_include_usable_guide_and_helper(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            for host in ("codex", "claude", "gemini"):
                distribution = package(host, base / host)
                self.assertEqual((distribution/"VERSION").read_text(),(distribution/"skills/decksmith/VERSION").read_text())
                self.assertIn("18323a3f5201d08e8afc", (distribution / "USER_GUIDE.md").read_text())
                workspace = base / (host + " workspace")
                workspace.mkdir()
                result = subprocess.run([
                    sys.executable, str(distribution / "scripts/setup_workspace.py"),
                    "--host", "both", "--workspace", str(workspace),
                ], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(json.loads(result.stdout)["skills"]), 2)
                installed=Path(json.loads(result.stdout)["skills"][0])
                version=subprocess.run([sys.executable,str(installed/"scripts/create_deck.py"),"--version"],capture_output=True,text=True)
                self.assertEqual(version.returncode,0,version.stderr)
                self.assertEqual(version.stdout.strip(),"DeckSmith " + (distribution/"VERSION").read_text().strip())
