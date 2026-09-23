import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).parents[1]
SPEC=importlib.util.spec_from_file_location("scene_compile",ROOT/"skills/decksmith/scripts/compile_spec.py")
M=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

class SceneTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.style={"独自の配色":"#A12345","配置":"右下の小さいタイトル"}
        self.structure={"slides":[{"id":"s","required_text":["項目1","項目2","項目3","項目4","項目5"]}]}
        self.write("style.yaml",self.style)
        self.write("structure.yaml",self.structure)
        self.scene={"schema_version":"1.0","canvas":{"width":1280,"height":720},
            "style_sha256":M.source_hash(self.base/"style.yaml"),
            "structure_sha256":M.source_hash(self.base/"structure.yaml"),
            "requirements":[{"source":"/"+k,"interpretation":v,"status":"implemented","targets":["s/t"]} for k,v in self.style.items()],
            "slides":[{"id":"s","background":"#FFFFFF","elements":[
                {"id":"t","type":"text","x":780,"y":480,"width":400,"height":210,"font":"Arial","size":24,"color":"#A12345",
                "text":"項目1\n項目2\n項目3\n項目4\n項目5"}]}]}
    def write(self,name,value):
        (self.base/name).write_text(json.dumps(value,ensure_ascii=False),encoding="utf-8")
    def compile(self):
        self.write("scene.yaml",self.scene)
        return M.compile_scene(self.base/"scene.yaml",self.base/"style.yaml",self.base/"structure.yaml")
    def test_custom_style_and_positions_are_preserved(self):
        result=self.compile()
        e=result["slides"][0]["elements"][0]
        self.assertEqual((e["x"],e["size"],e["color"]),(780,24,"#A12345"))
        self.scene["slides"][0]["elements"][0].update(x=50,y=50,width=1100,size=42)
        result=self.compile()
        self.assertEqual(result["slides"][0]["elements"][0]["x"],50)
    def test_no_fifth_item_truncation(self):
        self.scene["slides"][0]["elements"][0]["text"]="項目1項目2項目3項目4"
        with self.assertRaisesRegex(M.SpecError,"missing editable content"):
            self.compile()
    def test_style_edits_invalidate_scene(self):
        self.write("style.yaml",{"異なる色":"#000000"})
        with self.assertRaisesRegex(M.SpecError,"style changed"):
            self.compile()
    def test_missing_requirement_rejected(self):
        self.scene["requirements"].pop()
        with self.assertRaisesRegex(M.SpecError,"Uninterpreted"):
            self.compile()
    def test_unimplemented_requirement_rejected(self):
        self.scene["requirements"][0]["status"]="pending"
        with self.assertRaisesRegex(M.SpecError,"unresolved"):
            self.compile()
    def test_unknown_primitive_is_not_fallback(self):
        self.scene["slides"][0]["elements"][0]["type"]="preset"
        with self.assertRaisesRegex(M.SpecError,"unsupported"):
            self.compile()
    def test_unknown_render_field_rejected(self):
        self.scene["slides"][0]["elements"][0]["mask"]="round"
        with self.assertRaisesRegex(M.SpecError,"unsupported fields"):
            self.compile()
    def test_overflow_requires_reason(self):
        self.scene["slides"][0]["elements"][0]["x"]=1200
        with self.assertRaisesRegex(M.SpecError,"overflow_reason"):
            self.compile()
        self.scene["slides"][0]["elements"][0]["overflow_reason"]="Intentional crop"
        self.compile()
    def test_rich_text_keeps_content_and_separate_fonts(self):
        e=self.scene["slides"][0]["elements"][0]
        del e["text"]
        e["runs"]=[{"text":"項目1項目2","font":"First","color":"#A12345"},{"text":"項目3項目4項目5","font":"Second"}]
        result=self.compile()
        self.assertEqual(result["slides"][0]["elements"][0]["runs"][1]["font"],"Second")
    def test_absolute_and_missing_assets_rejected(self):
        e={"id":"img","type":"image","x":0,"y":0,"width":100,"height":100,"path":"/tmp/not-found.png","alt":"test"}
        self.scene["slides"][0]["elements"].append(e)
        with self.assertRaisesRegex(M.SpecError,"project-relative"):
            self.compile()
        e["path"]="missing.png"
        with self.assertRaisesRegex(M.SpecError,"missing/unsupported image"):
            self.compile()
    def test_layer_order_is_preserved(self):
        self.scene["slides"][0]["elements"].insert(0,{"id":"bg","type":"shape","geometry":"rect","x":1,"y":1,"width":10,"height":10,"fill":"#123456"})
        self.assertEqual([e["id"] for e in self.compile()["slides"][0]["elements"]],["bg","t"])

    def test_real_yaml_without_host_pyyaml(self):
        (self.base/"style.yaml").write_text("配色:\n  主役: '#A12345'\n指定: >-\n  右下の小さいタイトル\n",encoding="utf-8")
        parsed=M.load_mapping(self.base/"style.yaml")
        self.assertEqual(parsed["配色"]["主役"],"#A12345")
        self.assertEqual(parsed["指定"],"右下の小さいタイトル")

if __name__=="__main__":
    unittest.main()
