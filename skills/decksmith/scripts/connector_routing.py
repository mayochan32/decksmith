"""Route explicitly authored relationships around scene geometry.

No content inference, layout catalog, font dependency, or external service.
The result is ordinary editable paths and text, not PowerPoint live bindings.
"""
import copy
import heapq
import math
from compile_spec import SpecError, keys, number, text, color

ARROWS = {'none', 'triangle', 'arrow', 'stealth', 'diamond', 'oval'}
SIDES = ('right', 'bottom', 'left', 'top')
EPS = 1e-7


def rectangle(element):
    values = [number(element.get(k), element['id'] + '.' + k,
                     0.01 if k in ('width', 'height') else None)
              for k in ('x', 'y', 'width', 'height')]
    x, y, w, h = values
    angle = math.radians(number(element.get('rotation', 0), element['id'] + '.rotation'))
    bw = abs(w * math.cos(angle)) + abs(h * math.sin(angle))
    bh = abs(w * math.sin(angle)) + abs(h * math.cos(angle))
    return (x + (w - bw) / 2, y + (h - bh) / 2, x + (w + bw) / 2, y + (h + bh) / 2)


def expand(box, gap):
    return (box[0] - gap, box[1] - gap, box[2] + gap, box[3] + gap)


def contains(outer, inner):
    return (outer[0] <= inner[0] + EPS and outer[1] <= inner[1] + EPS and
            outer[2] >= inner[2] - EPS and outer[3] >= inner[3] - EPS)


def overlaps(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > EPS and min(a[3], b[3]) - max(a[1], b[1]) > EPS


def segment_crosses(a, b, box):
    """Whether any open interior of the box is crossed, including diagonal paths."""
    low, high = 0.0, 1.0
    for start, end, minimum, maximum in ((a[0], b[0], box[0], box[2]), (a[1], b[1], box[1], box[3])):
        delta = end - start
        if abs(delta) < EPS:
            if not minimum + EPS < start < maximum - EPS:
                return False
        else:
            first, last = sorted(((minimum + EPS - start) / delta, (maximum - EPS - start) / delta))
            low, high = max(low, first), min(high, last)
    return high - low > EPS


def simplify(points):
    result = []
    for point in points:
        point = tuple(point)
        if result and abs(result[-1][0] - point[0]) < EPS and abs(result[-1][1] - point[1]) < EPS:
            continue
        if len(result) >= 2:
            a, b = result[-2:]
            if ((abs(a[0] - b[0]) < EPS and abs(b[0] - point[0]) < EPS) or
                    (abs(a[1] - b[1]) < EPS and abs(b[1] - point[1]) < EPS)):
                # Keep a reversal; via points can deliberately require one.
                if (b[0] - a[0]) * (point[0] - b[0]) + (b[1] - a[1]) * (point[1] - b[1]) >= 0:
                    result.pop()
        result.append(point)
    return result


def path_cost(points, bend_penalty):
    points = simplify(points)
    length = sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(points, points[1:]))
    return length + max(0, len(points) - 2) * bend_penalty


def orthogonal_path(start, end, obstacles, bounds, bend_penalty):
    """Shortest rectilinear route on obstacle boundaries, with a bend cost."""
    if any(not bounds[0] - EPS <= p[0] <= bounds[2] + EPS or
           not bounds[1] - EPS <= p[1] <= bounds[3] + EPS for p in (start, end)):
        return None
    xs = sorted({start[0], end[0], bounds[0], bounds[2],
                 *(v for box in obstacles for v in (box[0], box[2]) if bounds[0] <= v <= bounds[2])})
    ys = sorted({start[1], end[1], bounds[1], bounds[3],
                 *(v for box in obstacles for v in (box[1], box[3]) if bounds[1] <= v <= bounds[3])})
    if len(xs) * len(ys) > 100000:
        raise SpecError('Connector routing grid is too large; specify relevant obstacle IDs with avoid.')
    source = (xs.index(start[0]), ys.index(start[1]), -1)
    target = (xs.index(end[0]), ys.index(end[1]))
    distances = {source: 0.0}
    previous = {}
    queue = [(0.0, source)]
    edge_cache = {}
    while queue:
        cost, state = heapq.heappop(queue)
        if cost != distances.get(state):
            continue
        x, y, axis = state
        if (x, y) == target:
            route = []
            while state is not None:
                route.append((xs[state[0]], ys[state[1]]))
                state = previous.get(state)
            return simplify(reversed(route))
        a = (xs[x], ys[y])
        for dx, dy, direction in ((1, 0, 0), (-1, 0, 0), (0, 1, 1), (0, -1, 1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < len(xs) and 0 <= ny < len(ys)):
                continue
            b = (xs[nx], ys[ny])
            cache_key = tuple(sorted(((x, y), (nx, ny))))
            if cache_key not in edge_cache:
                edge_cache[cache_key] = not any(segment_crosses(a, b, box) for box in obstacles)
            if not edge_cache[cache_key]:
                continue
            next_state = (nx, ny, direction)
            value = cost + abs(a[0] - b[0]) + abs(a[1] - b[1])
            if axis != -1 and axis != direction:
                value += bend_penalty
            if value < distances.get(next_state, float('inf')) - EPS:
                distances[next_state] = value
                previous[next_state] = state
                heapq.heappush(queue, (value, next_state))
    return None


def validate_connector(element):
    eid = element['id']
    keys(element, 'id type from to stroke stroke_width clearance avoid via start_arrow end_arrow label', eid)
    for field in ('from', 'to'):
        anchor = element.get(field)
        keys(anchor, 'element side offset', eid + '.' + field)
        text(anchor.get('element'), eid + '.' + field + '.element')
        if anchor.get('side', 'auto') not in (*SIDES, 'auto'):
            raise SpecError(eid + ': invalid connector side')
        if 'offset' in anchor and number(anchor['offset'], eid + '.' + field + '.offset', 0) > 1:
            raise SpecError(eid + ': connector offset must be between 0 and 1')
    color(element.get('stroke'), eid + '.stroke')
    if element['stroke'] == 'none':
        raise SpecError(eid + ': connector needs a visible stroke')
    number(element.get('stroke_width', 2), eid + '.stroke_width', 0.1)
    number(element.get('clearance', 12), eid + '.clearance', 0)
    for field in ('start_arrow', 'end_arrow'):
        if element.get(field, 'none' if field == 'start_arrow' else 'triangle') not in ARROWS:
            raise SpecError(eid + ': invalid arrow type')
    if 'avoid' in element and (not isinstance(element['avoid'], list) or
            any(not isinstance(value, str) for value in element['avoid']) or
            len(element['avoid']) != len(set(element['avoid']))):
        raise SpecError(eid + ': avoid must list distinct element IDs')
    if 'via' in element:
        if not isinstance(element['via'], list) or not element['via']:
            raise SpecError(eid + ': via must list waypoint pairs')
        for point in element['via']:
            if not isinstance(point, list) or len(point) != 2:
                raise SpecError(eid + ': invalid via point')
            for value in point:
                number(value, eid + '.via')
    label = element.get('label')
    if label is not None:
        keys(label, 'text font size color width height x y bold italic align vertical line_spacing tracking role overflow_reason', eid + '.label')
        for field in ('text', 'font'):
            text(label.get(field), eid + '.label.' + field)
        for field in ('width', 'height', 'size'):
            number(label.get(field), eid + '.label.' + field, 1)
        color(label.get('color'), eid + '.label.color')
        if ('x' in label) != ('y' in label):
            raise SpecError(eid + ': label x and y must be specified together')
        for field in ('x', 'y'):
            if field in label:
                number(label[field], eid + '.label.' + field)


def port(box, side, gap, offset=.5):
    left, top, right, bottom = box
    points = {'left': ((left, top + (bottom - top) * offset), (-1, 0)),
              'right': ((right, top + (bottom - top) * offset), (1, 0)),
              'top': ((left + (right - left) * offset, top), (0, -1)),
              'bottom': ((left + (right - left) * offset, bottom), (0, 1))}
    point, direction = points[side]
    return point, (point[0] + gap * direction[0], point[1] + gap * direction[1])


def port_offsets(source, target, first, last, source_anchor, target_anchor):
    offsets = (source_anchor.get('offset', .5), target_anchor.get('offset', .5))
    if 'offset' in source_anchor or 'offset' in target_anchor:
        return offsets
    if (first, last) in (('right', 'left'), ('left', 'right')):
        lower, upper = 1, 3
    elif (first, last) in (('bottom', 'top'), ('top', 'bottom')):
        lower, upper = 0, 2
    else:
        return offsets
    centers = [(box[lower] + box[upper]) / 2 for box in (source, target)]
    low, high = max(source[lower], target[lower]), min(source[upper], target[upper])
    # Only align within both central spans; do not pull exits toward a corner.
    if all(low - EPS <= center <= high + EPS for center in centers):
        coordinate = sum(centers) / 2
        return tuple((coordinate - box[lower]) / (box[upper] - box[lower]) for box in (source, target))
    return offsets


def place_label(label, points, obstacles, routes, bounds, gap):
    if 'x' in label:
        return copy.deepcopy(label)
    width, height = label['width'], label['height']
    candidates = []
    for order, (a, b) in enumerate(zip(points, points[1:])):
        if abs(a[1] - b[1]) < EPS:
            positions = [((a[0] + b[0] - width) / 2, a[1] - gap - height),
                         ((a[0] + b[0] - width) / 2, a[1] + gap)]
            slack = abs(a[0] - b[0]) - width
            orientation = 0
        else:
            positions = [(a[0] + gap, (a[1] + b[1] - height) / 2),
                         (a[0] - gap - width, (a[1] + b[1] - height) / 2)]
            slack = abs(a[1] - b[1]) - height
            orientation = 1
        for preference, (x, y) in enumerate(positions):
            box = (x, y, x + width, y + height)
            if not contains(bounds, box) or any(overlaps(box, other) for other in obstacles):
                continue
            if any(segment_crosses(c, d, box) for route in [points, *routes] for c, d in zip(route, route[1:])):
                continue
            candidates.append((max(0, -slack), orientation, order, preference, x, y))
    if not candidates:
        return None
    _, orientation, _, preference, x, y = min(candidates)
    result = {**label, 'x': x, 'y': y}
    # Attach the actual text to the nearby line, not merely its oversized box.
    # A long horizontal segment is easier to associate with a horizontal label.
    result.setdefault('align', 'center' if orientation == 0 else ('left' if preference == 0 else 'right'))
    result.setdefault('vertical', ('bottom' if preference == 0 else 'top') if orientation == 0 else 'middle')
    return result


def lower_connectors(elements, canvas):
    """Preserve explicit endpoints and text, resolving only their geometry."""
    originals = {}
    for element in elements:
        if not isinstance(element, dict):
            raise SpecError('Scene elements must be mappings')
        eid = text(element.get('id'), 'element.id')
        if eid in originals:
            raise SpecError('Duplicate element: ' + eid)
        originals[eid] = element
    nodes = {eid: e for eid, e in originals.items() if e.get('type') not in ('connector', 'path')}
    boxes = {eid: rectangle(e) for eid, e in nodes.items()}
    output, records, routes, placed_labels = [], [], [], []
    for element in elements:
        if element.get('type') != 'connector':
            output.append(element)
            continue
        validate_connector(element)
        eid = element['id']
        source, target = (element[field]['element'] for field in ('from', 'to'))
        if source not in nodes or target not in nodes or source == target:
            raise SpecError(eid + ': endpoints must name two distinct non-path elements on this slide')
        if any(abs(nodes[node].get('rotation', 0) % 360) > EPS for node in (source, target)):
            raise SpecError(eid + ': rotated endpoints need an explicitly authored path')
        label = element.get('label')
        label_id = eid + '__label'
        if label is not None and label_id in originals:
            raise SpecError(eid + ': reserved generated label ID already exists: ' + label_id)
        avoid = element.get('avoid')
        if avoid is not None and any(node not in boxes for node in avoid):
            raise SpecError(eid + ': avoid references an unknown or non-box element')
        selected = set(avoid) if avoid is not None else set(boxes)
        selected.update((source, target))
        if avoid is None:
            # Background panels and labels inside endpoint nodes do not block exits.
            selected = {node for node in selected if node in (source, target) or not any(
                contains(boxes[node], boxes[end]) or contains(boxes[end], boxes[node])
                for end in (source, target))}
        gap = element.get('clearance', 12) + element.get('stroke_width', 2) / 2
        obstacle_items = [(node, boxes[node]) for node in sorted(selected)] + [('prior-label', box) for box in placed_labels]
        actual_obstacles = [box for _, box in obstacle_items]
        inflated = [(node, expand(box, gap)) for node, box in obstacle_items]
        obstacles = [box for _, box in inflated]
        if label is not None and 'x' in label:
            box = expand((label['x'], label['y'], label['x'] + label['width'], label['y'] + label['height']), gap)
            obstacles.append(box)
            inflated.append(('explicit-label', box))
        inset = element.get('stroke_width', 2) / 2
        bounds = (inset, inset, canvas['width'] - inset, canvas['height'] - inset)
        starts = SIDES if element['from'].get('side', 'auto') == 'auto' else (element['from']['side'],)
        ends = SIDES if element['to'].get('side', 'auto') == 'auto' else (element['to']['side'],)
        choices = []
        for first in starts:
            for last in ends:
                source_offset, target_offset = port_offsets(boxes[source], boxes[target], first, last, element['from'], element['to'])
                p0, p1 = port(boxes[source], first, gap, source_offset)
                p3, p2 = port(boxes[target], last, gap, target_offset)
                if any(segment_crosses(p0, p1, box) for node, box in inflated if node != source):
                    continue
                if any(segment_crosses(p2, p3, box) for node, box in inflated if node != target):
                    continue
                route = [p0, p1]
                waypoints = [p1, *[tuple(p) for p in element.get('via', [])], p2]
                for a, b in zip(waypoints, waypoints[1:]):
                    section = orthogonal_path(a, b, obstacles, bounds, max(12, gap * 2))
                    if section is None:
                        break
                    route.extend(section[1:])
                else:
                    route = simplify([*route, p3])
                    if len(route) < 2:
                        continue
                    resolved_label = place_label(label, route, actual_obstacles, routes, bounds, max(6, gap / 2)) if label is not None else None
                    if label is not None and resolved_label is None:
                        continue
                    choices.append((path_cost(route, max(12, gap * 2)), first, last, route, resolved_label, source_offset, target_offset))
        if not choices:
            raise SpecError(eid + ': no clear route and label space; move nodes, adjust label dimensions, or specify via/avoid')
        _, first, last, route, resolved_label, source_offset, target_offset = min(choices, key=lambda item: (item[0], item[1], item[2]))
        left, top = min(p[0] for p in route), min(p[1] for p in route)
        width, height = max(p[0] for p in route) - left, max(p[1] for p in route) - top
        output.append({'id': eid, 'type': 'path', 'x': left, 'y': top,
                       'width': max(.01, width), 'height': max(.01, height),
                       'points': [[p[0] - left, p[1] - top] for p in route], 'closed': False,
                       'fill': 'none', 'stroke': element['stroke'], 'stroke_width': element.get('stroke_width', 2),
                       'start_arrow': element.get('start_arrow', 'none'), 'end_arrow': element.get('end_arrow', 'triangle')})
        if resolved_label is not None:
            output.append({'id': label_id, 'type': 'text', 'role': 'label', **resolved_label})
            placed_labels.append((resolved_label['x'], resolved_label['y'],
                                  resolved_label['x'] + resolved_label['width'], resolved_label['y'] + resolved_label['height']))
        routes.append(route)
        records.append({'id': eid, 'from': source, 'to': target, 'from_side': first, 'to_side': last,
                        'from_offset': source_offset, 'to_offset': target_offset,
                        'points': [list(p) for p in route], 'bends': max(0, len(route) - 2),
                        'label': label_id if resolved_label is not None else None})
    return output, records
