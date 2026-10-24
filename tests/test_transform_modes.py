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
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/decksmith/scripts'))
from compile_spec import SpecError, source_hash, compile_scene
from pptx_restyle import (A, P, body_text, children, descendants, first, package, shapes,
                         validate_plan, validate_preservation, write_candidate)
from restyle_deck import apply, prepare
from redesign_deck import source_content, validate_mapping
from review_deck import verify
from test_restyle import fixture, rewrite


def make_native_fixture(folder):
    folder = Path(folder)
    source = folder / 'native-source.pptx'
    js = folder / 'fixture.cjs'
    js.write_text('''
const PptxGenJS = require(process.argv[2]);
const pptx = new PptxGenJS(); pptx.layout = 'LAYOUT_WIDE';
let s=pptx.addSlide();
s.addText('改善提案',{x:0.5,y:0.5,w:10,h:0.7,fontSize:30,fontFace:'Arial'});
s.addText('東京で2026年に10%改善することを目標にしています。',{x:0.5,y:2,w:12,h:1,fontSize:22,fontFace:'Arial'});
s.addNotes('条件：東京での実施。出典：社内計画2026。');
s=pptx.addSlide();
s.addText('実績の確認',{x:0.5,y:0.5,w:10,h:0.7,fontSize:30,fontFace:'Arial'});
s.addTable([['指標','値'],['改善率','10%']],{x:0.5,y:2,w:5,h:2,fontSize:20});
s.addChart(pptx.ChartType.bar,[{name:'実績',labels:['前期','今期'],values:[10,20]}],{x:6.5,y:2,w:5.5,h:3,showLegend:false,showValue:true});
s.addNotes('数値は試験用。元の表とグラフを保持する。');
pptx.writeFile({fileName:process.argv[3]});
''', encoding='utf-8')
    result = subprocess.run(['node', str(js), str(ROOT / 'skills/decksmith/node_modules/pptxgenjs'), str(source)],
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return source


def make_redesign(folder, source, style):
    folder = Path(folder)
    prepare(source, style, folder, '3')
    content = source_content(source)
    plan = json.loads((folder / 'restyle-plan.yaml').read_text())
    plan['protection_review'] = 'Source numbers, Tokyo, units, conditions and citations are retained.'
    elements, mappings, required, notes, native_index, text_index = [], [], [], [], 0, 0
    for item in content['items']:
        target = 'combined/' + item['id'].replace('/', '-')
        mapping = {'source_id': item['id'], 'classification': 'content', 'targets': [target],
                   'reason': 'Preserve the source evidence while combining pages.'}
        if item['kind'] == 'notes':
            mapping.update(status='preserved', after=item['text'], targets=['combined/notes'])
            notes.append(item['text'])
        elif item['native_required']:
            elements.append({'id': target.split('/')[1], 'type': 'shape', 'geometry': 'rect',
                'x': 80 + 880 * native_index, 'y': 520, 'width': 800, 'height': 440,
                'fill': 'none', 'stroke': 'none'})
            native_index += 1
            mapping['status'] = 'native'
            if item['text'].strip():
                required.append(item['text'])
        elif item['text'].strip():
            value = item['text'].replace('することを目標にしています。', 'を目指します。')
            mapping.update(status='rewritten' if value != item['text'] else 'preserved', after=value)
            elements.append({'id': target.split('/')[1], 'type': 'text', 'text': value, 'font': 'Arial',
                'size': 48 if text_index == 0 else 32, 'color': '#173F35', 'role': 'body',
                'x': 80, 'y': 80 + 130 * text_index, 'width': 1740, 'height': 110})
            text_index += 1; required.append(value)
            if '東京' in item['text']:
                plan['protected_terms'].append({'source_id': item['id'], 'text': '東京'})
        else:
            mapping.update(status='omitted', classification='decoration', targets=[],
                           reason='Replace empty decorative objects with the new composition.')
        mappings.append(mapping)
    plan['mapping'] = mappings
    (folder / 'restyle-plan.yaml').write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
    structure = {'slides': [{'id': 'combined', 'purpose': 'Combine source text and editable evidence',
                            'required_text': required, 'notes': '\n'.join(notes)}]}
    (folder / 'structure.yaml').write_text(json.dumps(structure, ensure_ascii=False), encoding='utf-8')
    fingerprints = {'style_sha256': source_hash(style), 'structure_sha256': source_hash(folder / 'structure.yaml')}
    scene = {'schema_version': '1.0', **fingerprints, 'canvas': {'width': 1920, 'height': 1080},
             'requirements': [{'source': '/色', 'status': 'implemented', 'interpretation': 'Apply green type and light background',
                               'targets': ['combined']}],
             'slides': [{'id': 'combined', 'background': '#F4EEE5', 'elements': elements}]}
    (folder / 'scene.yaml').write_text(json.dumps(scene, ensure_ascii=False), encoding='utf-8')
    design = {**fingerprints, 'signatures': [{'source': '/色', 'intent': 'Green text with light background',
               'visual_check': 'Inspect the entire redesigned page'}], 'font_evidence': 'Arial requested; Japanese fallback requires visual review',
              'typography': {'body': {'font': 'Arial', 'min_size': 30, 'reason': 'Preserve legibility'}},
              'representative_slides': ['combined'],
              'slides': [{'id': 'combined', 'focal_element': elements[0]['id'], 'focal_reason': 'Source proposal',
                          'composition': 'Source text above native table and chart', 'asset_decision': 'Retain editable source objects'}]}
    (folder / 'design-plan.yaml').write_text(json.dumps(design, ensure_ascii=False), encoding='utf-8')
    return plan, scene, content


class RewriteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.source = self.base / 'source.pptx'; fixture(self.source)
        self.style = self.base / 'style.yaml'; self.style.write_text('色: "#123456"')
        self.path = self.base / 'plan.yaml'; self.output = self.base / 'result.pptx'
        self.plan = {'schema_version': '1.0', 'mode': 'style_and_text', 'source_sha256': source_hash(self.source),
            'style_sha256': source_hash(self.style), 'operations': [],
            'requirements': [{'source': '/色', 'status': 'not_applicable', 'interpretation': 'Writing-only test', 'reason': 'Test scope', 'operations': []}],
            'protection_review': 'Japanese label and numeric unit are locked.',
            'protected_terms': [{'slide': 1, 'shape_id': '2', 'text': '日本語'}, {'slide': 1, 'shape_id': '2', 'text': '10%'}],
            'rewrites': [{'id': 'concise', 'slide': 1, 'shape_id': '2',
                          'edits': [{'run': 0, 'before': ' 日本語  10% ', 'after': '日本語の改善率は10%', 'reason': 'Clarify the existing label'}]}]}

    def check(self):
        return validate_plan(self.plan, self.source, self.style, package(self.source)[2])

    def save(self):
        self.path.write_text(json.dumps(self.plan, ensure_ascii=False))

    def test_mode2_changes_only_declared_text_and_keeps_geometry(self):
        self.check(); original = self.source.read_bytes()
        receipt = write_candidate(self.source, self.output, self.plan)
        self.assertEqual(receipt['mode'], 'style_and_text')
        self.assertEqual(original, self.source.read_bytes())
        doc = package(self.output)[2][0][1]
        self.assertIn('日本語の改善率は10%', body_text(first(shapes(doc)['2'], P, 'txBody')))
        self.assertIn('1', body_text(first(shapes(doc)['2'], P, 'txBody')))  # Field retained.
        changed = self.base / 'bad.pptx'
        rewrite(self.output, changed, 'ppt/slides/slide9.xml', lambda raw: raw.replace(b'x="100"', b'x="101"'))
        with self.assertRaisesRegex(SpecError, 'Protected'):
            validate_preservation(self.source, changed, [], self.plan['rewrites'])

    def test_numbers_protected_names_stale_before_and_control_chars_are_rejected(self):
        original = copy.deepcopy(self.plan)
        for value in ('日本語の改善率は11%', '英語の改善率は10%', '日本語10%\n補足'):
            self.plan = copy.deepcopy(original); self.plan['rewrites'][0]['edits'][0]['after'] = value
            with self.subTest(value=value), self.assertRaises(SpecError):
                self.check()
        self.plan = original; self.plan['rewrites'][0]['edits'][0]['before'] = 'stale'
        with self.assertRaisesRegex(SpecError, 'before'):
            self.check()

    def test_duplicate_run_and_field_or_table_rewrites_are_rejected(self):
        self.plan['rewrites'] *= 2
        with self.assertRaises(SpecError): self.check()
        self.plan['rewrites'] = self.plan['rewrites'][:1]
        self.plan['rewrites'][0]['shape_id'] = '6'
        with self.assertRaisesRegex(SpecError, 'editable'):
            self.check()

    def test_output_text_must_exactly_match_recorded_after(self):
        self.check(); write_candidate(self.source, self.output, self.plan)
        bad = self.base / 'bad.pptx'
        rewrite(self.output, bad, 'ppt/slides/slide9.xml', lambda raw: raw.replace('改善率'.encode(), '利益率'.encode()))
        with self.assertRaisesRegex(SpecError, 'differs'):
            validate_preservation(self.source, bad, [], self.plan['rewrites'])

    def test_explicit_mode_does_not_allow_plan_to_switch_modes(self):
        self.save()
        with self.assertRaisesRegex(SpecError, 'differs from plan'):
            apply(self.source, self.style, self.path, self.output, renderer='none', mode='1')

    def test_mode2_report_and_review_do_not_claim_meaning_is_automatically_approved(self):
        self.save(); apply(self.source, self.style, self.path, self.output, renderer='none')
        result = verify(self.output)
        self.assertEqual(result['mode'], 'style_and_text')
        self.assertEqual(result['semantic_preservation'], 'not_checked')
        report = (self.output.with_suffix('.preview') / 'restyle-report.md').read_text()
        self.assertIn('Clarify the existing label', report)

    def test_style_ledger_can_reference_a_writing_improvement(self):
        self.plan['requirements'][0].update(status='implemented', operations=['concise'])
        self.check()

    def test_meaning_and_rewrite_evidence_are_required_for_visual_approval(self):
        self.save()
        def fake_render(pptx, work, scene, renderer, runtime, pdf=False):
            folder = work / 'preview'; folder.mkdir(parents=True)
            for i in (1, 2):
                (folder / f'slide-{i:02d}.png').write_bytes(b'fixture only')
            return folder
        with patch('restyle_deck.renderer_runtime', return_value={}), patch('restyle_deck.render', side_effect=fake_render):
            apply(self.source, self.style, self.path, self.output, renderer='libreoffice')
        review = {'output_sha256': source_hash(self.output), 'source_sha256': source_hash(self.source),
            'reviewer': 'Schema fixture; no actual visual approval', 'unresolved_items': [],
            'pages': [{'id': str(i), **{d: {'status': 'passed', 'evidence': 'Fixture schema evidence'}
                      for d in ('content', 'meaning', 'layout', 'overflow', 'legibility', 'style')}} for i in (1, 2)],
            'requirements': [{'source': '/色', 'status': 'passed', 'evidence': 'Fixture exclusion evidence'}],
            'protection_evidence': 'Fixture protected-term review',
            'rewrites': [{'id': 'concise', 'status': 'passed', 'evidence': 'Fixture semantic evidence'}]}
        path = self.output.with_suffix('.preview') / 'review.json'; path.write_text(json.dumps(review))
        self.assertEqual(verify(self.output)['status'], 'passed_with_exclusions')
        review['rewrites'] = []; path.write_text(json.dumps(review))
        with self.assertRaisesRegex(SpecError, 'every rewrite'):
            verify(self.output)


@unittest.skipUnless(shutil.which('node') and (ROOT / 'skills/decksmith/node_modules/pptxgenjs').exists(), 'requires local JS engine')
class RedesignTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.source = make_native_fixture(self.base)
        self.style = self.base / 'style.yaml'; self.style.write_text('色: "#173F35"')
        self.project = self.base / 'redesign'
        self.plan, self.scene, self.content = make_redesign(self.project, self.source, self.style)
        self.output = self.base / 'result.pptx'

    def test_source_content_includes_chart_cache_table_and_notes(self):
        self.assertEqual(self.content['slides'], 2)
        self.assertTrue(any('指標' in i['text'] for i in self.content['items']))
        self.assertTrue(any('20' in i['text'] and i['kind'] == 'graphicFrame' for i in self.content['items']))
        self.assertTrue(any(i['kind'] == 'notes' for i in self.content['items']))

    def test_full_redesign_merges_pages_and_retains_editable_native_objects(self):
        original = self.source.read_bytes()
        result = apply(self.source, self.style, self.project / 'restyle-plan.yaml', self.output, renderer='none', mode='3')
        self.assertEqual(result['slides'], 1); self.assertEqual(result['source_slides'], 2)
        self.assertEqual(self.source.read_bytes(), original)
        _, parts, slides, _ = package(self.output)
        self.assertEqual(len([n for n in shapes(slides[0][1]).values() if n.localName == 'graphicFrame']), 2)
        for table in descendants(slides[0][1], A, 'tbl'):
            self.assertEqual(sum(int(c.getAttribute('w')) for c in descendants(table, A, 'gridCol')), 800 * 9525)
            self.assertEqual(sum(int(r.getAttribute('h')) for r in children(table, A, 'tr')), 440 * 9525)
        source_parts = package(self.source)[1]
        imported = {name: raw for name, raw in parts.items() if '/decksmith-import/' in name and name.endswith('.xlsx')}
        self.assertTrue(imported)
        for name, raw in imported.items():
            self.assertIn(raw, source_parts.values())
        self.assertEqual(verify(self.output)['mode'], 'redesign')

    def test_missing_mapping_native_rasterization_and_number_changes_are_rejected(self):
        for mutation in ('missing', 'native', 'number'):
            plan = copy.deepcopy(self.plan)
            if mutation == 'missing': plan['mapping'].pop()
            elif mutation == 'native':
                next(m for m in plan['mapping'] if m['status'] == 'native')['status'] = 'redesigned'
            else:
                next(m for m in plan['mapping'] if '10%' in m.get('after', ''))['after'] = '東京で2026年に11%改善を目指します。'
            (self.project / 'restyle-plan.yaml').write_text(json.dumps(plan))
            with self.subTest(mutation=mutation), self.assertRaises(SpecError):
                apply(self.source, self.style, self.project / 'restyle-plan.yaml', self.output, renderer='none')
            self.assertFalse(self.output.exists())

    def test_omitting_content_requires_approval_and_protected_terms_cannot_disappear(self):
        plan = copy.deepcopy(self.plan)
        entry = next(m for m in plan['mapping'] if m['classification'] == 'content')
        entry.update(status='omitted', targets=[], after='')
        (self.project / 'restyle-plan.yaml').write_text(json.dumps(plan))
        with self.assertRaisesRegex(SpecError, 'approval'):
            apply(self.source, self.style, self.project / 'restyle-plan.yaml', self.output, renderer='none')

    def test_redesign_numeric_guard_uses_original_not_rewritten_scene(self):
        scene = copy.deepcopy(self.scene)
        scene['slides'][0]['notes'] = '\n'.join(i['text'] for i in self.content['items'] if i['kind'] == 'notes')
        mapping = next(m for m in self.plan['mapping'] if '10%' in m.get('after', ''))
        mapping['after'] = mapping['after'].replace('10%', '11%')
        target = next(e for e in scene['slides'][0]['elements'] if 'combined/'+e['id'] == mapping['targets'][0])
        target['text'] = target['text'].replace('10%', '11%')
        with self.assertRaisesRegex(SpecError, 'numeric values changed'):
            validate_mapping(self.plan, self.content, scene)

    def test_visual_redesign_review_covers_both_original_pages_and_native_objects(self):
        def fake_render(pptx, work, scene, renderer, runtime, pdf=False):
            folder = work / 'preview'; folder.mkdir(parents=True)
            for i in range(1, len(scene['slides'])+1):
                (folder / f'slide-{i:02d}.png').write_bytes(b'schema fixture only')
            return folder
        with patch('redesign_deck.renderer_runtime', return_value={}), patch('restyle_deck.render', side_effect=fake_render):
            apply(self.source, self.style, self.project / 'restyle-plan.yaml', self.output, renderer='libreoffice')
        folder = self.output.with_suffix('.preview')
        checks = json.loads((folder / 'design-checks.json').read_text())
        review = {'output_sha256':source_hash(self.output),'source_sha256':source_hash(self.source),
            'reviewer':'Schema fixture only; no actual visual assertion','unresolved_items':[],
            'pages':[{'id':'combined',**{d:{'status':'passed','evidence':'Schema evidence'} for d in ('content','meaning','layout','overflow','legibility','style')}}],
            'mapping':[{'source_id':m['source_id'],'status':'passed','evidence':'Schema source coverage'} for m in self.plan['mapping']],
            'source_pages':[{'id':str(i),'status':'passed','evidence':'Schema original page coverage'} for i in (1,2)],
            'protection_evidence':'Schema protection evidence',
            'requirements':[{'source':'/色','status':'passed','evidence':'Schema style evidence'}],
            'warning_resolutions':{w['id']:'Schema warning resolution' for w in checks['warnings']}}
        path = folder / 'review.json'; path.write_text(json.dumps(review))
        self.assertEqual(verify(self.output)['status'], 'passed')
        review['source_pages'].pop(); path.write_text(json.dumps(review))
        with self.assertRaisesRegex(SpecError, 'original page coverage'):
            verify(self.output)

    def test_native_groups_keep_nested_objects_and_dependency_data(self):
        from pptx_restyle import element, parse
        grouped = self.base / 'grouped.pptx'
        def group(raw):
            doc = parse(raw)
            tree = first(first(doc.documentElement, P, 'cSld'), P, 'spTree')
            frames = children(tree, P, 'graphicFrame')
            grp = element(tree, P, 'grpSp')
            nv = element(grp, P, 'nvGrpSpPr'); identity = element(nv, P, 'cNvPr')
            identity.setAttribute('id', '999'); identity.setAttribute('name', 'Evidence group')
            nv.appendChild(identity); grp.appendChild(nv)
            prop = element(grp, P, 'grpSpPr'); xfrm = element(prop, A, 'xfrm'); prop.appendChild(xfrm); grp.appendChild(prop)
            for local, attrs in (('off', {'x':0,'y':0}), ('ext', {'cx':12192000,'cy':6858000}),
                                 ('chOff', {'x':0,'y':0}), ('chExt', {'cx':12192000,'cy':6858000})):
                node = element(xfrm, A, local)
                for key, value in attrs.items(): node.setAttribute(key, str(value))
                xfrm.appendChild(node)
            for frame in frames: grp.appendChild(frame)
            tree.appendChild(grp)
            return doc.toxml(encoding='utf-8')
        rewrite(self.source, grouped, 'ppt/slides/slide2.xml', group)
        project = self.base / 'group-redesign'; make_redesign(project, grouped, self.style)
        result = apply(grouped, self.style, project / 'restyle-plan.yaml', self.output, renderer='none')
        doc = package(self.output)[2][0][1]
        self.assertEqual(len(descendants(doc, P, 'grpSp')), 1)
        self.assertEqual(len(descendants(doc, P, 'graphicFrame')), 2)
        identities = [n.getAttribute('id') for n in descendants(doc, P, 'cNvPr')]
        self.assertEqual(len(identities), len(set(identities)))

    def test_source_relationship_namespace_prefixes_survive_import(self):
        from pptx_restyle import parse
        modified = self.base / 'prefixed.pptx'
        with ZipFile(self.source) as source, ZipFile(modified, 'w') as output:
            for name in source.namelist():
                raw = source.read(name)
                if name.endswith('.rels'):
                    raw = raw.replace(b'<Relationships ', b'<rel:Relationships ').replace(b'</Relationships>', b'</rel:Relationships>')
                    raw = raw.replace(b'<Relationship ', b'<rel:Relationship ')
                    raw = raw.replace(b'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"',
                                      b'xmlns:rel="http://schemas.openxmlformats.org/package/2006/relationships"')
                output.writestr(name, raw)
        project = self.base / 'prefix-redesign'; make_redesign(project, modified, self.style)
        apply(modified, self.style, project / 'restyle-plan.yaml', self.output, renderer='none')
        with ZipFile(self.output) as output:
            for name in output.namelist():
                if name.endswith('.rels'):
                    parse(output.read(name))

    @unittest.skipUnless(os.environ.get('DECKSMITH_RENDER_TEST') == '1', 'requires converters')
    def test_redesign_renders_native_chart_and_table_and_exports_pdf(self):
        config = self.base / 'export.yaml'; config.write_text('output:\n  renderer: libreoffice\n  pdf: true\n')
        result = apply(self.source, self.style, self.project / 'restyle-plan.yaml', self.output,
                       renderer='libreoffice', config_path=config)
        folder = self.output.with_suffix('.preview')
        self.assertEqual(result['status'], 'ready_for_visual_review')
        self.assertEqual(len(list(folder.glob('slide-*.png'))), 1)
        self.assertEqual(len(list((folder / 'source').glob('slide-*.png'))), 2)
        self.assertTrue(self.output.with_suffix('.pdf').read_bytes().startswith(b'%PDF-'))


if __name__ == '__main__':
    unittest.main()
