# Local validation — 2026-11-16

Validated from this checkout using Docker Desktop's Linux engine. The running
local Compose project is `sakila-portal`, available at http://localhost:8092.

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

## External activation still required

- At the time of the local validation, no GitHub workflow or Octopus deployment
  had run. Subsequent remote CI results are tracked in GitHub Actions.
- GitHub repository variables now identify the Default space,
  Ecommerce-DevOps-Lab project, and Development environment.
  `OCTOPUS_ENABLED=false` until deployment prerequisites are ready.
  The Octopus API-key secret is still required.
- The Ubuntu `Tentacle` service was active and pointed at
  `karthik-devops-lab.octopus.app`, but Docker was unavailable in that WSL distro.
  Enable Docker integration for Ubuntu, or provide a native Docker Engine.
- The supplied screenshots confirm the Octopus names and show release `0.0.2`
  in Development. The connected Chrome profile lacks instance access, while
  the other Chrome window is minimized. The deployment process is not yet verified.
- Existing release `0.0.2` has not been changed.

Follow [OCTOPUS_SETUP.md](OCTOPUS_SETUP.md) before enabling CD. Local success
does not establish cloud deployment success.
