"""Portable estimates for text fit and visible relationship conflicts.

Unicode advance estimates are review prompts, not font shaping or glyph bounds.
Never changes text, font size, geometry, or the authored reading order.
"""
import math
import unicodedata
from connector_routing import contains, expand, segment_crosses

CLOSING = set('、。，．：；？！)]}）］｝」』】〉》…')
OPENING = set('([{（［｛「『【〈《')


def advance(character, size, tracking=0):
    if unicodedata.combining(character) or character in ('\u200d', '\ufe0f', '\ufe0e'):
        return 0.0
    if unicodedata.east_asian_width(character) in ('W', 'F'):
        ratio = 1.0
    elif character.isspace():
        ratio = 1.32 if character == '\t' else .33
    elif character in 'ilI|!.,:;\'`':
        ratio = .28
    elif character in 'mwMW@%':
        ratio = .85
    elif character.isupper():
        ratio = .65
    else:
        ratio = .55
    return max(0, size * ratio + tracking)


def glyphs(element):
    result = []
    for run in element.get('runs', [{'text': element.get('text', '')}]):
        size = run.get('size', element['size'])
        tracking = run.get('tracking', element.get('tracking', 0))
        for char in run['text'].replace('\r\n', '\n').replace('\r', '\n'):
            result.append((char, advance(char, size, tracking), size))
    return result


def tokens(items):
    result = []
    word = []
    for item in items:
        char = item[0]
        latin_word = (char.isalnum() and unicodedata.east_asian_width(char) not in ('W', 'F')) or char in "'’-_"
        if latin_word:
            word.append(item)
            continue
        if word:
            result.append(word); word = []
        if char in CLOSING and result and result[-1][-1][0] != '\n' and not result[-1][-1][0].isspace():
            result[-1].append(item)
        else:
            result.append([item])
    if word:
        result.append(word)
    index = 0
    while index + 1 < len(result):
        if result[index][-1][0] in OPENING and result[index + 1][0][0] != '\n':
            result[index:index + 2] = [result[index] + result[index + 1]]
        else:
            index += 1
    return result


def estimate(element):
    width = max(.01, element['width'])
    lines, current = [], []

    def finish(reason):
        nonlocal current
        while current and current[-1][0].isspace():
            current.pop()
        lines.append({'width': sum(item[1] for item in current),
                      'size': max((item[2] for item in current), default=element['size']),
                      'characters': sum(not char.isspace() and not unicodedata.combining(char)
                                        and char not in ('\u200d', '\ufe0f', '\ufe0e') for char, _, _ in current),
                      'break_after': reason})
        current = []

    for token in tokens(glyphs(element)):
        if token[0][0] == '\n':
            finish('paragraph')
            continue
        token_width = sum(item[1] for item in token)
        if current and sum(item[1] for item in current) + token_width > width + 1e-7:
            finish('wrap')
        if token_width > width:
            for item in token:
                if current and sum(value[1] for value in current) + item[1] > width + 1e-7:
                    finish('wrap')
                current.append(item)
        elif current or not token[0][0].isspace():
            current.extend(token)
    finish('end')
    spacing = element.get('line_spacing', 1.05)
    height = sum(line['size'] * spacing for line in lines[:-1]) + lines[-1]['size']
    return {'lines': lines, 'estimated_height': height, 'available_height': element['height'],
            'available_width': element['width'], 'estimated_line_count': len(lines)}


def regions(element, measured):
    if abs(element.get('rotation', 0) % 360) > 1e-7:
        return []
    extra = max(0, element['height'] - measured['estimated_height'])
    y = element['y'] + extra * {'top': 0, 'middle': .5, 'bottom': 1}.get(element.get('vertical', 'top'), 0)
    result = []
    for line in measured['lines']:
        align = element.get('align', 'left')
        width = element['width'] if align == 'justify' and line['break_after'] == 'wrap' else line['width']
        x = element['x'] + (element['width'] - width) * {'left': 0, 'justify': 0, 'center': .5, 'right': 1}.get(align, 0)
        if line['characters']:
            result.append((x, y, x + width, y + line['size']))
        y += line['size'] * element.get('line_spacing', 1.05)
    return result


def text_boxes(slide):
    for element in slide['elements']:
        if element['type'] == 'text':
            yield element['id'], element
        elif element['type'] == 'table':
            rows = [element['headers'], *element['rows']]
            columns = element.get('column_widths', [element['width'] / len(rows[0])] * len(rows[0]))
            heights = element.get('row_heights', [element['height'] / len(rows)] * len(rows))
            padding = element.get('padding', 12)
            overrides = {(h['row'], h['column']): h for h in element.get('highlights', [])}
            y = element['y']
            for r, row in enumerate(rows):
                x = element['x']
                for c, value in enumerate(row):
                    override = overrides.get((r, c), {})
                    yield element['id'] + ':r' + str(r) + 'c' + str(c), {
                        'text': str(value), 'font': element['font'], 'size': element['size'],
                        'x': x + padding, 'y': y + padding,
                        'width': columns[c] - padding * 2, 'height': heights[r] - padding * 2,
                        'align': element.get('column_alignments', ['left'] * len(row))[c], 'vertical': 'middle',
                        'color': override.get('color', element.get('header_color', element.get('color', '#000000')) if r == 0 else element.get('color', '#000000')),
                        'bold': override.get('bold', r == 0),
                        '_native_fill': override.get('fill', element.get('header_fill', element.get('fill', slide.get('background', '#FFFFFF'))) if r == 0 else element.get('fill', slide.get('background', '#FFFFFF'))),
                        '_source_id': element['id'], '_native_table': True}
                    x += columns[c]
                y += heights[r]


def absolute_points(element):
    if element['type'] == 'path' and not element.get('closed'):
        local = element['points']
    elif element['type'] == 'shape' and element.get('geometry') == 'line':
        local = [[0, 0], [element['width'], element['height']]]
    else:
        return []
    angle = math.radians(element.get('rotation', 0))
    cx, cy = element['width'] / 2, element['height'] / 2
    return [(element['x'] + cx + (x - cx) * math.cos(angle) - (y - cy) * math.sin(angle),
             element['y'] + cy + (x - cx) * math.sin(angle) + (y - cy) * math.cos(angle)) for x, y in local]


def is_axis_rect(element):
    if element['type'] != 'shape' or abs(element.get('rotation', 0) % 360) >= 1e-7:
        return False
    if 'radius' in element:
        return element.get('geometry') in ('rect', 'roundRect') and element['radius'] == 0
    return element.get('geometry') == 'rect'


def opaque_cover(element):
    fill = element.get('fill', 'none')
    if (is_axis_rect(element) and
            fill != 'none' and (len(fill) == 7 or fill[-2:].upper() == 'FF')):
        return (element['x'], element['y'], element['x'] + element['width'], element['y'] + element['height'])
    return None


def inspect_text_geometry(slide):
    warnings, measurements, texts = [], [], []
    positions = {e['id']: index for index, e in enumerate(slide['elements'])}
    for eid, element in text_boxes(slide):
        target = slide['id'] + '/' + eid
        measured = estimate(element)
        measurements.append({'id': target, **measured})
        if measured['estimated_height'] > element['height'] * 1.05:
            warnings.append({'id': target + ':text-fit', 'message': 'Estimated text height exceeds the box; inspect wrapping and clipping without automatic font shrinking.',
                             'estimated_height': measured['estimated_height'], 'available_height': element['height']})
        if any(line['width'] > element['width'] * 1.05 for line in measured['lines']):
            warnings.append({'id': target + ':text-width', 'message': 'A glyph or token is wider than the available text box.'})
        if any(previous['break_after'] == 'wrap' and current['break_after'] != 'wrap' and
               previous['characters'] >= 4 and current['characters'] == 1
               for previous, current in zip(measured['lines'], measured['lines'][1:])):
            warnings.append({'id': target + ':orphan-line', 'message': 'Estimated automatic wrapping leaves one isolated character; inspect the actual last line.'})
        parent_id = element.get('_source_id', eid)
        texts.append((eid, regions(element, measured), positions.get(parent_id, len(positions)), element.get('_native_table', False)))
    for index, element in enumerate(slide['elements']):
        if element.get('stroke', 'none') == 'none' or not element.get('stroke_width', 0):
            continue
        if len(element.get('stroke', '')) == 9 and element['stroke'][-2:] == '00':
            continue
        points = absolute_points(element)
        if len(points) < 2:
            continue
        for eid, boxes, text_index, table_cell in texts:
            if table_cell and index < text_index:
                continue  # Native table cells have opaque fills above an earlier line.
            conflict = False
            for box in boxes:
                # A white label panel above the line can intentionally hide it.
                covered = index < text_index and any(
                    cover is not None and contains(cover, box)
                    for cover in (opaque_cover(e) for e in slide['elements'][index + 1:text_index]))
                if not covered and any(segment_crosses(a, b, expand(box, element['stroke_width'] / 2))
                                       for a, b in zip(points, points[1:])):
                    conflict = True
                    break
            if conflict:
                warnings.append({'id': slide['id'] + '/' + element['id'] + ':text-crossing:' + eid,
                                 'message': 'An open line crosses an estimated text region; inspect whether the relationship and label remain readable.',
                                 'line': element['id'], 'text': eid})
    return warnings, measurements


def inspect_connector_labels(slide, routes):
    """Measure explicit label associations using estimated ink, not box proximity."""
    elements = {element['id']: element for element in slide['elements']}
    warnings, measurements = [], []
    for route in routes:
        label = elements.get(route.get('label'))
        if label is None:
            continue
        boxes = regions(label, estimate(label))
        distances = []
        for box in boxes:
            for a, b in zip(route['points'], route['points'][1:]):
                dx = max(box[0] - max(a[0], b[0]), min(a[0], b[0]) - box[2], 0)
                dy = max(box[1] - max(a[1], b[1]), min(a[1], b[1]) - box[3], 0)
                distances.append(math.hypot(dx, dy))
        if not distances:
            continue
        distance = min(distances)
        threshold = label['size'] * 2
        prefix = slide['id'] + '/' + route['id']
        measurements.append({'id': prefix, 'label': label['id'], 'estimated_ink_distance': distance,
                             'review_threshold': threshold})
        if distance > threshold:
            warnings.append({'id': prefix + ':detached-label', 'message': 'The label box is associated with a line, but its estimated visible text is far away. Inspect alignment and the reading relationship.',
                             'label': label['id'], 'estimated_ink_distance': distance})
    return warnings, measurements
