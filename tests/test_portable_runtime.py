import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/decksmith/scripts'))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


launcher = module('portable_launcher', ROOT / 'packaging/windows/launcher.py')
builder = module('portable_builder', ROOT / 'scripts/package_portable.py')


class PortableTests(unittest.TestCase):
    def test_pdf_input_routes_config_font_map_and_bundled_optional_dependencies(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); project = root / 'setting'; project.mkdir()
            (project / 'decksmith.yaml').write_text('output:\n  renderer: powerpoint\n')
            args = argparse.Namespace(project=project, action='inspect-source', renderer=None,
                source=Path('original.pdf'), style=Path('style.yaml'), pdf_font_map=Path('fonts.json'))
            cmd, _ = launcher.command(root, args)
            self.assertEqual(cmd[cmd.index('--renderer')+1], 'powerpoint')
            self.assertEqual(cmd[cmd.index('--pdf-font-map')+1], str((project / 'fonts.json').resolve()))
            self.assertEqual(cmd[cmd.index('--config')+1], str((project / 'decksmith.yaml').resolve()))
            (root / 'runtime/pdf').mkdir(parents=True)
            with patch.dict(os.environ, {'DECKSMITH_PDF_PYTHON': '/host/python', 'DECKSMITH_PDF_MODULES': '/host/dependencies'}):
                env = launcher.environment(root)
            self.assertNotIn('DECKSMITH_PDF_PYTHON', env)
            self.assertEqual(env['DECKSMITH_PDF_MODULES'], str(root / 'runtime/pdf'))

    def test_restyle_routes_to_shared_engine_and_preserves_relative_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            args = argparse.Namespace(project=project, action='inspect-source', renderer=None,
                                      source=Path('original.pptx'), style=Path('style.yaml'))
            cmd, cwd = launcher.command(Path('/bundle'), args)
            self.assertIn('/bundle/skills/decksmith/scripts/restyle_deck.py', cmd)
            self.assertIn('inspect', cmd)
            self.assertIn(str(project.resolve() / 'original.pptx'), cmd)
            self.assertIn(str(project.resolve() / 'restyle'), cmd)
            args.action = 'restyle'; args.renderer = 'powerpoint'; args.next_output = True
            cmd, cwd = launcher.command(Path('/bundle'), args)
            self.assertIn('apply', cmd)
            self.assertIn(str(project.resolve() / 'restyle/restyle-plan.yaml'), cmd)
            self.assertIn('--next-output', cmd)
            self.assertEqual(cmd[cmd.index('--renderer')+1], 'powerpoint')
            for mode in ('2', '3'):
                args.mode = mode
                cmd, _ = launcher.command(Path('/bundle'), args)
                self.assertEqual(cmd[cmd.index('--mode')+1], mode)
            args.renderer = None
            with self.assertRaisesRegex(ValueError, 'no automatic fallback'):
                launcher.command(Path('/bundle'), args)

    def test_environment_uses_only_bundled_runtime(self):
        with patch.dict(os.environ, {'PYTHONPATH': 'host', 'NODE_OPTIONS': '--bad',
                                     'DECKSMITH_NODE': 'host', 'DECKSMITH_SOFFICE': 'host'}):
            env = launcher.environment(Path('/bundle'))
        self.assertEqual(env['DECKSMITH_NODE'], '/bundle/runtime/node/node.exe')
        for key in ('PYTHONPATH', 'NODE_OPTIONS', 'DECKSMITH_SOFFICE'):
            self.assertNotIn(key, env)

    def test_no_config_explicit_none_and_unicode_paths(self):
        with tempfile.TemporaryDirectory(prefix='資料 space ') as folder:
            project = Path(folder)
            args = argparse.Namespace(project=project, action='build', renderer='none')
            cmd, cwd = launcher.command(Path('/bundle'), args)
            self.assertEqual(cwd, project.resolve())
            self.assertEqual(cmd[:2], ['/bundle/runtime/python/python.exe', '-I'])
            self.assertEqual(cmd[2:4], ['-X', 'utf8'])
            self.assertIn(str(project.resolve() / 'scene.yaml'), cmd)
            self.assertIn(str(project.resolve().parent / 'output/deck.pptx'), cmd)
            self.assertNotIn('--config', cmd)

    def test_reject_implicit_libreoffice(self):
        with tempfile.TemporaryDirectory() as folder:
            args = argparse.Namespace(project=Path(folder), action='doctor', renderer=None)
            with self.assertRaisesRegex(ValueError, 'no automatic fallback'):
                launcher.command(Path('/bundle'), args)

    def test_init_validate_review_and_explicit_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder)
            args=argparse.Namespace(project=project,action='init',renderer='powerpoint')
            cmd,cwd=launcher.command(Path('/bundle'),args)
            self.assertIn('/bundle/skills/decksmith/scripts/project_init.py',cmd)
            self.assertEqual(cwd,Path('/bundle'))
            args.action='validate';args.renderer=None
            args.output=Path('out/deck.pptx');args.next_output=True
            cmd,_=launcher.command(Path('/bundle'),args)
            self.assertIn('--validate-only',cmd)
            self.assertIn('--next-output',cmd)
            self.assertIn(str(project.resolve()/'out/deck.pptx'),cmd)
            args.action='review'
            cmd,_=launcher.command(Path('/bundle'),args)
            self.assertIn('/bundle/skills/decksmith/scripts/review_deck.py',cmd)

    def test_explicit_config_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            args=argparse.Namespace(project=Path(folder),action='build',renderer='none',config=Path('missing.yaml'))
            with self.assertRaisesRegex(ValueError,'Missing config'):launcher.command(Path('/bundle'),args)

    def test_missing_runtime_never_starts_host_process(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'VERSION').write_text('v0.7.0')
            with patch.object(launcher, '__file__', str(root / 'launcher.py')), \
                    patch.object(sys, 'platform', 'win32'), \
                    patch.object(sys, 'argv', ['launcher.py', 'doctor', '--renderer', 'none']), \
                    patch.object(launcher.subprocess, 'run') as run:
                self.assertEqual(launcher.main(), 2)
                run.assert_not_called()

    def test_powerpoint_config_routes_to_shared_adapter(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            (project / 'decksmith.yaml').write_text('output:\n  renderer: powerpoint\n  pdf: true\n')
            args = argparse.Namespace(project=project, action='build', renderer=None)
            cmd, _ = launcher.command(Path('/bundle'), args)
            self.assertIn('/bundle/skills/decksmith/scripts/create_deck.py', cmd)
            self.assertEqual(cmd[cmd.index('--renderer') + 1], 'powerpoint')
            self.assertIn('--config', cmd)

    def test_archive_rejects_bad_hash_and_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'runtime.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('../escape', 'bad')
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                builder.extract(archive, Path(folder) / 'out', 'bad')
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                builder.extract(archive, Path(folder) / 'out', digest)

    def test_valid_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'runtime.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('runtime/file', 'ok')
            builder.extract(archive, Path(folder) / 'out', hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertEqual((Path(folder) / 'out/runtime/file').read_text(), 'ok')

    @unittest.skipUnless(os.environ.get('DECKSMITH_PORTABLE_ZIP'), 'Optional built ZIP inspection')
    def test_built_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            with zipfile.ZipFile(os.environ['DECKSMITH_PORTABLE_ZIP']) as z:
                self.assertIsNone(z.testzip())
                z.extractall(folder)
            root = Path(folder) / 'decksmith-portable'
            from compile_spec import load_mapping
            config = load_mapping(root / 'setting/decksmith.yaml')
            template = load_mapping(root / 'templates/decksmith.yaml')
            self.assertEqual(config['output']['renderer'], 'powerpoint')
            self.assertEqual(config['output']['directory'], '../output')
            self.assertEqual((root / 'setting' / config['output']['directory']).resolve(),
                             (root / 'output').resolve())
            self.assertIsNone(config['input']['style'])
            self.assertIsNone(config['input']['brief'])
            template['output']['renderer'] = 'powerpoint'
            self.assertEqual(config, template)
            self.assertTrue((root / 'skills/decksmith/scripts/process_environment.py').is_file())
            for path in ('runtime/python/python.exe', 'runtime/node/node.exe'):
                self.assertEqual((root / path).read_bytes()[:2], b'MZ')
            pth = (root / 'runtime/python/python313._pth').read_text()
            self.assertIn('../../skills/decksmith/scripts', pth)
            self.assertNotIn('import site', pth)
            self.assertFalse(list(root.rglob('*.node')), 'Native dependencies need target-specific packaging')
            # This checks packaged JS with host Node, NOT Windows binary execution.
            env = dict(os.environ, DECKSMITH_NODE_MODULES=str(root / 'skills/decksmith/node_modules'))
            result = subprocess.run(['node', str(root / 'skills/decksmith/scripts/build_deck.mjs'), '--check'],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"ready":true', result.stdout)


if __name__ == '__main__':
    unittest.main()
