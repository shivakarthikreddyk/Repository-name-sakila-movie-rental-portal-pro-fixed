#!/usr/bin/env bash
set +x
set -Eeuo pipefail
umask 077
package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if declare -F get_octopusvariable >/dev/null; then
  export SAKILA_ENVIRONMENT SAKILA_PROJECT DB_PASSWORD MYSQL_ROOT_PASSWORD GHCR_USERNAME GHCR_TOKEN
  SAKILA_ENVIRONMENT="$(get_octopusvariable 'Octopus.Environment.Name')"
  SAKILA_PROJECT="$(get_octopusvariable 'Octopus.Project.Name')"
  DB_PASSWORD="$(get_octopusvariable 'Sakila.DbPassword')"
  MYSQL_ROOT_PASSWORD="$(get_octopusvariable 'Sakila.RootPassword')"
  GHCR_USERNAME="$(get_octopusvariable 'GHCR.Username')"
  GHCR_TOKEN="$(get_octopusvariable 'GHCR.KubernetesToken')"
fi
exec python3 "$package_dir/deploy-kubernetes.py"
