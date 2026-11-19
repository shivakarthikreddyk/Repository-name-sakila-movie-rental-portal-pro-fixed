"""Exercise Linux deployment success and failure transitions using a fake Docker CLI."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import pytest

pytestmark = pytest.mark.skipif(os.name != 'posix', reason='Tentacle Bash script runs on Linux')
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def deployment(tmp_path):
    package = tmp_path / 'package'
    package.mkdir()
    for name in ['deploy.sh', 'release-env.py']:
        shutil.copy(ROOT / 'deployment' / name, package / name)
    shutil.copy(ROOT / 'docker-compose.yml', package / 'docker-compose.yml')
    (package / 'smoke.py').write_text('print("smoke checked")\n')
    (package / 'release.json').write_text(json.dumps({'version': '0.0.3', 'images': {
        service: f'ghcr.io/example/{service}@sha256:' + 'a' * 64
        for service in ['mysql', 'backend', 'frontend']
    }}))
    fake_bin = tmp_path / 'bin'
    fake_bin.mkdir()
    docker = fake_bin / 'docker'
    docker.write_text('''#!/usr/bin/env python3
import json, os, sys
with open(os.environ['DOCKER_CALLS'], 'a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\\n')
mode = os.environ.get('FAIL_MODE')
if mode == 'pull' and 'pull' in sys.argv: sys.exit(17)
if mode == 'rollout' and 'up' in sys.argv and '--no-deps' not in sys.argv: sys.exit(23)
''')
    docker.chmod(0o755)
    env = dict(os.environ, PATH=f'{fake_bin}{os.pathsep}{os.environ["PATH"]}',
               DB_PASSWORD='sensitive-test-app', MYSQL_ROOT_PASSWORD='sensitive-test-root',
               DEPLOY_ROOT=str(tmp_path / 'target'), DOCKER_CALLS=str(tmp_path / 'docker.jsonl'),
               APP_PORT='8093', GHCR_USERNAME='', GHCR_TOKEN='')
    return package, env


def run(deployment, **changes):
    package, env = deployment
    result = subprocess.run(['bash', str(package / 'deploy.sh')], env=dict(env, **changes),
                            capture_output=True, text=True, timeout=20)
    log = Path(env['DOCKER_CALLS'])
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    assert not any('down' in call for call in calls)
    assert env['DB_PASSWORD'] not in result.stdout + result.stderr
    return result, calls


def test_success_records_release_without_saving_passwords(deployment):
    result, calls = run(deployment)
    assert result.returncode == 0, result.stdout + result.stderr
    target = Path(deployment[1]['DEPLOY_ROOT'])
    assert (target / 'current/release.json').exists()
    assert not list(target.glob('.docker-auth.*'))
    assert not list(target.glob('.release-env.*'))
    assert 'sensitive-test' not in (target / 'current/images.env').read_text()
    assert next(i for i, call in enumerate(calls) if 'pull' in call) < next(i for i, call in enumerate(calls) if 'up' in call)


def test_pull_failure_does_not_touch_running_containers(deployment):
    result, calls = run(deployment, FAIL_MODE='pull')
    assert result.returncode == 17
    assert not any('up' in call for call in calls)
    assert not (Path(deployment[1]['DEPLOY_ROOT']) / 'current').exists()


def test_rollout_failure_restores_previous_application_and_still_fails(deployment):
    result, _ = run(deployment)
    assert result.returncode == 0
    target = Path(deployment[1]['DEPLOY_ROOT'])
    previous = (target / 'current').resolve()
    result, calls = run(deployment, FAIL_MODE='rollout')
    assert result.returncode == 23
    rollback = [call for call in calls if '--no-deps' in call]
    assert len(rollback) == 1
    assert rollback[0][-2:] == ['backend', 'frontend']
    assert 'mysql' not in rollback[0]
    assert (target / 'current').resolve() == previous


@pytest.mark.parametrize('environment,project,port,compose,deploy_root', [
    ('QA', 'Sakila-Movie-Rental-Portal', '8093', 'sakila-production', '/opt/sakila'),
    ('Production', 'Sakila-Movie-Rental-Portal', '8094', 'sakila-qa', '/opt/sakila-qa'),
    ('Development', 'Sakila-Movie-Rental-Portal', '8092', 'sakila-production', '/opt/sakila'),
    ('Production', 'Ecommerce-DevOps-Lab', '8095', 'sakila-prod', '/opt/sakila-prod'),
    ('Unknown', 'Sakila-Movie-Rental-Portal', '8093', 'sakila-production', '/opt/sakila'),
])
def test_wrong_environment_scope_never_reaches_docker(deployment, environment, project,
                                                     port, compose, deploy_root):
    package, env = deployment
    helper = package / 'octopus-helper.sh'
    helper.write_text('''get_octopusvariable() {
      case "$1" in
        Octopus.Environment.Name) printf '%s' "$TEST_ENVIRONMENT" ;;
        Octopus.Project.Name) printf '%s' "$TEST_PROJECT" ;;
        Sakila.Port) printf '%s' "$APP_PORT" ;;
        Sakila.ComposeProject) printf '%s' "$COMPOSE_PROJECT_NAME" ;;
        Sakila.DeployRoot) printf '%s' "$DEPLOY_ROOT" ;;
        Sakila.BindAddress) printf '127.0.0.1' ;;
        Sakila.DbPassword) printf '%s' "$DB_PASSWORD" ;;
        Sakila.RootPassword) printf '%s' "$MYSQL_ROOT_PASSWORD" ;;
      esac
    }
''')
    result, calls = run(deployment, BASH_ENV=str(helper), TEST_ENVIRONMENT=environment,
                        TEST_PROJECT=project, APP_PORT=port,
                        COMPOSE_PROJECT_NAME=compose, DEPLOY_ROOT=deploy_root)
    assert result.returncode != 0
    assert calls == []
