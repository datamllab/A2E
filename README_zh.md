<p align="center">
  <img src="docs/A2E_logo.jpg" alt="A2E" width="900"/>
</p>

<p align="center">
  <a href="https://arxiv.org/abs/2608.07346"><img src="https://img.shields.io/badge/Paper-b31b1b?style=for-the-badge&logo=arxiv&logoColor=white" alt="Paper"/></a>
  <a href="https://github.com/datamllab/A2E"><img src="https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub"/></a>
  <a href="https://colab.research.google.com/github/stevewithjobs/AEP/blob/yuchenyue/notebooks/a2e_quickstart.ipynb"><img src="https://img.shields.io/badge/Colab-F9AB00?style=for-the-badge&logo=googlecolab&logoColor=white" alt="Colab"/></a>
  <a href="https://huggingface.co/papers/2608.07346"><img src="https://img.shields.io/badge/HuggingFace-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black" alt="HuggingFace"/></a>
</p>

<p align="center">
  <a href="#-更新日志">🎉 更新日志</a> •
  <a href="#1-快速开始">🚀 快速开始</a> •
  <a href="#2-构建实验">🧪 构建实验</a> •
  <a href="#3-捕获轨迹">📡 捕获轨迹</a> •
  <a href="#4-评测打分">📊 评测打分</a> •
  <a href="#5-查看结果">👀 查看结果</a>
</p>

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

A<sup>2</sup>E 与 harness、模型厂商无关，对主流 agent SDK（[OpenAI Agents SDK](#harness-openai-agents)、[Claude Agent SDK](#harness-claude-sdk)、[LangGraph](#harness-langgraph)、[Google ADK](#harness-google-adk)、[AutoGen AgentChat](#harness-autogen-agentchat)、[CrewAI](#harness-crewai)、[LlamaIndex](#harness-llama-index)、[Agno](#harness-agno)、[smolagents](#harness-smolagents)）开箱即用，模型侧走任意 OpenAI 兼容端点或 Anthropic 端点。每个 harness 都通过 OpenInference 自动打桩，你的 agent 代码无需改动 —— 完整列表与 instrumentor 路径见[支持的 harness 表](#3-捕获轨迹)。

## 🎉 更新日志

- **2026-08-12** — 🤗 论文页面已上线 [Hugging Face](https://huggingface.co/papers/2608.07346)。
- **2026-08-11** — 📓 [Colab quickstart notebook](https://colab.research.google.com/github/stevewithjobs/AEP/blob/yuchenyue/notebooks/a2e_quickstart.ipynb) 已发布，可在浏览器中端到端跑通 A<sup>2</sup>E。
- **2026-08-10** — ✨✨ A<sup>2</sup>E 完整代码库已发布。
- **2026-08-07** — 📄 A<sup>2</sup>E 预印本已发布于 [arXiv](https://arxiv.org/abs/2608.07346)。

## 1. 快速开始

**Dependency**

```bash
bash scripts/start.sh
```

**API key**

```bash
cp .env.example .env
# fill in the values below
```

然后打开 http://localhost:6006。

## 2. 构建实验

选定数据集与 agent harness 后运行：

```bash
# 终端 1 — 保持服务运行
bash scripts/start.sh                 # → http://localhost:6006

# 终端 2 — 官方 n=1 单格（评测器与 seed 按数据集选择）
# source scripts/a2e_net.sh             # autogen-agentchat 用 source scripts/autogen_env.sh
bash scripts/run_n1.sh <agent> <dataset>
# 例如 bash scripts/run_n1.sh agno tau-bench
#      bash scripts/run_n1.sh langgraph deepsearchqa
#      bash scripts/run_n1.sh llama-index gdpval-aa
```

也可走交互式示例：`bash example/run_examples.sh`。

### CLI

自定义实验在 `task/` 下跑（环境与 `run_n1.sh` 相同，不要 `uv sync`）：

```bash
# source scripts/a2e_net.sh
cd task
"$AEP_PY" examples/run_experiment.py \
  --dataset <数据集> \
  --agent   <框架>           # 默认 agno
  --model   kimi/kimi-k3 \
  --evaluators <a,b,...>     # 见下表；run_n1.sh 会自动填
  --n       1 \
  --sample-seed 20260816 \
  --domain  retail           # tau-bench / tau2 / tau3
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
# source scripts/a2e_net.sh
cd task
"$AEP_PY" examples/run_experiment.py --list
```

### Benchmarks

每个 benchmark 都内置了一组默认评测指标，可用 `--evaluators` 覆盖。
使用 `--list` 可查看全部 benchmark、agent harness 和 evaluator。

| Benchmark | 类型 | 内置默认评测指标 | 沙箱 |
|-----------|------|----------------------|------|
| `tau-bench` | Tool | `tool_recall`, `llm_judge` | / |
| `tau2` | Tool | `tool_recall`, `llm_judge` | / |
| `tau3` | Tool | `tool_recall`, `llm_judge` | / |
| `traject-bench` | Tool | `tool_recall`, `llm_judge` | / |
| `mmlu` | QA | `mc_letter`, `llm_judge` | / |
| `gsm8k` | QA | `numeric_match`, `llm_judge` | / |
| `humaneval` | QA | `substring`, `llm_judge` | / |
| `persistbench` | QA | `substring`, `llm_judge` | / |
| `gdpval-aa` | QA | `llm_judge` | HF [`openai/gdpval`](https://huggingface.co/datasets/openai/gdpval) |
| `gpqa` | QA | `mc_letter`, `llm_judge` | / |
| `mmlu-pro` | QA | `mc_letter`, `llm_judge` | / |
| `arc-challenge` | QA | `mc_letter`, `llm_judge` | / |
| `truthfulqa` | QA | `mc_letter`, `llm_judge` | / |
| `agieval` | QA | `mc_letter`, `llm_judge` | / |
| `commonsenseqa` | QA | `mc_letter`, `llm_judge` | / |
| `hellaswag` | QA | `mc_letter`, `llm_judge` | / |
| `openbookqa` | QA | `mc_letter`, `llm_judge` | / |
| `bbh` | QA | `exact_match`, `llm_judge` | / |
| `math` | QA | `numeric_match`, `llm_judge` | / |
| `swe-bench-lite` | Sandbox | `swe_resolved`, `swe_fail_to_pass`, `swe_pass_to_pass` | ✅ |
| `swe-bench-verified` | Sandbox | `swe_resolved`, `swe_fail_to_pass`, `swe_pass_to_pass` | ✅ |
| `swe-bench-pro` | Sandbox | `swe_resolved`, `swe_fail_to_pass`, `swe_pass_to_pass` | ✅ |
| `terminal-bench-2` | Sandbox | `tb_resolved` | ✅ |
| `terminal-bench-2.1` | Sandbox | `tb_resolved` | ✅ |

### Agent Harnesses

所有支持的 agent harness 都会自动打桩。使用 `--agent` 选择：

| `--agent` | Harness |
|-----------|---------|
| `agno` | Agno |
| `smolagents` | smolagents |
| `llama-index` | LlamaIndex |
| `langgraph` | LangGraph |
| `crewai` | CrewAI |
| `google-adk` | Google ADK |
| `autogen-agentchat` | AutoGen AgentChat |
| `claude-sdk` | Claude Agent SDK |
| `openai-agents` | OpenAI Agents SDK |

实现与 OpenInference 打桩包路径见 [捕获轨迹](#3-捕获轨迹)。

### 沙盒实验

沙盒 benchmark 需要 Docker，且每个镜像约为 1–3 GB。如需可复现的 SWE-bench
实验，将已缓存的实例 ID 传给辅助脚本：

```bash
bash task/run_sandbox_experiment.sh <cached_instance_id>
```

## 3. 捕获轨迹

实验运行时，**Monitor** 会自动打桩：LLM 调用、tool 调用及相关 span 以
OpenTelemetry / OpenInference 轨迹写入 server。对已支持的 harness，通常不需要单独做捕获步骤。

已支持自动打桩的 agent harness：

| `--agent` | Harness 目录 | OpenInference 打桩包 |
|-----------|--------------|----------------------|
| <a id="harness-agno"></a>`agno` | `task/agents/agno` | `monitor/instrumentation/openinference-instrumentation-agno` |
| <a id="harness-smolagents"></a>`smolagents` | `task/agents/smolagents` | `monitor/instrumentation/openinference-instrumentation-smolagents` |
| <a id="harness-llama-index"></a>`llama-index` | `task/agents/llama_index` | `monitor/instrumentation/openinference-instrumentation-llama-index` |
| <a id="harness-langgraph"></a>`langgraph` | `task/agents/langgraph` | `monitor/instrumentation/openinference-instrumentation-langchain` |
| <a id="harness-crewai"></a>`crewai` | `task/agents/crewai` | `monitor/instrumentation/openinference-instrumentation-crewai` |
| <a id="harness-google-adk"></a>`google-adk` | `task/agents/google_adk` | `monitor/instrumentation/openinference-instrumentation-google-adk` |
| <a id="harness-autogen-agentchat"></a>`autogen-agentchat` | `task/agents/autogen_agentchat` | `monitor/instrumentation/openinference-instrumentation-autogen-agentchat` |
| <a id="harness-claude-sdk"></a>`claude-sdk` | `task/agents/claude_sdk` | `monitor/instrumentation/openinference-instrumentation-anthropic` |
| <a id="harness-openai-agents"></a>`openai-agents` | `task/agents/openai_agents` | `monitor/instrumentation/openinference-instrumentation-openai-agents` |
| <a id="harness-pi"></a>`pi` | `task/agents/pi` | `monitor/instrumentation-js/openinference-instrumentation-pi` |
| <a id="harness-deepseek-harness"></a>`deepseek-harness` | `task/agents/deepseek_harness` | `monitor/instrumentation-js/openinference-instrumentation-deepseek-harness` |

Pi 同时支持两种接入：裸 `pi-agent-core` 通过公开的 `Agent.subscribe()` API
进行打桩，完整 `pi-coding-agent` 则通过非侵入式 Package 扩展进行监控。
安装与运行方式见 [Pi 接入说明](./task/agents/pi/README.md)。

公共 OpenInference 能力还在 `monitor/openinference-instrumentation` 与
`monitor/openinference-semantic-conventions`。具体框架映射由
`task/runners/.../registry.py` 中的 `framework_for_agent()` 决定。

捕获到的轨迹在 http://localhost:6006 的 **Trace** 页面查看：打开某条样本后切到
Trace，即可看到 LLM / tool 调用的 span 树。

## 4. 评测打分

轨迹入库后，用 `eval/` 中的统一评测流水线对过程与最终结果打分。构建实验时仍可用
`--evaluators` 做轻量内联评分；更深的指标分组（规划、工具、记忆、正确性、效率、安全）
走 `eval/`。

完整说明见 [`eval/README.md`](eval/README.md)。

### 跑完全部指标

```bash
# 终端 1 — 保持服务运行
bash scripts/start.sh                 # → http://localhost:6006

# 终端 2
cd server
uv run python ../eval/scripts/run_eval.py \
  --base-url http://localhost:6006 \
  --experiment-id <experiment_id> \
  --part all
```

### 跑某一组指标

| 部分 | 评测内容 |
|------|----------|
| `plan` | 规划质量与决策 |
| `skill` | 执行技能（如简洁性） |
| `memory` | 记忆 / 忠实性 |
| `tool` | 工具选择与执行 |
| `correct` | 最终任务正确性 |
| `efficiency` | token、成本、轮次、耗时 |
| `safety` | 安全相关行为 |

```bash
cd server
uv run python ../eval/scripts/run_eval.py \
  --base-url http://localhost:6006 \
  --experiment-id <experiment_id> \
  --part plan
```

支持的部分：

```text
plan, skill, memory, tool, correct, efficiency, safety
```

## 5. 查看结果

React 查看器由 `a2e serve` 挂载在 http://localhost:6006（`scripts/start.sh` 会先构建 UI）。
可在同一条样本上左右滑动切换 **Task / Trace / Eval**，在 Trace 面板查看 span 树。

### 开发模式（HMR）

`scripts/start.sh` 会构建生产 UI。若要用 Vite HMR，请分别启动 API 与前端：

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
├── scripts/             # 一键安装并启动服务
├── task/                # 构建实验（数据集、agent、runners）
├── monitor/             # 捕获轨迹（自动打桩）
├── eval/                # 评测打分（过程与结果）
├── server/              # 存放 runs、轨迹与分数
├── ui/                  # 查看结果
└── example/             # 交互式走查
```

这几个目录不是自上而下的分层，而是四个彼此独立、只在 server 处汇合的环节。下图是它们之间实际传递的东西：

<p align="center">
  <img src="docs/pipeline.png" alt="A2E 管线" width="720"/>
</p>

- **`task/` + `monitor/` — ①** `task/` 把 benchmark 与 agent harness 配对，放进沙盒里跑；`monitor/` 包在这次运行外层，自动打桩采集每一次 LLM / tool 调用，并把 run 与轨迹写入 server。harness 本身不需要改：你的 agent 代码完全不必知道 A<sup>2</sup>E 的存在。
- **`server/` — 中枢** 一个本地存储，存三类记录：`data`（数据集与样本）、`trace`（执行树）、`eval`（分数）。其余组件只跟它打交道，彼此之间不直接通信 —— 所以一次 run 跑完很久之后，仍然可以重新打分。
- **`eval/` — ② ③** 把轨迹取回来，从两个维度打分：*trace eval* 看过程（工具选得对不对、调用顺序是否合理），*outcome eval* 看最终答案。分数按相同的 trace ID 写回 server。
- **`ui/` — ④** 把这些全部读回来，在 http://localhost:6006 展示数据集、实验、轨迹树与分数。

正因为一切都经由 server 中转，每个环节都能单独跑：今天先采轨迹，下周再加一个 evaluator，然后直接给旧的 run 打分，一次 agent 都不用重跑。

## 致谢

A<sup>2</sup>E 的实现依赖并参考了以下开源项目：

- [OpenInference](https://github.com/Arize-ai/openinference)
- [Phoenix](https://github.com/Arize-ai/phoenix)

## 许可证

A<sup>2</sup>E 使用 [MIT License](LICENSE) 开源。

## 引用

如果 A<sup>2</sup>E 对你的研究有帮助，欢迎引用：

```bibtex
@misc{wang2026a2eendtoendagent,
      title={$A^2E$ : An End-to-End Agent Auditing Engine}, 
      author={Haoning Wang and Mingxun Zhang and Chenyue Yu and Yingjun Shang and Xia Hu and Guanchu Wang and Na Zou},
      year={2026},
      eprint={2608.07346},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2608.07346}, 
}
```
