import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from release_version import check, set_version, validate, METADATA, VERSION_FILE


class VersionTests(unittest.TestCase):
    def test_release_metadata_matches(self):
        self.assertRegex(check(),r"^v\d+\.\d+\.\d+$")

    def test_version_commands_need_no_generation_arguments(self):
        for name in ("create_deck.py","doctor.py"):
            result=subprocess.run([sys.executable,str(ROOT/"skills/decksmith/scripts"/name),"--version"],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.strip(),"DeckSmith " + check())

    def test_sync_and_mismatch_detection(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            for name in (*METADATA,str(VERSION_FILE)):
                destination=root/name
                destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(ROOT/name,destination)
            old=json.loads((root/"skills/decksmith/package-lock.json").read_text())["packages"]["node_modules/pptxgenjs"]
            self.assertEqual(set_version("v1.2.3",root),"v1.2.3")
            self.assertEqual(json.loads((root/"skills/decksmith/package-lock.json").read_text())["packages"]["node_modules/pptxgenjs"],old)
            (root/VERSION_FILE).write_text("v1.2.4\n")
            with self.assertRaisesRegex(ValueError,"mismatch"):
                check(root)

    def test_strict_format(self):
        for value in ("1.2.3","v1.2","v01.2.3","v1.2.3-beta","v1.2.3+build"):
            with self.subTest(value=value),self.assertRaises(ValueError):
                validate(value)
