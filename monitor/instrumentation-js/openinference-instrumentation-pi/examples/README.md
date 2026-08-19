# Smoke tests

## Standalone pi-agent-core smoke test

Start A2E, then run the core adapter without the coding-agent package:

```bash
export A2E_COLLECTOR_ENDPOINT=http://127.0.0.1:6006
export A2E_PROJECT_NAME=pi-core-smoke-test
npm run smoke:core
curl http://127.0.0.1:6006/v1/projects/pi-core-smoke-test/spans
```

This constructs a real `pi-agent-core` `Agent`, chains its provider hooks,
subscribes to its public events, executes a deterministic `read` tool, and
flushes the resulting AGENT/LLM/TOOL hierarchy to A2E.

## Deterministic Pi runtime smoke test

Start A2E, then run the included example from this package directory:

```bash
export A2E_COLLECTOR_ENDPOINT=http://127.0.0.1:6006
export A2E_PROJECT_NAME=pi-smoke-test
npm run smoke:pi
curl http://127.0.0.1:6006/v1/projects/pi-smoke-test/spans
```

The example uses Pi 0.84.1's official Faux Provider, but the agent loop and
`read` tool execution are real Pi runtime operations. It produces one AGENT,
two LLM, and one TOOL span without an external API key.

The automated test suite also runs a standalone `pi-agent-core` `Agent` through
the public `instrumentPiAgent()` / `Agent.subscribe()` path. The deterministic
smoke command above targets the complete coding-agent package and its extension
loader, which is the final delivery surface. An additional runtime task has the
complete coding agent create a file with its real `write` tool and read it back
with its real `read` tool, then verifies both the artifact and the exported
multi-turn trajectory.

## Manual provider smoke test

For a repeatable real-provider acceptance check, set the provider and model,
start A2E, and run:

```bash
export A2E_PI_LIVE_PROVIDER=openai
export A2E_PI_LIVE_MODEL=gpt-4o-mini
export OPENAI_API_KEY=...
npm run smoke:live
```

The command runs the official Pi CLI non-interactively, permits only the
read-only `read` tool, and then queries A2E's spans API. It fails unless the
new trace contains AGENT, LLM, and TOOL spans under one trace ID. Credentials
come only from Pi's saved authentication or the provider's standard environment
variable; the command never prints them.

To keep a key outside the repository, put all variables in a local file and
let Node load it for this process only:

```powershell
node --env-file=C:\Users\you\.a2e-pi-test.env scripts\live-smoke.mjs
```

For an interactive exploratory test instead, launch Pi with the local package:

```bash
pi -e /absolute/path/to/A2E/monitor/instrumentation-js/openinference-instrumentation-pi
```

Ask Pi to perform both a model-only response and a tool action, for example:

```text
Summarize the README, then use the bash tool to count its lines.
```

Expected hierarchy:

```text
pi.agent                         AGENT
|-- pi.llm <model>               LLM
|-- pi.tool read                 TOOL
|-- pi.llm <model>               LLM
`-- pi.tool bash                 TOOL
```

Verify that LLM spans contain input/output messages and token counts, tool
spans contain arguments/results, and all spans share the root trace ID. A
collector outage must not interrupt Pi; set `A2E_PI_MONITOR_DEBUG=true` to see
exporter diagnostics during that negative test.

## Benchmark-task Monitor validation

For an acceptance check beyond the synthetic smoke prompt, use one of A2E's
vendored Terminal-Bench tasks. The verified reference run used
`terminal-bench-2.1/regex-log` with `qwen3.8-max` through DashScope's
OpenAI-compatible endpoint. Keep the API key in an environment variable and
declare the custom Pi provider in a temporary `PI_CODING_AGENT_DIR/models.json`
using an environment reference such as `"apiKey": "$DASHSCOPE_API_KEY"`; do not
put the credential in the repository.

Pass the vendored `instruction.md` to the Pi CLI with this package loaded as an
extension, then evaluate the produced `/app/regex.txt` with the task's vendored
`tests/test_outputs.py`. The 2026-08-12 reference run passed those unmodified
assertions and A2E stored one AGENT, seven LLM, and six TOOL spans in a single
correctly parented trace.

This validates the Monitor against a benchmark task and its unmodified Python
assertions. Pi ran in a host-side temporary workspace rather than the task's
published image. Running the same task through A2E's `SandboxScoringRunner`
with an `--agent pi` CLI selection is a separate Runner integration.
