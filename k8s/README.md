# Sakila Kubernetes deployment

GitHub Actions tests the React/Express/MySQL application, publishes the same
three tested images privately to GHCR, and packages their digests. Octopus uses
`deployment/deploy.sh` and `deploy-kubernetes.py` on the Ubuntu polling Tentacle.
The image renderer validates GHCR digests before creating Kubernetes objects.

| Environment | Namespace | Local port |
| --- | --- | --- |
| Development | sakila-development | 8093 |
| QA | sakila-qa | 8094 |
| Production | sakila-production | 8095 |

Each namespace has its own DB Secret, registry pull Secret, Services, frontend
and backend Deployments, and a singleton MySQL StatefulSet with a 2 GiB claim.
Requests are 25m CPU and 32 MiB per app / 256 MiB for MySQL; memory limits are
64 MiB frontend, 128 MiB backend and 768 MiB MySQL. This is a single-host lab.
A local-only systemd port-forward preserves existing URLs without an ingress
controller. Keep Docker Desktop and Ubuntu running. The old default-namespace
Sakila application and unrelated workloads are not part of this pipeline.

## Target bootstrap

Run `python scripts/install-kubernetes-target.py` from the Windows checkout
using the administrator docker-desktop context. It provisions only the three
Sakila namespaces and installs a root-only kubeconfig in Ubuntu under
`/etc/sakila-kubernetes/config`. A dedicated service account receives namespace
roles; it cannot edit default/Ecommerce or delete PVCs. Its long-lived token is
for this local lab and must be revoked/replaced if the target is retired.

Octopus retains environment-scoped `Sakila.DbPassword` and
`Sakila.RootPassword`. `GHCR.KubernetesToken` is sensitive and contains a
read:packages classic token for the account in `GHCR.Username`. Unlike a job
token, it must remain valid for later Pod replacement/scaling. Renew it before
expiry by updating Octopus and redeploying each environment to refresh Secrets.
Never commit tokens, kubeconfigs, SQL dumps or database passwords.

## First migration

The deployment quiesces the matching legacy frontend/backend, dumps the source
database into a protected backup under that environment's /opt directory,
imports into the new namespace database, and compares film/customer/rental/
actor/payment row counts. It waits for app readiness and runs frontend, DB,
dashboard and list smoke checks. Only then does it stop the legacy database and
record successful migration. The legacy containers and volumes are retained.
A failed first migration restarts the legacy stack. Subsequent failed app
rollouts restore previous app image references and fail the Octopus task.
Database/schema changes require a separate reviewed migration and backup plan.

Production remains gated by the required, non-skippable Approve Sakila Production
step, assigned to Sakila Production Approvers. The CI account cannot approve.
Promote the same release after Development and QA succeed through the manual
GitHub Production promotion workflow. Releases made before the Kubernetes
cutover have Compose scripts and must not be promoted after migration.

## Scaling practice

Scale only the backend first (MySQL stays singleton):

```bash
kubectl --context docker-desktop -n sakila-qa scale deployment sakila-backend --replicas=2
kubectl --context docker-desktop -n sakila-qa get pods -w
kubectl --context docker-desktop -n sakila-qa scale deployment sakila-backend --replicas=1
```

The renderer omits backend replicas so later releases preserve the current
replica count. The ClusterIP backend Service routes to ready Pods. No metrics
server or HPA is installed for this minimum-resource exercise.

The old standalone YAML files in this folder are historical and must not be
applied. Use the release-driven renderer and Octopus deployment instead.
