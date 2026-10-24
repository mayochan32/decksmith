"""Conservative OOXML style edits. No slide reconstruction or text normalization."""
import copy
from collections import Counter
import posixpath
import re
from pathlib import Path
from urllib.parse import unquote
from xml.dom import Node, minidom
from zipfile import BadZipFile, ZipFile

from compile_spec import SpecError, keys, leaves, load_mapping, number, source_hash, text

P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
FILLS = {'noFill', 'solidFill', 'gradFill', 'blipFill', 'pattFill', 'grpFill'}
PROPERTIES = {'fill', 'line_color', 'text_color', 'font', 'font_size', 'bold', 'italic'}
METRICS = {'font', 'font_size', 'bold', 'italic'}


def children(node, ns=None, local=None):
    return [c for c in node.childNodes if c.nodeType == Node.ELEMENT_NODE
            and (ns is None or c.namespaceURI == ns) and (local is None or c.localName == local)]


def first(node, ns, local):
    return next(iter(children(node, ns, local)), None)


def descendants(node, ns, local):
    return list(node.getElementsByTagNameNS(ns, local))


def parse(raw):
    # DTD/entities are unnecessary in OOXML. Do not resolve supplied entities.
    if re.search(br'<!\s*(DOCTYPE|ENTITY)\b', raw, re.I):
        raise SpecError('DTD/entities are not supported in PPTX XML')
    try:
        return minidom.parseString(raw)
    except Exception as error:
        raise SpecError('Invalid PPTX XML: ' + str(error)) from error


def package(path):
    path = Path(path)
    if path.suffix.lower() != '.pptx':
        raise SpecError('This release supports PPTX input only; PDF/PPT input is not implemented')
    try:
        with ZipFile(path) as archive:
            if len(set(archive.namelist())) != len(archive.namelist()):
                raise SpecError('Duplicate PPTX package entries')
            if archive.testzip():
                raise SpecError('Corrupt PPTX package')
            if any(n.startswith('_xmlsignatures/') for n in archive.namelist()):
                raise SpecError('Digitally signed PPTX is unsupported; editing invalidates its signature')
            infos = archive.infolist()
            parts = {i.filename: archive.read(i.filename) for i in infos}
    except (BadZipFile, RuntimeError) as error:
        raise SpecError('Cannot read PPTX: ' + str(error)) from error
    if 'ppt/presentation.xml' not in parts or 'ppt/_rels/presentation.xml.rels' not in parts:
        raise SpecError('Missing presentation package parts')
    presentation = parse(parts['ppt/presentation.xml'])
    if presentation.documentElement.namespaceURI != P:
        raise SpecError('Unsupported PPTX namespace (Transitional OOXML required)')
    rels = parse(parts['ppt/_rels/presentation.xml.rels'])
    targets = {}
    for rel in children(rels.documentElement):
        if rel.getAttribute('TargetMode') == 'External':
            continue
        target = unquote(rel.getAttribute('Target'))
        targets[rel.getAttribute('Id')] = (target.lstrip('/') if target.startswith('/')
            else posixpath.normpath(posixpath.join('ppt', target)))
    slides = []
    for entry in descendants(presentation, P, 'sldId'):
        name = targets.get(entry.getAttributeNS(R, 'id'))
        if name not in parts:
            raise SpecError('Missing slide relationship target')
        root = parse(parts[name])
        if root.documentElement.namespaceURI != P or root.documentElement.localName != 'sld':
            raise SpecError('Invalid slide target: ' + name)
        common = first(root.documentElement, P, 'cSld')
        if common is None or first(common, P, 'spTree') is None:
            raise SpecError('Missing slide content or shape tree: ' + name)
        slides.append((name, root))
    if not slides or len({n for n, _ in slides}) != len(slides):
        raise SpecError('Presentation must contain distinct slides')
    sizes = descendants(presentation, P, 'sldSz')
    if len(sizes) != 1:
        raise SpecError('Missing slide size')
    try:
        canvas = {axis: int(sizes[0].getAttribute(attr)) / 9525
                  for axis, attr in (('width', 'cx'), ('height', 'cy'))}
        if min(canvas.values()) < 1:
            raise ValueError()
    except ValueError as error:
        raise SpecError('Invalid slide size') from error
    return infos, parts, slides, canvas


def shapes(doc):
    result = {}
    for node in descendants(doc, P, '*'):
        if node.localName in ('sp', 'pic', 'graphicFrame', 'grpSp', 'cxnSp'):
            # The first nonvisual child owns this object's ID, including groups.
            nv = next((c for c in children(node, P) if c.localName.startswith('nv')), None)
            identity = first(nv, P, 'cNvPr') if nv is not None else None
            if identity is None:
                raise SpecError('Missing shape identity')
            sid = identity.getAttribute('id')
            if not sid or sid in result:
                raise SpecError('Duplicate or missing shape ID')
            result[sid] = node
    return result


def body_text(body):
    paragraphs = []
    for paragraph in children(body, A, 'p'):
        pieces = []
        for item in children(paragraph):
            if item.namespaceURI == A and item.localName == 'br':
                pieces.append('\n')
            else:
                for t in descendants(item, A, 't'):
                    pieces.append(''.join(c.data for c in t.childNodes if c.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE)))
        paragraphs.append(''.join(pieces))
    return '\n'.join(paragraphs)


def node_text(node):
    return ''.join(c.data for c in node.childNodes if c.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE))


def editable_runs(shape):
    body = first(shape, P, 'txBody')
    if shape.localName != 'sp' or body is None:
        return []
    # Fields, bullets, paragraph structure and hyperlinks stay in the original tree.
    return [t for paragraph in children(body, A, 'p') for run in children(paragraph, A, 'r')
            for t in children(run, A, 't')]


def numeric_tokens(value):
    return Counter(re.findall(r'[+−-]?[0-9０-９]+(?:[.,．，][0-9０-９]+)*(?:[%％])?', value))


def apply_rewrites(slides, rewrites):
    for rewrite in rewrites:
        shape = shapes(slides[rewrite['slide']-1][1])[rewrite['shape_id']]
        runs = editable_runs(shape)
        for edit in rewrite['edits']:
            node = runs[edit['run']]
            if node_text(node) != edit['before']:
                raise SpecError('Rewrite before text does not match source')
            for child in list(node.childNodes):
                node.removeChild(child)
            node.appendChild(node.ownerDocument.createTextNode(edit['after']))


def validate_rewrites(plan, slides):
    rewrites = plan.get('rewrites')
    if not isinstance(rewrites, list):
        raise SpecError('Mode 2 requires a rewrites list')
    text(plan.get('protection_review'), 'protection_review')
    protections = plan.get('protected_terms')
    if not isinstance(protections, list):
        raise SpecError('Mode 2 requires protected_terms (names, units, conditions, citations)')
    ids, edited = set(), set()
    for rewrite in rewrites:
        keys(rewrite, 'id slide shape_id edits', 'rewrite')
        rid = text(rewrite.get('id'), 'rewrite.id')
        if rid in ids:
            raise SpecError('Duplicate rewrite id')
        ids.add(rid)
        index, sid = rewrite.get('slide'), rewrite.get('shape_id')
        if type(index) is not int or not 1 <= index <= len(slides) or not isinstance(sid, str):
            raise SpecError('Invalid rewrite target')
        shape = shapes(slides[index-1][1]).get(sid)
        if shape is None or not editable_runs(shape):
            raise SpecError('Rewrite target must have editable p:sp text runs; fields/tables/charts are protected')
        runs = editable_runs(shape)
        edits = rewrite.get('edits')
        if not isinstance(edits, list) or not edits:
            raise SpecError('Rewrite edits must be non-empty')
        for edit in edits:
            keys(edit, 'run before after reason', 'rewrite edit')
            run = edit.get('run')
            if type(run) is not int or not 0 <= run < len(runs) or (index, sid, run) in edited:
                raise SpecError('Invalid or overlapping rewrite run')
            edited.add((index, sid, run))
            if not isinstance(edit.get('before'), str) or node_text(runs[run]) != edit['before']:
                raise SpecError('Rewrite before text does not match source')
            after = edit.get('after')
            if not isinstance(after, str) or any(ord(c) < 32 for c in after):
                raise SpecError('Rewrite after must be text without control characters; preserve paragraph/break structure')
            if after == edit['before']:
                raise SpecError('Rewrite must change text')
            text(edit.get('reason'), 'rewrite reason')
    candidate = copy.deepcopy(slides)
    apply_rewrites(candidate, rewrites)
    targets = {(r['slide'], r['shape_id']) for r in rewrites}
    for index, sid in targets:
        old = body_text(first(shapes(slides[index-1][1])[sid], P, 'txBody'))
        new = body_text(first(shapes(candidate[index-1][1])[sid], P, 'txBody'))
        if not new.strip() or numeric_tokens(old) != numeric_tokens(new):
            raise SpecError('Mode 2 must preserve numeric values and cannot erase a text frame')
    for protection in protections:
        keys(protection, 'slide shape_id text', 'protected term')
        index, sid = protection.get('slide'), protection.get('shape_id')
        term = text(protection.get('text'), 'protected term.text')
        if type(index) is not int or not 1 <= index <= len(slides) or not isinstance(sid, str):
            raise SpecError('Invalid protected term target')
        shape = shapes(slides[index-1][1]).get(sid)
        if shape is None or first(shape, P, 'txBody') is None:
            raise SpecError('Protected term requires a text shape')
        old = body_text(first(shape, P, 'txBody'))
        new = body_text(first(shapes(candidate[index-1][1])[sid], P, 'txBody'))
        if not old.count(term) or old.count(term) != new.count(term):
            raise SpecError('Protected term missing or changed: ' + term)
    return rewrites


def part_relations(parts, name):
    relpath = posixpath.join(posixpath.dirname(name), '_rels', posixpath.basename(name) + '.rels')
    if relpath not in parts:
        return {}
    relations = {}
    for rel in children(parse(parts[relpath]).documentElement):
        if rel.getAttribute('TargetMode') == 'External':
            continue
        target = unquote(rel.getAttribute('Target'))
        resolved = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
        relations[rel.getAttribute('Type').rsplit('/', 1)[-1]] = resolved
    return relations


def image_fill_constraints(parts, slides):
    """Do not replace images used as shape fills or inherited backgrounds."""
    theme_images = any(descendants(parse(raw), A, 'blipFill') for name, raw in parts.items()
                       if name.startswith('ppt/theme/') and name.endswith('.xml'))
    inherited_images = any(descendants(parse(raw), A, 'blipFill') for name, raw in parts.items()
                          if name.startswith(('ppt/slideLayouts/', 'ppt/slideMasters/')) and name.endswith('.xml'))
    constraints = {}
    for index, (name, doc) in enumerate(slides, 1):
        owner, current, visited = name, doc, set()
        while owner not in visited:
            visited.add(owner)
            common = first(current.documentElement, P, 'cSld')
            bg = first(common, P, 'bg') if common is not None else None
            if bg is not None:
                if descendants(bg, A, 'blipFill') or (first(bg, P, 'bgRef') is not None and theme_images):
                    constraints[(index, 'background')] = 'Image background must be preserved in mode 1'
                break
            rels = part_relations(parts, owner)
            target = rels.get('slideLayout') or rels.get('slideMaster')
            if target is None:
                break
            if target not in parts:
                raise SpecError('Missing inherited layout/master: ' + target)
            owner, current = target, parse(parts[target])
        for sid, shape in shapes(doc).items():
            if shape.localName != 'sp':
                continue
            prop = first(shape, P, 'spPr')
            fills = [n for n in children(prop, A) if n.localName in FILLS] if prop is not None else []
            if any(n.localName == 'blipFill' for n in fills):
                constraints[(index, sid)] = 'Picture-filled shape must be preserved in mode 1'
            elif not fills and ((theme_images and descendants(shape, A, 'fillRef'))
                                or (inherited_images and descendants(shape, P, 'ph'))):
                constraints[(index, sid)] = 'Inherited fill may contain an image; fill replacement is unsupported'
    return constraints


def inspect_source(source):
    _, parts, slides, canvas = package(source)
    constraints = image_fill_constraints(parts, slides)
    pages = []
    for index, (name, doc) in enumerate(slides, 1):
        objects = []
        for sid, node in shapes(doc).items():
            body = first(node, P, 'txBody')
            identity = descendants(node, P, 'cNvPr')[0]
            available = PROPERTIES - ({'fill'} if (index, sid) in constraints else set())
            objects.append({'shape_id': sid, 'kind': node.localName,
                'name': identity.getAttribute('name'),
                'text': body_text(body) if body is not None else None,
                'text_runs': [{'run': i, 'text': node_text(t)} for i, t in enumerate(editable_runs(node))],
                'geometry_xml': [n.toxml() for n in descendants(node, A, 'xfrm')],
                'editable_properties': sorted(available if node.localName == 'sp' else []),
                'fill_constraint': constraints.get((index, sid)),
                'text_style_supported': body is not None and node.localName == 'sp'})
        pages.append({'slide': index, 'part': name, 'objects': objects,
                      'background_constraint': constraints.get((index, 'background'))})
    return {'schema_version': '1.0', 'mode': 'style_only', 'source_sha256': source_hash(source),
        'canvas': canvas, 'slides': pages,
        'preserved_parts': len(parts),
        'limitations': ['Only explicit slide backgrounds and p:sp formatting can be edited.',
            'Images, tables, charts, masters, layouts, notes and embedded objects are preserved unchanged.',
            'Text inside images is not editable. Font substitution, wrapping and overflow require visual review.']}


def validate_plan(plan, source, style, slides):
    mode = plan.get('mode')
    allowed = 'schema_version mode source_sha256 style_sha256 requirements operations'
    keys(plan, allowed + (' rewrites protected_terms protection_review' if mode == 'style_and_text' else ''), 'restyle plan')
    if plan.get('schema_version') != '1.0' or mode not in ('style_only', 'style_and_text'):
        raise SpecError('Only schema 1.0 / mode style_only or style_and_text is supported here')
    for label, path in (('source', source), ('style', style)):
        if plan.get(label + '_sha256') != source_hash(path):
            raise SpecError(label + ' changed; inspect and reinterpret before applying')
    operations = plan.get('operations')
    if not isinstance(operations, list) or (not operations and mode == 'style_only'):
        raise SpecError('operations must be a non-empty list in mode 1')
    if mode == 'style_and_text':
        validate_rewrites(plan, slides)
    rewrite_ids = {r['id'] for r in plan.get('rewrites', [])}
    ids, destinations = set(), set()
    constraints = image_fill_constraints(package(source)[1], slides)
    for op in operations:
        keys(op, 'id slide shape_id set', 'operation')
        oid = text(op.get('id'), 'operation.id')
        if oid in ids:
            raise SpecError('Duplicate operation id')
        ids.add(oid)
        index = op.get('slide')
        if type(index) is not int or not 1 <= index <= len(slides):
            raise SpecError('Invalid slide index')
        sid = op.get('shape_id')
        if sid != 'background' and (not isinstance(sid, str) or sid not in shapes(slides[index-1][1])):
            raise SpecError('Unknown shape_id')
        settings = op.get('set')
        keys(settings, 'fill' if sid == 'background' else ' '.join(sorted(PROPERTIES)), 'operation.set')
        if not settings:
            raise SpecError('Empty operation.set')
        if 'fill' in settings and (index, sid) in constraints:
            raise SpecError(constraints[(index, sid)])
        if sid != 'background':
            node = shapes(slides[index-1][1])[sid]
            if node.localName != 'sp':
                raise SpecError('Only p:sp formatting is supported; other objects must be preserved')
            if set(settings) - {'fill', 'line_color'} and first(node, P, 'txBody') is None:
                raise SpecError('Text styling requires a text body')
        for prop, value in settings.items():
            destination = (index, sid, prop)
            if destination in destinations:
                raise SpecError('Overlapping operations for the same property')
            destinations.add(destination)
            if prop in ('fill', 'line_color', 'text_color'):
                if not isinstance(value, str) or re.fullmatch(r'#[0-9a-fA-F]{6}', value) is None:
                    raise SpecError(prop + ' must be #RRGGBB')
            elif prop == 'font':
                text(value, 'font')
            elif prop == 'font_size':
                number(value, 'font_size', 1)
                if value > 400:
                    raise SpecError('font_size must be <= 400 pt')
            elif type(value) is not bool:
                raise SpecError(prop + ' must be boolean')
    requirements = plan.get('requirements')
    if ids & rewrite_ids:
        raise SpecError('Style operation and rewrite IDs must be distinct')
    if not isinstance(requirements, list) or not requirements:
        raise SpecError('requirements ledger is required')
    expected = set(leaves(load_mapping(style)))
    seen, covered = set(), set()
    for req in requirements:
        keys(req, 'source interpretation status operations reason', 'requirement')
        pointer = req.get('source')
        if not isinstance(pointer, str) or pointer not in expected or pointer in seen:
            raise SpecError('Style requirement coverage mismatch or duplicate')
        seen.add(pointer)
        text(req.get('interpretation'), 'requirement.interpretation')
        status = req.get('status')
        references = req.get('operations', [])
        if (not isinstance(references, list) or any(not isinstance(r, str) or r not in ids | rewrite_ids for r in references)
                or len(set(references)) != len(references)):
            raise SpecError('Requirement references unknown or duplicate operations')
        if status in ('implemented', 'partially_implemented'):
            if not references:
                raise SpecError('Implemented requirement needs operations')
            if status == 'partially_implemented':
                text(req.get('reason'), 'partially implemented requirement reason')
            covered.update(references)
        elif status in ('preservation_conflict', 'unsupported', 'not_applicable'):
            text(req.get('reason'), 'excluded requirement reason')
            if references:
                raise SpecError('Excluded requirements cannot claim operations')
        else:
            raise SpecError('Unresolved requirement; interpret every style value before applying')
    if seen != expected or not ids <= covered:
        raise SpecError('Every style value and operation must be covered by the ledger')
    return plan


def element(parent, ns, local):
    # Use in-scope prefixes, including documents that do not use p/a.
    prefix = None
    bindings = {}
    node = parent
    while node is not None:
        if node.nodeType == Node.ELEMENT_NODE:
            for i in range(node.attributes.length):
                attr = node.attributes.item(i)
                if attr.name == 'xmlns' or attr.name.startswith('xmlns:'):
                    name = attr.name.split(':', 1)[1] if ':' in attr.name else ''
                    bindings.setdefault(name, attr.value)
            prefix = next((name for name, uri in bindings.items() if uri == ns), None)
        if prefix is not None:
            break
        node = node.parentNode
    if prefix is None:
        prefix = 'a' if ns == A else 'p'
        while prefix in bindings:
            prefix += '_'
    result = parent.ownerDocument.createElementNS(ns, (prefix + ':' if prefix else '') + local)
    if node is None:
        result.setAttribute('xmlns:' + prefix, ns)
    return result


def remove(node):
    node.parentNode.removeChild(node)


def insert_before(parent, node, successors):
    reference = next((c for c in children(parent) if c.localName in successors), None)
    parent.insertBefore(node, reference)


def solid_fill(parent, value):
    for child in list(children(parent, A)):
        if child.localName in FILLS:
            remove(child)
    fill = element(parent, A, 'solidFill')
    rgb = element(fill, A, 'srgbClr')
    rgb.setAttribute('val', value[1:].upper())
    fill.appendChild(rgb)
    successors = {'ln', 'effectLst', 'effectDag', 'scene3d', 'sp3d', 'extLst',
        'prstDash', 'custDash', 'round', 'bevel', 'miter', 'headEnd', 'tailEnd', 'highlight',
        'uLnTx', 'uLn', 'uFillTx', 'uFill', 'latin', 'ea', 'cs', 'sym', 'hlinkClick', 'hlinkMouseOver', 'rtl'}
    if parent.localName in ('rPr', 'defRPr', 'endParaRPr'):
        successors.remove('ln')  # Character outline precedes character fill in OOXML.
    insert_before(parent, fill, successors)


def style_text(body, settings):
    for paragraph in children(body, A, 'p'):
        properties = []
        ppr = first(paragraph, A, 'pPr')
        if ppr is None:
            ppr = element(paragraph, A, 'pPr')
            paragraph.insertBefore(ppr, paragraph.firstChild)
        default = first(ppr, A, 'defRPr')
        if default is None:
            default = element(ppr, A, 'defRPr')
            insert_before(ppr, default, {'extLst'})
        properties.append(default)
        for run in children(paragraph, A):
            if run.localName not in ('r', 'fld', 'br'):
                continue
            rpr = first(run, A, 'rPr')
            if rpr is None:
                rpr = element(run, A, 'rPr')
                run.insertBefore(rpr, run.firstChild)
            properties.append(rpr)
        end = first(paragraph, A, 'endParaRPr')
        if end is not None:
            properties.append(end)
        for prop in properties:
            if 'text_color' in settings:
                solid_fill(prop, settings['text_color'])
            for key, attr in (('bold', 'b'), ('italic', 'i'), ('font_size', 'sz')):
                if key in settings:
                    value = str(round(settings[key] * 100)) if key == 'font_size' else str(int(settings[key]))
                    prop.setAttribute(attr, value)
            if 'font' in settings:
                for local in ('latin', 'ea', 'cs'):
                    font = first(prop, A, local)
                    if font is None:
                        font = element(prop, A, local)
                        successors = {'latin': {'ea', 'cs', 'sym'}, 'ea': {'cs', 'sym'}, 'cs': {'sym'}}[local]
                        insert_before(prop, font, successors | {'hlinkClick', 'hlinkMouseOver', 'rtl', 'extLst'})
                    font.setAttribute('typeface', settings['font'])


def apply_operations(slides, operations):
    for op in operations:
        doc = slides[op['slide']-1][1]
        settings = op['set']
        if op['shape_id'] == 'background':
            common = first(doc.documentElement, P, 'cSld')
            bg = first(common, P, 'bg')
            if bg is None:
                bg = element(common, P, 'bg')
                common.insertBefore(bg, common.firstChild)
            for ref in children(bg, P, 'bgRef'):
                remove(ref)
            prop = first(bg, P, 'bgPr')
            if prop is None:
                prop = element(bg, P, 'bgPr')
                bg.insertBefore(prop, bg.firstChild)
            solid_fill(prop, settings['fill'])
        else:
            shape = shapes(doc)[op['shape_id']]
            prop = first(shape, P, 'spPr')
            if prop is None:
                raise SpecError('Missing shape properties')
            if 'fill' in settings:
                solid_fill(prop, settings['fill'])
            if 'line_color' in settings:
                line = first(prop, A, 'ln')
                if line is None:
                    line = element(prop, A, 'ln')
                    insert_before(prop, line, {'effectLst', 'effectDag', 'scene3d', 'sp3d', 'extLst'})
                solid_fill(line, settings['line_color'])
            if set(settings) - {'fill', 'line_color'}:
                style_text(first(shape, P, 'txBody'), settings)


def canonical(node):
    if node.nodeType == Node.ELEMENT_NODE:
        attrs = tuple(sorted((node.attributes.item(i).name, node.attributes.item(i).value)
                             for i in range(node.attributes.length)))
        # Formatting indentation outside text values is insignificant XML whitespace.
        content = [c for c in node.childNodes if not (c.nodeType == Node.TEXT_NODE
            and not c.data.strip() and not (node.namespaceURI == A and node.localName == 't'))]
        return (node.tagName, attrs, tuple(canonical(c) for c in content))
    return (node.nodeType, getattr(node, 'data', ''), tuple(canonical(c) for c in node.childNodes))


def protected_projection(doc, operations, rewrites=()):
    """Remove only explicitly permitted properties; retain all content and geometry."""
    doc = copy.deepcopy(doc)
    for rewrite in rewrites:
        runs = editable_runs(shapes(doc)[rewrite['shape_id']])
        for edit in rewrite['edits']:
            node = runs[edit['run']]
            for child in list(node.childNodes):
                node.removeChild(child)
    def strip_fills(parent):
        for node in list(children(parent, A)):
            if node.localName in FILLS:
                remove(node)
    for op in operations:
        settings = op['set']
        if op['shape_id'] == 'background':
            common = first(doc.documentElement, P, 'cSld')
            for bg in children(common, P, 'bg'):
                remove(bg)
            continue
        shape = shapes(doc)[op['shape_id']]
        prop = first(shape, P, 'spPr')
        if 'fill' in settings:
            strip_fills(prop)
        if 'line_color' in settings:
            line = first(prop, A, 'ln')
            if line is not None:
                strip_fills(line)
                if not line.attributes.length and not line.childNodes:
                    remove(line)
        if set(settings) - {'fill', 'line_color'}:
            body = first(shape, P, 'txBody')
            for local in ('rPr', 'defRPr', 'endParaRPr'):
                for rpr in descendants(body, A, local):
                    if 'text_color' in settings:
                        strip_fills(rpr)
                    for key, attr in (('font_size', 'sz'), ('bold', 'b'), ('italic', 'i')):
                        if key in settings and rpr.hasAttribute(attr):
                            rpr.removeAttribute(attr)
                    if 'font' in settings:
                        for child in list(children(rpr, A)):
                            if child.localName in ('latin', 'ea', 'cs'):
                                # Only typeface is editable, preserve charset/panose etc.
                                if child.hasAttribute('typeface'):
                                    child.removeAttribute('typeface')
                                if not child.attributes.length and not child.childNodes:
                                    remove(child)
                    if not rpr.attributes.length and not rpr.childNodes:
                        remove(rpr)
            for ppr in descendants(body, A, 'pPr'):
                if not ppr.attributes.length and not ppr.childNodes:
                    remove(ppr)
    return canonical(doc)


def validate_preservation(source, output, operations, rewrites=()):
    _, before, slides_before, canvas = package(source)
    _, after, slides_after, _ = package(output)
    constraints = image_fill_constraints(before, slides_before)
    for op in operations:
        if 'fill' in op['set'] and (op['slide'], op['shape_id']) in constraints:
            raise SpecError(constraints[(op['slide'], op['shape_id'])])
    if set(before) != set(after) or [n for n, _ in slides_before] != [n for n, _ in slides_after]:
        raise SpecError('Package membership or slide order changed')
    changed = {slides_before[op['slide']-1][0] for op in list(operations) + list(rewrites)}
    for name in before:
        if name not in changed and before[name] != after[name]:
            raise SpecError('Protected package part changed: ' + name)
    for index, ((name, original), (_, candidate)) in enumerate(zip(slides_before, slides_after), 1):
        allowed = [op for op in operations if op['slide'] == index]
        edits = [r for r in rewrites if r['slide'] == index]
        for rewrite in edits:
            old_runs = editable_runs(shapes(original)[rewrite['shape_id']])
            new_runs = editable_runs(shapes(candidate)[rewrite['shape_id']])
            if len(old_runs) != len(new_runs):
                raise SpecError('Text run structure changed')
            for edit in rewrite['edits']:
                if node_text(old_runs[edit['run']]) != edit['before'] or node_text(new_runs[edit['run']]) != edit['after']:
                    raise SpecError('Output rewrite differs from approved plan')
            old_text = body_text(first(shapes(original)[rewrite['shape_id']], P, 'txBody'))
            new_text = body_text(first(shapes(candidate)[rewrite['shape_id']], P, 'txBody'))
            if numeric_tokens(old_text) != numeric_tokens(new_text):
                raise SpecError('Numeric values changed in rewritten frame')
        if protected_projection(original, allowed, edits) != protected_projection(candidate, allowed, edits):
            raise SpecError('Protected content, geometry or object structure changed: ' + name)
    return {'status': 'passed', 'slides': len(slides_before), 'canvas': canvas,
        'unchanged_parts': len(before) - len(changed),
        'checks': ['exact text including whitespace and explicit breaks', 'geometry and text frames',
            'object order, grouping, cropping and relationships', 'slide order and size',
            'untargeted properties', 'unchanged non-slide parts including images, charts and notes'],
        'mode': 'style_and_text' if rewrites else 'style_only',
        'scope': 'OOXML preservation except declared text edits; meaning, overflow and font substitution require review'}


def write_candidate(source, destination, plan):
    infos, parts, slides, _ = package(source)
    apply_operations(slides, plan['operations'])
    rewrites = plan.get('rewrites', [])
    if plan.get('mode') == 'style_only' and rewrites:
        raise SpecError('Mode 1 forbids text rewrites')
    if plan.get('mode') == 'style_and_text':
        validate_rewrites(plan, slides)
        apply_rewrites(slides, rewrites)
    changed = {slides[op['slide']-1][0] for op in plan['operations'] + rewrites}
    edited = {name: doc.toxml(encoding='utf-8') for name, doc in slides if name in changed}
    with Path(destination).open('xb') as stream, ZipFile(stream, 'w') as archive:
        for info in infos:
            archive.writestr(info, edited.get(info.filename, parts[info.filename]))
    result = validate_preservation(source, destination, plan['operations'], rewrites)
    result['mode'] = plan.get('mode', 'style_only')
    if result['mode'] == 'style_and_text':
        result['checks'][0] = 'only declared text edits; numeric values and protected terms retained'
    return result
