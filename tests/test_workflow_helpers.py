import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/decksmith/scripts'))
from compile_spec import SpecError,load_mapping,source_hash
from project_config import resolve_config
from workflow import prepare,policy_record,announce,freeze,check_content,prototype,compare
import test_design_workflow as design_fixtures
from test_portable_runtime import launcher
import argparse


class Helpers(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)

    def write(self,name,data):
        p=self.p/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(data),encoding='utf-8');return p

    def prepared(self,mode='restricted',images=None):
        self.write('decksmith.yaml',{'privacy':{'mode':mode},'images':images or {}})
        prepare(self.p)
        cfg=resolve_config(self.p/'decksmith.resolved.yaml')
        return cfg,load_mapping(self.p/'decksmith.resolved.policy.json')

    def test_default_normal_and_image_modes(self):
        result=prepare(self.p,capability='unavailable')
        self.assertIn('利用不可',result['notice'])
        self.assertEqual(load_mapping(result['settings'])['privacy']['mode'],'restricted')
        record=load_mapping(result['policy_record'])
        self.assertEqual(record['policy']['mode_source'],'default')
        self.assertEqual(record['approvals'],[])
        with self.assertRaises(SpecError):prepare(self.p)
        path=self.write('normal.yaml',{'privacy':{'mode':'normal'},'images':{'mode':'provided_only'}})
        config=resolve_config(path)
        self.assertEqual(config['privacy']['mode'],'normal')
        self.assertEqual(config['communication_policy']['web_search'],'human_approval_required')
        self.assertIn('使用しない',announce(config))

    def test_setting_and_output_are_siblings_after_init_and_prepare(self):
        from project_init import initialize
        setting = self.p / 'my-presentations' / 'setting'
        config_path = initialize(setting, 'none')
        expected = str((setting.parent / 'output').resolve())
        self.assertEqual(resolve_config(config_path)['output']['directory'], expected)
        result = prepare(setting, capability='unavailable')
        self.assertEqual(resolve_config(result['settings'])['output']['directory'], expected)
        args = argparse.Namespace(action='build', project=setting, renderer=None,
                                  config=Path('decksmith.resolved.yaml'))
        cmd, _ = launcher.command(Path('/bundle'), args)
        self.assertEqual(cmd[cmd.index('--output') + 1], str(Path(expected) / 'deck.pptx'))
        args.action = 'review'
        args.output = Path('../output/deck.pptx')
        cmd, _ = launcher.command(Path('/bundle'), args)
        self.assertEqual(cmd[cmd.index('--output') + 1], str(Path(expected) / 'deck.pptx'))

    def test_external_use_requires_prior_scoped_approval_both_modes(self):
        cfg,r=self.prepared()
        usage={'kind':'web_search','approval_id':'a','purpose':'check','destination':'search engine','data':'public query','used_at':'2026-09-28T11:00:00+09:00'}
        r['usage']=[usage]
        def verify():
            self.write('decksmith.resolved.policy.json',r);return policy_record(cfg)
        with self.assertRaisesRegex(SpecError,'lacks human'):verify()
        r['approvals']=[{'id':'a','purpose':'check','destination':'search engine','data':'public query',
            'human_evidence':'user message 3','approved_at':'2026-09-28T10:00:00+09:00'}]
        with self.assertRaisesRegex(SpecError,'explicit exception'):verify()
        r['approvals'][0]['restricted_exception']=True
        self.assertEqual(verify()['usage'],[usage])
        r['usage'][0]['data']='private brief'
        with self.assertRaisesRegex(SpecError,'scope'):verify()
        r['usage'][0]['data']='public query'
        r['approvals'][0]['approved_at']='2026-09-28T12:00:00+09:00'
        with self.assertRaisesRegex(SpecError,'precede'):verify()
        normal=self.write('normal.yaml',{'privacy':{'mode':'normal'}})
        cfg=resolve_config(normal);r['resolved_sha256']=source_hash(normal);r['policy']=cfg['communication_policy'];r['approvals']=[]
        self.write('normal.policy.json',r)
        with self.assertRaisesRegex(SpecError,'lacks human'):policy_record(cfg)

    def test_changed_settings_and_disabled_generation(self):
        cfg,r=self.prepared(images={'mode':'provided_only'})
        r['usage']=[{'kind':'host_image_generation'}]
        self.write('decksmith.resolved.policy.json',r)
        with self.assertRaisesRegex(SpecError,'disabled'):policy_record(cfg)
        self.write('decksmith.resolved.yaml',{'privacy':{'mode':'normal'}})
        with self.assertRaisesRegex(SpecError,'different resolved'):policy_record(resolve_config(self.p/'decksmith.resolved.yaml'))

    def test_fallback_requires_choice_evidence_and_editable_prompt(self):
        cfg,r=self.prepared()
        r['image_fallbacks']=[{'choice':'placeholder','reason':'quota','slides':['s']}]
        def verify(scene=None):
            self.write('decksmith.resolved.policy.json',r);return policy_record(cfg,scene)
        with self.assertRaises(SpecError):verify()
        r['image_fallbacks'][0].update(human_evidence='user selected option 2',prompt='space photo',box='s/b',text='s/t')
        scene={'slides':[{'id':'s','elements':[{'id':'b','type':'shape','geometry':'rect','x':0,'y':0,'width':500,'height':200},
            {'id':'t','type':'text','text':'space photo','x':10,'y':10,'width':450,'height':180}]}]}
        self.assertEqual(verify(scene)['image_fallbacks'][0]['choice'],'placeholder')
        scene['slides'][0]['elements'][1]['text']='missing'
        with self.assertRaisesRegex(SpecError,'not retained'):verify(scene)
        r['image_fallbacks'][0]={'choice':'omit','reason':'quota','slides':['s'],'human_evidence':'user selected option 1'}
        verify(scene)

    def test_independent_baseline_detects_circular_structure_rewrite(self):
        (self.p/'brief.md').write_text('Keep conditions',encoding='utf-8')
        self.write('structure.yaml',{'slides':[{'id':'s','required_text':['0.8c','10 years']}]})
        freeze(self.p)
        scene={'slides':[{'id':'s','elements':[{'type':'text','text':'0.8c 10 years'}]}]}
        self.assertIsNotNone(check_content(self.p,scene))
        self.write('structure.yaml',{'slides':[{'id':'s','required_text':['10 years']}]})
        scene['slides'][0]['elements'][0]['text']='10 years'
        with self.assertRaisesRegex(SpecError,'independent content'):check_content(self.p,scene)
        with self.assertRaises(FileExistsError):freeze(self.p)
        self.write('content-changes.json',{'changes':[{'slide':'s','original':'0.8c','replacement':'80% light speed','reason':'reader-friendly wording','source_evidence':'brief condition'}]})
        scene['slides'][0]['elements'][0]['text']='80% light speed 10 years'
        check_content(self.p,scene)
        (self.p/'brief.md').write_text('Changed source',encoding='utf-8')
        with self.assertRaisesRegex(SpecError,'Brief changed'):check_content(self.p,scene)

    def test_prototype_preserves_source_and_selects_existing_slides(self):
        fixture=design_fixtures.WorkflowTests();fixture.base=self.p
        scene=fixture.scene();self.write('scene.yaml',scene);self.write('design-plan.yaml',fixture.plan(scene))
        before=source_hash(self.p/'scene.yaml')
        result=prototype(self.p,self.p/'prototype',['s'])
        self.assertTrue(result['draft_required'])
        self.assertEqual(source_hash(self.p/'scene.yaml'),before)
        self.assertEqual(load_mapping(self.p/'prototype/design-plan.yaml')['structure_sha256'],source_hash(self.p/'prototype/structure.yaml'))
        with self.assertRaisesRegex(SpecError,'already exists'):prototype(self.p,self.p/'prototype',['s'])
        with self.assertRaisesRegex(SpecError,'existing slide'):prototype(self.p,self.p/'bad',['missing'])

    def test_review_records_and_placeholder_status(self):
        fixture=design_fixtures.WorkflowTests();fixture.base=self.p
        output,manifest,review=fixture.fixture_review()
        from review_deck import verify
        self.write('deck.preview/content-check.json',{'baseline':'test'})
        manifest['workflow_records']={'content-check.json':source_hash(self.p/'deck.preview/content-check.json')}
        manifest['delivery_status']='awaiting_images'
        self.write('deck.preview/review-manifest.json',manifest)
        with self.assertRaisesRegex(SpecError,'independent'):verify(output)
        review['source_content_evidence']='Compared baseline and source'
        self.write('deck.preview/review.json',review)
        with self.assertRaisesRegex(SpecError,'awaiting_images'):verify(output)
        review['delivery_status']='awaiting_images';self.write('deck.preview/review.json',review)
        self.assertEqual(verify(output)['status'],'awaiting_images')
        self.assertEqual(compare(output,output)['unchanged'],['s'])
        (self.p/'deck.preview/slide-01.png').write_bytes(b'changed')
        with self.assertRaisesRegex(SpecError,'Preview changed'):compare(output,output)

    def test_portable_routes_new_commands_without_host_runtime(self):
        for action in ('prepare','freeze-content','prototype','compare'):
            args=argparse.Namespace(action=action,project=self.p,renderer=None)
            cmd,cwd=launcher.command(Path('/bundle'),args)
            self.assertIn('/bundle/runtime/python/python.exe',cmd)
            self.assertIn('/bundle/skills/decksmith/scripts/workflow.py',cmd)
            self.assertIn(action,cmd)
