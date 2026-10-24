"""Source-grounded full redesign using DeckSmith's scene renderer and native imports."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from compile_spec import SpecError, compile_scene, keys, load_mapping, source_hash, text, text_content
from create_deck import executable, next_output_path, renderer_runtime, run
from design_quality import check_plan, inspect_design
from native_import import relationships, target_part, transplant
from pptx_restyle import A, P, R, body_text, children, descendants, first, inspect_source, numeric_tokens, package, parse, shapes
from project_config import resolve_config
from validate_pptx import validate_pptx
from version import read_version
from workflow import announce, policy_record, save_new


def source_content(source, assets=None):
    _, parts, slides, canvas = package(source)
    items = []
    for index, (name, doc) in enumerate(slides, 1):
        rels = relationships(parts, name)
        tree = first(first(doc.documentElement, P, 'cSld'), P, 'spTree')
        objects = shapes(doc)
        for sid, node in objects.items():
            if node.parentNode is not tree:
                parent = node.parentNode
                while parent is not None and parent is not tree and not (parent.namespaceURI == P and parent.localName == 'grpSp'):
                    parent = parent.parentNode
                if parent is not None and parent is not tree:
                    continue  # A group is mapped as one editable native object.
                raise SpecError('Alternate-content source objects require explicit supported import')
            body = first(node, P, 'txBody')
            value = body_text(body) if body is not None else '\n'.join(
                ''.join(c.data for c in t.childNodes if c.nodeType == c.TEXT_NODE) for t in descendants(node, A, 't'))
            for chart in descendants(node, 'http://schemas.openxmlformats.org/drawingml/2006/chart', 'chart'):
                rid = chart.getAttributeNS(R, 'id')
                if rid not in rels:
                    raise SpecError('Missing source chart relationship')
                part = target_part(name, rels[rid].getAttribute('Target'))
                if part not in parts:
                    raise SpecError('Missing source chart data')
                values = descendants(parse(parts[part]), 'http://schemas.openxmlformats.org/drawingml/2006/chart', 'v')
                value += '\n' + '\n'.join(''.join(c.data for c in v.childNodes if c.nodeType == c.TEXT_NODE) for v in values)
            item = {'id': f's{index}/o{sid}', 'slide': index, 'shape_id': sid,
                    'kind': node.localName, 'text': value,
                    'native_required': node.localName in ('graphicFrame', 'grpSp') or bool(descendants(node, A, 'blipFill')),
                    'assets': []}
            for blip in descendants(node, A, 'blip'):
                rid = blip.getAttributeNS(R, 'embed')
                if not rid:
                    continue
                if rid not in rels or rels[rid].getAttribute('TargetMode') == 'External':
                    raise SpecError('Missing source image relationship')
                part = target_part(name, rels[rid].getAttribute('Target'))
                if part not in parts:
                    raise SpecError('Missing source image')
                raw = parts[part]
                suffix = Path(part).suffix.lower()
                relative = 'assets/' + hashlib.sha256(raw).hexdigest() + suffix
                item['assets'].append({'part': part, 'path': relative, 'sha256': hashlib.sha256(raw).hexdigest()})
                if assets is not None:
                    target = Path(assets) / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.exists():
                        target.write_bytes(raw)
            items.append(item)
        for rel in rels.values():
            if rel.getAttribute('Type').endswith('/notesSlide'):
                part = target_part(name, rel.getAttribute('Target'))
                if part not in parts:
                    raise SpecError('Missing source notes')
                notes = []
                for shape in descendants(parse(parts[part]), P, 'sp'):
                    if any(p.getAttribute('type') == 'sldNum' for p in descendants(shape, P, 'ph')):
                        continue
                    body = first(shape, P, 'txBody')
                    if body is not None and body_text(body).strip():
                        notes.append(body_text(body))
                if notes:
                    items.append({'id': f's{index}/notes', 'slide': index, 'kind': 'notes',
                                  'text': '\n'.join(notes), 'native_required': False, 'assets': []})
    return {'schema_version': '1.0', 'source_sha256': source_hash(source),
            'canvas': canvas, 'slides': len(slides), 'items': items,
            'scope': 'slide objects and speaker notes; inherited master content also requires visual source review'}


def prepare_redesign(source, style, destination):
    inventory = inspect_source(source)
    load_mapping(style)
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Refusing to overwrite redesign workspace')
    # Parse before creating the workspace. Extraction uses generated safe filenames.
    content = source_content(source)
    destination.mkdir(parents=True, exist_ok=False)
    source_content(source, destination)
    inventory['mode'] = 'redesign'
    save_new(destination / 'source-inventory.json', inventory)
    save_new(destination / 'source-content.json', content)
    plan = {'schema_version': '1.0', 'mode': 'redesign', 'source_sha256': content['source_sha256'],
        'style_sha256': source_hash(style), 'scene': 'scene.yaml', 'structure': 'structure.yaml',
        'design_plan': 'design-plan.yaml', 'protection_review': '', 'protected_terms': [],
        'mapping': [{'source_id': item['id'], 'status': 'unresolved', 'classification': 'content',
                     'targets': [], 'after': '', 'reason': ''} for item in content['items']]}
    save_new(destination / 'restyle-plan.yaml', plan)
    return {'inventory': str(destination / 'source-inventory.json'),
            'content': str(destination / 'source-content.json'),
            'plan': str(destination / 'restyle-plan.yaml'), 'status': 'redesign_required'}


def validate_mapping(plan, content, scene):
    keys(plan, 'schema_version mode source_sha256 style_sha256 scene structure design_plan protection_review protected_terms mapping', 'redesign plan')
    if plan.get('schema_version') != '1.0' or plan.get('mode') != 'redesign':
        raise SpecError('Redesign requires schema 1.0 and mode redesign')
    text(plan.get('protection_review'), 'protection_review')
    protections = plan.get('protected_terms')
    if not isinstance(protections, list):
        raise SpecError('Redesign requires protected_terms')
    targets = {s['id'] + '/' + e['id']: e for s in scene['slides'] for e in s['elements']}
    for slide in scene['slides']:
        targets[slide['id'] + '/notes'] = {'type': 'notes', 'text': slide.get('notes', '')}
    sources = {item['id']: item for item in content['items']}
    mappings = plan.get('mapping')
    if not isinstance(mappings, list):
        raise SpecError('Redesign mapping must be a list')
    seen, slots, slotted, decisions = set(), [], set(), {}
    for mapping in mappings:
        keys(mapping, 'source_id status classification targets after reason approval', 'source mapping')
        sid = mapping.get('source_id')
        if not isinstance(sid, str) or sid not in sources or sid in seen:
            raise SpecError('Unknown or duplicate source mapping')
        seen.add(sid); decisions[sid] = mapping
        item = sources[sid]
        text(mapping.get('reason'), 'mapping.reason')
        if mapping.get('classification') not in ('content', 'decoration'):
            raise SpecError('Classify each source element as content or decoration')
        mapped = mapping.get('targets')
        if not isinstance(mapped, list) or any(not isinstance(t, str) or t not in targets for t in mapped) or len(set(mapped)) != len(mapped):
            raise SpecError('Mapping targets must exist and be distinct')
        status = mapping.get('status')
        if status == 'omitted':
            if mapped or mapping.get('after'):
                raise SpecError('Omitted source cannot claim output targets')
            if mapping['classification'] == 'content' or item['kind'] in ('graphicFrame', 'grpSp', 'notes'):
                text(mapping.get('approval'), 'Explicit approval evidence for omitting source content')
            continue
        if not mapped:
            raise SpecError('Every retained source requires targets')
        if status == 'native':
            if len(mapped) != 1 or 'shape_id' not in item or mapped[0] in slotted:
                raise SpecError('Native mapping needs one unique object slot')
            slot = targets[mapped[0]]
            if slot.get('type') != 'shape' or slot.get('geometry') != 'rect':
                raise SpecError('Native slot must be a scene rect shape')
            slotted.add(mapped[0])
            slots.append({'target': mapped[0], 'slide': item['slide'], 'shape_id': item['shape_id']})
            continue
        if item['native_required']:
            raise SpecError('Keep editable tables/charts/groups/picture fills with status native')
        if status not in ('preserved', 'rewritten', 'redesigned'):
            raise SpecError('Unresolved source mapping')
        if item['text'].strip():
            after = text(mapping.get('after'), 'mapping.after')
            actual = '\n'.join(text_content(targets[t]) for t in mapped if targets[t]['type'] in ('text', 'notes'))
            if after not in actual:
                raise SpecError('Mapped text does not exist at its output targets')
            if status == 'preserved' and after != item['text']:
                raise SpecError('Preserved mapping changed text')
            if numeric_tokens(item['text']) != numeric_tokens(after):
                raise SpecError('Source numeric values changed in redesign mapping')
            if item['kind'] != 'notes' and all(targets[t]['type'] == 'notes' for t in mapped):
                raise SpecError('Do not move visible source content only into notes')
        if item['kind'] == 'pic':
            allowed = {a['sha256'] for a in item['assets']}
            matched = any(targets[t]['type'] == 'image' and source_hash(targets[t]['path']) in allowed for t in mapped)
            if not matched and not (mapping['classification'] == 'decoration' and status == 'redesigned'):
                raise SpecError('Evidence images must retain original image bytes or use a native slot')
    if seen != set(sources):
        raise SpecError('Source mapping must cover every original object and notes item')
    for rule in protections:
        keys(rule, 'source_id text', 'protected term')
        sid, term = rule.get('source_id'), text(rule.get('text'), 'protected term.text')
        if not isinstance(sid, str) or sid not in sources or term not in sources[sid]['text']:
            raise SpecError('Protected term is not grounded in source')
        decision = decisions[sid]
        if decision['status'] != 'native' and term not in decision.get('after', ''):
            raise SpecError('Protected term missing from redesigned output: ' + term)
    return slots


def apply_redesign(source, style, plan_path, output, renderer=None, config_path=None, draft=False, next_output=False):
    from restyle_deck import markdown_report, render
    source, style, plan_path = (Path(p).resolve() for p in (source, style, plan_path))
    output = Path(output).expanduser().absolute()
    if output.suffix.lower() != '.pptx' or output.resolve() == source:
        raise SpecError('Choose a new .pptx output; source cannot be overwritten')
    if next_output:
        output = next_output_path(output)
    reports, pdf = output.with_suffix('.preview'), output.with_suffix('.pdf')
    if any(p.exists() or p.is_symlink() for p in (output, reports, pdf)):
        raise SpecError('Refusing to overwrite output or reports')
    config = resolve_config(config_path, plan_path.parent)
    renderer = renderer or config['output']['renderer']
    if renderer == 'none' and config['output']['pdf']:
        raise SpecError('PDF requires a renderer; no automatic fallback')
    policy = policy_record(config)
    if policy:
        config['communication_policy'] = policy['policy']
    import sys
    print(announce(config), file=sys.stderr)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='decksmith-redesign-', dir=output.parent) as raw:
        work = Path(raw); build = work / 'build'; build.mkdir()
        original = work / 'original.pptx'; shutil.copyfile(source, original)
        style_copy = build / 'style.yaml'; shutil.copyfile(style, style_copy)
        plan_copy = work / 'plan.yaml'; shutil.copyfile(plan_path, plan_copy)
        plan = load_mapping(plan_copy)
        for label, path in (('source', original), ('style', style_copy)):
            if plan.get(label + '_sha256') != source_hash(path):
                raise SpecError(label + ' changed; reinterpret the redesign')
        content = source_content(original)
        snapshots = {}
        for key in ('scene', 'structure', 'design_plan'):
            value = Path(text(plan.get(key), key))
            if value.is_absolute() or not (plan_path.parent / value).resolve().is_relative_to(plan_path.parent):
                raise SpecError('Redesign inputs must be plan-relative')
            snapshot = build / (key + '.yaml')
            shutil.copyfile(plan_path.parent / value, snapshot)
            snapshots[key] = snapshot
        raw_scene = load_mapping(snapshots['scene'])
        scene_origin = (plan_path.parent / plan['scene']).resolve().parent
        for slide in raw_scene.get('slides', []):
            for e in slide.get('elements', []):
                if e.get('type') == 'image':
                    relative = Path(text(e.get('path'), 'image.path'))
                    asset = (scene_origin / relative).resolve()
                    if relative.is_absolute() or not asset.is_relative_to(scene_origin):
                        raise SpecError('Image must be scene-relative')
                    target = build / 'assets' / (source_hash(asset) + asset.suffix.lower())
                    target.parent.mkdir(exist_ok=True)
                    if not target.exists():
                        shutil.copyfile(asset, target)
                    e['path'] = target.relative_to(build).as_posix()
        # Only asset locations are rebased; all style/structure fingerprints remain original.
        snapshots['scene'].write_text(json.dumps(raw_scene, ensure_ascii=False), encoding='utf-8')
        native_text = {}
        originals = {i['id']: i for i in content['items']}
        for mapping in plan.get('mapping', []):
            if isinstance(mapping, dict) and mapping.get('status') == 'native' and mapping.get('source_id') in originals:
                for target in mapping.get('targets', []):
                    if isinstance(target, str) and '/' in target:
                        sid = target.split('/', 1)[0]
                        native_text[sid] = native_text.get(sid, '') + '\n' + originals[mapping['source_id']]['text']
        scene = compile_scene(snapshots['scene'], style_copy, snapshots['structure'], allow_draft=draft, native_content=native_text)
        design = check_plan(snapshots['design_plan'], scene)
        design_checks = inspect_design(scene, design)
        if config['size_explicit'] and scene['canvas'] != config['canvas']:
            raise SpecError('Scene canvas conflicts with config')
        if policy:
            policy_record(config, scene)
        slots = validate_mapping(plan, content, scene)
        runtime = renderer_runtime(renderer)
        node = executable('node', 'DECKSMITH_NODE')
        builder = Path(__file__).with_name('build_deck.mjs')
        run([node, str(builder), '--check'])
        spec = work / 'scene.json'; save_new(spec, scene)
        generated = work / 'generated.pptx'
        run([node, str(builder), '--spec', str(spec), '--output', str(generated)])
        validation = validate_pptx(generated, scene)
        candidate = work / 'candidate.pptx'
        native = transplant(original, generated, candidate, scene, slots) if slots else {'objects': [], 'dependencies': {}}
        if not slots:
            shutil.copyfile(generated, candidate)
        validation.update(mode='redesign', native=native, source_coverage='passed',
                          scope='scene validation and source correspondence; semantic preservation requires review')
        folder = work / 'reports'; folder.mkdir()
        if renderer != 'none':
            before = render(original, work / 'before', {'canvas': content['canvas'], 'slides': [{}] * content['slides']}, renderer, runtime)
            after = render(candidate, work / 'after', scene, renderer, runtime, config['output']['pdf'])
            shutil.copytree(before, folder / 'source')
            for png in after.glob('slide-*.png'):
                shutil.copyfile(png, folder / png.name)
        status = 'draft' if draft else ('ready_for_visual_review' if renderer != 'none' else 'not_visually_reviewed')
        exclusions = [r for r in scene['requirements'] if r['status'] != 'implemented']
        report = {'decksmith_version': read_version(), 'workflow': 'restyle', 'mode': 'redesign', 'status': status,
            'source_sha256': source_hash(original), 'style_sha256': source_hash(style_copy), 'output_sha256': source_hash(candidate),
            'plan_sha256': source_hash(plan_copy), 'renderer': renderer, 'validation': validation,
            'operations': [], 'mapping': [dict(m, before=next(i['text'] for i in content['items'] if i['id'] == m['source_id'])) for m in plan['mapping']],
            'excluded_requirements': exclusions, 'visual_review': 'not_performed',
            'source_slides': content['slides'], 'page_change': {'before': content['slides'], 'after': len(scene['slides'])}}
        save_new(folder / 'restyle-report.json', report)
        # Standard scene exclusions can use reason_kind/approval; reasons are preserved.
        (folder / 'restyle-report.md').write_text(markdown_report(report), encoding='utf-8')
        inventory = inspect_source(original); inventory['mode'] = 'redesign'
        for name, value in (('restyle-plan.json', plan), ('source-content.json', content),
                            ('source-inventory.json', inventory), ('scene.json', scene),
                            ('design-plan.json', design), ('design-checks.json', design_checks)):
            save_new(folder / name, value)
        shutil.copyfile(style_copy, folder / 'style.yaml')
        if policy:
            save_new(folder / 'policy-record.json', policy)
        record_names = {'restyle-report.json', 'restyle-report.md', 'restyle-plan.json',
                        'source-content.json', 'source-inventory.json', 'scene.json',
                        'design-plan.json', 'design-checks.json', 'style.yaml', 'policy-record.json'}
        records = {p.name: source_hash(p) for p in folder.iterdir() if p.is_file() and p.name in record_names}
        manifest = {'workflow': 'restyle', 'mode': 'redesign', 'status': status,
            'output_sha256': report['output_sha256'], 'source_sha256': report['source_sha256'],
            'style_sha256': report['style_sha256'], 'requirements': scene['requirements'],
            'pdf_sha256': source_hash(work / 'after/pdf/candidate.pdf') if config['output']['pdf'] else None,
            'workflow_records': records,
            'preview_sha256': {p.relative_to(folder).as_posix(): source_hash(p) for p in folder.rglob('slide-*.png')},
            'source_slides': content['slides'],
            'slides': [{'id': s['id'], 'preview': f'slide-{i:02d}.png' if renderer != 'none' else None}
                       for i, s in enumerate(scene['slides'], 1)]}
        save_new(folder / 'review-manifest.json', manifest)
        if source_hash(source) != report['source_sha256'] or source_hash(style) != report['style_sha256']:
            raise SpecError('Source/style changed during processing; no result published')
        reserved = []
        try:
            with output.open('xb') as target, candidate.open('rb') as stream:
                reserved.append(output); shutil.copyfileobj(stream, target)
            reports.mkdir(exist_ok=False); reserved.append(reports)
            shutil.copytree(folder, reports, dirs_exist_ok=True)
            if config['output']['pdf']:
                with pdf.open('xb') as target, (work / 'after/pdf/candidate.pdf').open('rb') as stream:
                    reserved.append(pdf); shutil.copyfileobj(stream, target)
        except Exception:
            for p in reversed(reserved):
                shutil.rmtree(p) if p.is_dir() else p.unlink()
            raise
    return {'output': str(output), 'reports': str(reports), 'pdf': str(pdf) if config['output']['pdf'] else None,
            'status': status, 'mode': 'redesign', 'source_slides': content['slides'], 'slides': len(scene['slides'])}
