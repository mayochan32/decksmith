"""Build one standard package for all supported hosts. Does not install or publish it."""
import argparse
from pathlib import Path
import shutil
import tempfile
import zipfile
import json
from release_version import check

def package(output):
    root=Path(__file__).resolve().parents[1]
    check(root)
    target=output.resolve()/"decksmith"
    if target.exists() or target.is_symlink(): raise ValueError("Refusing to overwrite package: "+str(target))
    target.mkdir(parents=True)
    (target/"templates").mkdir()
    shutil.copy2(root/"skills/decksmith/assets/decksmith.yaml",target/"templates/decksmith.yaml")
    shutil.copy2(root/"skills/decksmith/VERSION",target/"VERSION")
    shutil.copytree(root/"skills",target/"skills",ignore=shutil.ignore_patterns("node_modules","__pycache__","*.pyc", ".DS_Store"))
    # All hosts share one Skill. Copilot uses setup_workspace.py without a manifest.
    for manifest in ("plugin.json", ".codex-plugin", ".claude-plugin", ".agents/plugins", "gemini-extension.json"):
        source=root/manifest
        if source.is_dir():
            (target/manifest).parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source,target/manifest)
        else: shutil.copy2(source,target/manifest)
    for filename in ("README.md","USER_GUIDE.md","PORTABLE_GUIDE.md","BROWSER_TRIAL.md","LICENSE"):
        if (root/filename).is_file(): shutil.copy2(root/filename,target/filename)
    (target/"scripts").mkdir()
    shutil.copy2(root/"scripts/setup_workspace.py",target/"scripts/setup_workspace.py")
    return target


def archive_folder(folder, output):
    """Archive with one top-level directory, without overwriting existing files."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(folder.parent))
    return output


def package_browser(output):
    """Make experimental upload archives; do not install, upload or claim support."""
    root = Path(__file__).resolve().parents[1]
    version = check(root)
    output = output.resolve()
    paths = [output / f'decksmith-{version}-{name}-experimental.zip'
             for name in ('claude-skill', 'chatgpt-plugin')]
    for path in paths:
        if path.exists() or path.is_symlink():
            raise ValueError('Refusing to overwrite: ' + str(path))
    with tempfile.TemporaryDirectory(prefix='decksmith-browser-package-') as raw:
        standard = package(Path(raw) / 'plugin')
        skill = Path(raw) / 'skill/decksmith'
        shutil.copytree(standard / 'skills/decksmith', skill)
        for folder in (skill, standard / 'skills/decksmith'):
            (folder / 'browser-trial.json').write_text(json.dumps({
                'decksmith_version': version, 'experimental': True,
                'browser_execution_verified': False,
                'required_result': 'pptx_and_all_previews_then_visual_review',
                'runtime_bundled': False, 'mcp_required': False,
            }, indent=2) + '\n', encoding='utf-8')
        shutil.copy2(root / 'LICENSE', skill / 'LICENSE')
        archive_folder(skill, paths[0])
        archive_folder(standard, paths[1])
    return paths

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument('--browser-trial', action='store_true', help='Build experimental Claude skill and ChatGPT plugin ZIPs')
    parser.add_argument('--zip', action='store_true', help='Also archive the standard distribution')
    args=parser.parse_args()
    if args.browser_trial:
        if args.zip: parser.error('--zip and --browser-trial are separate packaging modes')
        print(json.dumps([str(p) for p in package_browser(args.output)], ensure_ascii=False))
    else:
        if args.zip:
            name = f'decksmith-{check()}.zip'
            archive = args.output.resolve() / name
            if archive.exists() or archive.is_symlink():
                parser.error('Refusing to overwrite: ' + str(archive))
        target = package(args.output)
        print(archive_folder(target, archive) if args.zip else target)
