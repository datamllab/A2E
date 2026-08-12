# agno agent

Single-agent runner powered by the **Agno** agent framework (`agno`).

This is A2E's agno framework adapter: it is **dataset-agnostic**, consuming any
`AgentBinding` and driving the benchmark behind it. Adding a new benchmark
therefore costs one new `binding.py` under `task/datasets/<bench>/` — no new
agent file.

The agent code contains **zero** tracing calls: the `AgnoInstrumentor`
(installed by `ageneval.task.core.setup_instrumentation(framework="agno")`)
captures every agent step / tool call / model call span automatically.

## Usage

```python
from ageneval.task.agents.agno import AgnoAgent
from ageneval.task.datasets.mmlu import build_mmlu_binding, load_mmlu_tasks
from ageneval.task.core import ExperimentRunner, setup_instrumentation

provider = setup_instrumentation(
    project_name="mmlu-agno",
    framework="agno",
)
agent = AgnoAgent(binding=build_mmlu_binding())
dataset = load_mmlu_tasks(n=1)

with ExperimentRunner(dataset=dataset, agent=agent, tracer_provider=provider) as runner:
    import asyncio
    traces = asyncio.run(runner.run_all())
```

## Auth

The agent reaches the LLM through an **OpenAI-compatible endpoint**
(`agno.models.openai.like.OpenAILike`):

- `OPENAI_API_KEY`: API token (required).
- `OPENAI_API_BASE`: optional override for self-hosted / proxy endpoints.
- `A2E_MODEL`: unified non-reasoning instruct model name (defaults to `qwen-plus`).
