"""Optional local PDF parser and renderer. Imported only in the PDF worker runtime."""
import argparse
from collections import Counter
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys
import unicodedata

from compile_spec import SpecError


def dependencies():
    extra = os.environ.get('DECKSMITH_PDF_MODULES')
    if extra:
        if not Path(extra).is_dir():
            raise SpecError('DECKSMITH_PDF_MODULES must be an existing local dependency directory')
        sys.path.insert(0, str(Path(extra).resolve()))
    try:
        import pdfplumber
        import pypdf
        import pypdfium2
        from PIL import Image
    except ImportError as error:
        raise SpecError('PDF_DEPENDENCY_MISSING: install pdf-requirements.txt in the selected PDF Python runtime; '
                        'no software was installed automatically: ' + str(error)) from error
    return pdfplumber, pypdf, pypdfium2


def color(value):
    if isinstance(value, (float, int)):
        value = [value] * 3
    if not isinstance(value, (tuple, list)):
        return '#000000'
    if len(value) == 1:
        value = list(value) * 3
    elif len(value) == 4:
        c, m, y, k = value
        value = [1-min(1, c+k), 1-min(1, m+k), 1-min(1, y+k)]
    if len(value) != 3:
        return '#000000'
    return '#' + ''.join(f'{round(max(0, min(1, v))*255):02X}' for v in value)


def font_name(raw, overrides):
    raw = raw.split('+')[-1]
    if raw in overrides:
        return overrides[raw]
    aliases = {'ArialMT': 'Arial', 'Arial-BoldMT': 'Arial', 'Arial-ItalicMT': 'Arial', 'Arial-BoldItalicMT': 'Arial',
               'TimesNewRomanPSMT': 'Times New Roman', 'TimesNewRomanPS-BoldMT': 'Times New Roman',
               'TimesNewRomanPS-ItalicMT': 'Times New Roman', 'TimesNewRomanPS-BoldItalicMT': 'Times New Roman'}
    if raw in aliases:
        return aliases[raw]
    for original, replacement in (('Helvetica', 'Arial'), ('Times', 'Times New Roman'), ('Courier', 'Courier New')):
        if raw.startswith(original):
            return replacement
    return raw


def render_page(document, index, output, transparent=False):
    page = document[index]
    bitmap = page.render(scale=4/3, fill_color=(255, 255, 255, 0 if transparent else 255), draw_annots=True)
    try:
        bitmap.to_pil().save(output, format='PNG')
    finally:
        bitmap.close(); page.close()


def complex_text(page, reader, visited=None):
    """Text used for clipping/invisible OCR cannot safely be replaced by ordinary boxes."""
    from pypdf.generic import ContentStream
    visited = set() if visited is None else visited
    identity = getattr(page, 'indirect_reference', None)
    key = getattr(identity, 'idnum', None) or id(page)
    if key in visited:
        return False
    visited.add(key)
    stream = page if page.get('/Subtype') == '/Form' else page.get('/Contents')
    if stream is not None:
        for args, operator in ContentStream(stream, reader).operations:
            if operator == b'Tr' and args and int(args[0]) != 0:
                return True
    resources = page.get('/Resources', {})
    if hasattr(resources, 'get_object'):
        resources = resources.get_object()
    objects = resources.get('/XObject', {})
    if hasattr(objects, 'get_object'):
        objects = objects.get_object()
    for obj in objects.values():
        obj = obj.get_object()
        if obj.get('/Subtype') == '/Form':
            if complex_text(obj, reader, visited):
                return True
    return False


def layer_constraints(document, index, pdfium):
    """A text-over-graphics bridge cannot preserve occlusion or text transparency."""
    page = document[index]
    seen_text, reasons = [], set()
    try:
        for obj in page.get_objects():
            if obj.type == pdfium.raw.FPDF_PAGEOBJ_FORM:
                # Nested bounds use a form coordinate space; do not guess its composition.
                reasons.add('nested_form_composition')
                continue
            bounds = obj.get_bounds()
            if obj.type == pdfium.raw.FPDF_PAGEOBJ_TEXT:
                if pdfium.raw.FPDFPageObj_HasTransparency(obj):
                    reasons.add('transparent_or_blended_text')
                seen_text.append(bounds)
            elif any(min(bounds[2], t[2]) > max(bounds[0], t[0]) + 0.1
                     and min(bounds[3], t[3]) > max(bounds[1], t[1]) + 0.1 for t in seen_text):
                reasons.add('graphics_over_text')
        return sorted(reasons)
    finally:
        page.close()


def extract(source, destination, overrides=None):
    plumber, pypdf, pdfium = dependencies()
    source, destination = Path(source), Path(destination)
    raw = source.read_bytes()
    if not raw.lstrip().startswith(b'%PDF-'):
        raise SpecError('Invalid PDF signature')
    reader = pypdf.PdfReader(io.BytesIO(raw), strict=False)
    if reader.is_encrypted:
        raise SpecError('Encrypted PDFs are not imported; provide an unencrypted copy you can edit')
    if not reader.pages:
        raise SpecError('PDF has no pages')
    overrides = overrides or {}
    if not isinstance(overrides, dict) or any(not isinstance(k, str) or not isinstance(v, str) or not v.strip() for k, v in overrides.items()):
        raise SpecError('PDF font map must map source font names to installed font family names')
    destination.mkdir(parents=True, exist_ok=False)
    pages_dir = destination / 'source'; pages_dir.mkdir()
    graphics_dir = destination / 'graphics'; graphics_dir.mkdir()
    writer = pypdf.PdfWriter(clone_from=io.BytesIO(raw))
    writer.remove_text()
    stripped_bytes = io.BytesIO(); writer.write(stripped_bytes)
    stripped_raw = stripped_bytes.getvalue()
    stripped_reader = pypdf.PdfReader(io.BytesIO(stripped_raw))
    original_render = pdfium.PdfDocument(raw)
    stripped_render = pdfium.PdfDocument(stripped_raw)
    pages, fonts, sizes = [], {}, set()
    try:
        with plumber.open(io.BytesIO(raw)) as document:
            if len(document.pages) != len(reader.pages):
                raise SpecError('PDF backends disagree on page count')
            for index, page in enumerate(document.pages):
                reasons = layer_constraints(original_render, index, pdfium)
                w, h = float(page.width), float(page.height)
                if not all(math.isfinite(v) and 1 <= v <= 20000 for v in (w, h)):
                    raise SpecError('Unsupported PDF page dimensions')
                sizes.add((round(w, 3), round(h, 3)))
                p = reader.pages[index]
                user_unit = float(p.get('/UserUnit', 1))
                if not math.isfinite(user_unit) or user_unit <= 0:
                    raise SpecError('Invalid PDF UserUnit')
                if user_unit != 1:
                    reasons.append('non_default_user_unit')
                if p.rotation % 360:
                    reasons.append('rotated_page')
                if tuple(p.cropbox) != tuple(p.mediabox) or float(p.mediabox.left) != 0 or float(p.mediabox.bottom) != 0:
                    reasons.append('cropped_or_offset_page')
                if p.get('/Annots'):
                    # Interactive annotations have no equivalent in the imported slide.
                    reasons.append('annotations_or_forms')
                if complex_text(p, reader):
                    reasons.append('outlined_invisible_or_clipping_text')
                if not page.chars:
                    reasons.append('no_extractable_text')
                if any(not c.get('upright', True) for c in page.chars):
                    reasons.append('rotated_or_vertical_text')
                if any(abs(c['matrix'][1]) > 0.0001 or abs(c['matrix'][2]) > 0.0001
                       or c['matrix'][0] <= 0 or c['matrix'][3] <= 0
                       or abs(c['matrix'][0] - c['matrix'][3]) > 0.0001 for c in page.chars):
                    reasons.append('transformed_text')
                if any('\ufffd' in c.get('text', '') or '(cid:' in c.get('text', '') for c in page.chars):
                    reasons.append('unreliable_character_mapping')
                if any(any(unicodedata.bidirectional(c) in ('R', 'AL', 'AN') for c in ch.get('text', '')) for ch in page.chars):
                    reasons.append('right_to_left_text')
                if (stripped_reader.pages[index].extract_text() or '').strip():
                    reasons.append('residual_text_after_separation')
                spans = []
                words = page.extract_words(keep_blank_chars=True, extra_attrs=['fontname', 'size', 'non_stroking_color'],
                                           return_chars=True, expand_ligatures=False, x_tolerance=3, y_tolerance=2)
                covered = Counter()
                for number, word in enumerate(words, 1):
                    chars = word['chars']
                    value = ''.join(c['text'] for c in chars)
                    covered.update(c['text'] for c in chars)
                    x, y, right, bottom = (float(word[k]) for k in ('x0', 'top', 'x1', 'bottom'))
                    if x < -0.1 or y < -0.1 or right > w+0.1 or bottom > h+0.1:
                        reasons.append('text_outside_page')
                    family = font_name(word['fontname'], overrides)
                    fonts[word['fontname']] = family
                    spans.append({'id': f'p{index+1}-text-{number}', 'text': value,
                        'bbox_pt': [x, y, right-x, bottom-y], 'font_source': word['fontname'],
                        'baseline_pt': h - float(chars[0]['matrix'][5]),
                        'font': family, 'size_pt': float(word['size']),
                        'bold': 'bold' in word['fontname'].lower(), 'italic': any(v in word['fontname'].lower() for v in ('italic', 'oblique')),
                        'color': color(chars[0].get('non_stroking_color'))})
                if covered != Counter(c['text'] for c in page.chars):
                    reasons.append('unmapped_characters')
                reasons = sorted(set(reasons))
                source_image = pages_dir / f'slide-{index+1:02d}.png'
                render_page(original_render, index, source_image)
                graphics_image = graphics_dir / f'page-{index+1:02d}.png'
                # An unsupported page stays intact as a reference image in mode 3.
                render_page(original_render if reasons else stripped_render, index, graphics_image, transparent=not reasons)
                pages.append({'page': index+1, 'width_pt': w, 'height_pt': h,
                    'user_unit': user_unit, 'physical_width_pt': w*user_unit, 'physical_height_pt': h*user_unit,
                    'canvas': {'width': round(w*4/3), 'height': round(h*4/3)},
                    'representation': 'raster_reference' if reasons else 'editable_text_and_graphics',
                    'fixed_layout_supported': not reasons, 'reasons': reasons,
                    'spans': spans if not reasons else [], 'extracted_characters': len(page.chars),
                    'source_preview': source_image.relative_to(destination).as_posix(),
                    'graphics': graphics_image.relative_to(destination).as_posix()})
    finally:
        original_render.close(); stripped_render.close()
    fixed = all(p['fixed_layout_supported'] for p in pages) and len(sizes) == 1
    result = {'schema_version': '1.0', 'input_format': 'pdf', 'source_sha256': hashlib.sha256(raw).hexdigest(),
        'pages': pages, 'uniform_page_size': len(sizes) == 1,
        'capabilities': {'style_only': fixed, 'style_and_text': fixed, 'redesign': True},
        'fonts': fonts, 'ocr': 'not_performed', 'vector_graphics': 'rasterized_at_96dpi',
        'limitations': ['PDF glyphs are reconstructed into text frames; visual fidelity must be reviewed.',
                        'PDF graphics retain their appearance as image layers, not editable charts or datasets.',
                        'Unsupported pages are whole-page reference images in mode 3; OCR is not automatic.']}
    (destination / 'analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--font-map', type=Path)
    args = parser.parse_args()
    try:
        if args.probe:
            dependencies(); print(json.dumps({'ready': True})); return 0
        if not args.source or not args.destination:
            raise SpecError('Specify source and destination')
        mapping = json.loads(args.font_map.read_text(encoding='utf-8')) if args.font_map else None
        result = extract(args.source, args.destination, mapping)
        print(json.dumps({'ready': True, 'pages': len(result['pages'])})); return 0
    except Exception as error:
        print('DeckSmith PDF: ' + str(error), file=sys.stderr); return 2


if __name__ == '__main__':
    raise SystemExit(main())
