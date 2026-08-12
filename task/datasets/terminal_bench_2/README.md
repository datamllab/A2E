# ageneval-task-terminal-bench-2

Terminal-Bench 2.0 dataset adapter for A2E — **sandboxed terminal-task evaluation**.

**Source:** [`laude-institute/terminal-bench-2`](https://github.com/laude-institute/terminal-bench-2)
(Apache-2.0). The benchmark has 89 terminal tasks; a curated subset is vendored
here under `src/ageneval/task/datasets/terminal_bench_2/vendor/tasks/`
(see `vendor/SOURCE.md`).

## Shape

Sandbox dataset (`kind="sandbox"`, like `swe-bench`). Each task's published Docker
image (`alexgshaw/<task>:<date>`, Docker Hub) is the ready-to-run environment:

1. `SandboxScoringRunner` pulls the image and starts the container.
2. The agent works inside it via the `bash` + `str_replace_editor` tools — this is
   the **trajectory** (every shell command is captured).
3. `score_terminal_bench_2` copies the held-out `tests/` in, runs the official
   `test.sh`, and reads `/logs/verifier/reward.txt` → `resolved`.

## Run

```bash
cd task
# pick a specific (small, fast) task; pull happens automatically
A2E_TB2_TASK=fix-git \
uv run python examples/run_experiment.py \
    --dataset terminal-bench-2 --agent agno --model qwen-max \
    --evaluators tb_resolved --n 1
```

A no-pin run prefers tasks whose image is already pulled locally.

### Adding more tasks

Drop another task directory (with `task.toml`, `instruction.md`, `environment/`,
`tests/`) into `vendor/tasks/` — the loader auto-discovers it. Copy it verbatim
from the upstream repo and keep the Apache-2.0 attribution.

## Environment knobs

| Variable | Purpose |
|---|---|
| `A2E_TB2_TASK` | Pin one task id (else first-N / locally-cached preferred) |
| `A2E_TB2_SCORE_PROXY` | Proxy URL injected into the container so `test.sh` can install pytest |
| `A2E_TB2_DOCKER_GW` | Docker bridge gateway IP for host-proxy rewrite (default `172.17.0.1`) |

> Scoring's `test.sh` fetches uv/pytest from the internet. If that's unreachable
> from inside the container, scoring degrades to `resolved=False` but the agent
> **trajectory is still fully captured**.
