"""Inspect and transform existing PPTX files with explicit preservation modes."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from compile_spec import SpecError, leaves, load_mapping, source_hash
from create_deck import next_output_path, powerpoint_preview, preview, renderer_runtime
from pptx_restyle import inspect_source, package, validate_plan, write_candidate, METRICS
from project_config import resolve_config
from version import read_version
from workflow import announce, policy_record, save_new


MODES = {'1': 'style_only', '2': 'style_and_text', '3': 'redesign',
         'style_only': 'style_only', 'style_and_text': 'style_and_text', 'redesign': 'redesign'}


def mode_name(value):
    if value not in MODES:
        raise SpecError('Mode must be 1, 2, 3, style_only, style_and_text or redesign')
    return MODES[value]


def prepare(source, style, destination, mode='style_only', renderer=None, config_path=None, pdf_font_map=None):
    mode = mode_name(mode)
    if Path(source).suffix.lower() == '.pdf':
        from pdf_input import prepare_pdf
        return prepare_pdf(source, style, destination, mode, renderer, config_path, pdf_font_map)
    if mode == 'redesign':
        from redesign_deck import prepare_redesign
        return prepare_redesign(source, style, destination)
    inventory = inspect_source(source)
    style_data = load_mapping(style)
    requirements = [{'source': p, 'interpretation': '', 'status': 'unresolved', 'operations': []}
                    for p in leaves(style_data)]
    if not requirements:
        raise SpecError('Style must contain at least one value')
    inventory['mode'] = mode
    plan = {'schema_version': '1.0', 'mode': mode,
        'source_sha256': inventory['source_sha256'], 'style_sha256': source_hash(style),
        'requirements': requirements, 'operations': []}
    if mode == 'style_and_text':
        plan.update(rewrites=[], protected_terms=[], protection_review='')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    save_new(destination / 'source-inventory.json', inventory)
    save_new(destination / 'restyle-plan.yaml', plan)
    return {'inventory': str(destination / 'source-inventory.json'),
            'plan': str(destination / 'restyle-plan.yaml'), 'status': 'interpretation_required'}


def render(pptx, work, scene, renderer, runtime, pdf=False):
    work.mkdir()
    if renderer == 'powerpoint':
        return powerpoint_preview(pptx, work, scene, runtime['powershell'], pdf)
    return preview(pptx, work, scene, runtime['soffice'], runtime['pdftoppm'])


def markdown_report(report):
    descriptions = {'style_only': 'モード①：文章・配置を保持したスタイル変更。',
                    'style_and_text': 'モード②：配置を保持し、スタイルと文章を改善。',
                    'redesign': 'モード③：元資料を根拠として文章・配置・構成を再設計。'}
    lines = ['# スタイル変換レポート', '', descriptions[report['mode']], '',
             '- 構造保持検査：合格', '- 視覚確認：未確認（折り返し・はみ出し・フォント置換を含む）',
             '- ページ数：' + str(report['validation']['slides']),
             '- 変更操作数：' + str(len(report['operations'])),
             '- スタイル適用：' + ('一部未適用' if report['excluded_requirements'] else '全項目を実装。視覚確認は別途必要'), '',
             '## 変更操作', '']
    for operation in report['operations']:
        lines.append('- ' + json.dumps(operation, ensure_ascii=False))
    if report.get('rewrites'):
        lines += ['', '## 文章の変更前後と理由', '']
        for rewrite in report['rewrites']:
            lines.append('- ' + json.dumps(rewrite, ensure_ascii=False))
    if report.get('mapping'):
        lines += ['', '## 元資料と再設計後の対応', '']
        for mapping in report['mapping']:
            lines.append('- ' + json.dumps(mapping, ensure_ascii=False))
    if report['excluded_requirements']:
        lines += ['', '## 未適用・一部のみ適用した指定', '']
        for req in report['excluded_requirements']:
            lines.append('- ' + req['source'] + '：' + req['status'] + '／' + req['reason'])
    lines += ['', '## 制約', '',
        ('画像、表、グラフ、ノート、マスターは保持。画像内の文字は変更しません。'
         if report['mode'] != 'redesign' else '元の要素との対応と、統合・省略・再構成の理由を記録します。'),
        'XML上の保持検査は、表示上の折り返しや文字切れの合格を意味しません。',
        '元資料と変換後の全ページを比較し、review_deck.pyでレビュー記録を検査してください。', '']
    if report.get('input_format') == 'pdf':
        lines[4] = '- 構造保持検査：取り込み後のPPTXを基準に検査（元PDFとの表示比較は別途必須）'
        lines += ['## PDF取り込み', '', '元PDF SHA-256：' + report['pdf_source_sha256'],
                  'PDFの図・表・グラフは画像として保持します。元のデータ構造は復元しません。',
                  '画像化されたページの内容は、元PDFを見て確認してください。OCRは自動実行しません。', '']
        lines += ['- ' + value for value in report['pdf_limitations']]
    return '\n'.join(lines)


def apply(source, style, plan_path, output, renderer=None, config_path=None, draft=False, next_output=False, mode=None):
    selected = load_mapping(plan_path).get('mode')
    if mode is not None and mode_name(mode) != selected:
        raise SpecError('Requested mode differs from plan; inspect again for the selected mode')
    if Path(source).suffix.lower() == '.pdf':
        from pdf_input import apply_pdf
        return apply_pdf(source, style, plan_path, output, renderer, config_path, draft, next_output)
    if load_mapping(plan_path).get('input_format') == 'pdf':
        raise SpecError('PDF plan requires its original PDF source')
    if selected == 'redesign':
        from redesign_deck import apply_redesign
        return apply_redesign(source, style, plan_path, output, renderer, config_path, draft, next_output)
    source, style, plan_path = (Path(p).resolve() for p in (source, style, plan_path))
    output = Path(output).expanduser().absolute()
    if output.suffix.lower() != '.pptx':
        raise SpecError('Output must end in .pptx')
    if output.resolve() == source:
        raise SpecError('Source cannot be overwritten')
    if next_output:
        output = next_output_path(output)
    reports = output.with_suffix('.preview')
    pdf_output = output.with_suffix('.pdf')
    for path in (output, reports, pdf_output):
        if path.exists() or path.is_symlink():
            raise SpecError('Refusing to overwrite output or reports: ' + str(path))
    config = resolve_config(config_path, plan_path.parent)
    policy = policy_record(config)
    if policy:
        config['communication_policy'] = policy['policy']
    print(announce(config), file=sys.stderr)
    renderer = renderer or config['output']['renderer']
    if renderer == 'none' and config['output']['pdf']:
        raise SpecError('PDF requires a renderer; no automatic fallback')
    output.parent.mkdir(parents=True, exist_ok=True)
    # All checks and rendering finish before publishing a new result.
    with tempfile.TemporaryDirectory(prefix='decksmith-restyle-', dir=output.parent) as raw:
        work = Path(raw)
        original, style_copy, plan_copy = work / 'original.pptx', work / 'style.yaml', work / 'plan.yaml'
        shutil.copyfile(source, original)
        shutil.copyfile(style, style_copy)
        shutil.copyfile(plan_path, plan_copy)
        plan = load_mapping(plan_copy)
        _, _, slides, canvas = package(original)
        validate_plan(plan, original, style_copy, slides)
        unsupported = [r for r in plan['requirements'] if r['status'] == 'unsupported']
        if unsupported and not draft:
            raise SpecError('Unsupported style requirements remain; implement them or use --draft')
        runtime = renderer_runtime(renderer)
        candidate = work / 'candidate.pptx'
        validation = write_candidate(original, candidate, plan)
        folder = work / 'reports'
        folder.mkdir()
        scene = {'canvas': canvas, 'slides': [{} for _ in slides]}
        if renderer != 'none':
            before = render(original, work / 'before', scene, renderer, runtime)
            after = render(candidate, work / 'after', scene, renderer, runtime, config['output']['pdf'])
            shutil.copytree(before, folder / 'source')
            for png in after.glob('slide-*.png'):
                shutil.copyfile(png, folder / png.name)
        status = 'draft' if draft else ('ready_for_visual_review' if renderer != 'none' else 'not_visually_reviewed')
        exclusions = [r for r in plan['requirements'] if r['status'] != 'implemented']
        report = {'decksmith_version': read_version(), 'workflow': 'restyle', 'mode': plan['mode'],
            'status': status, 'source_sha256': source_hash(original), 'output_sha256': source_hash(candidate),
            'style_sha256': source_hash(style_copy), 'plan_sha256': source_hash(plan_copy),
            'renderer': renderer, 'validation': validation, 'operations': plan['operations'],
            'excluded_requirements': exclusions, 'visual_review': 'not_performed',
            'rewrites': plan.get('rewrites', []), 'protected_terms': plan.get('protected_terms', []),
            'metrics_changed': any(set(op['set']) & METRICS for op in plan['operations']),
            'configuration_notes': ['Source canvas and frame geometry are retained in modes 1 and 2.']}
        save_new(folder / 'restyle-report.json', report)
        (folder / 'restyle-report.md').write_text(markdown_report(report), encoding='utf-8')
        save_new(folder / 'restyle-plan.json', plan)
        inventory = inspect_source(original); inventory['mode'] = plan['mode']
        save_new(folder / 'source-inventory.json', inventory)
        shutil.copyfile(style_copy, folder / 'style.yaml')
        if policy:
            save_new(folder / 'policy-record.json', policy)
        preview_hashes = {str(p.relative_to(folder).as_posix()): source_hash(p)
                          for p in sorted(folder.rglob('slide-*.png'))}
        records = ('restyle-report.json', 'restyle-report.md', 'restyle-plan.json',
                   'source-inventory.json', 'style.yaml') + (('policy-record.json',) if policy else ())
        manifest = {'workflow': 'restyle', 'mode': plan['mode'], 'status': status,
            'output_sha256': report['output_sha256'], 'source_sha256': report['source_sha256'],
            'pdf_sha256': source_hash(work / 'after/pdf/candidate.pdf') if config['output']['pdf'] else None,
            'style_sha256': report['style_sha256'], 'preview_sha256': preview_hashes,
            'workflow_records': {name: source_hash(folder / name) for name in records},
            'requirements': plan['requirements'], 'slides': [{'id': str(i),
                'preview': f'slide-{i:02d}.png' if renderer != 'none' else None,
                'source_preview': f'source/slide-{i:02d}.png' if renderer != 'none' else None}
                for i in range(1, len(slides)+1)]}
        save_new(folder / 'review-manifest.json', manifest)
        if source_hash(source) != report['source_sha256'] or source_hash(style) != report['style_sha256']:
            raise SpecError('Source/style changed during processing; no result published')
        # Reserve result names exclusively. Roll back only files created by this call.
        reserved = []
        try:
            with output.open('xb') as target:
                reserved.append(output)
                with candidate.open('rb') as stream:
                    shutil.copyfileobj(stream, target)
            reports.mkdir(exist_ok=False)
            reserved.append(reports)
            shutil.copytree(folder, reports, dirs_exist_ok=True)
            if config['output']['pdf']:
                with pdf_output.open('xb') as target:
                    reserved.append(pdf_output)
                    with (work / 'after/pdf/candidate.pdf').open('rb') as stream:
                        shutil.copyfileobj(stream, target)
        except Exception:
            for path in reversed(reserved):
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
            raise
    return {'output': str(output), 'reports': str(reports), 'status': status, 'mode': plan['mode'],
        'pdf': str(pdf_output) if config['output']['pdf'] else None,
        'style_application': 'partial' if exclusions else 'all_requirements_implemented_pending_review'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version='DeckSmith ' + read_version())
    sub = parser.add_subparsers(dest='action', required=True)
    inspect = sub.add_parser('inspect')
    apply_parser = sub.add_parser('apply')
    for command in (inspect, apply_parser):
        command.add_argument('--source', type=Path, required=True)
        command.add_argument('--style', type=Path, required=True)
        command.add_argument('--mode', choices=tuple(MODES), default=None)
    inspect.add_argument('--destination', type=Path, required=True)
    inspect.add_argument('--config', type=Path)
    inspect.add_argument('--renderer', choices=('none', 'libreoffice', 'powerpoint'))
    inspect.add_argument('--pdf-font-map', type=Path)
    for name in ('plan', 'output'):
        apply_parser.add_argument('--' + name, type=Path, required=True)
    apply_parser.add_argument('--config', type=Path)
    apply_parser.add_argument('--renderer', choices=('none', 'libreoffice', 'powerpoint'))
    apply_parser.add_argument('--draft', action='store_true')
    apply_parser.add_argument('--next-output', action='store_true')
    args = parser.parse_args()
    print('DeckSmith ' + read_version(), file=sys.stderr)
    try:
        if args.action == 'inspect':
            result = prepare(args.source, args.style, args.destination, args.mode or 'style_only',
                             args.renderer, args.config, args.pdf_font_map)
        else:
            result = apply(args.source, args.style, args.plan, args.output, args.renderer,
                           args.config, args.draft, args.next_output, args.mode)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print('DeckSmith restyle: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
