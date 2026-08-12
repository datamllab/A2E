# google-adk agent

Single-agent runner powered by the **Google Agent Development Kit** (`google-adk`).

This is A2E's google-adk framework adapter: it is **dataset-agnostic**,
consuming any `AgentBinding` and driving the benchmark behind it. Adding a
new benchmark therefore costs one new `binding.py` under
`task/datasets/<bench>/` — no new agent file.

The agent code contains **zero** tracing calls: the
`GoogleADKInstrumentor` (installed by
`ageneval.task.core.setup_instrumentation(framework="google_adk")`)
captures every agent step / tool call / model call span automatically.

## Usage

```python
from ageneval.task.agents.google_adk import GoogleADKAgent
from ageneval.task.datasets.mmlu import build_mmlu_binding, load_mmlu_tasks
from ageneval.task.core import ExperimentRunner, setup_instrumentation

provider = setup_instrumentation(
    project_name="mmlu-google-adk",
    framework="google_adk",
)
agent = GoogleADKAgent(binding=build_mmlu_binding())
dataset = load_mmlu_tasks(n=1)

with ExperimentRunner(dataset=dataset, agent=agent, tracer_provider=provider) as runner:
    import asyncio
    traces = asyncio.run(runner.run_all())
```

## Auth

The agent reaches the LLM through an **OpenAI-compatible endpoint**
(`google.adk.models.lite_llm.LiteLlm`, which routes via LiteLLM):

- `OPENAI_API_KEY`: API token (required).
- `OPENAI_API_BASE`: optional override for self-hosted / proxy endpoints.
- `A2E_MODEL`: unified non-reasoning instruct model name (defaults to `qwen-plus`).
