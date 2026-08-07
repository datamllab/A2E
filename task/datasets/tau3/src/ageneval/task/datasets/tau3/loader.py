"""τ³-bench loader — vendored real TEXT-task sample (voice modality excluded).

τ³-bench (sierra-research tau2-bench @ dev/tau3) adds a full-duplex *voice*
modality on top of τ²-bench. Per integration scope, A2E uses the **text**
tool-agent-user tasks only — the audio (``tasks_voice.json`` / ``data/voice``)
is downloaded upstream but deliberately NOT used here. Tasks come from the
vendored sample extracted from the official dev/tau3 domains' ``tasks.json``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from ageneval.task.core.dataset import Dataset, TaskInput
from ageneval.task.datasets.tau3._vendor import VENDOR_TASKS

logger = logging.getLogger(__name__)


@dataclass
class Tau3Dataset(Dataset):
    """A concrete ``Dataset`` of τ³-bench text tasks."""

    name: str
    tasks: Sequence[TaskInput]

    def __iter__(self) -> Iterator[TaskInput]:
        return iter(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)


def load_tau3_tasks(*, n: int | None = None, split: str = "test", domain: str | None = None) -> Tau3Dataset:
    """Load τ³-bench TEXT tasks (voice modality intentionally excluded).

    Args:
        n: Cap on number of tasks (``None`` = all vendored tasks).
        split: Accepted for interface parity with other loaders (ignored — the
            vendored sample is a single set).

    Returns:
        A ``Tau3Dataset`` of real dev/tau3 text tasks with their expected tool
        actions.
    """
    rows = VENDOR_TASKS
    if domain:
        rows = [t for t in rows if t.get("domain") == domain]
    rows = rows[: (n or len(rows))]
    tasks = [
        TaskInput(
            task_id=f"tau3-{i:05d}-{t['task_id']}",
            instruction=t["instruction"],
            initial_state=t.get("initial_state", {}),
            expected_actions=tuple(t.get("expected_actions", ())),
            expected_outputs=tuple(t.get("expected_outputs", ())),
            metadata={
                "dataset": "tau3",
                "domain": t.get("domain"),
                "source": "upstream-full",
                "source_task_id": str(t["task_id"]),
                "modality": "text",
            },
        )
        for i, t in enumerate(rows)
    ]
    logger.info("τ³-bench loader: %d text tasks (voice excluded, domain=%s)", len(tasks), domain or "all")
    return Tau3Dataset(name="tau3", tasks=tasks)
