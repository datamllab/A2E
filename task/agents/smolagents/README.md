# smolagents τ-bench agent

Single-agent runner powered by **smolagents** (Hugging Face's lightweight
code-driven agent framework).

Used to demonstrate A2E's auto-instrumentation path for the
``smolagents`` ecosystem: the agent code contains **zero** tracing
calls; ``SmolagentsInstrumentor`` (installed by
``ageneval.task.core.setup_instrumentation(framework="smolagents")``)
captures every step / tool call / final answer span automatically.

## Usage

```python
from ageneval.task.agents.smolagents import SmolAgentsTauAgent
from ageneval.task.datasets.tau_bench import load_tau_bench_tasks
from ageneval.task.core import ExperimentRunner, setup_instrumentation

provider = setup_instrumentation(
    project_name="tau-bench-smolagents",
    framework="smolagents",
)
agent = SmolAgentsTauAgent(domain="retail", model="gpt-4o-mini")
dataset = load_tau_bench_tasks("retail", n=1)

with ExperimentRunner(dataset=dataset, agent=agent, tracer_provider=provider) as runner:
    import asyncio
    traces = asyncio.run(runner.run_all())
    for t in traces:
        print(t.task_id, t.status, t.turns, t.tool_calls)
```

## Auth

smolagents' ``OpenAIServerModel`` reads OpenAI-compatible credentials:

- ``OPENAI_API_KEY``: API token (required).
- ``OPENAI_API_BASE``: optional override for self-hosted endpoints
  (e.g. ``https://api.deepseek.com/v1``).
