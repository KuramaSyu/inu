#!/usr/bin/env bash
# Convenience script: run the project using `uv` so uv-managed deps are used
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed or not on PATH"
  exit 2
fi

# default: run module with optimized flag
exec uv run -- python -O -m inu.main "$@"
