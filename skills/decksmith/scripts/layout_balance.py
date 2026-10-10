"""Measure explicitly related labels and shapes, never infer a desired layout.

All limits come from this project's design plan. Text boxes and font em sizes
are geometric proxies, not rendered glyph bounds or an aesthetic score.
"""
from compile_spec import SpecError, keys, number, text


METRICS = {
    'font_size', 'shape_width', 'shape_height', 'font_height_ratio',
    'text_box_center_x', 'text_box_center_y',
    'padding_left', 'padding_right', 'padding_top', 'padding_bottom',
    'gap_x', 'gap_y',
}


def check_balance_groups(planned, slide):
    groups = planned.get('balance_groups', [])
    if not isinstance(groups, list):
        raise SpecError('balance_groups must be a list')
    elements = {e['id']: e for e in slide['elements']}
    seen = set()
    for group in groups:
        keys(group, 'id reason members checks', 'balance group')
        gid = text(group.get('id'), 'balance group.id')
        if gid in seen:
            raise SpecError('Duplicate balance group: ' + gid)
        seen.add(gid)
        text(group.get('reason'), 'balance group.reason')
        members = group.get('members')
        if not isinstance(members, list) or not members:
            raise SpecError('balance group.members must be non-empty')
        shapes, labels = set(), set()
        for member in members:
            keys(member, 'shape label', 'balance member')
            for field, kinds, used in (
                    ('shape', ('shape', 'path'), shapes),
                    ('label', ('text',), labels)):
                eid = text(member.get(field), 'balance member.' + field)
                if eid not in elements or elements[eid]['type'] not in kinds:
                    raise SpecError('Invalid balance ' + field + ' reference: ' + eid)
                if eid in used:
                    raise SpecError('Duplicate balance ' + field + ': ' + eid)
                used.add(eid)
        checks = group.get('checks')
        if not isinstance(checks, dict) or not checks:
            raise SpecError('balance group.checks must be a non-empty mapping')
        for metric, bounds in checks.items():
            if metric not in METRICS:
                raise SpecError('Unsupported balance metric: ' + str(metric))
            keys(bounds, 'min max max_spread', 'balance bounds')
            if not bounds:
                raise SpecError('Empty balance bounds: ' + metric)
            for name, value in bounds.items():
                number(value, 'balance.' + metric + '.' + name,
                       0 if name == 'max_spread' else None)
            if bounds.get('min', float('-inf')) > bounds.get('max', float('inf')):
                raise SpecError('Reversed balance bounds: ' + metric)
            sample_count = len(members) - (1 if metric.startswith('gap_') else 0)
            if sample_count < (2 if 'max_spread' in bounds else 1):
                raise SpecError('Too few balance members for ' + metric)
    return groups


def _values(metric, members, elements):
    pairs = [(elements[m['shape']], elements[m['label']]) for m in members]
    if metric.startswith('gap_'):
        axis, length = ('x', 'width') if metric == 'gap_x' else ('y', 'height')
        ordered = sorted((s for s, _ in pairs), key=lambda s: s[axis])
        return [b[axis] - a[axis] - a[length] for a, b in zip(ordered, ordered[1:])]
    values = []
    for shape, label in pairs:
        font_size = max(r.get('size', label['size']) for r in label.get('runs', [{}]))
        x = (label['x'] - shape['x']) / shape['width']
        y = (label['y'] - shape['y']) / shape['height']
        w = label['width'] / shape['width']
        h = label['height'] / shape['height']
        values.append({
            'font_size': font_size,
            'shape_width': shape['width'], 'shape_height': shape['height'],
            'font_height_ratio': font_size / shape['height'],
            'text_box_center_x': x + w / 2, 'text_box_center_y': y + h / 2,
            'padding_left': x, 'padding_right': 1 - x - w,
            'padding_top': y, 'padding_bottom': 1 - y - h,
        }[metric])
    return values


def inspect_balance(slide, planned):
    warnings, measurements = [], []
    elements = {e['id']: e for e in slide['elements']}
    for group in planned.get('balance_groups', []):
        prefix = slide['id'] + '/balance/' + group['id']
        rotated = [eid for m in group['members'] for eid in m.values()
                   if abs(elements[eid].get('rotation', 0) % 360) > 1e-8]
        if rotated:
            # Do not silently approve unmeasured groups, or forbid intentional rotation.
            warnings.append({'id': prefix + ':unmeasured',
                             'message': 'Rotated elements require visual balance review.',
                             'targets': rotated})
            measurements.append({'id': prefix, 'status': 'unmeasured',
                                 'reason': 'Rotation is outside the axis-aligned measurement scope.'})
            continue
        for metric, bounds in group['checks'].items():
            values = _values(metric, group['members'], elements)
            failures = []
            if 'min' in bounds and min(values) < bounds['min'] - 1e-8:
                failures.append('below min')
            if 'max' in bounds and max(values) > bounds['max'] + 1e-8:
                failures.append('above max')
            if 'max_spread' in bounds and max(values) - min(values) > bounds['max_spread'] + 1e-8:
                failures.append('spread exceeds limit')
            record = {'id': prefix + ':' + metric, 'metric': metric,
                      'members': group['members'], 'values': values,
                      'bounds': bounds, 'status': 'review_needed' if failures else 'within_bounds'}
            measurements.append(record)
            if failures:
                warnings.append({'id': record['id'],
                                 'message': 'Project balance intention: ' + ', '.join(failures)
                                            + '. Inspect rendered labels before revising.',
                                 'metric': metric, 'values': values, 'bounds': bounds,
                                 'reason': group['reason']})
    return warnings, measurements
