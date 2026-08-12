<p align="center">
  <img src="ui/ailab-logo.png" alt="Shanghai AI Lab" width="540"/>
</p>

<h1 align="center">
  <img src="docs/A2E_logo.png" alt="A2E" width="200" align="absmiddle"/>
  &nbsp;&nbsp;An End-to-End Agent Auditing Engine
</h1>

<p align="center">
  <em>Evaluate any agent on any dataset, with full trajectory visibility.</em>
</p>

<p align="center">
  <strong>English</strong> | <a href="README_zh.md">中文</a>
</p>

---

**A<sup>2</sup>E** (Agent Auditing Engine) is an open-source platform for auditing agent harnesses end to end. It helps you:

- **Build experiments** — pair any benchmark with any agent harness and run them through one CLI
- **Capture trajectories** — auto-instrument LLM and tool calls into standardized traces
- **Score results** — score both the process and the final outcome with multidimensional metrics
- **View results** — browse datasets, experiments, and trace trees in a local UI

The loop is simple: **build → capture → score → view**. A local server stores runs, traces, and scores for every step.

<p align="center">
  <img src="ui/pipeline.png" alt="A2E pipeline" width="720"/>
</p>

## Contents

1. [Quick start](#1-quick-start)
2. [Build experiments](#2-build-experiments)
3. [Capture trajectories](#3-capture-trajectories)
4. [Score results](#4-score-results)
5. [View results](#5-view-results)

## 1. Quick start

```bash
bash script/start.sh
```

Prerequisites are listed in the script header. This syncs dependencies, builds the UI, creates `.env` from `.env.example` when missing, and starts the server at http://localhost:6006.

Before running experiments, fill in API keys in `.env`. Field meanings and override priority are documented in `.env.example`.

## 2. Build experiments

Pick a dataset and an agent harness, then run:

```bash
# Terminal 1 — keep the server up
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
| `--list` | Print all datasets / agent harnesses / evaluators |
| `--dataset` | Dataset name (required) |
| `--agent` | Agent harness (default `agno`) |
| `--model` | Override `A2E_MODEL` for this run |
| `--evaluators` | Comma-separated scorers |
| `--n` | Sample size (absolute count, random without replacement) |
| `--domain` | `retail` / `airline` (tau-bench / tau2) |

```bash
uv run --frozen python examples/run_experiment.py --list
```

### Datasets & agent harnesses

| Datasets |
|---|
| tau-bench, tau2, tau3, traject-bench, mmlu, gsm8k, humaneval, gpqa, mmlu-pro, math, bbh, swe-bench-lite, swe-bench-verified, swe-bench-pro, terminal-bench-2, terminal-bench-2.1, … |

| Agent harnesses |
|---|
| smolagents · agno · llama-index · langgraph · crewai · google-adk · autogen-agentchat · claude-sdk · openai-agents |

Built-in scorers include `exact_match`, `substring`, `tool_recall`, `numeric_match`,
`mc_letter`, `swe_resolved`, `swe_fail_to_pass`, `swe_pass_to_pass`, `tb_resolved`,
and `llm_judge`. Recommended combos live in `task/runners/.../registry.py`
(`default_evaluators`).

### Sandbox experiments

Sandbox datasets need Docker and pullable images (1–3 GB each). Pin a cached instance before formal runs:

```bash
A2E_SWE_INSTANCE="<cached_instance_id>" \
uv run --frozen python examples/run_experiment.py \
  --dataset swe-bench-lite --agent agno --n 1 \
  --evaluators swe_resolved,swe_fail_to_pass,swe_pass_to_pass
```

- `swe-bench-pro` → `A2E_SWE_PRO_INSTANCE`
- `terminal-bench-2` → `A2E_TB2_TASK=<task>`

## 3. Capture trajectories

While an experiment runs, **Monitor** auto-instruments the agent: LLM calls, tool calls, and related spans are written to the server as OpenTelemetry / OpenInference traces. You do not need a separate capture step for supported harnesses.

Pi trajectory monitoring is also available for independently launched Pi runs:
standalone `pi-agent-core` Agents use the public `Agent.subscribe()` adapter,
while the full coding agent uses a non-invasive Pi Package extension. This
Monitor integration does not add an A2E `--agent pi` Runner. See the
[Pi monitor setup guide](./monitor/instrumentation-js/a2e-pi-monitor/README.md).

Browse captured trajectories at http://localhost:6006 under **`Experiment-<id>`** projects:

| Page | What you see |
|------|----------------|
| `/datasets` | Uploaded samples |
| `/experiments` | Per-sample scores |
| `/projects` | Trace trees (LLM + tool calls) |

## 4. Evaluation

Evaluate agent runs from both the process and outcome perspectives.

Once trajectories are collected, the evaluation module analyzes agent behavior,
including planning, tool usage, memory, efficiency, safety, and final task
correctness.

Evaluations can be run at different granularities:
- Run the complete evaluation suite to obtain an overall profile.
- Run individual evaluation groups to analyze specific capabilities.

### Run all evaluations

```bash
# Start the evaluation service
bash script/start.sh

# Run the full evaluation pipeline
cd server
uv run python ../eval/scripts/run_eval.py \
  --base-url http://localhost:6006 \
  --experiment-id <id> \
  --part all
## 5. View results

The React viewer is served by `a2e serve` at http://localhost:6006 (built by `script/start.sh`). Swipe between **Task / Trace / Eval** for the same sample; open Trace for the span tree.

### Development (HMR)

`script/start.sh` builds the production UI. For Vite HMR, start the API and the UI separately:

```bash
# Terminal 1 — API only (after deps are installed)
cd server && uv run a2e serve       # http://127.0.0.1:6006

# Terminal 2
cd ui && pnpm install && pnpm dev   # http://127.0.0.1:5173  (proxies /v1 → :6006)
```

Or use `a2e serve --dev` for Vite HMR via the server templates.

## Project layout

```
AEP/
├── script/              # One-click install + server start
├── task/                # Build experiments (datasets, agents, runners)
├── monitor/             # Capture trajectories (auto-instrumentation)
├── eval/                # Score results (process and outcomes)
├── server/              # Store runs, traces, and scores
├── ui/                  # View results
└── example/             # Interactive walkthrough
```

## Acknowledgements

A<sup>2</sup>E depends on and draws from the following open-source projects:

- [OpenInference](https://github.com/Arize-ai/openinference)
- [Phoenix](https://github.com/Arize-ai/phoenix)
