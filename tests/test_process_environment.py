import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).parents[1] / 'skills/decksmith/scripts'))
import process_environment as runtime
from create_deck import run, executable, SpecError
from doctor import inspect
from test_portable_runtime import launcher


class WindowsEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.platform = patch('sys.platform', 'win32')
        self.api = patch.object(runtime, 'windows_directory', return_value='D:\\Windows')
        self.platform.start()
        self.api.start()
        self.addCleanup(self.platform.stop)
        self.addCleanup(self.api.stop)

    def test_missing_variables_child_only_and_non_c_drive(self):
        source = {'PATH': 'minimal', 'TEMP': 'scratch'}
        env, report = runtime.child_environment(source)
        self.assertEqual(env['SystemRoot'], 'D:\\Windows')
        self.assertEqual(env['WINDIR'], 'D:\\Windows')
        self.assertEqual(report['added'], ['SystemRoot', 'WINDIR'])
        self.assertEqual(source, {'PATH': 'minimal', 'TEMP': 'scratch'})
        self.assertEqual(set(env), {'PATH', 'TEMP', 'SystemRoot', 'WINDIR'})
        self.assertTrue(runtime.powershell_path(env).startswith('D:\\Windows\\'))

    def test_existing_case_insensitive_values_preserved(self):
        source = {'SYSTEMROOT': 'd:\\windows', 'windir': 'D:\\Windows'}
        env, report = runtime.child_environment(source)
        self.assertEqual(env, source)
        self.assertEqual(report['status'], 'valid')

    def test_one_missing_and_empty_values(self):
        env, report = runtime.child_environment({'SYSTEMROOT': '', 'WINDIR': 'D:\\Windows'})
        self.assertEqual(report['added'], ['SystemRoot'])
        self.assertNotIn('SYSTEMROOT', env)
        self.assertEqual(env['SystemRoot'], 'D:\\Windows')

    def test_conflicts_are_not_overwritten(self):
        for source in ({'SystemRoot': 'C:\\Windows'}, {'WINDIR': 'relative'},
                       {'SystemRoot': 'D:\\Windows', 'SYSTEMROOT': 'D:\\Windows'}):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'CONFLICT'):
                runtime.child_environment(source)

    def test_failed_api_has_no_guessed_fallback(self):
        with patch.object(runtime, 'windows_directory', side_effect=OSError('fixture')):
            with self.assertRaisesRegex(ValueError, 'UNRESOLVED'):
                runtime.child_environment({})

    def test_disabled_repair_never_launches_child(self):
        with patch('create_deck.subprocess.run') as child:
            with self.assertRaisesRegex(SpecError, 'repair disabled'):
                run(['node'], env={runtime.REPAIR_OPTION: '0'})
            child.assert_not_called()

    def test_powershell_lookup_uses_api_when_path_is_missing(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch('create_deck.shutil.which', side_effect=[None, 'D:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe']):
            self.assertTrue(executable('powershell.exe', 'DECKSMITH_POWERSHELL').startswith('D:\\Windows'))

    def test_opt_out_stops_missing_but_accepts_complete_environment(self):
        with self.assertRaisesRegex(ValueError, 'repair disabled'):
            runtime.child_environment({runtime.REPAIR_OPTION: '0'})
        source = {runtime.REPAIR_OPTION: '0', 'SystemRoot': 'D:\\Windows', 'WINDIR': 'D:\\Windows'}
        self.assertEqual(runtime.child_environment(source)[0], source)

    def test_non_windows_is_unchanged(self):
        with patch('sys.platform', 'darwin'), patch.object(runtime, 'windows_directory') as api:
            source = {'PATH': 'local'}
            self.assertEqual(runtime.child_environment(source)[0], source)
            api.assert_not_called()

    def test_shared_runner_supplies_environment_and_does_not_modify_parent(self):
        with patch.dict(os.environ, {'PATH': 'minimal'}, clear=True), \
                patch('create_deck.subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'ok', '')) as child:
            self.assertEqual(run(['node', '--version']), 'ok')
            self.assertEqual(child.call_args.kwargs['env']['SystemRoot'], 'D:\\Windows')
            self.assertNotIn('SystemRoot', os.environ)

    def test_runner_errors_keep_stage_and_exit_code(self):
        with patch('create_deck.subprocess.run', return_value=subprocess.CompletedProcess([], 123, '', 'failed')):
            with self.assertRaisesRegex(SpecError, 'exit=123'):
                run(['node'], env={})
        with patch('create_deck.subprocess.run', side_effect=OSError('blocked')):
            with self.assertRaisesRegex(SpecError, 'PROCESS_START_FAILED'):
                run(['node'], env={})

    def test_portable_preserves_opt_out_and_bundled_runtime(self):
        with patch.dict(os.environ, {runtime.REPAIR_OPTION: '0'}, clear=True):
            with self.assertRaisesRegex(ValueError, 'repair disabled'):
                launcher.environment(Path('/bundle'))
        with patch.dict(os.environ, {'NODE_OPTIONS': 'untrusted'}, clear=True):
            env = launcher.environment(Path('/bundle'))
            self.assertEqual(env['SystemRoot'], 'D:\\Windows')
            self.assertNotIn('NODE_OPTIONS', env)
            self.assertEqual(env['DECKSMITH_POWERSHELL'], runtime.powershell_path(env))
            self.assertEqual(env['DECKSMITH_NODE'], '/bundle/runtime/node/node.exe')

    def test_doctor_reports_missing_vars_without_dumping_environment(self):
        with patch.dict(os.environ, {'SOME_SECRET': 'not-for-report'}, clear=True), \
                patch('doctor.executable', return_value='node'), patch('doctor.run', return_value='{"ready":true}'):
            result = inspect('none')
            report = result['execution_context']['windows_environment']
            self.assertEqual(report['added'], ['SystemRoot', 'WINDIR'])
            self.assertTrue(result['renderer']['ready'])
            self.assertNotIn('not-for-report', str(result))


@unittest.skipUnless(sys.platform == 'win32' and os.environ.get('DECKSMITH_WINDOWS_ENV_TEST') == '1',
                     'Optional native Windows stripped-environment process test')
class NativeWindowsEnvironmentTests(unittest.TestCase):
    def test_python_node_and_powershell_start_without_inherited_root(self):
        minimal = {key: value for key, value in os.environ.items()
                   if key.upper() in ('PATH', 'HOME', 'USERPROFILE', 'TEMP', 'TMP')}
        self.assertTrue(run([sys.executable, '-c', 'print("python-ok")'], env=minimal).strip() == 'python-ok')
        self.assertTrue(run([executable('node', 'DECKSMITH_NODE'), '--version'], env=minimal).strip().startswith('v'))
        env, report = runtime.child_environment(minimal)
        self.assertEqual(report['status'], 'repaired')
        output = run([runtime.powershell_path(env), '-NoProfile', '-NonInteractive',
                      '-Command', '[Console]::Write("powershell-ok")'], env=minimal)
        self.assertEqual(output, 'powershell-ok')


class WindowsApiTests(unittest.TestCase):
    def test_api_resizes_buffer(self):
        calls = []
        def query(buffer, size):
            calls.append(size)
            if len(calls) == 1:
                return 300
            buffer.value = 'D:\\Windows'
            return len(buffer.value)
        api = Mock(side_effect=query)
        kernel = Mock(GetSystemWindowsDirectoryW=api)
        with patch.object(runtime.ctypes, 'WinDLL', return_value=kernel, create=True), \
                patch('process_environment.os.path.isdir', return_value=True):
            self.assertEqual(runtime.windows_directory(), 'D:\\Windows')
        self.assertEqual(calls, [260, 301])

    def test_api_zero_result_raises(self):
        kernel = Mock(GetSystemWindowsDirectoryW=Mock(return_value=0))
        with patch.object(runtime.ctypes, 'WinDLL', return_value=kernel, create=True), \
                patch.object(runtime.ctypes, 'get_last_error', return_value=5, create=True):
            with self.assertRaises(OSError):
                runtime.windows_directory()
