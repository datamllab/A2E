# ageneval-task-agent-pi

This package registers Pi Coding Agent as A2E's `--agent pi` runner. Pi owns
the model loop and its tools; A2E supplies the task, parent trace context,
collector configuration, storage, and evaluator.

## Execution model

- For non-sandbox datasets (QA and host-side tool tasks), Pi runs on the host.
  If the dataset exposes `AgentBinding` tools, a short-lived authenticated
  loopback bridge adapts those dataset APIs into Pi function tools.
- For Docker datasets (Terminal-Bench and SWE-Bench), A2E builds a cached
  derived task image and runs the complete Pi CLI inside that container. Pi's
  native `bash`, `read`, `edit`, and `write` tools operate directly on the
  benchmark working tree. No host tool bridge is used for this path.
- Native tools are enabled by default because they are part of the evaluated
  Harness. Set `A2E_PI_DISABLE_BUILTIN_TOOLS=1` only for controlled comparison
  runs.

The monitor extension emits the hierarchy A2E already understands:

```text
[CHAIN] Task: task_fn
  [AGENT] pi.agent
    [LLM]  pi.llm <model>
    [TOOL] pi.tool <name>
```

The runner propagates the experiment's W3C `traceparent` into Pi and waits for
the collector's span set to stabilize before returning `TaskTrace`. Monitor
and export failures are isolated from Pi so observation does not alter the
Agent run.

## Provider configuration

The runner accepts `--model`, `--api-key`, and `--api-base`. A custom OpenAI-
compatible base URL is represented by a temporary Pi `models.json`; the API
key is passed through an environment placeholder and is never written to the
repository or persisted in A2E.

| Variable | Default | Purpose |
| --- | --- | --- |
| `A2E_PI_CLI` | vendored Pi CLI | Pi executable override |
| `A2E_PI_DEADLINE` | `600` | whole-run deadline in seconds |
| `A2E_PI_DISABLE_BUILTIN_TOOLS` | unset | disable Pi built-ins when nonempty |
| `A2E_HARNESS_NODE_IMAGE` | `node:22-bullseye-slim` | Linux runtime builder |

Pi 0.84.1 has no stable CLI maximum-turn option, so the wall-clock deadline is
the safety bound.

## Run a stored Docker benchmark

Start A2E, then run from `task/`:

```bash
A2E_TB2_TASK=fix-git \
uv run --frozen python examples/run_experiment.py \
  --dataset terminal-bench-2 \
  --agent pi \
  --model qwen3.6-plus \
  --api-base https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --evaluators tb_resolved \
  --n 1
```

The isolated dataset, experiment run, evaluator result, trace ID, and complete
span tree are stored in the configured A2E database.

## Tests

```bash
cd task
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --frozen pytest agents/pi/tests -q

cd ../monitor/instrumentation-js/openinference-instrumentation-pi
npm run verify
```

The Python suite covers runner credential/config handling, the authenticated
host binding bridge, and A2E span parsing. The TypeScript suite exercises both
`pi-agent-core` and a real Pi coding-agent `AgentSession`, including model and
native tool spans. See [VALIDATION.md](./VALIDATION.md) for stored real-task
results.
