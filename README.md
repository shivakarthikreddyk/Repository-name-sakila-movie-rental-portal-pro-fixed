# Sakila Movie Rental Portal

React + Express + MySQL, delivered by GitHub Actions, GHCR, and Octopus Cloud
to an Ubuntu WSL2 polling Tentacle. The application uses **Node.js**;
**Python/pytest** verifies the APIs, browser, and deployment tooling.

Sakila deploys only to **Sakila-Movie-Rental-Portal**: Development **8093**,
QA **8094**, and Production **8095**, each with its own containers and database volume.
**Ecommerce-DevOps-Lab** is a separate Python project on port **8092**.
They share the host, with separate Octopus processes and releases. Sakila delivery now targets Kubernetes namespaces; Ecommerce retains its original Docker deployment.

```mermaid
flowchart LR
    A[Developer: Ubuntu WSL2] --> B[GitHub repository]
    B --> C[GitHub Actions: unit tests]
    C --> D[Build frontend, backend, database images]
    D --> E[pytest: real APIs and Chromium UI]
    E --> F[GHCR: tested versioned images]
    F --> G[Octopus Cloud: versioned release]
    G --> H[Kubernetes Development: port 8093]
    H -->|Health checks pass| I[Kubernetes QA: port 8094]
    I --> J[Production promotion workflow]
    J --> K[Octopus: human approval]
    K --> L[Kubernetes Production: port 8095]
```

See [Kubernetes deployment and scaling](k8s/README.md) for namespace isolation,
resource limits, persistent data migration, and manual backend scaling.

## Run locally with Docker Compose

Install Docker with the Compose plugin and Python 3.12 or newer. For WSL2,
enable Docker Desktop integration for the **same Ubuntu distribution** where
you run these commands, or install Docker Engine directly inside that distro.

```bash
python3 scripts/init-env.py
docker compose -f docker-compose.yml -f compose.build.yml up -d --build --wait --wait-timeout 240
```

In PowerShell use `python scripts/init-env.py`; the Docker command is identical.
The setup creates an ignored `.env` with random passwords without replacing
existing credentials. Never commit this file.

- Portal: http://localhost:8093
- Database readiness: http://localhost:8093/api/health
- Backend liveness: http://localhost:8093/api/live

Only Nginx is published on the host. The browser calls `/api` through Nginx;
MySQL and Express communicate on private Compose networks. Local access is
bound to `127.0.0.1` by default. Set `APP_BIND_ADDRESS=0.0.0.0` explicitly if
you intend to expose this sample-data portal to your LAN.

The first startup imports the complete official Sakila sample: 1,000 films,
599 customers, and 16,044 rentals. Subsequent starts reuse the named volume.
Database passwords must match the values used when that volume was created;
editing `.env` does not rotate an existing MySQL user's password.

```bash
docker compose ps
docker compose logs --tail 100
docker compose down                 # stops containers; keeps database data
```

Do not use `docker compose down --volumes` on a deployment you want to keep.
Schema/data initialization scripts are for new volumes only. See
[database provenance and license](database/README.md).

## Validate

With the Docker stack healthy:

```bash
npm ci --prefix backend
npm test
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-test.txt
python -m playwright install --with-deps chromium
python -m pytest --browser chromium -q
```

In PowerShell use `.venv\Scripts\python` in place of `python` after creating
the virtual environment with `python -m venv .venv`. The Bash deployment tests
run on Linux and are skipped on Windows. Set `SAKILA_BASE_URL` to test a
different URL. Tests assert the original sample dataset counts, so run them
against a sample-data environment; the deployment smoke checks allow changed counts.

Tests cover database readiness, dashboard aggregates, all five lists, searches,
ratings, invalid input, asset serving, desktop/mobile navigation, API failure
handling, release validation, and deployment failure/rollback behavior.

## CI and releases

The workflow is [.github/workflows/pipeline.yml](.github/workflows/pipeline.yml).

1. Pushes and pull requests run Node unit tests and frontend builds.
2. CI builds the three Docker images, starts the full stack, and runs pytest
   API and Chromium tests through port 8093.
3. CI recreates containers and checks that the database data survives.
4. Successful builds on the default branch or `vMAJOR.MINOR.PATCH` tags publish
   those same tested images to GHCR. Feature branches and PRs do not publish.
5. A ZIP deployment package records the commit and exact GHCR image digests.
6. When `OCTOPUS_ENABLED=true`, CD pushes the package to Octopus, creates a
   release, deploys to Development, and promotes the same release to QA only
   after Development succeeds. Both deployments run target health and API checks.
7. Run **Promote Sakila release to Production** from GitHub Actions on `main`,
   entering that exact release number. Octopus requires Development and QA success
   and pauses for a Sakila Production Approvers member's approval before changing Production.
   This workflow does not rebuild images. Approve while its job is running;
   after timeout, cancel the pending Octopus deployment and rerun the workflow
   to supply fresh private-GHCR credentials.

Images are named `ghcr.io/<owner>/<repository>-frontend`, `-backend`, and
`-database`, with unique `build-<run-id>-<attempt>` tags. Releases resolve
images by digest, so a moved tag cannot change an existing release.
Default-branch release numbers use `0.1.<run-number>-ci.<attempt>`.
A tag such as `v0.0.5` creates Sakila release `0.0.5`. Ecommerce release
`0.0.2` belongs to its separate project and is not used by this pipeline.

Base images are pinned by digest, npm uses committed lockfiles, and Dependabot
proposes dependency updates. Updating the MySQL base image requires checking
database upgrade compatibility before promotion.

## Activate Octopus delivery

Follow [the Octopus and WSL2 setup guide](docs/OCTOPUS_SETUP.md) to configure the
target, process, sensitive variables, and GitHub settings for
`https://karthik-devops-lab.octopus.app`.

The pipeline deploys to the dedicated Sakila project in Development and QA.
Production requires the separate promotion workflow and human approval in Octopus.
The workflow rejects any other `OCTOPUS_PROJECT` value, and its Octopus role
is scoped to Sakila. See [validation evidence](docs/VALIDATION.md). The three GHCR images
are private. GitHub uses OIDC to sign into Octopus and supplies a temporary
package-read token for the deployment; no permanent API-key secret is needed.

For a new installation, keep `OCTOPUS_ENABLED=false` until target, variables,
permissions, and OIDC trust are configured, then set it to `true`. Keep Docker
Desktop and the Ubuntu WSL distro running so Tentacle can poll and serve the app.

The Jenkinsfile and standalone k8s/*.yaml files are historical examples. Live
Kubernetes resources are generated by deployment/kubernetes-render.py from the
release digests. Compose remains the local development and CI test harness.
