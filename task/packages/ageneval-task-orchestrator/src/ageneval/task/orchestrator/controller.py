"""Single-controller, multi-process Campaign orchestration."""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
import logging
import math
import multiprocessing
import os
import queue
import subprocess
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ageneval.model.gateway import (
    ModelProfile,
    ModelRuntime,
    ResolvedModel,
    load_model_profile,
    resolve_model,
)

from .concurrency import PermitBroker, RuntimeMetrics
from .executor import _error_retryable, _run_grader, run_cell_worker
from .matrix import CampaignPlan, expand_campaign
from .process import TrialProcessRunner
from .schema import (
    CampaignConfig,
    GraderConfig,
    LifecycleEvent,
    LifecycleRecord,
    TrialResult,
    load_campaign,
)
from .sink import A2ESink
from .state import RunDirectory, read_json

logger = logging.getLogger(__name__)


def _git_state(repo_root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ).stdout.strip()

    try:
        return {
            "commit": run("rev-parse", "HEAD"),
            "branch": run("branch", "--show-current"),
            "dirty": bool(run("status", "--porcelain")),
        }
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "branch": None, "dirty": None}


def _versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for name in (
        "ageneval-model-gateway",
        "ageneval-task-orchestrator",
        "ageneval-task-core",
        "ageneval-task-runners",
        "a2e-client",
    ):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "source"
    return result


def _task_payload(task: Any) -> dict[str, Any]:
    payload = {
        "task_id": task.task_id,
        "instruction": task.instruction,
        "initial_state": dict(task.initial_state),
        "expected_actions": list(task.expected_actions),
        "expected_outputs": list(task.expected_outputs),
        "metadata": dict(task.metadata),
        "sandbox": dict(task.sandbox) if task.sandbox is not None else None,
    }
    return json.loads(json.dumps(payload, ensure_ascii=False, default=str))


def _dataset_example(task: dict[str, Any]) -> dict[str, Any]:
    metadata = {"task_id": task["task_id"], **dict(task.get("metadata") or {})}
    if task.get("sandbox") is not None:
        metadata["sandbox"] = task["sandbox"]
    return {
        "input": {
            "instruction": task["instruction"],
            "initial_state": task.get("initial_state") or {},
        },
        "output": {
            "expected_outputs": task.get("expected_outputs") or [],
            "expected_actions": task.get("expected_actions") or [],
        },
        "metadata": metadata,
    }


class CampaignController:
    def __init__(
        self,
        *,
        config: CampaignConfig,
        config_path: Path | None,
        run_directory: RunDirectory,
        model_directory: Path,
        repo_root: Path,
        resume: bool = False,
    ) -> None:
        self.config = config
        self.config_path = config_path
        self.run_directory = run_directory
        self.model_directory = model_directory.resolve()
        self.repo_root = repo_root.resolve()
        self.resume = resume
        self.profiles: dict[str, ModelProfile] = {}
        self.profile_paths: dict[str, Path] = {}
        self.benchmark_profiles: dict[str, Any] = {}
        self.benchmark_profile_paths: dict[str, Path] = {}
        self.tasks: dict[str, list[dict[str, Any]]] = {}
        self.benchmarks: dict[str, dict[str, Any]] = {}
        self.plan: CampaignPlan | None = None
        self.lock: dict[str, Any] = {}
        self.concurrency_stats: dict[str, dict[str, int]] = {}
        self.runtime_stats: dict[str, Any] = {}
        self.gateway_stats: dict[str, dict[str, int]] = {}
        self._active_runtimes: dict[str, ModelRuntime] = {}

    @classmethod
    def from_config(
        cls,
        config_path: str | Path,
        *,
        runs_directory: str | Path,
        model_directory: str | Path,
        repo_root: str | Path,
    ) -> CampaignController:
        path = Path(config_path).resolve()
        config = load_campaign(path)
        provisional = expand_campaign_id(config)
        return cls(
            config=config,
            config_path=path,
            run_directory=RunDirectory(Path(runs_directory) / provisional),
            model_directory=Path(model_directory),
            repo_root=Path(repo_root),
        )

    @classmethod
    def from_run_directory(
        cls,
        run_directory: str | Path,
        *,
        model_directory: str | Path,
        repo_root: str | Path,
    ) -> CampaignController:
        run = RunDirectory(run_directory)
        config = CampaignConfig.model_validate(read_json(run.config_path))
        return cls(
            config=config,
            config_path=None,
            run_directory=run,
            model_directory=Path(model_directory),
            repo_root=Path(repo_root),
            resume=True,
        )

    def prepare(self) -> CampaignPlan:
        from ageneval.task.runners import (
            AGENTS,
            DATASETS,
            grader_for_dataset,
            sample_dataset,
        )

        unknown_benchmarks = {item.id for item in self.config.benchmarks} - set(DATASETS)
        unknown_harnesses = set(self.config.harnesses) - set(AGENTS)
        if unknown_benchmarks:
            raise ValueError(f"unknown benchmarks: {sorted(unknown_benchmarks)}")
        if unknown_harnesses:
            raise ValueError(f"unknown harnesses: {sorted(unknown_harnesses)}")

        for model_ref in self.config.models:
            path = Path(model_ref)
            if not path.is_absolute():
                candidate = self.model_directory / f"{model_ref}.yaml"
                path = candidate if candidate.exists() else self.model_directory / model_ref
            profile = load_model_profile(path)
            if profile.id != model_ref and Path(model_ref).name not in {
                path.name,
                path.stem,
            }:
                raise ValueError(
                    f"model reference {model_ref!r} resolved to profile id {profile.id!r}"
                )
            if profile.id in self.profiles:
                raise ValueError(f"duplicate model profile id: {profile.id}")
            self.profiles[model_ref] = profile
            self.profile_paths[model_ref] = path.resolve()

        locked_selections = {}
        locked_benchmark_profiles: dict[str, Any] = {}
        if self.resume:
            self.lock = self.run_directory.verify_config(
                self.config.model_dump(mode="json", exclude_none=False)
            )
            locked_selections = self.lock.get("selections") or {}
            locked_benchmark_profiles = self.lock.get("benchmark_profiles") or {}

        selected_ids: dict[str, list[str]] = {}
        for benchmark in self.config.benchmarks:
            ds_entry = DATASETS[benchmark.id]
            benchmark_profile = ds_entry["profile"]
            benchmark_profile_path = Path(ds_entry["profile_path"])
            self.benchmark_profiles[benchmark.id] = benchmark_profile
            self.benchmark_profile_paths[benchmark.id] = benchmark_profile_path
            if locked_benchmark_profiles:
                locked_profile = locked_benchmark_profiles.get(benchmark.id)
                if locked_profile is None:
                    raise ValueError(
                        f"benchmark profile {benchmark.id!r} is missing from campaign lock"
                    )
                if benchmark_profile.digest() != locked_profile.get("digest"):
                    raise ValueError(
                        f"benchmark profile {benchmark.id!r} changed since this "
                        "campaign was locked"
                    )
            load_kwargs = dict(benchmark.args)
            if benchmark.domain:
                load_kwargs["domain"] = benchmark.domain
            if benchmark.sample.exclude_categories:
                load_kwargs["exclude_categories"] = benchmark.sample.exclude_categories
            if benchmark.sample.task_ids:
                load_kwargs["task_ids"] = benchmark.sample.task_ids
            load_kwargs.setdefault("n", None)
            dataset = ds_entry["load"](**load_kwargs)
            if benchmark.id in locked_selections:
                locked_ids = list(locked_selections[benchmark.id]["task_ids"])
                by_id = {task.task_id: task for task in dataset.tasks}
                missing = set(locked_ids) - set(by_id)
                if missing:
                    raise ValueError(
                        f"locked tasks disappeared from {benchmark.id}: {sorted(missing)[:5]}"
                    )
                selected_tasks = [by_id[task_id] for task_id in locked_ids]
                selection = dict(locked_selections[benchmark.id])
            else:
                selected_dataset, selected = sample_dataset(
                    dataset,
                    n=benchmark.sample.n,
                    seed=benchmark.sample.seed,
                )
                selected_tasks = list(selected_dataset.tasks)
                selection = {
                    "strategy": selected.strategy,
                    "seed": selected.seed,
                    "requested_n": selected.requested_n,
                    "available_n": selected.available_n,
                    "selected_n": selected.selected_n,
                    "task_ids": list(selected.task_ids),
                }
            selected_ids[benchmark.id] = [task.task_id for task in selected_tasks]
            self.tasks[benchmark.id] = [_task_payload(task) for task in selected_tasks]
            spec = grader_for_dataset(benchmark.id)
            configured = list(benchmark.graders)
            if len(configured) > 1:
                raise ValueError(
                    f"benchmark {benchmark.id!r} owns one primary grader; "
                    "multiple graders are no longer supported"
                )
            if configured:
                grader = configured[0]
                accepted_ids = {spec.id, *spec.aliases}
                if grader.id not in accepted_ids:
                    raise ValueError(
                        f"benchmark {benchmark.id!r} uses grader {spec.id!r}; "
                        f"configured id {grader.id!r} is not compatible"
                    )
                grader = grader.model_copy(update={"id": spec.id, "mode": spec.mode})
            else:
                grader = GraderConfig(
                    id=spec.id,
                    mode=spec.mode,
                    required=spec.required,
                )
            graders = [grader]
            self.benchmarks[benchmark.id] = {
                **benchmark.model_dump(mode="json"),
                "profile_digest": benchmark_profile.digest(),
                "timeout_seconds": (
                    self.config.execution.timeout_seconds
                    if self.config.execution.timeout_seconds is not None
                    else benchmark_profile.defaults.run_deadline
                ),
                "graders": [grader.model_dump(mode="json") for grader in graders],
                "selection": selection,
            }

        requirements = {
            name: metadata.get("requirements", {}) for name, metadata in AGENTS.items()
        }
        self.plan = expand_campaign(
            self.config,
            profiles=self.profiles,
            selected_task_ids=selected_ids,
            harness_requirements=requirements,
        )
        isolated_cells = [
            cell
            for cell in self.plan.cells
            if bool(AGENTS[cell.harness].get("isolated"))
        ]
        if isolated_cells:
            isolated_python = (
                self.repo_root
                / "task/agents/autogen_agentchat/.venv/bin/python"
            )
            if not isolated_python.exists():
                raise ValueError(
                    "isolated harness environment is not installed; run: "
                    "uv sync --project task/agents/autogen_agentchat --frozen"
                )
            isolated_env = dict(os.environ)
            isolated_env["PYTHONPATH"] = str(
                self.repo_root / "task/packages/ageneval-task-orchestrator/src"
            )
            check = subprocess.run(
                [
                    str(isolated_python),
                    "-c",
                    (
                        "import autogen_agentchat, ageneval.model.gateway; "
                        "from ageneval.task.orchestrator.executor import _execute_attempt"
                    ),
                ],
                env=isolated_env,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            if check.returncode != 0:
                raise ValueError(
                    "isolated harness environment is incomplete; run: "
                    "uv sync --project task/agents/autogen_agentchat --frozen"
                )
        if self.resume and self.lock.get("campaign_id") != self.plan.campaign_id:
            raise ValueError(
                "resume config.json does not match the campaign_id recorded in lock.json"
            )
        if self.resume and self.run_directory.root.name != self.plan.campaign_id:
            raise ValueError(
                f"resume directory must be named {self.plan.campaign_id!r}"
            )
        if not self.resume and self.run_directory.root.name != self.plan.campaign_id:
            self.run_directory = RunDirectory(
                self.run_directory.root.parent / self.plan.campaign_id
            )

        if not self.resume:
            self.lock = {
                "schema_version": 1,
                "campaign_id": self.plan.campaign_id,
                "source_config": str(self.config_path) if self.config_path else None,
                "git": _git_state(self.repo_root),
                "versions": _versions(),
                "profiles": {
                    name: {
                        "path": str(self.profile_paths[name]),
                        "digest": profile.digest(),
                        "profile": profile.public_dict(),
                    }
                    for name, profile in self.profiles.items()
                },
                "benchmark_profiles": {
                    name: {
                        "path": str(self.benchmark_profile_paths[name]),
                        "digest": profile.digest(),
                        "profile": profile.model_dump(mode="json", exclude_none=False),
                    }
                    for name, profile in self.benchmark_profiles.items()
                },
                "selections": {
                    name: self.benchmarks[name]["selection"] for name in self.benchmarks
                },
                "cells": [cell.__dict__ for cell in self.plan.cells],
                "trials": [trial.__dict__ for trial in self.plan.trials],
                "server": {"datasets": {}, "cells": {}},
            }
            self.run_directory.initialize(
                config=self.config.model_dump(mode="json", exclude_none=False),
                lock=self.lock,
            )
        else:
            for name, profile in self.profiles.items():
                expected = self.lock["profiles"][name]["digest"]
                if profile.digest() != expected:
                    raise ValueError(
                        f"model profile {name!r} changed since this campaign was locked"
                    )
        self._initialize_trial_files()
        return self.plan

    def _initialize_trial_files(self) -> None:
        assert self.plan is not None
        cells = {cell.cell_id: cell for cell in self.plan.cells}
        for trial in self.plan.trials:
            cell = cells[trial.cell_id]
            self.run_directory.write_trial_spec(
                trial.trial_id,
                trial.__dict__,
                {
                    "campaign_id": self.plan.campaign_id,
                    "cell": cell.__dict__,
                    "profile_digest": cell.profile_digest,
                    "benchmark_profile_digest": self.benchmarks[cell.benchmark][
                        "profile_digest"
                    ],
                },
            )

    def dry_run_summary(self) -> dict[str, Any]:
        if self.plan is None:
            self.prepare()
        assert self.plan is not None
        return {
            "campaign_id": self.plan.campaign_id,
            "run_directory": str(self.run_directory.root),
            "cells": [cell.__dict__ for cell in self.plan.cells],
            "trial_count": len(self.plan.trials),
            "selections": {
                name: data["selection"] for name, data in self.benchmarks.items()
            },
        }

    async def run(self, *, rerun_failed: bool = False) -> dict[str, Any]:
        if self.plan is None:
            self.prepare()
        assert self.plan is not None
        with self.run_directory.controller_lock():
            sink = A2ESink()
            status = "failed"
            runtimes: dict[str, ModelRuntime] = {}
            resolved_models: dict[str, ResolvedModel] = {}
            has_sandbox = any(
                task.get("sandbox") is not None
                for tasks in self.tasks.values()
                for task in tasks
            )
            try:
                if has_sandbox and os.environ.get("A2E_SANDBOX_CLEANUP", "1") != "0":
                    from ageneval.task.sandbox import sweep_sandbox_containers

                    removed = await asyncio.to_thread(
                        sweep_sandbox_containers,
                        campaign_id=self.plan.campaign_id,
                        include_image_orphans=False,
                    )
                    if removed:
                        logger.info("removed %d stale sandbox containers", len(removed))
                # Resolve credentials and start optional compatibility middleware
                # before creating Server objects. Resolved values stay in memory.
                for name, profile in self.profiles.items():
                    runtime = ModelRuntime(resolve_model(profile))
                    runtimes[name] = runtime
                    resolved_models[name] = runtime.start()
                self._active_runtimes = runtimes
                server_state = await self._ensure_server_objects(sink)
                await self._upload_pending(sink, server_state)
                await self._run_trial_processes(
                    sink=sink,
                    server_state=server_state,
                    resolved_models=resolved_models,
                    rerun_failed=rerun_failed,
                )
                await self._upload_pending(sink, server_state)
                settled = [
                    bool(
                        result is not None
                        and (
                            result.status == "incompatible"
                            or (result.status in {"completed", "failed"} and result.uploaded)
                        )
                    )
                    for trial in self.plan.trials
                    for result in [self.run_directory.load_trial_result(trial.trial_id)]
                ]
                status = "completed" if all(settled) else "incomplete"
            except (KeyboardInterrupt, asyncio.CancelledError):
                status = "cancelled"
                raise
            finally:
                self.gateway_stats = {
                    name: runtime.metrics() for name, runtime in runtimes.items()
                }
                for runtime in runtimes.values():
                    runtime.close()
                self._active_runtimes = {}
                await sink.close()
                if has_sandbox and os.environ.get("A2E_SANDBOX_CLEANUP", "1") != "0":
                    from ageneval.task.sandbox import sweep_sandbox_containers

                    removed = await asyncio.to_thread(
                        sweep_sandbox_containers,
                        campaign_id=self.plan.campaign_id,
                        include_image_orphans=False,
                    )
                    if removed:
                        logger.info("cleaned %d sandbox containers", len(removed))
                by_cell: dict[str, list[str]] = defaultdict(list)
                for trial in self.plan.trials:
                    by_cell[trial.cell_id].append(trial.trial_id)
                for cell_id, trial_ids in by_cell.items():
                    self.run_directory.summarize_cell(cell_id, trial_ids)
                summary = self.run_directory.summarize(
                    [trial.trial_id for trial in self.plan.trials],
                    status=status,
                    extra={
                        "concurrency": self.concurrency_stats,
                        "runtime": self.runtime_stats,
                        "gateways": self.gateway_stats,
                    },
                )
        return summary

    async def _ensure_server_objects(self, sink: A2ESink) -> dict[str, Any]:
        from ageneval.task.runners import framework_for_agent

        assert self.plan is not None
        state = dict(self.lock.get("server") or {"datasets": {}, "cells": {}})
        state.setdefault("datasets", {})
        state.setdefault("cells", {})
        state = await self._validated_server_state(sink, state)
        for benchmark, tasks in self.tasks.items():
            if benchmark not in state["datasets"]:
                name = f"a2e-{self.plan.campaign_id}-{benchmark}"
                dataset, by_task = await sink.ensure_dataset(
                    name=name,
                    description=f"A2E campaign {self.plan.campaign_id}: {benchmark}",
                    examples=[_dataset_example(task) for task in tasks],
                    expected_task_ids=[task["task_id"] for task in tasks],
                )
                state["datasets"][benchmark] = {
                    "id": dataset.id,
                    "version_id": dataset.version_id,
                    "name": dataset.name,
                    "examples": by_task,
                }
                self.run_directory.update_lock({"server": state})
        for cell in self.plan.cells:
            if cell.cell_id in state["cells"]:
                continue
            dataset = state["datasets"][cell.benchmark]
            name = f"{self.config.name}-{cell.model}-{cell.benchmark}-{cell.harness}-{cell.cell_id[-8:]}"
            metadata = {
                "campaign_id": self.plan.campaign_id,
                "cell_id": cell.cell_id,
                # Standard experiment identity consumed by the UI and generic
                # downstream analysis. Keep the Campaign-specific dimensions
                # below as provenance rather than making consumers infer them.
                "agent_framework": cell.harness,
                "sdk": framework_for_agent(cell.harness),
                "model": self.profiles[cell.model].model,
                "model_profile": cell.model,
                "model_profile_digest": cell.profile_digest,
                "benchmark": cell.benchmark,
                "benchmark_profile_digest": self.benchmarks[cell.benchmark][
                    "profile_digest"
                ],
                "harness": cell.harness,
                "sample": self.benchmarks[cell.benchmark]["selection"],
            }
            experiment = await sink.ensure_experiment(
                dataset_id=dataset["id"],
                dataset_version_id=dataset["version_id"],
                name=name,
                description=f"Campaign cell {cell.cell_id}",
                metadata=metadata,
                repetitions=self.config.repetitions,
            )
            state["cells"][cell.cell_id] = {
                "experiment_id": experiment["id"],
                "project_name": experiment["project_name"],
                "name": name,
            }
            self.run_directory.update_lock({"server": state})
        self.lock["server"] = state
        return state

    async def _validated_server_state(
        self,
        sink: A2ESink,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """Discard Server IDs that belong to a different or reset database."""
        assert self.plan is not None
        datasets = dict(state.get("datasets") or {})
        cells = dict(state.get("cells") or {})
        try:
            for benchmark, locked in datasets.items():
                if benchmark not in self.tasks:
                    raise KeyError(benchmark)
                if not await sink.locked_dataset_exists(
                    dataset_id=str(locked["id"]),
                    version_id=str(locked["version_id"]),
                    expected_examples={
                        str(task_id): str(example_id)
                        for task_id, example_id in dict(locked["examples"]).items()
                    },
                ):
                    raise LookupError(f"dataset {benchmark!r} is missing or changed")

            cells_by_id = {cell.cell_id: cell for cell in self.plan.cells}
            for cell_id, locked in cells.items():
                cell = cells_by_id[cell_id]
                dataset = datasets[cell.benchmark]
                if not await sink.locked_experiment_exists(
                    dataset_id=str(dataset["id"]),
                    campaign_id=self.plan.campaign_id,
                    cell_id=cell_id,
                    experiment_id=str(locked["experiment_id"]),
                ):
                    raise LookupError(
                        f"experiment for Cell {cell_id!r} is missing or changed"
                    )
        except (KeyError, LookupError, TypeError, ValueError) as exc:
            logger.warning("resetting stale Campaign Server IDs: %s", exc)
            state = {"datasets": {}, "cells": {}}
            self.run_directory.update_lock({"server": state})
            self.lock["server"] = state
            return state
        return {"datasets": datasets, "cells": cells}

    async def _upload_one(
        self, sink: A2ESink, state: dict[str, Any], result: TrialResult
    ) -> TrialResult:
        cell = next(cell for cell in self.plan.cells if cell.cell_id == result.cell_id)  # type: ignore[union-attr]
        dataset_state = state["datasets"][cell.benchmark]
        try:
            return await sink.upload_trial(
                result=result,
                experiment_id=state["cells"][cell.cell_id]["experiment_id"],
                dataset_example_id=dataset_state["examples"][result.task_id],
            )
        except Exception as exc:
            logger.exception("upload failed for %s", result.trial_id)
            output = {**result.output, "_upload_error": str(exc)[:1000]}
            retained_status = "failed" if result.status == "failed" else "local_complete"
            return result.model_copy(update={"status": retained_status, "output": output})

    async def _upload_pending(self, sink: A2ESink, state: dict[str, Any]) -> None:
        assert self.plan is not None
        pending: list[TrialResult] = []
        for trial in self.plan.trials:
            result = self.run_directory.load_trial_result(trial.trial_id)
            if (
                result
                and result.status in {"local_complete", "uploading", "failed"}
                and not result.uploaded
            ):
                pending.append(result)
        if not pending:
            return

        queue_: asyncio.Queue[TrialResult | None] = asyncio.Queue(
            maxsize=self.config.execution.queue_capacity
        )

        async def upload_worker() -> None:
            while True:
                result = await queue_.get()
                try:
                    if result is None:
                        return
                    lifecycle = [
                        *result.lifecycle,
                        LifecycleRecord(
                            event=LifecycleEvent.UPLOAD_START,
                            timestamp=datetime.now(timezone.utc),
                            attempt=result.attempt,
                        ),
                    ]
                    uploaded = await self._upload_one(sink, state, result)
                    lifecycle.append(
                        LifecycleRecord(
                            event=LifecycleEvent.UPLOAD_END,
                            timestamp=datetime.now(timezone.utc),
                            attempt=result.attempt,
                        )
                    )
                    self.run_directory.write_trial_result(
                        uploaded.model_copy(update={"lifecycle": lifecycle})
                    )
                finally:
                    queue_.task_done()

        worker_count = min(
            self.config.execution.n_concurrent_uploads,
            len(pending),
        )
        workers = [asyncio.create_task(upload_worker()) for _ in range(worker_count)]
        for result in pending:
            await queue_.put(result)
        for _ in workers:
            await queue_.put(None)
        await queue_.join()
        await asyncio.gather(*workers)

    def _pending_by_cell(self, *, rerun_failed: bool) -> dict[str, list[dict[str, Any]]]:
        assert self.plan is not None
        result: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for trial in self.plan.trials:
            previous = self.run_directory.load_trial_result(trial.trial_id)
            if previous is not None:
                if previous.status == "completed":
                    continue
                if previous.status == "failed" and not rerun_failed:
                    continue
                if previous.status in {"local_complete", "uploading"}:
                    continue
                attempt = previous.attempt + 1
            else:
                attempt = 1
            result[trial.cell_id].append({**trial.__dict__, "attempt": attempt})
        return result

    async def _run_trial_processes(
        self,
        *,
        sink: A2ESink,
        server_state: dict[str, Any],
        resolved_models: dict[str, ResolvedModel],
        rerun_failed: bool,
    ) -> None:
        """Run every Trial attempt in its own OS process.

        The Controller owns scheduling and permits. No harness, SDK, sandbox,
        grader, or telemetry provider is constructed in this process.
        """
        from ageneval.task.runners import AGENTS

        assert self.plan is not None
        pending = self._pending_by_cell(rerun_failed=rerun_failed)
        if not pending:
            return
        cells = {cell.cell_id: cell for cell in self.plan.cells}
        model_limits = {
            f"model:{profile.concurrency.group}": profile.concurrency.max_sessions
            for profile in self.profiles.values()
        }
        limits = {
            "global": self.config.execution.n_concurrent_trials,
            "sandbox": self.config.execution.n_concurrent_sandboxes,
            "grader": self.config.execution.n_concurrent_graders,
            "upload": self.config.execution.n_concurrent_uploads,
            "model:total": (
                self.config.execution.n_concurrent_model_sessions
                or sum(model_limits.values())
            ),
            **model_limits,
        }
        broker = PermitBroker(limits)
        runtime = RuntimeMetrics()
        publish_lock = asyncio.Lock()
        last_publish = 0.0
        trial_ids = [trial.trial_id for trial in self.plan.trials]

        async def publish(*, force: bool = False) -> None:
            nonlocal last_publish
            now = asyncio.get_running_loop().time()
            if not force and now - last_publish < 0.25:
                return
            async with publish_lock:
                now = asyncio.get_running_loop().time()
                if not force and now - last_publish < 0.25:
                    return
                self.concurrency_stats = broker.snapshot()
                self.runtime_stats = runtime.snapshot()
                self.gateway_stats = {
                    name: model_runtime.metrics()
                    for name, model_runtime in self._active_runtimes.items()
                }
                self.run_directory.summarize(
                    trial_ids,
                    status="running",
                    extra={
                        "concurrency": self.concurrency_stats,
                        "runtime": self.runtime_stats,
                        "gateways": self.gateway_stats,
                    },
                )
                last_publish = now

        def resources_for(cell_id: str, event: LifecycleEvent) -> tuple[str, ...]:
            if event == LifecycleEvent.ENVIRONMENT_START:
                return ("sandbox",)
            if event == LifecycleEvent.AGENT_START:
                group = self.profiles[cells[cell_id].model].concurrency.group
                return (f"model:{group}", "model:total")
            if event == LifecycleEvent.VERIFICATION_START:
                return ("grader",)
            return ()

        def released_resources(cell_id: str, event: LifecycleEvent) -> tuple[str, ...]:
            if event == LifecycleEvent.ENVIRONMENT_END:
                return ("sandbox",)
            if event == LifecycleEvent.AGENT_END:
                group = self.profiles[cells[cell_id].model].concurrency.group
                return ("model:total", f"model:{group}")
            if event == LifecycleEvent.VERIFICATION_END:
                return ("grader",)
            return ()

        phase_names = {
            LifecycleEvent.ENVIRONMENT_START: "phase:environment",
            LifecycleEvent.AGENT_START: "phase:agent",
            LifecycleEvent.VERIFICATION_START: "phase:verification",
        }
        phase_end_names = {
            LifecycleEvent.ENVIRONMENT_END: "phase:environment",
            LifecycleEvent.AGENT_END: "phase:agent",
            LifecycleEvent.VERIFICATION_END: "phase:verification",
        }

        async def run_one(trial: dict[str, Any]) -> None:
            cell = cells[trial["cell_id"]]
            owner = f"{cell.cell_id}:{trial['trial_id']}"
            records: list[LifecycleRecord] = []
            held_phases: list[str] = []
            attempt = int(trial.get("attempt", 1))
            started_at = datetime.now(timezone.utc)
            acquired_global = False
            result: TrialResult | None = None

            async def lifecycle(event: LifecycleEvent, event_attempt: int | None) -> None:
                resources = resources_for(cell.cell_id, event)
                if resources:
                    await broker.acquire_many(owner, resources)
                    phase = phase_names[event]
                    runtime.activity(owner, phase, "start")
                    held_phases.append(phase)
                else:
                    resources = released_resources(cell.cell_id, event)
                    if resources:
                        broker.release_many(owner, resources)
                        phase = phase_end_names[event]
                        runtime.activity(owner, phase, "end")
                        if phase in held_phases:
                            held_phases.remove(phase)
                records.append(
                    LifecycleRecord(
                        event=event,
                        timestamp=datetime.now(timezone.utc),
                        attempt=event_attempt,
                    )
                )
                await publish()

            async def cleanup_orphan_sandbox() -> None:
                if self.tasks[cell.benchmark][0].get("sandbox") is None:
                    return
                if os.environ.get("A2E_SANDBOX_CLEANUP", "1") == "0":
                    return
                from ageneval.task.sandbox import sweep_sandbox_containers

                await asyncio.to_thread(
                    sweep_sandbox_containers,
                    campaign_id=self.plan.campaign_id,
                    trial_id=trial["trial_id"],
                    include_image_orphans=False,
                )

            try:
                await broker.acquire(owner, "global")
                acquired_global = True
                records.append(
                    LifecycleRecord(
                        event=LifecycleEvent.START,
                        timestamp=datetime.now(timezone.utc),
                    )
                )
                await publish()
                policy = self.config.execution.retry
                while True:
                    child_payload = {
                        "cell": {
                            **cell.__dict__,
                            "campaign_id": self.plan.campaign_id,
                            "retry": policy.model_dump(mode="json"),
                        },
                        "trial": {
                            "trial_id": trial["trial_id"],
                            "task_id": trial["task_id"],
                            "repetition": trial["repetition"],
                        },
                        "task": next(
                            item
                            for item in self.tasks[cell.benchmark]
                            if item["task_id"] == trial["task_id"]
                        ),
                        "benchmark": self.benchmarks[cell.benchmark],
                        "profile": resolved_models[cell.model].profile.public_dict(),
                        "base_url": resolved_models[cell.model].base_url,
                        "project_name": server_state["cells"][cell.cell_id]["project_name"],
                        "otel_endpoint": os.environ.get("A2E_COLLECTOR_ENDPOINT"),
                        "attempt": attempt,
                        "timeout_seconds": self.benchmarks[cell.benchmark].get(
                            "timeout_seconds"
                        ),
                    }
                    isolated = bool(AGENTS[cell.harness].get("isolated"))
                    python = (
                        str(self.repo_root / "task/agents/autogen_agentchat/.venv/bin/python")
                        if isolated
                        else sys.executable
                    )
                    pythonpath = (
                        str(
                            self.repo_root
                            / "task/packages/ageneval-task-orchestrator/src"
                        )
                        if isolated
                        else ""
                    )

                    def process_event(state: str, pid: int) -> None:
                        runtime.process_event(state, pid)
                        if state != "start":
                            runtime.release_activities(owner)

                    runner = TrialProcessRunner(
                        script=self.repo_root / "task/examples/run_isolated_trial.py",
                        cancellation_grace_seconds=(
                            self.config.execution.cancellation_grace_seconds
                        ),
                        lifecycle=lifecycle,
                        activity=lambda name, state: runtime.activity(
                            owner, name, state
                        ),
                        process_event=process_event,
                    )
                    attempt_dir = (
                        self.run_directory.trial_dir(trial["trial_id"])
                        / "attempts"
                        / str(attempt)
                    )
                    try:
                        result = await runner.run(
                            payload=child_payload,
                            resolved_model=resolved_models[cell.model],
                            python=python,
                            pythonpath=pythonpath,
                            stderr_path=attempt_dir / "stderr.log",
                            result_path=attempt_dir / "process-result.json",
                            # The child enforces the configured task timeout.
                            # Add cleanup grace so it can emit a typed result.
                            timeout_seconds=(
                                self.benchmarks[cell.benchmark]["timeout_seconds"]
                                + self.config.execution.cancellation_grace_seconds
                                if self.benchmarks[cell.benchmark].get("timeout_seconds")
                                is not None
                                else None
                            ),
                        )
                    except asyncio.CancelledError:
                        await cleanup_orphan_sandbox()
                        raise
                    except Exception as exc:
                        runtime.process_crashed()
                        await cleanup_orphan_sandbox()
                        error_type = type(exc).__name__
                        result = TrialResult(
                            trial_id=trial["trial_id"],
                            cell_id=cell.cell_id,
                            task_id=trial["task_id"],
                            repetition=trial["repetition"],
                            attempt=attempt,
                            status="failed",
                            error=str(exc)[:2000],
                            error_type=error_type,
                            retryable=_error_retryable(error_type, policy),
                            started_at=started_at,
                            ended_at=datetime.now(timezone.utc),
                        )
                    result = result.model_copy(update={"lifecycle": list(records)})
                    retry = (
                        result.status == "failed"
                        and result.retryable
                        and attempt <= policy.max_retries
                    )
                    if not retry:
                        break
                    self.run_directory.write_trial_attempt(result)
                    await publish(force=True)
                    wait_seconds = min(
                        policy.max_wait_seconds,
                        policy.min_wait_seconds
                        * (policy.multiplier ** max(0, attempt - 1)),
                    )
                    await asyncio.sleep(wait_seconds)
                    attempt += 1

                assert result is not None
                if result.status in {"local_complete", "failed"}:
                    await broker.acquire(owner, "upload")
                    records.append(
                        LifecycleRecord(
                            event=LifecycleEvent.UPLOAD_START,
                            timestamp=datetime.now(timezone.utc),
                            attempt=attempt,
                        )
                    )
                    try:
                        result = await self._upload_one(sink, server_state, result)
                    finally:
                        broker.release(owner, "upload")
                    records.append(
                        LifecycleRecord(
                            event=LifecycleEvent.UPLOAD_END,
                            timestamp=datetime.now(timezone.utc),
                            attempt=attempt,
                        )
                    )
            except asyncio.CancelledError:
                records.append(
                    LifecycleRecord(
                        event=LifecycleEvent.CANCEL,
                        timestamp=datetime.now(timezone.utc),
                        attempt=attempt,
                    )
                )
                result = TrialResult(
                    trial_id=trial["trial_id"],
                    cell_id=cell.cell_id,
                    task_id=trial["task_id"],
                    repetition=trial["repetition"],
                    attempt=attempt,
                    status="cancelled",
                    error="trial cancelled",
                    error_type="CancelledError",
                    started_at=started_at,
                    ended_at=datetime.now(timezone.utc),
                )
                raise
            finally:
                for phase in list(held_phases):
                    runtime.release_activities(owner)
                    held_phases.remove(phase)
                if acquired_global:
                    broker.release_all(owner)
                    records.append(
                        LifecycleRecord(
                            event=LifecycleEvent.END,
                            timestamp=datetime.now(timezone.utc),
                            attempt=attempt,
                        )
                    )
                if result is not None:
                    self.run_directory.write_trial_result(
                        result.model_copy(
                            update={
                                "lifecycle": list(records),
                                "ended_at": datetime.now(timezone.utc),
                            }
                        )
                    )
                await publish(force=True)

        # A cell window bounds resident configurations while each window is
        # scheduled round-robin. It no longer implies one shared Cell process.
        cell_order = list(
            dict.fromkeys(
                trial.cell_id for trial in self.plan.trials if trial.cell_id in pending
            )
        )
        await publish(force=True)
        try:
            for offset in range(0, len(cell_order), self.config.execution.n_active_cells):
                window = cell_order[
                    offset : offset + self.config.execution.n_active_cells
                ]
                queues = {cell_id: deque(pending[cell_id]) for cell_id in window}
                rotation = deque(window)
                active_tasks: set[asyncio.Task[None]] = set()
                while rotation or active_tasks:
                    while rotation and len(active_tasks) < self.config.execution.queue_capacity:
                        cell_id = rotation.popleft()
                        cell_queue = queues[cell_id]
                        if cell_queue:
                            task = asyncio.create_task(run_one(cell_queue.popleft()))
                            active_tasks.add(task)
                        if cell_queue:
                            rotation.append(cell_id)
                    if active_tasks:
                        done, active_tasks = await asyncio.wait(
                            active_tasks, return_when=asyncio.FIRST_COMPLETED
                        )
                        outcomes = await asyncio.gather(*done, return_exceptions=True)
                        error = next(
                            (
                                outcome
                                for outcome in outcomes
                                if isinstance(outcome, BaseException)
                            ),
                            None,
                        )
                        if error is not None:
                            raise error
        except BaseException:
            tasks = list(locals().get("active_tasks", set()))
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            raise
        finally:
            self.concurrency_stats = broker.snapshot()
            self.runtime_stats = runtime.snapshot()
            await publish(force=True)

    async def _run_workers(
        self,
        *,
        sink: A2ESink,
        server_state: dict[str, Any],
        resolved_models: dict[str, ResolvedModel],
        rerun_failed: bool,
    ) -> None:
        from ageneval.task.runners import AGENTS

        assert self.plan is not None
        pending = self._pending_by_cell(rerun_failed=rerun_failed)
        if not pending:
            return
        context = multiprocessing.get_context("spawn")
        event_queue = context.Queue(maxsize=self.config.execution.queue_capacity * 4)
        cells = {cell.cell_id: cell for cell in self.plan.cells}
        pending_queues = {
            cell_id: deque(items) for cell_id, items in pending.items() if items
        }
        # The order of first appearance in the already round-robin plan is the
        # deterministic Cell rotation order.
        waiting = deque(
            dict.fromkeys(
                trial.cell_id
                for trial in self.plan.trials
                if trial.cell_id in pending_queues
            )
        )
        model_limits = {
            f"model:{profile.concurrency.group}": profile.concurrency.max_sessions
            for profile in self.profiles.values()
        }
        limits = {
            "global": self.config.execution.n_concurrent_trials,
            "sandbox": self.config.execution.n_concurrent_sandboxes,
            "grader": self.config.execution.n_concurrent_graders,
            "upload": self.config.execution.n_concurrent_uploads,
            # An optional Campaign-wide ceiling across independent model pools.
            # With no explicit value it is observational only: the sum of the
            # group ceilings cannot be reduced by this aggregate pool.
            "model:total": (
                self.config.execution.n_concurrent_model_sessions
                or sum(model_limits.values())
            ),
            **model_limits,
        }
        broker = PermitBroker(limits)
        active: dict[str, dict[str, Any]] = {}
        uploads: set[asyncio.Task[Any]] = set()
        upload_errors: list[BaseException] = []
        worker_errors: dict[str, str] = {}
        lifecycle_tasks: dict[str, tuple[str, str, asyncio.Task[None]]] = {}
        cancelling = False
        n_rotation_cells = min(
            self.config.execution.n_active_cells, len(pending_queues)
        )
        cell_quantum = max(
            1,
            math.ceil(
                self.config.execution.n_concurrent_trials / max(1, n_rotation_cells)
            ),
        )

        def upload_done(task: asyncio.Task[Any]) -> None:
            uploads.discard(task)
            if task.cancelled():
                return
            error = task.exception()
            if error is not None:
                upload_errors.append(error)
                logger.error("upload task crashed: %s", error)

        def lifecycle_done(request_id: str, task: asyncio.Task[None]) -> None:
            lifecycle_tasks.pop(request_id, None)
            if task.cancelled():
                return
            error = task.exception()
            if error is not None:
                logger.error("lifecycle request %s crashed: %s", request_id, error)

        def start_next() -> None:
            while waiting and len(active) < self.config.execution.n_active_cells:
                cell_id = waiting.popleft()
                cell = cells[cell_id]
                payload = {
                    "cell": {
                        **cell.__dict__,
                        "campaign_id": self.plan.campaign_id,
                        "retry": self.config.execution.retry.model_dump(mode="json"),
                    },
                    # This IPC-only payload contains the credential. It is never
                    # handed to RunDirectory or logging.
                    "resolved_model": resolved_models[cell.model].model_dump(mode="python"),
                    "project_name": server_state["cells"][cell_id]["project_name"],
                    "otel_endpoint": os.environ.get("A2E_COLLECTOR_ENDPOINT"),
                    "benchmark": self.benchmarks[cell.benchmark],
                    "tasks_by_id": {
                        item["task_id"]: item for item in self.tasks[cell.benchmark]
                    },
                    "timeout_seconds": self.benchmarks[cell.benchmark].get(
                        "timeout_seconds"
                    ),
                    "isolated": bool(AGENTS[cell.harness].get("isolated")),
                    "isolated_python": str(
                        self.repo_root / "task/agents/autogen_agentchat/.venv/bin/python"
                    ),
                    "isolated_script": str(
                        self.repo_root / "task/examples/run_isolated_trial.py"
                    ),
                    "isolated_pythonpath": str(
                        self.repo_root
                        / "task/packages/ageneval-task-orchestrator/src"
                    ),
                }
                command_queue = context.Queue(
                    maxsize=self.config.execution.queue_capacity * 2
                )
                process = context.Process(
                    target=run_cell_worker,
                    args=(payload, command_queue, event_queue),
                    name=f"a2e-{cell_id[-8:]}",
                )
                process.start()
                active[cell_id] = {
                    "process": process,
                    "queue": command_queue,
                    "ready": False,
                    "stopping": False,
                    "assigned": 0,
                    "inflight": {},
                }

        def owner_key(cell_id: str, trial_id: str) -> str:
            return f"{cell_id}:{trial_id}"

        def resources_for(
            cell_id: str, event: LifecycleEvent
        ) -> tuple[str, ...]:
            if event == LifecycleEvent.START:
                return ("global",)
            if event == LifecycleEvent.ENVIRONMENT_START:
                return ("sandbox",)
            if event == LifecycleEvent.AGENT_START:
                group = self.profiles[cells[cell_id].model].concurrency.group
                return (f"model:{group}", "model:total")
            if event == LifecycleEvent.VERIFICATION_START:
                return ("grader",)
            return ()

        def released_resources(
            cell_id: str, event: LifecycleEvent
        ) -> tuple[str, ...]:
            if event == LifecycleEvent.ENVIRONMENT_END:
                return ("sandbox",)
            if event == LifecycleEvent.AGENT_END:
                group = self.profiles[cells[cell_id].model].concurrency.group
                return ("model:total", f"model:{group}")
            if event == LifecycleEvent.VERIFICATION_END:
                return ("grader",)
            return ()

        async def handle_lifecycle(message: dict[str, Any]) -> None:
            request_id = message["request_id"]
            cell_id = message["cell_id"]
            owner = owner_key(cell_id, message["trial_id"])
            event = LifecycleEvent(message["event"])
            response = {"type": "lifecycle_response", "request_id": request_id}
            try:
                resources = resources_for(cell_id, event)
                if resources:
                    await broker.acquire_many(owner, resources)
                else:
                    resources = released_resources(cell_id, event)
                    if resources:
                        broker.release_many(owner, resources)
                    elif event in {LifecycleEvent.CANCEL, LifecycleEvent.END}:
                        broker.release_all(owner)
                response["ok"] = True
            except Exception as exc:
                response.update({"ok": False, "error": str(exc)[:1000]})
            worker = active.get(cell_id)
            if worker is not None and worker["process"].is_alive():
                worker["queue"].put(response)

        def submit_lifecycle(message: dict[str, Any]) -> None:
            request_id = message["request_id"]
            task = asyncio.create_task(handle_lifecycle(message))
            lifecycle_tasks[request_id] = (
                message["cell_id"],
                message["trial_id"],
                task,
            )
            task.add_done_callback(
                lambda completed, item=request_id: lifecycle_done(item, completed)
            )

        async def abandon_lifecycle(message: dict[str, Any]) -> None:
            entry = lifecycle_tasks.pop(message["request_id"], None)
            if entry is not None:
                entry[2].cancel()
                await asyncio.gather(entry[2], return_exceptions=True)
            broker.release_all(owner_key(message["cell_id"], message["trial_id"]))

        def cancel_cell_lifecycle(cell_id: str) -> None:
            for request_id, (request_cell, _trial_id, task) in list(
                lifecycle_tasks.items()
            ):
                if request_cell == cell_id:
                    lifecycle_tasks.pop(request_id, None)
                    task.cancel()
            broker.release_prefix(f"{cell_id}:")

        async def upload_result(result: TrialResult) -> None:
            owner = owner_key(result.cell_id, result.trial_id)
            lifecycle = list(result.lifecycle)
            lifecycle.append(
                LifecycleRecord(
                    event=LifecycleEvent.UPLOAD_START,
                    timestamp=datetime.now(timezone.utc),
                    attempt=result.attempt,
                )
            )
            await broker.acquire(owner, "upload")
            try:
                uploaded = await self._upload_one(sink, server_state, result)
            finally:
                broker.release(owner, "upload")
            lifecycle.append(
                LifecycleRecord(
                    event=LifecycleEvent.UPLOAD_END,
                    timestamp=datetime.now(timezone.utc),
                    attempt=result.attempt,
                )
            )
            self.run_directory.write_trial_result(
                uploaded.model_copy(update={"lifecycle": lifecycle})
            )

        def mark_worker_crash(cell_id: str, error: str, *, cancelled: bool = False) -> None:
            now = datetime.now(timezone.utc)
            worker = active.get(cell_id)
            inflight = list((worker or {}).get("inflight", {}).values())
            for trial in inflight:
                current = self.run_directory.load_trial_result(trial["trial_id"])
                if current is not None and current.status in {
                    "completed",
                    "local_complete",
                    "uploading",
                }:
                    continue
                failed = TrialResult(
                    trial_id=trial["trial_id"],
                    cell_id=cell_id,
                    task_id=trial["task_id"],
                    repetition=trial["repetition"],
                    attempt=trial["attempt"],
                    status="cancelled" if cancelled else "failed",
                    error=error,
                    error_type="CancelledError" if cancelled else "WorkerProcessError",
                    started_at=now,
                    ended_at=now,
                    lifecycle=[
                        LifecycleRecord(
                            event=(
                                LifecycleEvent.CANCEL
                                if cancelled
                                else LifecycleEvent.END
                            ),
                            timestamp=now,
                            attempt=trial["attempt"],
                        )
                    ],
                )
                self.run_directory.write_trial_result(failed)
                if not cancelled:
                    task = asyncio.create_task(upload_result(failed))
                    uploads.add(task)
                    task.add_done_callback(upload_done)

        def dispatch() -> None:
            if not active:
                return
            outstanding = sum(len(worker["inflight"]) for worker in active.values())
            made_progress = True
            while (
                made_progress
                and outstanding < self.config.execution.queue_capacity
            ):
                made_progress = False
                for cell_id, worker in list(active.items()):
                    if outstanding >= self.config.execution.queue_capacity:
                        break
                    if not worker["ready"] or worker["stopping"]:
                        continue
                    cell_pending = pending_queues.get(cell_id)
                    if not cell_pending:
                        if not worker["inflight"]:
                            worker["stopping"] = True
                            worker["queue"].put({"type": "shutdown"})
                        continue
                    if worker["assigned"] >= cell_quantum and waiting:
                        if not worker["inflight"]:
                            worker["stopping"] = True
                            worker["queue"].put({"type": "shutdown"})
                        continue
                    if worker["assigned"] >= cell_quantum and not waiting:
                        worker["assigned"] = 0
                    trial = cell_pending.popleft()
                    worker["inflight"][trial["trial_id"]] = trial
                    worker["assigned"] += 1
                    worker["queue"].put({"type": "run_trial", "trial": trial})
                    outstanding += 1
                    made_progress = True

        async def close_worker(cell_id: str, *, crashed: bool) -> None:
            worker = active.get(cell_id)
            if worker is None:
                return
            process = worker["process"]
            await asyncio.to_thread(process.join, 5)
            if process.is_alive():
                process.terminate()
                await asyncio.to_thread(process.join, 5)
                crashed = True
            if crashed and worker["inflight"]:
                mark_worker_crash(
                    cell_id,
                    worker_errors.pop(
                        cell_id, f"cell worker exited with code {process.exitcode}"
                    ),
                )
            cancel_cell_lifecycle(cell_id)
            worker["queue"].close()
            worker["queue"].join_thread()
            active.pop(cell_id, None)
            if not cancelling and pending_queues.get(cell_id):
                waiting.append(cell_id)
            if not cancelling:
                start_next()
                dispatch()

        async def process_message(message: dict[str, Any]) -> None:
            kind = message.get("type")
            if kind == "lifecycle":
                submit_lifecycle(message)
            elif kind == "lifecycle_abandon":
                await abandon_lifecycle(message)
            elif kind == "worker_ready":
                worker = active.get(message["cell_id"])
                if worker is not None:
                    worker["ready"] = True
                dispatch()
            elif kind == "trial_result":
                result = TrialResult.model_validate(message["result"])
                if message.get("final"):
                    self.run_directory.write_trial_result(result)
                    worker = active.get(result.cell_id)
                    if worker is not None:
                        worker["inflight"].pop(result.trial_id, None)
                    if result.status in {"local_complete", "failed"}:
                        task = asyncio.create_task(upload_result(result))
                        uploads.add(task)
                        task.add_done_callback(upload_done)
                    dispatch()
                else:
                    self.run_directory.write_trial_attempt(result)
            elif kind == "worker_error":
                worker_errors[message["cell_id"]] = (
                    f"{message['error_type']}: {message['error']}"
                )
                logger.error(
                    "cell worker %s failed: %s: %s",
                    message["cell_id"],
                    message["error_type"],
                    message["error"],
                )
            elif kind == "worker_done":
                cell_id = message["cell_id"]
                worker = active.get(cell_id)
                await close_worker(
                    cell_id,
                    crashed=bool(
                        cell_id in worker_errors
                        or (worker and worker["process"].exitcode not in {None, 0})
                    ),
                )

        start_next()
        try:
            dispatch()
            while active or waiting:
                try:
                    message = await asyncio.to_thread(event_queue.get, True, 0.5)
                except queue.Empty:
                    crashed = [
                        cell_id
                        for cell_id, worker in active.items()
                        if worker["process"].exitcode not in {None, 0}
                    ]
                    for cell_id in crashed:
                        await close_worker(cell_id, crashed=True)
                    continue
                await process_message(message)
            if uploads:
                await asyncio.gather(*list(uploads))
            if upload_errors:
                raise RuntimeError(f"{len(upload_errors)} upload task(s) crashed")
        except BaseException:
            # Harbor-style cancellation: stop dispatching, ask every Worker to
            # cancel, continue serving lifecycle cleanup during the grace
            # period, and hard-kill only processes that do not settle.
            cancelling = True
            waiting.clear()
            for worker in active.values():
                if worker["process"].is_alive() and not worker["stopping"]:
                    worker["stopping"] = True
                    worker["queue"].put({"type": "cancel"})
            deadline = (
                asyncio.get_running_loop().time()
                + self.config.execution.cancellation_grace_seconds
            )
            while active and asyncio.get_running_loop().time() < deadline:
                try:
                    message = await asyncio.to_thread(event_queue.get, True, 0.2)
                except queue.Empty:
                    continue
                await process_message(message)
            for cell_id, worker in list(active.items()):
                if worker["process"].is_alive():
                    worker["process"].terminate()
                await asyncio.to_thread(worker["process"].join, 5)
                if worker["inflight"]:
                    mark_worker_crash(
                        cell_id,
                        "controller cancellation grace period expired",
                        cancelled=True,
                    )
                cancel_cell_lifecycle(cell_id)
                worker["queue"].close()
                worker["queue"].join_thread()
                active.pop(cell_id, None)
            raise
        finally:
            self.concurrency_stats = broker.snapshot()
            for _request_id, (_cell_id, _trial_id, task) in list(
                lifecycle_tasks.items()
            ):
                task.cancel()
            if lifecycle_tasks:
                await asyncio.gather(
                    *(item[2] for item in lifecycle_tasks.values()),
                    return_exceptions=True,
                )
            for task in list(uploads):
                if not task.done():
                    task.cancel()
            if uploads:
                await asyncio.gather(*list(uploads), return_exceptions=True)
            event_queue.close()
            event_queue.join_thread()

    async def regrade(self, grader_names: list[str] | None = None) -> dict[str, Any]:
        if self.plan is None:
            self.prepare()
        assert self.plan is not None
        by_cell = {cell.cell_id: cell for cell in self.plan.cells}
        task_maps = {
            benchmark: {task["task_id"]: task for task in tasks}
            for benchmark, tasks in self.tasks.items()
        }
        from ageneval.task.core import TaskInput

        sink = A2ESink()
        runtimes: dict[str, ModelRuntime] = {}
        try:
            resolved_models: dict[str, ResolvedModel] = {}
            for name, profile in self.profiles.items():
                runtime = ModelRuntime(resolve_model(profile))
                runtimes[name] = runtime
                resolved_models[name] = runtime.start()
            state = await self._ensure_server_objects(sink)
            for trial in self.plan.trials:
                result = self.run_directory.load_trial_result(trial.trial_id)
                if result is None or not result.output:
                    continue
                cell = by_cell[trial.cell_id]
                graders = [
                    GraderConfig.model_validate(item)
                    for item in self.benchmarks[cell.benchmark]["graders"]
                    if (not grader_names or item["id"] in grader_names)
                ]
                inline = [grader.id for grader in graders if grader.mode == "inline"]
                if inline:
                    raise ValueError(
                        f"inline graders cannot be regraded without rerunning the agent: {inline}"
                    )
                payload = task_maps[cell.benchmark][trial.task_id]
                task = TaskInput(**payload)
                grades = [
                    await _run_grader(
                        grader,
                        benchmark_id=cell.benchmark,
                        task=task,
                        output=result.output,
                        trace_id=result.trace_id,
                        resolved_model=resolved_models[cell.model],
                    )
                    for grader in graders
                ]
                updated = result.model_copy(
                    update={"grades": grades, "status": "local_complete", "uploaded": False}
                )
                self.run_directory.write_trial_result(updated)
                uploaded = await self._upload_one(sink, state, updated)
                self.run_directory.write_trial_result(uploaded)
        finally:
            for runtime in runtimes.values():
                runtime.close()
            await sink.close()
        return self.run_directory.summarize(
            [trial.trial_id for trial in self.plan.trials], status="completed"
        )


def expand_campaign_id(config: CampaignConfig) -> str:
    from .matrix import stable_id

    return stable_id("campaign", config.model_dump(mode="json", exclude_none=False))
