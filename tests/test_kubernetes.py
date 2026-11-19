"""Check Kubernetes isolation, persistent data and safe deployment entry points."""
import importlib.util
import os
from pathlib import Path
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('kubernetes_render',ROOT/'deployment/kubernetes-render.py')
renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)

@pytest.fixture
def release():
    return {'version':'0.2.0','images':{name:'ghcr.io/example/'+name+'@sha256:'+'a'*64 for name in ['mysql','backend','frontend']}}

@pytest.mark.parametrize('environment,namespace', [('Development','sakila-development'),('QA','sakila-qa'),('Production','sakila-production')])
def test_environment_isolation_and_persistent_database(release,environment,namespace):
    items=renderer.render(release,environment)['items']
    assert all(x['metadata']['namespace']==namespace for x in items)
    db=next(x for x in items if x['kind']=='StatefulSet')
    assert db['spec']['replicas']==1
    assert db['spec']['volumeClaimTemplates'][0]['spec']['accessModes']==['ReadWriteOnce']
    for item in items:
        if item['kind'] not in ['StatefulSet','Deployment']:continue
        pod=item['spec']['template']['spec']; container=pod['containers'][0]
        assert container['image'] in release['images'].values()
        assert pod['imagePullSecrets']==[{'name':'ghcr-pull'}]
        assert container['resources']['limits']['memory']
        assert container['startupProbe'] and container['readinessProbe'] and container['livenessProbe']
        for env in container['env']:
            if 'PASSWORD' in env['name']:assert env['valueFrom']['secretKeyRef']['name']=='sakila-database'
    frontend=next(x for x in items if x['kind']=='Service' and x['metadata']['name']=='sakila-frontend')
    assert frontend['spec']['type']=='ClusterIP'
    backend=next(x for x in items if x['kind']=='Deployment' and x['metadata']['name']=='sakila-backend')
    assert 'replicas' not in backend['spec'] # subsequent releases must preserve scaling


def test_renderer_rejects_mutable_images(release):
    release['images']['backend']='ghcr.io/example/backend:latest'
    with pytest.raises(ValueError):renderer.render(release,'Production')

@pytest.mark.skipif(os.name!='posix',reason='Target uses Linux fcntl')
@pytest.mark.parametrize('project,environment',[('Ecommerce-DevOps-Lab','Production'),('Sakila-Movie-Rental-Portal','Unknown')])
def test_wrong_destination_rejected_before_kubectl(tmp_path,project,environment):
    fake=tmp_path/'kubectl'; marker=tmp_path/'called'
    fake.write_text('#!/bin/sh\ntouch '+str(marker)+'\n');fake.chmod(0o755)
    result=subprocess.run(['python3',str(ROOT/'deployment/deploy-kubernetes.py')],env=dict(os.environ,PATH=str(tmp_path)+os.pathsep+os.environ['PATH'],SAKILA_PROJECT=project,SAKILA_ENVIRONMENT=environment),capture_output=True,text=True)
    assert result.returncode!=0
    assert not marker.exists()
