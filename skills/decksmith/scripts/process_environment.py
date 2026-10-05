"""Minimal child-only Windows environment repair; never changes host settings."""
import ctypes
import ntpath
import os
import sys


REPAIR_OPTION = 'DECKSMITH_WINDOWS_ENV_REPAIR'


def windows_directory():
    """Use the OS, not a guessed drive or a subprocess needing the missing env."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    query = kernel.GetSystemWindowsDirectoryW
    query.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
    query.restype = ctypes.c_uint
    size = 260
    for _ in range(3):
        buffer = ctypes.create_unicode_buffer(size)
        length = query(buffer, size)
        if not length:
            raise OSError(ctypes.get_last_error(), 'GetSystemWindowsDirectoryW failed')
        if length < size:
            value = buffer.value
            if not ntpath.isabs(value) or not os.path.isdir(value):
                raise ValueError('Windows API returned an invalid OS directory')
            return value
        size = length + 1
    raise ValueError('Windows directory exceeds API buffer limit')


def child_environment(source=None):
    env = dict(os.environ if source is None else source)
    report = {'status': 'not_applicable', 'added': [], 'source': None}
    if sys.platform != 'win32':
        return env, report
    # Windows names are case-insensitive, including explicit env dictionaries.
    grouped = {}
    for key in env:
        grouped.setdefault(key.upper(), []).append(key)
    for name in ('SYSTEMROOT', 'WINDIR', REPAIR_OPTION):
        if len(grouped.get(name, [])) > 1:
            raise ValueError('WINDOWS_ENV_CONFLICT: duplicate ' + name)
    def value(name):
        keys = grouped.get(name.upper(), [])
        return env[keys[0]] if keys else None
    option = value(REPAIR_OPTION)
    if option not in (None, '0', '1'):
        raise ValueError(REPAIR_OPTION + ' must be 0 or 1')
    missing = [name for name in ('SystemRoot', 'WINDIR') if not value(name)]
    if missing and option == '0':
        raise ValueError('WINDOWS_ENV_MISSING: ' + ', '.join(missing) +
                         '; repair disabled. Ask the user/admin; do not change host policy.')
    try:
        directory = windows_directory()
    except (OSError, ValueError) as error:
        raise ValueError('WINDOWS_ENV_UNRESOLVED: cannot obtain OS directory; ' + str(error)) from error
    for name in ('SystemRoot', 'WINDIR'):
        current = value(name)
        if current and ntpath.normcase(ntpath.normpath(current)) != ntpath.normcase(ntpath.normpath(directory)):
            raise ValueError('WINDOWS_ENV_CONFLICT: ' + name +
                             ' differs from Windows API; no override performed. Ask the user/admin.')
    for name in missing:
        for key in grouped.get(name.upper(), []):
            del env[key]
        env[name] = directory
    report.update(status='repaired' if missing else 'valid', added=missing,
                  source='GetSystemWindowsDirectoryW', windows_directory=directory)
    return env, report


def announce_repair(report):
    if report['added']:
        print('DeckSmith: Windows child environment: added ' + ', '.join(report['added']) +
              ' from ' + report['source'] + ' (' + report['windows_directory'] +
              '); host settings unchanged.', file=sys.stderr)


def powershell_path(env):
    root = next((v for k, v in env.items() if k.upper() == 'SYSTEMROOT'), None)
    if not root:
        raise ValueError('WINDOWS_ENV_MISSING: SystemRoot')
    return ntpath.join(root, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
