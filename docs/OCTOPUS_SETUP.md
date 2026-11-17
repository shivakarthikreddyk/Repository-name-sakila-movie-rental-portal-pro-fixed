# GitHub Actions → GHCR → Octopus → Ubuntu WSL2

This guide connects the supplied application to
`https://karthik-devops-lab.octopus.app` using the existing **Default** space
(`Spaces-1`), **Ecommerce-DevOps-Lab** project, and **Development** environment.
These names were confirmed from the supplied Octopus screenshots. QA and
Production are visible but are not targeted by this pipeline.

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
polling Tentacle is healthy, assigned to the intended environment, and has the
target role/tag `sakila-docker`. Prefer Octopus's generated Linux polling
installation/registration script if creating a new target; keep credentials out of Git.

Only one application can own port 8092. If the local development Compose stack
uses the same Docker daemon, stop it with `docker compose down` before the first
Octopus deployment. Its data remains in the development project's volume.

## 2. Configure the project variables

Select the existing **Ecommerce-DevOps-Lab** Octopus project and verify it is
**non-version-controlled**. This package-based workflow snapshots the scripts in its ZIP;
it does not require Octopus Config as Code.

Add these project variables, scoped to the target environment as appropriate:

| Variable | Value | Sensitive? |
| --- | --- | --- |
| `Sakila.DbPassword` | A unique application database password | Yes |
| `Sakila.RootPassword` | A separate unique database root password | Yes |
| `Sakila.Port` | `8092` | No |
| `Sakila.BindAddress` | `127.0.0.1` for local Windows/WSL access | No |
| `Sakila.DeployRoot` | `/opt/sakila` | No |
| `Sakila.ComposeProject` | `sakila-production` | No |
| `GHCR.Username` | GitHub account allowed to read the images | No |
| `GHCR.Token` | Token with `read:packages` and access to this repository's packages | Yes |

Set both GHCR variables to empty values only if the images are publicly
readable. GitHub's CI `GITHUB_TOKEN` is temporary and must not be reused on the
Tentacle. Newly published GHCR packages can be private even for public repositories.

Keep the database passwords, Compose project name, and deployment directory
stable between releases. The project name determines the persistent volume.
Changing it creates a different database volume. Rotating MySQL credentials
requires changing the account inside MySQL before updating Octopus values.

## 3. Configure the deployment process

The workflow publishes `sakila-deploy.<version>.zip` into the **Octopus built-in
package feed**. GHCR holds Docker images; the built-in feed holds scripts and
the release's image digest manifest.

Add one **Run a Script** step named `Deploy Sakila`:

1. Execution location: **Run on each deployment target**.
2. Target role/tag: `sakila-docker`.
3. Script source: **Script file inside a package**.
4. Package feed: **Octopus Server (built-in)**.
5. Package ID: **`sakila-deploy`**.
6. Script file: **`deploy.sh`** (at the ZIP root).
7. Language: **Bash**.

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

- Validates variables and digest references, then locks `/opt/sakila` to prevent
  concurrent target updates.
- Uses temporary GHCR authentication, pulls images before replacing containers,
  and waits for MySQL, Express, and Nginx readiness.
- Checks the frontend document, dashboard, and all five API lists through port 8092.
- Records successful releases under `/opt/sakila/releases/` and updates `current`.
- Restores the previous frontend/backend on a failed update and **still fails
  the Octopus task**. It never deletes or rolls back the database volume.

Database migrations and credential changes need their own reviewed process.
Automatic application rollback cannot reverse database changes. Keep MySQL
backups appropriate to your data before upgrades; sample data is not a backup.

## 4. Configure GitHub

Under **Repository → Settings → Secrets and variables → Actions**, create:

| Type | Name | Value |
| --- | --- | --- |
| Secret | `OCTOPUS_API_KEY` | Octopus service account API key with package, release, deployment, and task-read permissions in the intended space/project |
| Variable | `OCTOPUS_URL` | `https://karthik-devops-lab.octopus.app` |
| Variable | `OCTOPUS_SPACE` | `Default` |
| Variable | `OCTOPUS_PROJECT` | `Ecommerce-DevOps-Lab` |
| Variable | `OCTOPUS_ENVIRONMENT` | `Development` |
| Variable | `OCTOPUS_ENABLED` | `true`, after steps 1–3 are complete |

Keep API keys in Secrets, not Variables or source code. The workflow declares
`packages: write` for GHCR publishing. If organization policy restricts it,
allow this repository's workflow to publish its own packages.

The GitHub CLI can set the non-sensitive values:

```bash
gh variable set OCTOPUS_URL --body 'https://karthik-devops-lab.octopus.app'
gh variable set OCTOPUS_SPACE --body 'Default'
gh variable set OCTOPUS_PROJECT --body 'Ecommerce-DevOps-Lab'
gh variable set OCTOPUS_ENVIRONMENT --body 'Development'
gh secret set OCTOPUS_API_KEY     # enter the key at the protected prompt
gh variable set OCTOPUS_ENABLED --body 'true'
```

## 5. Release and verify

Merge the reviewed pipeline changes to the default branch. It will test,
publish, package, and deploy automatically when Octopus is enabled. For a stable
version after the existing `0.0.2`, create a new tag on the intended commit:

```bash
git tag v0.0.3
git push origin v0.0.3
```

Do not move an existing release tag. Release package uploads fail if a version
already exists. A rerun after a partially successful stable release may require
deploying that existing release from Octopus or choosing a new version.

Confirm the GitHub `octopus` job and Octopus deployment task both succeed.
Open `http://localhost:8092` and `http://localhost:8092/api/health` on the target
machine. `localhost` on GitHub's hosted runner is not your Windows machine;
post-deployment checks therefore run on the Tentacle.

Octopus environments/lifecycles control promotion. To add production approval,
configure it in Octopus rather than embedding target credentials into CI.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Octopus job skipped | Default branch or stable tag? `OCTOPUS_ENABLED=true`? |
| Release created, deployment pending | WSL running? Target healthy? Correct environment and role? |
| `docker` unavailable in Ubuntu | Docker Desktop WSL integration for the Tentacle distro, or native Engine service |
| Docker socket permission denied | Docker access for the **Tentacle service user** |
| GHCR unauthorized | Target token has `read:packages`, correct package/repository access, and required organization authorization |
| MySQL unhealthy / access denied | Passwords match the existing volume; inspect database logs without removing the volume |
| Port 8092 in use | Stop the local stack or choose another deployment port |
| Nginx 502 | Backend readiness and Compose DNS/network; do not point at host `localhost:5000` |

## References

- [Octopus GitHub Actions](https://octopus.com/docs/packaging-applications/build-servers/github-actions)
- [Run a script from a package](https://octopus.com/docs/deployments/custom-scripts/run-a-script-step)
- [Octopus variables in Bash](https://octopus.com/docs/deployments/custom-scripts/using-variables-in-scripts)
- [Linux Tentacle](https://octopus.com/docs/infrastructure/deployment-targets/tentacle/linux)
- [Compose health-based startup](https://docs.docker.com/compose/how-tos/startup-order/)
- [Docker Desktop WSL2 integration](https://docs.docker.com/desktop/features/wsl/)
- [Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
