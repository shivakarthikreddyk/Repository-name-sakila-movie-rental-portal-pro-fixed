"""Validate release metadata before exporting image references to Compose."""
import json
from pathlib import Path
import re
import sys


def render(manifest):
    version = manifest['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?', version):
        raise ValueError('Invalid release version')
    lines = [f'RELEASE_VERSION={version}']
    for service, key in [('mysql', 'DATABASE_IMAGE'), ('backend', 'BACKEND_IMAGE'), ('frontend', 'FRONTEND_IMAGE')]:
        image = manifest['images'][service]
        if not re.fullmatch(r'ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}', image):
            raise ValueError(f'{service} must use a GHCR digest reference')
        lines.append(f'{key}={image}')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    print(render(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))), end='')
