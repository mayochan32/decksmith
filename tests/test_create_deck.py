from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).parents[1] / "skills" / "decksmith" / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("decksmith_create_deck", SCRIPTS / "create_deck.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CreateDeckEnvironmentTests(unittest.TestCase):
    def make_presentations_skill(self, root: Path) -> Path:
        skill = root / "presentations"
        marker = skill / MODULE.PRESENTATIONS_MARKER
        marker.parent.mkdir(parents=True)
        marker.touch()
        return skill

    def test_explicit_presentations_directory(self):
        with tempfile.TemporaryDirectory() as raw:
            skill = self.make_presentations_skill(Path(raw))
            self.assertEqual(MODULE.resolve_presentations_skill_dir(skill), skill.resolve())

    def test_environment_presentations_directory(self):
        with tempfile.TemporaryDirectory() as raw:
            skill = self.make_presentations_skill(Path(raw))
            with mock.patch.dict(
                os.environ,
                {"DECKSMITH_PRESENTATIONS_SKILL_DIR": str(skill)},
                clear=True,
            ):
                self.assertEqual(MODULE.resolve_presentations_skill_dir(), skill.resolve())

    def test_current_runtime_environment_names(self):
        with tempfile.TemporaryDirectory() as raw:
            runtime = Path(raw) / "python"
            runtime.touch()
            with mock.patch.dict(
                os.environ,
                {"CODEX_PRIMARY_RUNTIME_PYTHON": str(runtime)},
                clear=True,
            ):
                self.assertEqual(MODULE.absolute_env_path("RUNTIME_PYTHON"), runtime)


if __name__ == "__main__":
    unittest.main()
