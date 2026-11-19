# GitHub Actions → GHCR → Octopus → Ubuntu WSL2

This guide connects the supplied application to
`https://karthik-devops-lab.octopus.app` using the **Default** space
(`Spaces-1`), dedicated **Sakila-Movie-Rental-Portal** project, and sequential
**Development → QA → Production** environments.
Ecommerce-DevOps-Lab is a separate Python application and owns port 8092.
Sakila uses ports 8093, 8094, and 8095. Production requires human approval.

## 1. Prepare the actual Tentacle target

In Windows, `wsl --list --verbose` lists the available distributions. Enter the
one containing your Tentacle service (the inspected machine uses `Ubuntu`).
Keep WSL2 and Windows awake while a deployment is running. A stopped WSL
distribution cannot poll Octopus Cloud.

Use one Docker installation:

- Docker Desktop: Settings → Resources → WSL Integration → enable **Ubuntu**
  → Apply & Restart. Verify Linux container mode and `docker info` in Ubuntu.
- Or Docker Engine and the Compose plugin installed directly in that Ubuntu
  distribution, following the official Docker Ubuntu installation guide.

Run `bash scripts/check-target.sh` **as the Tentacle service user**, not just
your interactive account. Check the service with:

```bash
systemctl show Tentacle -p User -p ActiveState
docker info
docker compose version
python3 --version
```

The target needs Bash, Python 3, `flock`, Docker, and Compose with
`up --wait --wait-timeout` support (Compose 2.20+). It does not build images or
need Node/npm/pytest. If using a non-root service account, grant that account
Docker access and ownership of `/opt/sakila`, then restart its service so group
membership takes effect. Docker access permits control of containers and host mounts.

In Octopus **Infrastructure → Deployment Targets**, verify the existing Linux
polling Tentacle is healthy, assigned to Development, QA, and Production, and has the
target role/tag `sakila-portal` (a separate tag for this application). Prefer Octopus's generated Linux polling
installation/registration script if creating a new target; keep credentials out of Git.

Only one application can own port 8093. If the local development Compose stack
uses the same Docker daemon, stop it with `docker compose down` before the first
Octopus deployment. Its data remains in the development project's volume.

## 2. Configure the project variables

Select the existing **Sakila-Movie-Rental-Portal** Octopus project and verify it is
**non-version-controlled**. This package-based workflow snapshots the scripts in its ZIP;
it does not require Octopus Config as Code.

Add these project variables, scoped to the target environment as appropriate:

| Variable | Value | Sensitive? |
| --- | --- | --- |
| `Sakila.DbPassword` | A unique application database password | Yes |
| `Sakila.RootPassword` | A separate unique database root password | Yes |
| `Sakila.Port` | `8093` | No |
| `Sakila.BindAddress` | `127.0.0.1` for local Windows/WSL access | No |
| `Sakila.DeployRoot` | `/opt/sakila` | No |
| `Sakila.ComposeProject` | `sakila-production` | No |
| `GHCR.Username` | Required prompted variable; supplied by the workflow as `github.actor` | No |
| `GHCR.Token` | Required prompted variable; supplied by the workflow as its temporary `GITHUB_TOKEN` | Yes |

Use these exact environment-scoped overrides. The deployment script rejects
any other project/environment/port/Compose-project/directory combination before
running Docker. All three bind to `127.0.0.1`.

| Octopus environment | `Sakila.Port` | `Sakila.ComposeProject` | `Sakila.DeployRoot` | Database volume |
| --- | --- | --- | --- | --- |
| Development | 8093 | sakila-production | /opt/sakila | sakila-production_mysql-data |
| QA | 8094 | sakila-qa | /opt/sakila-qa | sakila-qa_mysql-data |
| Production | 8095 | sakila-prod | /opt/sakila-prod | sakila-prod_mysql-data |

Development keeps its legacy Compose name `sakila-production` to preserve the
existing database. It is still the Development environment. Give QA and Production
their own sensitive `Sakila.DbPassword` and `Sakila.RootPassword` values.
New environments initialize their own sample databases; they do not copy Development data.

Keep the three GHCR packages private. Configure both GHCR variables as
**prompted and required**, with no stored default; make `GHCR.Token` sensitive.
The CD job has `packages: read` and passes its temporary `GITHUB_TOKEN` to
Octopus for this deployment only. It waits for deployment completion so the
token remains valid during image pulls. Docker login uses a temporary directory
which the deployment script removes on exit. No permanent GitHub PAT is needed.

The token expires when the GitHub job ends. A later manual deployment from the
Octopus portal requires a fresh package-read token entered in that prompt, or
use a new pipeline release. Do not reuse a token from a previous deployment.

Keep the database passwords, Compose project name, and deployment directory
stable between releases. The project name determines the persistent volume.
Changing it creates a different database volume. Rotating MySQL credentials
requires changing the account inside MySQL before updating Octopus values.

## 3. Configure the deployment process

The workflow publishes `sakila-deploy.<version>.zip` into the **Octopus built-in
package feed**. GHCR holds Docker images; the built-in feed holds scripts and
the release's image digest manifest.

Assign the dedicated **Sakila Development QA Production** lifecycle to Sakila.
Create three ordered phases, each containing only its matching environment,
with **All must complete** and manually queued deployment. GitHub queues
Development and QA in sequence; the separate promotion workflow queues Production.
Keep Ecommerce on its original lifecycle.

The Sakila process has validation, **Approve Sakila Production**, then
**02 - Deploy Sakila Docker Compose**. Configure the approval step for Production
only, responsible team **Sakila Production Approvers**, required/non-skippable,
blocking other deployments, and preventing AI agents from actioning it.
The CI service account must not belong to that team or have intervention permissions.

The Default-space approver team contains only the personal human account. Its
**Sakila Production Approval** role has `EnvironmentView`, `ProjectView`,
`TaskView`, `InterruptionView`, and `InterruptionViewSubmitResponsible`, scoped
to Sakila-Movie-Rental-Portal and Production. Do not use Octopus Administrators
as the responsible team unless the intended human approver actually belongs
to it. A team with only `octoadmin` leaves the personal account unable to assign
or proceed. After changing the gate, create a fresh release: existing releases
retain the old process snapshot.

Configure the Docker **Run a Script** step:

1. Execution location: **Run on each deployment target**.
2. Target role/tag: `sakila-portal`, scoped to Development, QA, and Production.
3. Script source: **Script file inside a package**.
4. Package feed: **Octopus Server (built-in)**.
5. Package ID: **`sakila-deploy`**.
6. Script file: **`deploy.sh`** (at the ZIP root).
7. Language: **Bash**.
8. Required: prevent this step from being skipped. Run only after previous steps succeed.

Use this script directly as the package script so Octopus's
`get_octopusvariable` helper is available. Do not wrap it in an unrelated
`bash deploy.sh` inline step that loses that helper. No variable-substitution
feature is needed; secrets are read from Octopus variables at runtime.

The package contains `docker-compose.yml`, `release.json`, `deploy.sh`,
`release-env.py`, and `smoke.py`. The target does not clone Git or rebuild
source. There is no dependency on files in the developer checkout.

If creating the step before a package exists is inconvenient, first run the
workflow with CD disabled, download its `octopus-package` artifact, and upload
that ZIP under **Library → Packages**. Then configure the step and enable CD.

The deployment script:

- Validates environment isolation and digest references, then locks the environment's deployment directory to prevent
  concurrent target updates.
- Uses temporary GHCR authentication, pulls images before replacing containers,
  and waits for MySQL, Express, and Nginx readiness.
- Checks the frontend document, dashboard, and all five API lists through that environment's port.
- Records successful releases under its deployment directory's `releases/` and updates `current`.
- Restores the previous frontend/backend on a failed update and **still fails
  the Octopus task**. It never deletes or rolls back the database volume.

Database migrations and credential changes need their own reviewed process.
Automatic application rollback cannot reverse database changes. Keep MySQL
backups appropriate to your data before upgrades; sample data is not a backup.

## 4. Configure GitHub

Under **Repository → Settings → Secrets and variables → Actions**, create:

| Type | Name | Value |
| --- | --- | --- |
| Variable | `OCTOPUS_SERVICE_ACCOUNT_ID` | The GUID from the dedicated Octopus service account's OpenID Connect section |
| Variable | `OCTOPUS_URL` | `https://karthik-devops-lab.octopus.app` |
| Variable | `OCTOPUS_SPACE` | `Default` |
| Variable | `OCTOPUS_PROJECT` | `Sakila-Movie-Rental-Portal` |
| Variable | `OCTOPUS_ENVIRONMENT` | `Development` |
| Variable | `OCTOPUS_ENABLED` | `true`, after steps 1–3 are complete |

Use a dedicated Octopus service account with package publishing rights in Default,
and release/deployment/task-read rights limited to Sakila-Movie-Rental-Portal and
Development, QA, and Production. The configured account is `sakila-github-actions`, assigned to the
Default-space team `Sakila CI Delivery`. Its custom role, `Sakila Pipeline Publisher`,
contains `BuiltInFeedDownload`, `BuiltInFeedPush`, `DeploymentCreate`,
`DeploymentView`, `EnvironmentView`, `FeedView`, `LibraryVariableSetView`,
`LifecycleView`, `ProcessView`, `ProjectView`, `ReleaseCreate`, `ReleaseView`,
`TargetTagView`, `TaskView`, and `TenantView`. The role assignment is scoped to
the project and those three environments; package permissions apply to the space's built-in feed.
It grants no editing, deletion, account administration, manual intervention approval,
or runbook execution.

Add GitHub Actions OIDC identities for this exact repository:

- Owner: `shivakarthikreddyk`
- Repository: `Repository-name-sakila-movie-rental-portal-pro-fixed`
- Branch identity: `main`
- Tag identity: `v*`

Enable **Use immutable subject claim** for both identities. This repository's
owner ID is `63806131` and repository ID is `1303712587`. Its subject is
`repo:shivakarthikreddyk@63806131/Repository-name-sakila-movie-rental-portal-pro-fixed@1303712587:ref:refs/heads/main`
for the branch, or the same prefix followed by `:ref:refs/tags/v*` for tags.
An identity using only owner/repository names will not match this repository.

Do not authorize pull-request identities. The workflow uses
`OctopusDeploy/login@v2` and short-lived tokens; no Octopus API-key secret is
needed. The service-account GUID is an identifier, not a credential. The workflow declares
`packages: write` for GHCR publishing. If organization policy restricts it,
allow this repository's workflow to publish its own packages.

The GitHub CLI can set the non-sensitive values:

```bash
gh variable set OCTOPUS_URL --body 'https://karthik-devops-lab.octopus.app'
gh variable set OCTOPUS_SPACE --body 'Default'
gh variable set OCTOPUS_PROJECT --body 'Sakila-Movie-Rental-Portal'
gh variable set OCTOPUS_ENVIRONMENT --body 'Development'
gh variable set OCTOPUS_SERVICE_ACCOUNT_ID --body '<service-account-guid>'
gh variable set OCTOPUS_ENABLED --body 'true'
```

## 5. Release and verify

Merge the reviewed pipeline changes to the default branch. It will test,
publish, package, and deploy automatically when Octopus is enabled. For a stable
version, create a new unused tag on the intended commit:

```bash
git tag v0.0.5
git push origin v0.0.5
```

Do not move an existing release tag. Release package uploads fail if a version
already exists. A rerun after a partially successful stable release may require
deploying that existing release from Octopus or choosing a new version.

Confirm the GitHub `octopus` job and Octopus deployment task both succeed.
Open `http://localhost:8093` and `http://localhost:8093/api/health` on the target
machine. `localhost` on GitHub's hosted runner is not your Windows machine;
post-deployment checks therefore run on the Tentacle.

After Development and QA succeed, run **Promote Sakila release to Production**
from GitHub Actions on `main`, with the exact existing release number. Approve
the pending task in Octopus as a member of Sakila Production Approvers. The same image digests
are promoted, with no rebuild. The Production workflow supplies a fresh temporary
GHCR token and waits up to 350 minutes within a six-hour job. If the job times out,
cancel the pending Octopus deployment and rerun the promotion workflow before
approving; an expired job token cannot pull private images.

Verify `http://localhost:8094/api/health` and `http://localhost:8095/api/health`,
as well as the frontend pages. A green historical task with a skipped Docker
step is not evidence of an environment deployment. Check actual container
health, port bindings, and each environment's separate MySQL volume.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Octopus job skipped | Default branch or stable tag? `OCTOPUS_ENABLED=true`? |
| Release created, deployment pending | WSL running? Target healthy? Correct environment and role? |
| `docker` unavailable in Ubuntu | Docker Desktop WSL integration for the Tentacle distro, or native Engine service |
| Docker socket permission denied | Docker access for the **Tentacle service user** |
| GHCR unauthorized | Target token has `read:packages`, correct package/repository access, and required organization authorization |
| MySQL unhealthy / access denied | Passwords match the existing volume; inspect database logs without removing the volume |
| Port 8093 in use | Stop the local stack or choose another deployment port |
| Nginx 502 | Backend readiness and Compose DNS/network; do not point at host `localhost:5000` |

## References

- [Octopus GitHub Actions](https://octopus.com/docs/packaging-applications/build-servers/github-actions)
- [Octopus GitHub OIDC authentication](https://octopus.com/docs/api/authentication/openid-connect/github-actions)
- [Run a script from a package](https://octopus.com/docs/deployments/custom-scripts/run-a-script-step)
- [Octopus variables in Bash](https://octopus.com/docs/deployments/custom-scripts/using-variables-in-scripts)
- [Linux Tentacle](https://octopus.com/docs/infrastructure/deployment-targets/tentacle/linux)
- [Compose health-based startup](https://docs.docker.com/compose/how-tos/startup-order/)
- [Docker Desktop WSL2 integration](https://docs.docker.com/desktop/features/wsl/)
- [Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
