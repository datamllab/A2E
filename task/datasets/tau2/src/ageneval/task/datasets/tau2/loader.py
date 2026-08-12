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


_LIVE_DOMAINS = frozenset({"retail", "airline"})


def load_tau2_tasks(
    *, n: int | None = None, split: str = "test", domain: str | None = "retail"
) -> Tau2Dataset:
    """Load τ²-bench tasks.

    Default ``domain='retail'``. The live tool environment only implements
    retail/airline; telecom/mock tasks would otherwise be paired with the
    retail wiki (the original domain-mismatch bug).
    """
    rows = VENDOR_TASKS
    resolved = domain or "retail"
    if resolved == "all":
        rows = [t for t in rows if t.get("domain") in _LIVE_DOMAINS]
    else:
        rows = [t for t in rows if t.get("domain") == resolved]
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
    logger.info("τ²-bench loader: %d tasks (domain=%s)", len(tasks), resolved)
    return Tau2Dataset(name="tau2", tasks=tasks)
