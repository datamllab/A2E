"""HumanEval loader — HuggingFace ``openai_humaneval``."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterator, Sequence

from ageneval.task.core.dataset import Dataset, TaskInput

logger = logging.getLogger(__name__)


@dataclass
class HumanEvalDataset(Dataset):
    name: str
    tasks: Sequence[TaskInput]

    def __iter__(self) -> Iterator[TaskInput]:
        return iter(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)


def load_humaneval_tasks(split: str = "test", n: int | None = 10) -> HumanEvalDataset:
    """Download HumanEval and convert each problem into a ``TaskInput``.

    The expected output is the canonical solution string; downstream evaluators
    typically grade by running the test cases shipped in ``initial_state``.
    """
    from datasets import load_dataset  # type: ignore

    ds = load_dataset("openai_humaneval", split=split, streaming=False)
    tasks: list[TaskInput] = []
    for i, row in enumerate(ds):
        if n is not None and i >= n:
            break
        prompt = row.get("prompt", "")
        canonical = row.get("canonical_solution", "")
        test_src = row.get("test", "")
        entry_point = row.get("entry_point", "")
        task_id_field = row.get("task_id") or f"humaneval-{i:04d}"
        tasks.append(
            TaskInput(
                task_id=str(task_id_field),
                instruction=(
                    "Complete the following Python function so that it passes "
                    "the hidden test cases:\n\n```python\n" + prompt + "\n```"
                ),
                initial_state={"prompt": prompt, "test": test_src, "entry_point": entry_point},
                expected_outputs=(canonical,),
                metadata={"dataset": "humaneval", "entry_point": entry_point},
            )
        )
    logger.info("HumanEval loader: %s tasks", len(tasks))
    return HumanEvalDataset(name=f"humaneval-{split}", tasks=tasks)
