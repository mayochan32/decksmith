"""Copy the complete settings template without overwriting user configuration."""
import argparse
from pathlib import Path


def initialize(project, renderer=None):
    project = Path(project).resolve()
    source = Path(__file__).resolve().parents[1] / 'assets/decksmith.yaml'
    content = source.read_text(encoding='utf-8')
    if renderer is not None:
        if renderer not in ('libreoffice', 'powerpoint', 'none'):
            raise ValueError('Unknown renderer')
        content = content.replace('renderer: libreoffice', 'renderer: ' + renderer, 1)
    project.mkdir(parents=True, exist_ok=True)
    target = project / 'decksmith.yaml'
    with target.open('x', encoding='utf-8') as out:
        out.write(content)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--renderer', choices=('libreoffice', 'powerpoint', 'none'))
    args = parser.parse_args()
    try:
        print(initialize(args.project, args.renderer))
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + '\n')
