#!/usr/bin/env bash
# One verification entry point for contributors and CI.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
mode="${1:---all}"
case "$mode" in --all|--core|--site|--repo) ;; *) echo 'Usage: scripts/check.sh [--all|--core|--site|--repo]' >&2; exit 2 ;; esac
if [ "$#" -gt 1 ]; then echo 'Use one verification mode.' >&2; exit 2; fi
test_python="${INSTANTKV_TEST_PYTHON:-python3}"
"$test_python" scripts/check-repo.py
"$test_python" scripts/test-check-repo.py
"$test_python" scripts/test-install-metrics.py
"$test_python" scripts/test-install-opencode-mcp.py
if [ "$mode" = --repo ]; then exit 0; fi
if [ "$mode" = --all ] || [ "$mode" = --core ]; then
  if ! "$test_python" -c 'import tiktoken' >/dev/null 2>&1; then
    echo 'Install eval/requirements-offline.txt in a venv and set INSTANTKV_TEST_PYTHON to its Python. See CONTRIBUTING.md.' >&2
    exit 1
  fi
  cargo fmt --all -- --check
  cargo clippy --workspace --all-targets --locked -- -D warnings
  cargo test --workspace --locked
  "$test_python" scripts/test-local-llm.py
  "$test_python" scripts/test-memory-controller.py
  "$test_python" scripts/test-memory-extraction.py
  "$test_python" scripts/test-memory-mcp.py
  "$test_python" scripts/test-retrieval-suite.py
  "$test_python" scripts/test-compare-supermemory.py
  "$test_python" -m unittest discover -s eval -p 'test_*.py'
  cargo build --workspace --release --locked
  ./target/release/instantkv demo
  ./target/release/instantkv demo --swarm
  "$test_python" scripts/test-start.py
  "$test_python" scripts/test-mcp-local.py
  "$test_python" scripts/memory-product-smoke.py
  for config in config/instantkv.example.toml config/local.toml config/local-cache.toml config/swarm.toml; do
    ./target/release/instantkv check-config --config "$config"
  done
  check_dir="$(mktemp -d "${TMPDIR:-/tmp}/instantkv-check.XXXXXX")"
  trap 'rm -rf -- "$check_dir"' EXIT
  cargo run --locked -p instantkv-core --example memory -- "$check_dir/embedded"
  ./target/release/instantkv schema > "$check_dir/checkpoint.schema.json"
  ./target/release/instantkv schema --kind memory > "$check_dir/memory.schema.json"
  diff -u examples/checkpoint.schema.json "$check_dir/checkpoint.schema.json"
  diff -u examples/memory.schema.json "$check_dir/memory.schema.json"
  for script in scripts/*.sh; do
    bash -n "$script"
  done
fi
if [ "$mode" = --all ] || [ "$mode" = --site ]; then
  cd site
  npm run check
  npm test
  npm run build
  npm run verify
fi
