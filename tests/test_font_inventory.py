import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/decksmith/scripts'))
from compile_spec import SpecError
from font_inventory import inspect_fonts, mac_names


class FontInventoryTests(unittest.TestCase):
    def data(self):
        return {'SPFontsDataType': [dict(enabled='yes', typefaces=[
            dict(_name='HiraginoSans-W3', fullname='ヒラギノ角ゴシック W3', family='ヒラギノ角ゴシック', enabled='yes'),
            dict(_name='HiraginoSans-W6', fullname='ヒラギノ角ゴシック W6', family='ヒラギノ角ゴシック', enabled='yes'),
            dict(_name='Disabled', fullname='Disabled', family='Disabled', enabled='no')])]}

    def test_macos_enumerates_actual_names_and_ignores_disabled_faces(self):
        names, families = mac_names(self.data())
        self.assertIn('HiraginoSans-W3', names)
        self.assertEqual(families, ['ヒラギノ角ゴシック'])
        self.assertNotIn('Disabled', names)

    def test_macos_selected_face_matches_postscript_name_without_style_guessing(self):
        calls = []
        def runner(args, **kwargs): calls.append(args); return json.dumps(self.data())
        result = inspect_fonts(['Hiragino Sans W3', 'Hiragino Sans W9'], 'darwin', runner, lambda *args: None)
        self.assertTrue(result['requested'][0]['found'])
        self.assertFalse(result['requested'][1]['found'])
        self.assertFalse(result['ready'])
        self.assertEqual(calls[0], ['/usr/sbin/system_profiler', 'SPFontsDataType', '-json'])

    def test_exact_localized_name_is_recorded_as_exact(self):
        result = inspect_fonts(['ヒラギノ角ゴシック W3'], 'darwin', lambda *a, **k: json.dumps(self.data()), lambda *a: None)
        self.assertTrue(result['ready'])
        self.assertEqual(result['requested'][0]['match'], 'exact')

    def test_windows_reuses_read_only_font_listing_and_keeps_one_name_response(self):
        calls = []
        def runner(args, **kwargs): calls.append(args); return json.dumps('Arial')
        result = inspect_fonts(['Arial'], 'win32', runner, lambda *args: 'powershell.exe')
        self.assertTrue(result['ready'])
        self.assertIn('-Fonts', calls[0])
        self.assertNotIn('-ExecutionPolicy', calls[0])
        self.assertEqual(result['families'], ['Arial'])

    def test_missing_font_does_not_install_substitute_or_rewrite_names(self):
        result = inspect_fonts(['Missing'], 'win32', lambda *a, **k: '["Arial"]', lambda *a: 'powershell.exe')
        self.assertFalse(result['ready'])
        self.assertEqual(result['names'], ['Arial'])
        self.assertEqual(result['requested'][0]['matching_names'], [])

    def test_empty_or_malformed_inventory_is_not_reported_ready(self):
        result = inspect_fonts([], 'darwin', lambda *a, **k: '{}', lambda *a: None)
        self.assertFalse(result['ready'])
        with self.assertRaises(SpecError): mac_names([])
        with self.assertRaises(SpecError):
            inspect_fonts([], 'win32', lambda *a, **k: '{"not":"a list"}', lambda *a: 'powershell.exe')

    def test_other_platforms_remain_explicitly_unverified(self):
        with self.assertRaisesRegex(SpecError, 'Windows and macOS'):
            inspect_fonts([], 'linux', lambda *a, **k: '', lambda *a: None)

    def test_selected_name_check_can_omit_the_large_inventory(self):
        result = inspect_fonts(['Hiragino Sans W3'], 'darwin', lambda *a, **k: json.dumps(self.data()),
                               lambda *a: None, include_names=False)
        self.assertTrue(result['ready'])
        self.assertGreater(result['name_count'], 0)
        self.assertNotIn('names', result)
        self.assertNotIn('families', result)
        self.assertTrue(result['requested'][0]['found'])


if __name__ == '__main__':
    unittest.main()
