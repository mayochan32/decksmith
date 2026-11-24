"""Read installed font names on the current host; never substitute or install.

Name matching does not prove glyph coverage, font metrics or renderer behaviour.
"""
import json
from pathlib import Path
import re
import sys
import unicodedata

from compile_spec import SpecError


def font_key(value):
    return re.sub(r'[\s_-]+', '', unicodedata.normalize('NFKC', value).casefold())


def mac_names(data):
    if not isinstance(data, dict):
        raise SpecError('Unexpected macOS font-inventory response')
    names, families = set(), set()

    def walk(value):
        if isinstance(value, dict):
            if value.get('enabled') == 'no' or value.get('valid') == 'no': return
            if isinstance(value.get('typefaces'), list):
                for face in value['typefaces']:
                    if not isinstance(face, dict): continue
                    if face.get('enabled') == 'no' or face.get('valid') == 'no': continue
                    if isinstance(face.get('family'), str): families.add(face['family'])
                    names.update(face[k] for k in ('family', 'fullname', '_name') if isinstance(face.get(k), str) and face[k].strip())
            for child in value.values(): walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(data.get('SPFontsDataType', []))
    return sorted(names), sorted(families)


def inspect_fonts(requested=(), platform=None, runner=None, locate=None, include_names=True):
    if runner is None or locate is None:
        from create_deck import run, executable
        runner = runner or run; locate = locate or executable
    platform = platform or sys.platform
    if platform == 'darwin':
        raw = runner(['/usr/sbin/system_profiler', 'SPFontsDataType', '-json'], timeout=60)
        names, families = mac_names(json.loads(raw)); method = 'macOS system_profiler'
    elif platform == 'win32':
        powershell = locate('powershell.exe', 'DECKSMITH_POWERSHELL')
        value = json.loads(runner([powershell, '-NoProfile', '-NonInteractive', '-STA', '-File',
            str(Path(__file__).with_name('powerpoint_export.ps1')), '-Fonts'], timeout=60))
        if isinstance(value, str): value = [value]
        if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
            raise SpecError('Unexpected Windows font-family response')
        names = families = sorted(set(v for v in value if v.strip())); method = 'Windows installed font families'
    else:
        raise SpecError('Font enumeration currently supports native Windows and macOS; inspect fonts locally on other hosts')
    wanted = list(dict.fromkeys(requested))
    if any(not isinstance(v, str) or not v.strip() for v in wanted):
        raise SpecError('Requested font names must be non-empty strings')
    checks = []
    for name in wanted:
        exact = [v for v in names if v == name]
        matching = exact or [v for v in names if font_key(v) == font_key(name)]
        checks.append({'requested': name, 'found': bool(matching), 'matching_names': matching,
                       'match': 'exact' if exact else 'normalized_name' if matching else 'missing'})
    report = {'ready': bool(names) and all(c['found'] for c in checks),
            'status': 'names_enumerated_not_glyph_or_renderer_verified', 'platform': platform,
            'method': method, 'requested': checks, 'name_count': len(names), 'family_count': len(families),
            'scope': 'Names on this host only; normalization ignores case, whitespace, hyphens and underscores. No substitution, glyph coverage, font embedding or client rendering test.'}
    if include_names: report.update(families=families, names=names)
    return report
