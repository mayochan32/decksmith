"""Copy DeckSmith into a VS Code workspace without overwriting existing skills."""
import argparse
import json
from pathlib import Path
import shutil
import sys

def setup(workspace, host, dry_run=False):
    source=Path(__file__).resolve().parents[1]/"skills"/"decksmith"
    workspace=Path(workspace).expanduser().resolve()
    if not workspace.is_dir():
        raise ValueError("Create and select an existing workspace directory first.")
    if not (source/"SKILL.md").is_file():
        raise ValueError("Incomplete distribution: skills/decksmith/SKILL.md is missing.")
    roots={"codex":".agents","claude":".claude"}
    selected=list(roots) if host=="both" else [host]
    targets=[workspace/roots[h]/"skills"/"decksmith" for h in selected]
    # Preflight every target before copying, including broken symlinks.
    for target in targets:
        if target.exists() or target.is_symlink():
            raise ValueError("Refusing to overwrite: "+str(target))
        if not target.resolve().is_relative_to(workspace):
            raise ValueError("Skill location points outside the selected workspace: "+str(target))
        if target.resolve().is_relative_to(source.resolve()):
            raise ValueError("Cannot copy a skill inside itself.")
    if not dry_run:
        for target in targets:
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copytree(source,target,ignore=shutil.ignore_patterns("node_modules","__pycache__","*.pyc",".DS_Store"))
    return {"dry_run":dry_run,"workspace":str(workspace),"skills":[str(p) for p in targets],
            "next":"Install Node dependencies in each copied skill, run doctor.py, then start a new extension chat."}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace",required=True,type=Path)
    parser.add_argument("--host",required=True,choices=("codex","claude","both"))
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args()
    try:
        print(json.dumps(setup(args.workspace,args.host,args.dry_run),ensure_ascii=False,indent=2))
        return 0
    except (ValueError,OSError) as error:
        print("DeckSmith: "+str(error),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
