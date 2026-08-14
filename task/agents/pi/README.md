# ageneval-task-agent-pi

A dataset-agnostic A2E runner for the Pi coding-agent CLI.

## Architecture

The integration has three layers:

```text
task/agents/pi/agent.py
  PiAgent: launches Pi and adapts A2E AgentBinding tools

monitor/instrumentation-js/a2e-pi-monitor/
  Pi extensions: AGENT / LLM / TOOL spans -> OTLP -> A2E

task/runners/.../registry.py
  registers --agent pi for the normal experiment CLI
```

Pi owns the model loop and native function calls. The Python runner exposes the
selected dataset's existing `AgentBinding` tools through a short-lived,
token-protected loopback bridge. Span capture remains inside Pi, so the runner
uses `framework="none"` and needs no Python model instrumentor.

## Trace and experiment linking

`run_experiment.py` wraps each sample in an A2E `CHAIN` span. `PiAgent` passes
that span's W3C `traceparent` and experiment project name to the Pi subprocess.
The monitor uses them when it creates the Pi `AGENT` span:

```text
[CHAIN] Task: task_fn
  [AGENT] pi.agent
    [LLM]  pi.llm <model>
    [TOOL] pi.tool <name>
```

After Pi exits, the runner polls the experiment project until the trace's span
set is stable. It then returns the LLM count and tool calls in `TaskTrace`, with
the same trace ID that A2E stores on the experiment run. This avoids returning a
partial trajectory when the collector exposes the root span before its
children.

## AgentBinding and Docker tools

When a binding declares tools, the runner writes their OpenAI-style schemas to
a temporary config. The package's `a2e-binding-tools` extension registers them
as native Pi function tools and forwards each call to a loopback-only Python
server. That server calls the existing contract:

```python
binding.tool_executor(name, arguments, task.initial_state)
```

The bridge listens only on `127.0.0.1`, uses a random bearer token, exists for
one task, and never contains provider credentials.

For Terminal-Bench, `task.initial_state` contains the live Docker sandbox. Its
`bash` and `str_replace_editor` binding tools therefore operate directly in the
published Linux image. Pi stays on the host because the images need not contain
Node.js; benchmark files are not copied to the host. The official held-out
verifier scores the same container before cleanup.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `A2E_PI_CLI` | `pi` or the vendored CLI | Pi executable or command |
| `A2E_PI_MONITOR` | vendored monitor path | Pi extension package |
| `A2E_PI_DEADLINE` | `600` | whole-run deadline in seconds |
| `PI_PROVIDER` | inferred from API-key env vars | Pi provider |
| `A2E_MODEL` | `qwen-plus` | model when `--model` is omitted |

Provider credentials use Pi's normal variables such as `DEEPSEEK_API_KEY`,
`OPENAI_API_KEY`, and `ANTHROPIC_API_KEY`.

## Run

Start A2E with the intended working directory/database, then use the normal
experiment CLI:

```bash
cd task
DEEPSEEK_API_KEY=... \
uv run --frozen python examples/run_experiment.py \
  --dataset terminal-bench-2.1 \
  --agent pi \
  --model deepseek-v4-pro \
  --evaluators tb_resolved \
  --n 1
```

Open `http://localhost:6006/datasets` to view the experiment and its complete
span tree. The isolated dataset, experiment, run output, evaluator annotation,
trace ID, and spans are persisted in A2E's configured database.

## Test

```bash
cd task
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --frozen --package ageneval-task-agent-pi pytest agents/pi/tests -q

cd ../monitor/instrumentation-js/a2e-pi-monitor
npm run verify
```

The Python tests cover the token-protected binding bridge and both flattened
and nested A2E span attribute shapes. The TypeScript suite covers standalone
`pi-agent-core`, Pi `AgentSession`, AGENT/LLM/TOOL hierarchy, traceparent
propagation, content controls, and OTLP transport.

## Known limitations

- Pi 0.84.1 does not expose usage data for every internal retry call, so those
  retry LLM spans can lack token counts even though their inputs are captured.
- Binding fidelity is dataset-owned. Pi calls exactly the schemas and executor
  supplied by the dataset; incomplete stubs or a mismatch between an upstream
  sample and its binding can produce a low score without implying a missing
  monitor span.
