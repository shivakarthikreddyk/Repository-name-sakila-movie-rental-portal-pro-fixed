"""One-time local admin bootstrap. Run on Windows; writes root-only target config in WSL."""
import base64,json,subprocess,time

def kubectl(*args,data=None):
    r=subprocess.run(['kubectl','--context=docker-desktop',*args],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    return r.stdout

def apply(obj): kubectl('apply','-f','-',data=json.dumps(obj).encode())

namespaces=['sakila-development','sakila-qa','sakila-production']
for ns in namespaces:
    apply({'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns,'labels':{'app.kubernetes.io/part-of':'sakila'}}})
apply({'apiVersion':'v1','kind':'ServiceAccount','metadata':{'name':'sakila-octopus','namespace':namespaces[0]}})
for ns in namespaces:
    rules=[{'apiGroups':[''],'resources':['services','configmaps','secrets'],'verbs':['get','list','watch','create','patch','update']},
           {'apiGroups':[''],'resources':['pods','pods/log','persistentvolumeclaims'],'verbs':['get','list','watch']},
           {'apiGroups':[''],'resources':['pods/exec','pods/portforward'],'verbs':['get','create']},
           {'apiGroups':['apps'],'resources':['deployments','statefulsets','replicasets','deployments/scale'],'verbs':['get','list','watch','create','patch','update']}]
    apply({'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':{'name':'sakila-deployer','namespace':ns},'rules':rules})
    apply({'apiVersion':'rbac.authorization.k8s.io/v1','kind':'RoleBinding','metadata':{'name':'sakila-octopus','namespace':ns},'subjects':[{'kind':'ServiceAccount','name':'sakila-octopus','namespace':namespaces[0]}],'roleRef':{'kind':'Role','name':'sakila-deployer','apiGroup':'rbac.authorization.k8s.io'}})
apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'sakila-octopus-access','namespace':namespaces[0],'annotations':{'kubernetes.io/service-account.name':'sakila-octopus'}},'type':'kubernetes.io/service-account-token'})
for attempt in range(20):
    secret=json.loads(kubectl('-n',namespaces[0],'get','secret','sakila-octopus-access','-o','json'))
    if secret.get('data',{}).get('token'): break
    time.sleep(1)
else: raise SystemExit('Service account credential was not provisioned')
original=json.loads(kubectl('config','view','--raw','--flatten','--minify','-o','json'))
cluster=original['clusters'][0]['cluster']
config={'apiVersion':'v1','kind':'Config','clusters':[{'name':'docker-desktop','cluster':{'server':cluster['server'],'certificate-authority-data':cluster['certificate-authority-data']}}],
        'contexts':[{'name':'sakila-octopus','context':{'cluster':'docker-desktop','user':'sakila-octopus','namespace':namespaces[0]}}],
        'current-context':'sakila-octopus','users':[{'name':'sakila-octopus','user':{'token':base64.b64decode(secret['data']['token']).decode()}}]}
subprocess.run(['wsl','-d','Ubuntu','-u','root','--','bash','-lc','umask 077; mkdir -p /etc/sakila-kubernetes; cat > /etc/sakila-kubernetes/config; chmod 600 /etc/sakila-kubernetes/config'],input=json.dumps(config).encode(),check=True)
print('Installed root-only Sakila kubeconfig with access limited to three Sakila namespaces. No PVC deletion permission.')
