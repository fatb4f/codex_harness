#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
cache_root="${XDG_CACHE_HOME:-$HOME/.cache}/codex_harness/pycache"

mkdir -p "$cache_root"
export PYTHONPYCACHEPREFIX="$cache_root"

exec python3 "$repo_root/src/runtime_probe.py" "$@"
