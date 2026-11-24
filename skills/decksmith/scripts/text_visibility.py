"""Review prompts for estimated text collisions, covering and colour contrast.

Never changes content or layout. Font-em regions are estimates, not shaped
glyphs. Images, nonrectangular fills and rotation can remain unmeasured.
"""
from text_geometry import text_boxes, estimate, regions, opaque_cover, is_axis_rect
from connector_routing import rectangle

EPS = 1e-7


def area(box):
    return max(0, box[2]-box[0]) * max(0, box[3]-box[1])


def intersection(a, b):
    box = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
    return box if area(box) > EPS else None


def subtract(box, cover):
    hit = intersection(box, cover)
    if hit is None: return [box]
    x0, y0, x1, y1 = box; a, b, c, d = hit
    return [r for r in [(x0, y0, x1, b), (x0, d, x1, y1), (x0, b, a, d), (c, b, x1, d)] if area(r) > EPS]


def rgba(value):
    if value == 'none': return (1, 1, 1, 0)
    if not isinstance(value, str) or len(value) not in (7, 9): return None
    try:
        return tuple(int(value[i:i+2], 16)/255 for i in (1, 3, 5)) + ((int(value[7:9], 16)/255 if len(value) == 9 else 1),)
    except ValueError:
        return None


def blend(foreground, background):
    if foreground is None: return None
    if foreground[3] >= 1-EPS: return foreground[:3]
    if foreground[3] <= EPS: return background
    if background is None: return None
    return tuple(foreground[i]*foreground[3]+background[i]*(1-foreground[3]) for i in range(3))


def ratio(foreground, background):
    def luminance(rgb):
        linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb]
        return sum(v*w for v, w in zip(linear, (.2126, .7152, .0722)))
    a, b = luminance(foreground), luminance(background)
    return (max(a, b)+.05)/(min(a, b)+.05)


def box_of(element):
    return rectangle(element)


def paint_regions(element):
    """Flat fills are known; unknown paint is represented by None."""
    kind = element['type']
    if kind in ('text', 'connector') or (kind == 'shape' and element.get('geometry') == 'line'):
        return []
    if kind == 'path':
        fill = rgba(element.get('fill', 'none'))
        return [(box_of(element), None)] if element.get('closed') and fill is not None and fill[3] > EPS else []
    if kind == 'table':
        rows = [element['headers'], *element['rows']]
        widths = element.get('column_widths', [element['width']/len(rows[0])]*len(rows[0]))
        heights = element.get('row_heights', [element['height']/len(rows)]*len(rows))
        overrides = {(h['row'], h['column']): h for h in element.get('highlights', [])}
        result = []; y = element['y']
        for r, row in enumerate(rows):
            x = element['x']
            for c, _ in enumerate(row):
                fill = overrides.get((r, c), {}).get('fill', element.get('header_fill', element.get('fill')) if r == 0 else element.get('fill'))
                result.append(((x, y, x+widths[c], y+heights[r]), fill))
                x += widths[c]
            y += heights[r]
        return result
    if kind == 'shape':
        fill = element.get('fill', 'none')
        if fill == 'none' or (rgba(fill) is not None and rgba(fill)[3] <= EPS): return []
        if is_axis_rect(element):
            return [(box_of(element), fill)]
    return [(box_of(element), None)]  # Images/chart internals/other geometry.


def backgrounds(boxes, elements, background):
    initial = blend(rgba(background), (1, 1, 1))
    pieces = [(box, initial) for box in boxes]
    for e in elements:
        for paint, fill in paint_regions(e):
            replacement = []
            for box, old in pieces:
                hit = intersection(box, paint)
                if hit is None:
                    replacement.append((box, old)); continue
                replacement.extend((part, old) for part in subtract(box, hit))
                replacement.append((hit, blend(rgba(fill), old)))
            pieces = replacement
            if len(pieces) > 512: return [(box, None) for box in boxes]
    return pieces


def inspect_text_visibility(slide):
    warnings, measurements, visible = [], [], []
    elements = slide['elements']; positions = {e['id']: i for i, e in enumerate(elements)}
    for eid, e in text_boxes(slide):
        prefix = slide['id'] + '/' + eid
        index = positions[e.get('_source_id', eid)]
        boxes = regions(e, estimate(e))
        if not boxes:
            measurements.append({'id': prefix, 'status': 'unmeasured', 'reason': 'Empty or rotated text regions.'})
            continue
        colours = [(r.get('color', e.get('color', '#000000')), r.get('size', e['size']))
                   for r in e.get('runs', [{'text': e.get('text', '')}]) if r.get('text', '').strip()]
        if not colours: continue
        if all(rgba(c) is not None and rgba(c)[3] <= EPS for c, _ in colours):
            warnings.append({'id': prefix + ':transparent-text', 'message': 'Declared text has fully transparent ink; it is retained natively but cannot be read.'})
            measurements.append({'id': prefix, 'status': 'transparent'})
            continue
        pieces = list(boxes); occluders = []; unknown_above = []
        for later in elements[index+1:]:
            cover = opaque_cover(later)
            if later['type'] in ('table', 'chart'): cover = box_of(later)
            if cover is not None:
                old_area = sum(area(b) for b in pieces)
                pieces = [part for box in pieces for part in subtract(box, cover)]
                if sum(area(b) for b in pieces) < old_area-EPS: occluders.append(later['id'])
            elif any((fill is None or (rgba(fill) is not None and EPS < rgba(fill)[3] < 1-EPS)) and any(intersection(box, paint) for box in pieces)
                     for paint, fill in paint_regions(later)):
                unknown_above.append(later['id'])
        original_area = sum(area(b) for b in boxes)
        covered = 1-sum(area(b) for b in pieces)/original_area
        if covered >= .2-EPS:
            warnings.append({'id': prefix + ':text-covered', 'message': 'A later opaque object covers a substantial part of an estimated text region; inspect lost content.',
                             'covered_fraction': round(covered, 4), 'covering_objects': occluders})
        if unknown_above:
            warnings.append({'id': prefix + ':occlusion-unmeasured', 'message': 'An image, nonrectangular object or translucent overlay above the text intersects its estimated region; visibility requires actual image review.', 'objects': unknown_above})
        visible.append((eid, pieces))
        if e.get('_native_table'):
            rgb = blend(rgba(e.get('_native_fill')), (1, 1, 1))
            paints = [(box, rgb) for box in pieces]
        else:
            paints = backgrounds(pieces, elements[:index], slide.get('background', '#FFFFFF'))
        known = {tuple(round(v, 10) for v in rgb) for _, rgb in paints if rgb is not None}
        unknown = any(rgb is None for _, rgb in paints) or bool(unknown_above)
        # A mixed-colour run cannot be assigned to multiple backgrounds without
        # shaped glyph positions. Do not invent spatial correspondence.
        uncertain_runs = len(set(c for c, _ in colours)) > 1 and len(known) > 1
        contrasts = []
        if not uncertain_runs and not unknown_above:
            for colour, size in sorted(set(colours)):
                threshold = 3.0 if size >= 24 else 4.5
                for bg in sorted(known):
                    fg = blend(rgba(colour), bg)
                    if fg is not None:
                        contrasts.append({'foreground': colour, 'background_rgb': bg,
                                          'ratio': round(ratio(fg, bg), 3), 'review_threshold': threshold})
        if any(c['ratio'] < c['review_threshold']-EPS for c in contrasts):
            warnings.append({'id': prefix + ':low-contrast', 'message': 'Text and a known flat background have a low colour-contrast ratio; inspect at viewing size without automatic recolouring.',
                             'minimum_ratio': min(c['ratio'] for c in contrasts)})
        measurements.append({'id': prefix, 'status': 'unmeasured' if not contrasts else ('partial' if unknown else 'measured_flat_fills'),
                             'covered_fraction': round(covered, 4), 'unknown_background': unknown or uncertain_runs,
                             'contrast': contrasts})
    for i, (left, first) in enumerate(visible):
        for right, second in visible[i+1:]:
            amount = sum(area(hit) for a in first for b in second if (hit := intersection(a, b)) is not None)
            smaller = min(sum(area(b) for b in first), sum(area(b) for b in second))
            if smaller > EPS and amount/smaller >= .1-EPS:
                warnings.append({'id': slide['id'] + '/' + left + '+' + right + ':text-overlap',
                                 'message': 'Estimated visible text regions overlap; inspect actual glyphs and any intentional typographic treatment.',
                                 'overlap_fraction': round(amount/smaller, 4)})
    # Native chart label positions are not exposed here, but their single text
    # colour and declared opaque chart fill can still be compared independently.
    for e in elements:
        if e['type'] != 'chart': continue
        bg = rgba(e.get('fill', slide.get('background', '#FFFFFF')))
        ink = rgba(e['color']); prefix = slide['id'] + '/' + e['id']
        if bg is None or ink is None or bg[3] < 1-EPS: continue
        contrast = ratio(blend(ink, bg[:3]), bg[:3]); threshold = 3 if e['size'] >= 24 else 4.5
        measurements.append({'id': prefix, 'status': 'chart_colour_only', 'ratio': round(contrast, 3), 'review_threshold': threshold})
        if contrast < threshold:
            warnings.append({'id': prefix + ':low-contrast', 'message': 'Native chart text has low contrast against its declared flat fill; chart label positions still require image review.'})
    return warnings, measurements
