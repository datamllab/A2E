# A2E Monitor for DeepSeek Harness

This package adapts the external
[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) to A2E's
existing OTLP/OpenInference trace format. It is a loadable Harness Cordis
plugin and is verified with `@deepseek-ai/dsh` `0.1.0-rc.6` on Node.js 24.

The adapter listens to Harness's durable `session/event` feed. It does not
replace a model client, wrap tool implementations, or modify the agent loop.
Observer and exporter errors are contained and logged so tracing cannot fail a
Harness run.

## Captured trajectory

Each Harness turn becomes an `AGENT` span. Every model step becomes an `LLM`
child, and each `tool/call` / `tool/result` pair becomes a `TOOL` child. The
monitor records:

- user input, system prompt, current model-visible message history, and final output;
- provider, model, invocation parameters, tool schemas, and assistant tool calls;
- uncached, cache-read, cache-write, output, and reasoning token counts;
- tool call ID, name, raw JSON arguments, model-facing result, duration, and error status;
- session, turn, step, working directory, subagent lineage, and span hierarchy.

Harness only emits a new `request/header` when its request epoch changes. The
adapter therefore retains the latest header but takes a fresh
`Session.deriveMessages()` snapshot at every `step/start`; later model calls
retain their complete inputs, including preceding tool results.

Some DSH/provider combinations emit empty tool `callId` values. The adapter
uses durable `sourceEventSeqs` links to pair calls/results and assigns stable
event-sequence IDs, so separate calls are not collapsed into one TOOL span.

If `TRACEPARENT` is present, each turn's AGENT span is parented to that remote
context. This lets an A2E experiment attach the Harness trajectory below its
existing CHAIN span. Otherwise the run is stored as an independent trace under
`A2E_PROJECT_NAME`.

When selected through A2E, non-sandbox datasets run Harness on the host and
may expose dataset `AgentBinding` tools through an authenticated loopback
bridge. Terminal/SWE datasets run the complete headless Harness profile and
this plugin inside the task container with native tools enabled. Set
`A2E_DEEPSEEK_DISABLE_BUILTIN_TOOLS=1` only for a deliberate ablation.

## Install in a Harness profile

Build the local package:

```bash
cd monitor/instrumentation-js/openinference-instrumentation-deepseek-harness
npm install --ignore-scripts
npm run build
```

Install it into each DeepSeek Harness profile that should be monitored. The
package's `dsh.bundle.patch` declaration makes the CLI add the Cordis plugin to
the profile automatically:

```bash
dsh plugin --profile headless add /absolute/path/to/A2E/monitor/instrumentation-js/openinference-instrumentation-deepseek-harness
```

If the profile previously installed this adapter under its pre-alignment name,
remove the stale dependency once before adding the renamed package:

```bash
dsh plugin --profile headless remove a2e-deepseek-harness-monitor
```

Confirm the composed profile contains `openinference-instrumentation-deepseek-harness`:

```bash
dsh --profile headless --dump-config
```

## Run and inspect A2E storage

Start A2E, configure the collector, then run Harness normally:

```bash
export A2E_COLLECTOR_ENDPOINT=http://127.0.0.1:6006
export A2E_PROJECT_NAME=deepseek-harness
dsh --profile headless "Use a shell tool to print 6 * 7, then report the result."
```

Inspect the stored spans:

```bash
curl http://127.0.0.1:6006/v1/projects/deepseek-harness/spans
```

The response should contain one `AGENT` root plus `LLM` and, when the task
uses tools, `TOOL` children sharing its trace ID.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `A2E_COLLECTOR_ENDPOINT` | `http://127.0.0.1:6006` | A2E base URL or full `/v1/traces` URL |
| `A2E_PROJECT_NAME` | `default` | A2E project resource name |
| `A2E_API_KEY` | unset | Sends `Authorization: Bearer <key>` |
| `A2E_CLIENT_HEADERS` | unset | Comma-separated, URL-encoded `key=value` headers |
| `A2E_DEEPSEEK_MONITOR_ENABLED` | `true` | Set to `false` to disable the Cordis plugin |
| `A2E_DEEPSEEK_CAPTURE_CONTENT` | `true` | Set to `false` to omit prompts, tool arguments/results, and error text |
| `A2E_DEEPSEEK_MAX_ATTRIBUTE_LENGTH` | `262144` | Per-attribute character safety limit |
| `A2E_DEEPSEEK_BINDING_CONFIG` | unset | Host-runner file that exposes A2E `AgentBinding` tools |
| `A2E_DEEPSEEK_DISABLE_BUILTIN_TOOLS` | unset | Runner-only ablation flag; native tools are enabled by default |

Standard `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`,
`OTEL_EXPORTER_OTLP_ENDPOINT`, and `OTEL_EXPORTER_OTLP_HEADERS` are also
supported. The signal-specific endpoint is treated as an exact URL; other base
URLs are normalized to `/v1/traces`.

Complete content capture is enabled because trajectory evaluation needs model
and tool content. Disable it for sensitive tasks. API credentials are not part
of Harness session events and are never read by this plugin.

### Attribute-count limit

The JavaScript provider defaults to 10,000 attributes per span, matching A2E's
shared Python OpenInference provider so long flattened histories retain their
later model outputs. Standard OpenTelemetry overrides are honored in order:
`OTEL_SPAN_ATTRIBUTE_COUNT_LIMIT`, then `OTEL_ATTRIBUTE_COUNT_LIMIT`, then the
A2E default. `A2E_DEEPSEEK_MAX_ATTRIBUTE_LENGTH` independently bounds each
individual value.

## Verification

Run the deterministic suite without a model key:

```bash
npm run verify
```

The suite covers event-to-span mapping, multi-step model history, hierarchy,
token/cache/reasoning usage, errors, incomplete operations, privacy mode,
configuration, W3C parent context, and a real OTLP protobuf POST to
`/v1/traces`.

On 2026-08-14, the package was also installed through the official `dsh plugin`
command and loaded in the `0.1.0-rc.6` headless profile. A live
`deepseek-v4-flash` task called the native `pwsh` tool to compute `6 * 7` and
returned `42`. A2E stored one trace with one AGENT, two LLM, and one TOOL span;
all four spans were OK, all three children had the AGENT parent, both model
steps retained input messages, the second input contained the tool result, and
the tool/final outputs contained `42`. No credential is stored in this
repository.
