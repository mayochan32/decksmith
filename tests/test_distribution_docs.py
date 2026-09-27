import re
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

    def test_all_provider_packages_include_linked_portable_guide(self):
        with tempfile.TemporaryDirectory() as raw:
            for host in ('codex','claude','gemini'):
                target=package(host,Path(raw)/host)
                self.check_links(target)
                self.assertTrue((target/'templates/decksmith.yaml').is_file())
