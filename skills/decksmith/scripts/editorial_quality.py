"""Link declared communication intent to visible objects and flag literal repeats.

This reports reading material, not a semantic, narrative or aesthetic verdict.
It never rewrites titles, deletes repetitions, chooses emphasis or changes order.
"""
import re
import unicodedata

from compile_spec import SpecError, text


def check_editorial_links(planned, slide):
    communication = planned.get('communication', {})
    if not isinstance(communication, dict):
        return  # Preserve earlier free-form communication notes.
    elements = {e['id']: e for e in slide['elements']}
    if 'headline' in communication:
        headline = communication['headline']
        if not isinstance(headline, str) or elements.get(headline, {}).get('type') != 'text':
            raise SpecError('communication.headline must reference visible text on ' + slide['id'])
    for name in ('visible_evidence', 'emphasis_targets'):
        if name not in communication:
            continue
        targets = communication[name]
        if (not isinstance(targets, list) or not targets
                or any(not isinstance(t, str) or t not in elements for t in targets)
                or len(set(targets)) != len(targets)):
            raise SpecError('communication.' + name + ' must reference distinct visible elements on ' + slide['id'])
    if 'visible_evidence' in communication:
        text(communication.get('takeaway'), 'communication.takeaway')
        text(communication.get('source_basis'), 'communication.source_basis')
    if 'continuity' in communication:
        text(communication['continuity'], 'communication.continuity')


def normalized(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', value)).casefold()


def text_parts(element):
    if element['type'] == 'text':
        value = ''.join(r['text'] for r in element['runs']) if element.get('runs') else element.get('text', '')
        return [(element['id'], value)]
    if element['type'] == 'table':
        return [(element['id'] + f'/cell/{r}/{c}', value)
                for r, row in enumerate([element['headers'], *element['rows']])
                for c, value in enumerate(row)]
    return []


def long_fragments(value):
    # Line breaks may separate a qualifying condition from a repeated sentence.
    # Keep punctuation/negation inside fragments; do not infer paraphrase matches.
    def length(part):
        return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1
                   for c in normalized(part) if c.isalnum())
    return {normalized(part) for part in re.split(r'[\n\r。！？!?]+', value) if length(part) >= 28}


def repetitions(slide):
    groups = [(e['id'], text_parts(e)) for e in slide['elements'] if e['type'] in ('text', 'table')]
    records = []
    for index, (left_id, left_parts) in enumerate(groups):
        for right_id, right_parts in groups[index + 1:]:
            matches = []
            for left_location, left in left_parts:
                for right_location, right in right_parts:
                    candidates = long_fragments(left) | long_fragments(right)
                    repeated = [v for v in candidates if v in normalized(left) and v in normalized(right)]
                    if repeated:
                        matches.append({'text': max(repeated, key=lambda v: (len(v), v)),
                                        'locations': [left_location, right_location]})
            if matches:
                records.append({'id': slide['id'] + '/' + left_id + '+' + right_id + ':repeated-explanation',
                                'elements': [left_id, right_id], 'matches': matches})
    return records


def reading_outline(scene, plan=None):
    planned = {s['id']: s for s in (plan or {}).get('slides', [])}
    outline = []
    for slide in scene['slides']:
        intent = planned.get(slide['id'], {})
        communication = intent.get('communication', {})
        if not isinstance(communication, dict):
            communication = {}
        elements = {e['id']: e for e in slide['elements']}
        headline = communication.get('headline')
        headings = [elements[headline]] if headline else [
            e for e in slide['elements'] if e['type'] == 'text' and e.get('role') in ('display', 'heading')]
        record = {'id': slide['id'],
                  'visible_headings': [{'element': e['id'], 'text': text_parts(e)[0][1]} for e in headings],
                  'declared_takeaway': communication.get('takeaway'),
                  'source_basis': communication.get('source_basis'),
                  'continuity': communication.get('continuity'),
                  'visible_evidence': communication.get('visible_evidence', []),
                  'emphasis_targets': communication.get('emphasis_targets', [])}
        emphasis = []
        for target in record['emphasis_targets']:
            e = elements[target]
            measured = {k: e[k] for k in ('type', 'size', 'color', 'fill', 'stroke', 'stroke_width') if k in e}
            if e['type'] == 'chart':
                measured.update(series_colors=e['colors'], point_highlights=e.get('highlights', []))
            elif e['type'] == 'table':
                measured['cell_highlights'] = e.get('highlights', [])
            emphasis.append({'element': target, **measured})
        record['emphasis_styles'] = emphasis
        outline.append(record)
    return outline
