#!/usr/bin/env python3
"""Single-round Docker execution backend for OpenClaw tasks.

This wraps benchmark/benchmark.py and writes ARCA-like local artifacts so the
existing batch analyzer and build reviewer can consume Docker runs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from execution_core import copy_path_preserving_symlinks


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_SCRIPT = PROJECT_ROOT / "benchmark" / "benchmark.py"
EVALUATE_TRAJECTORY_SCRIPT = PROJECT_ROOT / "scripts" / "evaluate_trajectory.py"


@dataclass(frozen=True)
class DockerModel:
    id: str
    model: str
    base_url: str
    api_key_env: str
    api_key: str
    thinking: str


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-")
    return safe or "trace"


def _resolve_env_refs(value: Any) -> Any:
    """Resolve ${VAR_NAME} references in Docker model config strings."""
    if not isinstance(value, str):
        return value

    def replace(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1), "")

    return re.sub(r"\$\{([^}]+)\}", replace, value)


def load_models_config(path: Path) -> list[DockerModel]:
    """Load Docker model config YAML."""
    if not path.exists():
        raise FileNotFoundError(f"models config not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    models_data = data.get("models")
    if not isinstance(models_data, list) or not models_data:
        raise ValueError(f"{path} must contain a non-empty 'models' list")

    models: list[DockerModel] = []
    for idx, item in enumerate(models_data, 1):
        if not isinstance(item, dict):
            raise ValueError(f"{path}: models[{idx}] must be a mapping")
        model_id = str(_resolve_env_refs(item.get("id") or item.get("template_id") or "")).strip()
        model = str(_resolve_env_refs(item.get("model") or "")).strip()
        base_url = str(_resolve_env_refs(item.get("base_url") or "")).strip()
        api_key_env = str(item.get("api_key_env") or "").strip()
        thinking = str(_resolve_env_refs(item.get("thinking") or "medium")).strip()

        missing = [
            name for name, value in (
                ("id", model_id),
                ("model", model),
                ("base_url", base_url),
                ("api_key_env", api_key_env),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"{path}: models[{idx}] missing required fields: {', '.join(missing)}")
        api_key = os.environ.get(api_key_env, "")
        if not api_key:
            raise ValueError(f"{path}: env var {api_key_env} is not set for model {model_id}")

        models.append(DockerModel(
            id=model_id,
            model=model,
            base_url=base_url,
            api_key_env=api_key_env,
            api_key=api_key,
            thinking=thinking,
        ))
    return models


def _copy_if_exists(src: Path, dst: Path) -> None:
    copy_path_preserving_symlinks(src, dst)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _load_task_targets(task_list: Path | None) -> dict[str, str]:
    """Read task_id -> target mappings from an ARCA-style task list."""
    if task_list is None or not task_list.exists():
        return {}
    targets: dict[str, str] = {}
    with open(task_list, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            task_id = str(item.get("task_id") or "")
            target = str(item.get("target") or "")
            if task_id and target:
                targets[task_id] = target
    return targets


def _resolve_eval_task_dir(
    dataset: Path,
    task_id: str,
    task_version: str,
    task_targets: dict[str, str],
) -> Path:
    """Resolve the concrete task directory passed to evaluate_trajectory.py."""
    candidates: list[Path] = []
    target = task_targets.get(task_id, "")
    roots = [dataset]
    project_tasks = PROJECT_ROOT / "tasks"
    if project_tasks not in roots:
        roots.append(project_tasks)

    for root in roots:
        if target:
            task_root = root / target / task_id
            if task_version:
                candidates.append(task_root / task_version)
            candidates.append(task_root)
        if task_version:
            candidates.append(root / task_id / task_version)
        candidates.append(root / task_id)

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / "task.yaml").exists():
            return candidate

    raise FileNotFoundError(
        f"Could not resolve task dir for {task_id} version {task_version or '(unknown)'} "
        f"under dataset {dataset}"
    )


def evaluate_benchmark_run_compatible(
    benchmark_run_dir: Path,
    dataset: Path,
    task_list: Path | None,
    run_id: str,
    judge_models_config: str | None,
    skip_judge: bool,
    timeout: int,
) -> None:
    """Evaluate Docker-produced trajectories with the ARCA evaluate_trajectory.py path."""
    summary = _read_json(benchmark_run_dir / "scores.json")
    task_results = summary.get("task_results", [])
    if not isinstance(task_results, list):
        task_results = []

    task_targets = _load_task_targets(task_list)
    for result in task_results:
        if not isinstance(result, dict):
            continue
        task_id = str(result.get("task_id") or "")
        if not task_id:
            continue
        task_version = str(result.get("task_version") or "")
        run_task_dir = benchmark_run_dir / task_id / run_id
        output_path = run_task_dir / "grading.json"
        transcript_path = run_task_dir / "transcript.jsonl"
        if not transcript_path.exists():
            output_path.write_text(
                json.dumps({
                    "total_score": None,
                    "criteria": {},
                    "details": "",
                    "error": f"Trace file not found: {transcript_path}",
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            continue

        try:
            task_dir = _resolve_eval_task_dir(dataset, task_id, task_version, task_targets)
        except Exception as exc:
            output_path.write_text(
                json.dumps({
                    "total_score": None,
                    "criteria": {},
                    "details": "",
                    "error": str(exc),
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            continue

        fixture_workspace = task_dir / "fixture" / "workspace"
        workspace_path = fixture_workspace if fixture_workspace.exists() else task_dir

        cmd = [
            sys.executable,
            str(EVALUATE_TRAJECTORY_SCRIPT),
            "--task-dir", str(task_dir),
            "--trajectory", str(transcript_path),
            "--workspace", str(workspace_path),
            "--output", str(output_path),
        ]
        audit_data_path = run_task_dir / "audit_data.json"
        if audit_data_path.exists():
            cmd.extend(["--audit-data", str(audit_data_path)])
        if skip_judge:
            cmd.append("--skip-judge")
        elif judge_models_config:
            cmd.extend(["--judge-models-config", judge_models_config])

        proc = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        if proc.returncode != 0:
            output_path.write_text(
                json.dumps({
                    "total_score": None,
                    "criteria": {},
                    "details": proc.stdout,
                    "error": proc.stderr or f"evaluate_trajectory.py exited {proc.returncode}",
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs for model config validation without overriding env."""
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                continue
            value = value.strip().strip("\"'")
            os.environ.setdefault(key, value)


def normalize_benchmark_run(
    benchmark_run_dir: Path,
    round_dir: Path,
    traces_dir: Path,
    run_id: str,
    model_cfg: DockerModel,
    round_name: str,
) -> list[dict[str, Any]]:
    """Convert benchmark.py output to ARCA-like jobs and traces."""
    summary = _read_json(benchmark_run_dir / "scores.json")
    task_results = summary.get("task_results", [])
    if not isinstance(task_results, list):
        task_results = []

    jobs: list[dict[str, Any]] = []
    for result in task_results:
        if not isinstance(result, dict):
            continue
        task_id = str(result.get("task_id") or "")
        if not task_id:
            continue
        trace_id = _safe_id(f"{round_name}_{task_id}_{model_cfg.id}_{run_id}")
        src_dir = benchmark_run_dir / task_id / run_id
        trace_dir = traces_dir / trace_id
        trace_dir.mkdir(parents=True, exist_ok=True)

        _copy_if_exists(src_dir / "transcript.jsonl", trace_dir / "session_transcript.jsonl")
        _copy_if_exists(src_dir / "transcript.jsonl", trace_dir / "transcript.jsonl")
        _copy_if_exists(src_dir / "grading.json", trace_dir / "evaluation.json")
        _copy_if_exists(src_dir / "grading.json", trace_dir / "grading.json")
        _copy_if_exists(src_dir / "execution.json", trace_dir / "execution.json")
        _copy_if_exists(src_dir / "rounds.json", trace_dir / "rounds.json")
        _copy_if_exists(src_dir / "workspace", trace_dir / "workspace")
        _copy_if_exists(src_dir / "audit_data.json", trace_dir / "audit_data.json")
        _copy_if_exists(src_dir / "agent_stdout.txt", trace_dir / "agent_stdout.txt")
        _copy_if_exists(src_dir / "agent_stderr.txt", trace_dir / "agent_stderr.txt")

        evaluation = _read_json(trace_dir / "evaluation.json")
        execution = _read_json(trace_dir / "execution.json")
        evaluation_error = evaluation.get("error") or ""
        execution_error = execution.get("error") or ""
        benchmark_error = result.get("error") or ""
        if evaluation and not evaluation_error:
            error = execution_error
        else:
            error = benchmark_error or evaluation_error or execution_error
        eval_completed = not error and (trace_dir / "evaluation.json").exists()
        transcript_path = trace_dir / "session_transcript.jsonl"

        jobs.append({
            "task_name": task_id,
            "task_id": task_id,
            "category": "",
            "template_id": model_cfg.id,
            "model_name": model_cfg.model,
            "sandbox_id": "",
            "oss_trace_prefix": "",
            "download_status": "completed" if transcript_path.exists() else "failed",
            "local_trace_path": str(transcript_path),
            "eval_status": "completed" if eval_completed else "failed",
            "eval_output_path": str(trace_dir / "evaluation.json"),
            "total_score": evaluation.get("total_score", result.get("score")),
            "error": str(error),
            "backend": "docker",
            "round": round_name,
            "trace_dir": str(trace_dir),
            "task_version": result.get("task_version", execution.get("task_version", "")),
        })

    return jobs


def write_scores(round_dir: Path, jobs: list[dict[str, Any]], args: argparse.Namespace) -> None:
    scored = [j for j in jobs if j.get("eval_status") == "completed" and j.get("total_score") is not None]
    errors = [j for j in jobs if j.get("eval_status") == "failed"]
    scores = [float(j["total_score"]) for j in scored]
    summary = {
        "backend": "docker",
        "round": args.round_name,
        "run_id": args.run_id,
        "dataset": args.dataset,
        "task_list": args.task_list,
        "models_config": args.models_config,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_jobs": len(jobs),
        "scored_jobs": len(scored),
        "error_jobs": len(errors),
        "average_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "task_results": [
            {
                "task_id": j.get("task_id"),
                "task_version": j.get("task_version"),
                "model_name": j.get("model_name"),
                "template_id": j.get("template_id"),
                "score": j.get("total_score"),
                "error": j.get("error"),
                "trace_dir": j.get("trace_dir"),
            }
            for j in jobs
        ],
    }
    with open(round_dir / "scores.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


def build_benchmark_command(
    args: argparse.Namespace,
    model_cfg: DockerModel,
    run_id: str,
    benchmark_output: Path,
) -> list[str]:
    """Build the benchmark.py command for one Docker backend model."""
    cmd = [
        sys.executable,
        str(BENCHMARK_SCRIPT),
        "--model", model_cfg.model,
        "--dataset", args.dataset,
        "--concurrency", str(args.concurrency),
        "--runs", "1",
        "--output-dir", str(benchmark_output),
        "--run-id", run_id,
        "--base-url", model_cfg.base_url,
        "--no-grade",
        "--thinking", model_cfg.thinking,
        "--init-timeout", str(args.init_timeout),
        "--timeout", str(args.timeout),
        "--no-resume",
    ]
    if args.suite:
        cmd.extend(["--suite", args.suite])
    if args.task_list:
        cmd.extend(["--task-list", args.task_list])
    if args.env_file:
        cmd.extend(["--env-file", args.env_file])
    if args.image:
        cmd.extend(["--image", args.image])
    if args.with_reference_solution:
        cmd.append("--with-reference-solution")
    if args.verbose:
        cmd.append("--verbose")
    return cmd


def run_model(args: argparse.Namespace, model_cfg: DockerModel, run_id: str, work_dir: Path) -> list[dict[str, Any]]:
    benchmark_output = work_dir / "benchmark" / model_cfg.id
    benchmark_output.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["OPENAI_API_KEY"] = model_cfg.api_key
    env["OPENAI_BASE_URL"] = model_cfg.base_url
    if args.judge_api_key_env and os.environ.get(args.judge_api_key_env):
        env["JUDGE_API_KEY"] = os.environ[args.judge_api_key_env]
    if args.judge_base_url:
        env["JUDGE_BASE_URL"] = args.judge_base_url
    if args.judge_model:
        env["JUDGE_MODEL_ID"] = args.judge_model

    cmd = build_benchmark_command(args, model_cfg, run_id, benchmark_output)

    log_file = Path(args.round_dir) / "logs" / f"{_safe_id(model_cfg.id)}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "w", encoding="utf-8") as log:
        log.write("$ " + " ".join(c if c != model_cfg.api_key else "***" for c in cmd) + "\n")
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, text=True, stdout=log, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        raise RuntimeError(f"benchmark failed for model {model_cfg.id}; see {log_file}")

    benchmark_run_dir = benchmark_output / run_id
    evaluate_benchmark_run_compatible(
        benchmark_run_dir=benchmark_run_dir,
        dataset=Path(args.dataset),
        task_list=Path(args.task_list) if args.task_list else None,
        run_id=run_id,
        judge_models_config=None if args.skip_judge else args.judge_models_config,
        skip_judge=args.skip_judge,
        timeout=max(args.timeout, 300),
    )
    return normalize_benchmark_run(
        benchmark_run_dir=benchmark_run_dir,
        round_dir=Path(args.round_dir),
        traces_dir=Path(args.traces_dir),
        run_id=run_id,
        model_cfg=model_cfg,
        round_name=args.round_name,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Docker backend evaluation round")
    parser.add_argument("--dataset", required=True, help="Task dataset directory")
    parser.add_argument("--task-list", default=None, help="Optional ARCA-style task list JSONL")
    parser.add_argument("--suite", default=None, help="Optional comma-separated task IDs")
    parser.add_argument("--round-dir", required=True, help="Output directory for jobs/logs/scores")
    parser.add_argument("--traces-dir", default=None, help="Trace directory (default: round-dir/traces)")
    parser.add_argument("--round-name", default="batch", help="Round label for jobs.jsonl")
    parser.add_argument("--models-config", required=True, help="Docker model config YAML")
    parser.add_argument("--run-id", default=None, help="Shared run id for this round")
    parser.add_argument("--with-reference-solution", action="store_true",
                        help="Append metadata.yaml reference_solution to prompts")
    parser.add_argument("--skip-judge", action="store_true", help="Use automated grading only")
    parser.add_argument("--judge-base-url", default=os.environ.get("EVAL_JUDGE_BASE_URL"))
    parser.add_argument("--judge-model", default=os.environ.get("EVAL_JUDGE_MODEL_ID"))
    parser.add_argument("--judge-models-config", default=None)
    parser.add_argument("--judge-api-key-env", default="EVAL_JUDGE_API_KEY")
    parser.add_argument("--image", default=None)
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--init-timeout", type=int, default=300)
    parser.add_argument("--concurrency", type=int, default=1,
                        help="Max parallel Docker task containers for each model (default: 1)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.concurrency < 1:
        parser.error("--concurrency must be >= 1")

    round_dir = Path(args.round_dir)
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "logs").mkdir(exist_ok=True)
    if args.traces_dir is None:
        args.traces_dir = str(round_dir / "traces")
    Path(args.traces_dir).mkdir(parents=True, exist_ok=True)

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    args.run_id = run_id

    if args.env_file:
        load_env_file(Path(args.env_file))
    models = load_models_config(Path(args.models_config))
    work_dir = round_dir / ".benchmark_runs"
    jobs: list[dict[str, Any]] = []

    for model_cfg in models:
        jobs.extend(run_model(args, model_cfg, f"{run_id}_{_safe_id(model_cfg.id)}", work_dir))

    jobs_path = round_dir / "jobs.jsonl"
    with open(jobs_path, "w", encoding="utf-8") as f:
        for job in jobs:
            f.write(json.dumps(job, ensure_ascii=False) + "\n")
    write_scores(round_dir, jobs, args)
    print(f"[INFO] Docker backend round complete: {len(jobs)} job(s)")
    print(f"[INFO] Jobs:   {jobs_path}")
    print(f"[INFO] Traces: {args.traces_dir}")


if __name__ == "__main__":
    main()
