#!/usr/bin/env bash
set -euo pipefail
result_dir="${1:-benchmark-results}"
client_bin="${INSTANTKV_BIN:-instantkv}"
mkdir -p "$result_dir"
for run in 1 2 3; do
  "$client_bin" bench --namespace scratch --operation get --requests 20000 --concurrency 16 --value-bytes 512 > "$result_dir/scratch-get-$run.json"
  "$client_bin" bench --namespace knowledge --operation get --requests 20000 --concurrency 16 --value-bytes 512 > "$result_dir/knowledge-get-$run.json"
  "$client_bin" bench --namespace knowledge --operation put --requests 2000 --concurrency 8 --value-bytes 512 > "$result_dir/knowledge-put-$run.json"
  "$client_bin" bench --namespace checkpoints --operation checkpoint --requests 500 --concurrency 8 > "$result_dir/checkpoint-$run.json"
  "$client_bin" bench --namespace checkpoints --operation restore --requests 10000 --concurrency 16 > "$result_dir/restore-$run.json"
done
printf 'Three runs per profile recorded in %s\n' "$result_dir"
