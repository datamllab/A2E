

#   An End-to-End Agent Auditing Engine  
端到端智能体审计引擎

*智能体审计引擎 — 在任意数据集上评测任意 agent，并具备完整轨迹可见性。*

[English](README.md) | **中文**

---

## 概述

**A2E**（Agent Auditing Engine）是面向 agent harness 的端到端智能体审计引擎。它基于
**Agent Task Protocol（ATP）** 将评测任务快速接入不同 harness，通过自动打桩的
**Monitor** 采集标准化执行轨迹，并以多维指标（而不只是准确率）系统评估 harness 能力。

核心逻辑是 **TASK → SERVER → EVAL → UI** 闭环。**TASK** 在沙盒中跑 Benchmark × Agent，
并由 **Monitor** 自动打桩、监控，将 runs + traces 写入 **SERVER**；**EVAL** 从服务端
拉取轨迹，分别做过程评测（**TRACE EVAL**）与结果评测（**OUTCOME EVAL**），再把分数写回；
**UI** 从服务端读取并展示轨迹与得分。**SERVER** 作为中枢，统一存放 data / trace / eval，
供其余三端读写。



## 项目结构

```
AEP/
├── script/              # 一键安装依赖并启动服务
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

1. [快速开始](#1-快速开始)
2. [Task Layer](#2-task-layer)
3. [Eval Layer](#3-eval-layer)
4. [UI Layer](#4-ui-layer)

## 1. 快速开始

### 一键安装并启动服务

```bash
bash script/start.sh
```

前置条件见脚本头部注释。依次 sync `task` / `server` / `eval`、构建 UI；若没有 `.env` 则从 `.env.example` 复制，并启动服务：http://localhost:6006。

### 配置 `.env`

跑实验前将 `.env.example` 复制为 `.env` 并填入 API key。
字段含义与覆盖优先级见 `.env.example` 内注释。

## 2. Task Layer

入口：`task/examples/run_experiment.py`。

### 启动服务并跑实验

```bash
# 终端 1 — 保持运行
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


| 旗标             | 作用                                               |
| -------------- | ------------------------------------------------ |
| `--list`       | 打印全部 dataset / agent harnesses / evaluator（权威清单） |
| `--dataset`    | 数据集名（必填）                                         |
| `--agent`      | agent harnesses（默认 `agno`）                       |
| `--model`      | 覆盖本次的 `A2E_MODEL`                                |
| `--evaluators` | 逗号分隔打分器                                          |
| `--n`          | 样本数（绝对数量，随机无放回）                                  |
| `--domain`     | `retail` / `airline`（tau-bench / tau2）           |


```bash
uv run --frozen python examples/run_experiment.py --list
```

### 数据集 / Agent Harnesses / Evaluator


| 数据集                                                                                                                                                                                 |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| tau-bench, tau2, tau3, traject-bench, mmlu, gsm8k, humaneval, gpqa, mmlu-pro, math, bbh, swe-bench-lite, swe-bench-verified, swe-bench-pro, terminal-bench-2, terminal-bench-2.1, … |



| Agent Harnesses                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------ |
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

打开 [http://localhost:6006：](http://localhost:6006：)


| 页面             | 内容                                   |
| -------------- | ------------------------------------ |
| `/datasets`    | 已上传样本                                |
| `/experiments` | 逐样本得分                                |
| `/projects`    | OpenTelemetry trace 树（LLM / tool 调用） |


Task 的 trace 挂在 `**Experiment-<id>**` project 下。

## 3. Eval Layer

评测层独立拉取已有轨迹、打分并写回服务端。
跑 task 不必先跑 eval；task CLI 可传 `--evaluators` 做轻量内联评分，
更深的指标分组用 `eval/`。

### 一次跑完全部 metric

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

React 实验查看器。生产构建由 `a2e serve` 挂载在 [http://localhost:6006。](http://localhost:6006。)
可在同一条样本上左右滑动切换 **Task / Trace / Eval**，在 Trace 面板查看 span 树。

### 生产构建

```bash
cd ui && pnpm install && pnpm build
bash script/start.sh                # http://localhost:6006
```

产物在 `ui/dist/`，服务端会自动挂载。

### 开发模式（HMR）

```bash
# 终端 1
bash script/start.sh                # http://127.0.0.1:6006

# 终端 2
cd ui && pnpm install && pnpm dev   # http://127.0.0.1:5173  （/v1 代理到 :6006）
```

也可使用 `a2e serve --dev`，通过服务端模板启用 Vite HMR。

## 致谢

A2E 的实现依赖并参考了以下开源项目：

- [OpenInference](https://github.com/Arize-ai/openinference)
- [Phoenix](https://github.com/Arize-ai/phoenix)

