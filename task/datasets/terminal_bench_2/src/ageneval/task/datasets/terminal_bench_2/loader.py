"""Load vendored Terminal-Bench 2.0 tasks into A2E ``TaskInput`` records.

Terminal-Bench 2.0 (laude-institute/terminal-bench-2) is **not** on PyPI / HF, so
its task definitions are vendored under ``vendor/tasks/<name>/`` (Apache-2.0; see
``vendor/SOURCE.md``). Each task ships:

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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence

from ageneval.task.core.dataset import Dataset, TaskInput

logger = logging.getLogger(__name__)

_WORKDIR_RE = re.compile(r"^\s*WORKDIR\s+(\S+)", re.MULTILINE)
_DEFAULT_WORKDIR = "/app"


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
    except Exception:  # noqa: BLE001
        return set()
    return {ln.strip() for ln in out.stdout.splitlines() if ln.strip()}


def list_task_names() -> list[str]:
    """Sorted names of all vendored Terminal-Bench 2 tasks."""
    base = _tasks_dir()
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if (p / "task.toml").is_file())


@dataclass
class TerminalBench2Dataset(Dataset):
    """A concrete ``Dataset`` of Terminal-Bench 2.0 tasks."""

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
        logger.warning("terminal-bench-2: task %s has no docker_image; skipping", name)
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
            "dataset": "terminal-bench-2",
            "tb_task": name,
            "tb_workdir": workdir,
            "tb_image": str(image),
            "difficulty": str(md.get("difficulty", "")),
            "category": str(md.get("category", "")),
            "verifier_timeout_sec": verifier_timeout,
        },
        sandbox={"type": "docker", "config": {"image": str(image), "cwd": workdir, "pull": True}},
    )


def _safe_build(task_dir: Path) -> TaskInput | None:
    try:
        return _build_task(task_dir)
    except Exception as exc:  # noqa: BLE001
        logger.warning("terminal-bench-2: failed to load task %s: %s", task_dir.name, exc)
        return None


def load_terminal_bench_2_tasks(
    n: int | None = 1,
    task_ids: Sequence[str] | None = None,
) -> TerminalBench2Dataset:
    """Load vendored Terminal-Bench 2.0 tasks into ``TaskInput`` records.

    Args:
        n: Cap on number of tasks when ``task_ids`` is not given (``None`` = all).
            With no explicit ids, tasks whose docker image is already pulled
            locally are preferred (so a demo/test "just works" without a fresh
            multi-GB pull), falling back to alphabetical order.
        task_ids: If given, load exactly these task names (ignoring ``n``).

    Returns:
        A ``TerminalBench2Dataset`` ready to feed ``SandboxScoringRunner``.

    Raises:
        FileNotFoundError: no vendored tasks are present.
    """
    base = _tasks_dir()
    available = list_task_names()
    if not available:
        raise FileNotFoundError(f"no vendored terminal-bench-2 tasks found under {base}")

    if task_ids:
        missing = sorted(set(task_ids) - set(available))
        if missing:
            logger.warning("terminal-bench-2: unknown task ids skipped: %s", missing)
        built = [(t, _safe_build(base / t)) for t in task_ids if t in available]
    else:
        built = [(t, _safe_build(base / t)) for t in available]
        built = [(t, ti) for t, ti in built if ti is not None]
        # Prefer locally-cached images so a no-pin run avoids a fresh multi-GB pull
        # (the docker daemon proxy here cannot reach registry-1.docker.io).
        local = _local_images()
        if local:
            cached = [(t, ti) for t, ti in built if str(ti.metadata.get("tb_image")) in local]
            rest = [(t, ti) for t, ti in built if str(ti.metadata.get("tb_image")) not in local]
            if cached:
                logger.info(
                    "terminal-bench-2: preferring locally-cached task(s): %s",
                    [t for t, _ in cached][: (n or 8)],
                )
                built = cached + rest
        if n is not None:
            built = built[:n]

    tasks = [ti for _, ti in built if ti is not None]
    logger.info("Terminal-Bench 2 loader: %s tasks (%s)", len(tasks), [t.task_id for t in tasks])
    return TerminalBench2Dataset(name="terminal-bench-2", tasks=tasks)


def setup_terminal_bench_2(task: TaskInput, sandbox) -> None:
    """SandboxScoringRunner setup hook. The published image is ready-to-run, so
    no preparation is needed before the agent starts. Kept as a uniform call site.
    """
    return None
