"""Transplant editable source objects and their actual dependencies into a new PPTX."""
import hashlib
import posixpath
from pathlib import Path
from urllib.parse import quote, unquote
from zipfile import ZipFile, ZIP_DEFLATED

from compile_spec import SpecError
from pptx_restyle import A, P, R, canonical, children, descendants, element, first, package, parse, shapes

REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'


def relpath(name):
    return posixpath.join(posixpath.dirname(name), '_rels', posixpath.basename(name) + '.rels')


def target_part(owner, target):
    target = unquote(target)
    return target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(posixpath.dirname(owner), target))


def relationships(parts, owner):
    name = relpath(owner)
    return {r.getAttribute('Id'): r for r in children(parse(parts[name]).documentElement)} if name in parts else {}


def digest(node):
    return hashlib.sha256(repr(canonical(node)).encode('utf-8')).hexdigest()


def transplant(source, generated, destination, scene, slots):
    """Slots use existing scene shape IDs; final objects stay native, never screenshots."""
    _, original, source_slides, _ = package(source)
    _, parts, output_slides, _ = package(generated)
    types = parse(parts['[Content_Types].xml'])
    source_types = parse(original['[Content_Types].xml'])
    overrides = {unquote(c.getAttribute('PartName')).lstrip('/'): c.getAttribute('ContentType')
                 for c in children(source_types.documentElement) if c.localName == 'Override'}
    defaults = {c.getAttribute('Extension'): c.getAttribute('ContentType')
                for c in children(source_types.documentElement) if c.localName == 'Default'}
    prefix = 'ppt/decksmith-import/' + hashlib.sha256(Path(source).read_bytes()).hexdigest()[:12] + '/'
    copied, expected, imported = {}, [], {}

    def import_part(name):
        if name in copied:
            return copied[name]
        if name not in original:
            raise SpecError('Missing native-object dependency: ' + name)
        new_name = prefix + name
        if new_name in parts:
            raise SpecError('Native import path collision')
        copied[name] = new_name
        imported[new_name] = original[name]
        kind = overrides.get(name) or defaults.get(name.rsplit('.', 1)[-1])
        if not kind:
            raise SpecError('Missing native content type: ' + name)
        entry = types.createElementNS(CT, 'Override')
        entry.setAttribute('PartName', '/' + quote(new_name, safe='/'))
        entry.setAttribute('ContentType', kind)
        types.documentElement.appendChild(entry)
        if relpath(name) in original:
            rels = parse(original[relpath(name)])
            for rel in children(rels.documentElement):
                if rel.getAttribute('TargetMode') != 'External':
                    dependency = import_part(target_part(name, rel.getAttribute('Target')))
                    rel.setAttribute('Target', '/' + quote(dependency, safe='/'))
            imported[relpath(new_name)] = rels.toxml(encoding='utf-8')
        return new_name

    slide_ids = {s['id']: i for i, s in enumerate(scene['slides'])}
    pending, remaps = [], {}
    for slot in slots:
        sid, eid = slot['target'].split('/', 1)
        oi = slide_ids[sid]
        out_name, out_doc = output_slides[oi]
        original_slide = source_slides[slot['slide']-1]
        src = shapes(original_slide[1])[slot['shape_id']]
        dst_element = scene['slides'][oi]['elements']
        eindex = next(i for i, e in enumerate(dst_element) if e['id'] == eid)
        tree = first(first(out_doc.documentElement, P, 'cSld'), P, 'spTree')
        objects = [n for n in children(tree, P) if n.localName in ('sp', 'pic', 'graphicFrame', 'grpSp', 'cxnSp')]
        placeholder = objects[eindex]
        clone = out_doc.importNode(src, deep=True)
        # Preserve inherited namespace bindings, including extension namespaces.
        node, bindings = src, {}
        while node is not None:
            if node.nodeType == node.ELEMENT_NODE:
                for i in range(node.attributes.length):
                    attr = node.attributes.item(i)
                    if attr.name == 'xmlns' or attr.name.startswith('xmlns:'):
                        bindings.setdefault(attr.name, attr.value)
            node = node.parentNode
        for name, value in bindings.items():
            clone.setAttribute(name, value)
        ids = remaps.setdefault((oi, slot['slide']), {})
        next_id = max(int(n.getAttribute('id')) for n in descendants(out_doc, P, 'cNvPr')) + 1
        for identity in descendants(clone, P, 'cNvPr'):
            old = identity.getAttribute('id')
            if old in ids:
                raise SpecError('A source object cannot be imported twice onto the same output slide')
            ids[old] = str(next_id)
            identity.setAttribute('id', str(next_id)); next_id += 1
        if clone.localName == 'graphicFrame':
            xfrm = first(clone, P, 'xfrm')
        else:
            prop = first(clone, P, 'grpSpPr' if clone.localName == 'grpSp' else 'spPr')
            if prop is None:
                raise SpecError('Native object has no transform properties')
            xfrm = first(prop, A, 'xfrm')
            if xfrm is None:
                xfrm = element(prop, A, 'xfrm'); prop.insertBefore(xfrm, prop.firstChild)
        if xfrm is None:
            raise SpecError('Native object has no transform')
        element_spec = dst_element[eindex]
        for local, attributes in (('off', ('x', 'y')), ('ext', ('cx', 'cy'))):
            item = first(xfrm, A, local)
            if item is None:
                item = element(xfrm, A, local); xfrm.appendChild(item)
            values = (element_spec['x'], element_spec['y']) if local == 'off' else (element_spec['width'], element_spec['height'])
            for attr, value in zip(attributes, values):
                item.setAttribute(attr, str(round(value * 9525)))
        xfrm.setAttribute('rot', str(round(element_spec.get('rotation', 0) * 60000)))
        if clone.localName == 'graphicFrame':
            # Native table layout uses its own grid/row dimensions as well as xfrm.
            for table in descendants(clone, A, 'tbl'):
                grid = first(table, A, 'tblGrid')
                for nodes, attr, length in ((children(grid, A, 'gridCol') if grid is not None else [], 'w', element_spec['width']),
                                            (children(table, A, 'tr'), 'h', element_spec['height'])):
                    sizes = [int(n.getAttribute(attr)) for n in nodes]
                    total, target = sum(sizes), round(length * 9525)
                    if total > 0:
                        assigned_size = 0
                        for i, (node, old) in enumerate(zip(nodes, sizes)):
                            new = target - assigned_size if i == len(nodes)-1 else round(old / total * target)
                            node.setAttribute(attr, str(new)); assigned_size += new
        rel_name = relpath(out_name)
        rel_doc = parse(parts[rel_name]) if rel_name in parts else parse(f'<Relationships xmlns="{REL}"/>'.encode())
        source_rels = relationships(original, original_slide[0])
        assigned = {}
        for node in [clone] + descendants(clone, '*', '*'):
            for i in range(node.attributes.length):
                attr = node.attributes.item(i)
                if attr.namespaceURI != R:
                    continue
                old_id = attr.value
                if old_id not in assigned:
                    if old_id not in source_rels:
                        raise SpecError('Missing native-object relationship: ' + old_id)
                    src_rel = source_rels[old_id]
                    if src_rel.getAttribute('Type').endswith('/slide'):
                        raise SpecError('Native internal slide hyperlinks need explicit redesign; cannot copy stale page links')
                    new_id = 'rIdDS' + str(len(children(rel_doc.documentElement)) + 1)
                    while any(r.getAttribute('Id') == new_id for r in children(rel_doc.documentElement)):
                        new_id += '_'
                    assigned[old_id] = new_id
                    rel = rel_doc.importNode(src_rel, True)
                    parent, rel_bindings = src_rel, {}
                    while parent is not None:
                        if parent.nodeType == parent.ELEMENT_NODE:
                            for i in range(parent.attributes.length):
                                binding = parent.attributes.item(i)
                                if binding.name == 'xmlns' or binding.name.startswith('xmlns:'):
                                    rel_bindings.setdefault(binding.name, binding.value)
                        parent = parent.parentNode
                    for key, value in rel_bindings.items():
                        rel.setAttribute(key, value)
                    rel.setAttribute('Id', new_id)
                    if rel.getAttribute('TargetMode') != 'External':
                        imported_part = import_part(target_part(original_slide[0], rel.getAttribute('Target')))
                        rel.setAttribute('Target', '/' + quote(imported_part, safe='/'))
                    rel_doc.documentElement.appendChild(rel)
                node.setAttributeNS(R, attr.name, assigned[old_id])
        parts[rel_name] = rel_doc.toxml(encoding='utf-8')
        tree.replaceChild(clone, placeholder)
        pending.append((clone, oi, slot['slide'], slot['target'], out_name))
    for clone, oi, source_index, target, out_name in pending:
        for local in ('stCxn', 'endCxn'):
            for connection in descendants(clone, A, local):
                old = connection.getAttribute('id')
                new = remaps[(oi, source_index)].get(old)
                if new is None:
                    raise SpecError('Native connector requires its connected objects on the same output page')
                connection.setAttribute('id', new)
        identity = descendants(clone, P, 'cNvPr')[0].getAttribute('id')
        expected.append({'target': target, 'part': out_name, 'shape_id': identity, 'sha256': digest(clone)})
    for name, doc in output_slides:
        parts[name] = doc.toxml(encoding='utf-8')
    parts['[Content_Types].xml'] = types.toxml(encoding='utf-8')
    parts.update(imported)
    with Path(destination).open('xb') as stream, ZipFile(stream, 'w', ZIP_DEFLATED) as archive:
        for name, raw in parts.items():
            archive.writestr(name, raw)
    # Verify serialized objects and copied dependency data, independently of rendering.
    _, final, final_slides, _ = package(destination)
    final_docs = dict(final_slides)
    for item in expected:
        if digest(shapes(final_docs[item['part']])[item['shape_id']]) != item['sha256']:
            raise SpecError('Native object changed during serialization')
    for old, new in copied.items():
        if final[new] != original[old]:
            raise SpecError('Native data changed: ' + old)
    return {'objects': expected, 'dependencies': {new: hashlib.sha256(final[new]).hexdigest() for new in imported},
            'assurance': 'native objects and original dependency bytes; placement intentionally redesigned'}
