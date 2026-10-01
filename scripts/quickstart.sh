#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -z "${INSTANTKV_BUILD_SOURCE:-}" ]]; then
  # Verified release binary avoids compiling Rust on supported Docker hosts.
  if [[ "$(docker info --format '{{.Architecture}}')" == x86_64 ]] &&
     INSTANTKV_PLATFORM=linux-x86_64 ./scripts/install.sh "$PWD/dist"; then
    export INSTANTKV_BUILD_SOURCE=prebuilt
  else
    printf '%s\n' 'Using source build (release binary unavailable for this platform/version).'
    export INSTANTKV_BUILD_SOURCE=source-build
  fi
fi
docker compose build
# Existing state is kept; initialize only on first use.
if ! docker compose run --rm --no-deps instantkv check-config >/dev/null 2>&1; then
  docker compose run --rm --no-deps instantkv init
fi
docker compose up -d --wait
docker compose exec -T instantkv instantkv doctor
printf '%s\n' "Ready at http://127.0.0.1:${INSTANTKV_PORT:-8080}" 'Try: ./scripts/kv.sh demo'
