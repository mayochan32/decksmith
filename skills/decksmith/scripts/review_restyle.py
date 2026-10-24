"""Read-only verification of a restyle result and independent per-page review."""
import json
from pathlib import Path

from compile_spec import SpecError, source_hash, text


def verify_restyle(output, manifest, review_path=None):
    output = Path(output)
    folder = output.with_suffix('.preview')
    mode = manifest.get('mode')
    if mode not in ('style_only', 'style_and_text', 'redesign'):
        raise SpecError('Invalid transformation mode')
    if source_hash(output) != manifest.get('output_sha256'):
        raise SpecError('PPTX changed since rendering; regenerate previews and review')
    if manifest.get('pdf_sha256') and source_hash(output.with_suffix('.pdf')) != manifest['pdf_sha256']:
        raise SpecError('PDF changed since rendering; regenerate and review')
    expected = {'restyle-report.json', 'restyle-report.md', 'restyle-plan.json', 'source-inventory.json', 'style.yaml'}
    if mode == 'redesign':
        expected |= {'source-content.json', 'scene.json', 'design-plan.json', 'design-checks.json'}
    if manifest.get('pdf_input'):
        expected |= {'pdf-conversion.json', 'pdf-plan.json'}
    records = manifest.get('workflow_records', {})
    if not expected <= set(records) or set(records) - expected - {'policy-record.json'}:
        raise SpecError('Missing or invalid restyle records')
    for name, digest in records.items():
        if source_hash(folder / name) != digest:
            raise SpecError('Restyle record changed: ' + name)
    report = json.loads((folder / 'restyle-report.json').read_text(encoding='utf-8'))
    plan = json.loads((folder / 'restyle-plan.json').read_text(encoding='utf-8'))
    inventory = json.loads((folder / 'source-inventory.json').read_text(encoding='utf-8'))
    requirements = (json.loads((folder / 'scene.json').read_text(encoding='utf-8'))['requirements']
                    if mode == 'redesign' else plan['requirements'])
    if (report['validation']['status'] != 'passed' or report['output_sha256'] != manifest['output_sha256']
            or report['source_sha256'] != manifest['source_sha256']
            or inventory['source_sha256'] != manifest['source_sha256']
            or plan['source_sha256'] != manifest['source_sha256']
            or source_hash(folder / 'style.yaml') != manifest['style_sha256']
            or requirements != manifest['requirements']
            or plan.get('mode') != mode or report.get('mode') != mode):
        raise SpecError('Restyle report identity or preservation check mismatch')
    if manifest.get('pdf_input'):
        from pdf_input import validate_conversion
        pdf_plan = json.loads((folder / 'pdf-plan.json').read_text(encoding='utf-8'))
        conversion = json.loads((folder / 'pdf-conversion.json').read_text(encoding='utf-8'))
        pdf_hash = manifest['pdf_input']['source_sha256']
        if (pdf_hash != pdf_plan.get('source_sha256') or pdf_hash != conversion.get('source_sha256')
                or report.get('pdf_source_sha256') != pdf_hash or pdf_plan.get('mode') != mode
                or manifest['pdf_input'].get('adapter_sha256') != manifest['source_sha256']
                or pdf_plan.get('prepared_files', {}).get('pdf-source.pptx') != manifest['source_sha256']
                or pdf_plan.get('prepared_files', {}).get('pdf/analysis.json') != source_hash(folder / 'pdf-conversion.json')
                or len(conversion.get('pages', [])) != len(inventory['slides'])):
            raise SpecError('Original PDF identity mismatch')
        validate_conversion(pdf_plan, conversion, manifest['status'] == 'ready_for_visual_review')
        if manifest['status'] == 'ready_for_visual_review':
            for page in conversion['pages']:
                original_name = 'pdf/' + page['source_preview']
                preview_name = f"source/slide-{page['page']:02d}.png"
                if manifest.get('preview_sha256', {}).get(preview_name) != pdf_plan['prepared_files'].get(original_name):
                    raise SpecError('PDF review must use original PDF page previews')
    if manifest['status'] == 'draft':
        raise SpecError('Draft cannot be finalized')
    if manifest['status'] == 'not_visually_reviewed':
        return {'status': 'not_visually_reviewed', 'mode': mode,
                'structural_preservation': ('imported_pdf_baseline' if manifest.get('pdf_input')
                                            else ('redesigned' if mode == 'redesign' else 'passed')),
                'visual_wrapping': 'not_checked', 'semantic_preservation': 'not_checked'}
    if manifest['status'] != 'ready_for_visual_review':
        raise SpecError('Invalid restyle review status')
    pages = manifest.get('slides', [])
    expected_previews = {p['preview'] for p in pages}
    if mode == 'redesign':
        content = json.loads((folder / 'source-content.json').read_text(encoding='utf-8'))
        if content['source_sha256'] != manifest['source_sha256'] or content['slides'] != manifest['source_slides']:
            raise SpecError('Source content identity mismatch')
        expected_previews |= {f'source/slide-{i:02d}.png' for i in range(1, content['slides']+1)}
    else:
        expected_previews |= {p['source_preview'] for p in pages}
    hashes = manifest.get('preview_sha256', {})
    if not pages or set(hashes) != expected_previews:
        raise SpecError('Both source and result previews are required for every page')
    for name, digest in hashes.items():
        # Restrict paths even if a supplied manifest is malformed.
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or source_hash(folder / path) != digest:
            raise SpecError('Invalid or modified restyle preview: ' + name)
    review = json.loads(Path(review_path or folder / 'review.json').read_text(encoding='utf-8-sig'))
    if review.get('output_sha256') != manifest['output_sha256'] or review.get('source_sha256') != manifest['source_sha256']:
        raise SpecError('Review is for different source/result')
    text(review.get('reviewer'), 'reviewer')
    if manifest.get('pdf_input'):
        if review.get('pdf_source_sha256') != manifest['pdf_input']['source_sha256']:
            raise SpecError('Review must identify the original PDF')
        text(review.get('pdf_fidelity_evidence'), 'original PDF fidelity and raster content coverage evidence')
    if review.get('unresolved_items') != []:
        raise SpecError('Resolve every visual issue before approval')
    checked = review.get('pages')
    if not isinstance(checked, list) or any(not isinstance(p, dict) for p in checked):
        raise SpecError('Per-page review required')
    if [p.get('id') for p in checked] != [p['id'] for p in pages]:
        raise SpecError('Review every page once in source order')
    for page in checked:
        dimensions = ('content', 'layout', 'wrapping', 'legibility', 'style') if mode == 'style_only' else ('content', 'meaning', 'layout', 'overflow', 'legibility', 'style')
        for dimension in dimensions:
            evidence = page.get(dimension, {})
            if not isinstance(evidence, dict) or evidence.get('status') != 'passed':
                raise SpecError('Restyle visual review failed: ' + page['id'] + '/' + dimension)
            text(evidence.get('evidence'), dimension + ' comparison evidence')
    if mode == 'style_and_text':
        verify_decisions(review.get('rewrites'), [r['id'] for r in plan['rewrites']], 'id', 'rewrite meaning')
        text(review.get('protection_evidence'), 'protected terms and factual conditions review')
    elif mode == 'redesign':
        verify_decisions(review.get('mapping'), [m['source_id'] for m in plan['mapping']], 'source_id', 'source coverage and meaning')
        verify_decisions(review.get('source_pages'), [str(i) for i in range(1, manifest['source_slides']+1)], 'id', 'original page coverage')
        text(review.get('protection_evidence'), 'protected terms and factual conditions review')
        checks = json.loads((folder / 'design-checks.json').read_text(encoding='utf-8'))
        resolutions = review.get('warning_resolutions', {})
        if not isinstance(resolutions, dict):
            raise SpecError('warning_resolutions must be a mapping')
        for warning in checks['warnings']:
            text(resolutions.get(warning['id']), 'design warning resolution')
    decisions = review.get('requirements')
    if (not isinstance(decisions, list) or any(not isinstance(r, dict) for r in decisions)
            or len(decisions) != len(manifest['requirements'])
            or {r.get('source') for r in decisions} != {r['source'] for r in manifest['requirements']}):
        raise SpecError('Review all applied and excluded requirements')
    for decision in decisions:
        if decision.get('status') != 'passed':
            raise SpecError('Requirement decision failed')
        text(decision.get('evidence'), 'requirement evidence')
    if 'policy-record.json' in records:
        text(review.get('policy_evidence'), 'actual tool use and approval evidence')
    return {'status': 'passed_with_exclusions' if report['excluded_requirements'] else 'passed',
            'mode': mode, 'structural_preservation': ('imported_pdf_baseline' if manifest.get('pdf_input')
                                                    else ('redesigned' if mode == 'redesign' else 'passed')),
            'assurance': 'artifact_identity_and_review_completeness; visual judgments supplied by reviewer'}


def verify_decisions(decisions, ids, key, label):
    if (not isinstance(decisions, list) or any(not isinstance(d, dict) for d in decisions)
            or len(decisions) != len(ids) or {d.get(key) for d in decisions} != set(ids)):
        raise SpecError('Review must cover every ' + label)
    for decision in decisions:
        if decision.get('status') != 'passed':
            raise SpecError('Unresolved ' + label)
        text(decision.get('evidence'), label + ' evidence')
