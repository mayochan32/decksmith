import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/decksmith/scripts'
sys.path.insert(0, str(SCRIPTS))
from compile_spec import source_hash, compile_scene, SpecError, load_mapping
from project_config import resolve_config
from project_init import initialize
from create_deck import next_output_path
from design_quality import check_plan, inspect_design
from review_deck import verify


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def write(self, name, data):
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')
        return path

    def test_template_contains_all_fields_and_defaults(self):
        baseline = resolve_config(base=self.base)
        path = initialize(self.base)
        result = resolve_config(path)
        for name in ('canvas','privacy','input','output','images','text','language'):
            self.assertEqual(result[name], baseline[name], name)
        data = load_mapping(path)
        self.assertEqual(set(data), {'slide','privacy','input','output','images','text','language'})
        expected = {'slide': 'width_px height_px aspect_ratio', 'privacy': 'mode',
                    'input': 'style brief', 'output': 'directory filename renderer pdf',
                    'images': 'mode amount type color plan', 'text': 'amount'}
        for key, fields in expected.items():
            self.assertEqual(set(data[key]), set(fields.split()))
        original = path.read_bytes()
        with self.assertRaises(FileExistsError):
            initialize(self.base, 'none')
        self.assertEqual(path.read_bytes(), original)

    def test_init_explicit_renderer(self):
        path = initialize(self.base, 'powerpoint')
        self.assertEqual(resolve_config(path)['output']['renderer'], 'powerpoint')

    def test_numbering_preserves_outputs_and_broken_links(self):
        output = self.base / '資料.pptx'
        output.write_bytes(b'original')
        (self.base / '資料-002.preview').mkdir()
        (self.base / '資料-003.pdf').symlink_to(self.base / 'missing')
        self.assertEqual(next_output_path(output).name, '資料-004.pptx')
        self.assertEqual(output.read_bytes(), b'original')

    def scene(self):
        style = self.write('style.yaml', {'自由指定': 'semantic focal point'})
        structure = self.write('structure.yaml', {'slides': [{'id':'s','required_text':['重要']} ]})
        return {'schema_version':'1.0', 'style_sha256':source_hash(style),
                'structure_sha256':source_hash(structure),'canvas':{'width':1920,'height':1080},
                'requirements':[{'source':'/自由指定','interpretation':'project-specific',
                                 'status':'implemented','targets':['s/t']}],
                'slides':[{'id':'s','background':'#FFFFFF','elements':[
                    {'id':'t','type':'text','text':'重要','role':'heading','font':'Arial',
                     'size':96,'tracking':-2,'color':'#000000','x':50,'y':50,'width':1000,'height':300}]}]}

    def compile(self, scene, draft=False):
        return compile_scene(self.write('scene.yaml',scene),self.base/'style.yaml',self.base/'structure.yaml',draft)

    def test_unavailable_asset_stays_unresolved(self):
        scene = self.scene()
        req = scene['requirements'][0]
        req.update(status='asset_pending',reason='No image provider available')
        with self.assertRaisesRegex(SpecError,'unresolved'):
            self.compile(scene)
        self.assertEqual(self.compile(scene,True)['requirements'][0]['status'],'asset_pending')
        req.update(status='not_applicable')
        with self.assertRaisesRegex(SpecError,'reason_kind'):
            self.compile(scene)
        req.update(reason_kind='user_excluded')
        with self.assertRaisesRegex(SpecError,'evidence'):
            self.compile(scene)
        req.update(approval='User explicitly requested no images in brief.md')
        self.compile(scene)

    def test_alternative_requires_user_approval(self):
        scene=self.scene()
        scene['requirements'][0].update(status='approved_alternative',reason='Alternative')
        with self.assertRaises(SpecError): self.compile(scene)
        scene['requirements'][0]['approval']='User approved replacement in message 3'
        self.compile(scene)

    def plan(self, scene):
        return {'style_sha256':scene['style_sha256'],'structure_sha256':scene['structure_sha256'],
                'signatures':[{'source':'/自由指定','intent':'Emphasize meaning','visual_check':'Check focal hierarchy'}],
                'font_evidence':'Fixture font; not a real visual review',
                'typography':{'heading':{'font':'Arial','min_size':96,'reason':'Fixture'}},
                'representative_slides':['s'],
                'slides':[{'id':'s','focal_element':'t','focal_reason':'Core concept',
                           'composition':'One dominant statement','asset_decision':'No image needed'}]}

    def test_plan_references_and_size_warnings(self):
        scene=self.scene(); plan=self.plan(scene)
        path=self.write('design-plan.yaml',plan)
        self.assertEqual(check_plan(path,scene),plan)
        self.assertEqual(inspect_design(scene,plan)['warnings'],[])
        scene['slides'][0]['elements'][0]['size']=20
        self.assertEqual(inspect_design(scene,plan)['warnings'][0]['id'],'s/t:role-size')
        plan['slides'][0]['focal_element']='not-found'
        with self.assertRaisesRegex(SpecError,'focal_element'):check_plan(self.write('design-plan.yaml',plan),scene)

    def fixture_review(self):
        output=self.base/'deck.pptx';output.write_bytes(b'fixture-not-a-pptx')
        preview=self.base/'deck.preview';preview.mkdir()
        (preview/'slide-01.png').write_bytes(b'fixture-not-a-png')
        self.write('deck.preview/design-plan.json',{})
        self.write('deck.preview/design-checks.json',{'warnings':[]})
        manifest={'status':'pending_visual_review','output_sha256':source_hash(output),
                  'preview_sha256':{'slide-01.png':source_hash(preview/'slide-01.png')},
                  'design_plan_sha256':source_hash(preview/'design-plan.json'),
                  'design_checks_sha256':source_hash(preview/'design-checks.json'),
                  'requirements':[{'source':'/free','status':'implemented'}],
                  'slides':[{'id':'s','preview':'slide-01.png'}]}
        self.write('deck.preview/review-manifest.json',manifest)
        evidence={'status':'passed','evidence':'Test fixture only, not a visual assessment'}
        review={'output_sha256':source_hash(output),'reviewer':'test','unresolved_items':[],
                'pages':[{'id':'s',**{k:copy.deepcopy(evidence) for k in ('content','legibility','style')}}],
                'requirements':[{'source':'/free',**evidence}]}
        self.write('deck.preview/review.json',review)
        return output,manifest,review

    def test_review_identity_and_separate_dimensions(self):
        output,manifest,review=self.fixture_review()
        self.assertEqual(verify(output)['status'],'passed')
        review['pages'][0]['style']['status']='failed'
        self.write('deck.preview/review.json',review)
        with self.assertRaisesRegex(SpecError,'Page review failed'):verify(output)
        review['pages'][0]['style']['status']='passed'
        self.write('deck.preview/review.json',review)
        output.write_bytes(b'resaved')
        with self.assertRaisesRegex(SpecError,'PPTX changed'):verify(output)

    def test_review_rejects_changed_png_and_draft(self):
        output,manifest,review=self.fixture_review()
        (output.with_suffix('.preview')/'slide-01.png').write_bytes(b'changed')
        with self.assertRaisesRegex(SpecError,'Preview changed'):verify(output)
        manifest['status']='draft';self.write('deck.preview/review-manifest.json',manifest)
        with self.assertRaisesRegex(SpecError,'Draft'):verify(output)

    def test_none_does_not_become_visual_approval(self):
        output,manifest,review=self.fixture_review()
        manifest['status']='not_visually_reviewed';self.write('deck.preview/review-manifest.json',manifest)
        self.assertEqual(verify(output)['style_review'],'not_checked')

    def test_approved_alternative_is_not_unqualified_pass(self):
        output,manifest,review=self.fixture_review()
        manifest['requirements'][0]['status']='approved_alternative'
        self.write('deck.preview/review-manifest.json',manifest)
        self.assertEqual(verify(output)['status'],'passed_with_approved_alternatives')

    def test_powershell_utf8_bom_review(self):
        output,manifest,review=self.fixture_review()
        (output.with_suffix('.preview')/'review.json').write_text(json.dumps(review),encoding='utf-8-sig')
        self.assertEqual(verify(output)['status'],'passed')

    def test_review_rejects_unresolved_and_modified_plan(self):
        output,manifest,review=self.fixture_review()
        review['unresolved_items']=['Missing photo']
        self.write('deck.preview/review.json',review)
        with self.assertRaisesRegex(SpecError,'Unresolved'):verify(output)
        review['unresolved_items']=[];self.write('deck.preview/review.json',review)
        self.write('deck.preview/design-plan.json',{'changed':True})
        with self.assertRaisesRegex(SpecError,'design plan'):verify(output)

    def test_unknown_style_names_do_not_select_layouts(self):
        for description in ('黒板に小さな注釈と巨大な問い', '赤い網点と厳密な左揃え', '未知の表現：右下の細い文字'):
            scene=self.scene()
            self.write('style.yaml',{'自由指定':description})
            scene['style_sha256']=source_hash(self.base/'style.yaml')
            scene['requirements'][0]['interpretation']=description
            result=self.compile(scene)
            self.assertEqual(result['slides'],scene['slides'] if 'notes' in scene['slides'][0] else
                             [{**scene['slides'][0], 'notes':''}])
