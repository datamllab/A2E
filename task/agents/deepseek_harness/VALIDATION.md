# DeepSeek Harness validation

Validation date: 2026-08-14

The official `@deepseek-ai/dsh` `0.1.0-rc.6` headless profile was run with
`deepseek-v4-flash` against one task from every dataset registered by A2E.
Each dataset, task output, evaluator annotation, and trace was stored by the
local A2E server in its normal database. No API credential is recorded here.

## Reproduce one run

Start A2E on port 6006, install the monitor into the headless profile as
described in the package README, and configure `DEEPSEEK_API_KEY` and
`DEEPSEEK_BASE_URL`. Then run, for example:

```bash
cd task
uv run --frozen python examples/run_experiment.py \
  --dataset traject-bench \
  --agent deepseek-harness \
  --model deepseek-v4-flash \
  --evaluators tool_recall \
  --n 1 \
  --run-id deepseek-harness-traject-bench-smoke
```

Sandbox datasets use the same command with their official evaluators. For
example:

```bash
uv run --frozen python examples/run_experiment.py \
  --dataset swe-bench-verified \
  --agent deepseek-harness \
  --model deepseek-v4-flash \
  --evaluators swe_resolved,swe_fail_to_pass,swe_pass_to_pass \
  --n 1
```

## Stored results

Every row below had one `CHAIN`, one `AGENT`, one trace ID, one successful
task run, and the listed model/tool children. A zero evaluator score means the
model did not solve that sampled task; it does not mean tracing or storage
failed.

| Experiment | Dataset | LLM | TOOL | Stored evaluator result |
| ---: | --- | ---: | ---: | --- |
| 57 | gsm8k | 1 | 0 | `numeric_match=1` |
| 58 | traject-bench | 9 | 9 | `tool_recall=1` |
| 59 | mmlu | 1 | 0 | `mc_letter=0` |
| 60 | humaneval | 1 | 0 | `substring=0` |
| 61 | persistbench | 1 | 0 | `substring=0` |
| 62 | gdpval | 8 | 15 | `llm_judge=0` |
| 63 | gpqa | 1 | 0 | `mc_letter=1` |
| 64 | mmlu-pro | 1 | 0 | `mc_letter=1` |
| 65 | arc-challenge | 1 | 0 | `mc_letter=1` |
| 66 | truthfulqa | 1 | 0 | `mc_letter=1` |
| 67 | bbh | 1 | 0 | `exact_match=1` |
| 68 | agieval | 1 | 0 | `mc_letter=1` |
| 69 | commonsenseqa | 1 | 0 | `mc_letter=1` |
| 70 | hellaswag | 1 | 0 | `mc_letter=1` |
| 71 | openbookqa | 1 | 0 | `mc_letter=1` |
| 72 | math | 1 | 0 | `numeric_match=1` |
| 73 | tau-bench | 17 | 18 | `tool_recall=1` |
| 74 | tau2 | 1 | 0 | `tool_recall=0` |
| 75 | tau3 | 1 | 0 | `tool_recall=0` |
| 76 | terminal-bench-2 | 13 | 12 | `tb_resolved=0` |
| 77 | terminal-bench-2.1 | 15 | 14 | `tb_resolved=0` |
| 78 | swe-bench-lite | 114 | 114 | all three SWE scores `1`; `RESOLVED_FULL` |
| 79 | swe-bench-verified | 59 | 58 | all three SWE scores `1`; `RESOLVED_FULL` |
| 80 | swe-bench-pro | 53 | 60 | all three SWE scores `1`; `resolved` |

Totals: 24 experiments and 652 spans. All 24 task outputs had status `ok`.
The three SWE runs passed every sampled Fail-to-Pass and Pass-to-Pass test.

Five TOOL spans across four long runs had an error status. They are expected,
recoverable Agent operations captured by the monitor: an out-of-range read, a
search timeout, a Windows permission error during glob, and two attempts to
use Harness's host `read` tool with a Linux container path. The Agent recovered
with the A2E sandbox `bash` tool; all four root traces completed successfully.

The Lite task output initially summarized `turns=0` and no tool calls even
though its stored trace contained 114 LLM and 114 TOOL spans. The cause was a
transient timeout while reading a large project response after the run. The
runner now allows 30 seconds per read, retries individual failed polls, and has
a regression test for this case. The already stored span tree and evaluator
result were never missing.

## Deterministic tests

- JavaScript monitor: 8 tests passed.
- Python runner: 3 tests passed.
- Ruff check for `task/agents/deepseek_harness`: passed.
- A2E registry discovery: `deepseek-harness` present.

The JavaScript suite covers event-to-span conversion, complete multi-step
history, tool success/error capture, hierarchy, privacy mode, W3C parent
context, and a real OTLP protobuf POST. The Python suite covers the authenticated
loopback binding bridge, span parsing, and transient collector-read retries.

## Known limits

- The JavaScript OpenTelemetry provider keeps the standard 128 attributes per
  span. Long flattened histories can exceed it; this cross-agent policy is
  documented but intentionally not changed by this adapter alone.
- Official Harness headless currently exposes no stable step-count limit. The
  runner uses `A2E_DEEPSEEK_DEADLINE` (default 900 seconds) as its safety bound
  and does not make the observer cancel a normal Harness run.
- The official `swebench` Python package imports Unix's `resource` module. The
  Windows-only validation used an untracked loader shim; no Windows-specific
  compatibility code is included in the deliverable.
