#!/usr/bin/env bash
# Shared runtime for tau experiments. Uses AEP venv packages (agno/langgraph/smolagents/pyarrow)
# and /root/A2E sources (fixed tau tools). Do not uv-sync or reinstall.
set -euo pipefail

export A2E_ROOT="/root/A2E"
export AEP_PY="/mnt/shared-storage-user/zhangmingxuan/ageneval/AEP/task/.venv/bin/python"

export PYTHONPATH="\
${A2E_ROOT}/monitor/openinference-semantic-conventions/src:\
${A2E_ROOT}/monitor/openinference-instrumentation/src:\
${A2E_ROOT}/monitor/instrumentation/openinference-instrumentation-agno/src:\
${A2E_ROOT}/monitor/instrumentation/openinference-instrumentation-langchain/src:\
${A2E_ROOT}/monitor/instrumentation/openinference-instrumentation-smolagents/src:\
${A2E_ROOT}/monitor/instrumentation/openinference-instrumentation-openai-agents/src:\
${A2E_ROOT}/monitor/instrumentation/openinference-instrumentation-llama-index/src:\
${A2E_ROOT}/monitor/instrumentation/openinference-instrumentation-crewai/src:\
${A2E_ROOT}/monitor/instrumentation/openinference-instrumentation-google-adk/src:\
${A2E_ROOT}/monitor/instrumentation/openinference-instrumentation-anthropic/src:\
${A2E_ROOT}/monitor/instrumentation/openinference-instrumentation-autogen-agentchat/src:\
${A2E_ROOT}/task/packages/ageneval-task-sandbox/src:\
${A2E_ROOT}/task/packages/ageneval-task-core/src:\
${A2E_ROOT}/task/datasets/tau_bench/src:\
${A2E_ROOT}/task/datasets/tau2/src:\
${A2E_ROOT}/task/datasets/tau3/src:\
${A2E_ROOT}/task/datasets/traject_bench/src:\
${A2E_ROOT}/task/datasets/mmlu/src:\
${A2E_ROOT}/task/datasets/gsm8k/src:\
${A2E_ROOT}/task/datasets/humaneval/src:\
${A2E_ROOT}/task/datasets/persistbench/src:\
${A2E_ROOT}/task/datasets/gdpval/src:\
${A2E_ROOT}/task/datasets/deepsearchqa/src:\
${A2E_ROOT}/task/datasets/qa_suite/src:\
${A2E_ROOT}/task/datasets/swe_bench/src:\
${A2E_ROOT}/task/datasets/swe_bench_pro/src:\
${A2E_ROOT}/task/datasets/terminal_bench_2/src:\
${A2E_ROOT}/task/datasets/terminal_bench_2_1/src:\
${A2E_ROOT}/task/agents/agno/src:\
${A2E_ROOT}/task/agents/langgraph/src:\
${A2E_ROOT}/task/agents/smolagents/src:\
${A2E_ROOT}/task/agents/openai_agents/src:\
${A2E_ROOT}/task/agents/llama_index/src:\
${A2E_ROOT}/task/agents/crewai/src:\
${A2E_ROOT}/task/agents/google_adk/src:\
${A2E_ROOT}/task/agents/claude_sdk/src:\
${A2E_ROOT}/task/agents/autogen_agentchat/src:\
${A2E_ROOT}/task/runners/src:\
${A2E_ROOT}/server/server/src:\
${A2E_ROOT}/server/packages/a2e-client/src:\
${A2E_ROOT}/server/packages/a2e-otel/src:\
${A2E_ROOT}/eval/packages/a2e-evals/src"

# Localhost must not go through a broken HTTP proxy.
export http_proxy=""
export https_proxy=""
export HTTP_PROXY=""
export HTTPS_PROXY=""

# Datasets are already on disk under ~/.cache/huggingface. Do not wait on
# huggingface.co HEAD/etag checks (those time out without the cluster proxy).
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export HF_DATASETS_OFFLINE="${HF_DATASETS_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"

set -a
# shellcheck disable=SC1091
source "${A2E_ROOT}/.env"
set +a

export OPENAI_API_BASE="${OPENAI_API_BASE:-http://35.220.164.252:3888/v1}"
export A2E_MODEL="${A2E_MODEL:-kimi/kimi-k3}"
# Fair-comparison API budget — every harness reads these via budget.py
export A2E_MAX_TOKENS="${A2E_MAX_TOKENS:-4096}"
export A2E_MAX_TURNS="${A2E_MAX_TURNS:-8}"
export A2E_MAX_STEPS="${A2E_MAX_STEPS:-8}"
export A2E_LLM_TIMEOUT="${A2E_LLM_TIMEOUT:-180}"
# Whole-run wall. run_n1.sh overrides per dataset (DeepSearchQA=1700, τ=1100).
export A2E_RUN_DEADLINE="${A2E_RUN_DEADLINE:-1800}"
export A2E_AGNO_DEADLINE="${A2E_AGNO_DEADLINE:-$A2E_RUN_DEADLINE}"
export A2E_WORKING_DIR="${A2E_ROOT}/.a2e-data-tau-fix"
export A2E_SQL_DATABASE_URL="sqlite:///${A2E_WORKING_DIR}/a2e.db"
export A2E_COLLECTOR_ENDPOINT="http://127.0.0.1:6006"
export no_proxy="127.0.0.1,localhost,10.0.0.0/8,.pjlab.org.cn,35.220.164.252,${no_proxy:-}"
export NO_PROXY="$no_proxy"
mkdir -p "${A2E_WORKING_DIR}"
