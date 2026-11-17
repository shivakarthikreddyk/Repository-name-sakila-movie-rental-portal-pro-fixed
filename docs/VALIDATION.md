# Validation — 2026-11-16

## Separate applications and deployments

The initial setup incorrectly reused Ecommerce-DevOps-Lab for Sakila. That was
corrected by creating a dedicated Sakila project and restoring Ecommerce's
original deployment process from Octopus's audit history.

| Application | Octopus project | URL | Verified release |
| --- | --- | --- | --- |
| Original Python Ecommerce API | Ecommerce-DevOps-Lab | http://localhost:8092 | 0.0.2 |
| React / Express / MySQL Sakila portal | Sakila-Movie-Rental-Portal | http://localhost:8093 | 0.0.5 |

Both use the existing healthy Ubuntu WSL2 polling Tentacle. Ecommerce selects
`ecommerce-api`; Sakila selects `sakila-portal`. Each has its own process,
variables, release history, images, containers, and port.

- [Sakila pipeline 44000505285](https://github.com/shivakarthikreddyk/Repository-name-sakila-movie-rental-portal-pro-fixed/actions/runs/44000505285)
  built and tested all three images, published them privately to GHCR, and
  deployed release 0.0.5 into the dedicated project.
- [Sakila deployment ServerTasks-112](https://karthik-devops-lab.octopus.app/app#/tasks/ServerTasks-112)
  succeeded and reported port 8093. Docker login emits a warning about its
  temporary credential file; that directory is removed on script exit.
- [Ecommerce restoration ServerTasks-113](https://karthik-devops-lab.octopus.app/app#/tasks/ServerTasks-113)
  successfully redeployed its original release 0.0.2. The previous stopped
  container is preserved as `octopus-ecommerce-octopus-pre-separation`.
- Ecommerce `/`, `/health`, and `/products` returned the expected Python API
  identity, healthy status, and three pickle products on port 8092.
- **16 API and Chromium checks passed against Sakila on port 8093**, including
  all navigation tabs, searches, empty results, mobile layout and error recovery.
- Sakila still uses `sakila-production_mysql-data`, created at
  `2026-11-17T01:42:47Z`; it was not replaced or deleted. Tests verified 1,000
  films, 599 customers, and 16,044 rentals after the move.
- Sakila's GitHub OIDC account is restricted to Sakila-Movie-Rental-Portal and
  Development. The workflow also rejects any other `OCTOPUS_PROJECT` value.
- Sakila-only variables were removed from Ecommerce. Its original inline Bash
  script, pinned Ecommerce image and `ecommerce-api` target tag were restored.
- Misrouted Sakila releases 0.0.4 and 0.1.8-ci.1 remain in Ecommerce's audit
  history, with progression blocked and an explanation attached. They are not
  Ecommerce versions and must not be redeployed there.

## Application and pipeline checks

| Check | Result |
| --- | --- |
| Frontend production build | Passed locally and in CI |
| Backend Node unit tests | 4 passed |
| Pytest API and Chromium checks | 16 passed |
| Linux release metadata / deployment failure tests | 9 passed |
| Docker Compose startup | All 3 Sakila containers healthy |
| Container replacement | Dataset retained; API checks passed afterward |
| Target smoke script | Frontend, health, dashboard, all 5 lists passed |
| GitHub Actions syntax (actionlint) | Passed |
| Bash syntax and ShellCheck | Passed |
| Git whitespace checks | Passed |

There are **29 distinct passing tests** across Node and Python. The Bash
failure tests simulate Docker failures to verify failed pulls leave containers
untouched and failed updates restore the previous application while preserving
an unsuccessful exit code.

The [separation branch CI](https://github.com/shivakarthikreddyk/Repository-name-sakila-movie-rental-portal-pro-fixed/actions/runs/44000065726)
and [pull-request CI](https://github.com/shivakarthikreddyk/Repository-name-sakila-movie-rental-portal-pro-fixed/actions/runs/44000095915)
both passed for commit `95455391dcc79cfad04173a226103f6c7038ea5b`.

The GHCR images remain **Private**. GitHub signs into Octopus with OIDC and
passes its temporary job token through required sensitive deployment prompts;
no permanent GitHub PAT or Octopus API key is stored. Keep Docker Desktop and
Ubuntu WSL running for the applications and Tentacle to remain available.

Follow [OCTOPUS_SETUP.md](OCTOPUS_SETUP.md) for the current setup.
