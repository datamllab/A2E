"""GSM8K loader — HuggingFace ``openai/gsm8k`` (config ``main`` or ``socratic``)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterator, Sequence

from ageneval.task.core.dataset import Dataset, TaskInput

logger = logging.getLogger(__name__)

_FINAL_ANSWER_RE = re.compile(r"####\s*(-?[\d,]+(?:\.\d+)?)")


@dataclass
class GSM8KDataset(Dataset):
    name: str
    tasks: Sequence[TaskInput]

    def __iter__(self) -> Iterator[TaskInput]:
        return iter(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)


def load_gsm8k_tasks(config: str = "main", split: str = "test", n: int | None = 10) -> GSM8KDataset:
    """Download GSM8K from HuggingFace and convert to ``TaskInput`` records."""
    from datasets import load_dataset  # type: ignore

    ds = load_dataset("openai/gsm8k", config, split=split, streaming=False)
    tasks: list[TaskInput] = []
    for i, row in enumerate(ds):
        if n is not None and i >= n:
            break
        question = row.get("question", "")
        answer_full = row.get("answer", "")
        m = _FINAL_ANSWER_RE.search(answer_full or "")
        final = m.group(1).replace(",", "") if m else answer_full.strip().split()[-1]
        tasks.append(
            TaskInput(
                task_id=f"gsm8k-{config}-{split}-{i:05d}",
                instruction=question,
                expected_outputs=(final,),
                metadata={
                    "dataset": "gsm8k",
                    "chain_of_thought": answer_full,
                },
            )
        )
    logger.info("GSM8K loader: %s/%s, %s tasks", config, split, len(tasks))
    return GSM8KDataset(name=f"gsm8k-{config}-{split}", tasks=tasks)
