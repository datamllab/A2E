"""Load vendored Terminal-Bench 2.1 tasks into AEP ``TaskInput`` records.

The official Terminal-Bench 2.1 task definitions are vendored from
``harbor-framework/terminal-bench-2-1`` under ``vendor/tasks/<name>/``.
See ``vendor/SOURCE.md``. Each task ships:

    task.toml           # name, difficulty, [environment].docker_image, timeouts
    instruction.md      # the natural-language task for the agent
    environment/        # Dockerfile (its last WORKDIR = the container cwd)
    tests/              # held-out verifier (test.sh + test_outputs.py)
    solution/           # reference solution (oracle; unused at agent time)

The published ``docker_image`` (Docker Hub, ``alexgshaw/<task>:<date>``) is the
ready-to-run environment — so, exactly like SWE-bench, each task becomes a
``TaskInput`` whose ``sandbox`` points at that image; ``SandboxScoringRunner``
starts the container, lets the agent work, then the dataset's ``score`` hook runs
the held-out tests.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ageneval.task.core.dataset import Dataset, TaskInput

logger = logging.getLogger(__name__)

_WORKDIR_RE = re.compile(r"^\s*WORKDIR\s+(\S+)", re.MULTILINE)
_DEFAULT_WORKDIR = "/app"
_DATASET_NAME = "terminal-bench-2.1"
_SOURCE_COMMIT = "5c8eadf1f393183288fa08b8f73ca9a469cc5e00"
_VERIFIER_CACHE_VOLUMES = (
    "aep-tb21-uv-cache-v1:/root/.cache/uv",
    "aep-tb21-uv-data-v1:/root/.local/share/uv",
)


def _tasks_dir() -> Path:
    """Absolute path to the vendored ``tasks/`` directory (package data)."""
    return Path(__file__).resolve().parent / "vendor" / "tasks"


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib  # py3.11+
    except ModuleNotFoundError:  # pragma: no cover - py3.10 fallback
        import tomli as tomllib  # type: ignore
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def _parse_workdir(task_dir: Path) -> str:
    """Return the container working dir = the last ``WORKDIR`` in the Dockerfile."""
    dockerfile = task_dir / "environment" / "Dockerfile"
    if not dockerfile.exists():
        return _DEFAULT_WORKDIR
    text = dockerfile.read_text(encoding="utf-8", errors="ignore")
    matches = _WORKDIR_RE.findall(text)
    return matches[-1] if matches else _DEFAULT_WORKDIR


def _local_images() -> set[str]:
    """Set of docker image tags present locally (best-effort; empty on any error)."""
    import shutil
    import subprocess

    if shutil.which("docker") is None:
        return set()
    try:
        out = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return set()
    return {ln.strip() for ln in out.stdout.splitlines() if ln.strip()}


def list_task_names() -> list[str]:
    """Sorted names of all vendored Terminal-Bench 2.1 tasks."""
    base = _tasks_dir()
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if (p / "task.toml").is_file())


@dataclass
class TerminalBench21Dataset(Dataset):
    """A concrete ``Dataset`` of Terminal-Bench 2.1 tasks."""

    name: str
    tasks: Sequence[TaskInput]

    def __iter__(self) -> Iterator[TaskInput]:
        return iter(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)


def _build_task(task_dir: Path) -> TaskInput | None:
    """Convert one vendored task dir into a ``TaskInput`` (or None if malformed)."""
    name = task_dir.name
    toml = _load_toml(task_dir / "task.toml")
    env = toml.get("environment", {}) or {}
    md = toml.get("metadata", {}) or {}
    image = env.get("docker_image")
    if not image:
        logger.warning("%s: task %s has no docker_image; skipping", _DATASET_NAME, name)
        return None
    instruction = (task_dir / "instruction.md").read_text(encoding="utf-8", errors="ignore").strip()
    workdir = _parse_workdir(task_dir)
    verifier_timeout = float((toml.get("verifier", {}) or {}).get("timeout_sec", 900.0))
    return TaskInput(
        task_id=name,
        instruction=instruction,
        initial_state={},
        expected_outputs=(),
        metadata={
            "dataset": _DATASET_NAME,
            "tb_version": "2.1",
            "tb_source_commit": _SOURCE_COMMIT,
            "tb_task": name,
            "tb_workdir": workdir,
            "tb_image": str(image),
            "difficulty": str(md.get("difficulty", "")),
            "category": str(md.get("category", "")),
            "environment_cpus": env.get("cpus"),
            "environment_memory_mb": env.get("memory_mb"),
            "environment_storage_mb": env.get("storage_mb"),
            "environment_gpus": env.get("gpus"),
            "environment_allow_internet": env.get("allow_internet"),
            "verifier_timeout_sec": verifier_timeout,
        },
        sandbox={
            "type": "docker",
            "config": {
                "image": str(image),
                "cwd": workdir,
                "pull": True,
                # Official verifiers run uvx with the same pinned dependencies.
                # Named volumes cache only uv downloads across fresh task
                # containers. Task files, held-out tests, and rewards stay
                # isolated in each container.
                "volumes": list(_VERIFIER_CACHE_VOLUMES),
            },
        },
    )


def _safe_build(task_dir: Path) -> TaskInput | None:
    try:
        return _build_task(task_dir)
    except Exception as exc:
        logger.warning("%s: failed to load task %s: %s", _DATASET_NAME, task_dir.name, exc)
        return None


def load_terminal_bench_2_1_tasks(
    n: int | None = 1,
    task_ids: Sequence[str] | None = None,
) -> TerminalBench21Dataset:
    """Load vendored Terminal-Bench 2.1 tasks into ``TaskInput`` records.

    Args:
        n: Cap on number of tasks when ``task_ids`` is not given (``None`` = all).
            With no explicit ids, tasks whose docker image is already pulled
            locally are preferred (so a demo/test "just works" without a fresh
            multi-GB pull), falling back to alphabetical order.
        task_ids: If given, load exactly these task names (ignoring ``n``).

    Returns:
        A ``TerminalBench21Dataset`` ready to feed ``SandboxScoringRunner``.

    Raises:
        FileNotFoundError: no vendored tasks are present.
    """
    base = _tasks_dir()
    available = list_task_names()
    if not available:
        raise FileNotFoundError(f"no vendored {_DATASET_NAME} tasks found under {base}")

    if task_ids:
        missing = sorted(set(task_ids) - set(available))
        if missing:
            logger.warning("%s: unknown task ids skipped: %s", _DATASET_NAME, missing)
        built = [(t, _safe_build(base / t)) for t in task_ids if t in available]
    else:
        built = [(t, _safe_build(base / t)) for t in available]
        built = [(t, ti) for t, ti in built if ti is not None]
        # Prefer locally-cached images so a no-pin run avoids a fresh multi-GB pull.
        if n is not None:
            local = _local_images()
            if local:
                cached = [(t, ti) for t, ti in built if str(ti.metadata.get("tb_image")) in local]
                rest = [(t, ti) for t, ti in built if str(ti.metadata.get("tb_image")) not in local]
                if cached:
                    logger.info(
                        "%s: preferring locally-cached task(s): %s",
                        _DATASET_NAME,
                        [t for t, _ in cached][:n],
                    )
                    built = cached + rest
        if n is not None:
            built = built[:n]

    tasks = [ti for _, ti in built if ti is not None]
    logger.info(
        "Terminal-Bench 2.1 loader: %s tasks (%s)",
        len(tasks),
        [t.task_id for t in tasks],
    )
    return TerminalBench21Dataset(name=_DATASET_NAME, tasks=tasks)


def setup_terminal_bench_2_1(task: TaskInput, sandbox) -> None:
    """SandboxScoringRunner setup hook. The published image is ready-to-run, so
    no preparation is needed before the agent starts. Kept as a uniform call site.
    """
    return None
