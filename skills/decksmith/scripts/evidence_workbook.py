"""Finish native chart data and explicit point styles before rendering new charts.

Only newly generated candidate files enter here, before any preview/hash/review.
Restore blank zero cells from declared data and remove the generated table-range
apostrophe, then apply explicitly selected point colors. Other disagreements are
left for validation to reject. Existing user-supplied PPTX files never enter here.
"""
from io import BytesIO
from pathlib import Path
import os
import re
import tempfile
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from compile_spec import SpecError
from evidence_validation import NS, column, relation
from chart_emphasis import apply_chart_highlights


def normalize_workbook(raw, evidence):
    with ZipFile(BytesIO(raw)) as source:
        entries = [(item, source.read(item.filename)) for item in source.infolist()]
    files = {item.filename:data for item,data in entries}
    name = 'xl/worksheets/sheet1.xml'; xml = files[name].decode('utf-8')
    sheet = ET.fromstring(xml)
    cells = {cell.get('r'):cell for cell in sheet.findall('s:sheetData/s:row/s:c', NS)}
    restored = []
    for index, series in enumerate(evidence['series'],1):
        for row,value in enumerate(series['values'],2):
            if value != 0: continue
            address = column(index)+str(row); cell = cells.get(address)
            if (cell is None or cell.get('t') not in (None,'n')
                    or cell.find('s:f',NS) is not None):
                raise SpecError('Unexpected generated zero cell: '+address)
            if cell.findtext('s:v','',NS) == '':
                pattern = r'(<c r="'+address+r'"><v>)\s*(</v></c>)'
                xml, count = re.subn(pattern,lambda m:m[1]+'0'+m[2],xml)
                if count != 1: raise SpecError('Unexpected generated zero-cell markup: '+address)
                restored.append(address)
    files[name] = xml.encode('utf-8')
    name = 'xl/tables/table1.xml'; xml = files[name].decode('utf-8')
    expected = 'A1:'+column(len(evidence['series']))+str(len(evidence['categories'])+1)
    actual = ET.fromstring(xml).get('ref')
    corrected = actual == expected+"'"
    if corrected: files[name] = xml.replace('ref="'+actual+'"','ref="'+expected+'"',1).encode('utf-8')
    elif actual != expected: raise SpecError('Unexpected generated chart table range')
    if not restored and not corrected: return raw, {'zero_cells_restored':[], 'table_range_corrected':False}
    result = BytesIO()
    with ZipFile(result,'w') as target:
        for item,data in entries: target.writestr(item, files[item.filename])
    return result.getvalue(), {'zero_cells_restored':restored,'table_range_corrected':corrected}


def normalize_chart_workbooks(candidate, scene):
    candidate = Path(candidate)
    updates = {}; records = []
    with ZipFile(candidate) as source:
        for index,slide in enumerate(scene['slides'],1):
            evidence = [e for e in slide['elements'] if e['type']=='chart']
            if not evidence: continue
            slide_path = f'ppt/slides/slide{index}.xml'
            root = ET.fromstring(source.read(slide_path))
            references = root.findall('.//c:chart',NS)
            if len(references) != len(evidence): raise SpecError('Native chart relationship count differs')
            for reference,element in zip(references,evidence):
                path = relation(source,slide_path,reference.get('{'+NS['r']+'}id'))
                chart = ET.fromstring(source.read(path)); external = chart.find('c:externalData',NS)
                if external is None: raise SpecError('Missing generated chart workbook')
                styled = apply_chart_highlights(source.read(path), element)
                if styled != source.read(path): updates[path] = styled
                workbook = relation(source,path,external.get('{'+NS['r']+'}id'))
                original = source.read(workbook)
                replacement, record = normalize_workbook(original,element)
                if replacement != original: updates[workbook] = replacement
                if element.get('highlights'): record['point_highlights_applied'] = len(element['highlights'])
                records.append(dict(chart=path,**record))
        if not updates: return records
        entries = [(item,source.read(item.filename)) for item in source.infolist()]
    # Atomic replacement in the private build directory, before final delivery.
    descriptor, name = tempfile.mkstemp(prefix='.native-data-',suffix='.pptx',dir=candidate.parent)
    os.close(descriptor)
    try:
        with ZipFile(name,'w') as target:
            for item,data in entries: target.writestr(item,updates.get(item.filename,data))
        os.replace(name,candidate)
    finally:
        if os.path.exists(name): os.unlink(name)
    return records
