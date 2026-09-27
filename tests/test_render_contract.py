"""Optional renderer contract test. Set DECKSMITH_RENDER_TEST=1 and runtime env."""
import base64
import json
import os
import shutil
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
            workspace=Path(raw)/"my-presentations"
            p=workspace/"setting"
            p.mkdir(parents=True)
            (p/"pixel.png").write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="))
            (p/"style.yaml").write_text("配色: '#C8102E'\n",encoding="utf-8")
            (p/"structure.yaml").write_text(json.dumps({"slides":[{"id":"s","required_text":["Editable text"],"notes":"Detailed explanation kept in speaker notes."}]}))
            scene={"schema_version":"1.0","canvas":{"width":1280,"height":720},
                "style_sha256":source_hash(p/"style.yaml"),"structure_sha256":source_hash(p/"structure.yaml"),
                "requirements":[{"source":"/配色","interpretation":"Red text","status":"implemented","targets":["s/title"]}],
                "slides":[{"id":"s","background":"#FFFFFF","elements":[
                    {"id":"under","type":"shape","geometry":"rect","x":100,"y":100,"width":200,"height":200,"fill":"#123456"},
                    {"id":"image","type":"image","path":"pixel.png","alt":"test pixel","x":110,"y":110,"width":80,"height":80},
                    {"id":"title","type":"text","x":120,"y":220,"width":850,"height":130,"font":"Arial","size":48,"color":"#C8102E","rotation":5,"tracking":-2,"role":"heading",
                     "runs":[{"text":"Editable ","bold":True},{"text":"text","font":"Georgia","color":"#152C48"}]},
                    {"id":"path","type":"path","x":100,"y":440,"width":500,"height":100,"points":[[0,0],[250,100],[500,0]],"stroke":"#C8102E","stroke_width":3}
                ]}]}
            (p/"scene.yaml").write_text(json.dumps(scene))
            plan={'style_sha256':scene['style_sha256'],'structure_sha256':scene['structure_sha256'],
                  'signatures':[{'source':'/配色','intent':'Red emphasis','visual_check':'Inspect title color'}],
                  'font_evidence':'Fixture only; verify real glyphs in target renderer',
                  'typography':{'heading':{'font':'Arial','min_size':40,'reason':'Contract fixture'}},
                  'representative_slides':['s'],
                  'slides':[{'id':'s','focal_element':'title','focal_reason':'Required words',
                             'composition':'Foreground editable title','asset_decision':'Fixture pixel'}]}
            (p/'design-plan.yaml').write_text(json.dumps(plan))
            (p/"decksmith.yaml").write_text(json.dumps({"slide":{"width_px":1280,"height_px":720},
                "input":{"style":"style.yaml"},"output":{"filename":"smoke.pptx","renderer":"none"},
                "language":"english","text":{"amount":"minimal"},"privacy":{"mode":"restricted"},"images":{"mode":"provided_only","amount":"less","type":"icon","color":"monotone","plan":"skip"}}))
            output=workspace/"output"/"smoke.pptx"
            from workflow import prepare, freeze
            (p/'brief.md').write_text('Editable text',encoding='utf-8')
            freeze(p)
            prepare(p,capability='unavailable')
            result=subprocess.run([sys.executable,str(SCRIPTS/"create_deck.py"),"--scene",str(p/"scene.yaml"),
                "--structure",str(p/"structure.yaml"),"--config",str(p/'decksmith.resolved.yaml')],capture_output=True,text=True,
                env={**os.environ,"DECKSMITH_SOFFICE":"missing-soffice","DECKSMITH_PDFTOPPM":"missing-pdftoppm"})
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(Path(json.loads(result.stdout)["output"]), output.resolve())
            self.assertFalse((p/"output").exists())
            manifest=json.loads((output.with_suffix(".preview")/"review-manifest.json").read_text())
            expected_version=(SCRIPTS.parent/"VERSION").read_text().strip()
            self.assertIn("DeckSmith " + expected_version,result.stderr)
            self.assertEqual(json.loads(result.stdout)["decksmith_version"],expected_version)
            self.assertEqual(manifest["decksmith_version"],expected_version)
            self.assertEqual(manifest["status"],"not_visually_reviewed")
            self.assertIn('content-check.json',manifest['workflow_records'])
            self.assertIn('policy-record.json',manifest['workflow_records'])
            self.assertEqual(manifest['project_settings']['communication_policy']['host_image_capability'],'unavailable')
            self.assertEqual(manifest['design_plan_sha256'], source_hash(output.with_suffix('.preview')/'design-plan.json'))
            self.assertIsNone(json.loads(result.stdout)["preview"])
            self.assertFalse(list(output.with_suffix(".preview").glob("*.png")))
            self.assertEqual(manifest["project_settings"]["language"],"english")
            self.assertEqual(manifest["project_settings"]["text"],{"amount":"minimal"})
            self.assertEqual(manifest["project_settings"]["privacy"]["mode"],"restricted")
            self.assertEqual(manifest["project_settings"]["images"],
                {"mode":"provided_only","amount":"less","type":"icon","color":"monotone","plan":"skip"})
            with ZipFile(output) as archive:
                self.assertIn(b"Detailed explanation kept in speaker notes.",archive.read("ppt/notesSlides/notesSlide1.xml"))
                xml=archive.read("ppt/slides/slide1.xml")
                root=ET.fromstring(xml)
                ns={"p":"http://schemas.openxmlformats.org/presentationml/2006/main","a":"http://schemas.openxmlformats.org/drawingml/2006/main"}
                self.assertEqual("".join(t.text or "" for t in root.findall(".//a:t",ns)),"Editable text")
                self.assertIn(b'val="C8102E"',xml)
                self.assertIn(b'val="152C48"',xml)
                self.assertIn(b'typeface="Georgia"',xml)
                self.assertIn(b'rot="300000"',xml)
                self.assertIn(b'spc="-150"',xml)
                self.assertIsNotNone(root.find(".//a:custGeom",ns))
                tree=root.find(".//p:spTree",ns)
                drawing_types=[e.tag.rsplit("}",1)[-1] for e in tree if e.tag.rsplit("}",1)[-1] in ("sp","pic")]
                self.assertEqual(drawing_types,["sp","pic","sp","sp"])
            powerpoint_test=os.environ.get("DECKSMITH_POWERPOINT_TEST")=="1"
            if powerpoint_test:
                self.assertEqual(sys.platform,"win32","PowerPoint integration test needs native Windows")
            if powerpoint_test or (shutil.which(os.environ.get("DECKSMITH_SOFFICE", "soffice")) and shutil.which("pdftoppm")):
                config=json.loads((p/"decksmith.yaml").read_text())
                config["output"].update(filename="with-pdf.pptx",pdf=True,renderer="powerpoint" if powerpoint_test else "libreoffice")
                (p/"decksmith.yaml").write_text(json.dumps(config))
                command=[sys.executable,str(SCRIPTS/"create_deck.py"),"--scene",str(p/"scene.yaml"),
                         "--structure",str(p/"structure.yaml")]
                result=subprocess.run(command,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                pdf=workspace/"output/with-pdf.pdf"
                self.assertTrue(pdf.read_bytes().startswith(b"%PDF"))
                png=(workspace/"output/with-pdf.preview/slide-01.png").read_bytes()
                self.assertEqual((int.from_bytes(png[16:20],"big"),int.from_bytes(png[20:24],"big")),(1280,720))
                original=pdf.read_bytes()
                result=subprocess.run(command,capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(pdf.read_bytes(),original)
