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

export no_proxy="127.0.0.1,localhost,${no_proxy:-}"
export NO_PROXY="$no_proxy"

cd "$task_dir"
exec uv run --frozen python examples/run_experiment.py \
  --dataset tau-bench --agent agno --model qwen-max \
  --evaluators tool_recall,llm_judge --domain retail
