import copy
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import warnings
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/decksmith/scripts'))
from compile_spec import SpecError, source_hash
from pptx_restyle import (A, P, inspect_source, package, parse, shapes, first, descendants,
                         validate_plan, validate_preservation, write_candidate)
from restyle_deck import apply, prepare
from review_deck import verify


def fixture(path):
    # Deliberately nonsequential slide filenames and source order.
    slide = '''<p:sld xmlns:p="{p}" xmlns:a="{a}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
      xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" mc:Ignorable="p14">
      <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/></p:nvGrpSpPr><p:grpSpPr/>
      <p:sp><p:nvSpPr><p:cNvPr id="2" name="日本語 text"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm rot="60000"><a:off x="100" y="200"/><a:ext cx="3000" cy="4000"/></a:xfrm><a:prstGeom prst="rect"/>
        <a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:ln w="12700"><a:solidFill><a:srgbClr val="000000"/></a:solidFill><a:headEnd type="triangle"/></a:ln></p:spPr>
      <p:txBody><a:bodyPr wrap="square" lIns="500"/><a:lstStyle/><a:p><a:pPr marL="10"><a:buChar char="•"/></a:pPr>
      <a:r><a:rPr lang="ja-JP" sz="2400"><a:latin typeface="Arial" pitchFamily="34"/></a:rPr><a:t xml:space="preserve"> 日本語  10% </a:t></a:r><a:br/>
      <a:fld id="field-id" type="slidenum"><a:t>1</a:t></a:fld><a:endParaRPr lang="ja-JP"/></a:p><a:p><a:r><a:t>次の段落</a:t></a:r></a:p></p:txBody>
      <p:extLst><p:ext uri="preserve"><p14:creationId val="123"/></p:ext></p:extLst></p:sp>
      <p:pic><p:nvPicPr><p:cNvPr id="3" name="image"/></p:nvPicPr><p:blipFill><a:blip r:embed="rId2"/><a:srcRect l="123"/></p:blipFill><p:spPr><a:xfrm><a:off x="1" y="2"/><a:ext cx="3" cy="4"/></a:xfrm></p:spPr></p:pic>
      <p:grpSp><p:nvGrpSpPr><p:cNvPr id="4" name="group"/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="1" y="2"/><a:ext cx="3" cy="4"/><a:chOff x="0" y="0"/><a:chExt cx="10" cy="20"/></a:xfrm></p:grpSpPr>
      <p:sp><p:nvSpPr><p:cNvPr id="5" name="nested"/></p:nvSpPr><p:spPr><a:xfrm><a:off x="5" y="6"/><a:ext cx="7" cy="8"/></a:xfrm></p:spPr></p:sp></p:grpSp>
      <p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="6" name="table"/></p:nvGraphicFramePr><a:graphic><a:graphicData uri="table"><a:tbl><a:tr><a:tc><a:txBody><a:p><a:r><a:t>table 99</a:t></a:r></a:p></a:txBody></a:tc></a:tr></a:tbl></a:graphicData></a:graphic></p:graphicFrame>
      </p:spTree></p:cSld></p:sld>'''.format(p=P, a=A)
    parts = {
        'ppt/presentation.xml': f'<p:presentation xmlns:p="{P}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId id="300" r:id="rId5"/><p:sldId id="301" r:id="rId2"/></p:sldIdLst><p:sldSz cx="9144000" cy="6858000"/></p:presentation>',
        'ppt/_rels/presentation.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId2" Target="slides/slide2.xml"/><Relationship Id="rId5" Target="slides/slide9.xml"/></Relationships>',
        'ppt/slides/slide9.xml': slide, 'ppt/slides/slide2.xml': slide,
        'ppt/media/image1.png': b'preserve image bytes',
        'ppt/notesSlides/notesSlide1.xml': b'<notes>keep 10%</notes>',
        'ppt/charts/chart1.xml': b'<chart>123</chart>',
        'ppt/slideMasters/slideMaster1.xml': b'<master>preserve</master>',
        'ppt/slides/_rels/slide9.xml.rels': b'<Relationships/>',
        'ppt/embeddings/workbook.xlsx': b'embedded chart data',
        '[Content_Types].xml': b'<Types/>',
    }
    with ZipFile(path, 'w') as archive:
        for name, raw in parts.items():
            archive.writestr(name, raw)


def rewrite(source, output, name, transform):
    with ZipFile(source) as before, ZipFile(output, 'w') as after:
        for item in before.infolist():
            raw = before.read(item.filename)
            after.writestr(item, transform(raw) if item.filename == name else raw)


class RestyleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='資料 space ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'original.pptx'
        fixture(self.source)
        self.style = self.base / 'style.yaml'
        self.style.write_text('配色: "#112233"\n書体: Arial\n', encoding='utf-8')
        self.plan = {'schema_version': '1.0', 'mode': 'style_only',
            'source_sha256': source_hash(self.source), 'style_sha256': source_hash(self.style),
            'operations': [
                {'id': 'color', 'slide': 1, 'shape_id': '2', 'set': {'text_color': '#112233', 'fill': '#EEEEEE', 'line_color': '#443322'}},
                {'id': 'font', 'slide': 1, 'shape_id': '2', 'set': {'font': 'Arial', 'bold': True, 'italic': False, 'font_size': 24}},
                {'id': 'bg', 'slide': 2, 'shape_id': 'background', 'set': {'fill': '#FAFAFA'}}],
            'requirements': [
                {'source': '/配色', 'status': 'implemented', 'interpretation': '文字と図形に適用', 'operations': ['color', 'bg']},
                {'source': '/書体', 'status': 'implemented', 'interpretation': '書体を統一', 'operations': ['font']}]}
        self.plan_path = self.base / 'restyle-plan.yaml'
        self.output = self.base / 'new.pptx'

    def save_plan(self):
        self.plan_path.write_text(json.dumps(self.plan, ensure_ascii=False), encoding='utf-8')

    def validate(self):
        return validate_plan(self.plan, self.source, self.style, package(self.source)[2])

    def run_apply(self, **kwargs):
        self.save_plan()
        return apply(self.source, self.style, self.plan_path, self.output, renderer='none', **kwargs)

    def test_inspection_preserves_exact_text_and_presentation_order(self):
        original = self.source.read_bytes()
        inventory = inspect_source(self.source)
        self.assertEqual([s['part'] for s in inventory['slides']], ['ppt/slides/slide9.xml', 'ppt/slides/slide2.xml'])
        self.assertEqual(inventory['canvas'], {'width': 960, 'height': 720})
        obj = next(o for o in inventory['slides'][0]['objects'] if o['shape_id'] == '2')
        self.assertEqual(obj['text'], ' 日本語  10% \n1\n次の段落')
        self.assertIn('rot="60000"', obj['geometry_xml'][0])
        self.assertEqual(original, self.source.read_bytes())

    def test_inspect_creates_unresolved_plan_and_never_overwrites(self):
        destination = self.base / 'analysis'
        report = prepare(self.source, self.style, destination)
        plan = json.loads(Path(report['plan']).read_text())
        self.assertEqual(plan['requirements'][0]['status'], 'unresolved')
        self.assertEqual(plan['source_sha256'], source_hash(self.source))
        with self.assertRaises(FileExistsError):
            prepare(self.source, self.style, destination)

    def test_all_allowed_edits_keep_content_geometry_and_other_parts(self):
        self.validate()
        original = self.source.read_bytes()
        result = write_candidate(self.source, self.output, self.plan)
        self.assertEqual(result['status'], 'passed')
        with ZipFile(self.output) as archive:
            raw = archive.read('ppt/slides/slide9.xml')
            self.assertIn(b'mc:Ignorable="p14"', raw)
            self.assertIn(b'xmlns:p14=', raw)
            doc = parse(raw)
            body = first(shapes(doc)['2'], P, 'txBody')
            for local in ('rPr', 'defRPr', 'endParaRPr'):
                for rpr in descendants(body, A, local):
                    self.assertEqual(rpr.getAttribute('sz'), '2400')
                    self.assertEqual(rpr.getAttribute('b'), '1')
                    self.assertEqual(first(rpr, A, 'latin').getAttribute('typeface'), 'Arial')
            latin = descendants(body, A, 'latin')[1]
            self.assertEqual(latin.getAttribute('pitchFamily'), '34')
            self.assertIn(b'val="112233"', raw)
            self.assertEqual(archive.read('ppt/media/image1.png'), b'preserve image bytes')
        self.assertEqual(original, self.source.read_bytes())

    def test_nested_shape_styling_preserves_group_transform(self):
        self.plan['operations'][0].update(shape_id='5', set={'fill': '#112233'})
        self.validate()
        write_candidate(self.source, self.output, self.plan)

    def test_exact_content_and_geometry_tampering_is_detected(self):
        write_candidate(self.source, self.output, self.plan)
        for old, new in ((b'10%', b'11%'), (b'  10%', b' 10%'),
                         (b'x="100"', b'x="101"'), (b'lIns="500"', b'lIns="501"'),
                         (b'l="123"', b'l="124"'), (b'lang="ja-JP"', b'lang="en-US"'),
                         (b'pitchFamily="34"', b'pitchFamily="35"')):
            with self.subTest(old=old):
                changed = self.base / 'bad.pptx'
                rewrite(self.output, changed, 'ppt/slides/slide9.xml', lambda raw: raw.replace(old, new))
                with self.assertRaisesRegex(SpecError, 'Protected'):
                    validate_preservation(self.source, changed, self.plan['operations'])
        changed = self.base / 'bad.pptx'
        rewrite(self.output, changed, 'ppt/slides/slide9.xml', lambda raw: re.sub(br'<a:br>.*?</a:br>', b'', raw, flags=re.S))
        with self.assertRaisesRegex(SpecError, 'Protected'):
            validate_preservation(self.source, changed, self.plan['operations'])

    def test_note_and_unedited_slide_tampering_is_detected(self):
        write_candidate(self.source, self.output, self.plan)
        for name in ('ppt/notesSlides/notesSlide1.xml', 'ppt/charts/chart1.xml', 'ppt/media/image1.png'):
            changed = self.base / 'bad.pptx'
            rewrite(self.output, changed, name, lambda raw: raw + b'bad')
            with self.assertRaisesRegex(SpecError, 'Protected package part'):
                validate_preservation(self.source, changed, self.plan['operations'])

    def test_unknown_properties_and_unsupported_targets_are_rejected(self):
        for settings in ({'x': 99}, {'text': 'changed'}, {'font_size': True}, {'bold': 'yes'},
                         {'fill': 'red'}, {'font': ''}, {'font_size': 401}, {'unknown': 1}, {}):
            with self.subTest(settings=settings):
                plan = copy.deepcopy(self.plan)
                self.plan['operations'][0]['set'] = settings
                with self.assertRaises(SpecError):
                    self.validate()
                self.plan = plan
        for sid in ('3', '4', '6', 'missing', 2):
            with self.subTest(sid=sid), self.assertRaises(SpecError):
                self.plan['operations'][0]['shape_id'] = sid
                self.validate()

    def test_picture_fills_cannot_be_replaced_with_solid_colors(self):
        modified = self.base / 'picture-fill.pptx'
        rewrite(self.source, modified, 'ppt/slides/slide9.xml', lambda raw: raw.replace(
            b'<a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>',
            b'<a:blipFill><a:blip r:embed="rId2"/><a:stretch><a:fillRect/></a:stretch></a:blipFill>', 1))
        inventory = inspect_source(modified)
        obj = next(o for o in inventory['slides'][0]['objects'] if o['shape_id'] == '2')
        self.assertNotIn('fill', obj['editable_properties'])
        self.plan['source_sha256'] = source_hash(modified)
        with self.assertRaisesRegex(SpecError, 'Picture-filled'):
            validate_plan(self.plan, modified, self.style, package(modified)[2])
        self.plan['operations'][0]['set'].pop('fill')
        validate_plan(self.plan, modified, self.style, package(modified)[2])
        write_candidate(modified, self.output, self.plan)  # Text styling still works.

    def test_inherited_image_background_is_not_hidden(self):
        with ZipFile(self.source, 'a') as archive:
            archive.writestr('ppt/slides/_rels/slide2.xml.rels',
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="layout" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>')
            archive.writestr('ppt/slideLayouts/slideLayout1.xml',
                f'<p:sldLayout xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:bg><p:bgPr><a:blipFill/></p:bgPr></p:bg><p:spTree/></p:cSld></p:sldLayout>')
        self.plan['source_sha256'] = source_hash(self.source)
        self.assertIn('Image background', inspect_source(self.source)['slides'][1]['background_constraint'])
        with self.assertRaisesRegex(SpecError, 'Image background'):
            self.validate()

    def test_source_and_style_fingerprints_are_enforced(self):
        for field in ('source_sha256', 'style_sha256'):
            with self.subTest(field=field):
                old = self.plan[field]
                self.plan[field] = 'stale'
                with self.assertRaisesRegex(SpecError, 'changed'):
                    self.validate()
                self.plan[field] = old

    def test_unknown_modes_are_not_silently_downgraded(self):
        for mode in ('rewrite', 'redesign', 2, 3):
            with self.subTest(mode=mode), self.assertRaisesRegex(SpecError, 'Only schema'):
                self.plan['mode'] = mode
                self.validate()

    def test_overlapping_operations_and_ledger_omissions_are_rejected(self):
        original = copy.deepcopy(self.plan)
        variants = []
        plan = copy.deepcopy(original); plan['requirements'].pop(); variants.append(plan)
        plan = copy.deepcopy(original); plan['requirements'][0]['operations'] = ['missing']; variants.append(plan)
        plan = copy.deepcopy(original); plan['requirements'][0]['status'] = 'unresolved'; variants.append(plan)
        plan = copy.deepcopy(original); plan['operations'][1]['set']['fill'] = '#000000'; variants.append(plan)
        plan = copy.deepcopy(original); plan['operations'][1]['id'] = 'color'; variants.append(plan)
        for plan in variants:
            with self.subTest(plan=plan), self.assertRaises(SpecError):
                self.plan = plan
                self.validate()

    def test_pdf_rejected_without_fake_conversion(self):
        pdf = self.base / 'input.pdf'; pdf.write_bytes(b'%PDF-test')
        with self.assertRaisesRegex(SpecError, 'PPTX input only'):
            inspect_source(pdf)

    def test_dtd_and_signature_are_rejected(self):
        bad = self.base / 'bad.pptx'
        rewrite(self.source, bad, 'ppt/slides/slide9.xml', lambda raw: b'<!DOCTYPE x [<!ENTITY x "bad">]>' + raw)
        with self.assertRaisesRegex(SpecError, 'DTD'):
            inspect_source(bad)
        with ZipFile(self.source, 'a') as archive:
            archive.writestr('_xmlsignatures/sig1.xml', '<signature/>')
        with self.assertRaisesRegex(SpecError, 'signed'):
            inspect_source(self.source)

    def test_duplicate_entries_and_missing_shape_tree_are_rejected(self):
        bad = self.base / 'bad.pptx'
        rewrite(self.source, bad, 'ppt/slides/slide9.xml', lambda raw: f'<p:sld xmlns:p="{P}"/>'.encode())
        with self.assertRaisesRegex(SpecError, 'shape tree'):
            inspect_source(bad)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with ZipFile(self.source, 'a') as archive:
                archive.writestr('ppt/presentation.xml', '<duplicate/>')
        with self.assertRaisesRegex(SpecError, 'Duplicate'):
            inspect_source(self.source)

    def test_drawing_namespace_may_be_default_or_use_another_prefix(self):
        for transform in (
                lambda raw: raw.replace(b'a:', b'draw:').replace(b'xmlns:a=', b'xmlns:draw='),
                lambda raw: raw.replace(b'xmlns:a=', b'xmlns=').replace(b'a:', b'')):
            # Only replace each slide; the other preserved parts remain byte-identical.
            modified = self.base / 'namespaces.pptx'
            with ZipFile(self.source) as before, ZipFile(modified, 'w') as after:
                for item in before.infolist():
                    raw = before.read(item.filename)
                    after.writestr(item, transform(raw) if item.filename.startswith('ppt/slides/slide') else raw)
            plan = copy.deepcopy(self.plan)
            plan['source_sha256'] = source_hash(modified)
            validate_plan(plan, modified, self.style, package(modified)[2])
            output = self.base / ('ns-' + str(len(list(self.base.glob('ns-*')))) + '.pptx')
            write_candidate(modified, output, plan)

    def test_character_outline_precedes_fill_and_remains_unchanged(self):
        modified = self.base / 'outline.pptx'
        rewrite(self.source, modified, 'ppt/slides/slide9.xml', lambda raw: raw.replace(
            b'<a:latin typeface="Arial"', b'<a:ln w="123"><a:solidFill><a:srgbClr val="ABCDEF"/></a:solidFill></a:ln><a:latin typeface="Arial"'))
        plan = copy.deepcopy(self.plan)
        plan['source_sha256'] = source_hash(modified)
        write_candidate(modified, self.output, plan)
        with ZipFile(self.output) as archive:
            body = first(shapes(parse(archive.read('ppt/slides/slide9.xml')))['2'], P, 'txBody')
            prop = next(p for p in descendants(body, A, 'rPr') if first(p, A, 'ln') is not None)
            locals_ = [c.localName for c in prop.childNodes if c.nodeType == c.ELEMENT_NODE]
            self.assertLess(locals_.index('ln'), locals_.index('solidFill'))
            self.assertEqual(first(prop, A, 'ln').getAttribute('w'), '123')

    def test_no_renderer_creates_reports_but_never_visual_approval(self):
        result = self.run_apply()
        self.assertEqual(result['status'], 'not_visually_reviewed')
        folder = self.output.with_suffix('.preview')
        report = json.loads((folder / 'restyle-report.json').read_text())
        self.assertTrue(report['metrics_changed'])
        self.assertEqual(report['validation']['status'], 'passed')
        self.assertEqual(verify(self.output)['visual_wrapping'], 'not_checked')

    def test_protects_original_existing_reports_pdf_and_broken_symlinks(self):
        self.save_plan()
        with self.assertRaisesRegex(SpecError, 'Source cannot'):
            apply(self.source, self.style, self.plan_path, self.source, renderer='none')
        for path in (self.output, self.output.with_suffix('.preview'), self.output.with_suffix('.pdf')):
            with self.subTest(path=path):
                path.symlink_to(self.base / 'missing')
                with self.assertRaisesRegex(SpecError, 'overwrite'):
                    self.run_apply()
                path.unlink()

    def test_numbering_preserves_previous_result(self):
        self.run_apply()
        original = self.output.read_bytes()
        result = self.run_apply(next_output=True)
        self.assertTrue(result['output'].endswith('new-002.pptx'))
        self.assertEqual(self.output.read_bytes(), original)

    def test_exclusions_are_visible_and_unsupported_needs_draft(self):
        req = self.plan['requirements'][1]
        self.plan['operations'].pop(1)
        req.update(status='unsupported', reason='Texture is not supported', operations=[])
        with self.assertRaisesRegex(SpecError, 'Unsupported'):
            self.run_apply()
        self.assertFalse(self.output.exists())
        result = self.run_apply(draft=True)
        self.assertEqual(result['status'], 'draft')
        with self.assertRaisesRegex(SpecError, 'Draft'):
            verify(self.output)

    def test_preservation_conflict_can_be_delivered_with_explicit_exclusion(self):
        self.plan['operations'].pop(1)
        self.plan['requirements'][1].update(status='preservation_conflict', reason='Repositioning would change layout', operations=[])
        self.assertEqual(self.run_apply()['style_application'], 'partial')
        report = (self.output.with_suffix('.preview') / 'restyle-report.md').read_text()
        self.assertIn('Repositioning would change layout', report)

    def test_partial_application_records_operations_and_unapplied_scope(self):
        self.plan['requirements'][0].update(status='partially_implemented')
        with self.assertRaisesRegex(SpecError, 'reason'):
            self.validate()
        self.plan['requirements'][0]['reason'] = 'Only free text and shapes; native table text is preserved'
        self.assertEqual(self.run_apply()['style_application'], 'partial')
        report = json.loads((self.output.with_suffix('.preview') / 'restyle-report.json').read_text())
        self.assertEqual(report['excluded_requirements'][0]['operations'], ['color', 'bg'])
        self.assertIn('native table', report['excluded_requirements'][0]['reason'])

    def test_report_and_result_identity_are_checked(self):
        self.run_apply()
        folder = self.output.with_suffix('.preview')
        (folder / 'restyle-report.json').write_text('{}')
        with self.assertRaisesRegex(SpecError, 'record changed'):
            verify(self.output)

    def test_render_failure_never_publishes_or_falls_back(self):
        self.save_plan()
        with patch('restyle_deck.renderer_runtime', side_effect=SpecError('converter unavailable')):
            with self.assertRaisesRegex(SpecError, 'unavailable'):
                apply(self.source, self.style, self.plan_path, self.output, renderer='libreoffice')
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_suffix('.preview').exists())

    def test_publication_failure_rolls_back_only_new_files(self):
        self.save_plan()
        source_bytes = self.source.read_bytes()
        with patch('restyle_deck.shutil.copyfileobj', side_effect=OSError('copy failed')):
            with self.assertRaisesRegex(OSError, 'copy failed'):
                apply(self.source, self.style, self.plan_path, self.output, renderer='none')
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_suffix('.preview').exists())
        self.assertEqual(self.source.read_bytes(), source_bytes)

    def test_exported_pdf_identity_is_checked(self):
        self.run_apply()
        folder = self.output.with_suffix('.preview')
        path = folder / 'review-manifest.json'
        manifest = json.loads(path.read_text())
        pdf = self.output.with_suffix('.pdf'); pdf.write_bytes(b'%PDF-original')
        manifest['pdf_sha256'] = source_hash(pdf)
        path.write_text(json.dumps(manifest))
        self.assertEqual(verify(self.output)['status'], 'not_visually_reviewed')
        pdf.write_bytes(b'%PDF-modified')
        with self.assertRaisesRegex(SpecError, 'PDF changed'):
            verify(self.output)

    @unittest.skipUnless(os.environ.get('DECKSMITH_RENDER_TEST') == '1', 'requires presentation runtime')
    def test_real_pptx_restyle_exports_original_and_result_previews_and_pdf(self):
        from smoke_test import make_fixture
        project = self.base / 'runtime-setting'
        make_fixture(project, 'none', 'Arial')
        original = self.base / 'runtime-original.pptx'
        result = subprocess.run([sys.executable, str(ROOT / 'skills/decksmith/scripts/create_deck.py'),
            '--scene', str(project / 'scene.yaml'), '--structure', str(project / 'structure.yaml'),
            '--config', str(project / 'decksmith.yaml'), '--output', str(original)],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = copy.deepcopy(self.plan)
        target = next(o for o in inspect_source(original)['slides'][0]['objects'] if o['text'])['shape_id']
        plan['source_sha256'] = source_hash(original)
        plan['operations'] = [{'id': 'title', 'slide': 1, 'shape_id': target,
                               'set': {'text_color': '#112233', 'font': 'Arial'}}]
        for req in plan['requirements']:
            req['operations'] = ['title']
        self.plan_path.write_text(json.dumps(plan))
        config = self.base / 'export.yaml'
        config.write_text('output:\n  renderer: libreoffice\n  pdf: true\n')
        result = apply(original, self.style, self.plan_path, self.output,
                       renderer='libreoffice', config_path=config)
        self.assertEqual(result['status'], 'ready_for_visual_review')
        folder = self.output.with_suffix('.preview')
        self.assertEqual(len(list(folder.glob('slide-*.png'))), 3)
        self.assertEqual(len(list((folder / 'source').glob('slide-*.png'))), 3)
        for png in folder.rglob('slide-*.png'):
            raw = png.read_bytes()
            self.assertEqual(raw[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual((int.from_bytes(raw[16:20], 'big'), int.from_bytes(raw[20:24], 'big')), (1920, 1080))
        self.assertTrue(self.output.with_suffix('.pdf').read_bytes().startswith(b'%PDF-'))
        with self.assertRaises(FileNotFoundError):
            verify(self.output)  # Rendering never manufactures a successful visual review.

    def test_visual_review_requires_original_and_result_for_every_page(self):
        def fake_render(pptx, work, scene, renderer, runtime, pdf=False):
            folder = work / 'preview'; folder.mkdir(parents=True)
            for i in range(1, 3):
                (folder / f'slide-{i:02d}.png').write_bytes(b'fake PNG evidence')
            return folder
        self.save_plan()
        with patch('restyle_deck.renderer_runtime', return_value={}), patch('restyle_deck.render', side_effect=fake_render):
            result = apply(self.source, self.style, self.plan_path, self.output, renderer='libreoffice')
        self.assertEqual(result['status'], 'ready_for_visual_review')
        folder = self.output.with_suffix('.preview')
        review = {'output_sha256': source_hash(self.output), 'source_sha256': source_hash(self.source),
            'reviewer': 'fixture reviewer (schema test, no visual assertion)', 'unresolved_items': [],
            'pages': [{'id': str(i), **{dim: {'status': 'passed', 'evidence': 'Fixture evidence, schema only'}
                      for dim in ('content', 'layout', 'wrapping', 'legibility', 'style')}} for i in range(1, 3)],
            'requirements': [{'source': r['source'], 'status': 'passed', 'evidence': 'Fixture evidence'} for r in self.plan['requirements']]}
        review_path = folder / 'review.json'
        review_path.write_text(json.dumps(review))
        self.assertEqual(verify(self.output)['status'], 'passed')
        review['pages'][0].pop('wrapping')
        review_path.write_text(json.dumps(review))
        with self.assertRaisesRegex(SpecError, 'wrapping'):
            verify(self.output)
        (folder / 'source/slide-01.png').write_bytes(b'modified')
        with self.assertRaisesRegex(SpecError, 'modified'):
            verify(self.output)

    def test_cli_inspect_and_apply_without_repository_state(self):
        self.save_plan()
        result = subprocess.run([sys.executable, str(ROOT / 'skills/decksmith/scripts/restyle_deck.py'),
            'apply', '--source', str(self.source), '--style', str(self.style), '--plan', str(self.plan_path),
            '--output', str(self.output), '--renderer', 'none'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'not_visually_reviewed')


if __name__ == '__main__':
    unittest.main()
