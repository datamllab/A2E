"""MMLU loader — fetch from HuggingFace ``cais/mmlu``."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterator, Sequence

from ageneval.task.core.dataset import Dataset, TaskInput

logger = logging.getLogger(__name__)

_LETTERS = ("A", "B", "C", "D")


@dataclass
class MMLUDataset(Dataset):
    name: str
    tasks: Sequence[TaskInput]

    def __iter__(self) -> Iterator[TaskInput]:
        return iter(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)


def load_mmlu_tasks(subset: str = "all", split: str = "test", n: int | None = 10) -> MMLUDataset:
    """Download MMLU from HuggingFace and convert to ``TaskInput`` records.

    Args:
        subset: ``"all"`` for the union of all 57 subjects, or a specific subject name
            (e.g. ``"abstract_algebra"``).
        split: ``"test"`` or ``"validation"`` or ``"dev"``.
        n: cap on the number of examples; ``None`` = full split.
    """
    from datasets import load_dataset  # type: ignore

    ds = load_dataset("cais/mmlu", subset, split=split, streaming=False)
    tasks: list[TaskInput] = []
    for i, row in enumerate(ds):
        if n is not None and i >= n:
            break
        choices = row.get("choices") or []
        answer_idx = int(row.get("answer", 0))
        answer_letter = _LETTERS[answer_idx] if 0 <= answer_idx < 4 else "?"
        instruction = (
            f"Question: {row.get('question', '')}\n"
            + "\n".join(f"{_LETTERS[i]}. {c}" for i, c in enumerate(choices))
        )
        tasks.append(
            TaskInput(
                task_id=f"mmlu-{subset}-{split}-{i:05d}",
                instruction=instruction,
                expected_outputs=(answer_letter,),
                metadata={"subject": row.get("subject", subset), "dataset": "mmlu"},
            )
        )
    logger.info("MMLU loader: %s/%s, %s tasks", subset, split, len(tasks))
    return MMLUDataset(name=f"mmlu-{subset}-{split}", tasks=tasks)
