import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/decksmith/scripts'))
from line_conflicts import inspect_line_conflicts


def line(name, points, **extra):
    return dict(id=name, type='path', x=0, y=0, width=100, height=100,
                points=points, stroke='#182E3A', stroke_width=2, **extra)


class LineConflictTests(unittest.TestCase):
    def inspect(self, *elements):
        return inspect_line_conflicts({'id': 's', 'elements': list(elements)})

    def panel(self, **extra):
        return dict(id='cover', type='shape', geometry='rect', x=40, y=40, width=20, height=20, fill='#FFFFFF', **extra)

    def test_unrelated_lines_cross_without_mutating_geometry(self):
        elements = [line('a', [[0, 0], [100, 100]]), line('b', [[0, 100], [100, 0]])]
        before = copy.deepcopy(elements); warnings, records = self.inspect(*elements)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(records[0]['conflicts'], [{'kind': 'crossing', 'point': (50.0, 50.0)}])
        self.assertEqual(elements, before)

    def test_common_endpoints_are_allowed_but_t_junctions_are_reported(self):
        a = line('a', [[0, 50], [100, 50]])
        self.assertEqual(self.inspect(a, line('b', [[100, 50], [100, 90]]))[0], [])
        self.assertEqual(self.inspect(a, line('b', [[50, 50], [50, 90]]))[1][0]['conflicts'][0]['kind'], 'touch')

    def test_collinear_overlap_is_reported_but_disjoint_lines_are_not(self):
        a = line('a', [[0, 50], [100, 50]])
        self.assertEqual(self.inspect(a, line('b', [[20, 50], [80, 50]]))[1][0]['conflicts'][0]['points'], [(20.0, 50.0), (80.0, 50.0)])
        self.assertEqual(self.inspect(a, line('b', [[110, 50], [150, 50]]))[0], [])

    def test_zero_length_closed_and_invisible_paths_are_excluded(self):
        a = line('a', [[0, 50], [100, 50]])
        for b in (line('b', [[50, 50], [50, 50]]), line('b', [[50, 0], [50, 100]], closed=True)):
            self.assertEqual(self.inspect(a, b)[0], [])
        b = line('b', [[50, 0], [50, 100]]); b['stroke'] = '#12345600'
        self.assertEqual(self.inspect(a, b)[0], [])

    def test_rotation_uses_actual_transformed_segments(self):
        a = line('a', [[0, 50], [100, 50]])
        b = line('b', [[0, 50], [100, 50]], rotation=90)
        self.assertEqual(len(self.inspect(a, b)[0]), 1)

    def test_opaque_panel_above_either_line_hides_the_crossing(self):
        a, b = line('a', [[0, 50], [100, 50]]), line('b', [[50, 0], [50, 100]])
        self.assertEqual(self.inspect(a, self.panel(), b)[0], [])
        self.assertEqual(len(self.inspect(self.panel(), a, b)[0]), 1)
        panel = self.panel(); panel['fill'] = '#FFFFFF80'
        self.assertEqual(len(self.inspect(a, b, panel)[0]), 1)

    def test_partial_occlusion_keeps_both_visible_overlap_pieces(self):
        a, b = line('a', [[0, 50], [100, 50]]), line('b', [[20, 50], [80, 50]])
        conflicts = self.inspect(a, b, self.panel())[1][0]['conflicts']
        self.assertEqual(len(conflicts), 2)
        panel = self.panel(); panel.update(x=0, width=100)
        self.assertEqual(self.inspect(a, b, panel)[0], [])

    def test_native_opaque_table_hides_earlier_crossings(self):
        a, b = line('a', [[0, 50], [100, 50]]), line('b', [[50, 0], [50, 100]])
        table = dict(id='table', type='table', x=40, y=40, width=20, height=20)
        self.assertEqual(self.inspect(a, b, table)[0], [])

    def test_conflict_reaches_the_shared_design_report(self):
        from design_quality import inspect_design
        scene = {'canvas': {'width': 100, 'height': 100}, 'slides': [{'id': 's', 'elements': [
            line('a', [[0, 50], [100, 50]]), line('b', [[50, 0], [50, 100]])]}]}
        report = inspect_design(scene)
        self.assertIn('s/a+b:line-conflict', [w['id'] for w in report['warnings']])
        self.assertEqual(report['line_conflicts'][0]['lines'], ['a', 'b'])


if __name__ == '__main__':
    unittest.main()
