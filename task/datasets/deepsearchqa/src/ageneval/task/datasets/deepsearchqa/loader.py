"""DeepSearchQA loader — HuggingFace ``google/deepsearchqa`` (split ``eval``)."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from ageneval.task.core.dataset import Dataset, TaskInput
from ageneval.task.datasets.deepsearchqa._vendor import VENDOR_TASKS

logger = logging.getLogger(__name__)

_HF_ID = "google/deepsearchqa"
_DEFAULT_SPLIT = "eval"


@dataclass
class DeepSearchQADataset(Dataset):
    name: str
    tasks: Sequence[TaskInput]

    def __iter__(self) -> Iterator[TaskInput]:
        return iter(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)


def _to_task(
    *,
    task_id: str,
    problem: str,
    answer: str,
    category: str,
    answer_type: str,
    source: str = "upstream",
) -> TaskInput:
    return TaskInput(
        task_id=task_id,
        instruction=str(problem or "").strip(),
        initial_state={"answer_type": answer_type, "problem_category": category},
        expected_actions=({"name": "web_search"},),
        expected_outputs=(str(answer or "").strip(),) if answer else (),
        metadata={
            "dataset": "deepsearchqa",
            "problem_category": category,
            "answer_type": answer_type,
            "source": source,
        },
    )


def load_deepsearchqa_tasks(
    *,
    hf_id: str | None = _HF_ID,
    split: str = _DEFAULT_SPLIT,
    n: int | None = None,
) -> DeepSearchQADataset:
    """Load DeepSearchQA. Falls back to the vendored sample if HF is unreachable.

    ``answer_type`` is stored on the task for the evaluator only — the binding
    never puts it in the agent prompt (dataset-card requirement).
    """
    if os.environ.get("A2E_DEEPSEARCH_VENDOR", "0") == "1":
        return _load_vendor(n=n)
    if hf_id:
        try:
            from datasets import load_dataset

            ds = load_dataset(hf_id, split=split, streaming=False)
            tasks: list[TaskInput] = []
            for i, row in enumerate(ds):
                if n is not None and i >= n:
                    break
                problem = row.get("problem") or row.get("question") or ""
                answer = row.get("answer") or ""
                category = str(row.get("problem_category") or "")
                answer_type = str(row.get("answer_type") or "Single Answer")
                tasks.append(
                    _to_task(
                        task_id=f"deepsearchqa-{split}-{i:04d}",
                        problem=str(problem),
                        answer=str(answer),
                        category=category,
                        answer_type=answer_type,
                    )
                )
            if tasks:
                logger.info("DeepSearchQA (hf %s/%s): %d tasks", hf_id, split, len(tasks))
                return DeepSearchQADataset(name=f"deepsearchqa-{split}", tasks=tasks)
        except Exception as exc:  # noqa: BLE001
            logger.warning("DeepSearchQA HF load failed (%s) — falling back to vendor", exc)
    return _load_vendor(n=n)


def _load_vendor(*, n: int | None) -> DeepSearchQADataset:
    raw = VENDOR_TASKS[: (n or len(VENDOR_TASKS))]
    tasks = [
        _to_task(
            task_id=t["task_id"],
            problem=t["problem"],
            answer=t["answer"],
            category=t["problem_category"],
            answer_type=t["answer_type"],
            source="vendor",
        )
        for t in raw
    ]
    return DeepSearchQADataset(name="deepsearchqa-vendor", tasks=tasks)
