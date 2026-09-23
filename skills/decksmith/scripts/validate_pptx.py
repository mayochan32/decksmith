"""Provider-independent OOXML checks; visual review remains separate."""
import posixpath
import re
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from compile_spec import SpecError, compact, text_content

NS={"p":"http://schemas.openxmlformats.org/presentationml/2006/main",
    "a":"http://schemas.openxmlformats.org/drawingml/2006/main"}

def validate_pptx(path, scene):
    with ZipFile(path) as archive:
        bad=archive.testzip()
        if bad: raise SpecError(f"Corrupt ZIP member: {bad}")
        names=set(archive.namelist())
        for name in names:
            if name.endswith((".xml",".rels")):
                root=ET.fromstring(archive.read(name))
                if name.endswith(".rels"):
                    base=posixpath.dirname(posixpath.dirname(name))
                    for rel in root:
                        if rel.get("TargetMode")=="External": continue
                        target=unquote(rel.get("Target",""))
                        resolved=target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(base,target))
                        if resolved not in names:
                            raise SpecError(f"Missing relationship target: {name}: {resolved}")
        presentation=ET.fromstring(archive.read("ppt/presentation.xml"))
        size=presentation.find("p:sldSz",NS)
        if (int(size.get("cx")),int(size.get("cy"))) != tuple(round(scene["canvas"][k]*9525) for k in ("width","height")):
            raise SpecError("Slide size changed")
        slide_names=[n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml",n)]
        if len(slide_names)!=len(scene["slides"]): raise SpecError("Slide count changed")
        for i, slide in enumerate(scene["slides"],1):
            root=ET.fromstring(archive.read(f"ppt/slides/slide{i}.xml"))
            objects=[e for e in root.find("p:cSld/p:spTree",NS) if e.tag.split("}")[-1] in ("sp","pic","graphicFrame","grpSp")]
            if len(objects)!=len(slide["elements"]): raise SpecError(f"Slide {i}: element loss")
            for node, e in zip(objects,slide["elements"]):
                if e["type"]=="image":
                    if node.tag.split("}")[-1]!="pic": raise SpecError("Image layer order changed")
                    continue
                xfrm=node.find("p:spPr/a:xfrm",NS)
                if xfrm is None: raise SpecError("Missing native geometry")
                off, ext=xfrm.find("a:off",NS), xfrm.find("a:ext",NS)
                actual=[int(off.get("x")),int(off.get("y")),int(ext.get("cx")),int(ext.get("cy"))]
                expected=[round(e[k]*9525) for k in ("x","y","width","height")]
                if any(abs(a-b)>2 for a,b in zip(actual,expected)):
                    raise SpecError(f"Slide {i}/{e['id']}: geometry changed")
                if e["type"]=="text":
                    actual_text="".join(t.text or "" for t in node.findall(".//a:t",NS))
                    if compact(actual_text)!=compact(text_content(e)):
                        raise SpecError(f"Slide {i}/{e['id']}: editable text changed")
                if e["type"]=="path" and node.find(".//a:custGeom",NS) is None:
                    raise SpecError("Path became non-native")
    return {"status":"passed","slides":len(scene["slides"]),
            "checks":["xml","relationships","slide count","canvas","element order","geometry","editable text","native paths"],
            "visual_review":"pending"}
