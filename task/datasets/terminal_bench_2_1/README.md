# ageneval-task-terminal-bench-2-1

Terminal-Bench 2.1 dataset adapter for AEP sandboxed terminal-task evaluation.

**Source:** [`harbor-framework/terminal-bench-2-1`](https://github.com/harbor-framework/terminal-bench-2-1)
(Apache-2.0), pinned to commit
`5c8eadf1f393183288fa08b8f73ca9a469cc5e00`. The complete set of 89 task
definitions is vendored under
`src/ageneval/task/datasets/terminal_bench_2_1/vendor/tasks/`.
See `vendor/SOURCE.md` and `vendor/LICENSE`.

## Shape

This is a sandbox dataset (`kind="sandbox"`). Each task points to its published
Docker image:

1. `SandboxScoringRunner` pulls and starts the image.
2. The agent works through the sandbox-backed `bash` and
   `str_replace_editor` tools.
3. `score_terminal_bench_2_1` copies the held-out `tests/` directory into the
   live container and runs the official verifier.
4. The verifier reward is normalized to the `resolved` result.

The 89 task definitions are stored locally. Docker images are pulled only when a
selected task is run.

## Run

```bash
cd /root/ageneval/AEP/task
AEP_TB21_TASK=fix-git \
uv run --frozen python examples/run_experiment.py \
  --dataset terminal-bench-2.1 \
  --agent agno \
  --model qwen-max \
  --evaluators tb_resolved \
  --n 1
```

Without `AEP_TB21_TASK`, the loader prefers an already cached task image and
then falls back to task-name order.

## Environment

| Variable | Purpose |
|---|---|
| `AEP_TB21_TASK` | Pin one Terminal-Bench 2.1 task ID |
| `A2E_TB21_TASK` | Backward-compatible alias for `AEP_TB21_TASK` |
| `A2E_TB2_SCORE_PROXY` | Proxy URL used by in-container verifier setup |
| `A2E_TB2_DOCKER_GW` | Docker bridge gateway used for proxy rewriting |
