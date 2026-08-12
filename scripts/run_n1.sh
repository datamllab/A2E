#!/usr/bin/env bash
# One n=1 A2E run with official non-judge evaluators (gdpval-aa keeps llm_judge).
# Usage: run_n1.sh <agent> <dataset> [extra args...]
set -euo pipefail
agent="${1:?agent}"
dataset="${2:?dataset}"
shift 2
# shellcheck disable=SC1091
# Machine-local network (institutional proxy). Keep the scripts; uncomment on this host.
# if [ "$agent" = "autogen-agentchat" ]; then
#   source /root/A2E/scripts/autogen_env.sh
# else
#   source /root/A2E/scripts/a2e_net.sh
# fi
# source <(curl -fsSL http://deploy.i.h.pjlab.org.cn/infra/scripts/setup_proxy.sh)
# : "${http_proxy:?setup_proxy.sh did not set http_proxy}"
# export no_proxy="127.0.0.1,localhost,10.0.0.0/8,.pjlab.org.cn,35.220.164.252,${no_proxy:-}"
# export NO_PROXY="$no_proxy"
source /root/A2E/scripts/tau_env.sh
if [ "$agent" = "autogen-agentchat" ]; then
  _ISO_SITE="/root/A2E/task/agents/autogen_agentchat/.venv/lib/python3.13/site-packages"
  if [ ! -d "$_ISO_SITE" ]; then
    echo "autogen isolated venv missing; create it with:" >&2
    echo "  cd /root/A2E/task/agents/autogen_agentchat && uv sync --index-strategy unsafe-best-match" >&2
    exit 1
  fi
  export PYTHONPATH="${_ISO_SITE}:${PYTHONPATH}"
fi
cd /root/A2E/task

case "$dataset" in
  deepsearchqa) evals="deepsearch_match,tool_recall" ;;
  tau-bench|tau2|tau3|tau3bench|tau3-bench|traject-bench) evals="tool_recall" ;;
  mmlu|gpqa|mmlu-pro|arc-challenge|truthfulqa|agieval|commonsenseqa|hellaswag|openbookqa) evals="mc_letter" ;;
  gsm8k|math) evals="numeric_match" ;;
  humaneval) evals="humaneval_pass" ;;
  persistbench) evals="substring" ;;
  bbh) evals="exact_match" ;;
  gdpval-aa) evals="llm_judge" ;;
  gdpval) echo "dataset gdpval was removed; use gdpval-aa (HF openai/gdpval)" >&2; exit 2 ;;
  *) echo "unknown dataset: $dataset" >&2; exit 2 ;;
esac

extra=()
case "$dataset" in
  tau-bench|tau2|tau3|tau3bench|tau3-bench) extra+=(--domain retail) ;;
esac

# Same wall + in-process deadline for every harness on a given dataset.
case "$dataset" in
  deepsearchqa) wall=1800 ;;
  tau-bench|tau2|tau3|tau3bench|tau3-bench) wall=1200 ;;
  *) wall=720 ;;
esac
export A2E_RUN_DEADLINE=$((wall - 100))
export A2E_AGNO_DEADLINE="$A2E_RUN_DEADLINE"

exec timeout "$wall" "$AEP_PY" examples/run_experiment.py \
  --dataset "$dataset" \
  --agent "$agent" \
  --n 1 \
  --model kimi/kimi-k3 \
  --evaluators "$evals" \
  --sample-seed 20260816 \
  "${extra[@]}" \
  "$@"
