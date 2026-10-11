# SeClaw

<div align="center">

**Benchmark for evaluating AI agent safety in synthetic openclaw tasks**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/Docker-Required-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-Apache--2.0-green.svg)](LICENSE)

[English](README.md) | 中文

</div>

## 在 A2E 中的位置

本目录保存 SeClaw 独立运行版本，目前尚未注册到 A2E 统一运行器。下方命令均在本模块目录执行：

```bash
cd task/datasets/seclaw
```

## 项目简介

SeClaw 是 Benchmark for evaluating AI agent safety in synthetic openclaw tasks。它在独立 Docker 容器中运行 AI Agent 安全评测任务；每个任务包含 synthetic OpenClaw workspace、MCP 工具、mock service 和任务专属 grader。当前开源 release 包含 150 个 OpenClaw 任务，以及一个用于模型对比的 Docker 批量执行入口。

公开入口是 `scripts/batch_execute.sh --backend docker`。它会对配置中的每个模型和任务执行一轮本地 Docker 评测，完成轨迹评估，并把结果写入 `batch_logs/{batch_name}`。

## 快速开始

```bash
# 1. 使用 uv 安装依赖并拉取 OpenClaw runtime 镜像。
uv sync
docker pull ghcr.io/openclaw/openclaw:main

# 2. 配置 provider 与待测模型。
cp .env.example .env
cp docker_models_config.example.yaml docker_models_config.yaml
# 编辑 .env 和 docker_models_config.yaml，填入 OpenAI-compatible provider。

# 3. 运行 v1 公开任务集。
bash scripts/batch_execute.sh \
  --backend docker \
  --tasks-jsonl batch_inputs/version/v1/test_tasks.jsonl \
  --models-config docker_models_config.yaml \
  --docker-concurrency 2 \
  --batch-logs batch_logs \
  --batch-name docker_eval_v1

# 4. 查看结果。
cat batch_logs/docker_eval_v1/scores.json | python -m json.tool
open batch_logs/docker_eval_v1/report.md
```

SeClaw 推荐使用 `uv` 管理依赖。存在 `uv.lock` 时，批量入口会使用 `uv run --frozen python`，因此公开 benchmark 运行会使用仓库中锁定的依赖版本，而不会在执行过程中重新解析依赖。如果本地没有 `uv`，仍可使用轻量兼容路径：`python3 -m pip install -r benchmark/requirements.txt`。

`docker_models_config.yaml` 可以配置多个 `models` 条目。每个条目都可以使用不同的 `model`、`base_url` 和 `api_key_env`，并通过 `.env` 中的 `DOCKER_BACKEND_MODEL_ID`、`DOCKER_BACKEND_BASE_URL`、`DOCKER_BACKEND_API_KEY` 等变量提供具体 provider 值。

如需 LLM judge 评分，复制 `judge_models_config.example.yaml` 为 `judge_models_config.yaml`，在 `.env` 中配置 `EVAL_JUDGE_*` provider 变量。Judge config 同样支持多个 provider。只跑规则 grader 时传 `--skip-judge`。

开发或验证任务本地服务时，可用 `uv sync --group task-test` 安装可选测试依赖，并用 `uv run --frozen python -m unittest discover -s tests` 运行测试。

## Release 内容

| 路径 | 说明 |
|------|------|
| `tasks/openclaw/` | 150 个 OpenClaw 任务目录，每个任务可直接运行。 |
| `batch_inputs/version/v1/test_tasks.jsonl` | v1 公开任务清单，行内使用 `task_name`、`task_id` 和 `target`。 |
| `scripts/batch_execute.sh` | 面向开源 benchmark 的 Docker-only 批量入口。 |
| `scripts/docker_execute_backend.py` | 执行每个模型的 Docker 评测并归一化输出。 |
| `benchmark/` | 批量入口使用的 Docker runtime integration。 |
| `docker_models_config.example.yaml` | 待测模型配置模板。 |
| `judge_models_config.example.yaml` | 可选 judge 模型配置模板。 |

## 任务结构

每个公开任务使用如下目录结构：

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

## 批量产物

`batch_execute.sh --backend docker` 标准产物：

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

## 常用参数

| 参数 | 说明 |
|------|------|
| `--tasks-jsonl` | JSONL 任务清单，推荐用于 release 任务集。 |
| `--tasks-dir` | 任务目录，与 `--tasks-jsonl` 二选一。 |
| `--models-config` | 待测模型 YAML 配置，必填。 |
| `--docker-concurrency` | 每个模型并行运行的 Docker task 容器数。 |
| `--docker-image` | 覆盖默认 OpenClaw 镜像。 |
| `--docker-timeout` | 单任务超时秒数。 |
| `--docker-init-timeout` | `fixture/init.sh` 超时秒数。 |
| `--skip-judge` | 只运行任务 grader，跳过 LLM judge。 |
| `--judge-models-config` | 可选 multi-judge 配置。 |
| `--skip-analyze` | 跳过 `report.md` 和 `analysis.json`。 |

## 文档

| 文档 | 说明 |
|------|------|
| [benchmark/README.md](benchmark/README.md) | 批量入口使用的 Docker runtime 架构。 |
| [docs/task-extension-guide.md](docs/task-extension-guide.md) | 任务编写参考。 |
| [docs/grading-design.md](docs/grading-design.md) | Grader 与 judge rubric 设计。 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南。 |
| [SECURITY.md](SECURITY.md) | 安全政策。 |

## 常见问题

- Docker 不可用：启动 Docker 并拉取 `ghcr.io/openclaw/openclaw:main`。
- 模型 401：检查 `.env` 中该模型对应的 `api_key_env`，以及 `docker_models_config.yaml` 中的 `base_url`。
- MCP 工具缺失：查看 `batch_logs/{batch_name}/logs/` 和对应 trace 下的 `agent_stderr.txt`。
- 初始化慢：增大 `--docker-init-timeout`。
- Judge 未执行：配置 `judge_models_config.yaml` 与 `EVAL_JUDGE_*` 变量；只跑 grader 时传 `--skip-judge`。

## License

Apache License 2.0。详见 [LICENSE](LICENSE)。
