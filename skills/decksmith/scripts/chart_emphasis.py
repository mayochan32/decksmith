"""Apply explicit native bar/column point colors to newly generated chart XML.

The installed PptxGenJS version exposes series colors but no per-point style for
multiple series. Values, categories, series order and workbook data stay intact.
"""
import re
from xml.etree import ElementTree as ET

from compile_spec import SpecError
from evidence_validation import NS


def apply_chart_highlights(raw, expected):
    highlights = expected.get('highlights', [])
    if not highlights:
        return raw
    if expected['chart_type'] not in ('bar', 'column'):
        raise SpecError('Point highlights require a native bar or column chart')
    root = ET.fromstring(raw)
    series = root.findall('c:chart/c:plotArea/c:barChart/c:ser', NS)
    if len(series) != len(expected['series']):
        raise SpecError('Unexpected generated chart series for point highlights')
    if any(s.findall('c:dPt', NS) for s in series):
        raise SpecError('Unexpected generated point styling before explicit highlights')
    xml = raw.decode('utf-8')
    index = 0

    def replace(match):
        nonlocal index
        items = sorted((h for h in highlights if h['series'] == index), key=lambda h: h['category'])
        index += 1
        if not items:
            return match[0]
        points = ''.join('<c:dPt><c:idx val="' + str(h['category']) + '"/><c:spPr>'
                         '<a:solidFill><a:srgbClr val="' + h['color'][1:] + '"/></a:solidFill>'
                         '</c:spPr></c:dPt>' for h in items)
        if match[0].count('<c:dLbls>') != 1:
            raise SpecError('Unexpected generated data-label markup for point highlights')
        return match[0].replace('<c:dLbls>', points + '<c:dLbls>', 1)

    xml = re.sub(r'<c:ser>.*?</c:ser>', replace, xml, flags=re.DOTALL)
    if index != len(series):
        raise SpecError('Unexpected generated series markup for point highlights')
    return xml.encode('utf-8')
