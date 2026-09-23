"""Report portable runtime availability without installing or changing anything."""
import json
import argparse
import sys
from pathlib import Path
from create_deck import executable, run, SpecError
from version import read_version

def inspect():
    result={"decksmith":{"version":read_version()},"python":{"ready":sys.version_info>=(3,9),"version":sys.version.split()[0]}}
    for name,env in (("node","DECKSMITH_NODE"),("soffice","DECKSMITH_SOFFICE"),("pdftoppm","DECKSMITH_PDFTOPPM")):
        try:
            value=executable(name,env)
            result[name]={"ready":True,"path":value}
        except SpecError as error: result[name]={"ready":False,"error":str(error)}
    try:
        node=executable("node","DECKSMITH_NODE")
        result["engine"]=json.loads(run([node,str(Path(__file__).with_name("build_deck.mjs")),"--check"]))
    except (SpecError,ValueError,OSError) as error: result["engine"]={"ready":False,"error":str(error)}
    result["image_generation"]={"status":"host_or_user_supplied","automatic_provider_api":False}
    result["fonts"]={"status":"must_verify_on_target"}
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version",action="version",version="DeckSmith " + read_version())
    parser.parse_args()
    report=inspect()
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(0 if all(report[k]["ready"] for k in ("python","node","soffice","pdftoppm","engine")) else 2)
