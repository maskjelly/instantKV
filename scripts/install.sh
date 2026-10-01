#!/usr/bin/env sh
set -eu
version="${INSTANTKV_VERSION:-0.1.0}"
case "$version" in ''|*[!0-9.]*) echo 'Invalid version' >&2; exit 1 ;; esac
destination="${1:-$HOME/.local/bin}"
platform="${INSTANTKV_PLATFORM:-}"
if [ -z "$platform" ]; then
  case "$(uname -s)/$(uname -m)" in
    Linux/x86_64) platform=linux-x86_64 ;;
    Darwin/arm64) platform=darwin-arm64 ;;
    *) echo 'No binary for this platform; install with Cargo.' >&2; exit 1 ;;
  esac
fi
case "$platform" in linux-x86_64|darwin-arm64) ;; *) echo 'Unsupported platform' >&2; exit 1 ;; esac
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT HUP INT TERM
archive="instantkv-$platform.tar.gz"
base="https://github.com/maskjelly/instantKV/releases/download/v$version"
curl --fail --silent --show-error --location --retry 2 "$base/$archive" -o "$work_dir/$archive"
curl --fail --silent --show-error --location --retry 2 "$base/$archive.sha256" -o "$work_dir/checksum"
expected="$(cut -d ' ' -f 1 "$work_dir/checksum")"
if command -v sha256sum >/dev/null 2>&1; then
  actual="$(sha256sum "$work_dir/$archive" | cut -d ' ' -f 1)"
else
  actual="$(shasum -a 256 "$work_dir/$archive" | cut -d ' ' -f 1)"
fi
if [ "$actual" != "$expected" ]; then
  echo 'Checksum verification failed' >&2; exit 1
fi
tar -xzf "$work_dir/$archive" -C "$work_dir" instantkv
mkdir -p "$destination"
install -m 755 "$work_dir/instantkv" "$destination/instantkv"
printf 'Installed instantKV %s at %s/instantkv\n' "$version" "$destination"
