#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -z "${INSTANTKV_BUILD_SOURCE:-}" ]]; then
  # Verified release binary avoids compiling Rust on supported Docker hosts.
  case "$(docker info --format '{{.Architecture}}')" in
    x86_64|amd64) docker_platform=linux-x86_64 ;;
    aarch64|arm64) docker_platform=linux-arm64 ;;
    *) docker_platform=unsupported ;;
  esac
  if INSTANTKV_PLATFORM="$docker_platform" ./scripts/install.sh "$PWD/dist"; then
    export INSTANTKV_BUILD_SOURCE=prebuilt
  else
    printf '%s\n' 'Using source build (release binary unavailable for this platform/version).'
    export INSTANTKV_BUILD_SOURCE=source-build
  fi
fi
docker compose build
# Existing state is kept; initialize only on first use.
if ! docker compose run --rm --no-deps instantkv check-config >/dev/null 2>&1; then
  docker compose run --rm --no-deps instantkv init --profile "${INSTANTKV_PROFILE:-local}"
fi
docker compose up -d --wait
docker compose exec -T instantkv instantkv doctor
ready_address="$(docker compose port instantkv 8080)"
printf '%s\n' "Ready at http://$ready_address" 'Try: ./scripts/kv.sh demo'
