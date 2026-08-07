# autogen-agentchat agent

Single-agent runner powered by **Microsoft AutoGen AgentChat**
(`autogen-agentchat` + `autogen-ext[openai]`).

This is A2E's autogen-agentchat framework adapter: it is **dataset-agnostic**,
consuming any `AgentBinding` and driving the benchmark behind it. Adding a new
benchmark therefore costs one new `binding.py` under `task/datasets/<bench>/` —
no new agent file.

The agent code contains **zero** tracing calls: the
`AutogenAgentChatInstrumentor` (installed by
`ageneval.task.core.setup_instrumentation(framework="autogen_agentchat")`)
captures every agent step / tool call / model call span automatically.

## ⚠️ Isolated uv project (protobuf conflict)

Unlike every other agent in `task/agents/*`, this package is **NOT** a member
of the top-level A2E uv workspace and is **NOT** installed by `uv sync` at the
repo root.

**Reason:** `autogen-core` (a transitive dependency of `autogen-agentchat`)
pins `protobuf>=5.29.3,<5.30`. A2E pulls in `grpcio-tools>=1.78.0`, which
requires `protobuf>=6.31.1,<7.0.0`. These ranges are disjoint, so AutoGen
**cannot** coexist with A2E in a single environment. The conflict is
fundamental, not a version-pin tweak.

This package is therefore a **standalone uv project** with its own `uv.lock`.
`ageneval-task-core` is referenced through an in-repo relative path in
`[tool.uv.sources]` — this does not violate the A2E standalone red line, which
forbids paths *outside* the repository.

## Install & run

```bash
cd task/agents/autogen_agentchat
uv sync --index-strategy unsafe-best-match
uv run python -m ...   # within this isolated environment
```

The `autogen-agentchat` entry in `task/runners/registry.py` carries
`"isolated": True`. Building it from the main workspace `.venv` raises a clear
`RuntimeError` pointing here.

## Usage

```python
from ageneval.task.agents.autogen_agentchat import AutogenAgentChatAgent
from ageneval.task.datasets.mmlu import build_mmlu_binding, load_mmlu_tasks
from ageneval.task.core import ExperimentRunner, setup_instrumentation

provider = setup_instrumentation(
    project_name="mmlu-autogen-agentchat",
    framework="autogen_agentchat",
)
agent = AutogenAgentChatAgent(binding=build_mmlu_binding())
dataset = load_mmlu_tasks(n=1)

with ExperimentRunner(dataset=dataset, agent=agent, tracer_provider=provider) as runner:
    import asyncio
    traces = asyncio.run(runner.run_all())
```

## Auth

The agent reaches the LLM through an **OpenAI-compatible endpoint**
(`autogen_ext.models.openai.OpenAIChatCompletionClient`):

- `OPENAI_API_KEY`: API token (required).
- `OPENAI_API_BASE`: optional override for self-hosted / proxy endpoints.
- `A2E_MODEL`: unified non-reasoning instruct model name (defaults to `qwen-plus`).

Because `qwen-plus` is not an OpenAI-official model, the agent supplies an
explicit `model_info` (`vision` / `function_calling` / `json_output` /
`family` / `structured_output` / `multiple_system_messages`) so AutoGen does
not reject the unknown model.
