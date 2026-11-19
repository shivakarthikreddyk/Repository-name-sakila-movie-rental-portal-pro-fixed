"""Octopus target deployment. Never print credentials or delete persistent volumes."""
import base64
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
ENVIRONMENTS = {'Development': ('sakila-development',8093,'sakila-production','/opt/sakila'), 'QA': ('sakila-qa',8094,'sakila-qa','/opt/sakila-qa'), 'Production': ('sakila-production',8095,'sakila-prod','/opt/sakila-prod')}

def run(args, *, data=None, capture=True, stdout=None):
    result = subprocess.run(args, input=data, stdout=stdout if stdout else subprocess.PIPE if capture else None, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        # Commands carrying secret JSON use stdin, never argv. Error bodies can echo Secret values.
        raise RuntimeError('Command failed: ' + ' '.join(args[:4]) + ' (exit ' + str(result.returncode) + ')')
    return result.stdout

def main():
    environment = os.environ.get('SAKILA_ENVIRONMENT')
    if os.environ.get('SAKILA_PROJECT') != 'Sakila-Movie-Rental-Portal' or environment not in ENVIRONMENTS:
        raise SystemExit('Wrong Sakila project or environment')
    namespace,port,legacy,deploy_root = ENVIRONMENTS[environment]
    required = ['DB_PASSWORD','MYSQL_ROOT_PASSWORD','GHCR_USERNAME','GHCR_TOKEN']
    if any(not os.environ.get(k) for k in required):
        raise SystemExit('Database and durable private-GHCR credentials are required')
    os.environ['KUBECONFIG'] = '/etc/sakila-kubernetes/config'
    kube = ['kubectl','--context','sakila-octopus','-n',namespace]
    def k(*args, data=None):
        return run(kube+list(args),data=data)
    def apply(obj):
        return k('apply','--server-side','--field-manager=sakila-octopus','-f','-', data=json.dumps(obj).encode())
    def query(command):
        return json.loads(k(*command))
    def exists(kind,name):
        return bool(k('get',kind,name,'--ignore-not-found','-o','name').strip())
    def sql_counts(command):
        statement='SELECT COUNT(*) FROM sakila.film; SELECT COUNT(*) FROM sakila.customer; SELECT COUNT(*) FROM sakila.rental; SELECT COUNT(*) FROM sakila.actor; SELECT COUNT(*) FROM sakila.payment;'
        return run(command+['sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -h 127.0.0.1 -u root -Nse '+ __import__('shlex').quote(statement)]).strip()
    root = Path(deploy_root); root.mkdir(parents=True,exist_ok=True)
    lock = (root/'.deploy.lock').open('w'); fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    spec=importlib.util.spec_from_file_location('renderer', ROOT/'kubernetes-render.py')
    renderer=importlib.util.module_from_spec(spec); spec.loader.exec_module(renderer)
    release=json.loads((ROOT/'release.json').read_text())
    resources=renderer.render(release,environment)
    apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'sakila-database','namespace':namespace},'type':'Opaque','data':{'password':base64.b64encode(os.environ['DB_PASSWORD'].encode()).decode(),'root-password':base64.b64encode(os.environ['MYSQL_ROOT_PASSWORD'].encode()).decode()}})
    auth=base64.b64encode((os.environ['GHCR_USERNAME']+':'+os.environ['GHCR_TOKEN']).encode()).decode()
    config={'auths':{'ghcr.io':{'auth':auth}}}
    apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'ghcr-pull','namespace':namespace},'type':'kubernetes.io/dockerconfigjson','data':{'.dockerconfigjson':base64.b64encode(json.dumps(config).encode()).decode()}})
    os.environ.pop('GHCR_TOKEN',None)
    marker='sakila-compose-migration'
    migrated=exists('configmap',marker)
    # Create DB and services first, leaving applications unexposed during import.
    db_objects=[o for o in resources['items'] if o['kind']=='StatefulSet' or o['kind']=='Service' and o['metadata']['name']=='sakila-mysql']
    app_objects=[o for o in resources['items'] if o not in db_objects]
    for obj in db_objects: apply(obj)
    k('rollout','status','statefulset/sakila-mysql','--timeout=420s')
    stopped=False
    migration_data=None
    unit='sakila-'+environment.lower()+'-port-forward.service'
    previous=[]
    for kind,name in [('deployment','sakila-backend'),('deployment','sakila-frontend'),('statefulset','sakila-mysql')]:
        if exists(kind,name):
            obj=query(['get',kind,name,'-o','json'])
            previous.append((kind,name,obj['spec']['template']['spec']['containers'][0]['image']))
    try:
        if not migrated:
            source=legacy+'-mysql-1'
            state=json.loads(run(['docker','inspect',source]))[0]['State']['Running']
            if not state: raise RuntimeError('Legacy database must be running for migration')
            run(['docker','stop',legacy+'-frontend-1',legacy+'-backend-1'])
            stopped=True
            source_command=['docker','exec',source]
            before=sql_counts(source_command)
            backup_dir=root/'backups'; backup_dir.mkdir(exist_ok=True,mode=0o700)
            fd,backup=tempfile.mkstemp(prefix='before-kubernetes-',suffix='.sql',dir=backup_dir)
            with os.fdopen(fd,'wb') as output:
                run(source_command+['sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -h 127.0.0.1 -u root --single-transaction --routines --triggers --events --set-gtid-purged=OFF --add-drop-database --databases sakila'],stdout=output)
            with open(backup,'rb') as source_file:
                result=subprocess.run(kube+['exec','-i','sakila-mysql-0','--','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -h 127.0.0.1 -u root'],stdin=source_file,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            if result.returncode: raise RuntimeError('Database import failed; protected backup retained')
            after=sql_counts(kube+['exec','sakila-mysql-0','--'])
            if before!=after: raise RuntimeError('Source/target row counts differ')
            migration_data={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':marker,'namespace':namespace},'data':{'source':source,'rowCounts':after.decode(),'backup':backup}}
        for obj in app_objects: apply(obj)
        for name in ['sakila-backend','sakila-frontend']:
            k('rollout','status','deployment/'+name,'--timeout=300s')
        # A local-only systemd forward preserves the existing URLs without ingress controllers.
        unit_text='[Unit]\nDescription=Sakila '+environment+' local Kubernetes access\nAfter=network-online.target\n[Service]\nEnvironment=KUBECONFIG=/etc/sakila-kubernetes/config\nExecStart=/usr/local/bin/kubectl --context=sakila-octopus -n '+namespace+' port-forward --address=127.0.0.1 service/sakila-frontend '+str(port)+':80\nRestart=always\nRestartSec=3\n[Install]\nWantedBy=multi-user.target\n'
        Path('/etc/systemd/system',unit).write_text(unit_text)
        run(['systemctl','daemon-reload']); run(['systemctl','enable','--now',unit])
        run(['python3',str(ROOT/'smoke.py'),'http://127.0.0.1:'+str(port)],capture=False)
        if migration_data: apply(migration_data)
        # Stop only the matching legacy database after end-to-end checks; its volume is retained.
        run(['docker','stop',legacy+'-mysql-1'])
        release_dir=root/'kubernetes-releases'/release['version']; release_dir.mkdir(parents=True,exist_ok=True)
        (release_dir/'release.json').write_text(json.dumps(release,indent=2))
        print('Successfully deployed Kubernetes release '+release['version']+' in '+namespace+' on port '+str(port))
    except Exception:
        if stopped:
            subprocess.run(['systemctl','stop',unit],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            run(['docker','start',legacy+'-mysql-1',legacy+'-backend-1',legacy+'-frontend-1'])
        else:
            for kind,name,image in previous:
                # Keep the DB on its current image; app rollback cannot reverse schema changes.
                if kind=='deployment': k('set','image',kind+'/'+name,name+'='+image)
        raise

if __name__=='__main__':
    os.umask(0o077)
    try: main()
    except Exception as error:
        print('Kubernetes deployment failed: '+str(error),file=sys.stderr)
        sys.exit(1)
