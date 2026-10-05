"""Report portable runtime availability without installing or changing anything."""
import json
import argparse
import sys
import subprocess
import os
from pathlib import Path
from create_deck import executable, run, SpecError, renderer_runtime
from project_config import resolve_config
from version import read_version
from process_environment import child_environment

def inspect(renderer="libreoffice"):
    result={"decksmith":{"version":read_version()},"python":{"ready":sys.version_info>=(3,9),"version":sys.version.split()[0]},
            "execution_context":{"platform":sys.platform,"python_executable":sys.executable,
                                 "cwd":str(Path.cwd()),"powershell_override":os.environ.get('DECKSMITH_POWERSHELL'),
                                 "sandbox":"not_detected; compare failing and successful host contexts"}}
    try:
        _, environment_report = child_environment()
        result["execution_context"]["windows_environment"] = {"ready": True, **environment_report}
    except ValueError as error:
        result["execution_context"]["windows_environment"] = {"ready": False, "error": str(error)}
    required=[("node","DECKSMITH_NODE")]
    if renderer == "libreoffice":
        required.extend((("soffice","DECKSMITH_SOFFICE"),("pdftoppm","DECKSMITH_PDFTOPPM")))
    for name,env in required:
        try:
            value=executable(name,env)
            result[name]={"ready":True,"path":value}
        except (SpecError,ValueError,OSError) as error: result[name]={"ready":False,"error":str(error)}
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
            result["powerpoint"]={"ready":False,"stage":"powershell_probe","cause":"undetermined","error":str(error),
                "next":"First check execution_context.windows_environment and the failing process/exit code. "
                       "If scripts are blocked, inspect Get-ExecutionPolicy -List and the downloaded file's trust status. "
                       "Ask the user/admin; do not automatically change policy, unblock files, or bypass it. "
                       "COM registration and PNG/PDF export are separate checks."}
    if renderer not in ("none","libreoffice","powerpoint"):
        raise SpecError("Unknown renderer")
    requirements=["python","node","engine"]+(["soffice","pdftoppm"] if renderer=="libreoffice" else ["powerpoint"] if renderer=="powerpoint" else [])
    result["renderer"]={"selected":renderer,"ready":all(result[k]["ready"] for k in requirements)
                        and result["execution_context"]["windows_environment"]["ready"]}
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version",action="version",version="DeckSmith " + read_version())
    parser.add_argument("--config",type=Path)
    parser.add_argument("--renderer",choices=("libreoffice","powerpoint","none"))
    parser.add_argument("--test-export",action="store_true",help="Explicitly open a temporary test deck in PowerPoint and test PNG/PDF")
    parser.add_argument("--fonts",action="store_true",help="List installed Windows font families (does not prove glyph coverage)")
    args=parser.parse_args()
    try:
        config=resolve_config(args.config)
        renderer=args.renderer or config["output"]["renderer"]
        if renderer=="none" and config["output"]["pdf"]:
            raise SpecError("output.pdf cannot be true with renderer=none")
        report=inspect(renderer)
        extra_ready = True
        if args.fonts:
            if sys.platform != 'win32':
                raise SpecError('--fonts currently supports Windows; verify fonts using the local host on other platforms')
            try:
                powershell = executable('powershell.exe','DECKSMITH_POWERSHELL')
                names = json.loads(run([powershell,'-NoProfile','-NonInteractive','-STA','-File',
                                       str(Path(__file__).with_name('powerpoint_export.ps1')),'-Fonts']))
                report['fonts'] = {'status':'families_enumerated_not_glyph_verified','families':names}
            except (SpecError,OSError,ValueError,subprocess.TimeoutExpired) as error:
                report['fonts'] = {'status':'failed','stage':'font_enumeration','error':str(error)}
                extra_ready = False
        if args.test_export:
            if renderer != 'powerpoint':
                raise SpecError('--test-export requires --renderer powerpoint')
            from runtime_probe import test_export
            report['export_test'] = test_export()
            extra_ready = extra_ready and all(report['export_test'][key]['ready'] for key in ('png','pdf'))
        print(json.dumps(report,ensure_ascii=False,indent=2))
        raise SystemExit(0 if report["renderer"]["ready"] and extra_ready else 2)
    except (SpecError,OSError,ValueError,subprocess.TimeoutExpired) as error:
        parser.exit(2,"DeckSmith: " + str(error) + "\n")
