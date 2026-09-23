"""Validate, render and preview a scene with provider-independent tools."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape
from compile_spec import SpecError, compile_scene, source_hash
from validate_pptx import validate_pptx
from project_config import resolve_config
from version import read_version

def executable(name, env):
    value=os.environ.get(env) or shutil.which(name)
    if not value: raise SpecError(f"Missing {name}; install it or set {env}")
    found=shutil.which(value)
    if not found: raise SpecError(f"Executable not found: {value}")
    return found

def run(command, timeout=180, env=None):
    result=subprocess.run(command,capture_output=True,text=True,timeout=timeout,env=env)
    if result.returncode:
        raise SpecError(result.stderr.strip() or result.stdout.strip() or f"Command failed: {command[0]}")
    return result.stdout

def preview(pptx, directory, scene, soffice, pdftoppm):
    env=os.environ.copy()
    # Headless macOS builds may use fontconfig instead of CoreText.
    # Scope discovery/cache to this render; never modify global font configuration.
    if sys.platform=="darwin" and not env.get("FONTCONFIG_FILE"):
        dirs=[Path("/System/Library/Fonts"),Path("/Library/Fonts"),Path.home()/"Library/Fonts"]
        config=directory/"fonts.conf"
        config.write_text('<?xml version="1.0"?><fontconfig>'+
            "".join("<dir>"+escape(str(p))+"</dir>" for p in dirs if p.is_dir())+
            "<cachedir>"+escape(str(directory/"font-cache"))+"</cachedir></fontconfig>",encoding="utf-8")
        env["FONTCONFIG_FILE"]=str(config)
    profile=directory/"office-profile"
    pdf_dir=directory/"pdf"; pdf_dir.mkdir()
    run([soffice,"-env:UserInstallation="+profile.as_uri(),"--headless","--convert-to","pdf",
         "--outdir",str(pdf_dir),str(pptx)],env=env)
    pdf=pdf_dir/(pptx.stem+".pdf")
    if not pdf.is_file(): raise SpecError("LibreOffice did not produce a PDF")
    result=directory/"preview"; result.mkdir()
    run([pdftoppm,"-png","-scale-to-x",str(round(scene["canvas"]["width"])),
         "-scale-to-y",str(round(scene["canvas"]["height"])),str(pdf),str(result/"page")])
    images=sorted(result.glob("page-*.png"),key=lambda p:int(p.stem.split("-")[-1]))
    if len(images)!=len(scene["slides"]): raise SpecError("Preview page count mismatch")
    for index,image in enumerate(images,1): image.rename(result/f"slide-{index:02d}.png")
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version="DeckSmith " + read_version())
    for name in ("scene","style","structure","output","config"):
        parser.add_argument("--"+name,required=name in ("scene","structure"),type=Path)
    parser.add_argument("--validate-only",action="store_true")
    parser.add_argument("--pptx-only",action="store_true",help="Explicitly skip preview; not visually verified")
    args=parser.parse_args()
    print("DeckSmith " + read_version(), file=sys.stderr)
    try:
        if args.config and not args.config.is_file():
            raise SpecError("Missing config: " + str(args.config))
        config=resolve_config(args.config, args.scene.resolve().parent)
        args.style=args.style or (Path(config["input"]["style"]) if "style" in config["input"] else None)
        if args.style is None: raise SpecError("Specify --style or input.style")
        if args.output is None:
            if not config["output"]["filename"]:
                raise SpecError("Choose a topic-based --output filename or output.filename")
            args.output=Path(config["output"]["directory"])/config["output"]["filename"]
        scene=compile_scene(args.scene.resolve(),args.style.resolve(),args.structure.resolve())
        if config["size_explicit"] and scene["canvas"] != config["canvas"]:
            raise SpecError("Scene canvas conflicts with config; redesign before rendering")
        if config["output"]["pdf"] and args.pptx_only:
            raise SpecError("output.pdf requires preview rendering; remove --pptx-only")
        if args.validate_only:
            print("Scene valid; visual review still required"); return 0
        output=args.output.resolve()
        previews=output.with_suffix(".preview")
        pdf_output=output.with_suffix(".pdf") if config["output"]["pdf"] else None
        if output.suffix.lower()!=".pptx": raise SpecError("Output must end in .pptx")
        if output.exists() or previews.exists(): raise SpecError("Refusing to overwrite output or preview")
        if pdf_output and pdf_output.exists(): raise SpecError("Refusing to overwrite PDF")
        node=executable("node","DECKSMITH_NODE")
        builder=Path(__file__).with_name("build_deck.mjs")
        run([node,str(builder),"--check"])
        if not args.pptx_only:
            soffice=executable("soffice","DECKSMITH_SOFFICE")
            pdftoppm=executable("pdftoppm","DECKSMITH_PDFTOPPM")
        output.parent.mkdir(parents=True,exist_ok=True)
        work=Path(tempfile.mkdtemp(prefix="."+output.stem+".decksmith-build-",dir=output.parent.parent))
        spec=work/"scene.json"; spec.write_text(json.dumps(scene,ensure_ascii=False),encoding="utf-8")
        candidate=work/"candidate.pptx"
        run([node,str(builder),"--spec",str(spec),"--output",str(candidate)])
        receipt=validate_pptx(candidate,scene)
        rendered=preview(candidate,work,scene,soffice,pdftoppm) if not args.pptx_only else work/"preview"
        rendered.mkdir(exist_ok=True)
        receipt.update(sha256=source_hash(candidate),engine="pptxgenjs",decksmith_version=read_version(),preview_renderer="LibreOffice/Poppler" if not args.pptx_only else None)
        (rendered/"validation.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
        config["canvas"]=scene["canvas"]
        config["output"].update(directory=str(output.parent),filename=output.name)
        manifest={"status":"pending_visual_review","output_sha256":receipt["sha256"],
            "decksmith_version":read_version(),
            "project_settings":config,"policy_enforcement":"agent_instructions_not_network_sandbox",
            "style_sha256":scene["style_sha256"],"structure_sha256":scene["structure_sha256"],
            "requirements":scene["requirements"],"slides":[{"id":s["id"],
            "preview":f"slide-{i:02d}.png" if not args.pptx_only else None,"status":"pending",
            "intentional_overflow":[{"id":e["id"],"reason":e["overflow_reason"]} for e in s["elements"] if e.get("overflow_reason")]}
            for i,s in enumerate(scene["slides"],1)]}
        (rendered/"review-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
        # Exclusive creation protects an existing deck even if another process finishes first.
        with output.open("xb") as target, candidate.open("rb") as source:
            shutil.copyfileobj(source,target)
        rendered.rename(previews)
        if pdf_output:
            with pdf_output.open("xb") as target, (work/"pdf"/"candidate.pdf").open("rb") as source:
                shutil.copyfileobj(source,target)
        print(json.dumps({"decksmith_version":read_version(),"output":str(output),"preview":str(previews),"pdf":str(pdf_output) if pdf_output else None,"status":"pending_visual_review"}))
        return 0
    except (SpecError,OSError,ValueError,subprocess.TimeoutExpired) as error:
        print(f"DeckSmith: {error}",file=sys.stderr); return 2

if __name__=="__main__":
    raise SystemExit(main())
