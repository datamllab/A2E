# Pi runner validation

Validation date: 2026-08-15. Pi `0.84.1` ran with `qwen3.6-plus` through the
DashScope OpenAI-compatible endpoint. Credentials came from external `.env`
files and are not stored here.

## Container-native benchmark results

Each row is a real task in its published Docker image. The complete Pi CLI and
monitor ran inside the task container with native tools enabled. Results and
spans are stored in `F:\A2E\.a2e-data-containerized\a2e.db` by the A2E server
used on port 6106.

| Experiment | Benchmark / task | LLM | TOOL | Official result |
| --- | --- | ---: | ---: | --- |
| `RXhwZXJpbWVudDoyMQ==` | Terminal-Bench 2 / `fix-git` | 9 | 9 | reward 1; 2/2 tests |
| `RXhwZXJpbWVudDo3` | Terminal-Bench 2.1 / `fix-git` | 10 | 11 | reward 1; 2/2 tests |
| `RXhwZXJpbWVudDoxMg==` | SWE-Bench Lite / `django__django-12915` | 11 | 11 | `RESOLVED_FULL`; F2P 3/3; P2P 8/8 |
| `RXhwZXJpbWVudDoxNg==` | SWE-Bench Verified / `django__django-11292` | 15 | 16 | `RESOLVED_FULL`; F2P 1/1; P2P 31/31 |
| `RXhwZXJpbWVudDoxOA==` | SWE-Bench Pro / OpenLibrary | 19 | 22 | unresolved; F2P 0/3; P2P 104/104 |

Every trace has one A2E CHAIN, one Pi AGENT, LLM children, and native TOOL
children. Observed tools include `bash`, `read`, `edit`, and `write`. Failed
tool attempts are retained as ERROR spans and did not prevent later recovery.
The Pro score is an Agent-quality result: Pi ran normally and the trace is
complete, but the sampled patch did not satisfy the three target tests.

## Reproduce

```bash
cd task
A2E_SWE_INSTANCE=django__django-12915 \
A2E_PI_DEADLINE=1800 \
uv run --frozen python examples/run_experiment.py \
  --dataset swe-bench-lite \
  --agent pi \
  --model qwen3.6-plus \
  --api-base https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --endpoint http://127.0.0.1:6106 \
  --evaluators swe_resolved,swe_fail_to_pass,swe_pass_to_pass \
  --n 1 --sample-seed 20260815
```

On Windows only, the official `swebench` package imports Unix's `resource`
module. These local validation runs put an untracked compatibility shim on
`PYTHONPATH` for the host-side spec loader. The Agent and official evaluation
script still ran in Linux Docker. No Windows-specific shim is committed to the
integration.

## Deterministic verification

- Pi monitor: `npm run verify` — 15 tests passed.
- Pi Python runner: 5 tests passed.
- Sandbox hook/image framework: 5 tests passed.
- Targeted Ruff checks passed.

The same runner was previously exercised against all non-Docker A2E datasets.
Those host-side QA/tool runs remain valid because the corrected architecture
changes only sandbox datasets: host datasets stay on the host, while complete
coding Harnesses move into Docker for Terminal/SWE tasks.

## Host QA matrix

On 2026-08-15, all 15 datasets whose registry kind is `qa` were rerun on the
host with `deepseek-v4-pro`, one reproducibly sampled task per dataset
(`sample_seed=20260816`). Every selected result below has `task_output.status=ok`,
one CHAIN, one closed AGENT root, and the listed child spans in
`F:\A2E\.a2e-data-containerized\a2e.db`.

| Dataset | Experiment row | LLM | TOOL | Evaluator result |
| --- | ---: | ---: | ---: | --- |
| MMLU | 32 | 1 | 0 | `mc_letter=1` |
| GSM8K | 45 | 1 | 0 | `numeric_match=1` |
| HumanEval | 46 | 1 | 0 | `substring=0` |
| PersistBench | 47 | 2 | 1 | `substring=0` |
| GDPVal | 72 | 28 | 29 | `llm_judge=0` |
| GPQA | 49 | 1 | 0 | `mc_letter=0` |
| MMLU-Pro | 50 | 1 | 0 | `mc_letter=0` |
| ARC-Challenge | 51 | 1 | 0 | `mc_letter=1` |
| TruthfulQA | 52 | 1 | 0 | `mc_letter=1` |
| BBH | 53 | 1 | 0 | `exact_match=0` |
| AGIEval | 54 | 1 | 0 | `mc_letter=1` |
| CommonsenseQA | 55 | 1 | 0 | `mc_letter=1` |
| HellaSwag | 56 | 1 | 0 | `mc_letter=1` |
| OpenBookQA | 57 | 1 | 0 | `mc_letter=1` |
| MATH | 58 | 1 | 0 | `numeric_match=0` |

GDPVal is registry-classified as QA but is a long, multi-step artifact task.
The default 600-second run (experiment row 48) timed out after exporting 20
LLM and 20 TOOL children, before the AGENT root could flush. Repeating the same
sample with `A2E_PI_DEADLINE=1200` completed in 28 turns and produced the valid
row 72 above. The retained failed row documents timeout behavior; it is not
counted as the acceptance result. Evaluator scores measure the sampled model's
answer quality, not monitor correctness.
