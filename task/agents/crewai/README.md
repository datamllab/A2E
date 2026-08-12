# crewai agent

Single-agent runner powered by **CrewAI** (`crewai`).

This is A2E's crewai framework adapter: it is **dataset-agnostic**, consuming
any `AgentBinding` and driving the benchmark behind it. Adding a new benchmark
therefore costs one new `binding.py` under `task/datasets/<bench>/` — no new
agent file.

The agent code contains **zero** tracing calls: the
`CrewAIInstrumentor` (installed by
`ageneval.task.core.setup_instrumentation(framework="crewai")`) captures every
agent step / tool call / model call span automatically.

## Usage

```python
from ageneval.task.agents.crewai import CrewAIAgent
from ageneval.task.datasets.mmlu import build_mmlu_binding, load_mmlu_tasks
from ageneval.task.core import ExperimentRunner, setup_instrumentation

provider = setup_instrumentation(
    project_name="mmlu-crewai",
    framework="crewai",
)
agent = CrewAIAgent(binding=build_mmlu_binding())
dataset = load_mmlu_tasks(n=1)

with ExperimentRunner(dataset=dataset, agent=agent, tracer_provider=provider) as runner:
    import asyncio
    traces = asyncio.run(runner.run_all())
```

## Auth

The agent reaches the LLM through an **OpenAI-compatible endpoint**. CrewAI
routes LLM calls through litellm; the `crewai.LLM` model name carries an
`openai/` prefix so a non-OpenAI-official model (e.g. `qwen-plus`) is driven
through the OpenAI chat-completions provider.

- `OPENAI_API_KEY`: API token (required).
- `OPENAI_API_BASE`: optional override for self-hosted / proxy endpoints.
- `A2E_MODEL`: unified non-reasoning instruct model name (defaults to `qwen-plus`).

## Tools

Each `AgentBinding` tool schema is wrapped into a `crewai.tools.BaseTool`
subclass instance. CrewAI's `BaseTool` requires a pydantic `args_schema`; a
permissive single-field schema (`arguments_json`, a JSON object string) keeps
the wiring dataset-agnostic. Every invocation is also captured into
`TaskTrace.tool_calls`.
