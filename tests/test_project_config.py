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
        self.assertEqual(config["images"], {"mode":"auto","amount":"normal","type":"auto","color":"color","plan":"show"})

    def test_image_options(self):
        self.assertEqual(self.read({})["text"], {"amount":"normal"})
        options={"amount":("normal","more","less","none"),
                 "type":("auto","illust","photo","icon","anime"),
                 "color":("color","gray","monotone"),"plan":("show","confirm","skip")}
        for name,values in options.items():
            for value in values:
                with self.subTest(name=name,value=value):
                    result=self.read({"privacy":{"mode":"restricted"},"images":{"mode":"provided_only",name:value}})
                    self.assertEqual(result["images"][name],value)
                    self.assertEqual(result["images"]["mode"],"provided_only")
                    self.assertEqual(result["privacy"]["mode"],"restricted")

    def test_image_options_reject_invalid_values(self):
        for name,values in {"amount":("多め","lots",False,None),
                            "type":("illustration","photorealistic","イラスト",[]),
                            "color":("grayscale","白黒",{}),"plan":("yes",True)}.items():
            for value in values:
                with self.subTest(name=name,value=value),self.assertRaisesRegex(SpecError,"images."+name):
                    self.read({"images":{name:value}})

    def test_image_options_real_yaml(self):
        self.path.write_text("images:\n  amount: more\n  type: illust\n  color: gray\n  plan: confirm\n",encoding="utf-8")
        self.assertEqual(resolve_config(self.path)["images"],
                         {"mode":"auto","amount":"more","type":"illust","color":"gray","plan":"confirm"})

    def test_dimensions(self):
        self.assertEqual(self.read({"text":{}})["text"]["amount"],"normal")
        self.assertEqual(self.read({})["output"]["renderer"],"libreoffice")
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

    def test_text_levels_and_independent_images(self):
        for amount in ("minimal","less","normal","more","dense"):
            with self.subTest(amount=amount):
                result=self.read({"text":{"amount":amount},"images":{"amount":"more"},"privacy":{"mode":"restricted"}})
                self.assertEqual(result["text"]["amount"],amount)
                self.assertEqual(result["images"]["amount"],"more")
                self.assertEqual(result["privacy"]["mode"],"restricted")

    def test_invalid_text_settings(self):
        for setting in (None,[],"dense",{"amount":None},{"amount":False},{"amount":5},
                        {"amount":[]},{"amount":{}},{"amount":"多め"},{"amount":"maximum"},{"amout":"dense"}):
            with self.subTest(setting=setting),self.assertRaises(SpecError):
                self.read({"text":setting})

    def test_text_real_yaml(self):
        self.path.write_text("text:\n  amount: minimal\nlanguage: 日本語\n",encoding="utf-8")
        result=resolve_config(self.path)
        self.assertEqual(result["text"],{"amount":"minimal"})
        self.assertEqual(result["language"],"日本語")

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
        for data in ({"output":{"renderer":"unknown"}}, {"output":{"renderer":"none","pdf":True}},
                     {"privacy":{"mode":"typo"}}, {"images":{"mode":"typo"}},
                     {"language":""},{"language":False},{"output":{"pdf":"false"}},
                     {"output":{"filename":"../overwrite.pptx"}},
                     {"input":{"style":"https://example.com/style.yaml"}},
                     {"input":{"brief":"missing.md"}}, {"privacy":None}, {"typo":True},
                     {"slide":{"width_px":True}}, {"slide":{"aspect_ratio":"nan:1"}},
                     {"slide":{"width_px":1920,"height_px":1080,"aspect_ratio":"4:3"}}):
            with self.subTest(data=data), self.assertRaises(SpecError):
                self.read(data)
