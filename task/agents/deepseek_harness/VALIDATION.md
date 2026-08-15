# DeepSeek Harness validation

Validation date: 2026-08-15. The headless DeepSeek Harness ran with
`qwen3.6-plus` through the DashScope OpenAI-compatible endpoint. Credentials
were loaded externally and are not stored in the repository or database.

## Container-native benchmark results

The complete DSH profile and monitor ran inside every published task image
with native tools enabled. Results and traces are stored in
`F:\A2E\.a2e-data-containerized\a2e.db` by the A2E server used on port 6106.

| Experiment | Benchmark / task | LLM | TOOL | Official result |
| --- | --- | ---: | ---: | --- |
| `RXhwZXJpbWVudDoyMg==` | Terminal-Bench 2 / `fix-git` | 9 | 12 | reward 0 |
| `RXhwZXJpbWVudDo2` | Terminal-Bench 2.1 / `fix-git` | 10 | 13 | reward 1; 2/2 tests |
| `RXhwZXJpbWVudDoxNA==` | SWE-Bench Lite / `django__django-12915` | 41 | 40 | `RESOLVED_FULL`; F2P 3/3; P2P 8/8 |
| `RXhwZXJpbWVudDoxNw==` | SWE-Bench Verified / `django__django-11292` | 30 | 29 | `RESOLVED_FULL`; F2P 1/1; P2P 31/31 |
| `RXhwZXJpbWVudDoyMA==` | SWE-Bench Pro / OpenLibrary | 25 | 30 | unresolved; F2P 0/3; P2P 104/104 |

Every valid row contains one CHAIN, one AGENT, LLM children, and DSH-native
TOOL children. Observed tools include `bash`, `read`, `edit`,
`str_replace_editor`, and `todo_write`. ERROR tool spans are retained and the
Agent can recover. Zero rewards are model/task outcomes, not monitor failures:
the task run has `status=ok` and its full trace is stored.

## Defects found by the matrix

- DSH/Qwen sometimes emits an empty `callId`. Pairing now uses durable source
  event sequence links and stable synthetic IDs instead of collapsing tools.
- With an explicit OpenAI-compatible `--api-base`, the runner now selects the
  matching OpenAI-compatible key before a separately configured DeepSeek key.
- The SWE-Pro Debian 11 image exposed a `GLIBC_2.34` mismatch in `node-pty`.
  The image composer now checks native modules in the final base and rebuilds
  incompatible ones there.
- `run_experiment.py` can exit zero even when a task output has `status=error`;
  acceptance therefore checks stored run output, evaluator result, and span
  tree rather than process exit code alone.

## Reproduce

```bash
cd task
A2E_SWE_INSTANCE=django__django-12915 \
A2E_DEEPSEEK_DEADLINE=1800 \
uv run --frozen python examples/run_experiment.py \
  --dataset swe-bench-lite \
  --agent deepseek-harness \
  --model qwen3.6-plus \
  --api-base https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --endpoint http://127.0.0.1:6106 \
  --evaluators swe_resolved,swe_fail_to_pass,swe_pass_to_pass \
  --n 1 --sample-seed 20260815
```

On Windows only, the official `swebench` package imports Unix's `resource`
module. Validation used an untracked `PYTHONPATH` shim only for the host-side
spec loader. The Harness and official evaluation script still ran in Linux
Docker. No Windows-only code is part of the deliverable.

## Deterministic verification

- DeepSeek monitor: `npm run verify` — 10 tests passed.
- DeepSeek Python runner: 5 tests passed.
- Sandbox hook/image framework: 5 tests passed.
- Targeted Ruff checks passed.

Earlier host-side QA and dataset-tool runs remain valid. The corrected
architecture only changes Docker datasets; non-sandbox datasets continue to
run DSH on the host.
