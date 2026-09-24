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

def renderer_runtime(renderer):
    if renderer == "none":
        return {}
    if renderer == "libreoffice":
        return {"soffice":executable("soffice","DECKSMITH_SOFFICE"),
                "pdftoppm":executable("pdftoppm","DECKSMITH_PDFTOPPM")}
    if renderer != "powerpoint":
        raise SpecError("Unknown renderer: " + str(renderer))
    if sys.platform != "win32":
        raise SpecError("PowerPoint renderer requires native Windows Python; Mac/WSL are not supported")
    powershell=executable("powershell.exe","DECKSMITH_POWERSHELL")
    command=[powershell,"-NoProfile","-NonInteractive","-STA","-File",
             str(Path(__file__).with_name("powerpoint_export.ps1"))]
    try:
        report=json.loads(run(command+["-Probe"],timeout=30))
        if not isinstance(report,dict) or report.get("ready") is not True:
            raise SpecError("PowerPoint is unavailable")
    except subprocess.TimeoutExpired as error:
        raise SpecError("PowerPoint environment check timed out") from error
    return {"powershell":powershell}

def powerpoint_preview(pptx, directory, scene, powershell, export_pdf):
    result=directory/"preview"; result.mkdir()
    pdf=directory/"pdf"/"candidate.pdf"
    if export_pdf: pdf.parent.mkdir()
    request=directory/"powerpoint-request.json"
    request.write_text(json.dumps({"pptx":str(pptx.resolve()),"preview":str(result.resolve()),
        "pdf":str(pdf.resolve()) if export_pdf else None,"count":len(scene["slides"]),
        "width":round(scene["canvas"]["width"]),"height":round(scene["canvas"]["height"])}),encoding="utf-8")
    try:
        run([powershell,"-NoProfile","-NonInteractive","-STA","-File",
             str(Path(__file__).with_name("powerpoint_export.ps1")),"-RequestPath",str(request.resolve())])
    except subprocess.TimeoutExpired as error:
        raise SpecError("PowerPoint export timed out. Check PowerPoint for dialogs; no fallback was used. "
                        "PowerPoint was not force-closed and may need manual cleanup.") from error
    images=sorted(result.glob("slide-*.png"))
    if len(images) != len(scene["slides"]): raise SpecError("PowerPoint preview page count mismatch")
    for index in range(1,len(scene["slides"])+1):
        image=result/f"slide-{index:02d}.png"
        with image.open("rb") as source: header=source.read(24)
        if header[:8] != b"\x89PNG\r\n\x1a\n" or (int.from_bytes(header[16:20],"big"),int.from_bytes(header[20:24],"big")) != (round(scene["canvas"]["width"]),round(scene["canvas"]["height"])):
            raise SpecError("PowerPoint preview dimensions or PNG signature invalid")
    if export_pdf:
        if not pdf.is_file(): raise SpecError("PowerPoint did not produce a PDF")
        with pdf.open("rb") as source:
            if source.read(5) != b"%PDF-": raise SpecError("PowerPoint PDF signature invalid")
    return result

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
    parser.add_argument("--renderer",choices=("libreoffice","powerpoint","none"))
    args=parser.parse_args()
    print("DeckSmith " + read_version(), file=sys.stderr)
    try:
        if args.config and not args.config.is_file():
            raise SpecError("Missing config: " + str(args.config))
        config=resolve_config(args.config, args.scene.resolve().parent)
        if args.pptx_only and args.renderer not in (None,"none"):
            raise SpecError("--pptx-only conflicts with --renderer")
        renderer="none" if args.pptx_only else (args.renderer or config["output"]["renderer"])
        config["output"]["renderer"]=renderer
        no_preview=renderer == "none"
        if no_preview and config["output"]["pdf"]:
            raise SpecError("output.pdf requires a renderer; cannot use none or --pptx-only")
        args.style=args.style or (Path(config["input"]["style"]) if "style" in config["input"] else None)
        if args.style is None: raise SpecError("Specify --style or input.style")
        if args.output is None:
            if not config["output"]["filename"]:
                raise SpecError("Choose a topic-based --output filename or output.filename")
            args.output=Path(config["output"]["directory"])/config["output"]["filename"]
        scene=compile_scene(args.scene.resolve(),args.style.resolve(),args.structure.resolve())
        if config["size_explicit"] and scene["canvas"] != config["canvas"]:
            raise SpecError("Scene canvas conflicts with config; redesign before rendering")
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
        runtime=renderer_runtime(renderer)
        output.parent.mkdir(parents=True,exist_ok=True)
        work=Path(tempfile.mkdtemp(prefix="."+output.stem+".decksmith-build-",dir=output.parent.parent))
        spec=work/"scene.json"; spec.write_text(json.dumps(scene,ensure_ascii=False),encoding="utf-8")
        candidate=work/"candidate.pptx"
        run([node,str(builder),"--spec",str(spec),"--output",str(candidate)])
        receipt=validate_pptx(candidate,scene)
        if renderer == "libreoffice":
            rendered=preview(candidate,work,scene,**runtime)
        elif renderer == "powerpoint":
            rendered=powerpoint_preview(candidate,work,scene,export_pdf=bool(pdf_output),**runtime)
        else:
            rendered=work/"preview"
        rendered.mkdir(exist_ok=True)
        status="not_visually_reviewed" if no_preview else "pending_visual_review"
        receipt.update(sha256=source_hash(candidate),engine="pptxgenjs",decksmith_version=read_version(),preview_renderer=None if no_preview else renderer)
        (rendered/"validation.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
        config["canvas"]=scene["canvas"]
        config["output"].update(directory=str(output.parent),filename=output.name)
        manifest={"status":status,"output_sha256":receipt["sha256"],
            "decksmith_version":read_version(),
            "project_settings":config,"policy_enforcement":"agent_instructions_not_network_sandbox",
            "style_sha256":scene["style_sha256"],"structure_sha256":scene["structure_sha256"],
            "requirements":scene["requirements"],"slides":[{"id":s["id"],
            "preview":f"slide-{i:02d}.png" if not no_preview else None,"status":"not_visually_reviewed" if no_preview else "pending",
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
        print(json.dumps({"decksmith_version":read_version(),"output":str(output),"preview":None if no_preview else str(previews),"reports":str(previews),"pdf":str(pdf_output) if pdf_output else None,"status":status}))
        return 0
    except (SpecError,OSError,ValueError,subprocess.TimeoutExpired) as error:
        print(f"DeckSmith: {error}",file=sys.stderr); return 2

if __name__=="__main__":
    raise SystemExit(main())
