import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('release_env', Path(__file__).resolve().parents[1] / 'deployment/release-env.py')
release_env = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_env)


def manifest():
    return {'version': '0.0.3', 'images': {
        service: f'ghcr.io/example/sakila-{service}@sha256:' + 'a' * 64
        for service in ['mysql', 'backend', 'frontend']
    }}


def test_release_requires_exact_published_images():
    output = release_env.render(manifest())
    assert 'RELEASE_VERSION=0.0.3\n' in output
    assert len(output.splitlines()) == 4


@pytest.mark.parametrize('image', ['ghcr.io/example/backend:latest', 'evil.example/backend@sha256:' + 'a'*64, '$(touch /tmp/unsafe)', 'image\nDB_PASSWORD=unsafe'])
def test_rejects_unpinned_or_injected_image_metadata(image):
    data = manifest()
    data['images']['backend'] = image
    with pytest.raises(ValueError):
        release_env.render(data)


def test_rejects_version_path_traversal():
    data = manifest()
    data['version'] = '../../outside'
    with pytest.raises(ValueError):
        release_env.render(data)
