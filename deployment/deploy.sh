#!/usr/bin/env bash
# Run this file as the script source in an Octopus "Run a Script" package step.
set +x
set -Eeuo pipefail
umask 077
package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if declare -F get_octopusvariable >/dev/null; then
  export DB_PASSWORD MYSQL_ROOT_PASSWORD APP_PORT APP_BIND_ADDRESS DEPLOY_ROOT COMPOSE_PROJECT_NAME GHCR_USERNAME GHCR_TOKEN
  DB_PASSWORD="$(get_octopusvariable 'Sakila.DbPassword')"
  MYSQL_ROOT_PASSWORD="$(get_octopusvariable 'Sakila.RootPassword')"
  APP_PORT="$(get_octopusvariable 'Sakila.Port')"
  APP_BIND_ADDRESS="$(get_octopusvariable 'Sakila.BindAddress')"
  DEPLOY_ROOT="$(get_octopusvariable 'Sakila.DeployRoot')"
  COMPOSE_PROJECT_NAME="$(get_octopusvariable 'Sakila.ComposeProject')"
  GHCR_USERNAME="$(get_octopusvariable 'GHCR.Username')"
  GHCR_TOKEN="$(get_octopusvariable 'GHCR.Token')"
  # Reject a mis-scoped environment before Docker can modify any container.
  environment="$(get_octopusvariable 'Octopus.Environment.Name')"
  project="$(get_octopusvariable 'Octopus.Project.Name')"
  [[ "$project" == Sakila-Movie-Rental-Portal ]] || { echo 'Wrong Octopus project'; exit 1; }
  case "$environment" in
    Development) expected='8093|sakila-production|/opt/sakila' ;;
    QA) expected='8094|sakila-qa|/opt/sakila-qa' ;;
    Production) expected='8095|sakila-prod|/opt/sakila-prod' ;;
    *) echo 'Unsupported Sakila environment'; exit 1 ;;
  esac
  [[ "$APP_PORT|$COMPOSE_PROJECT_NAME|$DEPLOY_ROOT" == "$expected" ]] || {
    echo "Environment isolation settings do not match $environment"; exit 1;
  }
  [[ "$APP_BIND_ADDRESS" == 127.0.0.1 ]] || { echo 'Expected local-only binding'; exit 1; }
fi
: "${DB_PASSWORD:?Set Sakila.DbPassword (sensitive)}"
: "${MYSQL_ROOT_PASSWORD:?Set Sakila.RootPassword (sensitive)}"
export APP_PORT="${APP_PORT:-8093}"
export APP_BIND_ADDRESS="${APP_BIND_ADDRESS:-127.0.0.1}"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-sakila-production}"
deploy_root="${DEPLOY_ROOT:-/opt/sakila}"
[[ "$deploy_root" = /* && "$deploy_root" != / ]] || { echo 'DeployRoot must be an absolute application directory'; exit 1; }
[[ "$COMPOSE_PROJECT_NAME" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || { echo 'Invalid Compose project'; exit 1; }
if [[ ! "$APP_PORT" =~ ^[1-9][0-9]{0,4}$ ]] || (( APP_PORT > 65535 )); then
  echo 'Invalid application port'; exit 1
fi
for command in docker python3 flock; do command -v "$command" >/dev/null; done
docker info >/dev/null
docker compose version
mkdir -p "$deploy_root/releases"
exec 9>"$deploy_root/.deploy.lock"
flock -n 9 || { echo 'Another deployment is running'; exit 1; }

# Export only validated key=value records; never source release files as shell code.
release_env="$(mktemp "$deploy_root/.release-env.XXXXXX")"
export DOCKER_CONFIG
DOCKER_CONFIG="$(mktemp -d "$deploy_root/.docker-auth.XXXXXX")"
cleanup() {
  rm -f -- "$release_env" "$DOCKER_CONFIG/config.json"
  rmdir -- "$DOCKER_CONFIG" 2>/dev/null || true
}
trap cleanup EXIT
python3 "$package_dir/release-env.py" "$package_dir/release.json" > "$release_env"
while IFS= read -r setting; do export "${setting?}"; done < "$release_env"
release_dir="$(mktemp -d "$deploy_root/releases/$RELEASE_VERSION.XXXXXX")"
cp "$package_dir/docker-compose.yml" "$package_dir/release.json" "$package_dir/smoke.py" "$release_dir/"
cp "$release_env" "$release_dir/images.env"

if [[ -n "${GHCR_TOKEN:-}" || -n "${GHCR_USERNAME:-}" ]]; then
  : "${GHCR_USERNAME:?Set GHCR.Username}"
  : "${GHCR_TOKEN:?Set GHCR.Token (sensitive, read:packages)}"
  printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin
fi
unset GHCR_TOKEN

compose() {
  docker compose --project-name "$COMPOSE_PROJECT_NAME" --env-file "$release_dir/images.env" -f "$release_dir/docker-compose.yml" "$@"
}
compose config --quiet
# Pull everything before changing any running container.
compose pull
previous_dir="$(readlink -f "$deploy_root/current" 2>/dev/null || true)"
rollback() {
  local result=$?
  trap - ERR
  echo "Release $RELEASE_VERSION failed."
  compose ps || true
  if [[ -n "$previous_dir" && -f "$previous_dir/images.env" ]]; then
    echo 'Restoring the previous frontend and backend; preserving the database.'
    while IFS= read -r setting; do export "${setting?}"; done < "$previous_dir/images.env"
    if docker compose --project-name "$COMPOSE_PROJECT_NAME" --env-file "$previous_dir/images.env" \
        -f "$previous_dir/docker-compose.yml" up -d --no-deps --wait --wait-timeout 120 backend frontend \
        && python3 "$previous_dir/smoke.py" "http://127.0.0.1:$APP_PORT"; then
      echo 'Previous application release restored.'
    else
      echo 'Automatic application rollback failed; inspect the target before redeploying.'
    fi
  else
    echo 'No previous successful release exists; containers retained for diagnosis.'
  fi
  exit "$result"
}
trap rollback ERR
compose up -d --wait --wait-timeout 240
python3 "$release_dir/smoke.py" "http://127.0.0.1:$APP_PORT"
if [[ -n "$previous_dir" && -f "$previous_dir/images.env" ]]; then
  ln -sfn "$previous_dir" "$deploy_root/previous"
fi
ln -sfn "$release_dir" "$deploy_root/.current-next"
mv -Tf "$deploy_root/.current-next" "$deploy_root/current"
trap - ERR
echo "Successfully deployed release $RELEASE_VERSION on port $APP_PORT."
