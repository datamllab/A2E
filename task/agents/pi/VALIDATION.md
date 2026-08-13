# Pi runner validation

This report records the 2026-08-13 acceptance run against Pi 0.84.1 and the
real `deepseek-v4-pro` provider. A2E was configured with
`A2E_WORKING_DIR=F:\A2E\.a2e-data`; the resulting experiments, run outputs,
evaluator annotations, traces, and spans are stored in `.a2e-data/a2e.db`.
Credentials were loaded from an external `.env` and are not present in the
repository or this report.

## Automated tests

- `npm run verify`: 14/14 TypeScript tests passed. Coverage includes a real
  `pi-agent-core` Agent, a Pi `AgentSession`, AGENT/LLM/TOOL hierarchy,
  traceparent propagation, content controls, and OTLP transport.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --frozen pytest agents/pi/tests -q`:
  2/2 Python tests passed. Coverage includes the authenticated binding bridge
  and A2E's flattened/nested span attribute shapes.

## Database acceptance matrix

One sampled task was run for every registered benchmark except the three
SWE-bench variants. Experiment IDs below are SQLite integer IDs; the A2E REST
and UI encode them as opaque IDs.

| Experiment | Benchmark | Status | LLM | TOOL | Evaluator score |
| ---: | --- | --- | ---: | ---: | ---: |
| 28 | traject-bench | ok | 1 | 0 | 1.0 |
| 29 | tau-bench | ok | 7 | 7 | 0.5 |
| 30 | tau2 | ok | 1 | 0 | 0.0 |
| 31 | tau3 | ok | 6 | 7 | 0.0 |
| 32 | mmlu | ok | 1 | 0 | 0.0 |
| 33 | gsm8k | ok | 1 | 0 | 0.0 |
| 34 | humaneval | ok | 1 | 0 | 0.0 |
| 35 | persistbench | ok | 1 | 0 | 0.0 |
| 36 | gdpval | ok | 1 | 0 | 0.0 |
| 37 | gpqa | ok | 1 | 0 | 0.0 |
| 38 | mmlu-pro | ok | 1 | 0 | 1.0 |
| 39 | arc-challenge | ok | 1 | 0 | 1.0 |
| 40 | truthfulqa | ok | 1 | 0 | 1.0 |
| 41 | bbh | ok | 1 | 0 | 0.0 |
| 42 | agieval | ok | 1 | 0 | 1.0 |
| 43 | commonsenseqa | ok | 1 | 0 | 1.0 |
| 44 | hellaswag | ok | 1 | 0 | 0.0 |
| 45 | openbookqa | ok | 1 | 0 | 1.0 |
| 46 | math | ok | 1 | 0 | 1.0 |
| 47 | terminal-bench-2 / regex-log | error | 2 | 1 | 0.0 |
| 48 | terminal-bench-2.1 / fix-git | ok | 10 | 9 | 1.0 |

A supplementary Terminal-Bench 2 `fix-git` run is stored as experiment 49
(13 LLM, 12 TOOL, reward 0). It exercised a second official 2.0 image; the
required one-per-benchmark acceptance row remains experiment 47 above.

For all 21 rows:

- the experiment run has a non-null trace ID;
- the trace belongs to the experiment's project, not `default`;
- the trace contains exactly one A2E `CHAIN`, one Pi `AGENT`, and at least one
  Pi `LLM` span;
- the Pi `AGENT.parent_id` equals the experiment `CHAIN.span_id`;
- the evaluator result is persisted in `experiment_run_annotations`.

Terminal-Bench used the published Docker images and the normal
`SandboxScoringRunner`. The 2.1 `fix-git` task passed its unmodified held-out
verifier (`tb_reward=1`). The 2.0 `regex-log` run is intentionally retained as
a failure-path trace: DeepSeek's second response reached its output-length
limit before it wrote the file, so the official verifier returned zero. Its
complete two-LLM/one-TOOL trajectory was still stored correctly.

`traject-bench` sampled an upstream ecommerce request while the repository's
current binding exposes only five utilities (weather, calculation, unit/fact/
currency tools), so the model made no tool call. That is a dataset-binding
mismatch rather than missing instrumentation. Tau-bench and Tau3 demonstrate
that native benchmark tool calls are captured and returned in `TaskTrace`.
