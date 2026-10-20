"""Check distributable paths and package contents using the standard library."""

import json
from pathlib import Path
import re


def main():
    root = Path(__file__).resolve().parents[1]
    marketplace = json.loads((root / '.agents/plugins/marketplace.json').read_text(encoding='utf-8'))
    assert marketplace['name'] == 'sysmac-github', 'Unexpected marketplace identity'
    for entry in marketplace['plugins']:
        assert entry['source']['source'] == 'local'
        relative = entry['source']['path']
        assert relative.startswith('./'), 'Plugin path must be relative to the repository root'
        plugin = (root / relative).resolve()
        assert plugin.is_relative_to(root), 'Plugin path escapes the repository'
        manifest = json.loads((plugin / 'plugin.json').read_text(encoding='utf-8'))
        assert manifest['name'] == entry['name'], 'Plugin identity mismatch'
        assert re.fullmatch(r'\d+\.\d+\.\d+', manifest['version'])
        assert manifest['repository'] == 'https://github.com/INVAREX/sysmac-project-interpretation'
        skills = list((plugin / 'skills').glob('*/SKILL.md'))
        assert skills, 'No packaged skills'
        for skill in skills:
            text = skill.read_text(encoding='utf-8')
            assert text.startswith('---\n')
            assert 'name: sysmac-project-interpretation' in text
            assert 'description:' in text
    for file in root.rglob('*'):
        if not file.is_file() or '.git' in file.parts:
            continue
        if file.suffix == '.md':
            text = file.read_text(encoding='utf-8')
            for target in re.findall(r'\]\(([^)]+)\)', text):
                if target.startswith(('https:', 'http:', '#')):
                    continue
                assert (file.parent / target).exists(), f'Broken link: {file.relative_to(root)} -> {target}'
    print('Repository manifests, package paths and references pass.')


if __name__ == '__main__':
    main()
