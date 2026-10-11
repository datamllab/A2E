# Docker Runtime Internals

`benchmark/` contains the Docker runtime integration used by the public SeClaw batch entry point. Public model evaluation should start from `../scripts/batch_execute.sh --backend docker`.

## Architecture

```text
Batch wrapper                 Docker container per task
model config  ------------>   OpenClaw runtime
task loader     loads         /home/node/workspace
fixture deploy  deploys       /opt/mcp
agent runner    runs          /opt/mock_service
grading flow    grades        /opt/local_files
```

The runtime starts a fresh container for each task, deploys the task fixture, runs `fixture/init.sh`, configures OpenClaw for the model under test, sends the task prompt, collects transcript/workspace/audit artifacts, and hands the run back to the batch flow for evaluation and normalization.

## Public Batch Entry

Use the repository-level batch wrapper:

```bash
../scripts/batch_execute.sh     --backend docker     --tasks-jsonl ../batch_inputs/version/v1/test_tasks.jsonl     --models-config ../docker_models_config.yaml     --docker-concurrency 2     --batch-logs ../batch_logs     --batch-name docker_eval_v1
```

Model providers are configured in `.env` and selected per model in `docker_models_config.yaml`. Each model can use a different `model`, `base_url`, and `api_key_env`.

## Grading Modes

| Batch option | Behavior |
|--------------|----------|
| default | Run task graders and use LLM judge when a judge config is available. |
| `--skip-judge` | Run task graders only. |
| `--judge-models-config` | Use an explicit multi-judge YAML/JSON config. |

Judge providers are configured with `judge_models_config.yaml` and `EVAL_JUDGE_*` variables in `.env`.

## Task Loading

The open source release uses flat tasks under `tasks/openclaw/<task_id>/`. The loader also understands versioned `vN/` directories for compatibility, but release tasks are published flat.

For JSONL task lists, use `--tasks-jsonl batch_inputs/version/v1/test_tasks.jsonl`. Each row includes `task_name`, `task_id`, and `target`; the loader resolves it as `tasks/{target}/{task_id}`.

## Fixture Deployment

The Docker backend deploys task fixture directories to fixed container paths:

| Fixture path | Container path |
|--------------|----------------|
| `fixture/workspace/` | `/home/node/workspace/` |
| `fixture/mcp/` | `/opt/mcp/` |
| `fixture/mock_service/` | `/opt/mock_service/` |
| `fixture/local_files/` | `/opt/local_files/` |

If a task declares `workspace: /opt/workspace`, the runtime creates a compatibility symlink to `/home/node/workspace` before `init.sh` runs.

## Outputs

The public batch flow writes normalized artifacts to `batch_logs/{batch_name}`:

```text
batch_logs/{batch_name}/
├── jobs.jsonl
├── scores.json
├── report.md
├── analysis.json
├── logs/
├── .benchmark_runs/
└── traces/
    └── {trace_id}/
        ├── session_transcript.jsonl
        ├── transcript.jsonl
        ├── evaluation.json
        ├── grading.json
        ├── execution.json
        ├── audit_data.json
        └── workspace/
```

## Useful Batch Options

| Option | Default | Description |
|--------|---------|-------------|
| `--tasks-jsonl` | none | JSONL task list with `task_name`, `task_id`, and `target`. |
| `--tasks-dir` | none | Flat task directory, used instead of `--tasks-jsonl`. |
| `--models-config` | required | YAML config for models under test. |
| `--docker-concurrency` | 3 | Max parallel containers per model. |
| `--docker-image` | `ghcr.io/openclaw/openclaw:main` | Docker image. |
| `--docker-timeout` | 600 | Per-task timeout. |
| `--docker-init-timeout` | 300 | Fixture initialization timeout. |
| `--skip-judge` | off | Skip LLM judge scoring. |
| `--skip-analyze` | off | Skip `report.md` and `analysis.json`. |
