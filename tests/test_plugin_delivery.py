import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'skills/decksmith/scripts'))
from package_plugin import package, package_browser, archive_folder
from smoke_test import smoke, make_fixture
from compile_spec import compile_scene
from design_quality import check_plan


class PluginDeliveryTests(unittest.TestCase):
    def test_local_catalogs_and_portable_identity_resolve_after_extraction(self):
        with tempfile.TemporaryDirectory(prefix='decksmith plugin ') as raw:
            base = Path(raw)
            folder = package(base / 'stage')
            archive = archive_folder(folder, base / 'decksmith.zip')
            with ZipFile(archive) as source:
                source.extractall(base / 'unpacked')
            root = (base / 'unpacked/decksmith').resolve()
            identity = json.loads((root / 'plugin.json').read_text())
            self.assertEqual(identity['version'], (root / 'VERSION').read_text().strip()[1:])
            openai = json.loads((root / '.agents/plugins/marketplace.json').read_text())['plugins'][0]
            claude = json.loads((root / '.claude-plugin/marketplace.json').read_text())['plugins'][0]
            for entry, relative in ((openai, openai['source']['path']), (claude, claude['source'])):
                resolved = (root / relative).resolve()
                self.assertTrue(resolved.is_relative_to(root))
                self.assertEqual(entry['name'], identity['name'])
                self.assertTrue((resolved / 'skills/decksmith/SKILL.md').is_file())
            self.assertFalse((root / 'mcp.json').exists())
            self.assertTrue((root / 'BROWSER_TRIAL.md').is_file())

    def test_browser_uploads_have_correct_roots_and_common_engine(self):
        with tempfile.TemporaryDirectory() as raw:
            archives = package_browser(Path(raw))
            for archive, prefix in zip(archives, ('decksmith/', 'decksmith/skills/decksmith/')):
                with ZipFile(archive) as source:
                    self.assertEqual({n.split('/')[0] for n in source.namelist()}, {'decksmith'})
                    self.assertIn(prefix + 'SKILL.md', source.namelist())
                    for name in ('SKILL.md', 'scripts/create_deck.py', 'scripts/smoke_test.py', 'package-lock.json'):
                        self.assertEqual(source.read(prefix + name), (ROOT / 'skills/decksmith' / name).read_bytes())
                    trial = json.loads(source.read(prefix + 'browser-trial.json'))
                    self.assertFalse(trial['browser_execution_verified'])
                    self.assertFalse(trial['mcp_required'])
                    self.assertFalse(any('/node_modules/' in n or '/__pycache__/' in n for n in source.namelist()))
                    # Installed standalone skills can report their version without the repository.
                    with tempfile.TemporaryDirectory() as extracted:
                        source.extractall(extracted)
                        result = subprocess.run([sys.executable, str(Path(extracted) / prefix / 'scripts/version.py')], capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stdout.strip(), 'DeckSmith ' + trial['decksmith_version'])

    def test_browser_conflict_does_not_create_partial_new_bundle(self):
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            version = (ROOT / 'VERSION').read_text().strip()
            protected = output / f'decksmith-{version}-chatgpt-plugin-experimental.zip'
            protected.write_bytes(b'user data')
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                package_browser(output)
            self.assertEqual(list(output.iterdir()), [protected])
            self.assertEqual(protected.read_bytes(), b'user data')

    def test_archive_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = package(Path(raw) / 'stage')
            output = Path(raw) / 'protected.zip'
            output.write_bytes(b'user data')
            with self.assertRaises(FileExistsError):
                archive_folder(folder, output)
            self.assertEqual(output.read_bytes(), b'user data')


class SmokeTests(unittest.TestCase):
    def test_fixture_has_independent_content_and_valid_design(self):
        with tempfile.TemporaryDirectory() as raw:
            p = Path(raw) / 'setting'
            make_fixture(p, 'libreoffice', 'Arial')
            scene = compile_scene(p / 'scene.yaml', p / 'style.yaml', p / 'structure.yaml')
            self.assertEqual(len(scene['slides']), 3)
            check_plan(p / 'design-plan.yaml', scene)
            contract = json.loads((p / 'content-contract.json').read_text())
            self.assertEqual([s['id'] for s in contract['slides']], [s['id'] for s in scene['slides']])

    def test_unavailable_dependencies_stop_without_fallback_or_generation(self):
        with tempfile.TemporaryDirectory() as raw:
            p = Path(raw) / 'trial'
            with patch('smoke_test.inspect', return_value={'renderer': {'ready': False}}), patch('smoke_test.subprocess.run') as run:
                report, success = smoke(p)
            self.assertFalse(success)
            self.assertEqual(report['stage'], 'dependencies')
            self.assertEqual(report['renderer'], 'libreoffice')
            self.assertEqual(report['visual_review'], 'not_performed')
            run.assert_not_called()
            self.assertFalse((p / 'setting').exists())
            self.assertEqual(json.loads((p / 'smoke-result.json').read_text())['status'], 'failed')

    def test_existing_or_broken_symlink_workspace_is_preserved(self):
        with tempfile.TemporaryDirectory() as raw:
            p = Path(raw)
            sentinel = p / 'keep'; sentinel.write_bytes(b'keep')
            with self.assertRaises(FileExistsError): smoke(p)
            link = p / 'broken'; link.symlink_to(p / 'missing')
            with self.assertRaises(FileExistsError): smoke(link)
            self.assertEqual(sentinel.read_bytes(), b'keep')
            self.assertFalse((p / 'missing').exists())

    @unittest.skipUnless(os.environ.get('DECKSMITH_RENDER_TEST') == '1', 'requires presentation runtime')
    def test_detached_distribution_generates_native_deck_and_keeps_review_pending(self):
        with tempfile.TemporaryDirectory(prefix='decksmith detached ') as raw:
            base = Path(raw)
            installed = package(base / 'package') / 'skills/decksmith'
            # Emulate locally installed dependencies, without downloading or using dev artifacts.
            deps = base / 'dependencies/node_modules'
            shutil.copytree(ROOT / 'skills/decksmith/node_modules', deps)
            trial = base / 'trial'
            result = subprocess.run([sys.executable, str(installed / 'scripts/smoke_test.py'), '--workspace', str(trial),
                '--renderer', 'libreoffice'], capture_output=True, text=True,
                env={**os.environ, 'DECKSMITH_NODE_MODULES': str(deps), 'PYTHONDONTWRITEBYTECODE': '1'}, timeout=480)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report['status'], 'ready_for_visual_review')
            self.assertEqual(report['visual_review'], 'not_performed')
            self.assertEqual(len(report['previews']), 3)
            self.assertEqual(report['validation']['slides'], 3)
            with ZipFile(report['artifacts']['output']) as archive:
                self.assertIn('日本語'.encode(), archive.read('ppt/slides/slide3.xml'))
            self.assertFalse((Path(report['artifacts']['reports']) / 'review.json').exists())
