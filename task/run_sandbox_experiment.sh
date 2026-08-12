#!/usr/bin/env bash
set -euo pipefail

task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$task_dir/.." && pwd)"
env_file="$repo_dir/.env"

if [[ ! -f "$env_file" ]]; then
  echo "Missing $env_file. Copy .env.example to .env and configure it first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$env_file"
set +a

if (( $# > 1 )); then
  echo "Usage: bash task/run_sandbox_experiment.sh <cached_instance_id>" >&2
  exit 2
fi

cached_instance_id="${1:-${A2E_SWE_INSTANCE:-}}"
if [[ -z "$cached_instance_id" ]]; then
  echo "Usage: bash task/run_sandbox_experiment.sh <cached_instance_id>" >&2
  exit 2
fi

export A2E_SWE_INSTANCE="$cached_instance_id"
export no_proxy="127.0.0.1,localhost,${no_proxy:-}"
export NO_PROXY="$no_proxy"

cd "$task_dir"
exec uv run --frozen python examples/run_experiment.py \
  --dataset swe-bench-lite --agent agno --n 1 \
  --evaluators swe_resolved,swe_fail_to_pass,swe_pass_to_pass
