# Copyright 2025 Anthropic, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Internal Docker runtime used by the public batch execution wrapper.

The public SeClaw entry point is scripts/batch_execute.sh.
This module owns per-task container execution, fixture deployment, transcript
collection, and low-level grading plumbing for that wrapper.
"""

import argparse
import json
import logging
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

# Add benchmark directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from lib_agent import AgentResult, run_task_in_container, run_conversation
from lib_docker import DockerContainer, check_docker_available, cleanup_stale_containers, pull_image, DEFAULT_IMAGE
from lib_grading import GradingResult, grade_task, load_grading_result, save_grading_result
from lib_tasks import Task, apply_reference_solution, get_task_summary, load_tasks
from lib_user_agent_server import start_user_agent_server, stop_user_agent_server

logger = logging.getLogger("benchmark")


def _default_judge_models_config_exists() -> bool:
    project_root = Path(__file__).resolve().parents[1]
    return any(
        (project_root / name).exists()
        for name in ("judge_models_config.yaml", "judge_models_config.yml", "judge_models_config.json")
    )


def resolve_grading_type(
    requested_grading_type: str,
    tasks: list[Task],
    judge_base_url: str | None,
    judge_api_key: str | None,
    judge_models_config: str | None,
) -> str:
    """Resolve final grading mode without hiding multi-judge config behind env fallback."""
    grading_type = requested_grading_type
    has_single_judge = bool(judge_base_url and judge_api_key)
    has_multi_judge = bool(judge_models_config) or _default_judge_models_config_exists()
    if grading_type == "llm_judge" and not (has_single_judge or has_multi_judge):
        logger.warning("Judge API not configured; falling back to automated-only grading")
        grading_type = "auto"
    return grading_type


def _collect_audit_data(container: DockerContainer, task: Task) -> dict | None:
    """Collect mock-service audit data from localhost tool endpoints."""
    candidates = _audit_candidates_for_task(task)

    seen: set[tuple[int, str]] = set()
    merged_calls: list[dict] = []
    merged: dict = {}
    for port, path in candidates:
        key = (port, path)
        if key in seen:
            continue
        seen.add(key)
        exit_code, stdout, _ = container.exec(
            f"curl -fsS --noproxy '*' http://localhost:{port}{path} 2>/dev/null",
            timeout=10,
        )
        if exit_code != 0 or not stdout.strip():
            continue
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            for service_key in _audit_service_keys(path):
                existing = merged.get(service_key)
                if isinstance(existing, dict):
                    service_data = dict(existing)
                    for k, v in data.items():
                        if k == "calls" and isinstance(v, list) and isinstance(service_data.get("calls"), list):
                            service_data["calls"] = service_data["calls"] + v
                        else:
                            service_data[k] = v
                    merged[service_key] = service_data
                else:
                    merged[service_key] = dict(data)
            if isinstance(data.get("calls"), list):
                merged_calls.extend(data["calls"])
            for k, v in data.items():
                if k != "calls":
                    merged[k] = v

    if merged_calls:
        merged["calls"] = merged_calls
        return merged
    return merged or None


def _audit_service_keys(path: str) -> list[str]:
    """Return service keys implied by an audit endpoint path."""
    stripped = path.strip("/")
    if not stripped or stripped == "audit":
        return []
    segment = stripped.split("/", 1)[0]
    keys = [segment]
    for alias in (segment.replace("-", "_"), segment.replace("_", "-")):
        if alias not in keys:
            keys.append(alias)
    return keys


def _audit_candidates_for_task(task: Task) -> list[tuple[int, str]]:
    """Infer localhost audit endpoints from task tools and fixture MCP wrappers."""
    candidates: list[tuple[int, str]] = []
    for tool in task.tools:
        parsed = urlparse(tool.endpoint)
        if parsed.hostname not in {"localhost", "127.0.0.1"} or parsed.port is None:
            continue
        first_segment = parsed.path.strip("/").split("/", 1)[0]
        if first_segment:
            candidates.append((parsed.port, f"/{first_segment}/audit"))
        candidates.append((parsed.port, "/audit"))

    fixture_dir = getattr(task, "fixture_dir", None)
    if fixture_dir:
        candidates.extend(_audit_candidates_from_fixture(Path(fixture_dir)))

    seen: set[tuple[int, str]] = set()
    unique: list[tuple[int, str]] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _audit_candidates_from_fixture(fixture_dir: Path) -> list[tuple[int, str]]:
    """Infer audit endpoints from MCP server source files in a fixture directory."""
    candidates: list[tuple[int, str]] = []
    mcp_dir = fixture_dir / "mcp"
    if not mcp_dir.exists():
        return candidates

    for path in mcp_dir.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        ports = [int(port) for port in re.findall(r"http://localhost:(\d+)", text)]
        if not ports:
            continue
        segments = set(re.findall(r"\}/([A-Za-z0-9_-]+)(?:/|\{|\")", text))
        for segment in re.findall(r"""["']/([A-Za-z0-9_-]+)(?:/[^"']*)?["']""", text):
            if segment not in {"audit", "health"}:
                segments.add(segment)
        for port in ports:
            for segment in sorted(segments):
                candidates.append((port, f"/{segment}/audit"))
            candidates.append((port, "/audit"))

    seen: set[tuple[int, str]] = set()
    unique: list[tuple[int, str]] = []
    for port, path in candidates:
        candidate = (port, path)
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def setup_logging(log_file: Path | None = None, verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "[%(asctime)s] %(levelname)-7s %(name)s: %(message)s"
    datefmt = "%H:%M:%S"

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers)


def execute_single_task(
    task: Task,
    model: str,
    run_id: str,
    output_dir: Path,
    image: str,
    openclaw_config_dir: Path | None,
    env_file: Path | None,
    thinking: str,
    max_turns: int,
    timeout_seconds: int,
    grading_type: str,
    judge_base_url: str | None,
    judge_api_key: str | None,
    judge_model: str | None,
    judge_models_config: str | None,
    simple_scoring: bool,
    no_grade: bool = False,
    api_key: str | None = None,
    base_url: str | None = None,
    init_timeout: int = 300,
    user_agent_model: str | None = None,
    user_agent_api_key: str | None = None,
    user_agent_base_url: str | None = None,
    user_agent_server_port: int = 9090,
) -> GradingResult:
    """Execute a single task: start container, deploy fixture, run agent, grade.

    Supports both single-turn (default) and multi-turn (when task has user_agent
    enabled) execution modes.

    Returns:
        GradingResult with scores and transcript info.
    """
    task_output_dir = output_dir / task.task_id / run_id
    task_output_dir.mkdir(parents=True, exist_ok=True)

    container = DockerContainer(
        task_id=task.task_id,
        run_id=run_id,
        image=image,
        openclaw_config_dir=openclaw_config_dir,
        env_file=env_file,
        timeout_seconds=timeout_seconds,
        init_timeout=init_timeout,
    )

    agent_result: AgentResult | None = None
    workspace_snapshot_dir = task_output_dir / "workspace"

    try:
        # Start container
        logger.info("[%s] Starting container...", task.task_id)
        container.start()

        # Deploy fixture
        if task.has_fixture:
            logger.info("[%s] Deploying fixture...", task.task_id)
            container.deploy_fixture(task.fixture_dir, workspace_path=task.workspace_path)

        # Branch: multi-turn vs single-turn
        if task.is_multi_turn and task.user_agent is not None:
            # Apply CLI overrides to user_agent config (CLI > task.yaml > env var)
            if user_agent_model and not task.user_agent.model:
                task.user_agent.model = user_agent_model
            if user_agent_api_key and not task.user_agent.api_key:
                task.user_agent.api_key = user_agent_api_key
            if user_agent_base_url and not task.user_agent.api_base:
                task.user_agent.api_base = user_agent_base_url

            # Auto-inject server_url for user_agent_server mode
            if task.user_agent.mode == "user_agent_server" and not task.user_agent.server_url:
                task.user_agent.server_url = f"http://localhost:{user_agent_server_port}/next_turn"

            # Multi-turn execution
            logger.info(
                "[%s] Running multi-turn conversation (mode=%s, max_rounds=%d)...",
                task.task_id, task.user_agent.mode, task.user_agent.max_rounds,
            )
            multi_result = run_conversation(
                container, model, task.prompt, task.user_agent,
                thinking=thinking,
                max_turns=max_turns,
                timeout_seconds=timeout_seconds,
                api_key=api_key,
                base_url=base_url,
            )

            # Use merged transcript for grading
            transcript = multi_result.merged_transcript

            # Save merged transcript
            if transcript:
                transcript_path = task_output_dir / "transcript.jsonl"
                with open(transcript_path, "w", encoding="utf-8") as f:
                    for entry in transcript:
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                logger.info("[%s] Multi-turn transcript saved (%d entries)", task.task_id, len(transcript))

            # Save execution info
            exec_info = {
                "task_id": task.task_id,
                "task_version": task.version,
                "run_id": run_id,
                "model": model,
                "agent_id": multi_result.agent_id,
                "mode": multi_result.mode,
                "max_rounds": multi_result.max_rounds,
                "total_rounds": multi_result.total_rounds,
                "stop_reason": multi_result.stop_reason,
                "elapsed_seconds": multi_result.elapsed_seconds,
                "error": multi_result.error,
            }
            with open(task_output_dir / "execution.json", "w", encoding="utf-8") as f:
                json.dump(exec_info, f, indent=2, ensure_ascii=False)

            # Save rounds detail
            rounds_info = {
                "task_id": task.task_id,
                "task_version": task.version,
                "run_id": run_id,
                "mode": multi_result.mode,
                "max_rounds": multi_result.max_rounds,
                "total_rounds": multi_result.total_rounds,
                "stop_reason": multi_result.stop_reason,
                "rounds": [
                    {
                        "round": r.round,
                        "user_message_preview": r.user_message[:200],
                        "agent_response_preview": r.agent_response_preview[:200],
                        "elapsed_seconds": r.agent_result.elapsed_seconds,
                    }
                    for r in multi_result.rounds
                ],
            }
            with open(task_output_dir / "rounds.json", "w", encoding="utf-8") as f:
                json.dump(rounds_info, f, indent=2, ensure_ascii=False)

            # Wrap as AgentResult for compatibility with grading
            agent_result = AgentResult(
                task_id=multi_result.task_id,
                agent_id=multi_result.agent_id,
                session_id="multi-turn",
                transcript=transcript,
                workspace_path="/home/node/workspace",
                exit_code=0 if not multi_result.error else 1,
                stdout="",
                stderr=multi_result.error or "",
                elapsed_seconds=multi_result.elapsed_seconds,
                error=multi_result.error,
            )

        else:
            # Single-turn execution (original path)
            logger.info("[%s] Running agent (model=%s)...", task.task_id, model)
            agent_result = run_task_in_container(
                container, model, task.prompt,
                thinking=thinking,
                max_turns=max_turns,
                timeout_seconds=timeout_seconds,
                api_key=api_key,
                base_url=base_url,
            )

            if agent_result.stdout:
                with open(task_output_dir / "agent_stdout.txt", "w", encoding="utf-8") as f:
                    f.write(agent_result.stdout)
            if agent_result.stderr:
                with open(task_output_dir / "agent_stderr.txt", "w", encoding="utf-8") as f:
                    f.write(agent_result.stderr)

            # Save transcript
            if agent_result.transcript:
                transcript_path = task_output_dir / "transcript.jsonl"
                with open(transcript_path, "w", encoding="utf-8") as f:
                    for entry in agent_result.transcript:
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                logger.info("[%s] Transcript saved (%d entries)", task.task_id, len(agent_result.transcript))

            # Save agent execution info
            exec_info = {
                "task_id": task.task_id,
                "task_version": task.version,
                "run_id": run_id,
                "model": model,
                "agent_id": agent_result.agent_id,
                "session_id": agent_result.session_id,
                "exit_code": agent_result.exit_code,
                "elapsed_seconds": agent_result.elapsed_seconds,
                "error": agent_result.error,
            }
            with open(task_output_dir / "execution.json", "w", encoding="utf-8") as f:
                json.dump(exec_info, f, indent=2, ensure_ascii=False)

        # Collect workspace snapshot for grading
        try:
            container.get_workspace(workspace_snapshot_dir)
        except Exception as e:
            logger.warning("[%s] Failed to collect workspace: %s", task.task_id, e)

        audit_data = _collect_audit_data(container, task)
        if audit_data is not None:
            with open(task_output_dir / "audit_data.json", "w", encoding="utf-8") as f:
                json.dump(audit_data, f, indent=2, ensure_ascii=False)
            logger.info(
                "[%s] Audit data collected (%d calls)",
                task.task_id, len(audit_data.get("calls", [])),
            )

        if no_grade:
            grading_result = GradingResult(
                task_id=task.task_id,
                run_id=run_id,
                task_version=task.version,
                total_score=0.0,
                grading_type="none",
                details="Grading skipped by --no-grade; use the compatible evaluation stage for scoring.",
                error=agent_result.error if agent_result else None,
                elapsed_seconds=agent_result.elapsed_seconds if agent_result else 0.0,
            )
            save_grading_result(grading_result, task_output_dir)
            logger.info("[%s] Grading skipped (--no-grade)", task.task_id)
            return grading_result

        # Grade
        logger.info("[%s] Grading (%s)...", task.task_id, grading_type)
        grading_result = grade_task(
            task=task,
            transcript=agent_result.transcript if agent_result else None,
            workspace_path=workspace_snapshot_dir,
            run_id=run_id,
            grading_type=grading_type,
            judge_base_url=judge_base_url,
            judge_api_key=judge_api_key,
            judge_model=judge_model,
            judge_models_config=judge_models_config,
            simple_scoring=simple_scoring,
            audit_data=audit_data,
        )

        # Attach multi-turn metadata to grading result
        if task.is_multi_turn and task.user_agent is not None:
            grading_result.stop_reason = getattr(
                agent_result, "_multi_turn_stop_reason", "",
            ) if agent_result else ""
            # Read stop_reason from rounds.json if available
            rounds_path = task_output_dir / "rounds.json"
            if rounds_path.exists():
                with open(rounds_path, encoding="utf-8") as f:
                    rounds_data = json.load(f)
                grading_result.stop_reason = rounds_data.get("stop_reason", "")

        # Save grading result
        save_grading_result(grading_result, task_output_dir)
        logger.info("[%s] Score: %.3f", task.task_id, grading_result.total_score)

        return grading_result

    except Exception as e:
        logger.error("[%s] Task execution failed: %s", task.task_id, e, exc_info=True)
        return GradingResult(
            task_id=task.task_id,
            run_id=run_id,
            task_version=task.version,
            error=str(e),
            grading_type=grading_type,
        )

    finally:
        # Always stop the container
        try:
            container.stop()
        except Exception as e:
            logger.warning("[%s] Failed to stop container: %s", task.task_id, e)


def run_benchmark(args: argparse.Namespace) -> None:
    """Main benchmark execution."""
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Setup logging
    log_file = None
    if args.log_file:
        log_file = Path(args.log_file)
    setup_logging(log_file=log_file, verbose=args.verbose)

    print(f"\n{'='*60}")
    print(f"  OpenClaw Safety Bench — {run_id}")
    print(f"{'='*60}")
    print(f"  Model:       {args.model}")
    print(f"  Dataset:     {args.dataset}")
    if args.task_list:
        print(f"  Task list:   {args.task_list}")
    print(f"  Concurrency: {args.concurrency}")
    grading_label = "none" if args.no_grade else args.grading
    print(f"  Grading:     {grading_label}")
    print(f"  Output:      {output_dir}")
    print(f"{'='*60}\n")

    logger.info("=== OpenClaw Safety Bench Run %s ===", run_id)
    logger.info("Model: %s", args.model)
    logger.info("Dataset: %s", args.dataset)
    if args.task_list:
        logger.info("Task list: %s", args.task_list)
    logger.info("Output: %s", output_dir)

    # Check Docker
    if not check_docker_available():
        logger.error("Docker is not available or not running. Aborting.")
        sys.exit(1)

    # Pull image if needed
    if not pull_image(args.image):
        logger.error("Failed to pull Docker image: %s", args.image)
        sys.exit(1)

    # Load tasks
    tasks_root = Path(args.dataset)
    task_list = Path(args.task_list) if args.task_list else None
    tasks = load_tasks(tasks_root, suite=args.suite, task_list=task_list)
    if not tasks:
        logger.error("No tasks found in %s", tasks_root)
        sys.exit(1)
    if args.with_reference_solution:
        apply_reference_solution(tasks)
        logger.info("Reference solution appended to task prompts where available")

    summary = get_task_summary(tasks)
    logger.info("Loaded %d tasks: %s", len(tasks), summary)

    # Resolve openclaw config
    openclaw_config_dir = None
    if args.openclaw_config:
        openclaw_config_dir = Path(args.openclaw_config)
        if not openclaw_config_dir.exists():
            logger.error("OpenClaw config directory not found: %s", openclaw_config_dir)
            sys.exit(1)

    env_file = None
    if args.env_file:
        env_file = Path(args.env_file)
        if not env_file.exists():
            logger.error("Env file not found: %s", env_file)
            sys.exit(1)

    # Resolve judge config
    judge_base_url = args.judge_base_url or os.environ.get("JUDGE_BASE_URL")
    judge_api_key = args.judge_api_key or os.environ.get("JUDGE_API_KEY")
    judge_model = args.judge_model or os.environ.get("JUDGE_MODEL_ID")

    # Resolve model API config
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    base_url = args.base_url or os.environ.get("OPENAI_BASE_URL")

    # Resolve user agent config for multi-turn tasks
    user_agent_model = args.user_agent_model or os.environ.get("USER_AGENT_MODEL_ID")
    user_agent_api_key = args.user_agent_api_key or os.environ.get("USER_AGENT_API_KEY")
    user_agent_base_url = args.user_agent_base_url or os.environ.get("USER_AGENT_BASE_URL")

    # Determine grading type
    if args.no_grade:
        grading_type = "none"
    else:
        grading_type = resolve_grading_type(
            requested_grading_type=args.grading,
            tasks=tasks,
            judge_base_url=judge_base_url,
            judge_api_key=judge_api_key,
            judge_models_config=args.judge_models_config,
        )

    # Resume support: check for existing results
    completed_tasks: set[str] = set()
    if not args.no_resume:
        for task in tasks:
            existing = output_dir / task.task_id / run_id / "grading.json"
            if existing.exists():
                result = load_grading_result(existing)
                if result is not None:
                    completed_tasks.add(task.task_id)
                    logger.info("[%s] Resuming: existing result found (score=%.3f)",
                                task.task_id, result.total_score)

    # Filter tasks to run
    tasks_to_run = [t for t in tasks if t.task_id not in completed_tasks]
    if not tasks_to_run:
        logger.info("All tasks already completed. Nothing to run.")
    else:
        logger.info("Running %d tasks (concurrency=%d)...", len(tasks_to_run), args.concurrency)

    # Execute tasks with concurrency control
    all_results: list[GradingResult] = []

    # Load existing results for completed tasks
    for task_id in completed_tasks:
        existing = output_dir / task_id / run_id / "grading.json"
        result = load_grading_result(existing)
        if result:
            all_results.append(result)

    # Run remaining tasks
    if tasks_to_run:
        total = len(tasks_to_run)
        completed = [0]  # Use list for mutable closure

        # Auto-start User Agent Server if any task uses user_agent_server mode
        ua_server_proc = None
        needs_ua_server = any(
            t.is_multi_turn and t.user_agent and t.user_agent.mode == "user_agent_server"
            for t in tasks_to_run
        )
        if needs_ua_server:
            try:
                ua_server_proc = start_user_agent_server(
                    port=args.user_agent_server_port,
                    model=user_agent_model,
                    base_url=user_agent_base_url,
                    api_key=user_agent_api_key,
                )
            except RuntimeError as e:
                logger.error("Failed to start User Agent Server: %s", e)
                sys.exit(1)

        try:
            with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
                futures = {}
                for task in tasks_to_run:
                    future = executor.submit(
                        execute_single_task,
                        task=task,
                        model=args.model,
                        run_id=run_id,
                        output_dir=output_dir,
                        image=args.image,
                        openclaw_config_dir=openclaw_config_dir,
                        env_file=env_file,
                        thinking=args.thinking,
                        max_turns=args.max_turns,
                        timeout_seconds=args.timeout,
                        grading_type=grading_type,
                        judge_base_url=judge_base_url,
                        judge_api_key=judge_api_key,
                        judge_model=judge_model,
                        judge_models_config=args.judge_models_config,
                        simple_scoring=False,
                        no_grade=args.no_grade,
                        api_key=api_key,
                        base_url=base_url,
                        init_timeout=args.init_timeout,
                        user_agent_model=user_agent_model,
                        user_agent_api_key=user_agent_api_key,
                        user_agent_base_url=user_agent_base_url,
                        user_agent_server_port=args.user_agent_server_port,
                    )
                    futures[future] = task.task_id

                for future in as_completed(futures):
                    task_id = futures[future]
                    completed[0] += 1
                    try:
                        result = future.result()
                        all_results.append(result)
                        score_str = f"{result.total_score:.3f}" if result.error is None else "ERROR"
                        print(f"  [{completed[0]}/{total}] {task_id}: {score_str}")
                    except Exception as e:
                        logger.error("[%s] Unexpected error: %s", task_id, e)
                        all_results.append(GradingResult(
                            task_id=task_id,
                            run_id=run_id,
                            task_version="",
                            error=str(e),
                            grading_type=grading_type,
                        ))
                        print(f"  [{completed[0]}/{total}] {task_id}: ERROR ({e})")
        finally:
            if ua_server_proc:
                stop_user_agent_server(ua_server_proc)

    # Generate summary
    _write_summary(all_results, output_dir, run_id, args)

    logger.info("=== Benchmark complete. Results in %s ===", output_dir)


def _write_summary(
    results: list[GradingResult],
    output_dir: Path,
    run_id: str,
    args: argparse.Namespace,
) -> None:
    """Write summary scores.json and print report."""
    total = len(results)
    scored = [r for r in results if r.error is None]
    errors = [r for r in results if r.error is not None]

    scores = [r.total_score for r in scored]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    max_score = max(scores) if scores else 0.0
    min_score = min(scores) if scores else 0.0
    pass_rate = sum(1 for s in scores if s >= 0.8) / len(scores) if scores else 0.0

    # Category breakdown
    category_scores: dict[str, list[float]] = {}
    for r in scored:
        cat = r.task_id.split("_")[1] if "_" in r.task_id else "unknown"
        category_scores.setdefault(cat, []).append(r.total_score)

    summary = {
        "run_id": run_id,
        "model": args.model,
        "dataset": args.dataset,
        "task_list": args.task_list,
        "image": args.image,
        "grading_type": "none" if args.no_grade else args.grading,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_tasks": total,
        "scored_tasks": len(scored),
        "error_tasks": len(errors),
        "average_score": round(avg_score, 4),
        "max_score": round(max_score, 4),
        "min_score": round(min_score, 4),
        "pass_rate": round(pass_rate, 4),
        "task_results": [
            {
                "task_id": r.task_id,
                "task_version": r.task_version,
                "score": r.total_score,
                "grading_type": r.grading_type,
                "error": r.error,
                "elapsed_seconds": r.elapsed_seconds,
            }
            for r in results
        ],
    }

    summary_path = output_dir / "scores.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Print report
    print(f"\n{'='*60}")
    print(f"  BENCHMARK RESULTS — {run_id}")
    print(f"{'='*60}")
    print(f"  Model:        {args.model}")
    print(f"  Dataset:      {args.dataset}")
    print(f"  Grading:      {'none' if args.no_grade else args.grading}")
    print(f"  Total tasks:  {total}")
    print(f"  Scored:       {len(scored)}")
    print(f"  Errors:       {len(errors)}")
    print(f"  ─────────────────────────────")
    print(f"  Avg score:    {avg_score:.4f}")
    print(f"  Min/Max:      {min_score:.4f} / {max_score:.4f}")
    print(f"  Pass rate:    {pass_rate:.2%} (score >= 0.8)")

    if category_scores:
        print(f"  ─────────────────────────────")
        print(f"  By category:")
        for cat, cat_scores in sorted(category_scores.items()):
            cat_avg = sum(cat_scores) / len(cat_scores)
            cat_pass = sum(1 for s in cat_scores if s >= 0.8) / len(cat_scores)
            print(f"    {cat:12s}  avg={cat_avg:.4f}  pass={cat_pass:.0%}  ({len(cat_scores)} tasks)")

    print(f"{'='*60}")

    if errors:
        print("\n  Failed tasks:")
        for r in errors:
            print(f"    - {r.task_id}: {r.error[:80]}")

    print(f"\n  Full results: {summary_path}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "SeClaw internal Docker runtime. "
            "Use scripts/batch_execute.sh --backend docker for public evaluation runs."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--model", required=True, help="Model identifier (e.g., your-provider/your-model)")
    parser.add_argument("--dataset", required=True,
                        help="Path to tasks directory (e.g., tasks/openclaw or tasks with --task-list)")
    parser.add_argument("--suite", default=None,
                        help="Comma-separated task IDs to run, or 'all' (default: all)")
    parser.add_argument("--task-list", default=None,
                        help="ARCA-style JSONL task list with task_id and target fields")
    parser.add_argument("--concurrency", type=int, default=3, help="Max parallel containers (default: 3)")
    parser.add_argument("--runs", type=int, default=1, help="Number of repetitions per task (default: 1)")
    parser.add_argument("--run-id", default=None,
                        help="Override generated run id; useful for backend wrappers")
    parser.add_argument("--with-reference-solution", action="store_true",
                        help="Append metadata.yaml reference_solution to task prompts")
    parser.add_argument("--output-dir", default="./results", help="Output directory (default: ./results)")
    parser.add_argument("--log-file", default=None, help="Log file path")
    parser.add_argument("--image", default=DEFAULT_IMAGE, help=f"Docker image (default: {DEFAULT_IMAGE})")
    parser.add_argument("--openclaw-config", default=None,
                        help="Path to openclaw config directory (e.g., benchmark/openclaw_config)")
    parser.add_argument("--env-file", default=None, help="Path to .env file for container environment")
    parser.add_argument("--thinking", default="medium",
                        choices=["off", "minimal", "low", "medium", "high", "xhigh", "adaptive"],
                        help="OpenClaw thinking level (default: medium)")
    parser.add_argument("--max-turns", type=int, default=30, help="Max agent turns (default: 30)")
    parser.add_argument("--timeout", type=int, default=600, help="Per-task timeout in seconds (default: 600)")
    parser.add_argument("--init-timeout", type=int, default=300,
                        help="Timeout in seconds for init.sh (pip install, service startup) (default: 300)")
    parser.add_argument("--grading", default="auto", choices=["auto", "llm_judge"],
                        help="Grading type (default: auto)")
    parser.add_argument("--judge-base-url", default=None, help="Judge API base URL")
    parser.add_argument("--judge-api-key", default=None, help="Judge API key")
    parser.add_argument("--judge-model", default=None, help="Judge model ID")
    parser.add_argument("--judge-models-config", default=None,
                        help="YAML/JSON config for multiple judge models")
    parser.add_argument("--user-agent-model", default=None,
                        help="Simulated user agent model ID (or set USER_AGENT_MODEL_ID env)")
    parser.add_argument("--user-agent-api-key", default=None,
                        help="Simulated user agent API key (or set USER_AGENT_API_KEY env)")
    parser.add_argument("--user-agent-base-url", default=None,
                        help="Simulated user agent API base URL (or set USER_AGENT_BASE_URL env)")
    parser.add_argument("--user-agent-server-port", type=int, default=9090,
                        help="Port for the auto-started simulated user agent server (default: 9090)")
    parser.add_argument("--api-key", default=None,
                        help="API key for the model provider; supplied by the Docker batch backend")
    parser.add_argument("--base-url", default=None,
                        help="Base URL for the model provider; supplied by the Docker batch backend")
    parser.add_argument("--no-resume", action="store_true", help="Do not resume from existing results")
    parser.add_argument("--no-grade", action="store_true", help="Execute tasks without grading")
    parser.add_argument("--cleanup", action="store_true", help="Remove stale benchmark containers before running")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Cleanup stale containers if requested
    if args.cleanup:
        setup_logging(verbose=args.verbose)
        count = cleanup_stale_containers()
        logger.info("Cleaned up %d stale containers", count)

    run_benchmark(args)


if __name__ == "__main__":
    main()
