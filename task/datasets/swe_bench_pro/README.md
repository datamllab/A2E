# ageneval-task-swe-bench-pro

SWE-bench Pro (ScaleAI) dataset adapter for A2E — a **sandbox** dataset
(`kind="sandbox"`): each task runs the agent inside a real per-instance Docker
container, then grades with the **official** Scale harness while the container
is alive.

## What it is

- **Dataset**: [`ScaleAI/SWE-bench_Pro`](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro)
  (public `test` split, 731 long-horizon SWE instances across professional OSS
  repos: ansible, openlibrary, qutebrowser, NodeBB, … in Python / Go / JS / TS).
- **Images**: `jefzda/sweap-images:{dockerhub_tag}` (the `dockerhub_tag` column),
  repo checked out at `/app`.
- **Grading** (official, byte-for-byte): reset `/app` to `base_commit` → apply
  the model patch → run the instance's `before_repo_set_cmd` → run the official
  per-instance `run_script.sh` over `selected_test_files_to_run` → parse with the
  official per-instance `parser.py` → **resolved = (fail_to_pass ∪ pass_to_pass)
  ⊆ {tests with status PASSED}**.

## How it plugs into A2E

Registered as `swe-bench-pro` in `task/runners/.../registry.py` with
`kind="sandbox"`, `score=score_swe_bench_pro`, `setup=setup_swe_bench_pro`, and
default evaluators `swe_resolved` / `swe_fail_to_pass` / `swe_pass_to_pass`.
`SandboxScoringRunner` wraps any of the 9 A2E agents unchanged — the live sandbox
is injected via `state["__sandbox__"]`, the agent edits `/app` with `bash` /
`str_replace_editor`, and grading happens before the container is torn down.

## Vendored harness (standalone)

SWE-bench Pro has **no PyPI grading package**. The authoritative grader is the
set of per-instance `run_script.sh` + `parser.py` scripts from
[`scaleapi/SWE-bench_Pro-os`](https://github.com/scaleapi/SWE-bench_Pro-os)
(MIT). They are vendored as `_harness/run_scripts.tar.gz` (≈0.4 MB) so A2E grades
exactly like the official harness with **no out-of-repo dependency**. See
`_harness/README.md` for provenance + the upstream `LICENSE`.

## Requirements

- Docker on the host (each instance pulls a multi-GB image; runs are serial).
- HuggingFace access for the dataset (small, public, not gated).

## Quick use

```bash
# CLI (target one already-pulled instance via env pin if desired)
cd task && uv run --frozen python examples/run_experiment.py \
    --dataset swe-bench-pro --agent agno --evaluators swe_resolved --n 1
```
