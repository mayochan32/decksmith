"""Validate AI-authored scenes without selecting visual layouts."""
import copy
import hashlib
import math
import re
import json
import importlib.util
import sys
from decimal import Decimal, ROUND_HALF_UP, localcontext
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
    if e.get('type') == 'table':
        return '\n'.join('\t'.join(row) for row in [e['headers'], *e['rows']])
    if e.get('type') == 'chart':
        # Required visible text is distinct from data kept only in the workbook.
        labels = [*e['categories'], e['unit']]
        if e.get('show_legend', len(e['series']) > 1):
            labels.extend(s['name'] for s in e['series'])
        if e.get('show_values', True):
            labels.extend(chart_value(v, e.get('number_format', 'General'))
                          for s in e['series'] for v in s['values'])
        return '\n'.join(labels)
    return e["text"] if "text" in e else "".join(r["text"] for r in e.get("runs",[]))


CHART_FORMATS = ('General', '0', '0.0', '0.00', '#,##0', '#,##0.0', '#,##0.00',
                 '0%', '0.0%', '0.00%')


def chart_value(value, number_format):
    if number_format == 'General':
        return format(value, '.15g')
    percent = number_format.endswith('%')
    pattern = number_format.rstrip('%')
    places = len(pattern.split('.')[1]) if '.' in pattern else 0
    number = Decimal(str(value)) * (100 if percent else 1)
    with localcontext() as context:
        context.prec = max(28, len(number.as_tuple().digits)+abs(number.as_tuple().exponent)+places+4)
        number = number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    formatted = format(number, (',' if ',' in pattern else '') + '.' + str(places) + 'f')
    return formatted + ('%' if percent else '')


def opaque(value, where):
    color(value, where)
    if not isinstance(value, str) or len(value) != 7:
        raise SpecError(where + ': native evidence color must be #RRGGBB')


def table_data(e):
    eid = e['id']; headers, rows = e.get('headers'), e.get('rows')
    if not isinstance(headers, list) or not headers:
        raise SpecError(eid + ': table needs headers')
    for value in headers: text(value, eid + '.header')
    if not isinstance(rows, list) or not rows:
        raise SpecError(eid + ': table needs data rows')
    if any(not isinstance(row, list) or len(row) != len(headers)
           or any(not isinstance(cell, str) for cell in row) for row in rows):
        raise SpecError(eid + ': table rows must contain one string per header; no truncation')
    return headers, rows


def chart_data(e):
    eid = e['id']; categories, series = e.get('categories'), e.get('series')
    if not isinstance(categories, list) or not categories:
        raise SpecError(eid + ': chart needs categories')
    for value in categories: text(value, eid + '.category')
    if not isinstance(series, list) or not series:
        raise SpecError(eid + ': chart needs series')
    values = []
    for item in series:
        keys(item, 'name values', eid + '.series')
        text(item.get('name'), eid + '.series.name')
        if not isinstance(item.get('values'), list) or len(item['values']) != len(categories):
            raise SpecError(eid + ': series values must match all categories')
        for value in item['values']: number(value, eid + '.value')
        if any(type(value) is int and abs(value) > 9007199254740991 for value in item['values']):
            raise SpecError(eid + ': chart integer exceeds the exact JavaScript range; use appropriate source units')
        values.extend(item['values'])
    text(e.get('unit'), eid + '.unit')
    return categories, series, values


def evidence_data(e):
    fields = ('type','headers','rows') if e['type']=='table' else ('type','categories','series','unit')
    return {key:e[key] for key in fields}


def source_evidence(items):
    if not isinstance(items, list): raise SpecError('Source evidence must be a list')
    result = {}
    for item in items:
        if not isinstance(item, dict) or item.get('type') not in ('table','chart'):
            raise SpecError('Source evidence must be a table or chart data record')
        fields = 'headers rows' if item['type']=='table' else 'categories series unit'
        keys(item, 'id type '+fields, 'source evidence')
        eid = text(item.get('id'), 'source evidence.id')
        if eid in result: raise SpecError('Duplicate source evidence ID')
        table_data(item) if item['type']=='table' else chart_data(item)
        result[eid] = evidence_data(item)
    return result


def check_evidence(slide, items):
    sources = source_evidence(items); seen = set()
    for element in slide['elements']:
        if element['type'] not in ('table','chart'): continue
        eid = element.get('evidence_id', element['id'])
        if eid not in sources: raise SpecError('Native evidence needs independent source data: '+str(eid))
        if evidence_data(element) != sources[eid]:
            raise SpecError('Native evidence differs from independent source data: '+eid)
        seen.add(eid)
    if seen != set(sources): raise SpecError('Source evidence was not retained as native objects')


def native_evidence(e):
    eid = e['id']
    text(e.get('font'), eid + '.font')
    number(e.get('size'), eid + '.size', 1)
    opaque(e.get('color'), eid + '.color')
    if 'evidence_id' in e: text(e['evidence_id'], eid + '.evidence_id')
    if e.get('rotation', 0) != 0:
        raise SpecError(eid + ': native tables/charts do not support rotation')
    if 'role' in e and e['role'] not in ('display','heading','body','caption','label'):
        raise SpecError(eid + ': invalid text role')
    if e['type'] == 'table':
        headers, rows = table_data(e)
        for name, count, extent in (('column_widths', len(headers), 'width'),
                                     ('row_heights', len(rows)+1, 'height')):
            if name in e:
                values = e[name]
                if not isinstance(values, list) or len(values) != count:
                    raise SpecError(eid + ': invalid ' + name)
                for value in values: number(value, eid + '.' + name, 0.01)
                if abs(sum(values) - e[extent]) > 0.01:
                    raise SpecError(eid + ': ' + name + ' must sum to ' + extent)
        for name in ('fill','header_fill','header_color','border_color'):
            if name in e: opaque(e[name], eid + '.' + name)
        for name in ('padding','border_width'):
            if name in e: number(e[name], eid + '.' + name, 0)
        if e.get('border_mode', 'all') not in ('all', 'horizontal', 'none'):
            raise SpecError(eid + ': border_mode must be all, horizontal or none')
        if 'column_alignments' in e and (not isinstance(e['column_alignments'], list)
                or len(e['column_alignments']) != len(headers)
                or any(v not in ('left','center','right') for v in e['column_alignments'])):
            raise SpecError(eid + ': invalid column_alignments')
        highlights = e.get('highlights', [])
        if not isinstance(highlights, list): raise SpecError(eid + ': highlights must be a list')
        seen = set()
        for cell in highlights:
            keys(cell, 'row column fill color bold', eid + '.highlight')
            for name, count in (('row',len(rows)+1), ('column',len(headers))):
                if type(cell.get(name)) is not int or not 0 <= cell[name] < count:
                    raise SpecError(eid + ': invalid highlight ' + name)
            target = (cell['row'], cell['column'])
            if target in seen: raise SpecError(eid + ': duplicate cell highlight')
            seen.add(target)
            for name in ('fill','color'):
                if name in cell: opaque(cell[name], eid + '.highlight.' + name)
            if 'bold' in cell and type(cell['bold']) is not bool:
                raise SpecError(eid + ': highlight bold must be boolean')
    else:
        if e.get('chart_type') not in ('bar','column','line'):
            raise SpecError(eid + ': supported chart types are bar, column, line')
        categories, series, values = chart_data(e)
        if e.get('number_format', 'General') not in CHART_FORMATS:
            raise SpecError(eid + ': unsupported number_format')
        colors = e.get('colors')
        if not isinstance(colors, list) or len(colors) != len(series):
            raise SpecError(eid + ': colors must cover all series')
        for value in colors: opaque(value, eid + '.series color')
        highlights = e.get('highlights', [])
        if not isinstance(highlights, list): raise SpecError(eid + ': chart highlights must be a list')
        if highlights and e['chart_type'] not in ('bar', 'column'):
            raise SpecError(eid + ': point highlights require bar or column')
        seen = set()
        for point in highlights:
            keys(point, 'series category color', eid + '.chart highlight')
            for name, count in (('series', len(series)), ('category', len(categories))):
                if type(point.get(name)) is not int or not 0 <= point[name] < count:
                    raise SpecError(eid + ': invalid chart highlight ' + name)
            target = (point['series'], point['category'])
            if target in seen: raise SpecError(eid + ': duplicate chart point highlight')
            seen.add(target)
            opaque(point.get('color'), eid + '.chart highlight.color')
        for name in ('fill','grid_color'):
            if name in e: opaque(e[name], eid + '.' + name)
        for name in ('show_values','show_legend'):
            if name in e and type(e[name]) is not bool:
                raise SpecError(eid + ': ' + name + ' must be boolean')
        for name in ('axis_min','axis_max','axis_step'):
            if name in e: number(e[name], eid + '.' + name)
        if e.get('axis_step', 1) <= 0: raise SpecError(eid + ': axis_step must be positive')
        if e.get('axis_min', min(values)) > min(values) or e.get('axis_max', max(values)) < max(values):
            raise SpecError(eid + ': axis must include all data values')
        if 'axis_min' in e and 'axis_max' in e and e['axis_min'] >= e['axis_max']:
            raise SpecError(eid + ': axis_min must be below axis_max')
        if e['chart_type'] in ('bar','column') and (e.get('axis_min', 0) > 0 or e.get('axis_max', 0) < 0):
            raise SpecError(eid + ': bar/column axis must include zero')

def compact(value):
    return re.sub(r"\s+","",value)

TYPES = {
    "text":"text runs font size color bold italic align vertical line_spacing tracking role",
    "shape":"geometry fill stroke stroke_width radius",
    "path":"points closed fill stroke stroke_width start_arrow end_arrow",
    "connector":"from to stroke stroke_width clearance avoid via start_arrow end_arrow label",
    "image":"path alt fit prompt",
    "table":"evidence_id headers rows column_widths row_heights font size color role fill header_fill header_color border_color border_width border_mode padding column_alignments highlights",
    "chart":"evidence_id chart_type categories series unit font size color role colors fill grid_color number_format show_values show_legend axis_min axis_max axis_step highlights",
}

def compile_scene(scene_path, style_path, structure_path, allow_draft=False, native_content=None):
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
        keys(item,"id purpose required_text notes citations evidence","content slide")
        content_ids.append(text(item.get("id"),"content id"))
        if not isinstance(item.get("required_text"),list) or not item["required_text"]:
            raise SpecError("Each content slide needs required_text")
        for value in item["required_text"]:
            text(value,"required_text")
        source_evidence(item.get('evidence', []))
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
        if any(isinstance(e, dict) and e.get('type') == 'connector' for e in elements):
            from connector_routing import lower_connectors
            elements, routes = lower_connectors(elements, canvas)
            slide['elements'] = elements
            scene.setdefault('connector_routes', {})[sid] = routes
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
                if "tracking" in e: number(e["tracking"],eid+".tracking")
                if "role" in e and e["role"] not in ("display","heading","body","caption","label"):
                    raise SpecError(f"{eid}: invalid text role")
                if "runs" in e:
                    if not isinstance(e["runs"],list) or not e["runs"]:
                        raise SpecError(f"{eid}: empty runs")
                    for run in e["runs"]:
                        keys(run,"text font size color bold italic tracking",eid+".run")
                        text(run.get("text"),eid+".run.text")
                        if "size" in run: number(run["size"],eid+".run.size",1)
                        if "color" in run: color(run["color"],eid+".run.color")
                        if "tracking" in run: number(run["tracking"],eid+".run.tracking")
                text(text_content(e),eid+".text")
            elif kind in ('table','chart'):
                native_evidence(e)
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
                    if 'start_arrow' in e or 'end_arrow' in e:
                        from connector_routing import ARROWS
                        if any(e.get(field, 'none') not in ARROWS for field in ('start_arrow', 'end_arrow')):
                            raise SpecError(eid + ': invalid arrow type')
                        if e.get('closed') or e.get('stroke', 'none') == 'none' or not e.get('stroke_width', 0):
                            raise SpecError(eid + ': native arrows need an open stroked path')
        native=compact("".join(text_content(e) for e in elements if e["type"] in ('text','table','chart'))
                       + (native_content or {}).get(sid, ''))
        for required in content["required_text"]:
            if compact(required) not in native:
                raise SpecError(f"{sid}: missing editable content {required!r}")
        check_evidence(slide, content.get('evidence', []))
        slide["notes"]="\n".join(filter(None,[content.get("notes",""),slide.get("notes",""),
            *("Source: "+str(c) for c in content.get("citations",[]))]))
    requirements=scene.get("requirements")
    if not isinstance(requirements,list) or not requirements:
        raise SpecError("requirements ledger is required")
    pointers=set(leaves(load_mapping(style_path)))
    covered=set()
    for req in requirements:
        keys(req,"source interpretation status targets reason reason_kind approval","requirement")
        pointer=req.get("source")
        if pointer not in pointers or pointer in covered:
            raise SpecError(f"Invalid/duplicate style pointer: {pointer}")
        covered.add(pointer)
        text(req.get("interpretation"),"requirement interpretation")
        if req.get("status") in ("implemented", "approved_alternative"):
            targets=req.get("targets")
            if not isinstance(targets,list) or not targets or not set(targets)<=target_ids:
                raise SpecError(f"{pointer}: implemented requirement needs valid targets")
            if req["status"] == "approved_alternative":
                text(req.get("reason"), "alternative reason")
                text(req.get("approval"), "user approval evidence")
        elif req.get("status")=="not_applicable":
            text(req.get("reason"),"not_applicable reason")
            if req.get("reason_kind") not in ("metadata", "content_absent", "catalog_not_selected", "user_excluded"):
                raise SpecError(f"{pointer}: not_applicable needs reason_kind; unavailable assets are asset_pending")
            if req["reason_kind"] == "user_excluded":
                text(req.get("approval"), "user exclusion evidence")
        elif req.get("status") in ("blocked", "asset_pending") and allow_draft:
            text(req.get("reason"), "unresolved reason")
        else:
            raise SpecError(f"{pointer}: unresolved requirement; no silent substitution")
    if pointers-covered:
        raise SpecError(f"Uninterpreted style fields: {sorted(pointers-covered)}")
    return scene
