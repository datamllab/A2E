<p align="center">
  <img src="ui/ailab-logo.png" alt="Shanghai AI Lab" width="540"/>
</p>

<h1 align="center">
  <img src="docs/A2E_logo.png" alt="A2E" width="200" align="absmiddle"/>
  &nbsp;&nbsp;An End-to-End Agent Auditing Engine<br/>端到端智能体审计引擎
</h1>

<p align="center">
  <em>智能体审计引擎 — 在任意数据集上评测任意 agent，并具备完整轨迹可见性。</em>
</p>

<p align="center">
  <a href="README.md">English</a> | <strong>中文</strong>
</p>

---

## 概述

**A<sup>2</sup>E**（Agent Auditing Engine）是面向 agent harness 的端到端智能体审计引擎。它基于
**Agent Task Protocol（ATP）** 将评测任务快速接入不同 harness，通过自动打桩的
**Monitor** 采集标准化执行轨迹，并以多维指标（而不只是准确率）系统评估 harness 能力。

核心逻辑是 **TASK → SERVER → EVAL → UI** 闭环。**TASK** 在沙盒中跑 Benchmark × Agent，
并由 **Monitor** 自动打桩、监控，将 runs + traces 写入 **SERVER**；**EVAL** 从服务端
拉取轨迹，分别做过程评测（**TRACE EVAL**）与结果评测（**OUTCOME EVAL**），再把分数写回；
**UI** 从服务端读取并展示轨迹与得分。**SERVER** 作为中枢，统一存放 data / trace / eval，
供其余三端读写。

<p align="center">
  <img src="ui/pipeline.png" alt="A2E 管线" width="720"/>
</p>

## 项目结构

```
AEP/
├── server/              # 后端 + REST API + a2e-client SDK
├── task/                # 数据集、agent 框架、实验运行器
│   ├── datasets/        # Benchmark 适配
│   ├── agents/          # Agent 框架适配
│   ├── runners/         # 注册中心（DATASETS / AGENTS / EVALUATORS）
│   └── examples/        # CLI：run_experiment.py
├── eval/                # 独立评测管线
├── monitor/             # OpenInference 打桩
├── ui/                  # React 实验查看器
└── example/             # 交互式走查脚本
```

## 目录

1. [配置](#1-配置)
2. [Task Layer](#2-task-layer)
3. [Eval Layer](#3-eval-layer)
4. [UI Layer](#4-ui-layer)

## 1. 配置

### 前置条件

| 工具 | 版本 | 说明 |
|------|------|------|
| **Python** | 3.10 – 3.14 | `uv python install 3.11` |
| **uv** | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Docker** | any | 仅沙盒数据集需要（swe-bench、terminal-bench） |
| **Node.js + pnpm** | Node 18+ | 仅重建 UI 时需要 |

### 安装与凭证

```bash
# task — 实验 / 数据集 / agent
cd task && uv sync --frozen --all-packages --index-strategy unsafe-best-match

# server — a2e serve + REST API
cd server && uv sync

# eval — 独立评测管线
cd eval && uv sync

cp .env.example .env   # 填入真实 key
```

`.env`（已 gitignore）：

```bash
A2E_MODEL=qwen3-coder-plus        # 所有 agent 的默认模型
OPENAI_API_KEY=sk-...
OPENAI_API_BASE=...
ANTHROPIC_API_KEY=sk-...          # 仅 claude-sdk
ANTHROPIC_BASE_URL=...            # 不要带尾部 /v1
```

优先级：**CLI 旗标 > `.env` / 环境变量 > 代码默认**。

| 想改的东西 | 改这里 |
|------------|--------|
| 默认模型 | `.env` → `A2E_MODEL` |
| 本次实验模型 | CLI `--model` |
| OpenAI 兼容端点 / key | `.env` → `OPENAI_API_BASE` / `OPENAI_API_KEY`，或 `--api-base` / `--api-key` |
| Anthropic 端点 / key | `.env` → `ANTHROPIC_BASE_URL` / `ANTHROPIC_API_KEY` |
| trajectory 落库位置 | 启动 `a2e serve` 时的 `A2E_WORKING_DIR`（不设 → `~/.a2e/a2e.db`） |

可选：

```bash
# 重建 UI
cd ui && pnpm install && pnpm build

# autogen-agentchat（隔离安装 — 与主 workspace 存在 protobuf 冲突）
cd task/agents/autogen_agentchat && uv sync --index-strategy unsafe-best-match
```

### 跑实验前的三条前提

1. **先起 `a2e serve`，再跑实验** — 脚本通过 HTTP / OTLP 写到正在运行的后端。
2. **`no_proxy` 必须含 `127.0.0.1,localhost`** — 否则 span 会被本地代理丢掉，`a2e.db` 里 `spans=0`。
3. **落库位置由 serve 进程决定** — 看启动时的 `A2E_WORKING_DIR`；实验脚本只写当前后端。

每个跑实验的终端先执行：

```bash
cd task
set -a; . ../.env; set +a
export no_proxy="127.0.0.1,localhost,${no_proxy:-}"; export NO_PROXY="$no_proxy"
```

## 2. Task Layer

入口：`task/examples/run_experiment.py`。

### 启动服务并跑实验

```bash
# 终端 1 — 保持运行
cd server && uv run a2e serve      # → http://localhost:6006

# 终端 2
cd task
set -a; . ../.env; set +a
export no_proxy="127.0.0.1,localhost,${no_proxy:-}"; export NO_PROXY="$no_proxy"
uv run --frozen python examples/run_experiment.py \
  --dataset tau-bench --agent agno --model qwen-max \
  --evaluators tool_recall,llm_judge --domain retail
```

也可走交互式示例：`bash example/run_examples.sh`。

### CLI

```bash
uv run --frozen python examples/run_experiment.py \
  --dataset <数据集> \
  --agent   <框架>           # 默认 agno
  --model   <模型>           # 默认读 .env 的 A2E_MODEL
  --evaluators <a,b,...>     # 默认 exact_match,substring
  --n       <样本数>         # 默认 40
  --sample-seed 20260721     # 可选，固定抽样
  --domain  retail           # 仅 tau-bench / tau2
```

| 旗标 | 作用 |
|------|------|
| `--list` | 打印全部 dataset / agent harnesses / evaluator（权威清单） |
| `--dataset` | 数据集名（必填） |
| `--agent` | agent harnesses（默认 `agno`） |
| `--model` | 覆盖本次的 `A2E_MODEL` |
| `--evaluators` | 逗号分隔打分器 |
| `--n` | 样本数（绝对数量，随机无放回） |
| `--domain` | `retail` / `airline`（tau-bench / tau2） |

```bash
uv run --frozen python examples/run_experiment.py --list
```

### 数据集 / Agent Harnesses / Evaluator

| 数据集 |
|---|
| tau-bench, tau2, tau3, traject-bench, mmlu, gsm8k, humaneval, gpqa, mmlu-pro, math, bbh, swe-bench-lite, swe-bench-verified, swe-bench-pro, terminal-bench-2, terminal-bench-2.1, … |

| Agent Harnesses |
|---|
| smolagents · agno · llama-index · langgraph · crewai · google-adk · autogen-agentchat · claude-sdk · openai-agents |

内置 evaluator：`exact_match`、`substring`、`tool_recall`、`numeric_match`、
`mc_letter`、`swe_resolved`、`swe_fail_to_pass`、`swe_pass_to_pass`、`tb_resolved`，
以及 `llm_judge`。各数据集推荐组合见 `task/runners/.../registry.py` 的
`default_evaluators`。

### 沙盒提示

需要 Docker，并能拉取镜像（单镜像 1–3 GB）。正式跑前建议固定已缓存实例：

```bash
A2E_SWE_INSTANCE="<已缓存的 instance_id>" \
uv run --frozen python examples/run_experiment.py \
  --dataset swe-bench-lite --agent agno --n 1 \
  --evaluators swe_resolved,swe_fail_to_pass,swe_pass_to_pass
```

- `swe-bench-pro` → `A2E_SWE_PRO_INSTANCE`
- `terminal-bench-2` → `A2E_TB2_TASK=<task>`

### 查看结果

打开 http://localhost:6006：

| 页面 | 内容 |
|------|------|
| `/datasets` | 已上传样本 |
| `/experiments` | 逐样本得分 |
| `/projects` | OpenTelemetry trace 树（LLM / tool 调用） |

Task 的 trace 挂在 **`Experiment-<id>`** project 下。

## 3. Eval Layer

评测层独立拉取已有轨迹、打分并写回服务端。
跑 task 不必先跑 eval；task CLI 可传 `--evaluators` 做轻量内联评分，
更深的指标分组用 `eval/`。

### 一次跑完全部 metric

```bash
# 终端 1
cd server && uv run a2e serve

# 终端 2
cd server
uv run python ../eval/scripts/run_eval.py \
  --base-url http://localhost:6006 \
  --experiment-id <id> \
  --part all
```

### 跑某一个部分的 metric

支持的部分：

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

React 实验查看器。生产构建由 `a2e serve` 挂载在 http://localhost:6006。
可在同一条样本上左右滑动切换 **Task / Trace / Eval**，在 Trace 面板查看 span 树。

### 生产构建

```bash
cd ui && pnpm install && pnpm build
cd server && uv run a2e serve       # http://localhost:6006
```

产物在 `ui/dist/`，服务端会自动挂载。

### 开发模式（HMR）

```bash
# 终端 1
cd server && uv run a2e serve       # http://127.0.0.1:6006

# 终端 2
cd ui && pnpm install && pnpm dev   # http://127.0.0.1:5173  （/v1 代理到 :6006）
```

也可使用 `a2e serve --dev`，通过服务端模板启用 Vite HMR。

## 致谢

A<sup>2</sup>E 的实现依赖并参考了以下开源项目：

- [OpenInference](https://github.com/Arize-ai/openinference)
- [Phoenix](https://github.com/Arize-ai/phoenix)
