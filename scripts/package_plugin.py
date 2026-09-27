"""Build one standard package for all supported hosts. Does not install or publish it."""
import argparse
from pathlib import Path
import shutil
from release_version import check

def package(output):
    root=Path(__file__).resolve().parents[1]
    check(root)
    target=output.resolve()/"decksmith"
    if target.exists(): raise ValueError("Refusing to overwrite package: "+str(target))
    target.mkdir(parents=True)
    (target/"templates").mkdir()
    shutil.copy2(root/"skills/decksmith/assets/decksmith.yaml",target/"templates/decksmith.yaml")
    shutil.copy2(root/"skills/decksmith/VERSION",target/"VERSION")
    shutil.copytree(root/"skills",target/"skills",ignore=shutil.ignore_patterns("node_modules","__pycache__","*.pyc"))
    # All hosts share one Skill. Copilot uses setup_workspace.py without a manifest.
    for manifest in (".codex-plugin", ".claude-plugin", "gemini-extension.json"):
        source=root/manifest
        if source.is_dir(): shutil.copytree(source,target/manifest)
        else: shutil.copy2(source,target/manifest)
    for filename in ("README.md","USER_GUIDE.md","PORTABLE_GUIDE.md","LICENSE"):
        if (root/filename).is_file(): shutil.copy2(root/filename,target/filename)
    (target/"scripts").mkdir()
    shutil.copy2(root/"scripts/setup_workspace.py",target/"scripts/setup_workspace.py")
    return target

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    print(package(args.output))
