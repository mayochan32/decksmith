import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/decksmith/scripts'))
from text_visibility import inspect_text_visibility, ratio


class TextVisibilityTests(unittest.TestCase):
    def text(self, eid='label', **changes):
        value = dict(id=eid, type='text', text='ABCDEFGH', x=0, y=0, width=300, height=50,
                     font='Arial', size=20, color='#000000', role='body')
        value.update(changes); return value

    def panel(self, **changes):
        value = dict(id='panel', type='shape', geometry='rect', x=0, y=0, width=400, height=80,
                     fill='#FFFFFF', stroke='none', stroke_width=0)
        value.update(changes); return value

    def inspect(self, *elements):
        return inspect_text_visibility(dict(id='s', background='#FFFFFF', elements=list(elements)))

    def ids(self, *elements):
        return [w['id'] for w in self.inspect(*elements)[0]]

    def test_black_white_ratio_and_low_contrast_are_measured(self):
        self.assertAlmostEqual(ratio((0, 0, 0), (1, 1, 1)), 21)
        self.assertEqual(self.ids(self.text()), [])
        self.assertIn('s/label:low-contrast', self.ids(self.text(color='#FFFFFF')))

    def test_later_opaque_panel_reports_lost_text(self):
        self.assertIn('s/label:text-covered', self.ids(self.text(), self.panel()))
        self.assertNotIn('s/label:text-covered', self.ids(self.panel(), self.text()))
        measured = self.inspect(self.text(), self.panel())[1][0]
        self.assertEqual(measured['covered_fraction'], 1)

    def test_partial_covering_keeps_remaining_text_for_overlap_checks(self):
        warnings, measured = self.inspect(self.text(), self.panel(width=60))
        self.assertIn('s/label:text-covered', [w['id'] for w in warnings])
        self.assertGreater(measured[0]['covered_fraction'], .2)
        self.assertLess(measured[0]['covered_fraction'], 1)

    def test_visible_text_collisions_reach_report(self):
        self.assertIn('s/a+b:text-overlap', self.ids(self.text('a'), self.text('b', y=8)))

    def test_empty_box_space_is_not_treated_as_text(self):
        self.assertFalse(any(':text-overlap' in v for v in self.ids(
            self.text('a', text='OK'), self.text('b', text='NO', x=100))))

    def test_hidden_old_label_does_not_create_a_false_collision_with_new_label(self):
        ids = self.ids(self.text('old'), self.panel(), self.text('new'))
        self.assertIn('s/old:text-covered', ids)
        self.assertNotIn('s/old+new:text-overlap', ids)

    def test_table_cell_colour_and_fill_overrides_are_used(self):
        table = dict(id='table', type='table', x=0, y=100, width=400, height=160,
            headers=['HEADER'], rows=[['OPEN']], font='Arial', size=24, color='#000000',
            header_color='#FFFFFF', header_fill='#182E3A', fill='#FFFFFF',
            highlights=[dict(row=1, column=0, color='#FFFFFF')])
        ids = self.ids(table)
        self.assertIn('s/table:r1c0:low-contrast', ids)
        self.assertNotIn('s/table:r0c0:low-contrast', ids)

    def test_image_background_is_unmeasured_until_opaque_panel_replaces_it(self):
        image = dict(id='photo', type='image', x=0, y=0, width=400, height=80)
        warnings, measured = self.inspect(image, self.text())
        self.assertEqual(warnings, [])
        self.assertEqual(measured[0]['status'], 'unmeasured')
        warnings, measured = self.inspect(image, self.panel(), self.text())
        self.assertEqual(warnings, [])
        self.assertEqual(measured[0]['status'], 'measured_flat_fills')

    def test_image_above_text_requires_visibility_review(self):
        image = dict(id='photo', type='image', x=0, y=0, width=400, height=80)
        self.assertIn('s/label:occlusion-unmeasured', self.ids(self.text(), image))

    def test_transparent_ink_is_not_counted_as_visible_text(self):
        ids = self.ids(self.text('hidden', color='#FFFFFF00'), self.text('visible'))
        self.assertIn('s/hidden:transparent-text', ids)
        self.assertNotIn('s/hidden+visible:text-overlap', ids)

    def test_alpha_panel_below_text_is_composited_and_above_is_unmeasured(self):
        panel = self.panel(fill='#00000080')
        ids = self.ids(panel, self.text(color='#FFFFFF'))
        self.assertIn('s/label:low-contrast', ids)
        ids = self.ids(self.text(), panel)
        self.assertIn('s/label:occlusion-unmeasured', ids)
        self.assertNotIn('s/label:text-covered', ids)

    def test_mixed_colour_runs_over_multiple_backgrounds_are_not_guessed(self):
        e = self.text(); e.pop('text')
        e['runs'] = [dict(text='ABCD', color='#FFFFFF'), dict(text='EFGH', color='#000000')]
        warnings, measured = self.inspect(self.panel(fill='#000000', width=50), e)
        self.assertEqual(warnings, [])
        self.assertTrue(measured[0]['unknown_background'])
        self.assertEqual(measured[0]['contrast'], [])

    def test_rotated_text_does_not_receive_a_false_visibility_approval(self):
        warnings, measured = self.inspect(self.text(rotation=30))
        self.assertEqual(warnings, [])
        self.assertEqual(measured[0]['status'], 'unmeasured')

    def test_chart_text_colour_is_checked_without_claiming_label_positions(self):
        chart = dict(id='chart', type='chart', x=0, y=0, width=100, height=100, size=32,
                     color='#FFFFFF', fill='#FFFFFF')
        self.assertIn('s/chart:low-contrast', self.ids(chart))
        self.assertEqual(self.inspect(chart)[1][0]['status'], 'chart_colour_only')

    def test_analysis_never_changes_source_content_or_layout(self):
        elements = [self.text('a'), self.text('b', y=8), self.panel(width=20)]
        before = copy.deepcopy(elements); self.inspect(*elements)
        self.assertEqual(elements, before)

    def test_shared_design_report_includes_visibility_warning(self):
        from design_quality import inspect_design
        scene = dict(canvas=dict(width=1600, height=900), slides=[dict(id='s', background='#FFFFFF', elements=[self.text(color='#FFFFFF')])])
        report = inspect_design(scene)
        self.assertIn('s/label:low-contrast', [w['id'] for w in report['warnings']])
        self.assertTrue(report['text_visibility'])

    def test_radius_alias_is_not_assumed_to_be_a_fully_opaque_rectangle(self):
        panel = self.panel(radius=20)
        ids = self.ids(self.text(), panel)
        self.assertIn('s/label:occlusion-unmeasured', ids)
        self.assertNotIn('s/label:text-covered', ids)
        _, measured = self.inspect(panel, self.text())
        self.assertEqual(measured[0]['status'], 'unmeasured')
        panel.update(geometry='roundRect', radius=0)
        self.assertIn('s/label:text-covered', self.ids(self.text(), panel))


if __name__ == '__main__':
    unittest.main()
