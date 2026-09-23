"""Validate AI-authored scenes without selecting visual layouts."""
import copy
import hashlib
import math
import re
import json
import importlib.util
import sys
from pathlib import Path

class SpecError(ValueError):
    pass

def load_mapping(path):
    raw = Path(path).read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        module_name = "_decksmith_yaml"
        if module_name not in sys.modules:
            package = Path(__file__).parent / "vendor" / "yaml"
            spec = importlib.util.spec_from_file_location(module_name, package / "__init__.py",
                submodule_search_locations=[str(package)])
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        yaml = sys.modules[module_name]
        try:
            value = yaml.safe_load(raw)
        except yaml.YAMLError as error:
            raise SpecError(f"Invalid YAML: {path}: {error}") from error
    if not isinstance(value, dict):
        raise SpecError(f"Expected mapping: {path}")
    return value

def source_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def leaves(value, pointer=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from leaves(item, pointer+"/"+str(key).replace("~","~0").replace("/","~1"))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from leaves(item, pointer+"/"+str(i))
    else:
        yield pointer

def keys(value, allowed, where):
    if not isinstance(value, dict):
        raise SpecError(f"{where}: expected mapping")
    unknown = set(value)-set(allowed.split())
    if unknown:
        raise SpecError(f"{where}: unsupported fields {sorted(unknown)}")

def number(value, where, minimum=None):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise SpecError(f"{where}: expected finite number")
    if minimum is not None and value < minimum:
        raise SpecError(f"{where}: must be >= {minimum}")
    return value

def text(value, where):
    if not isinstance(value,str) or not value.strip():
        raise SpecError(f"{where}: expected non-empty text")
    return value

def color(value, where):
    if value != "none" and not re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?",str(value)):
        raise SpecError(f"{where}: expected hex color or none")

def text_content(e):
    return e["text"] if "text" in e else "".join(r["text"] for r in e.get("runs",[]))

def compact(value):
    return re.sub(r"\s+","",value)

TYPES = {
    "text":"text runs font size color bold italic align vertical line_spacing",
    "shape":"geometry fill stroke stroke_width radius",
    "path":"points closed fill stroke stroke_width",
    "image":"path alt fit prompt",
}

def compile_scene(scene_path, style_path, structure_path):
    scene = copy.deepcopy(load_mapping(scene_path))
    keys(scene,"schema_version canvas style_sha256 structure_sha256 requirements slides","scene")
    if scene.get("schema_version") != "1.0":
        raise SpecError("schema_version must be 1.0")
    for name, source in (("style",style_path),("structure",structure_path)):
        if scene.get(name+"_sha256") != source_hash(source):
            raise SpecError(f"{name} changed or missing fingerprint; reinterpret before rendering")
    canvas = scene.setdefault("canvas", {"width": 1920, "height": 1080})
    keys(canvas,"width height","canvas")
    for axis in ("width","height"):
        number(canvas.get(axis),"canvas."+axis,1)
    source = load_mapping(structure_path)
    keys(source,"slides","structure")
    contents = source.get("slides")
    if not isinstance(contents,list) or not contents:
        raise SpecError("structure.slides must be non-empty")
    content_ids = []
    for item in contents:
        keys(item,"id purpose required_text notes citations","content slide")
        content_ids.append(text(item.get("id"),"content id"))
        if not isinstance(item.get("required_text"),list) or not item["required_text"]:
            raise SpecError("Each content slide needs required_text")
        for value in item["required_text"]:
            text(value,"required_text")
    if len(set(content_ids)) != len(content_ids):
        raise SpecError("Duplicate content slide IDs")
    slides = scene.get("slides")
    if not isinstance(slides,list) or any(not isinstance(s,dict) for s in slides) or [s.get("id") for s in slides] != content_ids:
        raise SpecError("Scene must preserve all content slides and their order")
    target_ids = set()
    for slide, content in zip(slides,contents):
        keys(slide,"id background elements notes","slide")
        sid = text(slide.get("id"),"slide.id")
        target_ids.add(sid)
        color(slide.get("background"),sid+".background")
        elements = slide.get("elements")
        if not isinstance(elements,list) or not elements:
            raise SpecError(f"{sid}: elements must be non-empty")
        element_ids = set()
        for e in elements:
            if not isinstance(e,dict) or e.get("type") not in TYPES:
                raise SpecError(f"{sid}: unsupported element type; no fallback")
            kind = e["type"]
            keys(e,"id type x y width height rotation overflow_reason "+TYPES[kind],sid)
            eid = text(e.get("id"),"element.id")
            if eid in element_ids:
                raise SpecError(f"{sid}: duplicate element {eid}")
            element_ids.add(eid)
            target_ids.add(sid+"/"+eid)
            for axis in ("x","y","width","height"):
                number(e.get(axis),eid+"."+axis,0.01 if axis in ("width","height") else None)
            angle = math.radians(number(e.get("rotation",0),eid+".rotation"))
            bw = abs(e["width"]*math.cos(angle))+abs(e["height"]*math.sin(angle))
            bh = abs(e["width"]*math.sin(angle))+abs(e["height"]*math.cos(angle))
            cx,cy=e["x"]+e["width"]/2,e["y"]+e["height"]/2
            if cx-bw/2 < -0.01 or cy-bh/2 < -0.01 or cx+bw/2 > canvas["width"]+0.01 or cy+bh/2 > canvas["height"]+0.01:
                text(e.get("overflow_reason"),eid+".overflow_reason")
            if kind == "text":
                if ("text" in e) == ("runs" in e):
                    raise SpecError(f"{eid}: use exactly one of text or runs")
                text(e.get("font"),eid+".font")
                number(e.get("size"),eid+".size",1)
                color(e.get("color"),eid+".color")
                if e.get("align","left") not in ("left","center","right","justify"):
                    raise SpecError(f"{eid}: invalid align")
                if e.get("vertical","top") not in ("top","middle","bottom"):
                    raise SpecError(f"{eid}: invalid vertical")
                if "line_spacing" in e: number(e["line_spacing"],eid+".line_spacing",0.1)
                if "runs" in e:
                    if not isinstance(e["runs"],list) or not e["runs"]:
                        raise SpecError(f"{eid}: empty runs")
                    for run in e["runs"]:
                        keys(run,"text font size color bold italic",eid+".run")
                        text(run.get("text"),eid+".run.text")
                        if "size" in run: number(run["size"],eid+".run.size",1)
                        if "color" in run: color(run["color"],eid+".run.color")
                text(text_content(e),eid+".text")
            elif kind == "image":
                raw=Path(text(e.get("path"),eid+".path"))
                base=Path(scene_path).resolve().parent
                asset=(base/raw).resolve()
                if raw.is_absolute() or not asset.is_relative_to(base):
                    raise SpecError(f"{eid}: image must be project-relative")
                if not asset.is_file() or asset.suffix.lower() not in (".png",".jpg",".jpeg"):
                    raise SpecError(f"{eid}: missing/unsupported image")
                text(e.get("alt"),eid+".alt")
                if e.get("fit","contain") not in ("cover","contain"):
                    raise SpecError(f"{eid}: invalid fit")
                e["path"]=str(asset)
            else:
                for key in ("fill","stroke"):
                    if key in e: color(e[key],eid+"."+key)
                if "stroke_width" in e: number(e["stroke_width"],eid+".stroke_width",0)
                if "radius" in e: number(e["radius"],eid+".radius",0)
                if kind == "shape" and e.get("geometry") not in ("rect","roundRect","ellipse","line","triangle","rightArrow"):
                    raise SpecError(f"{eid}: unsupported geometry; use path")
                if kind == "path":
                    points=e.get("points")
                    if not isinstance(points,list) or len(points)<2:
                        raise SpecError(f"{eid}: path needs two points")
                    for point in points:
                        if not isinstance(point,list) or len(point)!=2:
                            raise SpecError(f"{eid}: invalid point")
                        for v in point: number(v,eid+".point")
        native=compact("".join(text_content(e) for e in elements if e["type"]=="text"))
        for required in content["required_text"]:
            if compact(required) not in native:
                raise SpecError(f"{sid}: missing editable content {required!r}")
        slide["notes"]="\n".join(filter(None,[content.get("notes",""),slide.get("notes",""),
            *("Source: "+str(c) for c in content.get("citations",[]))]))
    requirements=scene.get("requirements")
    if not isinstance(requirements,list) or not requirements:
        raise SpecError("requirements ledger is required")
    pointers=set(leaves(load_mapping(style_path)))
    covered=set()
    for req in requirements:
        keys(req,"source interpretation status targets reason","requirement")
        pointer=req.get("source")
        if pointer not in pointers or pointer in covered:
            raise SpecError(f"Invalid/duplicate style pointer: {pointer}")
        covered.add(pointer)
        text(req.get("interpretation"),"requirement interpretation")
        if req.get("status")=="implemented":
            targets=req.get("targets")
            if not isinstance(targets,list) or not targets or not set(targets)<=target_ids:
                raise SpecError(f"{pointer}: implemented requirement needs valid targets")
        elif req.get("status")=="not_applicable":
            text(req.get("reason"),"not_applicable reason")
        else:
            raise SpecError(f"{pointer}: unresolved requirement; no silent substitution")
    if pointers-covered:
        raise SpecError(f"Uninterpreted style fields: {sorted(pointers-covered)}")
    return scene
