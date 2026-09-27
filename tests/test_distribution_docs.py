import re
import json
from pathlib import Path
import tempfile
import unittest
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from package_plugin import package


class DistributionDocsTests(unittest.TestCase):
    def check_links(self,root):
        for name in ('README.md','USER_GUIDE.md','PORTABLE_GUIDE.md'):
            for target in re.findall(r'\]\(([^)]+)\)',(root/name).read_text(encoding='utf-8')):
                if '://' in target or target.startswith('#'):continue
                path=target.split('#')[0]
                self.assertTrue((root/path).is_file(),name+': '+target)

    def test_root_guides_have_valid_local_links(self):
        self.check_links(ROOT)

    def test_unified_package_includes_all_manifests_and_linked_guides(self):
        with tempfile.TemporaryDirectory() as raw:
            target=package(Path(raw))
            self.check_links(target)
            self.assertTrue((target/'templates/decksmith.yaml').is_file())
            version=(target/'VERSION').read_text().strip().removeprefix('v')
            for name in ('.codex-plugin/plugin.json','.claude-plugin/plugin.json','gemini-extension.json'):
                manifest=json.loads((target/name).read_text())
                self.assertEqual(manifest['version'],version)
                if 'skills' in manifest:
                    self.assertTrue((target/manifest['skills']/'decksmith/SKILL.md').is_file())
            self.assertEqual(list((target/'skills').iterdir()),[target/'skills/decksmith'])
            self.assertFalse((target/'skills/decksmith/node_modules').exists())
