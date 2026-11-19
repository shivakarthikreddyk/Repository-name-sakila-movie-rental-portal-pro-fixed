# GitHub Actions → private GHCR → Octopus → Docker Desktop Kubernetes

The Default space uses the dedicated **Sakila-Movie-Rental-Portal** project.
**Ecommerce-DevOps-Lab** remains its separate Python/Docker application on 8092.

Follow [the Kubernetes target guide](../k8s/README.md) for bootstrap, namespace
permissions, database migration, resource limits and scaling commands.

## Environment mapping

| Environment | Namespace | Port | Legacy Compose project retained for recovery |
| --- | --- | --- | --- |
| Development | sakila-development | 8093 | sakila-production |
| QA | sakila-qa | 8094 | sakila-qa |
| Production | sakila-production | 8095 | sakila-prod |

The renderer generates ClusterIP Services, app Deployments, MySQL StatefulSets
and persistent claims. A target systemd unit provides localhost-only access.

## Octopus configuration

Use the **Sakila Development QA Production** lifecycle with ordered, required
Development, QA and Production phases. The process is:

1. 01 - Validate Deployment.
2. Approve Sakila Production: Production-only, required, blocking, AI-blocked;
   responsible team **Sakila Production Approvers**, containing only the human
   account. Its approval role is scoped to Sakila Production. CI cannot approve.
3. 02 - Deploy Sakila Kubernetes: required, run after success on sakila-portal
   tagged targets in Development, QA and Production. Bash script deploy.sh from
   package sakila-deploy in the built-in feed. No inline wrapper or substitution.

Variables:

- Sakila.DbPassword and Sakila.RootPassword: sensitive, separate per environment.
- GHCR.KubernetesToken: sensitive, durable classic token with read:packages.
- GHCR.Username: account owning that token. The workflow's actor currently matches.
- GHCR.Token: legacy prompted job token supplied by workflows; the Kubernetes
  deployer uses GHCR.KubernetesToken for durable image pull Secrets instead.
- Existing Sakila.Port/DeployRoot/ComposeProject values remain for historical
  snapshots; Kubernetes derives its destination from the exact environment name.

Do not rotate existing MySQL credentials by only editing variables: change the
account in MySQL through a reviewed procedure first. Keep secrets out of Git.

## GitHub configuration

Repository variables remain:

| Variable | Value |
| --- | --- |
| OCTOPUS_URL | https://karthik-devops-lab.octopus.app |
| OCTOPUS_SPACE | Default |
| OCTOPUS_PROJECT | Sakila-Movie-Rental-Portal |
| OCTOPUS_ENVIRONMENT | Development |
| OCTOPUS_SERVICE_ACCOUNT_ID | b536a28d-95b4-4615-b450-22dc13fc6d7f |
| OCTOPUS_ENABLED | true |

OIDC remains limited to main and v* identities for this repository with immutable
owner/repository subjects. The Sakila CI Delivery team stays scoped to Sakila
and the three environments, with publishing/deployment/view permissions only.
Do not grant intervention approval or process editing to CI.

CI runs unit, API, browser, persistence and deployment tests, publishes private
images, and packages the image digests with the Kubernetes deployer. New releases
carry the **Sakila Kubernetes environments v1.** marker. CD deploys Development,
waits for success, then deploys QA and waits for success.

Run **Promote Sakila release to Production** on main with the exact QA-tested
release. The workflow verifies the Kubernetes marker and approval-before-deploy
snapshot. The human must Assign to me and Proceed in Octopus. The workflow then
waits for the actual result. Do not promote historical Compose releases after
cutover; those snapshots still contain Compose scripts.

Check /api/health on ports 8093, 8094 and 8095. Inspect rollout status, Pods and
PVCs in the matching namespaces. The first migration retains protected backups
and old Compose volumes. Never delete a database claim/volume to fix a failed
rollout. Application rollback cannot reverse a database schema migration.
