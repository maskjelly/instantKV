#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 2 || "$1" != /* || ! -f "$1/state.tar" ]]; then
  printf '%s\n' 'Usage: scripts/restore-drill.sh /absolute/backup-directory checkpoint-id' >&2
  exit 1
fi
backup_dir="$1"
checkpoint_id="$2"
image="${INSTANTKV_IMAGE:-instantkv:local}"
drill_name="instantkv-drill-$(date +%s)-$RANDOM"
volume_name="$drill_name-memory"
docker volume create "$volume_name" >/dev/null
cleanup() {
  docker rm -f "$drill_name" >/dev/null 2>&1 || true
  docker volume rm "$volume_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker run --rm --user 0:0 --entrypoint sh \
  --mount "type=bind,src=$backup_dir,dst=/backup,readonly" \
  --mount "type=volume,src=$volume_name,dst=/restore" \
  "$image" -c 'tar -xf /backup/state.tar -C /restore && chown -R 10001:10001 /restore'
docker run -d --name "$drill_name" --read-only --cap-drop ALL \
  --security-opt no-new-privileges:true --tmpfs /tmp:size=16m,mode=1777 \
  --mount "type=volume,src=$volume_name,dst=/state" \
  "$image" serve --bind 127.0.0.1:8080 >/dev/null
for attempt in {1..50}; do
  if docker exec "$drill_name" instantkv doctor >/dev/null 2>&1; then
    docker exec "$drill_name" instantkv restore --id "$checkpoint_id"
    printf '%s\n' 'PASS: known checkpoint restored from an offline backup in an isolated volume.'
    exit 0
  fi
  sleep 0.1
done
docker logs --tail 20 "$drill_name" >&2
printf '%s\n' 'Restore drill did not become healthy.' >&2
exit 1
