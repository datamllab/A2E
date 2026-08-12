"""Load τ-bench tasks into A2E ``TaskInput`` records.

Resolution order:
    1. If the upstream ``tau_bench`` package is importable, use it.
    2. Otherwise fall back to the small vendored sample in ``_vendor``.

Both paths return a uniform ``TauBenchDataset``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Literal

from ageneval.task.core.dataset import Dataset, TaskInput
from ageneval.task.datasets.tau_bench._vendor import VENDOR_TASKS

logger = logging.getLogger(__name__)

Domain = Literal["retail", "airline"]


@dataclass
class TauBenchDataset(Dataset):
    """A concrete ``Dataset`` of τ-bench tasks."""

    name: str
    domain: Domain
    tasks: Sequence[TaskInput]

    def __iter__(self) -> Iterator[TaskInput]:
        return iter(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)


def load_tau_bench_tasks(
    domain: Domain = "retail",
    n: int | None = None,
    source: Literal["auto", "upstream", "vendor"] = "auto",
) -> TauBenchDataset:
    """Load τ-bench tasks.

    Args:
        domain: ``retail`` or ``airline``.
        n: Optional cap on the number of tasks returned.
        source: ``auto`` tries upstream first, then vendor.

    Returns:
        A ``TauBenchDataset`` ready to feed an ``ExperimentRunner``.
    """
    if source in ("auto", "upstream"):
        upstream_tasks = _try_load_upstream(domain)
        if upstream_tasks is not None:
            tasks = upstream_tasks
            mode = "upstream"
        elif source == "upstream":
            raise RuntimeError(
                "tau-bench upstream package is not installed; "
                "install with `uv pip install --extra upstream ageneval-task-tau-bench`."
            )
        else:
            tasks = _load_vendor(domain)
            mode = "vendor"
    else:
        tasks = _load_vendor(domain)
        mode = "vendor"

    if n is not None:
        tasks = tasks[:n]
    logger.info("τ-bench loader: %s domain, %s tasks (%s)", domain, len(tasks), mode)
    return TauBenchDataset(name=f"tau-bench-{domain}-{mode}", domain=domain, tasks=tasks)


def _load_vendor(domain: Domain) -> list[TaskInput]:
    raw = VENDOR_TASKS.get(domain, [])
    return [
        TaskInput(
            task_id=t["task_id"],
            instruction=t["instruction"],
            initial_state=t.get("initial_state", {}),
            expected_actions=tuple(t.get("expected_actions", ())),
            expected_outputs=tuple(t.get("expected_outputs", ())),
            metadata={"domain": domain, "source": "upstream-full"},
        )
        for t in raw
    ]


def _try_load_upstream(domain: Domain) -> list[TaskInput] | None:
    """Best-effort import of the upstream ``tau-bench`` package.

    Returns ``None`` if the package isn't installed or the import shape
    doesn't match — both are non-fatal; callers fall back to the vendor.
    """
    try:
        import tau_bench  # type: ignore  # noqa: F401
    except ImportError:
        return None

    # Upstream's interface has changed across versions; this is a best-effort
    # mapping that tolerates partial breakage and degrades to vendor mode.
    try:
        from tau_bench.envs import load_tasks  # type: ignore
    except Exception:
        logger.warning("Upstream tau_bench found but `load_tasks` is missing")
        return None

    try:
        raw_tasks = load_tasks(domain)  # type: ignore
    except Exception as exc:
        logger.warning("Upstream tau_bench failed to load %s tasks: %s", domain, exc)
        return None

    out: list[TaskInput] = []
    for i, t in enumerate(raw_tasks):
        out.append(
            TaskInput(
                task_id=getattr(t, "task_id", None) or f"{domain}-upstream-{i:04d}",
                instruction=getattr(t, "instruction", "") or getattr(t, "user_input", ""),
                initial_state=getattr(t, "initial_state", {}) or {},
                expected_actions=tuple(getattr(t, "actions", ()) or ()),
                expected_outputs=tuple(getattr(t, "outputs", ()) or ()),
                metadata={"domain": domain, "source": "upstream"},
            )
        )
    return out
