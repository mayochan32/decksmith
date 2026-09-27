"""Explicit local PowerPoint smoke test; no user presentation is opened."""
import json
from pathlib import Path
import tempfile
from create_deck import executable, renderer_runtime, run, powerpoint_preview, SpecError


def test_export():
    report = {'png': {'ready': False}, 'pdf': {'ready': False}}
    with tempfile.TemporaryDirectory(prefix='decksmith-probe-') as raw:
        directory = Path(raw)
        scene = {'canvas': {'width': 1280, 'height': 720}, 'slides': [
            {'background': '#FFFFFF', 'elements': [
                {'id': 'probe', 'type': 'text', 'x': 80, 'y': 100, 'width': 1000,
                 'height': 200, 'font': 'Arial', 'size': 64, 'color': '#123456',
                 'text': 'DeckSmith export test'}]}]}
        spec = directory / 'scene.json'
        spec.write_text(json.dumps(scene), encoding='utf-8')
        pptx = directory / 'candidate.pptx'
        try:
            runtime = renderer_runtime('powerpoint')
            run([executable('node', 'DECKSMITH_NODE'), str(Path(__file__).with_name('build_deck.mjs')),
                 '--spec', str(spec), '--output', str(pptx)])
            powerpoint_preview(pptx, directory, scene, export_pdf=True, **runtime)
            report['png']['ready'] = report['pdf']['ready'] = True
        except (ValueError, OSError) as error:
            report['error'] = str(error)
            # PDF may fail after PNG export. Report the stages separately.
            png = directory / 'preview/slide-01.png'
            if png.is_file():
                header = png.read_bytes()[:24]
                report['png']['ready'] = (header[:8] == b'\x89PNG\r\n\x1a\n' and
                    (int.from_bytes(header[16:20], 'big'), int.from_bytes(header[20:24], 'big')) == (1280, 720))
    report['notice'] = 'PowerPoint may remain running; close it manually before the next build. No policy change or fallback used.'
    return report
