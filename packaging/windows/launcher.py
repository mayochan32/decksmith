"""Windows PORTABLE launcher; never downloads or selects host runtimes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def environment(root):
    from process_environment import child_environment, announce_repair, powershell_path, REPAIR_OPTION
    env = {k: v for k, v in os.environ.items()
           if (not k.upper().startswith(('PYTHON', 'DECKSMITH_'))
               and k.upper() not in ('NODE_OPTIONS', 'NODE_PATH'))
           or k.upper() == REPAIR_OPTION}
    env, report = child_environment(env)
    announce_repair(report)
    env['DECKSMITH_NODE'] = str(root / 'runtime/node/node.exe')
    env['DECKSMITH_NODE_MODULES'] = str(root / 'skills/decksmith/node_modules')
    if (root / 'runtime/pdf').is_dir():
        env['DECKSMITH_PDF_MODULES'] = str(root / 'runtime/pdf')
    if sys.platform == 'win32':
        env['DECKSMITH_POWERSHELL'] = powershell_path(env)
    return env


def command(root, args):
    from project_config import resolve_config
    project = args.project.resolve()
    scripts = root / 'skills/decksmith/scripts'
    cmd = [str(root / 'runtime/python/python.exe'), '-I', '-X', 'utf8']
    if args.action == 'init':
        cmd += [str(scripts / 'project_init.py'), '--project', str(project)]
        if args.renderer:
            cmd += ['--renderer', args.renderer]
        return cmd, root
    if not project.is_dir():
        raise ValueError('Project directory does not exist: ' + str(project))
    def at_project(value):
        return (project / value).resolve()
    if args.action in ('prepare','freeze-content','prototype','compare'):
        cmd += [str(scripts / 'workflow.py'), args.action]
        if args.action != 'compare': cmd += ['--project',str(project)]
        for key in ('config','destination','structure','brief','previous','output'):
            value=getattr(args,key,None)
            if value: cmd += ['--'+key,str(at_project(value))]
        for key in ('image_capability','source_evidence'):
            value=getattr(args,key,None)
            if value: cmd += ['--'+key.replace('_','-'),value]
        if getattr(args,'slides',None):cmd += ['--slides',*args.slides]
        return cmd, project
    if args.action == 'review':
        if not getattr(args, 'output', None):
            raise ValueError('review requires --output <PPTX>')
        cmd += [str(scripts / 'review_deck.py'), '--output', str(at_project(args.output))]
        if getattr(args, 'review', None):
            cmd += ['--review', str(at_project(args.review))]
        return cmd, project
    if args.action in ('inspect-source', 'restyle'):
        source = getattr(args, 'source', None)
        if not source:
            raise ValueError(args.action + ' requires --source <PPTX or PDF>')
        config = at_project(args.config) if getattr(args, 'config', None) else project / 'decksmith.yaml'
        if getattr(args, 'config', None) and not config.is_file():
            raise ValueError('Missing config: ' + str(config))
        settings = resolve_config(config if config.is_file() else None, base=project)
        style = at_project(args.style) if getattr(args, 'style', None) else Path(settings['input'].get('style', project / 'style.yaml'))
        cmd += [str(scripts / 'restyle_deck.py'), 'inspect' if args.action == 'inspect-source' else 'apply',
                '--source', str(at_project(source)), '--style', str(style)]
        if getattr(args, 'mode', None):
            cmd += ['--mode', args.mode]
        if args.action == 'inspect-source':
            pdf_input = Path(source).suffix.lower() == '.pdf'
            if (pdf_input or args.renderer) and (args.renderer or settings['output']['renderer']) not in ('none', 'powerpoint'):
                raise ValueError('Portable supports only none or powerpoint; no automatic fallback.')
            cmd += ['--destination', str(at_project(getattr(args, 'destination', None) or 'restyle'))]
            if pdf_input or args.renderer:
                cmd += ['--renderer', args.renderer or settings['output']['renderer']]
            if config.is_file():
                cmd += ['--config', str(config)]
            if getattr(args, 'pdf_font_map', None):
                cmd += ['--pdf-font-map', str(at_project(args.pdf_font_map))]
        else:
            renderer = args.renderer or settings['output']['renderer']
            if renderer not in ('none', 'powerpoint'):
                raise ValueError('Portable supports only none or powerpoint; no automatic fallback.')
            cmd += ['--plan', str(at_project(getattr(args, 'plan', None) or 'restyle/restyle-plan.yaml')),
                    '--output', str(at_project(args.output) if getattr(args, 'output', None) else
                        Path(settings['output']['directory']) / (settings['output']['filename'] or 'restyled.pptx')),
                    '--renderer', renderer]
            if config.is_file():
                cmd += ['--config', str(config)]
            for flag in ('draft', 'next_output'):
                if getattr(args, flag, False):
                    cmd += ['--' + flag.replace('_', '-')]
        return cmd, project
    config = at_project(args.config) if getattr(args, 'config', None) else project / 'decksmith.yaml'
    if getattr(args, 'config', None) and not config.is_file():
        raise ValueError('Missing config: ' + str(config))
    settings = resolve_config(config if config.is_file() else None, base=project)
    renderer = args.renderer or settings['output']['renderer']
    validating = args.action == 'validate' or getattr(args, 'validate_only', False)
    if not validating and renderer not in ('none', 'powerpoint'):
        raise ValueError('Portable supports only none or powerpoint. Set output.renderer '
                         'in decksmith.yaml or pass --renderer; no automatic fallback.')
    if args.action == 'doctor':
        cmd += [str(scripts / 'doctor.py'), '--renderer', renderer]
        if config.is_file():
            cmd += ['--config', str(config)]
        for flag in ('fonts', 'test_export', 'pdf_input'):
            if getattr(args, flag, False):
                cmd += ['--' + flag.replace('_', '-')]
    else:
        cmd += [str(scripts / 'create_deck.py'),
                '--scene', str(at_project(getattr(args, 'scene', None) or 'scene.yaml')),
                '--structure', str(at_project(getattr(args, 'structure', None) or 'structure.yaml')),
                '--renderer', renderer]
        if config.is_file():
            cmd += ['--config', str(config)]
        if getattr(args, 'style', None):
            cmd += ['--style', str(at_project(args.style))]
        elif not settings['input'].get('style'):
            cmd += ['--style', str(project / 'style.yaml')]
        if getattr(args, 'output', None):
            cmd += ['--output', str(at_project(args.output))]
        elif not settings['output']['filename']:
            cmd += ['--output', str(Path(settings['output']['directory']) / 'deck.pptx')]
        if validating:
            cmd += ['--validate-only']
        for flag in ('draft', 'next_output'):
            if getattr(args, flag, False):
                cmd += ['--' + flag.replace('_', '-')]
        if getattr(args, 'design_plan', None):
            cmd += ['--design-plan', str(at_project(args.design_plan))]
    return cmd, project


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='store_true')
    parser.add_argument('action', nargs='?', choices=('init', 'doctor', 'validate', 'build', 'review','prepare','freeze-content','prototype','compare','inspect-source','restyle'))
    parser.add_argument('--project', type=Path, default=Path.cwd())
    parser.add_argument('--renderer', choices=('none', 'powerpoint'))
    for name in ('config', 'scene', 'structure', 'style', 'output', 'design-plan', 'review','destination','brief','previous','source','plan','pdf-font-map'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--slides',nargs='+')
    parser.add_argument('--image-capability',choices=('available','unavailable','unverified'))
    parser.add_argument('--source-evidence')
    parser.add_argument('--mode', choices=('1','2','3','style_only','style_and_text','redesign'))
    for name in ('validate-only', 'draft', 'next-output', 'fonts', 'test-export', 'pdf-input'):
        parser.add_argument('--' + name, action='store_true')
    args = parser.parse_args()
    common = {'project', 'renderer'}
    allowed = {
        'init': common,
        'doctor': common | {'config', 'fonts', 'test_export', 'pdf_input'},
        'validate': common | {'config', 'scene', 'structure', 'style', 'output', 'design_plan', 'draft', 'validate_only'},
        'build': common | {'config', 'scene', 'structure', 'style', 'output', 'design_plan', 'draft', 'validate_only', 'next_output'},
        'review': {'project', 'output', 'review'},
        'prepare': {'project','config','destination','image_capability','source_evidence'},
        'freeze-content': {'project','structure','brief'},
        'prototype': {'project','config','destination','slides'},
        'compare': {'project','previous','output'},
        'inspect-source': common | {'config','source','style','destination','mode','pdf_font_map'},
        'restyle': common | {'config','source','style','plan','output','draft','next_output','mode'},
    }
    if args.action:
        for key, value in vars(args).items():
            if key not in {'action', 'version'} | allowed[args.action] and value not in (None, False):
                parser.error('--' + key.replace('_', '-') + ' is not supported for ' + args.action)
    try:
        version = (root / 'VERSION').read_text().strip()
        print('DeckSmith ' + version + ' (portable / windows-x64)',
              file=sys.stderr, flush=True)
        if args.version:
            return 0
        if not args.action:
            parser.error('Specify init, doctor, validate, build, review, or --version')
        if sys.platform != 'win32':
            raise ValueError('This PORTABLE bundle supports Windows x64 only.')
        for path in ('runtime/python/python.exe', 'runtime/node/node.exe',
                     'skills/decksmith/node_modules/pptxgenjs/package.json',
                     'skills/decksmith/node_modules/image-size/package.json'):
            if not (root / path).is_file():
                raise ValueError('Incomplete bundle: ' + path + '; extract the complete ZIP.')
        cmd, project = command(root, args)
        return subprocess.run(cmd, cwd=str(project), env=environment(root)).returncode
    except (ValueError, OSError) as error:
        print('DeckSmith: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
