import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/decksmith/scripts'))
from compile_spec import SpecError
from layout_balance import check_balance_groups, inspect_balance
from design_quality import inspect_design


class BalanceTests(unittest.TestCase):
    def fixture(self):
        elements = []
        for i, x in enumerate((0, 180, 360)):
            elements += [dict(id=f's{i}', type='shape', x=x, y=0, width=200, height=100,
                              fill='#FFFFFF' if i == 0 else 'none'),
                         dict(id=f't{i}', type='text', x=x+20, y=25, width=160, height=50,
                              size=30, font='Arial', role='label')]
        slide = dict(id='slide', elements=elements)
        planned = dict(balance_groups=[dict(id='peers', reason='Equivalent labels; first item has intentional emphasis.',
                       members=[dict(shape=f's{i}', label=f't{i}') for i in (2, 0, 1)],
                       checks=dict(font_height_ratio=dict(min=.25, max=.35),
                                   text_box_center_y=dict(min=.48, max=.52), gap_x=dict(max_spread=0)))])
        return slide, planned

    def inspect(self, slide, plan):
        check_balance_groups(plan, slide)
        return inspect_balance(slide, plan)

    def test_overlap_and_different_fills_are_valid_and_not_mutated(self):
        s, p = self.fixture(); before = copy.deepcopy((s, p))
        warnings, measured = self.inspect(s, p)
        self.assertEqual(warnings, [])
        self.assertEqual(measured[-1]['values'], [-20, -20])
        self.assertEqual((s, p), before)

    def test_offset_and_small_label_warn_then_clear_after_repair(self):
        s, p = self.fixture(); label = s['elements'][3]
        label.update(y=10, size=12)
        warnings, _ = self.inspect(s, p)
        self.assertEqual({w['metric'] for w in warnings}, {'font_height_ratio', 'text_box_center_y'})
        label.update(y=25, size=30)
        self.assertEqual(self.inspect(s, p)[0], [])

    def test_relative_metrics_are_scale_invariant(self):
        s, p = self.fixture(); before = self.inspect(s, p)[1]
        for e in s['elements']:
            for key in ('x', 'y', 'width', 'height', 'size'):
                if key in e: e[key] *= 2
        after = self.inspect(s, p)[1]
        self.assertEqual(before[:2], after[:2])
        self.assertEqual(after[-1]['values'], [-40, -40])

    def test_rotation_is_unmeasured_not_approved(self):
        s, p = self.fixture(); s['elements'][0]['rotation'] = 15
        warnings, measured = self.inspect(s, p)
        self.assertTrue(warnings[0]['id'].endswith(':unmeasured'))
        self.assertEqual(measured[0]['status'], 'unmeasured')

    def test_unrelated_element_is_ignored_and_legacy_has_no_balance_findings(self):
        s, p = self.fixture()
        s['elements'].append(dict(id='unrelated', type='shape', x=0, y=0, width=900, height=900))
        self.assertEqual(self.inspect(s, p)[0], [])
        report = inspect_design(dict(canvas=dict(height=100), slides=[s]))
        self.assertEqual(report['balance_measurements'], [])
        self.assertEqual([w['id'] for w in report['warnings']], ['design-plan-missing'])

    def test_effective_run_size_is_measured(self):
        s, p = self.fixture(); s['elements'][1]['runs'] = [dict(text='a'), dict(text='b', size=45)]
        self.assertEqual(self.inspect(s, p)[0][0]['metric'], 'font_height_ratio')

    def test_invalid_declarations_fail(self):
        cases = [lambda g: g.update(checks={'overlap': {'max': 0}}),
                 lambda g: g['members'][0].update(label='missing'),
                 lambda g: g.update(members=g['members'][:1], checks={'gap_x': {'min': 0}}),
                 lambda g: g.update(checks={'font_size': {'min': 40, 'max': 20}}),
                 lambda g: g.update(checks={'font_size': {'max': float('nan')}}),
                 lambda g: g.update(checks={'font_size': {'max_spread': -1}}),
                 lambda g: g['members'].append(g['members'][0]),
                 lambda g: g.update(checks={'font_size': {}})]
        for change in cases:
            with self.subTest(change=change):
                s, p = self.fixture(); change(p['balance_groups'][0])
                with self.assertRaises(SpecError): self.inspect(s, p)

    def test_design_inspection_includes_balance_warnings(self):
        s, p = self.fixture(); s['elements'][1]['y'] = 0
        p['id'] = s['id']
        report = inspect_design(dict(canvas=dict(height=100), slides=[s]),
                                dict(typography={}, slides=[p]))
        self.assertEqual(report['warnings'][0]['id'], 'slide/balance/peers:text_box_center_y')
        self.assertEqual(len(report['balance_measurements']), 3)
