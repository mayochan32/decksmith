"""Report portable runtime availability without installing or changing anything."""
import json
import argparse
import sys
from pathlib import Path
from create_deck import executable, run, SpecError, renderer_runtime
from project_config import resolve_config
from version import read_version

def inspect(renderer="libreoffice"):
    result={"decksmith":{"version":read_version()},"python":{"ready":sys.version_info>=(3,9),"version":sys.version.split()[0]}}
    required=[("node","DECKSMITH_NODE")]
    if renderer == "libreoffice":
        required.extend((("soffice","DECKSMITH_SOFFICE"),("pdftoppm","DECKSMITH_PDFTOPPM")))
    for name,env in required:
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
    if renderer == "powerpoint":
        try:
            result["powerpoint"]={"ready":True,**renderer_runtime(renderer),"check":"COM registration only; export not yet verified"}
        except (SpecError,ValueError,OSError) as error:
            result["powerpoint"]={"ready":False,"error":str(error)}
    if renderer not in ("none","libreoffice","powerpoint"):
        raise SpecError("Unknown renderer")
    requirements=["python","node","engine"]+(["soffice","pdftoppm"] if renderer=="libreoffice" else ["powerpoint"] if renderer=="powerpoint" else [])
    result["renderer"]={"selected":renderer,"ready":all(result[k]["ready"] for k in requirements)}
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version",action="version",version="DeckSmith " + read_version())
    parser.add_argument("--config",type=Path)
    parser.add_argument("--renderer",choices=("libreoffice","powerpoint","none"))
    args=parser.parse_args()
    try:
        config=resolve_config(args.config)
        renderer=args.renderer or config["output"]["renderer"]
        if renderer=="none" and config["output"]["pdf"]:
            raise SpecError("output.pdf cannot be true with renderer=none")
        report=inspect(renderer)
        print(json.dumps(report,ensure_ascii=False,indent=2))
        raise SystemExit(0 if report["renderer"]["ready"] else 2)
    except (SpecError,OSError,ValueError) as error:
        parser.exit(2,"DeckSmith: " + str(error) + "\n")
