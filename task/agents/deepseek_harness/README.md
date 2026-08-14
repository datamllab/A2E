# ageneval-task-agent-deepseek-harness

This package makes the official DeepSeek Harness available as the normal A2E
`--agent deepseek-harness` runner. Harness owns the model/tool loop; A2E only
supplies the selected dataset binding and experiment context.

## Data flow

```text
A2E CHAIN span
  -> Python runner starts dsh --profile headless
  -> loopback bridge registers AgentBinding tools in Harness
  -> a2e-deepseek-harness-monitor observes Harness events
  -> AGENT / LLM / TOOL spans are exported to the same A2E trace
```

The bridge listens on `127.0.0.1`, uses a random bearer token, and exists for
one task. Dataset tool execution remains in Python, so Terminal-Bench and
SWE-bench tools operate on their live Docker sandbox rather than the host.

## Setup

```bash
cd monitor/instrumentation-js/a2e-deepseek-harness-monitor
npm install
npm run build
npx dsh plugin --profile headless add "$PWD"
```

Configure DeepSeek Harness normally with `DEEPSEEK_API_KEY` and optionally
`DEEPSEEK_BASE_URL`. The runner also accepts `--model`, `--api-key`, and
`--api-base` from A2E's experiment CLI.

## Run one stored benchmark task

```bash
cd task
uv run --frozen python examples/run_experiment.py \
  --dataset gsm8k \
  --agent deepseek-harness \
  --model deepseek-v4-flash \
  --evaluators numeric_match \
  --n 1
```

The dataset, experiment output, evaluator result, trace ID, and complete span
tree are stored in the configured A2E database.

Harness does not currently expose a stable headless `max_turns` option. The
runner therefore uses `A2E_DEEPSEEK_DEADLINE` as a wall-clock safety limit
(900 seconds by default) and otherwise leaves Harness's model/tool loop
unchanged. This is intentional: the monitor must not cancel a normal Harness
run merely to enforce an A2E-side step recommendation.

## Live benchmark verification

On 2026-08-14, one real task from every registered A2E dataset was run with
`deepseek-v4-flash` through this runner and stored in A2E: 15 QA datasets,
four tool-use datasets, Terminal-Bench 2/2.1, and SWE-Bench Lite, Verified,
and Pro (24 experiments total). All 24 task runs completed with status `ok`.
The projects contained 652 spans in total; every project had exactly one
CHAIN, one AGENT, at least one LLM, and one trace ID. The three SWE variants
also completed their official graders and stored all three SWE evaluator
scores. Evaluator score is model/task quality, not monitor health, so a score
of zero is still a valid integration result when the run and trace are stored.

See [VALIDATION.md](./VALIDATION.md) for the per-dataset experiment IDs, span
counts, evaluator results, reproducible commands, and known limitations.

The official `swebench` Python package imports Unix's `resource` module and
does not import natively on Windows. The Windows validation used a local,
untracked compatibility shim only for loading the grader. No Windows-specific
change is part of this package; normal Linux CI and benchmark images use the
official dependency directly.

## Test

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --package \
  ageneval-task-agent-deepseek-harness pytest agents/deepseek_harness/tests -q

cd ../monitor/instrumentation-js/a2e-deepseek-harness-monitor
npm run verify
```
