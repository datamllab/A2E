# A2E Monitor for Pi Agent

Pi is the external [Pi Agent Harness](https://github.com/earendil-works/pi): a
Node.js coding-agent runtime that combines a multi-provider model API, agent
loop, tools, sessions, CLI/TUI, and extensions. It is not an existing A2E
module. This adapter targets the current
`@earendil-works/pi-coding-agent` package and is verified against Pi `0.84.1`
(Node.js `>=22.19.0`).

This package captures both standalone `pi-agent-core` Agents and complete Pi
coding-agent runs as OpenTelemetry traces using the OpenInference attributes
already understood by A2E. It uses Pi's public event APIs only; the monitor
extension does not replace model clients, wrap tools, or register a global
OpenTelemetry provider. The optional runner-only binding extension appends the
dataset system prompt and registers its tools when `A2E_PI_BINDING_CONFIG` is
present.

## Integration layers

The shared event-to-span implementation has two public adapters:

- `instrumentPiAgent(agent)` subscribes to a standalone
  `@earendil-works/pi-agent-core` `Agent` through `Agent.subscribe()` and safely
  chains its public `onPayload` / `onResponse` hooks;
- the Pi Package monitor extension listens through
  `@earendil-works/pi-coding-agent` `ExtensionAPI.on()` and adds coding-agent
  prompt, context, provider-response, working-directory, and session lifecycle
  data.

When this package is launched by A2E's `--agent pi` runner, a second extension
registers the selected dataset's `AgentBinding` tools. Tool execution crosses a
token-protected loopback bridge back to the existing Python executor, so Pi's
native tool events are traced without changing dataset interfaces. Direct Pi
users who do not set `A2E_PI_BINDING_CONFIG` are unaffected.

The coding-agent extension reuses the same core event dispatcher. Do not attach
`instrumentPiAgent()` to the same underlying Agent while the extension is
enabled, because observing both surfaces would intentionally duplicate spans.

## Captured trajectory

Each `agent_start`/`agent_end` pair becomes an `AGENT` root span. Assistant
messages become `LLM` children, and every tool execution becomes a `TOOL` child.
The adapter records:

- expanded prompt, system prompt, and model input/output messages;
- provider, API, model name, token usage, cache usage, and reported cost;
- tool call ID, name, arguments, result, duration, and error status;
- correct parent/trace IDs, including independent spans for concurrent tools.

The emitted names and attributes (`openinference.span.kind`,
`llm.input_messages.*`, `llm.output_messages.*`, `tool.name`, `input.value`,
`output.value`, and token counts) are consumed directly by A2E's collector and
span-tree API.

## Standalone pi-agent-core

Install this package as a local/file dependency in the application that owns
the core Agent. Then attach and shut down the instrumentation explicitly:

```ts
import { Agent } from "@earendil-works/pi-agent-core";
import { instrumentPiAgent } from "a2e-pi-monitor";

const agent = new Agent({ /* model, streamFn, tools, ... */ });
const tracing = instrumentPiAgent(agent, { cwd: process.cwd() });
try {
  await agent.prompt("Read package.json and report its package name.");
} finally {
  await tracing.shutdown();
}
```

This lower-level adapter records the public Agent, message, and tool lifecycle.
It restores any pre-existing `onPayload` / `onResponse` callbacks on `dispose()`
and never swallows errors raised by those application callbacks; only tracing
failures are isolated from the Agent.
Use the coding-agent extension below when running the full Pi CLI/SDK, because
that layer can also observe the assembled prompt, provider payload/response,
and session shutdown.

## Install and run pi-coding-agent

1. Build this local package once (a file/Git install runs the same `prepare`
   script automatically):

   ```bash
   cd monitor/instrumentation-js/a2e-pi-monitor
   npm install --ignore-scripts
   npm run build
   ```

2. Start A2E from the repository root:

   ```bash
   bash script/start.sh
   ```

3. Install this local Pi Package (use the absolute path on your machine):

   ```bash
   pi install /absolute/path/to/A2E/monitor/instrumentation-js/a2e-pi-monitor
   ```

   To enable it only for the current project, add `-l`. To try it for one run
   without changing Pi settings, use:

   ```bash
   pi -e /absolute/path/to/A2E/monitor/instrumentation-js/a2e-pi-monitor
   ```

4. Configure the collector and run Pi:

   ```bash
   export A2E_COLLECTOR_ENDPOINT=http://127.0.0.1:6006
   export A2E_PROJECT_NAME=pi-agent
   pi
   ```

5. Confirm that A2E stored the spans:

   ```bash
   curl http://127.0.0.1:6006/v1/projects/pi-agent/spans
   ```

   A2E's current web frontend is an experiment viewer. It renders a span tree
   when a trace is referenced by an experiment sample. A standalone Pi run sent
   only through OTLP is stored and available through the projects/spans REST
   API, but the current frontend does not provide a raw-project trace browser.

Pi installs the package's OpenTelemetry dependencies and runs its build hook
automatically for file/Git installs. When loading this source directory directly
with `-e`, make sure `npm run build` has produced `dist/` first.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `A2E_COLLECTOR_ENDPOINT` | `http://127.0.0.1:6006` | A2E base URL or full `/v1/traces` URL |
| `A2E_PROJECT_NAME` | `default` | A2E project resource name |
| `A2E_API_KEY` | unset | Sends `Authorization: Bearer <key>` |
| `A2E_CLIENT_HEADERS` | unset | Comma-separated, URL-encoded `key=value` headers |
| `A2E_PI_CAPTURE_CONTENT` | `true` | Set to `false` to omit prompt/tool content while retaining timings and metadata |
| `A2E_PI_MAX_ATTRIBUTE_LENGTH` | `262144` | Per-attribute safety limit in characters |
| `A2E_PI_MONITOR_ENABLED` | `true` | Set to `false` to disable the extension |
| `A2E_PI_MONITOR_DEBUG` | `false` | Log tracing failures to stderr |

Standard `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`, `OTEL_EXPORTER_OTLP_ENDPOINT`, and
`OTEL_EXPORTER_OTLP_HEADERS` are also supported. A2E variables take precedence,
except the signal-specific traces endpoint, which is treated as the exact URL.

Tracing and export failures are swallowed by the extension so they do not fail
or alter a Pi run. Content capture is enabled by default because complete
trajectory evaluation requires it; disable it when prompts or tool results are
sensitive.

## Development verification

```bash
cd monitor/instrumentation-js/a2e-pi-monitor
npm install --ignore-scripts
npm run verify
```

`npm run verify` includes two real Pi runtime integration levels. A standalone
`pi-agent-core` `Agent` is instrumented through `Agent.subscribe()`. Separately,
a Pi coding-agent `AgentSession` loads the built package extension through
`DefaultResourceLoader`. In both cases Pi's official Faux Provider produces two
model responses and Pi executes a `read` tool. The tests assert one AGENT, two
LLM, and one TOOL span with the correct hierarchy and content. They do not
require an API key or external model. A second coding-agent task uses Pi's real
`write` and `read` tools to create an artifact and verify it over three model
turns. The suite also verifies that disabling content capture removes prompts,
model payloads, tool arguments/results, and sensitive error messages while
retaining operational metadata.

To send the same deterministic smoke run to a running A2E server:

```bash
export A2E_COLLECTOR_ENDPOINT=http://127.0.0.1:6006
export A2E_PROJECT_NAME=pi-agent-smoke
npm run smoke:pi
curl http://127.0.0.1:6006/v1/projects/pi-agent-smoke/spans
```

To exercise the standalone core adapter against the same real A2E receiver,
use `A2E_PROJECT_NAME=pi-core-smoke` and run `npm run smoke:core` instead.

After configuring a real provider in Pi or its standard API-key environment
variable, run the live acceptance check:

```bash
export A2E_PI_LIVE_PROVIDER=openai
export A2E_PI_LIVE_MODEL=gpt-4o-mini
npm run smoke:live
```

This invokes the official Pi CLI, requires a real model to call Pi's read-only
`read` tool, and queries A2E afterward. It exits unsuccessfully unless A2E
stored AGENT, LLM, and TOOL spans for the new trace. See
[`examples/README.md`](./examples/README.md) for credential-safe setup.

The remaining tests cover span hierarchy, OpenInference attributes, usage/cost
mapping, concurrent tools, error status, orphan cleanup, endpoint
normalization, authentication configuration, and OTLP protobuf transport.

## Live-provider verification

On 2026-08-12 the coding-agent path was also verified with a real DashScope
`qwen-plus` request (not the Faux Provider). Pi made two model calls, executed
its read-only `read` tool against `package.json`, and returned the package name.
A2E stored one trace containing exactly one AGENT, two LLM, and one TOOL span;
all spans were OK and had the correct parent IDs. The two LLM spans recorded
token counts of 678/12 and 748/19 (prompt/completion), and A2E retained the tool
input, tool output, and final agent answer. No credential is stored in this
repository.

### Benchmark-task Monitor validation

On 2026-08-12 the complete coding-agent path was additionally exercised on the
vendored Terminal-Bench 2.1 `regex-log` task, pinned by A2E to upstream commit
`5c8eadf1f393183288fa08b8f73ca9a469cc5e00`. Pi used DashScope's
OpenAI-compatible endpoint with `qwen3.8-max`, created the requested
`regex.txt`, and ran its own checks through the coding-agent tools. The output
then passed the unmodified held-out assertions from the task's official
`tests/test_outputs.py` inside an isolated Linux container.

A2E stored exactly one complete trace for the acceptance project: one AGENT,
seven LLM, and six TOOL spans (`read` once and `bash` five times). Every child
had the AGENT span as its parent. One failed tool attempt was recorded as ERROR;
Pi recovered, completed the task, and the task's unmodified Python assertions
still passed. The
LLM spans all identified `qwen3.8-max` and retained their message and token
metadata.

The normal A2E experiment path is now also supported:

```bash
cd task
uv run --frozen python examples/run_experiment.py \
  --dataset terminal-bench-2.1 --agent pi \
  --model deepseek-v4-pro --evaluators tb_resolved --n 1
```

Pi stays on the host while its registered `bash` and editor tools execute
through the dataset binding in the live Docker container. The official verifier
runs before container cleanup. On 2026-08-13, Terminal-Bench 2.1 `fix-git`
completed with reward `1`; A2E stored one trace containing one CHAIN, one AGENT,
ten LLM, and nine TOOL spans, with the Pi AGENT parented to the experiment
CHAIN. The experiment run, score, trace ID, and all spans were persisted to the
same SQLite database used by the A2E UI.
