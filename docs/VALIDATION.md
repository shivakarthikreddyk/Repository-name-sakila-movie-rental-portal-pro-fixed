# Local validation — 2026-11-16

Validated from this checkout using Docker Desktop's Linux engine. Octopus now
manages the running `sakila-production` Compose project at http://localhost:8092.
The local test project `sakila-portal` is stopped; its database volume is preserved.

| Check | Result |
| --- | --- |
| Frontend production build | Passed, including inside Docker |
| Backend unit tests | 4 passed |
| Windows pytest: real API, Chromium UI, release metadata | 22 passed |
| Linux pytest: release metadata and deployment scripts | 9 passed (6 overlap the Windows run) |
| Docker Compose build and startup | All 3 containers healthy |
| Container replacement | All 3 recreated; dataset retained; API/UI checks passed afterward |
| Target smoke script | Frontend, health, dashboard, and all 5 lists passed |
| GitHub Actions syntax (actionlint) | Passed |
| Bash scripts (ShellCheck) | Passed |
| Git whitespace checks | Passed |

This is **29 distinct passing tests** across Node and Python. The 3 Bash
deployment tests are skipped on Windows and were run successfully in a Linux
Python container. They simulate Docker failures to verify that failed pulls
leave containers untouched and failed updates restore the previous application
while preserving the failure exit code.

Real API tests verified 1,000 films, 599 customers, and 16,044 rentals through
Nginx → Express → MySQL. Browser tests covered all navigation tabs, filtered
search, empty results, mobile width, and recovery after an API error.

## Remote validation and activation

- [Branch CI run 43994024399](https://github.com/shivakarthikreddyk/Repository-name-sakila-movie-rental-portal-pro-fixed/actions/runs/43994024399)
  passed all checks.
- [Release build 43994590104](https://github.com/shivakarthikreddyk/Repository-name-sakila-movie-rental-portal-pro-fixed/actions/runs/43994590104)
  passed on attempt 2, published the three GHCR images, and produced
  `sakila-deploy.0.0.3.zip` with their exact digests. Attempt 1 encountered a
  transient GHCR `unknown blob` error; the workflow now retries image pushes.
- Restarting Docker Desktop restored its Ubuntu WSL integration. Docker 29.6.1,
  Compose 5.3.0, Python, and the active root-owned Tentacle were verified in
  `Ubuntu`. That distro can reach the healthy application on port 8092.
- The existing Octopus step now runs packaged `deploy.sh` on the `ecommerce-api`
  target tag in Development. Database passwords are saved as sensitive variables.
- A dedicated GitHub OIDC service account is configured for this repository's
  main branch and version tags. The CD job supplies temporary package-read
  credentials through sensitive prompted variables; the GHCR images stay private.
- All three packages were explicitly changed to **Private** after GitHub initially
  inherited public visibility from the source repository.
- [Full pipeline run 43997079969](https://github.com/shivakarthikreddyk/Repository-name-sakila-movie-rental-portal-pro-fixed/actions/runs/43997079969)
  passed both jobs and deployed release **0.0.4** to **Development** through the
  polling Tentacle. The first CD attempt identified GitHub's immutable OIDC subject
  format; both trust identities were corrected and only CD was retried.
- [Octopus deployment task ServerTasks-110](https://karthik-devops-lab.octopus.app/app#/tasks/ServerTasks-110)
  completed successfully at 19:43 CST. All three containers became healthy and
  the target's smoke checks passed. Octopus shows a warning from Docker login's
  temporary credential file; the script removes that directory on exit and the
  GitHub token expires at job completion.
- **16 API and Chromium checks passed against the actual Octopus-managed deployment**.
  The browser displayed 1,000 films, 599 customers, 16,044 rentals and $67,406.56
  revenue. Release state is recorded in `/opt/sakila/current`.
- Existing release `0.0.2` has not been changed.

Follow [OCTOPUS_SETUP.md](OCTOPUS_SETUP.md) for the exact runtime and permissions.
