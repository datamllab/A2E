<p align="center">
  <img src="ui/ailab-logo.png" alt="Shanghai AI Lab" width="540"/>
</p>

<h1 align="center">
  <img src="docs/A2E_logo.png" alt="A2E" width="200" align="absmiddle"/>
  &nbsp;&nbsp;An End-to-End Agent Auditing Engine
</h1>

<p align="center">
  <em>An agent auditing engine — evaluate any agent on any dataset, with full trace visibility.</em>
</p>

<p align="center">
  <strong>English</strong> | <a href="README_zh.md">中文</a>
</p>

---

## Overview

**A<sup>2</sup>E** (Agent Auditing Engine) is an end-to-end auditing engine for agent
harnesses. It uses the **Agent Task Protocol (ATP)** to plug evaluation tasks into
different harnesses quickly, captures standardized execution traces via an
auto-instrumented **Monitor**, and scores harness capabilities with
multidimensional metrics beyond accuracy alone.

The core loop is **TASK → SERVER → EVAL → UI**. **TASK** runs Benchmark × Agent
(optionally in a sandbox) while **Monitor** auto-instruments the run and writes
runs + traces to **SERVER**. **EVAL** then pulls traces from the server, scores
both the process (**TRACE EVAL**) and the final result (**OUTCOME EVAL**), and
writes scores back. **UI** reads from the server to display traces and scores.
**SERVER** is the hub that stores data, traces, and eval results for the other
three stages.

<p align="center">
  <img src="ui/pipeline.png" alt="A2E pipeline" width="720"/>
</p>

## Project Structure

```
AEP/
├── script/              # One-click install + server start
├── server/              # Backend + REST API + a2e-client SDK
├── task/                # Datasets, agents, experiment runners
│   ├── datasets/        # Benchmark adapters
│   ├── agents/          # Agent framework adapters
│   ├── runners/         # Registry (DATASETS / AGENTS / EVALUATORS)
│   └── examples/        # CLI: run_experiment.py
├── eval/                # Standalone evaluation pipeline
├── monitor/             # OpenInference instrumentation
├── ui/                  # React experiment viewer
└── example/             # Interactive walkthrough script
```

## Contents

1. [Quick start](#1-quick-start)
2. [Task Layer](#2-task-layer)
3. [Eval Layer](#3-eval-layer)
4. [UI Layer](#4-ui-layer)

## 1. Quick start

### One-click install & serve

```bash
bash script/start.sh
```

Prerequisites are listed in the script header. Syncs `task` / `server` / `eval`, builds the UI, creates `.env` from `.env.example` when missing, and starts the server at http://localhost:6006.

### Configure `.env`

Before running experiments, copy `.env.example` to `.env` and fill in API keys.
See comments in `.env.example` for field meanings and override priority.

## 2. Task Layer

Entry point: `task/examples/run_experiment.py`.

### Start server + run an experiment

```bash
# Terminal 1 — keep open
bash script/start.sh                 # → http://localhost:6006

# Terminal 2
cd task
set -a; . ../.env; set +a
export no_proxy="127.0.0.1,localhost,${no_proxy:-}"; export NO_PROXY="$no_proxy"
uv run --frozen python examples/run_experiment.py \
  --dataset tau-bench --agent agno --model qwen-max \
  --evaluators tool_recall,llm_judge --domain retail
```

Or follow the interactive walkthrough: `bash example/run_examples.sh`.

### CLI

```bash
uv run --frozen python examples/run_experiment.py \
  --dataset <dataset> \
  --agent   <framework>      # default: agno
  --model   <model>          # default: A2E_MODEL from .env
  --evaluators <a,b,...>     # default: exact_match,substring
  --n       <count>          # default: 40
  --sample-seed 20260721     # optional, reproducible sample
  --domain  retail           # tau-bench / tau2 only
```

| Flag | Purpose |
|------|---------|
| `--list` | Print all datasets/agent harnesses/evaluators (source of truth) |
| `--dataset` | Dataset name (required) |
| `--agent` | Agent harnesses (default `agno`) |
| `--model` | Override `A2E_MODEL` for this run |
| `--evaluators` | Comma-separated scorers |
| `--n` | Sample size (absolute count, random without replacement) |
| `--domain` | `retail` / `airline` (tau-bench / tau2) |

```bash
uv run --frozen python examples/run_experiment.py --list
```

### Datasets / Agent Harnesses / Evaluators

| Datasets |
|---|
| tau-bench, tau2, tau3, traject-bench, mmlu, gsm8k, humaneval, gpqa, mmlu-pro, math, bbh, swe-bench-lite, swe-bench-verified, swe-bench-pro, terminal-bench-2, terminal-bench-2.1, … |

| Agent Harnesses |
|---|
| smolagents · agno · llama-index · langgraph · crewai · google-adk · autogen-agentchat · claude-sdk · openai-agents |


Built-in evaluators: `exact_match`, `substring`, `tool_recall`, `numeric_match`,
`mc_letter`, `swe_resolved`, `swe_fail_to_pass`, `swe_pass_to_pass`, `tb_resolved`,
plus `llm_judge`. Recommended combos live in `task/runners/.../registry.py`
(`default_evaluators`).

### Sandbox tips

Needs Docker and pullable images (1–3 GB each). Pin a cached instance before formal runs:

```bash
A2E_SWE_INSTANCE="<cached_instance_id>" \
uv run --frozen python examples/run_experiment.py \
  --dataset swe-bench-lite --agent agno --n 1 \
  --evaluators swe_resolved,swe_fail_to_pass,swe_pass_to_pass
```

- `swe-bench-pro` → `A2E_SWE_PRO_INSTANCE`
- `terminal-bench-2` → `A2E_TB2_TASK=<task>`

### View results

Open http://localhost:6006:

| Page | What you see |
|------|----------------|
| `/datasets` | Uploaded samples |
| `/experiments` | Per-sample scores |
| `/projects` | OpenTelemetry trace trees (LLM + tool calls) |

Task traces live under the **`Experiment-<id>`** project.

## 3. Eval Layer

The eval layer pulls existing traces, scores them, and writes results back.
Task runs do not require eval; pass `--evaluators` on the task CLI for lightweight
inline scoring, or use `eval/` for deeper metric groups.

### Run all metrics

```bash
# Terminal 1
bash script/start.sh

# Terminal 2
cd server
uv run python ../eval/scripts/run_eval.py \
  --base-url http://localhost:6006 \
  --experiment-id <id> \
  --part all
```

### Run one metric group

Supported parts:

```text
plan, skill, memory, tool, correct, efficiency, safety
```

```bash
cd server
uv run python ../eval/scripts/run_eval.py \
  --base-url http://localhost:6006 \
  --experiment-id <id> \
  --part plan
```

## 4. UI Layer

React experiment viewer. Production build is served by `a2e serve` at
http://localhost:6006. Swipe between **Task / Trace / Eval** for the same sample;
open the Trace panel for the span tree.

### Production

```bash
cd ui && pnpm install && pnpm build
bash script/start.sh                # http://localhost:6006
```

Artifacts go to `ui/dist/`. The server mounts them automatically.

### Development (HMR)

```bash
# Terminal 1
bash script/start.sh                # http://127.0.0.1:6006

# Terminal 2
cd ui && pnpm install && pnpm dev   # http://127.0.0.1:5173  (proxies /v1 → :6006)
```

Or use `a2e serve --dev` for Vite HMR via the server templates.

## Acknowledgements

A<sup>2</sup>E depends on and draws from the following open-source projects:

- [OpenInference](https://github.com/Arize-ai/openinference)
- [Phoenix](https://github.com/Arize-ai/phoenix)
