import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/"skills/decksmith/scripts"))
from create_deck import executable, run, SpecError

class PortableEnvironmentTests(unittest.TestCase):
    def test_path_discovery(self):
        with patch.dict(os.environ,{},clear=True), patch("shutil.which",return_value="/bin/node"):
            self.assertEqual(executable("node","DECKSMITH_NODE"),"/bin/node")
    def test_explicit_override(self):
        with patch.dict(os.environ,{"DECKSMITH_NODE":sys.executable},clear=True):
            self.assertEqual(executable("node","DECKSMITH_NODE"),sys.executable)
    def test_missing_runtime(self):
        with patch.dict(os.environ,{},clear=True), patch("shutil.which",return_value=None):
            with self.assertRaises(SpecError): executable("node","DECKSMITH_NODE")
    def test_command_failure(self):
        with self.assertRaises(SpecError): run([sys.executable,"-c","raise SystemExit(2)"])
