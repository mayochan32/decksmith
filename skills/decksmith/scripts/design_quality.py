"""Validate project-specific design intent and report measurable review prompts.

No style presets; these checks cannot judge semantic or aesthetic quality.
"""
from compile_spec import SpecError, load_mapping, number, text


def check_plan(path, scene):
    plan = load_mapping(path)
    for field in ('style_sha256', 'structure_sha256'):
        if plan.get(field) != scene[field]:
            raise SpecError('Design plan fingerprint mismatch: ' + field)
    signatures = plan.get('signatures')
    sources = {r['source'] for r in scene['requirements']}
    if not isinstance(signatures, list) or not signatures:
        raise SpecError('design-plan.signatures must identify defining visual intentions')
    for signature in signatures:
        if not isinstance(signature, dict) or signature.get('source') not in sources:
            raise SpecError('Design signature must reference an actual style requirement')
        text(signature.get('intent'), 'signature.intent')
        text(signature.get('visual_check'), 'signature.visual_check')
    text(plan.get('font_evidence'), 'design-plan.font_evidence')
    roles = plan.get('typography')
    if not isinstance(roles, dict) or not roles:
        raise SpecError('design-plan.typography needs project-specific text roles')
    for role, rule in roles.items():
        if role not in ('display','heading','body','caption','label') or not isinstance(rule, dict):
            raise SpecError('Invalid typography role')
        text(rule.get('font'), 'typography.font')
        number(rule.get('min_size'), 'typography.min_size', 1)
        text(rule.get('reason'), 'typography.reason')
    slides = plan.get('slides')
    if not isinstance(slides, list) or any(not isinstance(s, dict) for s in slides):
        raise SpecError('design-plan.slides must be a list')
    if [s.get('id') for s in slides] != [s['id'] for s in scene['slides']]:
        raise SpecError('Design plan must cover the same slides in the same order')
    for planned, actual in zip(slides, scene['slides']):
        ids = {e['id'] for e in actual['elements']}
        if planned.get('focal_element') not in ids:
            raise SpecError('Design focal_element must exist on ' + actual['id'])
        for key in ('focal_reason', 'composition', 'asset_decision'):
            text(planned.get(key), 'design slide.' + key)
        for element in actual['elements']:
            if element['type'] == 'text' and element.get('role') not in roles:
                raise SpecError('Every planned text element needs a defined role: ' + element['id'])
    representatives = plan.get('representative_slides')
    ids = {s['id'] for s in scene['slides']}
    if (not isinstance(representatives, list) or not representatives
            or any(not isinstance(s, str) or s not in ids for s in representatives)
            or len(set(representatives)) != len(representatives)):
        raise SpecError('Choose distinct representative slide IDs from this deck')
    return plan


def inspect_design(scene, plan=None):
    warnings = []
    height = scene['canvas']['height']
    roles = plan['typography'] if plan else {}
    if plan is None:
        warnings.append({'id': 'design-plan-missing', 'message': 'Legacy build: design direction has not been recorded.'})
    for slide in scene['slides']:
        for element in slide['elements']:
            if element['type'] != 'text':
                continue
            target = slide['id'] + '/' + element['id']
            sizes = [r.get('size', element['size']) for r in element.get('runs', [{}])]
            rule = roles.get(element.get('role'), {})
            if rule and min(sizes) < rule['min_size']:
                warnings.append({'id': target + ':role-size', 'message': 'Below the project typography minimum.'})
            elif min(sizes) / height < 0.025:
                warnings.append({'id': target + ':small-text', 'message': 'Small relative to canvas; inspect at presentation viewing size.'})
            fonts = {r.get('font', element['font']) for r in element.get('runs', [{}])}
            if rule and fonts != {rule['font']}:
                warnings.append({'id': target + ':font', 'message': 'Font differs from planned role; verify intentional substitution.'})
    return {'automated_scope': 'measurements_only_not_visual_approval', 'warnings': warnings}
