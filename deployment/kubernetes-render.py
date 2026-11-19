"""Render namespaced Kubernetes resources from a validated, digest-pinned release."""
import argparse
import importlib.util
import json
from pathlib import Path

ENVIRONMENTS = {'Development': ('sakila-development', 8093), 'QA': ('sakila-qa', 8094), 'Production': ('sakila-production', 8095)}

def render(release, environment):
    spec = importlib.util.spec_from_file_location('release_env', Path(__file__).with_name('release-env.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.render(release)
    namespace, port = ENVIRONMENTS[environment]
    objects = []
    def resource(kind, name, body, api='v1'):
        item = {'apiVersion': api, 'kind': kind, 'metadata': {'name': name, 'namespace': namespace, 'labels': {'app.kubernetes.io/part-of': 'sakila'}}}
        item.update(body)
        objects.append(item)
    def service(name, target, exposed=None):
        resource('Service', name, {'spec': {'selector': {'app': name}, 'ports': [{'port': exposed or target, 'targetPort': target}], 'type': 'ClusterIP'}})
    def secret_env(key):
        return {'secretKeyRef': {'name': 'sakila-database', 'key': key}}
    def workload(name, image, cpu, memory, env, probe, stateful=False, mounts=None):
        container = {'name': name, 'image': image, 'imagePullPolicy': 'IfNotPresent', 'env': env,
            'resources': {'requests': {'cpu': '25m', 'memory': '256Mi' if stateful else '32Mi'}, 'limits': {'cpu': cpu, 'memory': memory}},
            'readinessProbe': dict(probe, periodSeconds=5, timeoutSeconds=5, failureThreshold=12),
            'startupProbe': dict(probe, periodSeconds=5, timeoutSeconds=5, failureThreshold=60),
            'livenessProbe': {'tcpSocket': {'port': 3306}, 'periodSeconds': 10} if stateful else {'httpGet': {'path': '/api/live' if name == 'sakila-backend' else '/', 'port': 5000 if name == 'sakila-backend' else 80}, 'periodSeconds': 10}}
        pod = {'imagePullSecrets': [{'name': 'ghcr-pull'}], 'containers': [container]}
        if mounts:
            container['volumeMounts'] = mounts
        body = {'selector': {'matchLabels': {'app': name}}, 'template': {'metadata': {'labels': {'app': name}}, 'spec': pod}}
        if stateful:
            body.update({'replicas': 1, 'serviceName': name, 'volumeClaimTemplates': [{'metadata': {'name': 'mysql-data'}, 'spec': {'accessModes': ['ReadWriteOnce'], 'resources': {'requests': {'storage': '2Gi'}}}}]})
        elif name == 'sakila-frontend':
            body['replicas'] = 1
            pod['volumes'] = [{'name': 'nginx', 'configMap': {'name': 'sakila-nginx'}}]
        resource('StatefulSet' if stateful else 'Deployment', name, {'spec': body}, 'apps/v1')
    db_env = [{'name': 'MYSQL_DATABASE', 'value': 'sakila'}, {'name': 'MYSQL_USER', 'value': 'sakila'}, {'name': 'MYSQL_PASSWORD', 'valueFrom': secret_env('password')}, {'name': 'MYSQL_ROOT_PASSWORD', 'valueFrom': secret_env('root-password')}]
    workload('sakila-mysql', release['images']['mysql'], '1', '768Mi', db_env,
        {'exec': {'command': ['sh', '-c', 'MYSQL_PWD="$MYSQL_PASSWORD" mysql -h 127.0.0.1 -u sakila sakila -Nse "SELECT COUNT(*) FROM film" >/dev/null']}}, True, [{'name': 'mysql-data', 'mountPath': '/var/lib/mysql'}])
    service('sakila-mysql', 3306)
    backend_env = [{'name': k, 'value': v} for k,v in {'NODE_ENV':'production','DB_HOST':'sakila-mysql','DB_PORT':'3306','DB_USER':'sakila','DB_NAME':'sakila','PORT':'5000'}.items()]
    backend_env.append({'name':'DB_PASSWORD','valueFrom':secret_env('password')})
    workload('sakila-backend', release['images']['backend'], '500m', '128Mi', backend_env, {'httpGet': {'path':'/api/health','port':5000}})
    service('sakila-backend', 5000)
    nginx = 'server { listen 80; root /usr/share/nginx/html; index index.html; location / { try_files $uri /index.html; } location /api/ { proxy_pass http://sakila-backend:5000; proxy_set_header Host $host; proxy_connect_timeout 5s; proxy_read_timeout 30s; } }'
    resource('ConfigMap', 'sakila-nginx', {'data': {'default.conf': nginx}})
    workload('sakila-frontend', release['images']['frontend'], '250m', '64Mi', [], {'httpGet': {'path':'/api/health','port':80}}, mounts=[{'name':'nginx','mountPath':'/etc/nginx/conf.d','readOnly':True}])
    service('sakila-frontend', 80)
    return {'apiVersion': 'v1', 'kind': 'List', 'items': objects}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('release')
    parser.add_argument('environment', choices=ENVIRONMENTS)
    args = parser.parse_args()
    print(json.dumps(render(json.loads(Path(args.release).read_text()), args.environment)))
