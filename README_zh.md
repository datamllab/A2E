<p align="center">
  <img src="ui/ailab-logo.png" alt="Shanghai AI Lab" width="540"/>
</p>

<h1 align="center">
  <img src="docs/A2E_logo.png" alt="A2E" width="200" align="absmiddle"/>
  &nbsp;&nbsp;An End-to-End Agent Auditing Engine<br/>端到端智能体审计引擎
</h1>

<p align="center">
  <em>在任意数据集上评测任意 agent，并具备完整轨迹可见性。</em>
</p>

<p align="center">
  <a href="README.md">English</a> | <strong>中文</strong>
</p>

---

**A<sup>2</sup>E**（Agent Auditing Engine）是面向 agent harness 的端到端开源审计平台。它帮你：

- **构建实验** — 用一套 CLI 把任意 benchmark 与任意 agent harness 组合起来跑
- **捕获轨迹** — 自动采集 LLM / tool 调用，沉淀为标准化执行轨迹
- **评测打分** — 同时对过程与最终结果打分，而不仅看准确率
- **查看结果** — 在本地 UI 浏览数据集、实验与轨迹树

闭环很简单：**构建 → 捕获 → 打分 → 查看**。本地 server 统一存放 runs、轨迹与分数。

<p align="center">
  <img src="ui/pipeline.png" alt="A2E 管线" width="720"/>
</p>

## 目录

1. [快速开始](#1-快速开始)
2. [构建实验](#2-构建实验)
3. [捕获轨迹](#3-捕获轨迹)
4. [评测打分](#4-评测打分)
5. [查看结果](#5-查看结果)

## 1. 快速开始

```bash
bash script/start.sh
```

前置条件见脚本头部注释。会同步依赖、构建 UI；若没有 `.env` 则从 `.env.example` 复制，并启动服务：http://localhost:6006。

跑实验前在 `.env` 中填入 API key。字段含义与覆盖优先级见 `.env.example` 内注释。

## 2. 构建实验

选定数据集与 agent harness 后运行：

```bash
# 终端 1 — 保持服务运行
bash script/start.sh                 # → http://localhost:6006

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
| `--list` | 打印全部 dataset / agent harness / evaluator |
| `--dataset` | 数据集名（必填） |
| `--agent` | agent harness（默认 `agno`） |
| `--model` | 覆盖本次的 `A2E_MODEL` |
| `--evaluators` | 逗号分隔打分器 |
| `--n` | 样本数（绝对数量，随机无放回） |
| `--domain` | `retail` / `airline`（tau-bench / tau2） |

```bash
uv run --frozen python examples/run_experiment.py --list
```

### 数据集与 agent harness

| 数据集 |
|---|
| tau-bench, tau2, tau3, traject-bench, mmlu, gsm8k, humaneval, gpqa, mmlu-pro, math, bbh, swe-bench-lite, swe-bench-verified, swe-bench-pro, terminal-bench-2, terminal-bench-2.1, … |

| Agent harness |
|---|
| smolagents · agno · llama-index · langgraph · crewai · google-adk · autogen-agentchat · claude-sdk · openai-agents |

内置打分器：`exact_match`、`substring`、`tool_recall`、`numeric_match`、
`mc_letter`、`swe_resolved`、`swe_fail_to_pass`、`swe_pass_to_pass`、`tb_resolved`，
以及 `llm_judge`。各数据集推荐组合见 `task/runners/.../registry.py` 的
`default_evaluators`。

### 沙盒实验

沙盒数据集需要 Docker，并能拉取镜像（单镜像 1–3 GB）。正式跑前建议固定已缓存实例：

```bash
A2E_SWE_INSTANCE="<已缓存的 instance_id>" \
uv run --frozen python examples/run_experiment.py \
  --dataset swe-bench-lite --agent agno --n 1 \
  --evaluators swe_resolved,swe_fail_to_pass,swe_pass_to_pass
```

- `swe-bench-pro` → `A2E_SWE_PRO_INSTANCE`
- `terminal-bench-2` → `A2E_TB2_TASK=<task>`

## 3. 捕获轨迹

实验运行时，**Monitor** 会自动打桩：LLM 调用、tool 调用及相关 span 以 OpenTelemetry / OpenInference 轨迹写入 server。对已支持的 harness，通常不需要单独做捕获步骤。

在 http://localhost:6006 的 **`Experiment-<id>`** project 下查看轨迹：

| 页面 | 内容 |
|------|------|
| `/datasets` | 已上传样本 |
| `/experiments` | 逐样本得分 |
| `/projects` | 轨迹树（LLM / tool 调用） |

## 4. 评测打分

轨迹入库后，可对过程与最终结果打分。轻量评分可在构建实验时用 `--evaluators` 内联完成；更深的指标分组用 `eval/`。

### 跑完全部指标

```bash
# 终端 1
bash script/start.sh

# 终端 2
cd server
uv run python ../eval/scripts/run_eval.py \
  --base-url http://localhost:6006 \
  --experiment-id <id> \
  --part all
```

### 跑某一组指标

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

## 5. 查看结果

React 查看器由 `a2e serve` 挂载在 http://localhost:6006（`script/start.sh` 会先构建 UI）。
可在同一条样本上左右滑动切换 **Task / Trace / Eval**，在 Trace 面板查看 span 树。

### 开发模式（HMR）

`script/start.sh` 会构建生产 UI。若要用 Vite HMR，请分别启动 API 与前端：

```bash
# 终端 1 — 只起 API（依赖已装好后）
cd server && uv run a2e serve       # http://127.0.0.1:6006

# 终端 2
cd ui && pnpm install && pnpm dev   # http://127.0.0.1:5173  （/v1 代理到 :6006）
```

也可使用 `a2e serve --dev`，通过服务端模板启用 Vite HMR。

## 项目结构

```
AEP/
├── script/              # 一键安装并启动服务
├── task/                # 构建实验（数据集、agent、runners）
├── monitor/             # 捕获轨迹（自动打桩）
├── eval/                # 评测打分（过程与结果）
├── server/              # 存放 runs、轨迹与分数
├── ui/                  # 查看结果
└── example/             # 交互式走查
```

## 致谢

A<sup>2</sup>E 的实现依赖并参考了以下开源项目：

- [OpenInference](https://github.com/Arize-ai/openinference)
- [Phoenix](https://github.com/Arize-ai/phoenix)
