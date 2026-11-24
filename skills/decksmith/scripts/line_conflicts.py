"""Report visible centerline crossings, mid-route touches and shared segments.

No inference of relationships, no automatic rewiring or visual approval. Opaque
axis-aligned rectangles, tables and charts can hide earlier line portions.
"""
import math
from text_geometry import absolute_points, opaque_cover

EPS = 1e-7


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def along(a, vector, t):
    return (a[0] + vector[0] * t, a[1] + vector[1] * t)


def near(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1]) < EPS


def intersection(a, b, c, d):
    r, s = sub(b, a), sub(d, c)
    rr, ss = sum(v*v for v in r), sum(v*v for v in s)
    if rr < EPS*EPS or ss < EPS*EPS:
        return None
    denominator = cross(r, s); delta = sub(c, a)
    if abs(denominator) > EPS:
        t, u = cross(delta, s) / denominator, cross(delta, r) / denominator
        if -EPS <= t <= 1+EPS and -EPS <= u <= 1+EPS:
            return {'kind': 'crossing' if EPS < t < 1-EPS and EPS < u < 1-EPS else 'touch',
                    'point': along(a, r, max(0, min(1, t)))}
        return None
    if abs(cross(delta, r)) > EPS:
        return None
    t0 = sum(delta[i]*r[i] for i in (0, 1)) / rr
    t1 = sum((d[i]-a[i])*r[i] for i in (0, 1)) / rr
    low, high = max(0, min(t0, t1)), min(1, max(t0, t1))
    if high < low-EPS:
        return None
    if high-low < EPS:
        return {'kind': 'touch', 'point': along(a, r, low)}
    return {'kind': 'overlap', 'points': [along(a, r, low), along(a, r, high)]}


def covered_interval(a, b, box, inset):
    x0, y0, x1, y1 = box[0]+inset, box[1]+inset, box[2]-inset, box[3]-inset
    if x0 >= x1 or y0 >= y1:
        return None
    low, high = 0.0, 1.0
    for start, end, lower, upper in ((a[0], b[0], x0, x1), (a[1], b[1], y0, y1)):
        delta = end-start
        if abs(delta) < EPS:
            if not lower <= start <= upper: return None
        else:
            t0, t1 = (lower-start)/delta, (upper-start)/delta
            low, high = max(low, min(t0, t1)), min(high, max(t0, t1))
        if low > high: return None
    return (low, high)


def visible_overlap(a, b, covers):
    intervals = [(0.0, 1.0)]
    for box, radius in covers:
        hidden = covered_interval(a, b, box, radius)
        if hidden is None: continue
        pieces = []
        for low, high in intervals:
            if hidden[0] > low: pieces.append((low, min(high, hidden[0])))
            if hidden[1] < high: pieces.append((max(low, hidden[1]), high))
        intervals = [(low, high) for low, high in pieces if high-low > EPS]
    vector = sub(b, a)
    return [[along(a, vector, low), along(a, vector, high)] for low, high in intervals]


def inspect_line_conflicts(slide):
    lines, panels = [], []
    for index, e in enumerate(slide['elements']):
        box = opaque_cover(e)
        if e['type'] in ('table', 'chart'):
            box = (e['x'], e['y'], e['x']+e['width'], e['y']+e['height'])
        if box is not None: panels.append((index, box))
        stroke = e.get('stroke', 'none'); width = e.get('stroke_width', 1)
        if stroke == 'none' or width <= 0 or (len(stroke) == 9 and stroke[-2:].upper() == '00'):
            continue
        points = absolute_points(e)
        if len(points) >= 2: lines.append((index, e['id'], points, width))
    records, warnings = [], []
    for i, (li, left, lp, lw) in enumerate(lines):
        for ri, right, rp, rw in lines[i+1:]:
            covers = [(box, width/2) for index, box in panels
                      for path_index, width in ((li, lw), (ri, rw)) if index > path_index]
            found = []
            for a, b in zip(lp, lp[1:]):
                for c, d in zip(rp, rp[1:]):
                    item = intersection(a, b, c, d)
                    if item is None: continue
                    if item['kind'] == 'overlap':
                        found.extend({'kind': 'overlap', 'points': points}
                                     for points in visible_overlap(*item['points'], covers))
                    else:
                        point = item['point']
                        if any(near(point, p) for p in (lp[0], lp[-1])) and any(near(point, p) for p in (rp[0], rp[-1])):
                            continue  # Whole-path endpoints may intentionally join.
                        if any(covered_interval(point, point, box, radius) is not None for box, radius in covers):
                            continue
                        if not any(old.get('point') is not None and near(old['point'], point) for old in found):
                            found.append(item)
            if found:
                record = {'id': slide['id'] + '/' + left + '+' + right + ':line-conflict',
                          'lines': [left, right], 'conflicts': found}
                records.append(record)
                warnings.append({'id': record['id'], 'message': 'Open lines visibly cross, touch mid-route or share a segment. Inspect the intended connections; do not silently merge or remove a relationship.'})
    return warnings, records
