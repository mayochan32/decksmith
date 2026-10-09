"""Run a three-slide runtime test offline. Never install software or approve visuals."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from compile_spec import source_hash, SpecError
from doctor import inspect
from version import read_version
from workflow import freeze, prepare, save_new


def make_fixture(project, renderer, font):
    """Fixed diagnostic content; production decks still require AI design."""
    project.mkdir()
    content = [
        ('overview', 'DeckSmith 実行テスト', '本文・数値・図形は編集可能です。'),
        ('flow', '生成から確認まで', '原稿 → ページ設計 → PPTX生成 → プレビュー確認'),
        ('check', '確認する項目', '日本語の表示・文字の切れ・色と配置'),
    ]
    save_new(project / 'style.yaml', {'背景': '#F5F7FB', '強調': '#315CFF', '書体': font})
    (project / 'brief.md').write_text('\n\n'.join(title + '\n' + body for _, title, body in content), encoding='utf-8')
    save_new(project / 'structure.yaml', {'slides': [
        {'id': sid, 'required_text': [title, body], 'notes': '実行環境の確認用。任意スタイルの設計テストではない。'}
        for sid, title, body in content]})
    freeze(project)  # Independent content baseline precedes scene construction.
    save_new(project / 'decksmith.yaml', {
        'input': {'style': 'style.yaml', 'brief': 'brief.md'},
        'output': {'directory': '../output', 'filename': 'decksmith-smoke.pptx',
                   'renderer': renderer, 'pdf': renderer != 'none'},
        'slide': {'width_px': 1920, 'height_px': 1080}, 'language': '日本語',
        'privacy': {'mode': 'restricted'}, 'text': {'amount': 'less'},
        'images': {'mode': 'provided_only', 'amount': 'none', 'plan': 'skip'}})
    prepare(project, capability='unavailable')
    (project / 'text-plan.md').write_text('各ページは見出し1行と必須本文1行。生成画像は使用しない。\n', encoding='utf-8')
    slides = []
    for index, (sid, title, body) in enumerate(content, 1):
        slides.append({'id': sid, 'background': '#F5F7FB', 'elements': [
            {'id': 'accent', 'type': 'shape', 'geometry': 'rect', 'x': 120, 'y': 135,
             'width': 90 * index, 'height': 16, 'fill': '#315CFF'},
            {'id': 'title', 'type': 'text', 'x': 120, 'y': 220, 'width': 1650, 'height': 175,
             'font': font, 'size': 88, 'color': '#152C48', 'role': 'heading', 'text': title},
            {'id': 'body', 'type': 'text', 'x': 120, 'y': 475, 'width': 1650, 'height': 245,
             'font': font, 'size': 52, 'color': '#152C48', 'role': 'body', 'text': body},
            {'id': 'page', 'type': 'text', 'x': 120, 'y': 900, 'width': 500, 'height': 70,
             'font': font, 'size': 32, 'color': '#315CFF', 'role': 'caption', 'text': f'RUNTIME TEST  {index} / 3'},
        ]})
    fingerprints = {'style_sha256': source_hash(project / 'style.yaml'),
                    'structure_sha256': source_hash(project / 'structure.yaml')}
    requirements = [
        {'source': '/背景', 'interpretation': 'Light background', 'status': 'implemented', 'targets': [sid for sid, _, _ in content]},
        {'source': '/強調', 'interpretation': 'Blue accent', 'status': 'implemented', 'targets': [sid + '/accent' for sid, _, _ in content]},
        {'source': '/書体', 'interpretation': 'Requested diagnostic font', 'status': 'implemented', 'targets': [sid + '/title' for sid, _, _ in content]},
    ]
    save_new(project / 'scene.yaml', {'schema_version': '1.0', 'canvas': {'width': 1920, 'height': 1080},
             **fingerprints, 'requirements': requirements, 'slides': slides})
    save_new(project / 'design-plan.yaml', {**fingerprints,
        'signatures': [{'source': r['source'], 'intent': r['interpretation'],
                        'visual_check': 'Inspect the actual PNG against style.yaml'} for r in requirements],
        'font_evidence': f'Requested {font}; glyph coverage and substitution require visual inspection on this host.',
        'typography': {role: {'font': font, 'min_size': size, 'reason': 'Diagnostic text readability'}
                       for role, size in (('heading', 88), ('body', 52), ('caption', 32))},
        'representative_slides': ['overview'],
        'slides': [{'id': sid, 'focal_element': 'title', 'focal_reason': 'Runtime test label',
                    'composition': 'Title, required body and editable accent',
                    'asset_decision': 'No images required for this runtime test'} for sid, _, _ in content]})


def smoke(workspace, renderer='libreoffice', font='Arial'):
    workspace = Path(workspace).expanduser().absolute()
    if workspace.exists() or workspace.is_symlink():
        raise FileExistsError('Refusing to overwrite workspace: ' + str(workspace))
    workspace = workspace.resolve()
    # Exclusive creation prevents tests from altering an existing workspace.
    workspace.mkdir(parents=True, exist_ok=False)
    report = {'decksmith_version': read_version(), 'renderer': renderer,
              'workspace': str(workspace), 'visual_review': 'not_performed',
              'browser_support': 'not_established_by_runtime_test', 'stage': 'dependencies'}
    try:
        report['runtime'] = inspect(renderer)
        if not report['runtime']['renderer']['ready']:
            raise SpecError('Required runtime unavailable; no install or renderer fallback was attempted')
        report['stage'] = 'fixture'
        project = workspace / 'setting'
        make_fixture(project, renderer, font)
        report['stage'] = 'build'
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('create_deck.py')),
            '--scene', str(project / 'scene.yaml'), '--structure', str(project / 'structure.yaml'),
            '--config', str(project / 'decksmith.resolved.yaml')],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=480)
        (workspace / 'build.log').write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
        if result.returncode:
            raise SpecError('Deck generation failed: ' + result.stderr.strip())
        report['artifacts'] = json.loads(result.stdout)
        folder = Path(report['artifacts']['reports'])
        manifest = json.loads((folder / 'review-manifest.json').read_text(encoding='utf-8'))
        report['stage'] = 'artifact_check'
        if len(manifest['slides']) != 3:
            raise SpecError('Expected three slides')
        from validate_pptx import validate_pptx
        from compile_spec import compile_scene
        scene = compile_scene(project / 'scene.yaml', project / 'style.yaml', project / 'structure.yaml')
        report['validation'] = validate_pptx(Path(report['artifacts']['output']), scene)
        previews = sorted(folder.glob('slide-*.png'))
        if renderer != 'none':
            if len(previews) != 3 or not Path(report['artifacts']['pdf']).read_bytes().startswith(b'%PDF-'):
                raise SpecError('Missing PNG previews or PDF')
            for png in previews:
                header = png.read_bytes()[:24]
                if header[:8] != b'\x89PNG\r\n\x1a\n' or (int.from_bytes(header[16:20], 'big'), int.from_bytes(header[20:24], 'big')) != (1920, 1080):
                    raise SpecError('Invalid preview dimensions or signature: ' + png.name)
        report.update(stage='complete', previews=[str(p) for p in previews],
            status='ready_for_visual_review' if renderer != 'none' else 'not_visually_reviewed')
        success = True
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        report.update(status='failed', error=str(error))
        success = False
    save_new(workspace / 'smoke-result.json', report)
    return report, success


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path, help='New directory; existing directories are refused')
    parser.add_argument('--renderer', choices=('libreoffice', 'powerpoint', 'none'), default='libreoffice')
    parser.add_argument('--font', default='Arial', help='Font available on the target host; verify Japanese glyphs visually')
    args = parser.parse_args()
    try:
        report, success = smoke(args.workspace, args.renderer, args.font)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        raise SystemExit(0 if success else 2)
    except OSError as error:
        parser.exit(2, 'DeckSmith smoke: ' + str(error) + '\n')
