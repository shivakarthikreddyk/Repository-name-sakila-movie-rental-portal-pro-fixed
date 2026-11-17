"""Package only deployment inputs, pinning images to their published digests."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', default='artifacts')
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?', args.version):
        parser.error('Version must be a SemVer without build metadata')
    root = Path(__file__).resolve().parents[1]
    images = {}
    for service, key in [('mysql', 'DATABASE_IMAGE'), ('backend', 'BACKEND_IMAGE'), ('frontend', 'FRONTEND_IMAGE')]:
        tag = os.environ[key]
        refs = json.loads(subprocess.check_output(
            ['docker', 'image', 'inspect', tag, '--format', '{{json .RepoDigests}}'], text=True))
        repository = tag.rsplit(':', 1)[0]
        matches = [ref for ref in refs or [] if ref.startswith(repository + '@sha256:')]
        if len(matches) != 1:
            raise SystemExit(f'Expected one published digest for {service}; push the tested image first')
        images[service] = matches[0]
    manifest = {'version': args.version, 'commit': args.commit, 'images': images}
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    package = output / f'sakila-deploy.{args.version}.zip'
    with zipfile.ZipFile(package, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(root / 'docker-compose.yml', 'docker-compose.yml')
        for filename in ['deploy.sh', 'smoke.py', 'release-env.py']:
            archive.write(root / 'deployment' / filename, filename)
        archive.writestr('release.json', json.dumps(manifest, indent=2) + '\n')
    print(package)


if __name__ == '__main__':
    main()
