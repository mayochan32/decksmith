"""PDF integration tests use an explicitly selected local optional backend."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/decksmith/scripts'))
from compile_spec import SpecError, source_hash, load_mapping
from pdf_input import local_file, validate_conversion
from restyle_deck import prepare, apply
from review_deck import verify
from pptx_restyle import inspect_source, package, descendants, A
from test_transform_modes import make_redesign

PDF_PYTHON = os.environ.get('DECKSMITH_PDF_PYTHON')


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


class PdfGuardTests(unittest.TestCase):
    def test_unsafe_paths_and_unreviewed_or_unsupported_conversions(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for path in ('../source.pdf', '/source.pdf', 'missing'):
                with self.subTest(path=path), self.assertRaises(SpecError):
                    local_file(root, path)
        analysis = {'capabilities': {'style_only': False}, 'pages': [{'page': 1}]}
        with self.assertRaisesRegex(SpecError, 'no automatic mode switch'):
            validate_conversion({'mode': 'style_only'}, analysis, False)
        analysis['capabilities']['style_only'] = True
        with self.assertRaises(SpecError):
            validate_conversion({'mode': 'style_only', 'baseline_renderer': 'none'}, analysis, True)
        with self.assertRaises(SpecError):
            validate_conversion({'mode': 'style_only', 'baseline_renderer': 'libreoffice'}, analysis, True)


@unittest.skipUnless(PDF_PYTHON, 'Set DECKSMITH_PDF_PYTHON to an optional PDF backend Python')
class PdfIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'original.pdf'
        self.style = self.base / 'style.yaml'; self.style.write_text('色: "#173F35"', encoding='utf-8')
        self.fixture()

    def fixture(self, kind='text'):
        script = '''
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, NumberObject
from PIL import Image
from io import BytesIO
import sys
path, kind = sys.argv[1:]
b=BytesIO(); c=canvas.Canvas(b,pagesize=(720,405))
if kind == 'scan':
    image=Image.new('RGB',(720,405),'navy'); c.drawInlineImage(image,0,0,720,405)
else:
    c.setFont('Helvetica',24); c.drawString(40,330,'Tokyo 2026: improve 10%.')
    c.setFont('Helvetica',16); c.drawString(40,270,'We aim to improve the proposal.')
    c.setFillColorRGB(.1,.25,.3); c.rect(0,0,720,50,fill=1,stroke=0)
    if kind == 'annotation': c.linkURL('https://example.invalid', (40,330,300,355))
    if kind == 'vertical':
        c.saveState(); c.translate(620,80); c.rotate(90); c.drawString(0,0,'Vertical'); c.restoreState()
    if kind == 'invisible':
        t=c.beginText(50,200); t.setTextRenderMode(3); t.textLine('Hidden OCR'); c.drawText(t)
    if kind == 'outline':
        t=c.beginText(50,200); t.setTextRenderMode(1); t.textLine('Outline'); c.drawText(t)
    if kind == 'alpha':
        c.saveState(); c.setFillAlpha(0); c.drawString(40,170,'Hidden 123.45'); c.restoreState()
    if kind == 'cover':
        c.setFillColorRGB(1,1,1); c.rect(30,260,400,40,fill=1,stroke=0)
    if kind == 'mixed':
        c.showPage(); c.setPageSize((405,720)); c.drawString(40,650,'Portrait')
c.save(); r=PdfReader(b); w=PdfWriter()
for p in r.pages:
    if kind == 'rotation': p.rotate(90)
    if kind == 'crop': p.cropbox.lower_left=(20,20)
    if kind == 'userunit': p[NameObject('/UserUnit')]=NumberObject(2)
    w.add_page(p)
if kind == 'encrypted': w.encrypt('password')
w.write(path)
'''
        result = subprocess.run([PDF_PYTHON, '-c', script, str(self.source), kind], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)

    def prep(self, mode='2', renderer='none', folder='prepared'):
        target = self.base / folder
        result = prepare(self.source, self.style, target, mode, renderer)
        return target, result

    def complete_fixed_plan(self, target, rewrite=False):
        path = target / 'pptx/restyle-plan.yaml'; plan = load_mapping(path)
        inventory = load_mapping(target / 'pptx/source-inventory.json')
        objects = inventory['slides'][0]['objects']
        obj = next(o for o in objects if o.get('text') and 'Tokyo' in o['text'])
        plan['operations'] = [{'id': 'green', 'slide': 1, 'shape_id': obj['shape_id'], 'set': {'text_color': '#173F35'}}]
        plan['requirements'] = [{'source': '/色', 'interpretation': 'Green title', 'status': 'implemented', 'operations': ['green']}]
        if plan['mode'] == 'style_and_text':
            plan['protection_review'] = 'Preserve Tokyo, 2026, 10%, goal and source conditions.'
            plan['protected_terms'] = [{'slide': 1, 'shape_id': obj['shape_id'], 'text': 'Tokyo'}]
            if rewrite:
                plan['rewrites'] = [{'id': 'concise', 'slide': 1, 'shape_id': obj['shape_id'],
                    'edits': [{'run': 0, 'before': obj['text'], 'after': 'Tokyo 2026: target 10%.', 'reason': 'Shorten the same goal'}]}]
        write(path, plan)

    def test_text_pdf_modes1_and2_preserve_source_and_report_provenance(self):
        digest = source_hash(self.source)
        for mode in ('1', '2'):
            with self.subTest(mode=mode):
                target, result = self.prep(mode, folder='mode'+mode)
                self.assertTrue(result['capabilities']['style_only'])
                for _, document in package(target / 'pdf-source.pptx')[2]:
                    self.assertTrue(all(p.getAttribute('wrap') == 'none' for p in descendants(document, A, 'bodyPr')))
                self.complete_fixed_plan(target, rewrite=mode == '2')
                output = self.base / ('mode'+mode+'.pptx')
                receipt = apply(self.source, self.style, target / 'restyle-plan.yaml', output, 'none')
                self.assertEqual(receipt['input_format'], 'pdf')
                self.assertEqual(source_hash(self.source), digest)
                report = load_mapping(output.with_suffix('.preview') / 'restyle-report.json')
                self.assertEqual(report['pdf_source_sha256'], digest)
                self.assertEqual(verify(output)['status'], 'not_visually_reviewed')
                texts = str(inspect_source(output))
                self.assertIn('Tokyo 2026: target 10%.' if mode == '2' else 'Tokyo 2026: improve 10%.', texts)
                self.assertFalse(output.with_suffix('.pdf').exists())
                with self.assertRaisesRegex(SpecError, 'overwrite'):
                    apply(self.source, self.style, target / 'restyle-plan.yaml', output, 'none')

    def test_pdf_mode3_uses_original_source_mapping(self):
        target, _ = self.prep('3')
        authored = self.base / 'authoring'
        make_redesign(authored, target / 'pdf-source.pptx', self.style)
        shutil.rmtree(target / 'pptx'); shutil.copytree(authored, target / 'pptx')
        output = self.base / 'redesigned.pptx'
        apply(self.source, self.style, target / 'restyle-plan.yaml', output, 'none')
        report = load_mapping(output.with_suffix('.preview') / 'restyle-report.json')
        self.assertTrue(report['mapping'])
        self.assertEqual(report['input_format'], 'pdf')
        self.assertEqual(verify(output)['status'], 'not_visually_reviewed')

    def test_scan_rotated_vertical_cropped_annotation_and_ocr_only_support_reference_redesign(self):
        for kind in ('scan', 'rotation', 'vertical', 'crop', 'annotation', 'invisible', 'outline', 'alpha', 'cover', 'userunit', 'mixed'):
            with self.subTest(kind=kind):
                self.fixture(kind)
                target, receipt = self.prep('1', folder=kind)
                self.assertFalse(receipt['capabilities']['style_only'])
                self.assertTrue(receipt['capabilities']['redesign'])
                analysis = load_mapping(target / 'pdf/analysis.json')
                self.assertEqual(analysis['ocr'], 'not_performed')
                with self.assertRaisesRegex(SpecError, 'not supported'):
                    apply(self.source, self.style, target / 'restyle-plan.yaml', self.base / (kind+'.pptx'), 'none', draft=True)
                self.assertFalse((self.base / (kind+'.pptx')).exists())

    def test_invalid_encrypted_inputs_and_missing_backend_leave_no_preparation(self):
        with patch.dict(os.environ, {'DECKSMITH_PDF_MODULES': str(self.base / 'missing-dependencies')}):
            with self.assertRaisesRegex(SpecError, 'dependency directory'):
                self.prep()
        self.assertFalse((self.base / 'prepared').exists())
        self.fixture('encrypted')
        with self.assertRaisesRegex(SpecError, 'Encrypted'):
            self.prep()
        self.assertFalse((self.base / 'prepared').exists())
        self.source.write_bytes(b'not a PDF')
        with self.assertRaisesRegex(SpecError, 'signature'):
            self.prep()
        self.assertFalse((self.base / 'prepared').exists())

    def test_preparation_and_original_changes_and_mode_mismatch_are_rejected(self):
        target, _ = self.prep('2'); self.complete_fixed_plan(target)
        plan = target / 'restyle-plan.yaml'; output = self.base / 'result.pptx'
        with self.assertRaisesRegex(SpecError, 'mode'):
            apply(self.source, self.style, plan, output, 'none', mode='1')
        graphics = target / 'pdf/graphics/page-01.png'; original = graphics.read_bytes()
        graphics.write_bytes(original + b'modified')
        with self.assertRaisesRegex(SpecError, 'preparation changed'):
            apply(self.source, self.style, plan, output, 'none')
        graphics.write_bytes(original)
        self.source.write_bytes(self.source.read_bytes() + b'\nchanged')
        with self.assertRaisesRegex(SpecError, 'source/style changed'):
            apply(self.source, self.style, plan, output, 'none')
        self.assertFalse(output.exists())

    def test_scan_mode3_preserves_reference_image_and_reports_no_ocr(self):
        self.fixture('scan'); target, _ = self.prep('3')
        folder = target / 'pptx'; plan_path = folder / 'restyle-plan.yaml'
        plan = load_mapping(plan_path); content = load_mapping(folder / 'source-content.json')
        item = content['items'][0]
        plan.update(protection_review='Retain the entire raster source; no text extraction or automatic OCR is claimed.',
            mapping=[{'source_id': item['id'], 'classification': 'content', 'status': 'preserved',
                      'targets': ['reference/source'], 'reason': 'Retain the original scanned visual'}])
        write(plan_path, plan)
        write(folder / 'structure.yaml', {'slides': [{'id': 'reference', 'purpose': 'Show source visual', 'required_text': ['Reference']}]})
        hashes = {'style_sha256': source_hash(self.style), 'structure_sha256': source_hash(folder / 'structure.yaml')}
        write(folder / 'scene.yaml', {'schema_version': '1.0', **hashes, 'canvas': {'width': 960, 'height': 540},
            'requirements': [{'source': '/色', 'status': 'implemented', 'interpretation': 'Green heading', 'targets': ['reference/title']}],
            'slides': [{'id': 'reference', 'background': '#FFFFFF', 'elements': [
                {'id': 'source', 'type': 'image', 'path': item['assets'][0]['path'], 'alt': 'Unchanged scan',
                 'x': 40, 'y': 120, 'width': 880, 'height': 380, 'fit': 'contain'},
                {'id': 'title', 'type': 'text', 'text': 'Reference', 'font': 'Arial', 'size': 32, 'color': '#173F35',
                 'role': 'body', 'x': 40, 'y': 40, 'width': 880, 'height': 60}]}]})
        write(folder / 'design-plan.yaml', {**hashes,
            'signatures': [{'source': '/色', 'intent': 'Green heading', 'visual_check': 'Inspect the title'}],
            'font_evidence': 'Arial requested; check the actual target rendering',
            'typography': {'body': {'font': 'Arial', 'min_size': 30, 'reason': 'Readable heading'}},
            'representative_slides': ['reference'], 'slides': [{'id': 'reference', 'focal_element': 'source',
                'focal_reason': 'Source image', 'composition': 'Source under the title', 'asset_decision': 'Retain original raster image'}]})
        output = self.base / 'scan-mode3.pptx'
        apply(self.source, self.style, target / 'restyle-plan.yaml', output, 'none')
        report = load_mapping(output.with_suffix('.preview') / 'pdf-conversion.json')
        self.assertEqual(report['pages'][0]['representation'], 'raster_reference')
        self.assertEqual(report['ocr'], 'not_performed')

    @unittest.skipUnless(os.environ.get('DECKSMITH_RENDER_TEST') == '1', 'Real renderer test opt-in')
    def test_real_pdf_previews_import_gate_final_review_and_original_preview_binding(self):
        target, _ = self.prep('2', 'libreoffice'); self.complete_fixed_plan(target, True)
        output = self.base / 'result.pptx'; outer_path = target / 'restyle-plan.yaml'
        with self.assertRaises(SpecError):
            apply(self.source, self.style, outer_path, output, 'libreoffice')
        self.assertFalse(output.exists())
        outer = load_mapping(outer_path)
        outer['conversion_review'] = {'reviewer': 'Automated test of supplied review validation', 'pages': [
            {'page': 1, 'status': 'passed', 'text_evidence': 'Fixture glyph coverage',
             'layout_evidence': 'Fixture frame coverage', 'graphics_evidence': 'Fixture rectangle coverage'}]}
        write(outer_path, outer)
        apply(self.source, self.style, outer_path, output, 'libreoffice')
        folder = output.with_suffix('.preview'); manifest = load_mapping(folder / 'review-manifest.json')
        self.assertEqual(source_hash(folder / 'source/slide-01.png'), source_hash(target / 'pdf/source/slide-01.png'))
        self.assertNotEqual(source_hash(folder / 'source/slide-01.png'), source_hash(target / 'normalized-source/slide-01.png'))
        evidence = {'status': 'passed', 'evidence': 'Synthetic fixture evidence to test record validation, not a visual judgment'}
        review = {'reviewer': 'Test', 'output_sha256': source_hash(output), 'source_sha256': manifest['source_sha256'],
            'unresolved_items': [], 'pages': [{'id': '1', **{k: evidence for k in ('content','meaning','layout','overflow','legibility','style')}}],
            'requirements': [{'source': '/色', **evidence}], 'rewrites': [{'id': 'concise', **evidence}],
            'protection_evidence': 'Synthetic factual condition check'}
        write(folder / 'review.json', review)
        with self.assertRaisesRegex(SpecError, 'original PDF'):
            verify(output)
        review.update(pdf_source_sha256=source_hash(self.source), pdf_fidelity_evidence='Synthetic original PDF comparison evidence')
        write(folder / 'review.json', review)
        self.assertEqual(verify(output)['status'], 'passed')
        changed = copy.deepcopy(manifest)
        changed['preview_sha256']['source/slide-01.png'] = source_hash(target / 'normalized-source/slide-01.png')
        write(folder / 'review-manifest.json', changed)
        with self.assertRaisesRegex(SpecError, 'original PDF'):
            verify(output)


if __name__ == '__main__':
    unittest.main()
