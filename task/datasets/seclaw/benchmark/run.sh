#!/usr/bin/env bash
# Internal SeClaw runtime helper.
# Public evaluations should use ../scripts/batch_execute.sh --backend docker.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

python benchmark/benchmark.py "$@"
