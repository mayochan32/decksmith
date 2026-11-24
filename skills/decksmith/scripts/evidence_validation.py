"""Verify native table cells, chart caches and embedded literal workbook data."""
from decimal import Decimal, InvalidOperation
from io import BytesIO
import posixpath
from urllib.parse import unquote
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

from compile_spec import SpecError, compact

NS = {'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
      'c':'http://schemas.openxmlformats.org/drawingml/2006/chart',
      'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      's':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def relation(archive, source, rid):
    name = posixpath.join(posixpath.dirname(source), '_rels', posixpath.basename(source)+'.rels')
    for item in ET.fromstring(archive.read(name)):
        if item.get('Id') == rid:
            if item.get('TargetMode') == 'External':
                raise SpecError('Native chart data must be embedded, not externally linked')
            target = unquote(item.get('Target', ''))
            return target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(posixpath.dirname(source), target))
    raise SpecError('Missing native evidence relationship: ' + str(rid))


def table(node, expected):
    actual = node.find('.//a:tbl', NS)
    if actual is None: raise SpecError('Table became non-native')
    rows = actual.findall('a:tr', NS)
    source = [expected['headers'], *expected['rows']]
    if len(rows) != len(source): raise SpecError('Native table row loss')
    overrides = {(h['row'], h['column']): h for h in expected.get('highlights', [])}
    for row_index, (actual_row, expected_row) in enumerate(zip(rows, source)):
        cells = actual_row.findall('a:tc', NS)
        if len(cells) != len(expected_row): raise SpecError('Native table column loss')
        for column_index, (cell, value) in enumerate(zip(cells, expected_row)):
            content = ''.join(t.text or '' for t in cell.findall('.//a:t', NS))
            if compact(content) != compact(value):
                raise SpecError('Native table cell content changed')
            override = overrides.get((row_index, column_index), {})
            fill = override.get('fill', expected.get('header_fill', expected.get('fill')) if row_index == 0 else expected.get('fill'))
            if fill is not None:
                actual_fill = cell.find('a:tcPr/a:solidFill/a:srgbClr', NS)
                if actual_fill is None or actual_fill.get('val', '').upper() != fill[1:].upper():
                    raise SpecError('Native table cell fill changed')
            color = override.get('color', expected.get('header_color', expected['color']) if row_index == 0 else expected['color'])
            bold = override.get('bold', row_index == 0)
            for run in cell.findall('.//a:r', NS):
                properties = run.find('a:rPr', NS)
                ink = properties.find('a:solidFill/a:srgbClr', NS) if properties is not None else None
                if ink is None or ink.get('val', '').upper() != color[1:].upper():
                    raise SpecError('Native table cell text color changed')
                if (properties.get('b') == '1') != bold:
                    raise SpecError('Native table cell bold emphasis changed')
            if 'border_mode' in expected:
                mode = expected['border_mode']
                visible_sides = {'lnT', 'lnB'} if mode == 'horizontal' else ({'lnT', 'lnR', 'lnB', 'lnL'} if mode == 'all' else set())
                width = expected.get('border_width', 1)
                if width == 0: visible_sides = set()
                for side in ('lnT', 'lnR', 'lnB', 'lnL'):
                    line = cell.find('a:tcPr/a:'+side, NS)
                    if line is None: raise SpecError('Native table borders changed')
                    visible = line.find('a:noFill', NS) is None and int(line.get('w', '0')) > 0
                    if visible != (side in visible_sides): raise SpecError('Native table borders changed')
                    if visible:
                        color = line.find('a:solidFill/a:srgbClr', NS)
                        if (color is None or color.get('val', '').upper() != expected.get('border_color', expected['color'])[1:].upper()
                                or abs(int(line.get('w'))-round(width*9525)) > 2):
                            raise SpecError('Native table border style changed')
    widths = expected.get('column_widths', [expected['width']/len(expected['headers'])]*len(expected['headers']))
    grid = actual.findall('a:tblGrid/a:gridCol', NS)
    if len(grid) != len(widths) or any(abs(int(col.get('w'))-round(width*9525)) > 2 for col,width in zip(grid,widths)):
        raise SpecError('Native table column widths changed')
    heights = expected.get('row_heights', [expected['height']/len(source)]*len(source))
    if any(abs(int(row.get('h'))-round(height*9525)) > 2 for row,height in zip(rows,heights)):
        raise SpecError('Native table row heights changed')


def points(node):
    values = node.findall('.//c:pt', NS) if node is not None else []
    if [point.get('idx') for point in values] != [str(i) for i in range(len(values))]:
        raise SpecError('Chart cache contains missing or reordered points')
    return [point.findtext('c:v', '', NS) for point in values]


def same_number(actual, expected):
    try:
        return Decimal(actual) == Decimal(str(expected))
    except (InvalidOperation, TypeError, ValueError):
        return False


def column(index):
    result = ''; index += 1
    while index:
        index, digit = divmod(index-1, 26)
        result = chr(65+digit) + result
    return result


def chart(archive, slide_path, node, expected):
    reference = node.find('.//c:chart', NS)
    if reference is None: raise SpecError('Chart became non-native')
    path = relation(archive, slide_path, reference.get('{'+NS['r']+'}id'))
    root = ET.fromstring(archive.read(path))
    kind = 'lineChart' if expected['chart_type'] == 'line' else 'barChart'
    plot = root.find('c:chart/c:plotArea/c:'+kind, NS)
    if plot is None: raise SpecError('Native chart type changed')
    if kind == 'barChart' and plot.find('c:barDir', NS).get('val') != ('bar' if expected['chart_type']=='bar' else 'col'):
        raise SpecError('Native chart orientation changed')
    series = plot.findall('c:ser', NS)
    if len(series) != len(expected['series']): raise SpecError('Native chart series loss')
    for index,(actual, source) in enumerate(zip(series,expected['series']),1):
        color = actual.find('c:spPr/a:solidFill/a:srgbClr', NS)
        if color is None or color.get('val', '').upper() != expected['colors'][index-1][1:].upper():
            raise SpecError('Native chart series color changed')
        expected_points = {h['category']: h['color'] for h in expected.get('highlights', []) if h['series'] == index-1}
        point_colors = {}
        for point in actual.findall('c:dPt', NS):
            idx = point.find('c:idx', NS)
            fill = point.find('c:spPr/a:solidFill/a:srgbClr', NS)
            try:
                position = int(idx.get('val'))
            except (AttributeError, TypeError, ValueError) as error:
                raise SpecError('Invalid native chart point emphasis') from error
            if position in point_colors or fill is None:
                raise SpecError('Invalid native chart point emphasis')
            point_colors[position] = '#' + fill.get('val', '').upper()
        if point_colors != {k: v.upper() for k, v in expected_points.items()}:
            raise SpecError('Native chart point emphasis changed')
        tx, cat, val = (actual.find('c:'+name, NS) for name in ('tx','cat','val'))
        if points(tx) != [source['name']] or points(cat) != expected['categories']:
            raise SpecError('Native chart names/categories changed')
        numbers = points(val)
        if len(numbers) != len(source['values']) or any(not same_number(a,b) for a,b in zip(numbers,source['values'])):
            raise SpecError('Native chart values changed')
        end = len(expected['categories'])+1; col = column(index)
        formulas = [part.findtext('.//c:f', '', NS) for part in (tx,cat,val)]
        if formulas != [f'Sheet1!${col}$1', f'Sheet1!$A$2:$A${end}', f'Sheet1!${col}$2:${col}${end}']:
            raise SpecError('Unsupported or changed chart workbook references')
        labels = actual.find('c:dLbls', NS)
        show = labels.find('c:showVal', NS) if labels is not None else None
        if (show is not None and show.get('val')=='1') != expected.get('show_values', True):
            raise SpecError('Native chart value-label visibility changed')
        format_node = labels.find('c:numFmt', NS) if labels is not None else None
        if format_node is None or format_node.get('formatCode') != expected.get('number_format', 'General'):
            raise SpecError('Native chart number format changed')
    unit = ''.join(t.text or '' for t in root.findall('c:chart/c:plotArea/c:valAx/c:title//a:t', NS))
    if unit != expected['unit']: raise SpecError('Native chart unit changed')
    for field, tag in (('axis_min','min'),('axis_max','max')):
        if field in expected:
            bound = root.find('c:chart/c:plotArea/c:valAx/c:scaling/c:'+tag, NS)
            if bound is None or not same_number(bound.get('val'), expected[field]):
                raise SpecError('Native chart axis bound changed')
    legend = root.find('c:chart/c:legend', NS)
    if (legend is not None) != expected.get('show_legend', len(series)>1):
        raise SpecError('Native chart legend visibility changed')
    external = root.find('c:externalData', NS)
    if external is None: raise SpecError('Chart has no embedded editable workbook')
    workbook_path = relation(archive, path, external.get('{'+NS['r']+'}id'))
    try:
        with ZipFile(BytesIO(archive.read(workbook_path))) as book:
            strings = ET.fromstring(book.read('xl/sharedStrings.xml'))
            strings = [''.join(t.text or '' for t in item.findall('.//s:t', NS)) for item in strings]
            sheet = ET.fromstring(book.read('xl/worksheets/sheet1.xml'))
            data_table = ET.fromstring(book.read('xl/tables/table1.xml'))
            if data_table.get('ref') != 'A1:'+column(len(expected['series']))+str(len(expected['categories'])+1):
                raise SpecError('Chart workbook table range is invalid')
            cells = {}
            for cell in sheet.findall('s:sheetData/s:row/s:c', NS):
                if cell.find('s:f', NS) is not None: raise SpecError('Expected literal chart workbook values')
                value = cell.findtext('s:v', '', NS)
                cells[cell.get('r')] = strings[int(value)] if cell.get('t')=='s' else value
            for row,label in enumerate(expected['categories'],2):
                if cells.get('A'+str(row)) != label: raise SpecError('Chart workbook categories differ from cache')
            for index,source in enumerate(expected['series'],1):
                col = column(index)
                if cells.get(col+'1') != source['name']: raise SpecError('Chart workbook series differs from cache')
                if any(not same_number(cells.get(col+str(row)),value) for row,value in enumerate(source['values'],2)):
                    raise SpecError('Chart workbook values differ from cache')
    except (BadZipFile, KeyError, IndexError, ValueError, ET.ParseError) as error:
        raise SpecError('Invalid embedded chart workbook: '+str(error)) from error
