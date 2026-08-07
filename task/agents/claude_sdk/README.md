# claude-sdk agent

Single-agent runner powered by the **Anthropic Python SDK** (`anthropic`
package) over the Messages API, with **native tool use**.

Dataset-agnostic: `ClaudeSDKAgent` consumes any `AgentBinding`, so adding a
new benchmark costs **zero** new agent code. It talks to the Anthropic
Messages API directly over HTTP — no `claude` CLI subprocess — so it runs
headlessly anywhere. Point it at any Anthropic-compatible endpoint
(including OpenAI-style gateways that also expose `/v1/messages`) via
`ANTHROPIC_BASE_URL`.

## Usage

```python
from ageneval.task.agents.claude_sdk import ClaudeSDKTauAgent
from ageneval.task.datasets.tau_bench import load_tau_bench_tasks
from ageneval.task.core import ExperimentRunner

# Reads ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL from the environment.
agent = ClaudeSDKTauAgent(domain="retail", model="qwen-plus")
dataset = load_tau_bench_tasks("retail", n=1)

with ExperimentRunner(dataset=dataset, agent=agent) as runner:
    import asyncio
    traces = asyncio.run(runner.run_all())
    for t in traces:
        print(t.task_id, t.status, t.turns, t.tool_calls)
```

## How it works

`run()` drives a standard Anthropic tool-use loop:

1. Convert the binding's OpenAI-style `tool_schemas` to Anthropic tool
   schema (`name` / `description` / `input_schema`).
2. `AsyncAnthropic.messages.create(...)` with the tools + system prompt.
3. On `tool_use` blocks: execute each via `binding.tool_executor`, append
   `tool_result` blocks, loop.
4. On a plain text reply: that text is the `final_answer`.

## Auth

Set in `.env` (or the environment):

- `ANTHROPIC_API_KEY` — required.
- `ANTHROPIC_BASE_URL` — Anthropic-compatible endpoint base (no trailing
  `/v1`; the SDK appends `/v1/messages`). Omit to use `api.anthropic.com`.

The model is supplied by the caller (`model=...`); any model the endpoint
serves over `/v1/messages` works.
