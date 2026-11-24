import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/decksmith/scripts'
sys.path.insert(0, str(SCRIPTS))
from compile_spec import compile_scene, source_hash, SpecError
from connector_routing import lower_connectors, rectangle, segment_crosses
from validate_pptx import validate_pptx


class ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='decksmith routes ')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)

    def write(self, name, value):
        path = self.base / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return path

    def elements(self):
        return [dict(id='flow', type='connector',
                     **{'from': dict(element='start', side='right'), 'to': dict(element='finish', side='left')},
                     stroke='#177E68', stroke_width=2, clearance=12,
                     label=dict(text='Complete fields', font='Arial', size=24, color='#19333A', width=180, height=36)),
                dict(id='start', type='shape', geometry='rect', x=80, y=240, width=180, height=100, fill='#FFFFFF'),
                dict(id='start-text', type='text', text='Submit', font='Arial', size=28, color='#19333A',
                     x=100, y=270, width=140, height=40),
                dict(id='finish', type='shape', geometry='rect', x=720, y=240, width=180, height=100, fill='#FFFFFF'),
                dict(id='finish-text', type='text', text='Receive', font='Arial', size=28, color='#19333A',
                     x=740, y=270, width=140, height=40),
                dict(id='explanation', type='text', text='Do not cross this explanation', font='Arial', size=24,
                     color='#19333A', x=400, y=245, width=160, height=90)]

    def compile(self, elements):
        style = self.write('style.yaml', {'accent': '#177E68'})
        structure = self.write('structure.yaml', {'slides': [dict(id='s', required_text=['Submit', 'Receive', 'Complete fields'])]})
        scene = dict(schema_version='1.0', canvas=dict(width=1000, height=600),
                     style_sha256=source_hash(style), structure_sha256=source_hash(structure),
                     requirements=[dict(source='/accent', interpretation='Connector ink', status='implemented', targets=['s/flow'])],
                     slides=[dict(id='s', background='#F6F7F4', elements=elements)])
        return compile_scene(self.write('scene.yaml', scene), style, structure)

    def test_route_preserves_explicit_endpoints_and_avoids_text(self):
        original = self.elements()
        before = copy.deepcopy(original)
        scene = self.compile(original)
        route = scene['connector_routes']['s'][0]
        self.assertEqual(route['points'][0], [260, 290])
        self.assertEqual(route['points'][-1], [720, 290])
        self.assertGreater(route['bends'], 0)
        obstacle = rectangle(original[-1])
        self.assertFalse(any(segment_crosses(a, b, obstacle) for a, b in zip(route['points'], route['points'][1:])))
        label = next(e for e in scene['slides'][0]['elements'] if e['id'] == 'flow__label')
        self.assertEqual(label['text'], 'Complete fields')
        self.assertEqual(label['size'], 24)
        self.assertEqual(original, before)

    def test_auto_ports_follow_changed_node_positions(self):
        elements = self.elements()
        elements[0]['from']['side'] = elements[0]['to']['side'] = 'auto'
        first = lower_connectors(elements, dict(width=1000, height=600))[1][0]
        elements[3].update(x=80, y=440)
        elements[4].update(x=100, y=470)
        second = lower_connectors(elements, dict(width=1000, height=600))[1][0]
        self.assertNotEqual(first['points'][-1], second['points'][-1])
        self.assertEqual(second['to'], 'finish')
        self.assertTrue(second['points'][-1][1] >= 440)

    def test_background_and_inner_labels_do_not_block_node_exits(self):
        elements = self.elements()
        elements.insert(0, dict(id='panel', type='shape', geometry='rect', x=30, y=180, width=920, height=200, fill='#FFFFFF'))
        scene = self.compile(elements)
        self.assertEqual(scene['connector_routes']['s'][0]['to'], 'finish')

    def test_missing_references_bad_labels_and_blocked_via_stop(self):
        edits = [lambda e: e[0]['to'].update(element='missing'),
                 lambda e: e[0]['from'].update(side='diagonal'),
                 lambda e: e[0]['from'].update(offset=1.1),
                 lambda e: e[0]['label'].update(x=300),
                 lambda e: e[0].update(avoid=['missing']),
                 lambda e: e[0].update(via=[[450, 270]]),
                 lambda e: e[0]['to'].update(element='start'),
                 lambda e: e[0]['label'].update(unknown=True),
                 lambda e: e.append(dict(e[2], id='flow__label'))]
        for edit in edits:
            elements = self.elements(); edit(elements)
            with self.subTest(edit=edit), self.assertRaises(SpecError):
                self.compile(elements)

    def test_facing_edges_align_without_resizing_nodes_and_explicit_offsets_are_preserved(self):
        elements = self.elements()[:-1]
        elements[3]['height'] = 140
        route = lower_connectors(elements, dict(width=1000, height=600))[1][0]
        self.assertEqual(route['points'], [[260, 300], [720, 300]])
        self.assertEqual((elements[1]['height'], elements[3]['height']), (100, 140))
        elements[0]['from']['offset'] = elements[0]['to']['offset'] = .5
        fixed = lower_connectors(elements, dict(width=1000, height=600))[1][0]
        self.assertEqual(fixed['points'][0], [260, 290])
        self.assertEqual(fixed['points'][-1], [720, 310])
        self.assertEqual((fixed['from_offset'], fixed['to_offset']), (.5, .5))

    def test_return_path_does_not_infer_or_change_relationships(self):
        elements = self.elements()
        elements[0].update(via=[[650, 500], [300, 500]])
        elements[0]['from'].update(element='finish', side='bottom')
        elements[0]['to'].update(element='start', side='bottom')
        route = self.compile(elements)['connector_routes']['s'][0]
        self.assertEqual((route['from'], route['to']), ('finish', 'start'))
        self.assertEqual(route['points'][0], [810, 340])
        self.assertEqual(route['points'][-1], [170, 340])
        self.assertTrue(any(point[1] == 500 for point in route['points']))

    def test_label_prefers_spacious_horizontal_segment_and_faces_its_line(self):
        elements = self.elements()
        elements[0].update(via=[[810, 500], [170, 500]])
        elements[0]['from'].update(element='finish', side='bottom')
        elements[0]['to'].update(element='start', side='bottom')
        elements[0]['label'].update(text='Return only if incomplete\nSpecify the missing fields', width=400, height=72)
        expanded = lower_connectors(elements, dict(width=1000, height=600))[0]
        label = next(e for e in expanded if e['id'] == 'flow__label')
        self.assertEqual(label['align'], 'center')
        self.assertEqual(label['vertical'], 'bottom')
        self.assertAlmostEqual(label['y'] + label['height'], 500 - 6.5)

    def test_vertical_label_uses_near_edge_alignment_unless_explicit(self):
        elements = self.elements()
        elements[1].update(x=200, y=60)
        elements[2].update(x=220, y=90)
        elements[3].update(x=200, y=450)
        elements[4].update(x=220, y=480)
        elements[0]['from']['side'] = 'bottom'
        elements[0]['to']['side'] = 'top'
        label = next(e for e in lower_connectors(elements, dict(width=1000, height=600))[0] if e['id'] == 'flow__label')
        self.assertEqual(label['align'], 'right')
        self.assertEqual(label['vertical'], 'middle')
        self.assertAlmostEqual(label['x'] + label['width'], 290 - 6.5)
        elements[0]['label'].update(align='center', vertical='top')
        explicit = next(e for e in lower_connectors(elements, dict(width=1000, height=600))[0] if e['id'] == 'flow__label')
        self.assertEqual((explicit['align'], explicit['vertical']), ('center', 'top'))

    @unittest.skipUnless(shutil.which('node') and (ROOT / 'skills/decksmith/node_modules/pptxgenjs').is_dir(), 'Local renderer dependencies')
    def test_native_route_points_and_arrow_mutations(self):
        scene = self.compile(self.elements())
        compiled = self.write('compiled.json', scene)
        output = self.base / 'route.pptx'
        env = dict(os.environ, DECKSMITH_NODE_MODULES=str(ROOT / 'skills/decksmith/node_modules'))
        subprocess.run(['node', str(SCRIPTS / 'build_deck.mjs'), '--spec', str(compiled), '--output', str(output)],
                       env=env, capture_output=True, text=True, check=True)
        self.assertEqual(validate_pptx(output, scene)['status'], 'passed')
        with ZipFile(output) as package:
            files = {name: package.read(name) for name in package.namelist()}
        ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
              'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}
        for change in ('point', 'arrow', 'closure', 'alignment'):
            root = ET.fromstring(files['ppt/slides/slide1.xml'])
            if change == 'point':
                node = root.find('.//a:custGeom/a:pathLst/a:path/a:lnTo/a:pt', ns)
                node.set('x', str(int(node.get('x')) + 100))
            elif change == 'arrow':
                root.find('.//a:tailEnd', ns).set('type', 'none')
            elif change == 'closure':
                ET.SubElement(root.find('.//a:custGeom/a:pathLst/a:path', ns), '{' + ns['a'] + '}close')
            else:
                root.find('.//p:txBody/a:p/a:pPr', ns).set('algn', 'r')
            altered = self.base / (change + '.pptx')
            with ZipFile(altered, 'w') as package:
                for name, data in files.items():
                    package.writestr(name, ET.tostring(root) if name == 'ppt/slides/slide1.xml' else data)
            with self.subTest(change=change), self.assertRaisesRegex(SpecError, 'native path points changed|native arrow changed|native path closure changed|text alignment changed'):
                validate_pptx(altered, scene)


if __name__ == '__main__':
    unittest.main()
