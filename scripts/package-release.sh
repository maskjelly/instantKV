#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
case "$(uname -s)/$(uname -m)" in
  Linux/x86_64) platform=linux-x86_64; binary=target/x86_64-unknown-linux-musl/release/instantkv ;;
  Linux/aarch64|Linux/arm64) platform=linux-arm64; binary=target/aarch64-unknown-linux-musl/release/instantkv ;;
  Darwin/arm64) platform=darwin-arm64; binary=target/release/instantkv ;;
  *) printf '%s\n' 'Unsupported release platform' >&2; exit 1 ;;
esac
mkdir -p dist
release_dir="$(mktemp -d)"
trap 'rm -rf "$release_dir"' EXIT
cp "$binary" "$release_dir/instantkv"
cp LICENSE README.md "$release_dir/"
printf 'Version: %s\nCommit: %s\nPlatform: %s\n' "$("$binary" --version | cut -d ' ' -f 2)" "${GITHUB_SHA:-local}" "$platform" > "$release_dir/BUILD.txt"
archive="instantkv-$platform.tar.gz"
# macOS copyfile metadata must not become release archive members.
COPYFILE_DISABLE=1 tar -czf "dist/$archive" -C "$release_dir" instantkv LICENSE README.md BUILD.txt
(cd dist && shasum -a 256 "$archive" > "$archive.sha256")
