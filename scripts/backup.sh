#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 1 || "$1" != /* ]]; then
  printf '%s\n' 'Usage: scripts/backup.sh /absolute/new/backup-directory' >&2
  exit 1
fi
backup_dir="$1"
if [[ -e "$backup_dir" ]]; then
  printf '%s\n' 'Backup directory must not already exist.' >&2
  exit 1
fi
cd "$(dirname "$0")/.."
umask 077
mkdir -m 700 "$backup_dir"
docker compose stop -t 30 instantkv
trap 'docker compose up -d --wait instantkv' EXIT
docker compose cp instantkv:/state/. - > "$backup_dir/state.tar"
printf 'Offline backup complete: %s\n' "$backup_dir"
