import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]/"skills/decksmith/scripts"))
from project_config import resolve_config, SpecError


class ProjectConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name).resolve()
        self.path=self.base/"decksmith.yaml"

    def read(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")
        return resolve_config(self.path)

    def test_defaults_without_file(self):
        config=resolve_config(base=self.base)
        self.assertEqual(config["canvas"], {"width":1920,"height":1080})
        self.assertEqual(config["privacy"]["mode"], "normal")
        self.assertEqual(config["images"]["mode"], "auto")
        self.assertFalse(config["output"]["pdf"])

    def test_dimensions(self):
        for data, expected in (({"aspect_ratio":"9:16"},(1080,1920)),
                               ({"width_px":800,"height_px":600},(800,600)),
                               ({"width_px":900,"aspect_ratio":"3:2"},(900,600)),
                               ({"height_px":900},(1600,900))):
            with self.subTest(data=data):
                canvas=self.read({"slide":data})["canvas"]
                self.assertEqual((canvas["width"],canvas["height"]),expected)

    def test_language_names_preserved(self):
        for language in ("ja","日本語","english","英語","繁體中文","ブラジルのポルトガル語"):
            self.assertEqual(self.read({"language":language})["language"],language)

    def test_all_fields_and_relative_paths(self):
        (self.base/"style.yaml").write_text("{}")
        (self.base/"brief.md").write_text("brief")
        result=self.read({"slide":{"width_px":1920,"height_px":1080,"aspect_ratio":"16:9"},
            "privacy":{"mode":"restricted"},"images":{"mode":"provided_only"},"language":"日本語",
            "input":{"style":"style.yaml","brief":"brief.md"},
            "output":{"directory":"result","filename":"日本語.pptx","pdf":True}})
        self.assertEqual(result["input"]["style"],str(self.base/"style.yaml"))
        self.assertEqual(result["output"]["directory"],str(self.base/"result"))
        self.assertEqual(result["privacy"]["mode"],"restricted")
        self.assertTrue(result["output"]["pdf"])

    def test_invalid_settings_rejected(self):
        for data in ({"privacy":{"mode":"typo"}}, {"images":{"mode":"typo"}},
                     {"language":""},{"language":False},{"output":{"pdf":"false"}},
                     {"output":{"filename":"../overwrite.pptx"}},
                     {"input":{"style":"https://example.com/style.yaml"}},
                     {"input":{"brief":"missing.md"}}, {"privacy":None}, {"typo":True},
                     {"slide":{"width_px":True}}, {"slide":{"aspect_ratio":"nan:1"}},
                     {"slide":{"width_px":1920,"height_px":1080,"aspect_ratio":"4:3"}}):
            with self.subTest(data=data), self.assertRaises(SpecError):
                self.read(data)
