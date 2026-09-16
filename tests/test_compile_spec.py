from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path(__file__).parents[1] / "skills" / "decksmith" / "scripts" / "compile_spec.py"
SPEC = importlib.util.spec_from_file_location("decksmith_compile_spec", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CompileSpecTests(unittest.TestCase):
    def write_yaml(self, directory: Path, name: str, value: object) -> Path:
        target = directory / name
        target.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
        return target

    def base_inputs(self, directory: Path):
        topic = self.write_yaml(
            directory,
            "topic.yaml",
            {"title": "Deck", "audience": "Team", "objective": "Decide"},
        )
        structure = self.write_yaml(
            directory,
            "structure.yaml",
            {"slides": [{"id": "cover", "layout": "cover", "title": "Deck"}]},
        )
        creative = self.write_yaml(directory, "creative.yaml", {"name": "calm"})
        executable = self.write_yaml(directory, "executable.yaml", {"name": "calm-16x9"})
        return topic, structure, creative, executable

    def test_compiles_minimal_project(self):
        with tempfile.TemporaryDirectory() as raw:
            paths = self.base_inputs(Path(raw))
            result = MODULE.compile_spec(*paths)
            self.assertEqual(result["schema_version"], "0.1")
            self.assertEqual(result["slides"][0]["layout"], "cover")
            self.assertEqual(result["style"]["executable"]["canvas"]["width"], 1280)

    def test_rejects_unknown_layout(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            topic, _, creative, executable = self.base_inputs(directory)
            structure = self.write_yaml(
                directory,
                "bad-structure.yaml",
                {"slides": [{"id": "x", "layout": "dashboard", "title": "Bad"}]},
            )
            with self.assertRaises(MODULE.SpecError):
                MODULE.compile_spec(topic, structure, creative, executable)

    def test_rejects_unmaterialized_prompt_image(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            topic, _, creative, executable = self.base_inputs(directory)
            structure = self.write_yaml(
                directory,
                "prompt-only.yaml",
                {
                    "slides": [
                        {
                            "id": "visual",
                            "layout": "image-right",
                            "title": "Visual",
                            "image": {"prompt": "A clean editorial illustration"},
                        }
                    ]
                },
            )
            with self.assertRaises(MODULE.SpecError):
                MODULE.compile_spec(topic, structure, creative, executable)


if __name__ == "__main__":
    unittest.main()
