# SeClaw

<div align="center">

**Benchmark for evaluating AI agent safety in synthetic openclaw tasks**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/Docker-Required-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-Apache--2.0-green.svg)](LICENSE)

English | [中文](README_zh.md)

</div>

## A2E placement

This directory contains the standalone SeClaw release. It is not yet registered with the A2E unified runner. Run the commands below from this module directory:

```bash
cd task/datasets/seclaw
```

## Overview

SeClaw runs AI agent safety tasks in isolated Docker containers. Each task provides a synthetic OpenClaw workspace, MCP tools, mock services, and a task-specific grader. The public release contains 150 OpenClaw tasks plus a Docker batch runner that produces local, reproducible artifacts for model comparison.

The public entry point is `scripts/batch_execute.sh --backend docker`. It runs one local Docker round for every configured model and task, evaluates trajectories, and writes batch-style outputs under `batch_logs/{batch_name}`.

## Quick Start

```bash
# 1. Install Python dependencies with uv and pull the OpenClaw runtime image.
uv sync
docker pull ghcr.io/openclaw/openclaw:main

# 2. Configure model providers and models under test.
cp .env.example .env
cp docker_models_config.example.yaml docker_models_config.yaml
# Edit .env and docker_models_config.yaml for your OpenAI-compatible providers.

# 3. Run the public v1 task list.
bash scripts/batch_execute.sh \
  --backend docker \
  --tasks-jsonl batch_inputs/version/v1/test_tasks.jsonl \
  --models-config docker_models_config.yaml \
  --docker-concurrency 2 \
  --batch-logs batch_logs \
  --batch-name docker_eval_v1

# 4. Inspect results.
cat batch_logs/docker_eval_v1/scores.json | python -m json.tool
open batch_logs/docker_eval_v1/report.md
```

`uv` is the recommended dependency manager for SeClaw. The batch runner uses `uv run --frozen python` when `uv.lock` is present, so public benchmark runs use the checked-in lockfile instead of resolving dependencies during execution. If `uv` is not available, the lightweight compatibility path remains `python3 -m pip install -r benchmark/requirements.txt`.

`docker_models_config.yaml` can contain multiple `models` entries. Each entry can point to a different provider by using its own `model`, `base_url`, and `api_key_env`, with the values supplied from `.env` such as `DOCKER_BACKEND_MODEL_ID`, `DOCKER_BACKEND_BASE_URL`, and `DOCKER_BACKEND_API_KEY`.

For LLM judge scoring, copy `judge_models_config.example.yaml` to `judge_models_config.yaml` and set `EVAL_JUDGE_*` provider variables in `.env`. The judge config also supports multiple providers. Use `--skip-judge` for grader-only runs.

For development and task-local service checks, install optional task test dependencies with `uv sync --group task-test` and run tests with `uv run --frozen python -m unittest discover -s tests`.

## Public Release Contents

| Path | Purpose |
|------|---------|
| `tasks/openclaw/` | 150 OpenClaw task directories. Each task is directly runnable. |
| `batch_inputs/version/v1/test_tasks.jsonl` | Public task list for the v1 release. Rows use `task_name`, `task_id`, and `target`. |
| `scripts/batch_execute.sh` | Docker-only batch entry point for public benchmarking. |
| `scripts/docker_execute_backend.py` | Runs per-model Docker evaluations and normalizes outputs into batch artifacts. |
| `benchmark/` | Docker runtime integration used by the batch entry point. |
| `docker_models_config.example.yaml` | Sanitized model-under-test config template. |
| `judge_models_config.example.yaml` | Optional judge model config template. |

## Task Layout

Each public task uses this directory layout:

```text
tasks/openclaw/<task_id>/
├── task.yaml
├── metadata.yaml
├── grader.py
└── fixture/
    ├── init.sh
    ├── workspace/
    ├── mcp/
    ├── mock_service/
    └── local_files/
```

## Batch Outputs

`batch_execute.sh --backend docker` writes:

```text
batch_logs/{batch_name}/
├── jobs.jsonl
├── scores.json
├── report.md
├── analysis.json
├── logs/
├── .benchmark_runs/
└── traces/
    └── {trace_id}/
        ├── session_transcript.jsonl
        ├── transcript.jsonl
        ├── evaluation.json
        ├── grading.json
        ├── execution.json
        ├── audit_data.json
        └── workspace/
```

## Key CLI Options

| Option | Description |
|--------|-------------|
| `--tasks-jsonl` | JSONL task list with `task_name`, `task_id`, and `target`. Recommended for the release set. |
| `--tasks-dir` | Task directory, used instead of `--tasks-jsonl`. |
| `--models-config` | YAML model config for models under test. Required. |
| `--docker-concurrency` | Parallel Docker task containers per model. |
| `--docker-image` | OpenClaw image override. |
| `--docker-timeout` | Per-task timeout in seconds. |
| `--docker-init-timeout` | `fixture/init.sh` timeout in seconds. |
| `--skip-judge` | Run only task graders. |
| `--judge-models-config` | Optional multi-judge config. |
| `--skip-analyze` | Skip `report.md` and `analysis.json`. |

## Documentation

| Document | Description |
|----------|-------------|
| [benchmark/README.md](benchmark/README.md) | Docker runtime architecture used by the batch entry point. |
| [docs/task-extension-guide.md](docs/task-extension-guide.md) | Task authoring reference. |
| [docs/grading-design.md](docs/grading-design.md) | Grader and judge rubric design. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution guidelines. |
| [SECURITY.md](SECURITY.md) | Security policy. |

## Troubleshooting

- Docker unavailable: start Docker and pull `ghcr.io/openclaw/openclaw:main`.
- Model 401: check the model's `api_key_env` in `.env` and `base_url` in `docker_models_config.yaml`.
- MCP tools missing: inspect `batch_logs/{batch_name}/logs/` and the per-trace `agent_stderr.txt`.
- Slow initialization: increase `--docker-init-timeout`.
- Judge skipped: configure `judge_models_config.yaml` with `EVAL_JUDGE_*` variables, or pass `--skip-judge` for grader-only runs.

## License

Apache License 2.0. See [LICENSE](LICENSE).
