"""τ²-bench loader — full vendored real task set (sierra tau2-bench).

Tasks come from the vendored ``full_tasks.json.gz`` (domains: retail / airline /
telecom / mock), each with a real user scenario and real expected tool calls.
An optional ``domain`` filters to one domain.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from ageneval.task.core.dataset import Dataset, TaskInput
from ageneval.task.datasets.tau2._vendor import VENDOR_TASKS

logger = logging.getLogger(__name__)


@dataclass
class Tau2Dataset(Dataset):
    name: str
    tasks: Sequence[TaskInput]

    def __iter__(self) -> Iterator[TaskInput]:
        return iter(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)


def load_tau2_tasks(
    *, n: int | None = None, split: str = "test", domain: str | None = None
) -> Tau2Dataset:
    """Load τ²-bench tasks (full real set; optional ``domain`` filter; ``n`` caps)."""
    rows = VENDOR_TASKS
    if domain:
        rows = [t for t in rows if t.get("domain") == domain]
    rows = rows[: (n or len(rows))]
    tasks = [
        TaskInput(
            task_id=f"tau2-{i:05d}-{t['task_id']}",
            instruction=t["instruction"],
            initial_state=t.get("initial_state", {}),
            expected_actions=tuple(t.get("expected_actions", ())),
            expected_outputs=tuple(t.get("expected_outputs", ())),
            metadata={
                "dataset": "tau2",
                "domain": t.get("domain"),
                "source": "upstream-full",
                "source_task_id": str(t["task_id"]),
            },
        )
        for i, t in enumerate(rows)
    ]
    logger.info("τ²-bench loader: %d tasks (domain=%s)", len(tasks), domain or "all")
    return Tau2Dataset(name="tau2", tasks=tasks)
