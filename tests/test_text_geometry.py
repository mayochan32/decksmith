import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/decksmith/scripts'))
from text_geometry import estimate, inspect_text_geometry, inspect_connector_labels


class TextGeometryTests(unittest.TestCase):
    def text(self, **values):
        return dict(id='label', type='text', text='OK', font='Arial', size=20, color='#19333A',
                    x=30, y=40, width=100, height=30, **values)

    def inspect(self, elements):
        return inspect_text_geometry(dict(id='s', elements=elements))[0]

    def test_cjk_automatic_orphan_is_detected_without_rewriting(self):
        element = self.text()
        element.update(text='六項目が揃ったら', size=28, width=28 * (len('六項目が揃ったら') - 1) + .1, height=100)
        before = copy.deepcopy(element)
        warnings = self.inspect([element])
        self.assertIn('s/label:orphan-line', [w['id'] for w in warnings])
        self.assertEqual(element, before)

    def test_explicit_line_break_is_preserved_and_not_called_automatic_orphan(self):
        element = self.text()
        element.update(text='六項目が揃った\nら', width=400, height=100)
        result = estimate(element)
        self.assertEqual(result['estimated_line_count'], 2)
        self.assertNotIn('s/label:orphan-line', [w['id'] for w in self.inspect([element])])

    def test_large_run_is_included_in_height_estimate(self):
        element = self.text()
        element.pop('text')
        element['runs'] = [dict(text='Important', size=80), dict(text=' condition', size=20)]
        element.update(width=800, height=40)
        self.assertIn('s/label:text-fit', [w['id'] for w in self.inspect([element])])

    def test_native_table_long_cell_is_measured_with_padding(self):
        table = dict(id='table:row', type='table', headers=['A', 'B'], rows=[['条件を省略せずに長い説明文を残す', 'OK']],
                     x=20, y=20, width=240, height=140, font='Arial', size=24, padding=12)
        warnings, measurements = inspect_text_geometry(dict(id='s', elements=[table]))
        self.assertIn('s/table:row:r1c0:text-fit', [w['id'] for w in warnings])
        self.assertEqual(len(measurements), 4)

    def line(self):
        return dict(id='line', type='path', x=0, y=50, width=120, height=.01,
                    points=[[0, 0], [120, 0]], closed=False, fill='none', stroke='#177E68', stroke_width=2)

    def test_line_crossing_visible_text_is_reported(self):
        warnings = self.inspect([self.line(), self.text()])
        self.assertIn('s/line:text-crossing:label', [w['id'] for w in warnings])

    def test_empty_part_of_text_box_is_not_treated_as_ink(self):
        line = self.line()
        line.update(x=90, width=25, points=[[0, 0], [25, 0]])
        self.assertFalse(any(':text-crossing:' in w['id'] for w in self.inspect([line, self.text()])))

    def test_opaque_label_panel_hides_earlier_line_but_not_later_line(self):
        panel = dict(id='panel', type='shape', geometry='rect', x=20, y=30, width=100, height=60, fill='#FFFFFF')
        self.assertFalse(any(':text-crossing:' in w['id'] for w in self.inspect([self.line(), panel, self.text()])))
        self.assertTrue(any(':text-crossing:' in w['id'] for w in self.inspect([panel, self.text(), self.line()])))

    def test_native_table_hides_line_below_its_opaque_cells(self):
        table = dict(id='table:row', type='table', headers=['AAA'], rows=[['BBB']],
                     x=0, y=0, width=120, height=120, font='Arial', size=24, padding=12)
        line = self.line(); line.update(y=30)
        self.assertFalse(any(':text-crossing:' in w['id'] for w in self.inspect([line, table])))
        self.assertTrue(any(':text-crossing:' in w['id'] for w in self.inspect([table, line])))

    def test_transparent_stroke_and_rotated_ink_are_not_claimed_visible_conflicts(self):
        line = self.line(); line['stroke'] = '#177E6800'
        self.assertFalse(any(':text-crossing:' in w['id'] for w in self.inspect([line, self.text()])))
        element = self.text(); element['rotation'] = 45
        self.assertFalse(any(':text-crossing:' in w['id'] for w in self.inspect([self.line(), element])))

    def test_connector_label_is_measured_by_ink_not_the_near_edge_of_an_empty_box(self):
        label = self.text()
        label.update(id='edge__label', x=90, y=300, width=500, height=100, align='left')
        slide = dict(id='s', elements=[label])
        routes = [dict(id='edge', label='edge__label', points=[[600, 200], [600, 600]])]
        warnings, measurements = inspect_connector_labels(slide, routes)
        self.assertEqual(warnings[0]['id'], 's/edge:detached-label')
        self.assertGreater(measurements[0]['estimated_ink_distance'], 400)
        label['align'] = 'right'
        warnings, measurements = inspect_connector_labels(slide, routes)
        self.assertEqual(warnings, [])
        self.assertAlmostEqual(measurements[0]['estimated_ink_distance'], 10)


if __name__ == '__main__':
    unittest.main()
