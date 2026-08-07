# ageneval-task-tau3

τ³-bench adapter for A2E — a **tool** dataset (`kind="tool"`), parallel to
`tau-bench` / `tau2`.

## What it is

- **Upstream**: [`sierra-research/tau2-bench` @ `dev/tau3`](https://github.com/sierra-research/tau2-bench/tree/dev/tau3)
  — τ³-bench ("[𝜏³-bench: Voice](https://sierra.ai/resources/research/tau-3-bench)")
  extends τ²-bench with a full-duplex **voice** modality across the retail /
  airline / telecom / banking-knowledge domains.
- **Scope in A2E**: the **text** tool-agent-user tasks only. Each task carries a
  real user scenario and its real expected tool calls
  (`evaluation_criteria.actions`), vendored from the dev/tau3 domains'
  `tasks.json`.

## Voice/audio is downloaded but NOT used

The dev/tau3 branch ships voice data (`tasks_voice.json`, `data/voice/…`
background-noise `.wav` files). Per the integration scope these are downloaded
with the upstream clone but **deliberately excluded** from this adapter — the
vendored sample is taken only from `tasks.json`, and nothing in this package
reads any audio. `metadata.modality` is always `"text"`.

## How it plugs into A2E

Registered as `tau3` in `task/runners/.../registry.py` with `kind="tool"` and
default evaluators `tool_recall` + `llm_judge`. The binding exposes the real
domain tool names (so `tool_recall` is meaningful) with a JSON-action protocol;
the executor serves light state lookups and acknowledges other tools (same
approach as the τ2 adapter). All 9 A2E agents drive it unchanged.

## Quick use

```bash
cd task && uv run --frozen python examples/run_experiment.py \
    --dataset tau3 --agent agno --evaluators tool_recall,llm_judge --n 3
```
