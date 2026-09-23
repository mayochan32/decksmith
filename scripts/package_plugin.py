"""Build an isolated provider package. Does not install or publish it."""
import argparse
from pathlib import Path
import shutil

def package(host,output):
    root=Path(__file__).resolve().parents[1]
    target=output.resolve()/"decksmith"
    if target.exists(): raise ValueError("Refusing to overwrite package: "+str(target))
    manifest={"codex":".codex-plugin","claude":".claude-plugin","gemini":"gemini-extension.json"}[host]
    target.mkdir(parents=True)
    shutil.copytree(root/"skills",target/"skills",ignore=shutil.ignore_patterns("node_modules","__pycache__","*.pyc"))
    source=root/manifest
    if source.is_dir(): shutil.copytree(source,target/manifest)
    else: shutil.copy2(source,target/manifest)
    for filename in ("README.md","USER_GUIDE.md","LICENSE"):
        if (root/filename).is_file(): shutil.copy2(root/filename,target/filename)
    (target/"scripts").mkdir()
    shutil.copy2(root/"scripts/setup_workspace.py",target/"scripts/setup_workspace.py")
    return target

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host",choices=("codex","claude","gemini"),required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    print(package(args.host,args.output))
