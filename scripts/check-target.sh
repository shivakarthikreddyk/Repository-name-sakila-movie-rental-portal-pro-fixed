#!/usr/bin/env bash
# Run inside the same Ubuntu distro and as the same user as the polling Tentacle.
set -euo pipefail
for command in docker python3 flock; do
  command -v "$command" >/dev/null || { echo "Missing prerequisite: $command"; exit 1; }
done
docker info --format 'Docker server: {{.ServerVersion}}'
docker compose version
python3 --version
if systemctl is-active --quiet Tentacle; then
  echo 'Polling Tentacle service is active.'
else
  echo 'Tentacle service is not active; verify the service name and configuration.'
  exit 1
fi
echo 'Local target prerequisites passed. Confirm target health in Octopus Cloud too.'
