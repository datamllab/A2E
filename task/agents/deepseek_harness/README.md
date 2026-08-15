# ageneval-task-agent-deepseek-harness

This package registers the official DeepSeek Harness as A2E's
`--agent deepseek-harness` runner. DSH owns the model loop and native tools;
A2E supplies tasks, trace context, storage, and evaluation.

## Execution model

- Non-sandbox QA/tool datasets run DSH on the host. Dataset `AgentBinding`
  tools, when present, are exposed through a short-lived authenticated
  loopback bridge.
- Terminal-Bench and SWE-Bench run the complete headless DSH profile inside a
  cached derived benchmark image. DSH's native tools operate on the container
  working tree; the host bridge is not used.
- Built-in tools are enabled by default because they are part of the Harness
  under evaluation. Set `A2E_DEEPSEEK_DISABLE_BUILTIN_TOOLS=1` only for an
  explicit ablation.

The Cordis monitor reads DSH's durable event stream and emits:

```text
[CHAIN] Task: task_fn
  [AGENT] deepseek-harness.agent
    [LLM]  deepseek-harness.llm <model>
    [TOOL] deepseek-harness.tool <name>
```

Empty DSH `callId` values are replaced by stable IDs derived from source event
sequences, and tool results are paired through `sourceEventSeqs`. This retains
complete and correctly ordered TOOL spans without changing Harness execution.

## Images and native modules

The Node Harness runtime is content-addressed separately from each benchmark
base image, so `npm ci` runs once per Harness revision. Composition checks
native modules in the final task image. If a base image uses an older glibc,
`node-pty` is rebuilt against that base with Node 22 headers; the final image
does not retain the temporary build toolchain.

| Variable | Default | Purpose |
| --- | --- | --- |
| `A2E_DEEPSEEK_DEADLINE` | `900` | whole-run deadline in seconds |
| `A2E_DEEPSEEK_PROFILE` | `headless` | DSH profile |
| `A2E_DEEPSEEK_DISABLE_BUILTIN_TOOLS` | unset | disable DSH built-ins when nonempty |
| `A2E_HARNESS_NODE_IMAGE` | `node:22-bullseye-slim` | Linux runtime builder |

The runner accepts `--model`, `--api-key`, and `--api-base`. Explicit API keys
win. With a custom OpenAI-compatible base URL, `OPENAI_API_KEY` is preferred;
the default DeepSeek route prefers `DEEPSEEK_API_KEY`.

## Run

```bash
cd task
A2E_TB2_TASK=fix-git \
uv run --frozen python examples/run_experiment.py \
  --dataset terminal-bench-2 \
  --agent deepseek-harness \
  --model qwen3.6-plus \
  --api-base https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --evaluators tb_resolved \
  --n 1
```

## Tests

```bash
cd task
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --frozen pytest agents/deepseek_harness/tests -q

cd ../monitor/instrumentation-js/a2e-deepseek-harness-monitor
npm run verify
```

See [VALIDATION.md](./VALIDATION.md) for stored real-task results and Windows
grader notes.
