"""Synchronize release metadata from the canonical skill VERSION file."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = Path("skills/decksmith/VERSION")
METADATA = (".codex-plugin/plugin.json", ".claude-plugin/plugin.json", "gemini-extension.json",
            "skills/decksmith/package.json", "skills/decksmith/package-lock.json")


def validate(value):
    if not re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value):
        raise ValueError("Version must be vx.y.z, e.g. v0.4.1")
    return value


def check(root=ROOT):
    value=validate((root/VERSION_FILE).read_text().strip())
    if (root/"VERSION").read_text().strip() != value:
        raise ValueError("Version mismatch: VERSION")
    for name in METADATA:
        data=json.loads((root/name).read_text())
        if data["version"] != value[1:]:
            raise ValueError("Version mismatch: " + name)
        if name.endswith("package-lock.json") and data["packages"][""]["version"] != value[1:]:
            raise ValueError("Lockfile root version mismatch")
    return value


def set_version(value, root=ROOT):
    validate(value)
    # Parse all files before changing anything; never modify dependency versions.
    updates={}
    for name in METADATA:
        data=json.loads((root/name).read_text())
        data["version"]=value[1:]
        if name.endswith("package-lock.json"):
            data["packages"][""]["version"]=value[1:]
        updates[name]=json.dumps(data,ensure_ascii=False,indent=2)+"\n"
    for name, content in updates.items():
        (root/name).write_text(content,encoding="utf-8")
    (root/VERSION_FILE).write_text(value+"\n",encoding="utf-8")
    (root/"VERSION").write_text(value+"\n",encoding="utf-8")
    return check(root)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check",action="store_true")
    group.add_argument("--set",metavar="vx.y.z")
    args=parser.parse_args()
    try:
        print(set_version(args.set) if args.set else check())
    except (ValueError,OSError,KeyError) as error:
        parser.exit(2,str(error)+"\n")
