import copy
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT/'skills/decksmith/scripts'
sys.path.insert(0,str(SCRIPTS))
from compile_spec import compile_scene, source_hash, SpecError, text_content, chart_value, evidence_data
from workflow import freeze, check_content
from validate_pptx import validate_pptx
from evidence_workbook import normalize_chart_workbooks


class EvidenceFixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)

    def write(self,name,data):
        path=self.p/name;path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8');return path

    def table(self):
        return dict(id='e',type='table',x=50,y=100,width=1180,height=560,
            headers=['条件','現行','試行案'],rows=[[f'条件{i}',f'既存{i}',f'提案{i}'] for i in range(1,7)],
            font='Arial',size=28,color='#222222',role='body',padding=8,
            column_widths=[300,440,440],row_heights=[80]*7,header_fill='#224466',header_color='#FFFFFF')

    def chart(self,kind='bar'):
        return dict(id='e',type='chart',chart_type=kind,x=50,y=100,width=1180,height=560,
            categories=['開場時','昼','終了前'],series=[dict(name='現行',values=[12,8,5]),dict(name='試行',values=[7,5,4])],
            unit='分',font='Arial',size=28,color='#222222',role='label',colors=['#566677','#BB3322'],number_format='0')

    def scene(self,element,required=None):
        style=self.write('style.yaml',{'色':'#BB3322'})
        structure=self.write('structure.yaml',{'slides':[dict(id='s',required_text=required or ['条件6'],
            evidence=[{'id':element['id'],**copy.deepcopy(evidence_data(element))}])]})
        scene=dict(schema_version='1.0',canvas=dict(width=1280,height=720),
            style_sha256=source_hash(style),structure_sha256=source_hash(structure),
            requirements=[dict(source='/色',interpretation='Fixture',status='implemented',targets=['s/e'])],
            slides=[dict(id='s',background='#FFFFFF',elements=[element])])
        self.write('scene.yaml',scene)
        return scene

    def compile(self,scene):
        return compile_scene(self.write('scene.yaml',scene),self.p/'style.yaml',self.p/'structure.yaml')


class EvidenceSpecTests(EvidenceFixture):
    def test_table_sixth_row_is_editable_content_and_input_is_not_mutated(self):
        scene=self.scene(self.table());before=copy.deepcopy(scene)
        result=self.compile(scene)
        self.assertIn('条件6',text_content(result['slides'][0]['elements'][0]))
        self.assertEqual(scene,before)
        scene['slides'][0]['elements'][0]['rows'].pop()
        scene['slides'][0]['elements'][0].pop('row_heights')
        with self.assertRaisesRegex(SpecError,'missing editable content'):self.compile(scene)

    def test_table_requires_all_columns_and_explicit_string_cells(self):
        for row in (['a','b'],['a','b','c','d'],['a',12,'c']):
            scene=self.scene(self.table());scene['slides'][0]['elements'][0]['rows'][0]=row
            with self.subTest(row=row),self.assertRaisesRegex(SpecError,'one string per header'):self.compile(scene)

    def test_table_dimensions_and_cell_highlight_references_are_checked(self):
        scene=self.scene(self.table());e=scene['slides'][0]['elements'][0]
        for field,value in (('column_widths',[10,10,10]),('row_heights',[80,80]),
                            ('highlights',[dict(row=7,column=0,fill='#FFFFFF')]),
                            ('highlights',[dict(row=True,column=0,fill='#FFFFFF')]),
                            ('highlights',[dict(row=0,column=0),dict(row=0,column=0)])):
            original=copy.deepcopy(e);e[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(SpecError):self.compile(scene)
            e.clear();e.update(original)
        e['highlights']=[dict(row=6,column=2,fill='#F0EEDD',bold=True)]
        self.compile(scene)

    def test_chart_preserves_categories_series_values_and_units(self):
        for kind in ('bar','column','line'):
            element=self.chart(kind);scene=self.scene(element,['開場時','終了前','分','12','7','試行'])
            result=self.compile(scene)['slides'][0]['elements'][0]
            self.assertEqual(result,element)

    def test_table_border_mode_is_explicit_and_rejects_unknown_modes(self):
        for mode in ('all', 'horizontal', 'none'):
            element=self.table();element['border_mode']=mode
            self.assertEqual(self.compile(self.scene(element))['slides'][0]['elements'][0]['border_mode'],mode)
        for mode in ('diagonal', None, True):
            element=self.table();element['border_mode']=mode
            with self.subTest(mode=mode),self.assertRaisesRegex(SpecError,'border_mode'):self.compile(self.scene(element))

    def test_point_emphasis_is_explicit_and_does_not_change_source_data(self):
        element = self.chart('column'); baseline = copy.deepcopy(evidence_data(element))
        element['highlights'] = [dict(series=0, category=1, color='#224466'), dict(series=1, category=1, color='#C9703A')]
        result = self.compile(self.scene(element, ['分']))['slides'][0]['elements'][0]
        self.assertEqual(evidence_data(result), baseline)
        for highlights in ([dict(series=True, category=1, color='#224466')],
                           [dict(series=2, category=1, color='#224466')],
                           [dict(series=0, category=3, color='#224466')],
                           [dict(series=0, category=1)],
                           [dict(series=0, category=1, color='#224466')] * 2):
            invalid = copy.deepcopy(element); invalid['highlights'] = highlights
            with self.subTest(highlights=highlights), self.assertRaises(SpecError):
                self.compile(self.scene(invalid, ['分']))
        element['chart_type'] = 'line'
        with self.assertRaisesRegex(SpecError, 'require bar or column'):
            self.compile(self.scene(element, ['分']))

    def test_chart_incomplete_or_nonfinite_data_is_rejected(self):
        for values in ([12,8],[12,8,True],[12,8,float('nan')],[12,8,float('inf')],[12,8,9007199254740993]):
            scene=self.scene(self.chart(),['分']);scene['slides'][0]['elements'][0]['series'][0]['values']=values
            with self.subTest(values=values),self.assertRaises(SpecError):self.compile(scene)

    def test_chart_rejects_clipping_and_truncated_bar_axes(self):
        for options in (dict(axis_min=5),dict(axis_max=10),dict(axis_step=0),dict(axis_min=0,axis_max=0)):
            scene=self.scene(self.chart(),['分']);scene['slides'][0]['elements'][0].update(options)
            with self.subTest(options=options),self.assertRaises(SpecError):self.compile(scene)
        scene=self.scene(self.chart('line'),['分'])
        scene['slides'][0]['elements'][0].update(axis_min=3,axis_max=13)
        self.compile(scene)

    def test_hidden_values_and_legend_do_not_satisfy_visible_text_requirements(self):
        scene=self.scene(self.chart(),['12']);scene['slides'][0]['elements'][0]['show_values']=False
        with self.assertRaisesRegex(SpecError,'missing editable content'):self.compile(scene)
        scene=self.scene(self.chart(),['現行']);scene['slides'][0]['elements'][0]['show_legend']=False
        with self.assertRaisesRegex(SpecError,'missing editable content'):self.compile(scene)

    def test_percentage_precision_and_large_finite_numbers(self):
        self.assertEqual(chart_value(0.1235,'0.0%'),'12.4%')
        self.assertEqual(chart_value(1234.5,'#,##0.0'),'1,234.5')
        self.assertTrue(chart_value(1e100,'0').startswith('100000'))
        scene=self.scene(self.chart(),['12.4%'])
        scene['slides'][0]['elements'][0].update(number_format='0.0%')
        scene['slides'][0]['elements'][0]['series'][0]['values'][0]=0.1235
        structure=json.loads((self.p/'structure.yaml').read_text())
        structure['slides'][0]['evidence'][0]['series'][0]['values'][0]=0.1235
        scene['structure_sha256']=source_hash(self.write('structure.yaml',structure))
        self.compile(scene)

    def test_independent_content_baseline_also_checks_native_evidence(self):
        scene=self.scene(self.chart(),['12','分']);compiled=self.compile(scene)
        (self.p/'brief.md').write_text('12分という値と単位を保持',encoding='utf-8');freeze(self.p)
        check_content(self.p,compiled)
        compiled['slides'][0]['elements'][0]['series'][0]['values'][0]=99
        with self.assertRaisesRegex(SpecError,'independent content'):check_content(self.p,compiled)

    def test_native_evidence_rejects_unsupported_options_and_rotation(self):
        for change in (dict(rotation=10),dict(chart_type='pie'),dict(number_format='arbitrary'),dict(colors=['#FFFFFF'])):
            scene=self.scene(self.chart(),['分']);scene['slides'][0]['elements'][0].update(change)
            with self.subTest(change=change),self.assertRaises(SpecError):self.compile(scene)

    def test_rounded_display_cannot_hide_a_source_data_change(self):
        e=self.chart();e['series'][0]['values'][0]=0.12341;e['number_format']='0.0%'
        scene=self.scene(e,['12.3%']);compiled=self.compile(scene)
        (self.p/'brief.md').write_text('原データは0.12341',encoding='utf-8');freeze(self.p)
        compiled['slides'][0]['elements'][0]['series'][0]['values'][0]=0.12349
        self.assertIn('12.3%',text_content(compiled['slides'][0]['elements'][0]))
        with self.assertRaisesRegex(SpecError,'independent source data'):check_content(self.p,compiled)

    def test_native_object_cannot_claim_unknown_or_omitted_source_data(self):
        scene=self.scene(self.table());scene['slides'][0]['elements'][0]['evidence_id']='unknown'
        with self.assertRaisesRegex(SpecError,'independent source data'):self.compile(scene)
        scene=self.scene(self.table());scene['slides'][0]['elements'][0]['rows'][0][1]='changed'
        with self.assertRaisesRegex(SpecError,'independent source data'):self.compile(scene)


@unittest.skipUnless(os.environ.get('DECKSMITH_RENDER_TEST')=='1','requires presentation runtime')
class EvidenceRenderTests(EvidenceFixture):
    def build(self,element,required):
        scene=self.compile(self.scene(element,required))
        spec=self.write('compiled.json',scene);output=self.p/'native.pptx'
        result=subprocess.run([os.environ.get('DECKSMITH_NODE') or shutil.which('node'),str(SCRIPTS/'build_deck.mjs'),
            '--spec',str(spec),'--output',str(output)],capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        normalize_chart_workbooks(output,scene)
        validate_pptx(output,scene)
        return output,scene

    def rewrite(self,path,member,change):
        with ZipFile(path) as z:files={n:z.read(n) for n in z.namelist()}
        files[member]=change(files[member])
        with ZipFile(path,'w',compression=ZIP_DEFLATED) as z:
            for name,value in files.items():z.writestr(name,value)

    def test_all_chart_types_are_native_and_have_editable_workbooks(self):
        for kind in ('bar','column','line'):
            with self.subTest(kind=kind):
                output,scene=self.build(self.chart(kind),['分','12'])
                with ZipFile(output) as z:
                    self.assertIn('ppt/charts/chart1.xml',z.namelist())
                    self.assertTrue(any(n.endswith('.xlsx') for n in z.namelist()))
                    self.assertFalse(any(n.startswith('ppt/media/') and not n.endswith('/') for n in z.namelist()))

    def test_table_keeps_six_rows_and_empty_cells_and_rejects_cell_mutation(self):
        table=self.table();table['rows'][3][1]=''
        output,scene=self.build(table,['条件6'])
        def mutate(raw):
            root=ET.fromstring(raw);ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
            root.findall('.//a:tbl/a:tr',ns)[-1].find('.//a:t',ns).text='changed'
            return ET.tostring(root)
        self.rewrite(output,'ppt/slides/slide1.xml',mutate)
        with self.assertRaisesRegex(SpecError,'cell content changed'):validate_pptx(output,scene)

    def test_table_borders_are_native_cell_properties_with_no_line_overlays(self):
        ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
        for mode,sides in [('all',{'lnT','lnR','lnB','lnL'}),('horizontal',{'lnT','lnB'}),('none',set())]:
            with self.subTest(mode=mode):
                element=self.table();element.update(border_mode=mode,border_width=1.6,border_color='#4A6070')
                output,scene=self.build(element,['条件6'])
                with ZipFile(output) as z:root=ET.fromstring(z.read('ppt/slides/slide1.xml'))
                self.assertEqual(root.findall('.//p:sp',ns),[])
                cells=root.findall('.//a:tbl/a:tr/a:tc',ns);self.assertEqual(len(cells),21)
                for cell in cells:
                    visible={side for side in ('lnT','lnR','lnB','lnL') if cell.find('a:tcPr/a:'+side+'/a:solidFill',ns) is not None}
                    self.assertEqual(visible,sides)

    def test_native_table_border_mutation_is_detected_without_changing_cell_data(self):
        element=self.table();element.update(border_mode='horizontal')
        output,scene=self.build(element,['条件6'])
        def mutate(raw):
            root=ET.fromstring(raw);ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
            row=root.find('.//a:tbl/a:tr',ns);row.find('a:tc/a:tcPr/a:lnL',ns).set('w','9525')
            line=row.find('a:tc/a:tcPr/a:lnL',ns);line.remove(line.find('a:noFill',ns))
            fill=ET.SubElement(line,'{'+ns['a']+'}solidFill');ET.SubElement(fill,'{'+ns['a']+'}srgbClr',{'val':'222222'})
            return ET.tostring(root)
        self.rewrite(output,'ppt/slides/slide1.xml',mutate)
        with self.assertRaisesRegex(SpecError,'borders changed'):validate_pptx(output,scene)

    def test_point_emphasis_is_native_with_multiple_series_and_zeros(self):
        ns = {'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart',
              'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
        for kind in ('bar', 'column'):
            element = self.chart(kind)
            element['series'][0]['values'] = [-2, 0, 5]
            element['series'][1]['values'] = [-1, 0, 4]
            element['highlights'] = [dict(series=0, category=2, color='#224466'), dict(series=1, category=2, color='#C9703A')]
            output, scene = self.build(element, ['分'])
            with ZipFile(output) as archive:
                root = ET.fromstring(archive.read('ppt/charts/chart1.xml'))
            series = root.findall('.//c:barChart/c:ser', ns)
            for actual, color in zip(series, ['224466', 'C9703A']):
                self.assertEqual(len(actual.findall('c:dPt', ns)), 1)
                self.assertEqual(actual.find('c:dPt/c:idx', ns).get('val'), '2')
                self.assertEqual(actual.find('c:dPt/c:spPr/a:solidFill/a:srgbClr', ns).get('val'), color)

    def test_point_emphasis_loss_or_recolor_is_detected(self):
        for mutation in ('remove', 'color'):
            element = self.chart('column'); element['highlights'] = [dict(series=0, category=1, color='#224466')]
            output, scene = self.build(element, ['分'])
            def mutate(raw):
                ns = {'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart', 'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
                root = ET.fromstring(raw); series = root.find('.//c:barChart/c:ser', ns)
                if mutation == 'remove': series.remove(series.find('c:dPt', ns))
                else: series.find('c:dPt/c:spPr/a:solidFill/a:srgbClr', ns).set('val', 'FFFFFF')
                return ET.tostring(root)
            self.rewrite(output, 'ppt/charts/chart1.xml', mutate)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(SpecError, 'point emphasis changed'):
                validate_pptx(output, scene)

    def test_table_highlight_fill_and_bold_loss_are_detected(self):
        for mutation in ('fill', 'bold'):
            element = self.table(); element['highlights'] = [dict(row=6, column=2, fill='#F0EEDD', bold=True)]
            output, scene = self.build(element, ['条件6'])
            def mutate(raw):
                ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
                root = ET.fromstring(raw); cell = root.findall('.//a:tbl/a:tr', ns)[-1].findall('a:tc', ns)[-1]
                if mutation == 'fill': cell.find('a:tcPr/a:solidFill/a:srgbClr', ns).set('val', 'FFFFFF')
                else: cell.find('.//a:rPr', ns).set('b', '0')
                return ET.tostring(root)
            self.rewrite(output, 'ppt/slides/slide1.xml', mutate)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(SpecError, 'cell (fill|bold emphasis) changed'):
                validate_pptx(output, scene)

    def test_chart_cache_mutation_is_detected(self):
        output,scene=self.build(self.chart(),['分'])
        def mutate(raw):
            root=ET.fromstring(raw);ns={'c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
            root.find('.//c:val/c:numRef/c:numCache/c:pt/c:v',ns).text='99'
            return ET.tostring(root)
        self.rewrite(output,'ppt/charts/chart1.xml',mutate)
        with self.assertRaisesRegex(SpecError,'chart values changed'):validate_pptx(output,scene)

    def test_workbook_mutation_without_cache_change_is_detected(self):
        output,scene=self.build(self.chart(),['分'])
        with ZipFile(output) as z:member=next(n for n in z.namelist() if n.endswith('.xlsx'))
        def mutate(raw):
            buffer=BytesIO()
            with ZipFile(BytesIO(raw)) as original,ZipFile(buffer,'w',compression=ZIP_DEFLATED) as changed:
                for name in original.namelist():
                    data=original.read(name)
                    if name=='xl/worksheets/sheet1.xml':
                        root=ET.fromstring(data);ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                        root.find('.//s:c[@r="B2"]/s:v',ns).text='99';data=ET.tostring(root)
                    changed.writestr(name,data)
            return buffer.getvalue()
        self.rewrite(output,member,mutate)
        with self.assertRaisesRegex(SpecError,'workbook values differ'):validate_pptx(output,scene)

    def test_percentage_data_is_retained_as_fraction(self):
        e=self.chart('line');e.update(number_format='0.0%',unit='%')
        e['series']=[dict(name='比率',values=[0.1235,0.25,0.5])];e['colors']=['#BB3322']
        output,scene=self.build(e,['12.4%','25.0%','50.0%'])
        with ZipFile(output) as z:self.assertIn(b'0.1235',z.read('ppt/charts/chart1.xml'))

    def test_negative_values_and_explicit_axis_bounds_survive(self):
        e=self.chart('column');e.update(unit='件（増減）',axis_min=-6,axis_max=6,axis_step=2)
        e['series'][0]['values']=[-5,-3,0];e['series'][1]['values']=[4,0,-2]
        self.build(e,['-5','-3','4'])
        e['series'][1]['values']=[-4,-1,-2];e['axis_max']=0
        self.build(e,['-5','-4'])
