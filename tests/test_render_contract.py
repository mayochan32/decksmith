"""Optional renderer contract test. Set DECKSMITH_RENDER_TEST=1 and runtime env."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

SCRIPTS=Path(__file__).parents[1]/"skills/decksmith/scripts"
sys.path.insert(0,str(SCRIPTS))
from compile_spec import source_hash

@unittest.skipUnless(os.environ.get("DECKSMITH_RENDER_TEST")=="1","requires presentation runtime")
class RenderContractTests(unittest.TestCase):
    def test_native_runs_paths_rotation_and_image_layer(self):
        with tempfile.TemporaryDirectory() as raw:
            p=Path(raw)
            (p/"pixel.png").write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="))
            (p/"style.yaml").write_text("配色: '#C8102E'\n",encoding="utf-8")
            (p/"structure.yaml").write_text(json.dumps({"slides":[{"id":"s","required_text":["Editable text"]}]}))
            scene={"schema_version":"1.0","canvas":{"width":1280,"height":720},
                "style_sha256":source_hash(p/"style.yaml"),"structure_sha256":source_hash(p/"structure.yaml"),
                "requirements":[{"source":"/配色","interpretation":"Red text","status":"implemented","targets":["s/title"]}],
                "slides":[{"id":"s","background":"#FFFFFF","elements":[
                    {"id":"under","type":"shape","geometry":"rect","x":100,"y":100,"width":200,"height":200,"fill":"#123456"},
                    {"id":"image","type":"image","path":"pixel.png","alt":"test pixel","x":110,"y":110,"width":80,"height":80},
                    {"id":"title","type":"text","x":120,"y":220,"width":850,"height":130,"font":"Arial","size":48,"color":"#C8102E","rotation":5,
                     "runs":[{"text":"Editable ","bold":True},{"text":"text","font":"Georgia","color":"#152C48"}]},
                    {"id":"path","type":"path","x":100,"y":440,"width":500,"height":100,"points":[[0,0],[250,100],[500,0]],"stroke":"#C8102E","stroke_width":3}
                ]}]}
            (p/"scene.yaml").write_text(json.dumps(scene))
            output=p/"output"/"smoke.pptx"
            result=subprocess.run([sys.executable,str(SCRIPTS/"create_deck.py"),"--scene",str(p/"scene.yaml"),
                "--style",str(p/"style.yaml"),"--structure",str(p/"structure.yaml"),"--output",str(output),
                "--pptx-only"],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            with ZipFile(output) as archive:
                xml=archive.read("ppt/slides/slide1.xml")
                root=ET.fromstring(xml)
                ns={"p":"http://schemas.openxmlformats.org/presentationml/2006/main","a":"http://schemas.openxmlformats.org/drawingml/2006/main"}
                self.assertEqual("".join(t.text or "" for t in root.findall(".//a:t",ns)),"Editable text")
                self.assertIn(b'val="C8102E"',xml)
                self.assertIn(b'val="152C48"',xml)
                self.assertIn(b'typeface="Georgia"',xml)
                self.assertIn(b'rot="300000"',xml)
                self.assertIsNotNone(root.find(".//a:custGeom",ns))
                tree=root.find(".//p:spTree",ns)
                drawing_types=[e.tag.rsplit("}",1)[-1] for e in tree if e.tag.rsplit("}",1)[-1] in ("sp","pic")]
                self.assertEqual(drawing_types,["sp","pic","sp","sp"])
