"""PDF adapter: local extraction, reviewable import, and transactional restyle output."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

from compile_spec import SpecError, load_mapping, source_hash, text
from create_deck import executable, next_output_path, renderer_runtime, run
from project_config import resolve_config


def worker(*arguments):
    python = executable(sys.executable, 'DECKSMITH_PDF_PYTHON')
    return run([python, str(Path(__file__).with_name('pdf_import.py')), *map(str, arguments)], timeout=300)


def local_file(root, name):
    path = Path(name)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise SpecError('PDF preparation paths must be relative and inside their folder')
    result = (root / path).resolve()
    if root.resolve() not in result.parents or not result.is_file():
        raise SpecError('Missing or unsafe PDF preparation file: ' + str(name))
    return result


def bridge_scene(analysis, folder):
    canvas = {k: max(p['canvas'][k] for p in analysis['pages']) for k in ('width', 'height')}
    slides = []
    for page in analysis['pages']:
        elements = [{'id': 'pdf-graphics', 'type': 'image', 'path': str((folder / page['graphics']).resolve()),
            'x': 0, 'y': 0, 'width': page['width_pt']*4/3, 'height': page['height_pt']*4/3,
            'fit': 'contain', 'alt': 'Original PDF graphics; raster reference, not editable data'}]
        for span in page['spans']:
            x, y, width, height = (n*4/3 for n in span['bbox_pt'])
            elements.append({'id': span['id'], 'type': 'text', 'text': span['text'],
                'x': x, 'y': (span['baseline_pt'] - span['size_pt'])*4/3, 'width': width, 'height': height,
                'font': span['font'], 'size': span['size_pt']*4/3,
                'bold': span['bold'], 'italic': span['italic'], 'color': span['color'],
                'line_spacing': 1, 'vertical': 'top', 'wrap': False})
        slides.append({'id': str(page['page']), 'background': '#FFFFFF', 'elements': elements})
    return {'canvas': canvas, 'slides': slides}


def prepare_pdf(source, style, destination, mode, renderer=None, config_path=None, font_map=None):
    from restyle_deck import prepare, render
    source, style = Path(source).resolve(), Path(style).resolve()
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise SpecError('Refusing to overwrite PDF preparation: ' + str(destination))
    config = resolve_config(config_path, destination.parent)
    renderer = renderer or config['output']['renderer']
    runtime = renderer_runtime(renderer)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_digest, style_digest = source_hash(source), source_hash(style)
    with tempfile.TemporaryDirectory(prefix='decksmith-pdf-', dir=destination.parent) as raw:
        work = Path(raw); stage = work / 'prepared'; stage.mkdir()
        snapshot = work / 'source.pdf'; shutil.copyfile(source, snapshot)
        arguments = ['--source', snapshot, '--destination', stage / 'pdf']
        if font_map is not None:
            arguments += ['--font-map', Path(font_map).resolve()]
        worker(*arguments)
        analysis = load_mapping(stage / 'pdf/analysis.json')
        scene = bridge_scene(analysis, stage / 'pdf')
        spec = work / 'bridge.json'; spec.write_text(json.dumps(scene, ensure_ascii=False), encoding='utf-8')
        adapter = stage / 'pdf-source.pptx'
        run([executable('node', 'DECKSMITH_NODE'), str(Path(__file__).with_name('build_deck.mjs')),
             '--spec', str(spec), '--output', str(adapter)])
        if renderer != 'none':
            images = render(adapter, work / 'baseline', scene, renderer, runtime)
            shutil.copytree(images, stage / 'normalized-source')
        prepare(adapter, style, stage / 'pptx', mode)
        prepared = {p.relative_to(stage).as_posix(): source_hash(p) for p in sorted(stage.rglob('*'))
                    if p.is_file() and 'pptx' not in p.relative_to(stage).parts}
        plan = {'schema_version': '1.0', 'input_format': 'pdf', 'mode': mode,
            'source_sha256': source_digest, 'style_sha256': style_digest,
            'adapter': 'pdf-source.pptx', 'inner_plan': 'pptx/restyle-plan.yaml',
            'prepared_files': prepared, 'baseline_renderer': renderer,
            'conversion_review': {'reviewer': '', 'pages': [{'page': p['page'], 'status': 'pending',
                'text_evidence': '', 'layout_evidence': '', 'graphics_evidence': ''} for p in analysis['pages']]}}
        (stage / 'restyle-plan.yaml').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
        if source_hash(source) != source_digest or source_hash(style) != style_digest:
            raise SpecError('Source/style changed during PDF preparation')
        # Rename a complete new folder only. No partially prepared destination is published.
        destination.mkdir(exist_ok=False)
        try:
            shutil.copytree(stage, destination, dirs_exist_ok=True)
        except Exception:
            shutil.rmtree(destination); raise
    return {'plan': str(destination / 'restyle-plan.yaml'), 'inner_plan': str(destination / plan['inner_plan']),
        'analysis': str(destination / 'pdf/analysis.json'), 'source_previews': str(destination / 'pdf/source'),
        'normalized_previews': str(destination / 'normalized-source') if renderer != 'none' else None,
        'capabilities': analysis['capabilities'], 'mode': mode,
        'status': 'interpretation_and_import_review_required' if analysis['capabilities'][mode] else 'unsupported_for_selected_mode'}


def validate_conversion(plan, analysis, rendered):
    mode = plan['mode']
    if not analysis['capabilities'].get(mode):
        raise SpecError('PDF is not supported for this fixed-layout mode; inspect analysis.json. '
                        'Use mode 3 explicitly or supply a supported text PDF/PPTX; no automatic mode switch.')
    if not rendered:
        return
    if plan.get('baseline_renderer') == 'none':
        raise SpecError('PDF import has no rendered baseline; inspect again with a renderer before visual approval')
    review = plan.get('conversion_review', {})
    text(review.get('reviewer'), 'PDF conversion reviewer')
    pages = review.get('pages')
    if (not isinstance(pages, list) or any(not isinstance(p, dict) for p in pages)
            or [p.get('page') for p in pages] != [p['page'] for p in analysis['pages']]):
        raise SpecError('PDF import review must cover every original page once in order')
    for page in pages:
        if page.get('status') != 'passed':
            raise SpecError('PDF import fidelity review is pending or failed')
        for field in ('text_evidence', 'layout_evidence', 'graphics_evidence'):
            text(page.get(field), 'PDF import ' + field)


def apply_pdf(source, style, plan_path, output, renderer=None, config_path=None, draft=False, next_output=False):
    from restyle_deck import apply, markdown_report
    source, style, plan_path = (Path(p).resolve() for p in (source, style, plan_path))
    output = Path(output).absolute()
    if output.suffix.lower() != '.pptx':
        raise SpecError('Output must end in .pptx')
    if next_output:
        output = next_output_path(output)
    targets = (output, output.with_suffix('.preview'), output.with_suffix('.pdf'))
    for target in targets:
        if target.exists() or target.is_symlink() or target.resolve() == source:
            raise SpecError('Refusing to overwrite source, output or reports: ' + str(target))
    plan = load_mapping(plan_path); root = plan_path.parent
    if plan.get('input_format') != 'pdf' or plan.get('source_sha256') != source_hash(source) or plan.get('style_sha256') != source_hash(style):
        raise SpecError('PDF source/style changed; inspect again')
    files = plan.get('prepared_files', {})
    if not isinstance(files, dict) or not {'pdf-source.pptx', 'pdf/analysis.json'} <= files.keys():
        raise SpecError('Missing PDF preparation records')
    for name, digest in files.items():
        if source_hash(local_file(root, name)) != digest:
            raise SpecError('PDF preparation changed; inspect again: ' + name)
    if plan.get('adapter') != 'pdf-source.pptx' or plan.get('inner_plan') != 'pptx/restyle-plan.yaml':
        raise SpecError('Invalid PDF adapter or inner plan location')
    adapter = local_file(root, plan['adapter']); inner = local_file(root, plan['inner_plan'])
    analysis = load_mapping(root / 'pdf/analysis.json')
    if analysis.get('source_sha256') != plan['source_sha256'] or load_mapping(inner).get('mode') != plan['mode']:
        raise SpecError('PDF import identity or mode mismatch')
    for page in analysis['pages']:
        name = 'pdf/' + page['source_preview']
        if name not in files:
            raise SpecError('Original PDF preview is not recorded')
    config = resolve_config(config_path, inner.parent)
    renderer = renderer or config['output']['renderer']
    validate_conversion(plan, analysis, renderer != 'none' and not draft)
    if renderer != 'none' and not draft and plan.get('baseline_renderer') != renderer:
        raise SpecError('PDF baseline renderer differs; inspect again with the selected renderer')
    if renderer != 'none' and not draft:
        for page in analysis['pages']:
            if f"normalized-source/slide-{page['page']:02d}.png" not in files:
                raise SpecError('Missing normalized PDF baseline preview')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='decksmith-pdf-result-', dir=output.parent) as raw:
        work = Path(raw); candidate = work / 'candidate.pptx'
        result = apply(adapter, style, inner, candidate, renderer, config_path, draft, False, plan['mode'])
        folder = candidate.with_suffix('.preview')
        if renderer != 'none':
            shutil.rmtree(folder / 'source')
            (folder / 'source').mkdir()
            for page in analysis['pages']:
                original = local_file(root, 'pdf/' + page['source_preview'])
                shutil.copyfile(original, folder / 'source' / f"slide-{page['page']:02d}.png")
        report = load_mapping(folder / 'restyle-report.json')
        report.update(input_format='pdf', pdf_source_sha256=plan['source_sha256'],
                      pdf_limitations=analysis['limitations'], pdf_import_review=plan['conversion_review'])
        (folder / 'restyle-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        (folder / 'restyle-report.md').write_text(markdown_report(report), encoding='utf-8')
        shutil.copyfile(root / 'pdf/analysis.json', folder / 'pdf-conversion.json')
        (folder / 'pdf-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
        manifest = load_mapping(folder / 'review-manifest.json')
        manifest['pdf_input'] = {'source_sha256': plan['source_sha256'], 'adapter_sha256': source_hash(adapter)}
        manifest['preview_sha256'] = {p.relative_to(folder).as_posix(): source_hash(p)
                                      for p in sorted(folder.rglob('slide-*.png'))}
        for name in ('restyle-report.json', 'restyle-report.md', 'pdf-conversion.json', 'pdf-plan.json'):
            manifest['workflow_records'][name] = source_hash(folder / name)
        (folder / 'review-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        if source_hash(source) != plan['source_sha256'] or source_hash(style) != plan['style_sha256']:
            raise SpecError('PDF source/style changed during processing; no result published')
        for name, digest in files.items():
            if source_hash(local_file(root, name)) != digest:
                raise SpecError('PDF preparation changed during processing; no result published')
        reserved = []
        try:
            with output.open('xb') as target:
                reserved.append(output)
                with candidate.open('rb') as stream:
                    shutil.copyfileobj(stream, target)
            targets[1].mkdir(exist_ok=False); reserved.append(targets[1])
            shutil.copytree(folder, targets[1], dirs_exist_ok=True)
            if result['pdf']:
                with targets[2].open('xb') as target:
                    reserved.append(targets[2])
                    with candidate.with_suffix('.pdf').open('rb') as stream:
                        shutil.copyfileobj(stream, target)
        except Exception:
            for path in reversed(reserved):
                shutil.rmtree(path) if path.is_dir() else path.unlink()
            raise
    result.update(output=str(output), reports=str(targets[1]), pdf=str(targets[2]) if result['pdf'] else None,
                  input_format='pdf', pdf_source_sha256=plan['source_sha256'])
    return result
