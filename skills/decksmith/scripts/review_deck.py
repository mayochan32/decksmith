"""Check final artifact identity and structured human/agent review evidence.

Read-only: never turns its own measurements into a visual approval.
"""
import argparse
import json
from pathlib import Path
from compile_spec import SpecError, source_hash, text


def verify(output, review_path=None):
    output = Path(output).resolve()
    folder = output.with_suffix('.preview')
    manifest = json.loads((folder / 'review-manifest.json').read_text(encoding='utf-8-sig'))
    actual = source_hash(output)
    if actual != manifest['output_sha256']:
        raise SpecError('PPTX changed since rendering; regenerate previews and review. Do not replace only the recorded hash.')
    for name, digest in manifest.get('workflow_records', {}).items():
        if name not in ('content-check.json','policy-record.json') or source_hash(folder/name)!=digest:
            raise SpecError('Workflow record changed since rendering')
    if manifest['status'] == 'draft':
        raise SpecError('Draft with unresolved requirements cannot be finalized')
    if manifest['status'] == 'not_visually_reviewed':
        return {'status': 'not_visually_reviewed', 'output_sha256': actual,
                'delivery_status':manifest.get('delivery_status','standard'),
                'content_review': 'not_checked', 'style_review': 'not_checked'}
    preview_hashes = manifest.get('preview_sha256')
    if not isinstance(preview_hashes, dict) or not preview_hashes:
        raise SpecError('Missing preview fingerprints; rebuild with the current tool')
    expected_names = {s['preview'] for s in manifest['slides']}
    if set(preview_hashes) != expected_names:
        raise SpecError('Preview fingerprint set does not match slides')
    for name, digest in preview_hashes.items():
        if Path(name).name != name or source_hash(folder / name) != digest:
            raise SpecError('Preview changed or invalid: ' + name)
    plan_hash = manifest.get('design_plan_sha256')
    if not plan_hash or source_hash(folder / 'design-plan.json') != plan_hash:
        raise SpecError('Missing or modified design plan; style approval requires project-specific intent')
    quality_hash = manifest.get('design_checks_sha256')
    if not quality_hash or source_hash(folder / 'design-checks.json') != quality_hash:
        raise SpecError('Missing or modified design checks')
    review = json.loads(Path(review_path or folder / 'review.json').read_text(encoding='utf-8-sig'))
    if review.get('output_sha256') != actual:
        raise SpecError('Review is for a different PPTX')
    text(review.get('reviewer'), 'reviewer')
    if review.get('unresolved_items') != []:
        raise SpecError('Unresolved items must be listed and resolved before approval')
    if 'content-check.json' in manifest.get('workflow_records', {}):
        text(review.get('source_content_evidence'), 'independent source content review')
    if 'policy-record.json' in manifest.get('workflow_records', {}):
        text(review.get('policy_evidence'), 'actual tool use and human approval review')
    if manifest.get('delivery_status')=='awaiting_images' and review.get('delivery_status')!='awaiting_images':
        raise SpecError('Image placeholders must remain awaiting_images at delivery')
    pages = review.get('pages')
    if not isinstance(pages, list) or any(not isinstance(p, dict) for p in pages):
        raise SpecError('Review requires per-page evidence')
    if [p.get('id') for p in pages] != [s['id'] for s in manifest['slides']]:
        raise SpecError('Review must cover every page once, in order')
    for page in pages:
        for dimension in ('content', 'legibility', 'style'):
            evidence = page.get(dimension, {})
            if not isinstance(evidence, dict) or evidence.get('status') != 'passed':
                raise SpecError('Page review failed: ' + page['id'] + '/' + dimension)
            text(evidence.get('evidence'), dimension + ' visual evidence')
    requirements = manifest['requirements']
    decisions = review.get('requirements')
    if not isinstance(decisions, list) or any(not isinstance(r, dict) for r in decisions):
        raise SpecError('Review must check requirement decisions, including exclusions')
    if (len(decisions) != len(requirements)
            or {r.get('source') for r in decisions} != {r['source'] for r in requirements}):
        raise SpecError('Requirement review coverage mismatch')
    for decision in decisions:
        if decision.get('status') != 'passed':
            raise SpecError('Requirement not visually satisfied or exclusion not justified')
        text(decision.get('evidence'), 'requirement evidence')
    checks = json.loads((folder / 'design-checks.json').read_text(encoding='utf-8-sig'))
    acknowledgments = review.get('warning_resolutions', {})
    if not isinstance(acknowledgments, dict):
        raise SpecError('warning_resolutions must be a mapping')
    for warning in checks['warnings']:
        text(acknowledgments.get(warning['id']), 'resolution for ' + warning['id'])
    alternatives = [r['source'] for r in requirements if r['status'] == 'approved_alternative']
    return {'status': 'awaiting_images' if manifest.get('delivery_status')=='awaiting_images' else ('passed_with_approved_alternatives' if alternatives else 'passed'),
            'output_sha256': actual, 'approved_alternatives': alternatives,
            'assurance': 'artifact_identity_and_review_completeness; visual judgments supplied by reviewer'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--review', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.output, args.review), ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, 'DeckSmith review: ' + str(error) + '\n')
