"""Provider-independent OOXML checks; visual review remains separate."""
import posixpath
import re
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from compile_spec import SpecError, compact, text_content
import evidence_validation

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
                xfrm=node.find("p:xfrm",NS) if e['type'] in ('table','chart') else node.find("p:spPr/a:xfrm",NS)
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
                    if 'align' in e:
                        expected_align = {'left': 'l', 'center': 'ctr', 'right': 'r', 'justify': 'just'}[e['align']]
                        for paragraph in node.findall('p:txBody/a:p', NS):
                            properties = paragraph.find('a:pPr', NS)
                            if (properties.get('algn', 'l') if properties is not None else 'l') != expected_align:
                                raise SpecError(f"Slide {i}/{e['id']}: text alignment changed")
                    if 'vertical' in e:
                        body = node.find('p:txBody/a:bodyPr', NS)
                        expected_anchor = {'top': 't', 'middle': 'ctr', 'bottom': 'b'}[e['vertical']]
                        if body is None or body.get('anchor', 't') != expected_anchor:
                            raise SpecError(f"Slide {i}/{e['id']}: text vertical alignment changed")
                if e["type"]=="path" and node.find(".//a:custGeom",NS) is None:
                    raise SpecError("Path became non-native")
                if e['type'] == 'path':
                    path_node = node.find('.//a:custGeom/a:pathLst/a:path', NS)
                    points = path_node.findall('a:moveTo/a:pt', NS) + path_node.findall('a:lnTo/a:pt', NS)
                    actual_points = [(int(p.get('x')), int(p.get('y'))) for p in points]
                    expected_points = [tuple(round(v * 9525) for v in point) for point in e['points']]
                    if len(actual_points) != len(expected_points) or any(
                            abs(a - b) > 2 for pair, expected_pair in zip(actual_points, expected_points)
                            for a, b in zip(pair, expected_pair)):
                        raise SpecError(f"Slide {i}/{e['id']}: native path points changed")
                    if len(path_node.findall('a:close', NS)) != int(bool(e.get('closed'))):
                        raise SpecError(f"Slide {i}/{e['id']}: native path closure changed")
                    for field, tag in (('start_arrow', 'headEnd'), ('end_arrow', 'tailEnd')):
                        if field in e:
                            arrow = node.find('p:spPr/a:ln/a:' + tag, NS)
                            if arrow is None or arrow.get('type') != e[field]:
                                raise SpecError(f"Slide {i}/{e['id']}: native arrow changed")
                if e['type']=='table': evidence_validation.table(node,e)
                if e['type']=='chart': evidence_validation.chart(archive,f'ppt/slides/slide{i}.xml',node,e)
    return {"status":"passed","slides":len(scene["slides"]),
            "checks":["xml","relationships","slide count","canvas","element order","geometry","editable text","native paths and arrows",
                      "native table cells","chart data and embedded workbook"],
            "visual_review":"pending"}
