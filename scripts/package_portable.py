"""Build the Windows x64 PORTABLE distribution from verified local runtime archives."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
import zipfile


def extract(archive, destination, expected):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise ValueError('Runtime SHA256 mismatch: ' + str(archive))
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            path = PurePosixPath(entry.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in entry.filename
                    or ':' in entry.filename or (entry.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('Unsafe archive member: ' + entry.filename)
        source.extractall(destination)


def package(inputs, output, npm, cache=None):
    root = Path(__file__).resolve().parents[1]
    runtime_source = root / 'packaging/windows'
    lock = json.loads((runtime_source / 'runtime-lock.json').read_text())
    version = (root / 'VERSION').read_text().strip()
    output = output.resolve()
    if output.exists():
        raise ValueError('Refusing to overwrite: ' + str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='decksmith-portable-') as temporary:
        temporary = str(Path(temporary).resolve())
        stage = Path(temporary) / 'decksmith-portable'
        stage.mkdir()
        (stage / 'templates').mkdir()
        shutil.copy2(root / 'skills/decksmith/assets/decksmith.yaml', stage / 'templates/decksmith.yaml')
        for name in ('decksmith.cmd', 'launcher.py', 'runtime-lock.json'):
            shutil.copy2(runtime_source / name, stage / name)
        for name in ('VERSION', 'LICENSE', 'README.md', 'USER_GUIDE.md', 'PORTABLE_GUIDE.md', 'BROWSER_TRIAL.md'):
            shutil.copy2(root / name, stage / name)
        skill = stage / 'skills/decksmith'
        shutil.copytree(root / 'skills/decksmith', skill,
                        ignore=shutil.ignore_patterns('node_modules', '__pycache__', '*.pyc'))
        python = stage / 'runtime/python'
        python.mkdir(parents=True)
        extract(inputs / lock['python']['filename'], python, lock['python']['sha256'])
        node_tmp = Path(temporary) / 'node'
        extract(inputs / lock['node']['filename'], node_tmp, lock['node']['sha256'])
        node = stage / 'runtime/node'
        node.mkdir()
        original = node_tmp / ('node-v' + lock['node']['version'] + '-win-x64')
        for name in ('node.exe', 'LICENSE'):
            shutil.copy2(original / name, node / name)
        pth_files = list(python.glob('*._pth'))
        if len(pth_files) != 1:
            raise ValueError('Expected exactly one embedded Python path configuration')
        pth_files[0].write_text('python313.zip\n.\n../../skills/decksmith/scripts\n', encoding='utf-8')
        # Install in a standalone dependency directory, outside the nested skill tree.
        deps = Path(temporary) / 'dependencies'
        deps.mkdir()
        for name in ('package.json', 'package-lock.json'):
            shutil.copy2(skill / name, deps / name)
        cmd = [npm, 'ci', '--prefix', str(deps), '--ignore-scripts', '--no-audit', '--no-fund', '--no-bin-links']
        if cache:
            cmd += ['--offline', '--cache', str(cache.resolve())]
        subprocess.run(cmd, check=True, cwd=str(deps))
        shutil.copytree(deps / 'node_modules', skill / 'node_modules')
        manifest = {'distribution': 'portable', 'platform': 'windows-x64',
                    'decksmith_version': version, 'runtimes': lock,
                    'windows_execution_verified': False,
                    'package_lock_sha256': hashlib.sha256((skill / 'package-lock.json').read_bytes()).hexdigest()}
        (stage / 'portable-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        with output.open('xb') as stream, zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    archive.write(path, path.relative_to(stage.parent))
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--npm', default='npm')
    parser.add_argument('--cache', type=Path)
    args = parser.parse_args()
    print(package(args.inputs, args.output, args.npm, args.cache))
